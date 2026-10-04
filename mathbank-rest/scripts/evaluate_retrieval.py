#!/usr/bin/env python3
"""Retrieval evaluation harness — Precision@K / Recall@K / MRR / nDCG@K.

Runs each case in scripts/golden_queries.py against a live mathbank-rest
instance (black-box, over HTTP, same as any real client) and scores
`/v1/search/problems` results against a *derived* ground truth: every problem
tagged with the case's concept/technique slug (per knowledge.problem_concept /
problem_technique), optionally narrowed by competition.

This is intentionally black-box and independent of the search implementation
so it keeps working across `vector_search.py` rewrites (e.g. it caught the
pre-filter-vs-post-filter regression class of bug described in
mathematics_tutor_db_plan/agent/11_hybrid_rag_execution.md, had it existed then).

Usage:
    mathbank-rest/.venv/bin/python scripts/evaluate_retrieval.py
    mathbank-rest/.venv/bin/python scripts/evaluate_retrieval.py --base-url http://127.0.0.1:8000 --k 10

Exit code is always 0 (report-only) unless --fail-under is given, because the
ground truth itself is LLM-classification-derived, not hand-labeled — see
golden_queries.py's docstring. Use --fail-under in CI once a case set has been
promoted to hand-verified (track that promotion in the output table's
"ground_truth" column, currently always "derived").
"""
from __future__ import annotations

import argparse
import csv
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from golden_queries import GOLDEN_CASES, GoldenCase  # noqa: E402


def fetch_ground_truth(client: httpx.Client, case: GoldenCase) -> set[str]:
    if case.concept_slug:
        path = f"/v1/concepts/{case.concept_slug}/problems"
    elif case.technique_slug:
        path = f"/v1/techniques/{case.technique_slug}/problems"
    else:
        raise ValueError(f"case {case.name!r} has neither concept_slug nor technique_slug")
    codes: set[str] = set()
    offset = 0
    page_size = 200
    while True:
        resp = client.get(path, params={"limit": page_size, "offset": offset})
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            break
        codes.update(r["canonical_code"] for r in rows)
        if len(rows) < page_size:
            break
        offset += page_size
    if case.competition:
        # Ground truth isn't competition-scoped by that endpoint, so filter client-side
        # using the same /v1/problems endpoint (which does support competition=).
        comp_codes: set[str] = set()
        offset = 0
        while True:
            comp_resp = client.get(
                "/v1/problems",
                params={"competition": case.competition, "limit": page_size, "offset": offset},
            )
            comp_resp.raise_for_status()
            comp_rows = comp_resp.json()
            if not comp_rows:
                break
            comp_codes.update(r["canonical_code"] for r in comp_rows)
            if len(comp_rows) < page_size:
                break
            offset += page_size
        codes &= comp_codes
    return codes


def run_search(client: httpx.Client, case: GoldenCase, k: int) -> list[str]:
    body: dict = {"query": case.query, "limit": k}
    if case.competition:
        body["filters"] = {"competition": case.competition}
    resp = client.post("/v1/search/problems", json=body)
    resp.raise_for_status()
    results = resp.json()["results"]
    return [r["canonical_code"] for r in results]


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    return sum(1 for code in top_k if code in relevant) / len(top_k)


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    top_k = retrieved[:k]
    return sum(1 for code in top_k if code in relevant) / len(relevant)


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for i, code in enumerate(retrieved, start=1):
        if code in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Binary relevance nDCG@K (every relevant doc has gain 1)."""
    top_k = retrieved[:k]
    dcg = sum(
        1.0 / math.log2(i + 1) for i, code in enumerate(top_k, start=1) if code in relevant
    )
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=Path(__file__).parent, text=True
        ).strip()
    except Exception:
        return "unknown"


def append_history(log_file: Path, rows: list[dict], k: int) -> None:
    """Append one row per case per run, so precision/recall can be trended over
    time (git sha + UTC timestamp) rather than only seen in the console table.
    One append-only CSV, not a DB table — this is a dev/CI diagnostic, not
    product data, so it doesn't need its own schema/migration.
    """
    is_new = not log_file.exists()
    run_at = datetime.now(timezone.utc).isoformat()
    sha = _git_sha()
    with log_file.open("a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(
                ["run_at", "git_sha", "k", "case", "relevant_count", "retrieved_count",
                 "precision_at_k", "recall_at_k", "mrr", "ndcg_at_k"]
            )
        for r in rows:
            writer.writerow(
                [run_at, sha, k, r["name"], r["relevant_count"], r["retrieved_count"],
                 f"{r['precision@k']:.4f}", f"{r['recall@k']:.4f}", f"{r['mrr']:.4f}",
                 f"{r['ndcg@k']:.4f}"]
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="exit 1 if mean Recall@K across all cases is below this threshold",
    )
    parser.add_argument(
        "--log-file",
        default=str(Path(__file__).parent.parent / "eval_history.csv"),
        help="CSV file to append this run's per-case metrics to (set to '' to disable)",
    )
    args = parser.parse_args()

    rows = []
    with httpx.Client(base_url=args.base_url, timeout=30.0) as client:
        for case in GOLDEN_CASES:
            relevant = fetch_ground_truth(client, case)
            retrieved = run_search(client, case, args.k)
            rows.append(
                {
                    "name": case.name,
                    "ground_truth": "derived",
                    "relevant_count": len(relevant),
                    "retrieved_count": len(retrieved),
                    "precision@k": precision_at_k(retrieved, relevant, args.k),
                    "recall@k": recall_at_k(retrieved, relevant, args.k),
                    "mrr": reciprocal_rank(retrieved, relevant),
                    "ndcg@k": ndcg_at_k(retrieved, relevant, args.k),
                }
            )

    header = f"{'case':28} {'rel':>5} {'ret':>5} {'P@K':>6} {'R@K':>6} {'MRR':>6} {'nDCG@K':>8}"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r['name']:28} {r['relevant_count']:>5} {r['retrieved_count']:>5} "
            f"{r['precision@k']:>6.2f} {r['recall@k']:>6.2f} {r['mrr']:>6.2f} {r['ndcg@k']:>8.2f}"
        )

    mean_recall = sum(r["recall@k"] for r in rows) / len(rows)
    mean_precision = sum(r["precision@k"] for r in rows) / len(rows)
    print("-" * len(header))
    print(f"mean precision@{args.k}={mean_precision:.3f}  mean recall@{args.k}={mean_recall:.3f}")

    if args.log_file:
        log_path = Path(args.log_file)
        append_history(log_path, rows, args.k)
        print(f"appended {len(rows)} rows to {log_path} (trend tracking across runs)")

    if args.fail_under is not None and mean_recall < args.fail_under:
        print(f"FAIL: mean recall@{args.k} {mean_recall:.3f} < threshold {args.fail_under}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
