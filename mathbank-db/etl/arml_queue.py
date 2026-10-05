"""Durable ARML queue, gated on a specific COMPLETE full Purple Comet run.

No ARML network/model work occurs before the dependency passes. This runner
never generates pedagogy or publishes graphs: the existing teaching watcher
owns those operations. Restart with --resume RUN_UUID after correcting failures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from uuid import UUID

from psycopg.types.json import Jsonb

from arml_archive import BASE_URL, INGESTION, ROOT, VOLUMES, configure_cpu
from pdf_pipeline import _connect, cmd_ingest

LOGS = INGESTION / "logs/arml"
BOOKS = INGESTION / "data/archive_books/arml"
PYTHON = INGESTION / ".venv/bin/python"


def dependency_ready(conn, run_id: str) -> bool:
    row = conn.execute(
        "SELECT run_type,status,expected_items,completed_items,failed_items,requested_scope "
        "FROM pipeline.run WHERE run_id=%s", (run_id,),
    ).fetchone()
    if not row:
        raise ValueError("Purple dependency run UUID does not exist")
    kind, status, expected, completed, failed, scope = row
    papers = scope.get("papers", [])
    if kind != "PAPER_BATCH" or not papers or any(not code.startswith("PAPER_PURPLE_") for code in papers):
        raise ValueError("Dependency must be a full Purple PAPER_BATCH snapshot")
    registered = {r[0] for r in conn.execute(
        "SELECT paper_external_code FROM pipeline.pdf_source WHERE competition_external_code IN ('PURPLE_MS','PURPLE_HS')"
    )}
    # A successful one-paper pilot must never release the archive queue.
    if set(papers) != registered or expected != len(papers) or len(papers) != len(set(papers)):
        return False
    if status != "COMPLETED" or failed != 0 or completed != expected:
        return False
    items = conn.execute(
        "SELECT item_key,status,metrics FROM pipeline.work_item "
        "WHERE run_id=%s AND item_type='paper_end_to_end'", (run_id,),
    ).fetchall()
    if {r[0] for r in items} != set(papers):
        return False
    if any(r[1] != "COMPLETED" or r[2].get("graph_verified") is not True
           or r[2].get("classification_status") != "COMPLETED" for r in items):
        return False
    bad = conn.execute(
        "SELECT count(*) FROM pipeline.pdf_source WHERE paper_external_code=ANY(%s) "
        "AND (download_status!='DOWNLOADED' OR parse_status!='PARSED' OR ingest_status!='INGESTED' "
        "OR questions_found<=0 OR questions_found!=questions_ingested OR last_error IS NOT NULL)",
        (papers,),
    ).fetchone()[0]
    if bad:
        return False
    missing_vectors = conn.execute(
        "WITH entities AS (SELECT 'PROBLEM' AS kind,p.problem_id AS id FROM core.problem p "
        "JOIN core.paper t USING(paper_id) WHERE t.external_code=ANY(%s) UNION ALL "
        "SELECT 'SOLUTION',s.solution_id FROM core.solution s JOIN core.problem p USING(problem_id) "
        "JOIN core.paper t USING(paper_id) WHERE t.external_code=ANY(%s)) "
        "SELECT count(*) FROM entities x WHERE NOT EXISTS (SELECT 1 FROM search.representation r "
        "WHERE r.source_entity_type=x.kind AND r.source_entity_id=x.id AND r.status='ACTIVE' "
        "AND EXISTS(SELECT 1 FROM search.chunk c WHERE c.representation_id=r.representation_id) "
        "AND NOT EXISTS(SELECT 1 FROM search.chunk c WHERE c.representation_id=r.representation_id "
        "AND NOT EXISTS(SELECT 1 FROM search.embedding e JOIN search.embedding_model m USING(embedding_model_id) "
        "WHERE e.chunk_id=c.chunk_id AND e.status='ACTIVE' AND m.provider='openai' "
        "AND m.model_name='text-embedding-3-small' AND m.model_revision='v1')))", (papers, papers),
    ).fetchone()[0]
    return missing_vectors == 0


def record(conn, run_id, key, stage, status, error=None, metrics=None):
    conn.execute(
        "INSERT INTO pipeline.work_item(run_id,item_type,item_key,status,started_at,completed_at,last_error,metrics) "
        "VALUES(%s,%s,%s,%s,now(),CASE WHEN %s='COMPLETED' THEN now() END,%s,%s) "
        "ON CONFLICT(run_id,item_type,item_key) DO UPDATE SET status=EXCLUDED.status,"
        "completed_at=EXCLUDED.completed_at,last_error=EXCLUDED.last_error,"
        "attempt_count=pipeline.work_item.attempt_count+CASE WHEN EXCLUDED.status='IN_PROGRESS' THEN 1 ELSE 0 END,"
        "metrics=pipeline.work_item.metrics || EXCLUDED.metrics",
        (run_id, stage, key, status, status, error, Jsonb(metrics or {})),
    )
    conn.execute("UPDATE pipeline.run SET heartbeat_at=now() WHERE run_id=%s", (run_id,))


def done(conn, run_id, key, stage) -> bool:
    row = conn.execute(
        "SELECT status FROM pipeline.work_item WHERE run_id=%s AND item_key=%s AND item_type=%s",
        (run_id, key, stage),
    ).fetchone()
    return bool(row and row[0] == "COMPLETED")


def command(conn, run_id, key, stage, argv, timeout=14400):
    if done(conn, run_id, key, stage):
        return
    record(conn, run_id, key, stage, "IN_PROGRESS")
    log = LOGS / f"{run_id}.{key}.{stage}.log"
    with log.open("a") as stream:
        process = subprocess.Popen(argv, cwd=ROOT, env={**os.environ, "PYTHONUNBUFFERED": "1"},
                                   stdout=stream, stderr=subprocess.STDOUT)
        start = time.monotonic()
        try:
            while process.poll() is None:
                if time.monotonic() - start > timeout:
                    raise TimeoutError(f"{stage} exceeded {timeout}s")
                conn.execute("UPDATE pipeline.run SET heartbeat_at=now() WHERE run_id=%s", (run_id,))
                time.sleep(10)
            if process.returncode:
                raise RuntimeError(f"{stage} exited {process.returncode}; see {log}")
        except BaseException as exc:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            record(conn, run_id, key, stage, "FAILED", str(exc))
            raise
    record(conn, run_id, key, stage, "COMPLETED", metrics={"log": str(log)})


def download(conn, run_id, volume):
    filename = f"ARML-{volume}.pdf"
    path = BOOKS / filename
    record(conn, run_id, volume, "download", "IN_PROGRESS")
    if not path.is_file():
        request = urllib.request.Request(BASE_URL + filename, headers={"User-Agent": "MathBank ARML archive"})
        partial = path.with_suffix(".pdf.partial")
        try:
            with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as output:
                if not response.url.startswith(BASE_URL):
                    raise ValueError("ARML PDF redirected outside official archive")
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
                    conn.execute("UPDATE pipeline.run SET heartbeat_at=now() WHERE run_id=%s", (run_id,))
            if not partial.read_bytes()[:1024].lstrip().startswith(b"%PDF-"):
                raise ValueError("Official ARML download is not a PDF")
            partial.replace(path)
        finally:
            partial.unlink(missing_ok=True)
    if not path.read_bytes()[:1024].lstrip().startswith(b"%PDF-"):
        raise ValueError(f"Invalid cached PDF: {path}")
    record(conn, run_id, volume, "download", "COMPLETED",
           metrics={"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "path": str(path)})
    return path


def register(conn, sources):
    for source in sources:
        competition = source["competition_external_code"]
        conn.execute(
            "INSERT INTO core.competition(external_code,name,organization,level) VALUES(%s,%s,'ARML','HIGH_SCHOOL') "
            "ON CONFLICT(external_code) DO NOTHING",
            (competition, {"ARML": "American Regions Mathematics League", "ARML_LOCAL": "ARML Local",
                           "ARML_POWER": "ARML Power Contest"}[competition]),
        )
        conn.execute(
            "INSERT INTO pipeline.pdf_source(paper_external_code,competition_external_code,crawl_dir,problem_url,"
            "solution_url,link_scope,download_status,parse_status,questions_found,downloaded_at,parsed_at) "
            "VALUES(%s,%s,%s,%s,%s,'AGGREGATE_MULTI_EXAM_PDF','DOWNLOADED','PARSED',%s,now(),now()) "
            "ON CONFLICT(paper_external_code) DO UPDATE SET parse_status='PARSED',"
            "questions_found=EXCLUDED.questions_found,last_error=NULL,updated_at=now()",
            (source["paper_external_code"], competition, source["crawl_dir"], source["problem_url"],
             source["problem_url"], source["expected_count"]),
        )


def verify_artifacts(source):
    folder = INGESTION / "data/crawl_pdf" / source["crawl_dir"] / source["paper_external_code"]
    index = json.loads((folder / "index.json").read_text())
    codes = index["questions"]
    expected = [f"{source['paper_external_code']}_Q{i:02d}" for i in range(1, source["expected_count"] + 1)]
    if codes != expected or not codes:
        raise ValueError("ARML question inventory mismatch")
    for i in range(1, len(codes) + 1):
        question = folder / "questions" / f"Q{i:02d}"
        for side in ("problem", "solution"):
            receipt = json.loads((question / f"{side}.docling.json").read_text())
            if receipt["used_fallback"] is not False or receipt["device"] != "cpu":
                raise ValueError("ARML requires CPU Docling, not native fallback")
            if not receipt.get("images") or any(not (question / image).is_file() for image in receipt["images"]):
                raise ValueError("ARML extracted image inventory is incomplete")
            if not (question / f"{side}.md").read_text().strip():
                raise ValueError("Empty ARML Docling text")
            for page, _, _ in receipt["spans"]:
                if not (question / "images" / f"{side}_page_{page:03d}.png").is_file():
                    raise ValueError("Missing ARML full rendered page")
    return codes


def import_and_classify(conn, run_id, source):
    from paper_batches import verify_classification
    from load_corpus import load_concepts, load_techniques, load_problem_concepts, load_problem_techniques
    paper = source["paper_external_code"]
    codes = verify_artifacts(source)
    folder = INGESTION / "data/crawl_pdf" / source["crawl_dir"] / paper
    provenance = json.loads((folder / "provenance.json").read_text())
    if set(provenance) != {str(i) for i in range(1, len(codes) + 1)}:
        raise ValueError("ARML source provenance inventory mismatch")
    register(conn, [source])
    if not done(conn, run_id, paper, "ingest"):
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("SET LOCAL mathbank.automatic_writer='on'")
            cmd_ingest(cur, [paper], set(codes))
            for ordinal, code in enumerate(codes, 1):
                first_page = provenance[str(ordinal)]["problem"][0][0]
                cur.execute("UPDATE core.problem SET source_url=%s,answer_type=CASE "
                            "WHEN %s AND official_answer IS NULL THEN 'PROOF' ELSE answer_type END "
                            "WHERE canonical_code=%s",
                            (f"{source['problem_url']}#page={first_page}",
                             bool(source["contextual"]) and "Puzzles" not in source["title"], code))
            cur.execute(
                "UPDATE core.problem_image i SET source='PDF_ANSWER_PAGE' "
                "FROM core.problem p WHERE i.problem_id=p.problem_id AND p.canonical_code=ANY(%s) "
                "AND regexp_replace(i.local_path,'^.*/','') LIKE 'answer_%%'", (codes,))
        record(conn, run_id, paper, "ingest", "COMPLETED",
               metrics={"source": source, "provenance": provenance, "questions": len(codes)})
    count, solutions, images = conn.execute(
        "SELECT count(*),count(*) FILTER (WHERE EXISTS(SELECT 1 FROM core.solution s WHERE s.problem_id=p.problem_id)),"
        "count(*) FILTER (WHERE EXISTS(SELECT 1 FROM core.problem_image i WHERE i.problem_id=p.problem_id)) "
        "FROM core.problem p JOIN core.paper t USING(paper_id) WHERE t.external_code=%s", (paper,),
    ).fetchone()
    if (count, solutions, images) != (len(codes), len(codes), len(codes)):
        raise ValueError(f"{paper}: Postgres statement/solution/image inventory mismatch")
    command(conn, run_id, paper, "classify", [
        str(PYTHON), str(INGESTION / "scripts/classify_pdf_corpus.py"), "--competition",
        source["competition_external_code"], "--paper", paper, "--limit", str(len(codes)), "--retry-failed"])
    verify_classification(codes)
    command(conn, run_id, paper, "export", [
        str(PYTHON), str(INGESTION / "scripts/export_classifications_to_csv.py"), "--paper", paper])
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SET LOCAL mathbank.automatic_writer='on'")
        load_concepts(cur)
        load_techniques(cur)
        load_problem_concepts(cur, set(codes))
        load_problem_techniques(cur, set(codes))
    unapproved = conn.execute(
        "SELECT count(*) FROM core.problem p WHERE canonical_code=ANY(%s) AND NOT "
        "(EXISTS(SELECT 1 FROM knowledge.problem_concept c WHERE c.problem_id=p.problem_id AND "
        "(c.review_status='REVIEWED' OR c.approval_method='human')) OR "
        "EXISTS(SELECT 1 FROM knowledge.problem_technique t WHERE t.problem_id=p.problem_id AND "
        "(t.review_status='REVIEWED' OR t.approval_method='human')))", (codes,),
    ).fetchone()[0]
    if unapproved:
        raise ValueError("Classifications not automatically approved; check migration 008")
    command(conn, run_id, paper, "vectors", [sys.executable, str(ROOT / "mathbank-db/etl/embed_corpus.py"),
                                            "backfill", "--paper", paper])
    missing_vectors = conn.execute(
        "WITH entities AS (SELECT 'PROBLEM' AS kind,p.problem_id AS id FROM core.problem p "
        "WHERE canonical_code=ANY(%s) UNION ALL SELECT 'SOLUTION',s.solution_id FROM core.solution s "
        "JOIN core.problem p USING(problem_id) WHERE p.canonical_code=ANY(%s)) "
        "SELECT count(*) FROM entities x WHERE NOT EXISTS (SELECT 1 FROM search.representation r "
        "WHERE r.source_entity_type=x.kind AND r.source_entity_id=x.id AND r.status='ACTIVE' "
        "AND EXISTS(SELECT 1 FROM search.chunk c WHERE c.representation_id=r.representation_id) "
        "AND NOT EXISTS(SELECT 1 FROM search.chunk c WHERE c.representation_id=r.representation_id "
        "AND NOT EXISTS(SELECT 1 FROM search.embedding e JOIN search.embedding_model m USING(embedding_model_id) "
        "WHERE e.chunk_id=c.chunk_id AND e.status='ACTIVE' AND m.provider='openai' "
        "AND m.model_name='text-embedding-3-small' AND m.model_revision='v1')))", (codes, codes),
    ).fetchone()[0]
    if missing_vectors:
        raise ValueError(f"{paper}: {missing_vectors} entities lack complete active scoped embeddings")
    return codes


def watcher_ready(conn, codes) -> bool:
    pending = conn.execute(
        "SELECT count(*) FROM core.problem p LEFT JOIN knowledge.enrichment_job j USING(problem_id) "
        "WHERE canonical_code=ANY(%s) AND (j.status IS DISTINCT FROM 'COMPLETED' OR j.published_at IS NULL "
        "OR NOT EXISTS(SELECT 1 FROM knowledge.problem_skill s WHERE s.problem_id=p.problem_id) "
        "OR NOT EXISTS(SELECT 1 FROM knowledge.problem_pedagogy d WHERE d.problem_id=p.problem_id))", (codes,),
    ).fetchone()[0]
    if pending:
        return False
    # Both concept and skill catalogs touched by this archive must have reached
    # the relationship watcher; zero justified edges is a valid completed job.
    missing = conn.execute(
        "WITH anchors AS (SELECT 'skill' AS kind,s.skill_id AS id FROM knowledge.problem_skill s "
        "JOIN core.problem p USING(problem_id) JOIN knowledge.skill k USING(skill_id) "
        "WHERE p.canonical_code=ANY(%s) AND k.review_status='REVIEWED' UNION "
        "SELECT 'concept',c.concept_id FROM knowledge.problem_concept c JOIN core.problem p USING(problem_id) "
        "JOIN knowledge.concept k USING(concept_id) WHERE p.canonical_code=ANY(%s) AND k.status='ACTIVE') "
        "SELECT count(*) FROM anchors a LEFT JOIN "
        "knowledge.relationship_enrichment_job j ON j.entity_kind=a.kind AND j.anchor_id=a.id "
        "WHERE j.status IS DISTINCT FROM 'COMPLETED' OR j.published_at IS NULL", (codes, codes),
    ).fetchone()[0]
    return missing == 0


def verify_publication(conn, codes):
    from dotenv import dotenv_values
    from neo4j import GraphDatabase
    from paper_batches import verify_graph
    verify_graph(conn, set(codes))
    expected = {tuple(str(value) if i == 1 else value for i, value in enumerate(row))
                for row in conn.execute(
                    "SELECT p.canonical_code,s.skill_id,s.relation_type,s.role,s.review_status,s.approval_method "
                    "FROM knowledge.problem_skill s JOIN core.problem p USING(problem_id) "
                    "WHERE p.canonical_code=ANY(%s)", (codes,))}
    env = dotenv_values(os.environ["GRAPH_ENV_FILE"])
    with GraphDatabase.driver(env["NEO4J_URI"], auth=(
        env.get("NEO4J_USERNAME") or env.get("NEO4J_USER") or "neo4j", env["NEO4J_PASSWORD"])) as driver:
        with driver.session(database=env.get("NEO4J_DATABASE") or "neo4j") as session:
            actual = {tuple(row.values()) for row in session.run(
                "MATCH (p:Problem)-[r:REQUIRES|PRACTICES|TESTS]->(s:Skill) "
                "WHERE p.canonical_code IN $codes RETURN p.canonical_code,s.canonical_id,type(r),"
                "r.role,r.review_status,r.approval_method", codes=codes)}
            if actual != expected:
                raise ValueError("ARML pedagogical graph assertion mismatch")
            expected_nodes = {
                tuple(row) for row in conn.execute(
                    "SELECT p.canonical_code,p.official_answer,d.review_status,d.approval_method,"
                    "(SELECT count(*) FROM core.solution s WHERE s.problem_id=p.problem_id),"
                    "(SELECT count(*) FROM core.problem_image i WHERE i.problem_id=p.problem_id "
                    "AND i.source='PDF_PROBLEM_PAGE'),"
                    "(SELECT count(*) FROM core.problem_image i WHERE i.problem_id=p.problem_id "
                    "AND i.source='PDF_SOLUTION_PAGE') FROM core.problem p "
                    "JOIN knowledge.problem_pedagogy d USING(problem_id) WHERE p.canonical_code=ANY(%s)", (codes,))}
            actual_nodes = {tuple(row.values()) for row in session.run(
                "MATCH (p:Problem) WHERE p.canonical_code IN $codes "
                "OPTIONAL MATCH (p)-[:HAS_SOLUTION]->(s:Solution) "
                "RETURN p.canonical_code,p.official_answer,p.pedagogy_review_status,p.pedagogy_approval_method,"
                "count(s),p.problem_page_images,p.solution_page_images", codes=codes)}
            if actual_nodes != expected_nodes or len(expected_nodes) != len(codes):
                raise ValueError("ARML graph answer/solution/page-image/teaching inventory mismatch")
            for catalog, id_field, table, source_field, target_field in [
                ("Skill", "skill_id", "skill_relation", "from_skill_id", "to_skill_id"),
                ("Concept", "concept_id", "concept_relation", "from_concept_id", "to_concept_id"),
            ]:
                mapping = "problem_skill" if catalog == "Skill" else "problem_concept"
                anchors = [str(r[0]) for r in conn.execute(
                    f"SELECT DISTINCT m.{id_field} FROM knowledge.{mapping} m "
                    "JOIN core.problem p USING(problem_id) WHERE p.canonical_code=ANY(%s)", (codes,))]
                relations = set()
                for left, right, kind, status, method in conn.execute(
                    f"SELECT {source_field},{target_field},relation_type,review_status,approval_method "
                    f"FROM knowledge.{table} WHERE {source_field}=ANY(%s::uuid[]) OR {target_field}=ANY(%s::uuid[])",
                    (anchors, anchors)):
                    if kind == "HAS_SUBCONCEPT":
                        left, right, kind = right, left, "PART_OF"
                    if kind in {"PREREQUISITE_OF", "PART_OF", "BUILDS_ON"}:
                        relations.add((str(left), str(right), kind, status, method))
                graph_relations = {tuple(r.values()) for r in session.run(
                    f"MATCH (a:{catalog})-[r:PREREQUISITE_OF|PART_OF|BUILDS_ON]->(b:{catalog}) "
                    "WHERE a.canonical_id IN $ids OR b.canonical_id IN $ids "
                    "RETURN a.canonical_id,b.canonical_id,type(r),r.review_status,r.approval_method", ids=anchors)}
                if graph_relations != relations:
                    raise ValueError(f"ARML {catalog} relationship publication mismatch")


def run(conn, run_id, after, poll):
    while not dependency_ready(conn, after):
        conn.execute("UPDATE pipeline.run SET status='QUEUED',heartbeat_at=now() WHERE run_id=%s", (run_id,))
        print("ARML queued: Purple is not fully successful; no ARML stages released.", flush=True)
        time.sleep(poll)
    sys.path.insert(0, str(ROOT / "scripts"))
    from project_env import load_project_openai
    load_project_openai(INGESTION / ".env")
    conn.execute("UPDATE pipeline.run SET status='IN_PROGRESS',failed_items=0,completed_at=NULL,"
                 "started_at=COALESCE(started_at,now()) WHERE run_id=%s", (run_id,))
    for volume in VOLUMES:
        if done(conn, run_id, volume, "volume"):
            continue
        # Cooperate with the existing paper runner, but NEVER publish a graph.
        while not conn.execute("SELECT pg_try_advisory_lock(hashtext('mathbank-paper-batches'))").fetchone()[0]:
            conn.execute("UPDATE pipeline.run SET heartbeat_at=now() WHERE run_id=%s", (run_id,))
            time.sleep(poll)
        try:
            # Recheck after lock acquisition, before downloads or paid work.
            if not dependency_ready(conn, after):
                raise RuntimeError("Purple dependency changed while waiting for the paper lock")
            path = download(conn, run_id, volume)
            command(conn, run_id, volume, "parse", [str(PYTHON), str(ROOT / "mathbank-db/etl/arml_archive.py"), str(path)],
                    timeout=7 * 86400)
            sources = [json.loads(p.read_text())["source"] for p in
                       (INGESTION / "data/crawl_pdf").glob("arml*/PAPER_ARML_*/index.json")
                       if json.loads(p.read_text()).get("source", {}).get("volume") == path.name]
            if not sources:
                raise ValueError("ARML parser produced no verified round sources")
            codes = []
            for source in sources:
                codes.extend(import_and_classify(conn, run_id, source))
            record(conn, run_id, volume, "watcher", "IN_PROGRESS", metrics={"codes": codes})
        finally:
            conn.execute("SELECT pg_advisory_unlock(hashtext('mathbank-paper-batches'))")
        while not watcher_ready(conn, codes):
            conn.execute("UPDATE pipeline.run SET heartbeat_at=now() WHERE run_id=%s", (run_id,))
            print(f"{volume}: waiting for existing teaching/relationship watcher publication", flush=True)
            time.sleep(poll)
        verify_publication(conn, codes)
        record(conn, run_id, volume, "watcher", "COMPLETED", metrics={"graph_verified": True})
        record(conn, run_id, volume, "volume", "COMPLETED", metrics={"questions": len(codes), "rounds": len(sources)})
        conn.execute("UPDATE pipeline.run SET completed_items=completed_items+1 WHERE run_id=%s", (run_id,))
    conn.execute("UPDATE pipeline.run SET status='COMPLETED',completed_at=now(),failed_items=0,completed_items=4 WHERE run_id=%s", (run_id,))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--after-run", type=UUID, help="Full Purple PAPER_BATCH run UUID")
    group.add_argument("--resume", type=UUID, help="Existing ARML_ARCHIVE run UUID")
    parser.add_argument("--poll-seconds", type=int, default=60)
    args = parser.parse_args()
    def terminate(signum, frame):
        raise KeyboardInterrupt(f"Termination signal {signum}; resume the durable run")
    signal.signal(signal.SIGTERM, terminate)
    if args.poll_seconds < 10:
        parser.error("poll-seconds must be at least 10")
    if not os.environ.get("PG_ENV_FILE") or not os.environ.get("GRAPH_ENV_FILE"):
        parser.error("Explicit PG_ENV_FILE and GRAPH_ENV_FILE are required")
    configure_cpu()
    LOGS.mkdir(parents=True, exist_ok=True)
    BOOKS.mkdir(parents=True, exist_ok=True)
    with _connect(direct=True) as conn:
        conn.autocommit = True
        if not conn.execute("SELECT pg_try_advisory_lock(hashtext('mathbank-arml-archive'))").fetchone()[0]:
            raise RuntimeError("An ARML queue already owns this archive")
        if args.resume:
            run_id = str(args.resume)
            row = conn.execute("SELECT requested_scope FROM pipeline.run WHERE run_id=%s AND run_type='ARML_ARCHIVE'",
                               (run_id,)).fetchone()
            if not row:
                raise ValueError("No matching durable ARML queue")
            after = row[0]["after_run"]
        else:
            after = str(args.after_run)
            # Validate identity before persisting; not-ready is a normal queue state.
            dependency_ready(conn, after)
            run_id = str(conn.execute(
                "INSERT INTO pipeline.run(run_type,status,expected_items,requested_scope) "
                "VALUES('ARML_ARCHIVE','QUEUED',4,%s) RETURNING run_id",
                (Jsonb({"after_run": after, "volumes": list(VOLUMES)}),),
            ).fetchone()[0])
        print(f"ARML_QUEUE_RUN={run_id}; dependency={after}; logs={LOGS}", flush=True)
        try:
            run(conn, run_id, after, args.poll_seconds)
        except BaseException as exc:
            conn.execute("UPDATE pipeline.run SET status='FAILED',failed_items=1,completed_at=now(),"
                         "metadata=metadata || %s WHERE run_id=%s",
                         (Jsonb({"last_error": str(exc)[:2000]}), run_id))
            raise


if __name__ == "__main__":
    main()
