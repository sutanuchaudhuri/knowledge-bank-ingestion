"""Original problem documents, separate from student-safe diagram crops."""

import logging
from pathlib import Path
from urllib.parse import quote, urlsplit

from sqlalchemy import text

log = logging.getLogger(__name__)
PDF_ROOT = Path(__file__).resolve().parents[4] / "mathbank_data_ingestion/data/crawl_pdf"


def source_record(conn, code: str) -> dict | None:
    row = (
        conn.execute(
            text("""
        SELECT p.source_url, s.problem_url, s.crawl_dir, s.paper_external_code, s.link_scope
        FROM core.problem p
        LEFT JOIN pipeline.pdf_source s
          ON s.paper_external_code = regexp_replace(p.canonical_code, '_Q[0-9]+$', '')
        WHERE p.canonical_code = :code
    """),
            {"code": code},
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None


def source_pdf(record: dict) -> Path | None:
    directory, paper = record.get("crawl_dir"), record.get("paper_external_code")
    if not directory or not paper:
        return None
    path = (PDF_ROOT / directory / paper / "problem.pdf").resolve()
    if PDF_ROOT.resolve() not in path.parents:
        raise ValueError("Source PDF path is outside the corpus")
    return path if path.is_file() else None


def source_metadata(record: dict, code: str) -> dict | None:
    local = source_pdf(record)
    url = record.get("problem_url") or record.get("source_url")
    if url:
        try:
            parsed = urlsplit(url)
            valid = (
                parsed.scheme in {"http", "https"}
                and bool(parsed.hostname)
                and not (parsed.username or parsed.password)
            )
        except ValueError:
            valid = False
        if not valid:
            log.warning("%s: invalid original source URL", code)
            url = None
    if not url and local is None:
        return None
    registered_pdf = bool(record.get("problem_url")) and record.get("link_scope") in {
        "DIRECT_PROBLEM_AND_SOLUTION",
        "DIRECT_PROBLEM_ONLY",
        "DIRECT_PROBLEM_PDF",
        "AGGREGATE_MULTI_EXAM_PDF",
    }
    is_pdf = (
        local is not None
        or registered_pdf
        or bool(url and urlsplit(url).path.lower().endswith(".pdf"))
    )
    return {
        "url": url,
        "kind": "pdf" if is_pdf else "web",
        "embed_url": f"/api/rest/solve/source-pdf/{quote(code, safe='')}"
        if local
        else url
        if is_pdf
        else None,
        "label": "Original full document" if is_pdf else "Original source page",
    }
