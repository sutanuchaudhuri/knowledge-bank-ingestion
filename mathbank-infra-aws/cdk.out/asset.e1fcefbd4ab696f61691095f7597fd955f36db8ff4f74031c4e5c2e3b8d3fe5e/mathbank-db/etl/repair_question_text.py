"""Audit/repair AMC and AIME source text independently of concept mapping. No AI calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from load_corpus import _upsert_solution
from pdf_pipeline import INGESTION_ROOT, _connect

sys.path.insert(0, str(INGESTION_ROOT / "src"))
from mathbank.crawl.aops_parser import ParsedQuestion, parse_aops_page

log = logging.getLogger(__name__)
COMPETITIONS = ("AIME", "AMC10", "AMC12")


def missing_text(value: str | None) -> bool:
    return not value or not value.strip() or value.lstrip().startswith("[Placeholder]")


def validate_source_bundle(
    bundle: dict, sources: dict[str, str | None]
) -> dict[str, ParsedQuestion]:
    unknown = set(bundle) - sources.keys()
    if unknown:
        raise ValueError(
            f"Source bundle contains questions outside the selected scope: {sorted(unknown)}"
        )
    parsed_records = {}
    for code, entry in bundle.items():
        if entry["url"] != sources[code] or entry["status"] != 200:
            raise ValueError(
                f"{code}: source bundle URL/status does not match the recorded source"
            )
        parsed = parse_aops_page(entry["html"], code, sources[code] or "")
        if not parsed.has_problem:
            raise ValueError(f"{code}: source bundle contains no problem statement")
        parsed_records[code] = parsed
    return parsed_records


def local_record(folder: Path, code: str, url: str | None) -> dict | None:
    path = folder / "parsed.json"
    record = json.loads(path.read_text()) if path.is_file() else None
    if record and record.get("question_id", code) != code:
        raise ValueError(f"{code}: source artifact question ID mismatch")
    if record and not missing_text(record.get("problem_text")):
        return record
    html = folder / "problem.html"
    if html.is_file():
        parsed = parse_aops_page(html.read_text(), code, url or "")
        if parsed.has_problem:
            return {
                **(record or {}),
                "question_id": code,
                "url": url,
                "problem_text": parsed.problem_text,
                "solution_texts": parsed.solution_texts,
                "answer_value": parsed.answer_value,
                "answer_choices": parsed.answer_choices,
                "parse_warnings": parsed.parse_warnings,
            }
    return record


def apply_record(
    cur,
    staging,
    problem_id: str,
    code: str,
    statement: str,
    record: dict,
    *,
    write: bool,
) -> Counter:
    totals = Counter()
    problem = (record.get("problem_text") or "").strip().replace("\x00", "")
    if missing_text(statement) and not missing_text(problem):
        totals["statements_recoverable"] += 1
        if write:
            cur.execute(
                """UPDATE core.problem SET statement_text=%s,content_hash=%s,updated_at=now()
                   WHERE problem_id=%s AND
                     (trim(coalesce(statement_text,''))='' OR
                      ltrim(statement_text) LIKE '[Placeholder]%%')""",
                (problem, hashlib.sha256(problem.encode()).hexdigest(), problem_id),
            )
            totals["statements_updated"] += 1
            staging.execute(
                "UPDATE questions SET problem_text_latex=?,problem_text_raw=? WHERE question_id=?",
                (problem, problem, code),
            )
    solutions = [
        s.strip().replace("\x00", "")
        for s in record.get("solution_texts", [])
        if s and s.strip()
    ]
    if write:
        for ordinal, solution in enumerate(solutions, 1):
            _upsert_solution(
                cur, problem_id, "AOPS_COMMUNITY", ordinal, solution, only_missing=True
            )
        if solutions:
            staging.execute(
                """UPDATE questions SET
                   solution_text_latex=CASE WHEN trim(coalesce(solution_text_latex,''))=''
                     THEN ? ELSE solution_text_latex END,
                   all_solutions_json=CASE WHEN coalesce(all_solutions_json,'') IN ('','[]','null')
                     THEN ? ELSE all_solutions_json END
                   WHERE question_id=?""",
                (solutions[0], json.dumps(solutions, ensure_ascii=False), code),
            )
        answer = record.get("answer_value")
        if answer:
            cur.execute(
                "UPDATE core.problem SET official_answer=%s WHERE problem_id=%s "
                "AND coalesce(official_answer,'')=''",
                (answer, problem_id),
            )
    totals["local_solution_bodies"] += len(solutions)
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Repair local-source text and solution bodies",
    )
    parser.add_argument("--competition", action="append", choices=COMPETITIONS)
    parser.add_argument("--db", type=Path, default=INGESTION_ROOT / "data/mathbank.db")
    parser.add_argument(
        "--report", type=Path, help="Write source-gap inventory as JSON"
    )
    parser.add_argument(
        "--source-bundle",
        type=Path,
        help="JSON array of {code,url,status,html} acquired from the original browser pages",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    folders = {
        p.parent.name: p.parent
        for p in (INGESTION_ROOT / "data/crawl").glob("*/*/parsed.json")
    }
    bundle = {}
    if args.source_bundle:
        for entry in json.loads(args.source_bundle.read_text()):
            if entry["code"] in bundle:
                raise ValueError("Duplicate question in source bundle")
            bundle[entry["code"]] = entry
    totals = Counter()
    coverage = {}
    gaps = []
    if not args.db.is_file():
        raise FileNotFoundError(
            "Existing staging database is required; no migration is performed"
        )
    mode = "rw" if args.apply else "ro"
    with sqlite3.connect(
        f"{args.db.resolve().as_uri()}?mode={mode}", uri=True
    ) as staging:
        staging.execute("SELECT question_id FROM questions LIMIT 0")
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.problem_id::text,p.canonical_code,p.statement_text,p.source_url,
                       comp.external_code,pa.external_code,
                       EXISTS(SELECT 1 FROM core.solution s WHERE s.problem_id=p.problem_id
                              AND trim(coalesce(s.body_markdown,''))!='') AS has_solution,
                       EXISTS(SELECT 1 FROM search.chunk ch
                              JOIN search.representation r USING(representation_id)
                              JOIN search.embedding e USING(chunk_id)
                              JOIN search.embedding_model m USING(embedding_model_id)
                              WHERE ch.problem_id=p.problem_id AND r.status='ACTIVE'
                                AND r.representation_kind='PROBLEM_STATEMENT'
                                AND r.rendered_text=trim('[Problem] ' || p.statement_text)
                                AND e.status='ACTIVE' AND m.status='ACTIVE') AS current_vector
                FROM core.problem p JOIN core.paper pa USING(paper_id)
                JOIN core.competition_edition ed USING(edition_id)
                JOIN core.competition comp USING(competition_id)
                WHERE comp.external_code=ANY(%s) ORDER BY p.canonical_code
            """,
                (args.competition or list(COMPETITIONS),),
            )
            rows = cur.fetchall()
            parsed_bundle = validate_source_bundle(
                bundle, {row[1]: row[3] for row in rows}
            )
            with conn.pipeline():
                for (
                    pid,
                    code,
                    statement,
                    url,
                    competition,
                    paper,
                    has_solution,
                    vector,
                ) in rows:
                    counts = coverage.setdefault(competition, Counter())
                    counts["questions"] += 1
                    counts["missing_statement"] += missing_text(statement)
                    counts["missing_solution"] += not has_solution
                    counts["current_statement_vector"] += vector
                    counts["text_without_current_vector"] += (
                        not missing_text(statement) and not vector
                    )
                    folder = folders.get(code)
                    record = local_record(folder, code, url) if folder else None
                    if code in bundle:
                        entry = bundle[code]
                        parsed = parsed_bundle[code]
                        folder = folder or (
                            INGESTION_ROOT
                            / "data/crawl"
                            / {"AMC10": "amc_10", "AMC12": "amc_12", "AIME": "aime"}[
                                competition
                            ]
                            / code
                        )
                        record = {
                            **(record or {}),
                            "question_id": code,
                            "url": url,
                            "problem_text": parsed.problem_text,
                            "solution_texts": parsed.solution_texts,
                            "answer_value": parsed.answer_value,
                            "answer_choices": parsed.answer_choices,
                            "parse_warnings": parsed.parse_warnings,
                        }
                        totals["browser_sources_validated"] += 1
                        if args.apply:
                            folder.mkdir(parents=True, exist_ok=True)
                            (folder / "problem.html").write_text(entry["html"])
                            (folder / "problem_text.md").write_text(parsed.to_md())
                            folders[code] = folder
                    if record and (missing_text(statement) or not has_solution):
                        totals.update(
                            apply_record(
                                cur,
                                staging,
                                pid,
                                code,
                                statement,
                                record,
                                write=args.apply,
                            )
                        )
                        if args.apply and not missing_text(record.get("problem_text")):
                            (folder / "parsed.json").write_text(
                                json.dumps(record, indent=2, ensure_ascii=False) + "\n"
                            )
                    if missing_text(statement):
                        recoverable = bool(
                            record and not missing_text(record.get("problem_text"))
                        )
                        status = (
                            "LOCAL_RECOVERABLE"
                            if recoverable
                            else (
                                "INVALID_LOCAL_SOURCE"
                                if folder
                                else "SOURCE_NOT_FETCHED"
                            )
                        )
                        gaps.append(
                            {"code": code, "paper": paper, "url": url, "status": status}
                        )
                        totals[status.lower()] += 1
            if not args.apply:
                conn.rollback()
    report = {
        "mode": "applied" if args.apply else "dry-run",
        "coverage": coverage,
        "repair": totals,
        "gaps": gaps,
    }
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "gaps"}, sort_keys=True))
    if any(gap["status"] != "LOCAL_RECOVERABLE" for gap in gaps):
        log.warning(
            "%s statements remain unavailable locally; acquire original sources, then rerun",
            sum(g["status"] != "LOCAL_RECOVERABLE" for g in gaps),
        )


if __name__ == "__main__":
    main()
