"""Resource-sized, local-only multi-machine tutoring ingestion."""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest import route_compiler, route_runtime
from mathbank_rest.db.postgres import engine
from mathbank_rest.route_critic import CriticRejected, evaluate
from mathbank_rest.route_ollama import OllamaError, OllamaProvider
from mathbank_rest.route_resources import capacity, discover
from mathbank_rest.step_runtime import RuntimeError_

log = logging.getLogger(__name__)
LEASE_SECONDS = 180
HEARTBEAT_SECONDS = 30


class LeaseLost(RuntimeError):
    pass


def seed(limit: int | None, retry_failed: bool) -> int:
    with engine.begin() as conn:
        sources = route_compiler.select_sources(conn, limit)
        rows = [
            {
                "v": route_compiler.VERSION,
                "sid": source["solution_id"],
                "hash": route_compiler.source_hash(source),
            }
            for source in sources
        ]
        for start in range(0, len(rows), 250):
            conn.execute(
                text("""
                INSERT INTO pedagogy.route_compile_task(generator_version,solution_id,source_hash)
                VALUES (:v,:sid,:hash) ON CONFLICT DO NOTHING
            """),
                rows[start : start + 250],
            )
        if retry_failed:
            for start in range(0, len(rows), 250):
                conn.execute(
                    text("""
                    UPDATE pedagogy.route_compile_task
                    SET status='QUEUED',error_code=NULL,completed_at=NULL
                    WHERE generator_version=:v AND solution_id=:sid AND source_hash=:hash
                      AND status='FAILED'
                """),
                    rows[start : start + 250],
                )
    return len(sources)


def claim(run_id: str) -> dict | None:
    token = str(uuid4())
    with engine.begin() as conn:
        row = (
            conn.execute(
                text("""
            WITH candidate AS (
                SELECT task_id FROM pedagogy.route_compile_task
                WHERE generator_version=:v AND
                    (status='QUEUED' OR (status='RUNNING' AND lease_until < now()))
                ORDER BY created_at,task_id
                FOR UPDATE SKIP LOCKED LIMIT 1
            )
            UPDATE pedagogy.route_compile_task t
            SET status='RUNNING',owner_token=:token,owner_run_id=:run,
                lease_until=now()+make_interval(secs => :seconds),attempts=attempts+1,
                error_code=NULL,completed_at=NULL
            FROM candidate WHERE t.task_id=candidate.task_id
            RETURNING t.*
        """),
                {
                    "v": route_compiler.VERSION,
                    "token": token,
                    "run": run_id,
                    "seconds": LEASE_SECONDS,
                },
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        task = dict(row)
        conn.execute(
            text("""
            INSERT INTO pedagogy.route_compiler_job(run_id,solution_id,source_hash,status)
            VALUES (:run,:sid,:hash,'RUNNING')
            ON CONFLICT(run_id,solution_id) DO UPDATE SET status='RUNNING',
                completed_at=NULL,error_code=NULL,error_details='[]'::jsonb
        """),
            {"run": run_id, "sid": task["solution_id"], "hash": task["source_hash"]},
        )
        return task


def check_owner(conn, task: dict) -> None:
    row = conn.execute(
        text("""
        SELECT task_id FROM pedagogy.route_compile_task
        WHERE task_id=:id AND owner_token=:token AND status='RUNNING' AND lease_until > now()
        FOR UPDATE
    """),
        {"id": task["task_id"], "token": task["owner_token"]},
    ).first()
    if row is None:
        raise LeaseLost("Task lease lost; generated content will not be persisted.")


@contextmanager
def heartbeat(task: dict, stop: threading.Event):
    done = threading.Event()

    def renew():
        while not done.wait(HEARTBEAT_SECONDS):
            try:
                with engine.begin() as conn:
                    count = conn.execute(
                        text("""
                        UPDATE pedagogy.route_compile_task
                        SET lease_until=now()+make_interval(secs => :seconds)
                        WHERE task_id=:id AND owner_token=:token AND status='RUNNING'
                          AND lease_until > now()
                    """),
                        {
                            "seconds": LEASE_SECONDS,
                            "id": task["task_id"],
                            "token": task["owner_token"],
                        },
                    ).rowcount
                if count != 1:
                    with engine.connect() as conn:
                        completed = conn.execute(
                            text("""
                            SELECT task_id FROM pedagogy.route_compile_task
                            WHERE task_id=:id AND owner_token=:token AND status='DONE'
                        """),
                            {"id": task["task_id"], "token": task["owner_token"]},
                        ).first()
                    if completed or done.is_set():
                        return
                    log.error("Task heartbeat lost ownership: %s", task["task_id"])
                    stop.set()
                    return
            except SQLAlchemyError as exc:
                log.error("Task heartbeat database failure: %s", type(exc).__name__)
                stop.set()
                return

    thread = threading.Thread(target=renew, daemon=True)
    thread.start()
    try:
        yield
    finally:
        done.set()
        thread.join()


def transient_database_error(exc: SQLAlchemyError) -> bool:
    code = getattr(exc.orig, "sqlstate", None) if hasattr(exc, "orig") else None
    return (
        code in {"40001", "40P01"}
        or bool(code and code.startswith("08"))
        or bool(getattr(exc, "connection_invalidated", False))
    )


def store(task: dict, source: dict, program, run_id: str, reviewer: str | None) -> str:
    # All source/structure/enrichment checks precede this transaction.
    # Roll back on failure; only connection/serialization/deadlock failures retry.
    for attempt in range(3):
        try:
            with engine.begin() as conn:
                completed = conn.execute(
                    text("""
                    SELECT route_release_id FROM pedagogy.route_compile_task
                    WHERE task_id=:id AND owner_token=:token AND status='DONE'
                """),
                    {"id": task["task_id"], "token": task["owner_token"]},
                ).scalar()
                if completed:
                    return str(completed)
                check_owner(conn, task)
                release = route_compiler.persist(conn, source, program, run_id)
                if reviewer:
                    state = (
                        conn.execute(
                            text("""
                        SELECT status,content_hash FROM pedagogy.solution_route_release
                        WHERE route_release_id=:id
                    """),
                            {"id": release},
                        )
                        .mappings()
                        .one()
                    )
                    if state["status"] == "DRAFT":
                        route_runtime.review(conn, UUID(release), reviewer, state["content_hash"])
                conn.execute(
                    text("""
                    UPDATE pedagogy.route_compiler_job SET generation_metadata=CAST(:m AS jsonb)
                    WHERE run_id=:run AND solution_id=:sid
                """),
                    {
                        "m": json.dumps(source["_generation_metadata"]),
                        "run": run_id,
                        "sid": source["solution_id"],
                    },
                )
                conn.execute(
                    text("""
                    UPDATE pedagogy.route_compile_task SET status='DONE',route_release_id=:r,
                        completed_at=now(),lease_until=NULL
                    WHERE task_id=:id AND owner_token=:token
                """),
                    {"r": release, "id": task["task_id"], "token": task["owner_token"]},
                )
            return release
        except SQLAlchemyError as exc:
            if attempt == 2 or not transient_database_error(exc):
                raise
            log.warning(
                "Retrying rolled-back persistence: %s attempt=%s", type(exc).__name__, attempt + 1
            )
            time.sleep(2**attempt)
    raise RuntimeError("Persistence retry budget exhausted.")


def process(
    task: dict,
    run_id: str,
    nodes: list[dict],
    provider: OllamaProvider,
    critic: OllamaProvider,
    reviewer: str | None,
    stop: threading.Event,
) -> dict:
    source = {}
    try:
        with heartbeat(task, stop):
            with engine.connect() as conn:
                source = dict(
                    conn.execute(
                        text("""
                    SELECT s.solution_id::text,s.problem_id::text,p.canonical_code,
                           p.statement_text,s.verification_status,
                           coalesce(nullif(trim(s.body_markdown),''),s.body_latex) AS source
                    FROM core.solution s JOIN core.problem p USING(problem_id)
                    WHERE s.solution_id=:sid
                """),
                        {"sid": task["solution_id"]},
                    )
                    .mappings()
                    .one()
                )
            if route_compiler.source_hash(source) != task["source_hash"]:
                raise ValueError(
                    "Canonical source changed since queue creation; reseed updated source."
                )
            history = []
            for attempt in range(3):
                program = route_compiler.generate(source, nodes, provider)
                evaluation = evaluate(program, source, critic, provider, nodes)
                history.append(
                    {
                        "attempt": attempt,
                        "generator": {
                            key: source["_generation_metadata"].get(key)
                            for key in ("model", "digest", "calls", "program_hash", "repair_count")
                        },
                        "critic": evaluation,
                    }
                )
                source["_generation_metadata"]["critic_attempt_history"] = list(history)
                source["_critic_attempt_history"] = list(history)
                if evaluation["accepted"]:
                    break
                source["_critic_feedback"] = evaluation["evaluations"]
                if attempt == 2:
                    raise CriticRejected(
                        "Different-model eval rejected after two feedback repairs."
                    )
            release = store(task, source, program, run_id, reviewer)
        return {"task_id": str(task["task_id"]), "status": "DONE", "release": release}
    except (
        ValueError,
        TypeError,
        ValidationError,
        SQLAlchemyError,
        OllamaError,
        LeaseLost,
        RuntimeError_,
    ) as exc:
        details = (
            exc.errors(include_input=False, include_context=False, include_url=False)
            if isinstance(exc, ValidationError)
            else [{"message": str(exc)}]
            if isinstance(exc, (ValueError, LeaseLost))
            else []
        )
        log.error("Task failed: %s %s %s", task["task_id"], type(exc).__name__, details)
        if source.get("_critic_attempt_history"):
            source.setdefault("_generation_metadata", {})["critic_attempt_history"] = source[
                "_critic_attempt_history"
            ]
        if isinstance(exc, (OllamaError, LeaseLost, SQLAlchemyError)):
            stop.set()
        with engine.begin() as conn:
            updated = conn.execute(
                text("""
                UPDATE pedagogy.route_compile_task SET status='FAILED',error_code=:error,
                    completed_at=now(),lease_until=NULL
                WHERE task_id=:id AND owner_token=:token AND status='RUNNING'
                  AND lease_until > now()
                RETURNING task_id
            """),
                {
                    "error": type(exc).__name__,
                    "id": task["task_id"],
                    "token": task["owner_token"],
                },
            ).first()
            conn.execute(
                text("""
                UPDATE pedagogy.route_compiler_job SET status='FAILED',error_code=:error,
                    error_details=CAST(:details AS jsonb),generation_metadata=CAST(:m AS jsonb),
                    completed_at=now()
                WHERE run_id=:run AND solution_id=:sid
            """),
                {
                    "error": type(exc).__name__ if updated else "LeaseLost",
                    "details": json.dumps(details),
                    "m": json.dumps(source.get("_generation_metadata", {})),
                    "run": run_id,
                    "sid": task["solution_id"],
                },
            )
        return {
            "task_id": str(task["task_id"]),
            "status": "FAILED",
            "error_code": type(exc).__name__,
        }


def queue_counts() -> dict:
    with engine.connect() as conn:
        return dict(
            conn.execute(
                text("""
            SELECT status,count(*) FROM pedagogy.route_compile_task
            WHERE generator_version=:v GROUP BY status
        """),
                {"v": route_compiler.VERSION},
            ).all()
        )


def progress(run_id: str | None = None) -> dict:
    counts = queue_counts()
    with engine.connect() as conn:
        runs = [
            dict(row)
            for row in conn.execute(
                text("""
            SELECT run_id::text,status,created_at,completed_at,
                   generation_config->>'host' AS machine,
                   generation_config->>'model' AS model
            FROM pedagogy.route_compiler_run WHERE generator_version=:v
            ORDER BY created_at DESC LIMIT 20
        """),
                {"v": route_compiler.VERSION},
            ).mappings()
        ]
        expired = conn.execute(
            text("""
            SELECT count(*) FROM pedagogy.route_compile_task
            WHERE generator_version=:v AND status='RUNNING' AND lease_until < now()
        """),
            {"v": route_compiler.VERSION},
        ).scalar_one()
        errors = [
            dict(row)
            for row in conn.execute(
                text("""
            SELECT error_code,count(*) AS jobs FROM pedagogy.route_compile_task
            WHERE generator_version=:v AND status='FAILED'
            GROUP BY error_code ORDER BY jobs DESC
        """),
                {"v": route_compiler.VERSION},
            ).mappings()
        ]
        evals = [
            dict(row)
            for row in conn.execute(
                text("""
            SELECT j.generation_metadata #>> '{critic,model}' AS critic_model,
                   item->'evaluation'->>'verdict' AS verdict,count(*) AS step_evals
            FROM pedagogy.route_compiler_job j
            JOIN pedagogy.route_compiler_run r USING(run_id)
            CROSS JOIN LATERAL jsonb_array_elements(
                coalesce(j.generation_metadata #> '{critic,evaluations}','[]'::jsonb)
            ) AS item
            WHERE r.generator_version=:v
            GROUP BY critic_model,verdict ORDER BY critic_model,verdict
        """),
                {"v": route_compiler.VERSION},
            ).mappings()
        ]
    total = sum(counts.values())
    report = {
        "compiler_version": route_compiler.VERSION,
        "shared_queue": counts,
        "total": total,
        "done": counts.get("DONE", 0),
        "completion_percent": round(100 * counts.get("DONE", 0) / total, 2) if total else 0,
        "expired_reclaimable_leases": expired,
        "failures_by_code": errors,
        "latest_machine_runs": runs,
        "job_eval_summary": evals,
    }
    if run_id:
        report["machine_run"] = route_compiler.run_report(run_id)
    return report


def recheck(release_id: UUID, critic: OllamaProvider) -> dict:
    """Re-evaluate a manually edited draft without regenerating or publishing it."""
    with engine.connect() as conn:
        release = dict(
            conn.execute(
                text("""
            SELECT r.*,p.statement_text,s.verification_status,
                coalesce(nullif(trim(s.body_markdown),''),s.body_latex) AS source
            FROM pedagogy.solution_route_release r JOIN core.solution s USING(solution_id)
            JOIN core.problem p ON p.problem_id=r.problem_id WHERE route_release_id=:id
        """),
                {"id": release_id},
            )
            .mappings()
            .one()
        )
        if release["status"] != "DRAFT":
            raise ValueError("Only a DRAFT can receive new critic evaluations.")
        program = route_runtime.load_program(conn, str(release_id))
        rows = list(
            conn.execute(
                text("""
            SELECT generation_metadata FROM pedagogy.route_step
            WHERE route_release_id=:id ORDER BY step_index
        """),
                {"id": release_id},
            ).scalars()
        )
        nodes = route_compiler.taxonomy(conn)
    generator_metadata = next((row for row in rows if row.get("model") and row.get("digest")), None)
    if generator_metadata is None:
        raise ValueError(
            "Draft has no known generator identity; recompile rather than invent provenance."
        )
    if any(not row.get("model") or not row.get("digest") for row in rows):
        raise ValueError("A step has unknown original model provenance; recompile the route.")
    source = dict(release) | {
        "solution_id": str(release["solution_id"]),
        "_generation_metadata": dict(generator_metadata),
    }
    from mathbank_rest.route_contracts import program_digest, validate_enrichment, validate_source

    if route_compiler.source_hash(source) != release["source_hash"]:
        raise ValueError("Canonical source changed; recompile rather than re-evaluate.")
    validate_enrichment(program)
    validate_source(program, source["source"], {node["taxonomy_node_id"] for node in nodes})
    result = evaluate(
        program,
        source,
        critic,
        OllamaProvider(
            model=generator_metadata["model"],
            digest=generator_metadata["digest"],
        ),
        nodes,
    )
    with engine.begin() as conn:
        current = (
            conn.execute(
                text("""
            SELECT r.status,r.content_hash,p.statement_text,s.verification_status,
                s.solution_id::text,
                coalesce(nullif(trim(s.body_markdown),''),s.body_latex) AS source
            FROM pedagogy.solution_route_release r JOIN core.solution s USING(solution_id)
            JOIN core.problem p ON p.problem_id=r.problem_id
            WHERE route_release_id=:id FOR UPDATE OF r FOR SHARE OF s,p
        """),
                {"id": release_id},
            )
            .mappings()
            .one()
        )
        if (
            current["status"] != "DRAFT"
            or current["content_hash"] != program_digest(program)
            or route_compiler.source_hash(dict(current)) != release["source_hash"]
        ):
            raise ValueError(
                "Draft/source changed during critic evaluation; retry the current draft."
            )
        for index, metadata in enumerate(rows, 1):
            updated = dict(metadata)
            updated["critic_eval_history"] = metadata.get("critic_eval_history", []) + [
                metadata.get("critic", {}),
            ]
            updated["critic"] = result
            conn.execute(
                text("""
                UPDATE pedagogy.route_step SET generation_metadata=CAST(:m AS jsonb)
                WHERE route_release_id=:id AND step_index=:i
            """),
                {"m": json.dumps(updated), "id": release_id, "i": index},
            )
    return {"route_release_id": str(release_id), "critic": result}


def migrate() -> None:
    sql = Path(__file__).resolve().parents[3] / "mathbank-db/sql/028_route_distributed_queue.sql"
    direct = create_engine(engine.url.set(host=(engine.url.host or "").replace("-pooler.", ".")))
    try:
        with direct.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.exec_driver_sql(sql.read_text(), execution_options={"no_parameters": True})
    finally:
        direct.dispose()


@contextmanager
def server(log_dir: Path, slots: int):
    executable = shutil.which("ollama")
    if not executable:
        raise ValueError(
            "Ollama executable missing; install Ollama and pull the chosen model first."
        )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    endpoint = f"http://127.0.0.1:{port}"
    env = dict(
        os.environ,
        OLLAMA_HOST=f"127.0.0.1:{port}",
        OLLAMA_NUM_PARALLEL=str(slots),
        OLLAMA_MAX_LOADED_MODELS="1",
        OLLAMA_FLASH_ATTENTION="1",
        OLLAMA_KV_CACHE_TYPE="q8_0",
    )
    with (log_dir / "server.log").open("a") as handle:
        child = subprocess.Popen([executable, "serve"], env=env, stdout=handle, stderr=handle)
        try:
            for _ in range(60):
                if child.poll() is not None:
                    raise OllamaError("Owned Ollama server exited; inspect server.log.")
                try:
                    with httpx.Client(timeout=1) as client:
                        response = client.get(endpoint + "/api/version")
                        response.raise_for_status()
                    break
                except httpx.HTTPError:
                    time.sleep(0.5)
            else:
                raise OllamaError("Owned Ollama server did not become responsive.")
            yield endpoint
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


def ensure_model(endpoint: str, model: str, log_dir: Path) -> None:
    with httpx.Client(timeout=900) as client:
        response = client.get(endpoint + "/api/tags")
        response.raise_for_status()
        if any(item["name"] == model for item in response.json()["models"]):
            return
        print(f"Installing missing Ollama model {model}; see model-install.log.", flush=True)
        with (log_dir / "model-install.log").open("a") as handle:
            complete = False
            with client.stream(
                "POST", endpoint + "/api/pull", json={"model": model, "stream": True}
            ) as stream:
                stream.raise_for_status()
                for line in stream.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    handle.write(json.dumps(data) + "\n")
                    handle.flush()
                    if data.get("error"):
                        raise OllamaError("Model download failed; inspect model-install.log.")
                    complete = data.get("status") == "success"
            if not complete:
                raise OllamaError("Model download did not complete; inference was not started.")
    OllamaProvider(model=model, endpoint=endpoint).preflight()


def run(
    provider: OllamaProvider, critic: OllamaProvider, sizing: dict, args, log_dir: Path
) -> dict:
    selected = seed(args.limit, args.retry_failed)
    with engine.begin() as conn:
        run_id = conn.execute(
            text("""
            INSERT INTO pedagogy.route_compiler_run
                (generator_version,requested_limit,status,auto_review_by,generation_config)
            VALUES (:v,:n,'RUNNING',:who,CAST(:config AS jsonb)) RETURNING run_id::text
        """),
            {
                "v": route_compiler.VERSION,
                "n": max(1, selected),
                "who": args.approve_by,
                "config": json.dumps(
                    provider.config()
                    | {"critic": critic.config(), "resources": sizing, "host": socket.gethostname()}
                ),
            },
        ).scalar_one()
        nodes = route_compiler.taxonomy(conn)
    stop = threading.Event()
    report_lock = threading.Lock()
    print(json.dumps({"run_id": run_id, "resources": sizing, "selected": selected}), flush=True)
    log.info(
        "Run started %s", json.dumps({"run_id": run_id, "resources": sizing, "selected": selected})
    )

    def snapshot():
        with report_lock:
            report = route_compiler.run_report(run_id) | {"shared_queue": queue_counts()}
            route_compiler.write_report(log_dir / "progress.json", report)
        return report

    def worker():
        while not stop.is_set():
            task = claim(run_id)
            if task is None:
                return
            result = process(task, run_id, nodes, provider, critic, args.approve_by, stop)
            log.info("Task result %s", json.dumps(result))
            print(json.dumps(result), flush=True)
            snapshot()

    snapshot()
    try:
        with ThreadPoolExecutor(max_workers=sizing["workers"]) as pool:
            futures = [pool.submit(worker) for _ in range(sizing["workers"])]
            try:
                for future in futures:
                    future.result()
            finally:
                stop.set()
    finally:
        stop.set()
        report = snapshot()
        with engine.begin() as conn:
            conn.execute(
                text("""
                UPDATE pedagogy.route_compiler_run SET status=:status,completed_at=now()
                WHERE run_id=:id
            """),
                {
                    "status": "PARTIAL"
                    if report["failures"] or report["remaining"]
                    else "COMPLETED",
                    "id": run_id,
                },
            )
        report = snapshot()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["plan", "prepare", "run", "evaluate", "migrate", "status"]
    )
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--critic-model", default="llama3.2:3b")
    parser.add_argument("--context", type=int, default=16384)
    parser.add_argument(
        "--workers", type=int, help="Optional lower ceiling; unsafe overrides refused."
    )
    parser.add_argument("--limit", type=int, help="Seed a bounded source cohort instead of all.")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--approve-by", help="Named operator bulk approval; never publishes.")
    parser.add_argument("--run-id", help="Include detailed progress for one machine run.")
    parser.add_argument(
        "--release-id", type=UUID, help="DRAFT release to re-evaluate after an edit."
    )
    parser.add_argument("--log-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if not 8192 <= args.context <= 32768:
        parser.error("--context must be 8192-32768 for generation plus critic evals")
    if args.approve_by is not None and not args.approve_by.strip():
        parser.error("--approve-by must be nonblank")
    if args.command == "evaluate" and args.release_id is None:
        parser.error("evaluate requires --release-id")
    os.umask(0o077)
    args.log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            logging.FileHandler(args.log_dir / "ingestion.log"),
        ],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if args.command == "migrate":
        migrate()
        print("Distributed queue migration applied.")
        return
    if args.command == "status":
        print(json.dumps(progress(args.run_id), indent=2, default=str))
        return
    if args.command == "run":
        with engine.connect() as conn:
            present = conn.execute(
                text("SELECT to_regclass('pedagogy.route_compile_task') IS NOT NULL")
            ).scalar_one()
        if not present:
            raise ValueError("Distributed queue is absent; run make routes-migrate first.")
    infrastructure = discover()
    startup = {
        "infrastructure": infrastructure.__dict__,
        "model_storage_free_bytes": shutil.disk_usage(Path.home()).free,
        "generator_model": args.model,
        "critic_model": args.critic_model,
    }
    route_compiler.write_report(args.log_dir / "infrastructure.json", startup)
    log.info("Infrastructure %s", json.dumps(startup))
    print(json.dumps(startup), flush=True)
    if args.model == args.critic_model:
        raise ValueError("Generator and critic models must be different.")
    # Probe model inventory without loading it, before sizing the inference server.
    with server(args.log_dir, 1) as endpoint:
        if args.command in {"prepare", "run", "evaluate"}:
            if args.command != "evaluate":
                ensure_model(endpoint, args.model, args.log_dir)
            ensure_model(endpoint, args.critic_model, args.log_dir)
        selected_models = (
            [args.critic_model]
            if args.command == "evaluate"
            else [
                args.model,
                args.critic_model,
            ]
        )
        providers = [
            OllamaProvider(model=model, endpoint=endpoint, num_ctx=args.context).preflight()
            for model in selected_models
        ]
        if len(providers) == 2 and providers[0].digest == providers[1].digest:
            raise ValueError("Generator and critic digests must differ.")
        with httpx.Client(timeout=15) as client:
            tags = client.get(endpoint + "/api/tags")
            tags.raise_for_status()
            sizes = {
                item["name"]: item["size"]
                for item in tags.json()["models"]
                if item["name"] in selected_models
            }
        sizing = capacity(discover(), max(sizes.values()), args.context, args.workers)
        sizing["model_sizes"] = sizes
        sizing["generator_model"] = args.model
        sizing["critic_model"] = args.critic_model
    route_compiler.write_report(args.log_dir / "resources.json", sizing)
    print(json.dumps(sizing, indent=2), flush=True)
    if args.command in {"plan", "prepare"}:
        return
    with server(args.log_dir, sizing["workers"]) as endpoint:
        critic = OllamaProvider(
            model=args.critic_model,
            endpoint=endpoint,
            num_ctx=args.context,
            num_thread=sizing["num_thread"],
            num_predict=2048,
        ).preflight()
        if args.command == "evaluate":
            result = recheck(args.release_id, critic)
            route_compiler.write_report(args.log_dir / "critic-evals.json", result)
            print(json.dumps(result, indent=2), flush=True)
            if not result["critic"]["accepted"]:
                raise SystemExit(1)
            return
        provider = OllamaProvider(
            model=args.model,
            endpoint=endpoint,
            num_ctx=args.context,
            num_thread=sizing["num_thread"],
        ).preflight()
        if provider.digest == critic.digest:
            raise ValueError("Generator and critic digests must differ.")
        report = run(provider, critic, sizing, args, args.log_dir)
    print(json.dumps(report, indent=2, default=str), flush=True)
    if report["failures"] or report["remaining"]:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except (SQLAlchemyError, httpx.HTTPError) as exc:
        # Driver/transport exception bodies can contain credentials or SQL parameters.
        log.error("Pipeline failed: %s; check service connectivity.", type(exc).__name__)
        raise SystemExit(
            f"Pipeline failed: {type(exc).__name__}; check service connectivity."
        ) from None
    except (OllamaError, ValueError) as exc:
        log.error("Pipeline failed: %s", str(exc))
        raise SystemExit(f"Pipeline failed: {exc}") from None
