"""Admin write queries — competitions + paper registration + pipeline status.

Raw SQL via SQLAlchemy Core, same convention as db/queries.py. Writes here are
intentionally narrow: insert a competition row, insert a pipeline.pdf_source
row (PENDING by default — the actual download/parse/ingest/embed/graph work
is done by the existing etl/pdf_pipeline.py, etl/embed_corpus.py,
etl/load_corpus.py, mathbank-graph/etl/project_from_postgres.py scripts, all
of which already read pipeline.pdf_source / pipeline.run / pipeline.graph_projection).
"""
from __future__ import annotations

from sqlalchemy import text

from mathbank_rest.db.postgres import engine


def create_competition(
    *, external_code: str, name: str, organization: str | None, country: str | None, level: str | None
) -> dict:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "INSERT INTO core.competition (external_code, name, organization, country, level) "
                "VALUES (:external_code, :name, :organization, :country, :level) "
                "ON CONFLICT (external_code) DO UPDATE SET "
                " name = EXCLUDED.name, organization = EXCLUDED.organization, "
                " country = EXCLUDED.country, level = EXCLUDED.level "
                "RETURNING competition_id, external_code, name, organization, country, level"
            ),
            {
                "external_code": external_code,
                "name": name,
                "organization": organization,
                "country": country,
                "level": level,
            },
        ).mappings().first()
        return dict(row)


def register_paper(
    *,
    paper_external_code: str,
    competition_external_code: str,
    crawl_dir: str,
    problem_url: str,
    solution_url: str | None,
    source_kind: str,
    link_scope: str | None,
) -> dict:
    """Inserts a PENDING pipeline.pdf_source row — the download/parse/ingest
    stages pick it up automatically next time those scripts run (no separate
    'activate' step). Re-registering the same paper_external_code updates the
    URLs/source_kind rather than creating a duplicate row."""
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "INSERT INTO pipeline.pdf_source "
                "(paper_external_code, competition_external_code, crawl_dir, "
                " problem_url, solution_url, source_kind, link_scope) "
                "VALUES (:paper_external_code, :competition_external_code, :crawl_dir, "
                " :problem_url, :solution_url, :source_kind, :link_scope) "
                "ON CONFLICT (paper_external_code) DO UPDATE SET "
                " problem_url = EXCLUDED.problem_url, solution_url = EXCLUDED.solution_url, "
                " source_kind = EXCLUDED.source_kind, link_scope = EXCLUDED.link_scope, "
                " updated_at = now() "
                "RETURNING pdf_source_id, paper_external_code, competition_external_code, "
                " source_kind, download_status, parse_status, ingest_status, created_at"
            ),
            {
                "paper_external_code": paper_external_code,
                "competition_external_code": competition_external_code,
                "crawl_dir": crawl_dir,
                "problem_url": problem_url,
                "solution_url": solution_url,
                "source_kind": source_kind,
                "link_scope": link_scope,
            },
        ).mappings().first()
        return dict(row)


def list_papers(
    *, competition: str | None = None, status: str | None = None, limit: int = 100, offset: int = 0
) -> list[dict]:
    clauses = []
    params: dict = {"limit": limit, "offset": offset}
    if competition:
        clauses.append("competition_external_code = :competition")
        params["competition"] = competition
    if status:
        clauses.append(
            "(download_status = :status OR parse_status = :status OR ingest_status = :status)"
        )
        params["status"] = status
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"SELECT s.*, w.status AS batch_status, w.metrics AS batch_metrics, "
                f"       w.run_id AS batch_run_id, w.last_error AS batch_error "
                f"FROM pipeline.pdf_source s LEFT JOIN LATERAL ("
                f" SELECT status, metrics, run_id, last_error FROM pipeline.work_item "
                f" WHERE item_type='paper_end_to_end' AND item_key=s.paper_external_code "
                f" ORDER BY started_at DESC LIMIT 1"
                f") w ON true {where} "
                f"ORDER BY s.created_at DESC LIMIT :limit OFFSET :offset"
            ),
            params,
        ).mappings()
        return [dict(r) for r in rows]


def retry_paper(paper_external_code: str) -> dict | None:
    """Resets a FAILED paper back through PENDING so the next pipeline run retries it.
    Does not touch stages that already succeeded (e.g. a paper DOWNLOADED+PARSED
    but FAILED at ingest only resets ingest_status)."""
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "UPDATE pipeline.pdf_source SET "
                " download_status = CASE WHEN download_status = 'FAILED' THEN 'PENDING' ELSE download_status END, "
                " parse_status = CASE WHEN parse_status = 'FAILED' THEN 'PENDING' ELSE parse_status END, "
                " ingest_status = CASE WHEN ingest_status = 'FAILED' THEN 'PENDING' ELSE ingest_status END, "
                " last_error = NULL, updated_at = now() "
                "WHERE paper_external_code = :code "
                "RETURNING pdf_source_id, paper_external_code, download_status, parse_status, ingest_status"
            ),
            {"code": paper_external_code},
        ).mappings().first()
        return dict(row) if row else None


def list_pipeline_runs(limit: int = 20) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT run_id, run_type, status, started_at, completed_at, "
                "       completed_items, failed_items, expected_items, heartbeat_at, metadata "
                "FROM pipeline.run ORDER BY started_at DESC LIMIT :limit"
            ),
            {"limit": limit},
        ).mappings()
        return [dict(r) for r in rows]


def list_graph_projections(limit: int = 20) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT projection_run_id, graph_name, status, started_at, completed_at, "
                "       nodes_upserted, edges_upserted, error "
                "FROM pipeline.graph_projection ORDER BY started_at DESC LIMIT :limit"
            ),
            {"limit": limit},
        ).mappings()
        return [dict(r) for r in rows]
