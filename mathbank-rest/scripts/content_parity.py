#!/usr/bin/env python3
"""Content read-model parity: PostgreSQL (read-only) against ``mb-content`` (requirement 71 WP4 gate: 0 diffs).

    set -a; . ../mathbank-graph/remote.env; set +a          # NEON_PG_HOST / DATABASE / USER / PASSWORD (read-only use)
    python scripts/content_parity.py --env dev                         # 5 % sampled hash rebuild, every type
    python scripts/content_parity.py --env dev --full --json > parity.json
    python scripts/content_parity.py --env dev --types PROBLEM STEP --include-vectors

Two sources of truth for what *should* be in DynamoDB:

``--source migration`` (default)
    Runs the migration's own mappings (``mathbank-db/aws/dynamo/specs/content.py``: SQL + transform) through the
    read-only source connection of ``mathbank-db/aws/common.py`` and treats every produced item as the expectation,
    including its ``content_sha256``. A freshly migrated table must therefore reconcile with 0 diffs, for all types
    (not only the ones the admin endpoint knows). Needs a repository checkout; local-file image bytes are skipped.
``--source rest``
    The same facts the admin endpoint ``POST /v1/admin/content/reconcile`` uses (``routers/admin_content.build_sources``),
    read in a ``SET TRANSACTION READ ONLY`` transaction. Covers COMPETITION, PROBLEM, ACT, STEP, LI, TAXNODE, MC.

Prints the ReconcileReport per type and exits 1 when any diff exists (2 on a setup error); ``--json`` prints the report.
Nothing is written to PostgreSQL, DynamoDB or S3. AWS credentials: the usual chain / ``--profile``.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mathbank_rest.content_publisher import item_state
from mathbank_rest.stores.content.reconcile import (
    VECTOR_FAMILIES,
    ReconcileReport,
    SourceAggregate,
    reconcile,
)

MIGRATION_ROOT = ROOT.parent / "mathbank-db"
SKIP_MAPPINGS = {"core.problem_image"}              # reads image bytes from local files
LISTED_GSI2 = ("PLIST#", "TAXTYPE#", "CATALOG#", "THMBY#")


def aggregate_from_item(item: dict) -> SourceAggregate:
    """The expectation the migration's transform implies for one item (its hash is the 'rebuilt' hash)."""
    typ, pk, sk = item["type"], item["PK"], item["SK"]
    list_index, list_pk = None, None
    if typ in ("COMPETITION", "FACET"):
        list_pk = pk
    elif str(item.get("GSI2PK", "")).startswith(LISTED_GSI2):
        list_index, list_pk = "GSI2", item["GSI2PK"]
    return SourceAggregate(type=typ, pk=pk, sk=sk, id=f"{pk}|{sk}", src_rev=int(item.get("src_rev", 0)),
                           state=item_state(item), list_index=list_index, list_pk=list_pk,
                           rebuilt_sha256=item.get("content_sha256"))


def migration_sources(mappings: Sequence[str], types: set[str] | None) -> Iterator[SourceAggregate]:
    if not (MIGRATION_ROOT / "aws" / "common.py").exists():
        raise SystemExit(f"--source migration needs {MIGRATION_ROOT}; use --source rest from a bare checkout")
    sys.path.insert(0, str(MIGRATION_ROOT))
    from aws.common import source, stream
    from aws.dynamo.specs import content as spec

    with source() as conn:                           # read-only session, verified by the helper
        for m in spec.MAPPINGS:
            if m.name in SKIP_MAPPINGS or m.note.startswith("no own items") or (mappings and m.name not in mappings):
                continue
            print(f"# reading {m.name}", file=sys.stderr)
            for row in stream(conn, m.sql, m.params):
                for it in m.transform(row):
                    if isinstance(it, dict) and (not types or it["type"] in types):
                        yield aggregate_from_item(it)


def rest_sources(types: Sequence[str] | None, sample_pct: float, seed: str, include_facets: bool) -> list[SourceAggregate]:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import URL

    from mathbank_rest.config import settings
    from mathbank_rest.routers import admin_content

    if os.environ.get("NEON_PG_HOST"):
        url = URL.create("postgresql+psycopg", username=os.environ["NEON_PG_USER"], password=os.environ["NEON_PG_PASSWORD"],
                         host=os.environ["NEON_PG_HOST"], port=int(os.environ.get("NEON_PG_PORT", "5432")),
                         database=os.environ["NEON_PG_DATABASE"], query={"sslmode": os.environ.get("NEON_PG_SSLMODE", "require"),
                                                                        "application_name": "mathbank-content-parity"})
    else:
        url = settings.postgres_dsn
    engine = create_engine(url, pool_pre_ping=True, future=True)
    req = admin_content.ReconcileRequest(types=list(types) if types else None, sample_pct=sample_pct, include_facets=include_facets)
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        sources, notes = admin_content.build_sources(conn, req, seed)
    for n in notes:
        print(f"# {n}", file=sys.stderr)
    return sources


def vector_keys(types_present: set[str]) -> dict[str, list[str]]:
    from mathbank_rest.vector_catalog import Family
    from mathbank_rest.vector_store import S3VectorsStore

    store = S3VectorsStore()
    return {f: list(store.keys(Family(f))) for f, (t, _) in VECTOR_FAMILIES.items() if t in types_present}


def render(report: ReconcileReport, *, limit: int = 40) -> str:
    lines = [f"mb-content parity  sample={report.sample_pct:g}% seed={report.sample_seed or '-'}  started {report.started_at}", "",
             f"{'type':<14}{'source':>9}{'active':>9}{'found':>9}{'sampled':>9}{'skipped':>9}  diffs"]
    for t in report.types:
        diffs = ", ".join(f"{k}={n}" for k, n in sorted(t.diffs.items())) or "-"
        lines.append(f"{t.type:<14}{t.source:>9}{t.active:>9}{t.found:>9}{t.sampled:>9}{t.sample_skipped:>9}  {diffs}")
    for v in report.vectors:
        lines.append(f"vectors {v.family:<16} expected={v.expected} in_store={v.in_store} missing={v.missing} orphan={v.orphan}")
    for n in report.notes:
        lines.append(f"note: {n}")
    for d in report.diffs[:limit]:
        lines.append(f"  {d.kind:<17}{d.type:<12}{d.pk} | {d.sk}  expected={d.expected} actual={d.actual}")
    if report.diff_count > limit:
        lines.append(f"  ... {report.diff_count - limit} more (use --json for up to --max-diffs)")
    lines += ["", "PARITY OK: 0 diffs" if report.ok else f"PARITY FAILED: {report.diff_count} diffs {report.by_kind()}"]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", default="dev", help="mb-content-<env> (default dev)")
    ap.add_argument("--allow-prod", action="store_true", help="required for --env prod")
    ap.add_argument("--profile", default="", help="AWS profile (default: the credential chain)")
    ap.add_argument("--source", choices=("migration", "rest"), default="migration")
    ap.add_argument("--types", nargs="*", help="item types to compare (default: all the source produces)")
    ap.add_argument("--mapping", nargs="*", default=[], help="migration mappings to run, e.g. core.competition core.problem")
    ap.add_argument("--sample-pct", type=float, default=5.0, help="share whose hash is rebuilt (default 5)")
    ap.add_argument("--full", action="store_true", help="shorthand for --sample-pct 100 (the weekly run)")
    ap.add_argument("--seed", default=dt.datetime.now(dt.UTC).date().isoformat(), help="sampling seed (default: today)")
    ap.add_argument("--include-vectors", action="store_true", help="compare vector_state keys with S3 Vectors (needs VECTOR bucket access)")
    ap.add_argument("--include-facets", action="store_true", help="--source rest: also reconcile STEP/LI FACET partitions")
    ap.add_argument("--max-diffs", type=int, default=1000)
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    a = ap.parse_args(argv)
    if a.env == "prod" and not a.allow_prod:
        print("refusing --env prod without --allow-prod", file=sys.stderr)
        return 2
    from mathbank_rest.config import settings

    settings.ddb_env = a.env
    if a.profile:
        settings.aws_profile = a.profile
    pct = 100.0 if a.full else a.sample_pct
    types = {t.upper() for t in a.types} if a.types else None
    try:
        if a.source == "migration":
            sources = list(migration_sources(a.mapping, types))
        else:
            sources = rest_sources(sorted(types) if types else None, pct, a.seed, a.include_facets)
        present = {s.type for s in sources}
        report = reconcile(sources, sample_pct=pct, sample_seed=a.seed, max_diffs=a.max_diffs,
                           vector_keys_by_family=vector_keys(present) if a.include_vectors else None)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - a CLI: show the cause and exit 2
        print(f"content parity could not run: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps({**report.model_dump(mode="json"), "by_kind": report.by_kind()}, indent=2, sort_keys=True))
    else:
        print(render(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
