"""Vector/search subsystem — Phase 1-3 of mathematics_tutor_db_plan_v2/vector/12_implementation_sequence.md.

Pipeline: core.problem/core.solution -> search.representation -> search.chunk
-> search.embedding (OpenAI), with pipeline.run / search.embedding_job
tracking per mathematics_tutor_db_plan_v2/vector/06_embedding_pipeline_reembedding_and_versioning.md.

Loads OPENAI_API_KEY from project .env files, ignoring inherited shell keys.
Never pass it on the command line or print it.

Usage:
    python etl/embed_corpus.py backfill            # representations + chunks + embeddings
    python etl/embed_corpus.py backfill --limit 50  # small test batch
    python etl/embed_corpus.py index                # create the HNSW index for the active model
    python etl/embed_corpus.py status
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import psycopg
import tiktoken
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent))
from load_corpus import _load_env  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from project_env import load_project_openai  # noqa: E402

PROVIDER = "openai"
MODEL_NAME = "text-embedding-3-small"
MODEL_REVISION = "v1"
DIMENSIONS = 1536
BATCH_SIZE = 100
MAX_CHARS_PER_CHUNK = 6000  # ~1500 tokens; our statements/solutions are short enough to rarely split


def _ensure_openai_api_key() -> None:
    load_project_openai(Path(__file__).resolve().parents[1] / ".env")

_encoding = tiktoken.get_encoding("cl100k_base")


def _connect():
    # NEON_PG_* (from mathbank-graph/remote.env, via PG_ENV_FILE) target the
    # remote Neon instance; falls back to the local mathbank-db cluster when
    # absent — same precedence as etl/load_corpus.py::main().
    env = _load_env()
    conninfo = (
        f"host={env.get('NEON_PG_HOST', '127.0.0.1')} "
        f"port={env.get('NEON_PG_PORT') or env.get('PG_PORT', '5433')} "
        f"dbname={env.get('NEON_PG_DATABASE') or env.get('APP_DB', 'mathbank')} "
        f"user={env.get('NEON_PG_USER') or env.get('APP_USER', 'mathbank_app')} "
        f"password={env.get('NEON_PG_PASSWORD') or env.get('APP_DB_PASSWORD', '')}"
        + (f" sslmode={env['NEON_PG_SSLMODE']}" if env.get("NEON_PG_SSLMODE") else "")
    )
    return psycopg.connect(conninfo)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ensure_model_and_profile(cur) -> tuple[str, str]:
    """Returns (embedding_model_id, preprocessing_profile_id)."""
    cur.execute(
        """
        INSERT INTO search.embedding_model
          (provider, model_name, model_revision, dimensions, distance_metric, status, activated_at)
        VALUES (%s, %s, %s, %s, 'COSINE', 'ACTIVE', now())
        ON CONFLICT (provider, model_name, model_revision) DO UPDATE SET status = 'ACTIVE'
        RETURNING embedding_model_id
        """,
        (PROVIDER, MODEL_NAME, MODEL_REVISION, DIMENSIONS),
    )
    model_id = str(cur.fetchone()[0])

    cur.execute(
        """
        INSERT INTO search.preprocessing_profile (name, version, configuration)
        VALUES ('default', 1, %s)
        ON CONFLICT (name, version) DO NOTHING
        RETURNING preprocessing_profile_id
        """,
        ('{"normalize_unicode": true, "preserve_latex": true, "prepend_entity_type": true}',),
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(
            "SELECT preprocessing_profile_id FROM search.preprocessing_profile WHERE name='default' AND version=1"
        )
        row = cur.fetchone()
    profile_id = str(row[0])
    return model_id, profile_id


def _upsert_representation(cur, profile_id: str, entity_type: str, entity_id: str,
                            kind: str, rendered_text: str) -> str | None:
    """Marks prior ACTIVE representations with a different hash SUPERSEDED, inserts/reuses
    the current one. Returns representation_id, or None if rendered_text is empty."""
    rendered_text = rendered_text.strip()
    if not rendered_text:
        return None
    content_hash = _sha256(rendered_text)

    cur.execute(
        """
        UPDATE search.representation
        SET status = 'SUPERSEDED'
        WHERE source_entity_type = %s AND source_entity_id = %s AND representation_kind = %s
          AND preprocessing_profile_id = %s AND status = 'ACTIVE' AND content_hash != %s
        """,
        (entity_type, entity_id, kind, profile_id, content_hash),
    )
    cur.execute(
        """
        INSERT INTO search.representation
          (source_entity_type, source_entity_id, representation_kind, preprocessing_profile_id,
           rendered_text, content_hash, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'ACTIVE')
        ON CONFLICT (source_entity_type, source_entity_id, representation_kind, preprocessing_profile_id, content_hash)
          DO UPDATE SET status = 'ACTIVE'
        RETURNING representation_id
        """,
        (entity_type, entity_id, kind, profile_id, rendered_text, content_hash),
    )
    return str(cur.fetchone()[0])


def _split_into_chunks(text: str) -> list[str]:
    if len(text) <= MAX_CHARS_PER_CHUNK:
        return [text]
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) + 2 > MAX_CHARS_PER_CHUNK:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks or [text]


def _upsert_chunks(cur, representation_id: str, text: str, problem_id: str | None, solution_id: str | None) -> int:
    pieces = _split_into_chunks(text)
    chunk_kind = "FULL" if len(pieces) == 1 else "WINDOW"
    for ordinal, piece in enumerate(pieces):
        token_count = len(_encoding.encode(piece))
        cur.execute(
            """
            INSERT INTO search.chunk
              (representation_id, chunk_ordinal, chunk_kind, chunk_text, chunk_hash,
               token_count, char_count, problem_id, solution_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (representation_id, chunk_ordinal) DO UPDATE
              SET chunk_text = EXCLUDED.chunk_text, chunk_hash = EXCLUDED.chunk_hash,
                  token_count = EXCLUDED.token_count, char_count = EXCLUDED.char_count
            """,
            (representation_id, ordinal, chunk_kind, piece, _sha256(piece),
             token_count, len(piece), problem_id, solution_id),
        )
    return len(pieces)


def build_representations_and_chunks(cur, profile_id: str, limit: int | None,
                                     paper_codes: list[str] | None = None) -> tuple[int, int]:
    reps = chunks = 0

    query = "SELECT problem_id, statement_text FROM core.problem WHERE statement_text NOT LIKE '[Placeholder]%%'"
    params = []
    if paper_codes is not None:
        query += " AND paper_id IN (SELECT paper_id FROM core.paper WHERE external_code=ANY(%s))"
        params.append(paper_codes)
    if limit:
        query += f" LIMIT {int(limit)}"
    cur.execute(query, params)
    for problem_id, statement_text in cur.fetchall():
        rendered = f"[Problem] {statement_text}"
        rep_id = _upsert_representation(cur, profile_id, "PROBLEM", str(problem_id), "PROBLEM_STATEMENT", rendered)
        if rep_id:
            reps += 1
            chunks += _upsert_chunks(cur, rep_id, rendered, str(problem_id), None)

    query = "SELECT solution_id, body_markdown FROM core.solution WHERE body_markdown IS NOT NULL"
    params = []
    if paper_codes is not None:
        query += " AND problem_id IN (SELECT p.problem_id FROM core.problem p JOIN core.paper t USING(paper_id) WHERE t.external_code=ANY(%s))"
        params.append(paper_codes)
    if limit:
        query += f" LIMIT {int(limit)}"
    cur.execute(query, params)
    for solution_id, body_markdown in cur.fetchall():
        rendered = f"[Solution] {body_markdown}"
        rep_id = _upsert_representation(cur, profile_id, "SOLUTION", str(solution_id), "SOLUTION_FULL", rendered)
        if rep_id:
            reps += 1
            chunks += _upsert_chunks(cur, rep_id, rendered, None, str(solution_id))

    return reps, chunks


def embed_pending_chunks(cur, conn, model_id: str, limit: int | None,
                         paper_codes: list[str] | None = None,
                         representation_kinds: list[str] | None = None) -> tuple[int, int]:
    client = OpenAI()  # reads OPENAI_API_KEY from the environment (see _ensure_openai_api_key)

    cur.execute(
        """
        INSERT INTO pipeline.run (run_type, status, started_at)
        VALUES ('EMBEDDING_BACKFILL', 'IN_PROGRESS', now())
        RETURNING run_id
        """
    )
    run_id = cur.fetchone()[0]
    conn.commit()

    query = """
        SELECT c.chunk_id, c.chunk_text, c.chunk_hash, c.representation_id
        FROM search.chunk c
        LEFT JOIN search.embedding e ON e.chunk_id = c.chunk_id AND e.embedding_model_id = %s
        WHERE e.embedding_id IS NULL
    """
    params: list = [model_id]
    if paper_codes is not None:
        query = query.replace("e.embedding_model_id = %s", "e.embedding_model_id = %s AND e.status='ACTIVE'")
        query += """
          AND EXISTS (SELECT 1 FROM search.representation r
                      WHERE r.representation_id=c.representation_id AND r.status='ACTIVE')
          AND (c.problem_id IN (
                SELECT p.problem_id FROM core.problem p JOIN core.paper t USING(paper_id)
                WHERE t.external_code=ANY(%s))
               OR c.solution_id IN (
                SELECT s.solution_id FROM core.solution s JOIN core.problem p USING(problem_id)
                JOIN core.paper t USING(paper_id) WHERE t.external_code=ANY(%s)))
        """
        params.extend([paper_codes, paper_codes])
    if representation_kinds is not None:
        query += """
          AND EXISTS (SELECT 1 FROM search.representation r
                      WHERE r.representation_id=c.representation_id AND r.status='ACTIVE'
                        AND r.representation_kind=ANY(%s))
        """
        params.append(representation_kinds)
    if limit:
        query += " LIMIT %s"
        params.append(limit)
    cur.execute(query, params)
    pending = cur.fetchall()

    embedded = failed = 0
    for batch_start in range(0, len(pending), BATCH_SIZE):
        batch = pending[batch_start : batch_start + BATCH_SIZE]
        texts = [row[1] for row in batch]
        try:
            response = client.embeddings.create(model=MODEL_NAME, input=texts)
        except Exception as exc:  # noqa: BLE001 - record and keep going
            for chunk_id, _, chunk_hash, representation_id in batch:
                cur.execute(
                    """
                    INSERT INTO search.embedding_job
                      (run_id, representation_id, embedding_model_id, status, input_hash, last_error, completed_at)
                    VALUES (%s, %s, %s, 'FAILED', %s, %s, now())
                    ON CONFLICT (representation_id, embedding_model_id, input_hash) DO UPDATE
                      SET status = 'FAILED', last_error = EXCLUDED.last_error, completed_at = now()
                    """,
                    (run_id, representation_id, model_id, chunk_hash, str(exc)),
                )
                failed += 1
            conn.commit()
            continue

        if len(response.data) != len(batch) or sorted(item.index for item in response.data) != list(range(len(batch))):
            cur.execute(
                "UPDATE pipeline.run SET status='FAILED',completed_at=now(),failed_items=%s,"
                "metadata=metadata || jsonb_build_object('error','incomplete embedding provider batch') "
                "WHERE run_id=%s", (len(batch), run_id),
            )
            conn.commit()
            raise RuntimeError("Embedding provider returned an incomplete or invalid batch")
        for (chunk_id, _, chunk_hash, representation_id), item in zip(batch, sorted(response.data, key=lambda item: item.index)):
            vector_values = item.embedding
            if len(vector_values) != DIMENSIONS:
                cur.execute(
                    """
                    INSERT INTO search.embedding_job
                      (run_id, representation_id, embedding_model_id, status, input_hash, last_error, completed_at)
                    VALUES (%s, %s, %s, 'FAILED', %s, %s, now())
                    ON CONFLICT (representation_id, embedding_model_id, input_hash) DO UPDATE
                      SET status = 'FAILED', last_error = EXCLUDED.last_error, completed_at = now()
                    """,
                    (run_id, representation_id, model_id, chunk_hash,
                     f"dimension mismatch: got {len(vector_values)}, expected {DIMENSIONS}"),
                )
                failed += 1
                continue

            vector_literal = "[" + ",".join(repr(v) for v in vector_values) + "]"
            cur.execute(
                """
                INSERT INTO search.embedding (chunk_id, embedding_model_id, embedding, status)
                VALUES (%s, %s, %s::vector, 'ACTIVE')
                ON CONFLICT (chunk_id, embedding_model_id) DO UPDATE
                  SET embedding = EXCLUDED.embedding, status = 'ACTIVE', generated_at = now()
                """,
                (chunk_id, model_id, vector_literal),
            )
            cur.execute(
                """
                INSERT INTO search.embedding_job
                  (run_id, representation_id, embedding_model_id, status, input_hash, completed_at)
                VALUES (%s, %s, %s, 'COMPLETED', %s, now())
                ON CONFLICT (representation_id, embedding_model_id, input_hash) DO UPDATE
                  SET status = 'COMPLETED', completed_at = now(), last_error = NULL
                """,
                (run_id, representation_id, model_id, chunk_hash),
            )
            embedded += 1
        conn.commit()

    cur.execute(
        """
        UPDATE pipeline.run
        SET status = %s, completed_at = now(),
            expected_items = %s, completed_items = %s, failed_items = %s
        WHERE run_id = %s
        """,
        ("FAILED" if failed else "COMPLETED", len(pending), embedded, failed, run_id),
    )
    conn.commit()
    return embedded, failed


def create_hnsw_index(cur, model_id: str) -> None:
    index_name = f"idx_search_embedding_{MODEL_NAME.replace('-', '_')}_hnsw"
    cur.execute(
        f"""
        CREATE INDEX IF NOT EXISTS {index_name}
        ON search.embedding USING hnsw ((embedding::vector({DIMENSIONS})) vector_cosine_ops)
        WHERE embedding_model_id = '{model_id}' AND status = 'ACTIVE'
        """
    )
    print(f"index: {index_name} ready")


def cmd_status(cur) -> None:
    cur.execute(
        """
        SELECT representation_kind, status, count(*) FROM search.representation
        GROUP BY 1, 2 ORDER BY 1, 2
        """
    )
    print("representations:")
    for kind, status, n in cur.fetchall():
        print(f"  {kind:<20} {status:<12} {n}")

    cur.execute("SELECT count(*) FROM search.chunk")
    print(f"chunks: {cur.fetchone()[0]}")

    cur.execute(
        """
        SELECT em.model_name, e.status, count(*)
        FROM search.embedding e JOIN search.embedding_model em ON em.embedding_model_id = e.embedding_model_id
        GROUP BY 1, 2 ORDER BY 1, 2
        """
    )
    print("embeddings:")
    for model_name, status, n in cur.fetchall():
        print(f"  {model_name:<24} {status:<10} {n}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["backfill", "index", "status"])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--paper", action="append", help="Exact paper external code; repeat for a scoped backfill")
    args = parser.parse_args()

    with _connect() as conn:
        with conn.cursor() as cur:
            model_id, profile_id = ensure_model_and_profile(cur)
            conn.commit()

            if args.command == "backfill":
                _ensure_openai_api_key()
                cur.execute(
                    "INSERT INTO pipeline.run (run_type, status, started_at) "
                    "VALUES ('EMBED_BACKFILL', 'IN_PROGRESS', now()) RETURNING run_id"
                )
                run_id = cur.fetchone()[0]
                conn.commit()
                try:
                    reps, chunks = build_representations_and_chunks(cur, profile_id, args.limit, args.paper)
                    conn.commit()
                    print(f"representations: {reps} chunks: {chunks}")
                    embedded, failed = embed_pending_chunks(cur, conn, model_id, args.limit, args.paper)
                    print(f"embedded: {embedded} failed: {failed}")
                    if failed:
                        raise RuntimeError(f"{failed} embedding chunks failed; backfill is incomplete")
                except Exception as exc:
                    cur.execute(
                        "UPDATE pipeline.run SET status = 'FAILED', completed_at = now(), "
                        "metadata = metadata || jsonb_build_object('error', %s) WHERE run_id = %s",
                        (str(exc)[:2000], run_id),
                    )
                    conn.commit()
                    raise
                else:
                    cur.execute(
                        "UPDATE pipeline.run SET status = 'COMPLETED', completed_at = now(), "
                        "completed_items = %s, failed_items = %s WHERE run_id = %s",
                        (embedded, failed, run_id),
                    )
                    conn.commit()
            elif args.command == "index":
                create_hnsw_index(cur, model_id)
                conn.commit()
            elif args.command == "status":
                cmd_status(cur)


if __name__ == "__main__":
    main()
