"""Run a resumable Postgres-driven SMT/HMMT PDF backlog in bounded batches.

Each paper is downloaded, strictly split, ingested and classified; each batch
exports scoped classifications and projects Postgres to Neo4j. COMPLETED means
the graph was verified, not merely that a subprocess returned zero.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from dotenv import dotenv_values
from load_corpus import (
    _clean_crawl_pdf_markdown,
    load_concepts,
    load_problem_concepts,
    load_problem_techniques,
    load_techniques,
)
from pdf_pipeline import INGESTION_ROOT, PDF_CRAWL_DIR, REPO_ROOT, _connect, cmd_ingest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

COMPETITIONS = ("SMT", "HMMT_FEB", "HMMT_NOV", "HMMT_INV")
INGESTION_PYTHON = INGESTION_ROOT / ".venv/bin/python"
SQLITE_DB = INGESTION_ROOT / "data/mathbank.db"
LOG_ROOT = INGESTION_ROOT / "logs/paper_batches"


def question_codes(source: dict) -> list[str]:
    base = PDF_CRAWL_DIR / source["crawl_dir"] / source["paper_external_code"]
    index = json.loads((base / "index.json").read_text())
    ids = index.get("questions", [])
    prefix = source["paper_external_code"]
    numbers = []
    for code in ids:
        match = re.fullmatch(re.escape(prefix) + r"_Q(\d+)", code)
        if match is None:
            raise ValueError("Whole-paper fallback cannot be marked PARSED")
        number = int(match.group(1))
        numbers.append(number)
        path = base / "questions" / f"Q{number:02d}" / "problem.md"
        if not path.exists() or not _clean_crawl_pdf_markdown(path.read_text()).strip():
            raise ValueError(f"Missing question artifact: {code}")
    if not numbers or sorted(numbers) != list(range(1, len(numbers) + 1)):
        raise ValueError("Question numbers are not contiguous from 1")
    return ids


def verify_classification(codes: list[str]) -> None:
    with sqlite3.connect(SQLITE_DB) as conn:
        placeholders = ",".join("?" for _ in codes)
        rows = conn.execute(
            f"SELECT question_id, classification_status, taxonomy_mapping_count FROM questions "
            f"WHERE question_id IN ({placeholders})",
            codes,
        ).fetchall()
        mapped = {
            row[0] for row in rows if row[1] == "SOLUTION_REVIEWED" and row[2] > 0
        }
        if mapped != set(codes):
            raise ValueError(
                f"{len(set(codes) - mapped)} questions lack successful classification"
            )


def stage(
    conn,
    run_id: str,
    paper: str,
    name: str,
    command: list[str],
    log_dir: Path,
    timeout: int = 1800,
) -> None:
    log = log_dir / f"{paper}.{name}.log"
    print(f"{paper}: {name} START -> {log}", flush=True)
    metrics = {"stage": name, f"{name}_log": str(log)}
    if name == "classify":
        metrics["classification_status"] = "IN_PROGRESS"
    conn.execute(
        "UPDATE pipeline.work_item SET metrics=metrics || %s WHERE run_id=%s AND item_key=%s",
        (Jsonb(metrics), run_id, paper),
    )
    started = datetime.now(timezone.utc)
    temporary_dir = log_dir / "tmp"
    temporary_dir.mkdir(exist_ok=True)
    with log.open("a") as output:
        process = subprocess.Popen(
            command,
            cwd=INGESTION_ROOT,
            stdout=output,
            stderr=subprocess.STDOUT,
            env={
                **os.environ,
                "PYTHONUNBUFFERED": "1",
                "TMPDIR": str(temporary_dir),
                "MATHBANK_PDF_DEVICE": "cpu",
            },
        )
        try:
            while True:
                try:
                    code = process.wait(timeout=15)
                    break
                except subprocess.TimeoutExpired:
                    conn.execute(
                        "UPDATE pipeline.run SET heartbeat_at=now() WHERE run_id=%s",
                        (run_id,),
                    )
                    if (datetime.now(timezone.utc) - started).total_seconds() > timeout:
                        raise TimeoutError(f"{name} exceeded {timeout}s; see {log}")
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise
    if code:
        raise RuntimeError(f"{name} exited {code}; see {log}")
    print(f"{paper}: {name} OK", flush=True)


def snapshot(conn, args) -> tuple[str, list[dict], Path]:
    if args.resume:
        run_id = str(UUID(args.resume))
        row = conn.execute(
            "SELECT requested_scope,metadata FROM pipeline.run WHERE run_id=%s "
            "AND run_type='PAPER_BATCH'",
            (run_id,),
        ).fetchone()
        if row is None:
            raise ValueError("No matching PAPER_BATCH run")
        papers = row[0]["papers"]
        done = {
            r[0]
            for r in conn.execute(
                "SELECT item_key FROM pipeline.work_item "
                "WHERE run_id=%s AND status='COMPLETED'",
                (run_id,),
            )
        }
        papers = [paper for paper in papers if paper not in done]
        log_dir = Path(row[1]["log_dir"])
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM pipeline.pdf_source WHERE paper_external_code=ANY(%s)",
                (papers,),
            )
            rows = cur.fetchall()
        if len(rows) != len(papers):
            raise ValueError("A paper from the original snapshot is missing")
        conn.execute(
            "UPDATE pipeline.run SET status='IN_PROGRESS',completed_at=NULL,"
            "heartbeat_at=now() WHERE run_id=%s",
            (run_id,),
        )
    else:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT * FROM pipeline.pdf_source WHERE competition_external_code=ANY(%s) "
                "AND source_kind='PDF' AND ingest_status!='INGESTED' "
                "AND (%s::text[] IS NULL OR paper_external_code=ANY(%s)) "
                "ORDER BY substring(paper_external_code from '[0-9]{4}') DESC, paper_external_code "
                "LIMIT %s",
                (list(COMPETITIONS), args.paper, args.paper, args.limit),
            )
            rows = cur.fetchall()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        log_dir = LOG_ROOT / timestamp
        log_dir.mkdir(parents=True, exist_ok=False)
        run_id = str(
            conn.execute(
                "INSERT INTO pipeline.run(run_type,status,started_at,heartbeat_at,expected_items,"
                "requested_scope,metadata) VALUES('PAPER_BATCH','IN_PROGRESS',now(),now(),%s,%s,%s) "
                "RETURNING run_id",
                (
                    len(rows),
                    Jsonb(
                        {
                            "competitions": list(COMPETITIONS),
                            "papers": [row["paper_external_code"] for row in rows],
                        }
                    ),
                    Jsonb({"log_dir": str(log_dir), "batch_size": args.batch_size}),
                ),
            ).fetchone()[0]
        )
    (log_dir / "sources.json").write_text(json.dumps(rows, default=str, indent=2))
    return run_id, rows, log_dir


def process_paper(conn, run_id: str, source: dict, log_dir: Path) -> list[str]:
    paper = source["paper_external_code"]
    conn.execute(
        "INSERT INTO pipeline.work_item(run_id,item_type,item_key,status,started_at,attempt_count) "
        "VALUES(%s,'paper_end_to_end',%s,'IN_PROGRESS',now(),1) "
        "ON CONFLICT(run_id,item_type,item_key) DO UPDATE SET status='IN_PROGRESS',"
        "started_at=now(),completed_at=NULL,last_error=NULL,attempt_count=pipeline.work_item.attempt_count+1",
        (run_id, paper),
    )
    source_file = log_dir / f"{paper}.source.json"
    with (
        INGESTION_ROOT / "src/mathbank/data/maths_corpus/paper_registry.csv"
    ).open() as registry:
        count = next(
            (
                row["Question_Count"]
                for row in csv.DictReader(registry)
                if row["Paper_ID"] == paper
            ),
            "",
        )
    if count.isdigit() and int(count) > 0:
        source = {**source, "expected_count": int(count)}
    source_file.write_text(json.dumps([source], default=str))
    parse_command = [
        str(INGESTION_PYTHON),
        "scripts/crawl_pdf_papers.py",
        "--sources-file",
        str(source_file),
        "--require-split",
        "--delay",
        "2",
    ]
    try:
        stage(conn, run_id, paper, "parse", parse_command, log_dir, timeout=900)
    except RuntimeError as exc:
        print(
            f"{paper}: rejected Docling parse ({exc}); retrying explicit native-text extraction",
            flush=True,
        )
        stage(
            conn,
            run_id,
            paper,
            "parse",
            [*parse_command, "--native-extraction", "--reparse"],
            log_dir,
            timeout=900,
        )
        conn.execute(
            "UPDATE pipeline.work_item SET metrics=metrics || %s WHERE run_id=%s AND item_key=%s",
            (
                Jsonb(
                    {
                        "extraction_warning": "Docling parse rejected; native-text fallback requires review"
                    }
                ),
                run_id,
                paper,
            ),
        )
    stage(
        conn,
        run_id,
        paper,
        "split",
        [
            str(INGESTION_PYTHON),
            "scripts/split_pdf_artifacts.py",
            "--paper",
            paper,
        ],
        log_dir,
    )
    codes = question_codes(source)
    warnings = set()
    for code in codes:
        artifact = (
            INGESTION_ROOT / "data/crawl" / source["crawl_dir"] / code / "parsed.json"
        )
        warnings.update(json.loads(artifact.read_text()).get("parse_warnings", []))
    if warnings:
        print(f"{paper}: extraction warnings: {sorted(warnings)}", flush=True)
        conn.execute(
            "UPDATE pipeline.work_item SET metrics=metrics || %s WHERE run_id=%s AND item_key=%s",
            (Jsonb({"parse_warnings": sorted(warnings)}), run_id, paper),
        )
    with conn.transaction():
        conn.execute(
            "UPDATE pipeline.pdf_source SET download_status='DOWNLOADED',parse_status='PARSED',"
            "downloaded_at=COALESCE(downloaded_at,now()),parsed_at=COALESCE(parsed_at,now()),"
            "questions_found=%s,last_error=NULL,updated_at=now() WHERE paper_external_code=%s",
            (len(codes), paper),
        )
        with conn.cursor() as cur:
            cmd_ingest(cur, [paper], set(codes))
    stored = conn.execute(
        "SELECT count(*) FROM core.problem p JOIN core.paper t USING(paper_id) WHERE t.external_code=%s",
        (paper,),
    ).fetchone()[0]
    if stored != len(codes):
        raise ValueError(f"Postgres contains {stored} problems, expected {len(codes)}")
    stage(
        conn,
        run_id,
        paper,
        "classify",
        [
            str(INGESTION_PYTHON),
            "scripts/classify_pdf_corpus.py",
            "--competition",
            source["competition_external_code"],
            "--paper",
            paper,
            "--limit",
            str(len(codes)),
            "--retry-failed",
        ],
        log_dir,
    )
    verify_classification(codes)
    conn.execute(
        "UPDATE pipeline.work_item SET metrics=metrics || %s WHERE run_id=%s AND item_key=%s",
        (
            Jsonb(
                {
                    "questions": len(codes),
                    "stage": "classified",
                    "classification_status": "COMPLETED",
                }
            ),
            run_id,
            paper,
        ),
    )
    return codes


def publish_batch(
    conn, run_id: str, sources: list[dict], codes: set[str], log_dir: Path, batch: int
) -> None:
    label = f"batch-{batch:03d}"
    command = [str(INGESTION_PYTHON), "scripts/export_classifications_to_csv.py"]
    for source in sources:
        command.extend(["--paper", source["paper_external_code"]])
        conn.execute(
            "UPDATE pipeline.work_item SET metrics=metrics || %s WHERE run_id=%s AND item_key=%s",
            (
                Jsonb({"stage": "export", "batch": batch}),
                run_id,
                source["paper_external_code"],
            ),
        )
    stage(conn, run_id, label, "export", command, log_dir)
    with conn.transaction(), conn.cursor() as cur:
        load_concepts(cur)
        load_techniques(cur)
        concepts = load_problem_concepts(cur, codes)[0]
        techniques = load_problem_techniques(cur, codes)[0]
    coverage = conn.execute(
        "SELECT count(*) FROM core.problem p WHERE canonical_code=ANY(%s) AND "
        "(EXISTS(SELECT 1 FROM knowledge.problem_concept c WHERE c.problem_id=p.problem_id) "
        "OR EXISTS(SELECT 1 FROM knowledge.problem_technique t WHERE t.problem_id=p.problem_id))",
        (list(codes),),
    ).fetchone()[0]
    if coverage != len(codes):
        raise ValueError(
            f"Postgres classifications cover {coverage}/{len(codes)} questions"
        )
    for source in sources:
        conn.execute(
            "UPDATE pipeline.work_item SET metrics=metrics || %s WHERE run_id=%s AND item_key=%s",
            (
                Jsonb({"stage": "graph", "graph_status": "IN_PROGRESS"}),
                run_id,
                source["paper_external_code"],
            ),
        )
    stage(
        conn,
        run_id,
        label,
        "graph",
        [
            sys.executable,
            str(REPO_ROOT / "mathbank-graph/etl/project_from_postgres.py"),
            "--pedagogy",
        ],
        log_dir,
    )
    verify_graph(conn, codes)
    for source in sources:
        conn.execute(
            "UPDATE pipeline.work_item SET status='COMPLETED',completed_at=now(),"
            "metrics=metrics || %s WHERE run_id=%s AND item_key=%s",
            (
                Jsonb(
                    {
                        "stage": "graph_verified",
                        "batch": batch,
                        "graph_verified": True,
                        "graph_status": "COMPLETED",
                        "new_batch_concept_links": concepts,
                        "new_batch_technique_links": techniques,
                    }
                ),
                run_id,
                source["paper_external_code"],
            ),
        )


def verify_graph(conn, codes: set[str]) -> None:
    from neo4j import GraphDatabase

    expected = {
        (
            row[0],
            row[1],
            str(row[2]),
            row[3],
            row[4],
            row[5],
            float(row[6]) if row[6] is not None else None,
        )
        for row in conn.execute(
            "SELECT p.canonical_code,'TESTS',c.concept_id,c.role,c.review_status,"
            "c.assertion_source,c.confidence FROM core.problem p "
            "JOIN knowledge.problem_concept c USING(problem_id) WHERE p.canonical_code=ANY(%s) "
            "UNION ALL SELECT p.canonical_code,'USES_TECHNIQUE',t.technique_id,t.role,"
            "t.review_status,t.assertion_source,t.confidence FROM core.problem p "
            "JOIN knowledge.problem_technique t USING(problem_id) WHERE p.canonical_code=ANY(%s)",
            (list(codes), list(codes)),
        )
    }
    env = dotenv_values(os.environ["GRAPH_ENV_FILE"])
    user = env.get("NEO4J_USERNAME") or env.get("NEO4J_USER") or "neo4j"
    with (
        GraphDatabase.driver(
            env["NEO4J_URI"], auth=(user, env["NEO4J_PASSWORD"])
        ) as driver,
        driver.session(database=env.get("NEO4J_DATABASE") or "neo4j") as session,
    ):
        records = list(
            session.run(
                "MATCH (p:Problem)-[r:TESTS|USES_TECHNIQUE]->(target) "
                "WHERE p.canonical_code IN $codes AND (target:Concept OR target:Technique) "
                "RETURN p.canonical_code AS code,type(r) AS kind,target.canonical_id AS target,"
                "r.role AS role,r.review_status AS status,r.source AS source,r.confidence AS confidence",
                codes=list(codes),
            )
        )
        actual = {
            (
                r["code"],
                r["kind"],
                r["target"],
                r["role"],
                r["status"],
                r["source"],
                r["confidence"],
            )
            for r in records
        }
        if actual != expected or len(records) != len(expected):
            raise ValueError(
                f"Graph assertion mismatch: {len(expected - actual)} missing/changed, "
                f"{len(actual - expected)} unexpected, {len(records) - len(actual)} duplicates"
            )


def progress(conn, run_id: str, finished: bool = False) -> tuple[int, int]:
    counts = dict(
        conn.execute(
            "SELECT status,count(*) FROM pipeline.work_item WHERE run_id=%s "
            "AND item_type='paper_end_to_end' GROUP BY status",
            (run_id,),
        ).fetchall()
    )
    completed, failed = counts.get("COMPLETED", 0), counts.get("FAILED", 0)
    conn.execute(
        "UPDATE pipeline.run SET completed_items=%s,failed_items=%s,heartbeat_at=now(),"
        "status=%s,completed_at=CASE WHEN %s THEN now() ELSE NULL END WHERE run_id=%s",
        (
            completed,
            failed,
            ("FAILED" if failed else "COMPLETED") if finished else "IN_PROGRESS",
            finished,
            run_id,
        ),
    )
    return completed, failed


def record_failure(conn, run_id: str, paper: str, error: Exception) -> None:
    metrics = conn.execute(
        "SELECT metrics FROM pipeline.work_item WHERE run_id=%s AND item_key=%s",
        (run_id, paper),
    ).fetchone()[0]
    stage_name = metrics.get("stage")
    update = {}
    if stage_name == "classify":
        update["classification_status"] = "FAILED"
    if stage_name == "graph":
        update["graph_status"] = "FAILED"
    conn.execute(
        "UPDATE pipeline.work_item SET status='FAILED',last_error=%s,completed_at=now(),"
        "metrics=metrics || %s WHERE run_id=%s AND item_key=%s",
        (str(error), Jsonb(update), run_id, paper),
    )
    conn.execute(
        "UPDATE pipeline.pdf_source SET last_error=%s,updated_at=now() "
        "WHERE paper_external_code=%s",
        (str(error), paper),
    )
    if stage_name in {"parse", "split"}:
        crawl_dir = conn.execute(
            "SELECT crawl_dir FROM pipeline.pdf_source WHERE paper_external_code=%s",
            (paper,),
        ).fetchone()[0]
        downloaded = (PDF_CRAWL_DIR / crawl_dir / paper / "problem.pdf").is_file()
        conn.execute(
            "UPDATE pipeline.pdf_source SET download_status=%s,parse_status=%s,"
            "downloaded_at=CASE WHEN %s THEN COALESCE(downloaded_at,now()) ELSE downloaded_at END "
            "WHERE paper_external_code=%s",
            (
                "DOWNLOADED" if downloaded else "FAILED",
                "FAILED" if downloaded else "PENDING",
                downloaded,
                paper,
            ),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--paper", action="append")
    parser.add_argument(
        "--resume", help="Resume original Postgres run UUID, including failed stages"
    )
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 20 or args.limit < 1:
        parser.error("batch-size must be 1..20 and limit must be positive")
    if not os.environ.get("PG_ENV_FILE") or not os.environ.get("GRAPH_ENV_FILE"):
        parser.error("Explicit PG_ENV_FILE and GRAPH_ENV_FILE are required")
    if not os.environ.get("OPENAI_API_KEY"):
        api_key = dotenv_values(INGESTION_ROOT / ".env").get("OPENAI_API_KEY")
        if not api_key:
            parser.error(
                "OPENAI_API_KEY must be configured before starting paid classification"
            )
        os.environ["OPENAI_API_KEY"] = api_key
    with _connect() as conn:
        conn.autocommit = True
        if not conn.execute(
            "SELECT pg_try_advisory_lock(hashtext('mathbank-paper-batches'))"
        ).fetchone()[0]:
            raise RuntimeError("Another paper batch runner is active")
        run_id, sources, log_dir = snapshot(conn, args)
        print(
            f"RUN {run_id}: {len(sources)} papers, batches of {args.batch_size}; logs={log_dir}",
            flush=True,
        )
        try:
            for start in range(0, len(sources), args.batch_size):
                batch = start // args.batch_size + 1
                ready, codes = [], set()
                for source in sources[start : start + args.batch_size]:
                    paper = source["paper_external_code"]
                    try:
                        codes.update(process_paper(conn, run_id, source, log_dir))
                        ready.append(source)
                    except (ValueError, RuntimeError, OSError) as exc:
                        print(f"{paper}: FAILED {exc}", flush=True)
                        record_failure(conn, run_id, paper, exc)
                if ready:
                    try:
                        publish_batch(conn, run_id, ready, codes, log_dir, batch)
                    except (ValueError, RuntimeError, OSError) as exc:
                        print(f"BATCH {batch}: publication FAILED {exc}", flush=True)
                        for source in ready:
                            record_failure(
                                conn, run_id, source["paper_external_code"], exc
                            )
                completed, failed = progress(conn, run_id)
                print(
                    f"BATCH {batch}: cumulative completed={completed} failed={failed}",
                    flush=True,
                )
            completed, failed = progress(conn, run_id, finished=True)
            print(f"RUN {run_id}: completed={completed}, failed={failed}", flush=True)
        except BaseException:
            conn.execute(
                "UPDATE pipeline.run SET status='FAILED',completed_at=now() WHERE run_id=%s",
                (run_id,),
            )
            raise
        if failed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
