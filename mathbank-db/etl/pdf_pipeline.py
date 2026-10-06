"""PDF download → parse → ingest pipeline tracker.

Tracks per-paper progress through three stages in `pipeline.pdf_source`
(one row per `paper_registry.csv` direct-link "PAPER_*" row, or one row per
admin-registered paper via mathbank-rest's `POST /v1/admin/papers`):

    PENDING -> DOWNLOADED -> PARSED -> INGESTED   (per stage column)

Some competitions publish PDFs (CHMMC/CMM/SMT/PUMaC/MPG_OLY — need Docling
parsing); others publish a single HTML page per paper. `source_kind`
(`PDF` | `HTML`, see sql/004_admin_pipeline.sql) controls which fetch path a
row goes through at the `fetch` stage — `reconcile`/`ingest` are format-agnostic
(both just look for `questions/Qnn/problem.md` on disk) so neither needs to
know or care which fetch path produced those files.

Subcommands (safe, local-only — no network calls):
    discover    upsert pipeline.pdf_source from paper_registry.csv
    reconcile   check data/crawl_pdf/<dir>/<paper>/ on disk, update
                download_status / parse_status / questions_found
    ingest      load PARSED-but-not-yet-INGESTED papers into
                core.problem / core.solution (same logic as
                etl/load_corpus.py::load_pdf_crawl_problems, scoped per paper
                and recorded via pipeline.run / pipeline.work_item)
    status      print a progress summary table
    run         discover -> reconcile -> ingest -> status

Fetch subcommand (NOT run by `run` — triggers real network downloads):
    fetch       PENDING PDF rows: shell out to
                mathbank_data_ingestion/scripts/crawl_pdf_papers.py (Docling,
                needs that project's own .venv). PENDING HTML rows: fetch +
                strip tags directly here (stdlib urllib/html.parser, no extra
                deps) — see cmd_fetch_html.

Usage:
    python etl/pdf_pipeline.py discover
    python etl/pdf_pipeline.py reconcile
    python etl/pdf_pipeline.py ingest
    python etl/pdf_pipeline.py status
    python etl/pdf_pipeline.py run
    python etl/pdf_pipeline.py fetch --limit 10   # real downloads, opt-in only
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import subprocess
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

import psycopg

REPO_ROOT = Path(__file__).resolve().parents[2]
INGESTION_ROOT = REPO_ROOT / "mathbank_data_ingestion"
CORPUS_DIR = INGESTION_ROOT / "src" / "mathbank" / "data" / "maths_corpus"
PDF_CRAWL_DIR = INGESTION_ROOT / "data" / "crawl_pdf"

# Load corpus utilities (markdown cleanup, NUL-stripping) without duplicating them.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from load_corpus import _clean_crawl_pdf_markdown, _load_env, _upsert_solution  # noqa: E402
from pdf_assets import paper_images, store_images  # noqa: E402

ARCHIVE_POINTER_PREFIX = "PAPER_ARCHIVE_"
DIRECT_LINK_SCOPES = {
    "DIRECT_PROBLEM_AND_SOLUTION",
    "DIRECT_PROBLEM_ONLY",
    "DIRECT_PROBLEM_PDF",
    "AGGREGATE_MULTI_EXAM_PDF",
}


def _connect(*, direct: bool = False):
    # NEON_PG_* (from mathbank-graph/remote.env, via PG_ENV_FILE) target the
    # remote Neon instance; falls back to the local mathbank-db cluster when
    # absent — same precedence as etl/load_corpus.py::main().
    env = _load_env()
    host = env.get("NEON_PG_HOST", "127.0.0.1")
    if direct and host.endswith(".neon.tech"):
        host = host.replace("-pooler.", ".")
    conninfo = (
        f"host={host} "
        f"port={env.get('NEON_PG_PORT') or env.get('PG_PORT', '5433')} "
        f"dbname={env.get('NEON_PG_DATABASE') or env.get('APP_DB', 'mathbank')} "
        f"user={env.get('NEON_PG_USER') or env.get('APP_USER', 'mathbank_app')} "
        f"password={env.get('NEON_PG_PASSWORD') or env.get('APP_DB_PASSWORD', '')}"
        + (f" sslmode={env['NEON_PG_SSLMODE']}" if env.get("NEON_PG_SSLMODE") else "")
    )
    return psycopg.connect(conninfo)


def cmd_discover(cur) -> None:
    inserted = skipped = 0
    with (CORPUS_DIR / "paper_registry.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            paper_id = (row.get("Paper_ID") or "").strip()
            link_scope = (row.get("Link_Scope") or "").strip()
            problem_url = (row.get("Problem_URL") or "").strip() or None
            if (
                not paper_id
                or paper_id.startswith(ARCHIVE_POINTER_PREFIX)
                or link_scope not in DIRECT_LINK_SCOPES
                or not problem_url
            ):
                skipped += 1
                continue

            competition_code = (row.get("Competition_ID") or "").strip()
            crawl_dir = competition_code.lower()
            cur.execute(
                """
                INSERT INTO pipeline.pdf_source
                  (paper_external_code, competition_external_code, crawl_dir,
                   problem_url, solution_url, link_scope)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (paper_external_code) DO UPDATE
                  SET problem_url = EXCLUDED.problem_url,
                      solution_url = EXCLUDED.solution_url,
                      link_scope = EXCLUDED.link_scope,
                      updated_at = now()
                """,
                (
                    paper_id,
                    competition_code,
                    crawl_dir,
                    problem_url,
                    (row.get("Solution_URL") or "").strip() or None,
                    link_scope,
                ),
            )
            inserted += 1
    print(f"discover: tracked={inserted} skipped(archive-pointer/no-direct-link)={skipped}")


def cmd_reconcile(cur) -> None:
    """Check the filesystem for what's already downloaded/parsed and update statuses."""
    cur.execute(
        "SELECT paper_external_code, crawl_dir, download_status, parse_status FROM pipeline.pdf_source"
    )
    rows = cur.fetchall()

    downloaded = parsed = 0
    for paper_external_code, crawl_dir, download_status, parse_status in rows:
        paper_dir = PDF_CRAWL_DIR / crawl_dir / paper_external_code
        has_pdf = (paper_dir / "problem.pdf").exists()
        question_dirs = sorted((paper_dir / "questions").glob("Q*")) if paper_dir.is_dir() else []
        questions_found = sum(1 for q in question_dirs if (q / "problem.md").exists())

        new_download_status = "DOWNLOADED" if (has_pdf or questions_found) else download_status
        new_parse_status = "PARSED" if questions_found else parse_status

        if new_download_status != download_status or new_parse_status != parse_status or questions_found:
            cur.execute(
                """
                UPDATE pipeline.pdf_source
                SET download_status = %s,
                    downloaded_at = CASE WHEN %s = 'DOWNLOADED' AND downloaded_at IS NULL THEN now() ELSE downloaded_at END,
                    parse_status = %s,
                    parsed_at = CASE WHEN %s = 'PARSED' AND parsed_at IS NULL THEN now() ELSE parsed_at END,
                    questions_found = %s,
                    updated_at = now()
                WHERE paper_external_code = %s
                """,
                (
                    new_download_status,
                    new_download_status,
                    new_parse_status,
                    new_parse_status,
                    questions_found,
                    paper_external_code,
                ),
            )
        if new_download_status == "DOWNLOADED" and download_status != "DOWNLOADED":
            downloaded += 1
        if new_parse_status == "PARSED" and parse_status != "PARSED":
            parsed += 1

    print(f"reconcile: newly_downloaded={downloaded} newly_parsed={parsed} (checked {len(rows)} tracked papers)")


def cmd_ingest(
    cur, paper_codes: list[str] | None = None, question_codes: set[str] | None = None
) -> None:
    cur.execute("SELECT external_code, competition_id FROM core.competition")
    competition_by_code = {code: str(cid) for code, cid in cur.fetchall() if code}

    cur.execute(
        """
        SELECT paper_external_code, crawl_dir, competition_external_code
        FROM pipeline.pdf_source
        WHERE parse_status = 'PARSED' AND ingest_status != 'INGESTED'
          AND (%s::text[] IS NULL OR paper_external_code = ANY(%s))
        """,
        (paper_codes, paper_codes),
    )
    pending = cur.fetchall()

    cur.execute(
        """
        INSERT INTO pipeline.run (run_type, status, started_at)
        VALUES ('PDF_INGEST', 'IN_PROGRESS', now())
        RETURNING run_id
        """
    )
    run_id = cur.fetchone()[0]

    total_q = total_s = failed = 0
    for paper_external_code, crawl_dir, competition_code in pending:
        competition_id = competition_by_code.get(competition_code)
        paper_dir = PDF_CRAWL_DIR / crawl_dir / paper_external_code
        match = re.match(r"^PAPER_[A-Z]+(?:_[A-Z]+)*_(\d{4})_(.+)$", paper_external_code)
        if not competition_id or not match or not paper_dir.is_dir():
            cur.execute(
                """
                UPDATE pipeline.pdf_source SET ingest_status = 'FAILED',
                  last_error = 'missing competition/paper_id match/dir', updated_at = now()
                WHERE paper_external_code = %s
                """,
                (paper_external_code,),
            )
            failed += 1
            continue

        year = int(match.group(1))
        paper_code = match.group(2)

        cur.execute(
            """
            INSERT INTO core.competition_edition (competition_id, year)
            VALUES (%s, %s)
            ON CONFLICT (competition_id, year, season, edition_label) DO NOTHING
            """,
            (competition_id, year),
        )
        cur.execute(
            """
            SELECT edition_id FROM core.competition_edition
            WHERE competition_id = %s AND year = %s AND season IS NULL AND edition_label IS NULL
            """,
            (competition_id, year),
        )
        edition_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO core.paper (edition_id, external_code, paper_code)
            VALUES (%s, %s, %s)
            ON CONFLICT (external_code) DO UPDATE SET paper_code = EXCLUDED.paper_code
            RETURNING paper_id
            """,
            (edition_id, paper_external_code, paper_code),
        )
        pg_paper_id = str(cur.fetchone()[0])

        q_count = s_count = 0
        visuals = paper_images(paper_dir)
        for q_dir in sorted((paper_dir / "questions").glob("Q*")):
            problem_md = q_dir / "problem.md"
            q_match = re.match(r"Q(\d+)", q_dir.name)
            if not problem_md.exists() or not q_match:
                continue
            problem_number = int(q_match.group(1))
            canonical_code = f"{paper_external_code}_Q{problem_number:02d}"
            if question_codes is not None and canonical_code not in question_codes:
                continue
            statement_text = _clean_crawl_pdf_markdown(
                problem_md.read_text(encoding="utf-8").replace("\x00", "")
            )
            if not statement_text:
                continue
            content_hash = hashlib.sha256(statement_text.encode("utf-8")).hexdigest()

            cur.execute(
                """
                INSERT INTO core.problem (paper_id, problem_number, canonical_code, statement_text, content_hash)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (canonical_code) DO UPDATE
                  SET statement_text = EXCLUDED.statement_text, content_hash = EXCLUDED.content_hash, updated_at = now()
                RETURNING problem_id
                """,
                (pg_paper_id, problem_number, canonical_code, statement_text, content_hash),
            )
            pg_problem_id = str(cur.fetchone()[0])
            q_count += 1
            if competition_code.startswith(("PURPLE_", "ARML")):
                answers_path = paper_dir / "answers.json"
                if not answers_path.is_file() and competition_code.startswith("PURPLE_"):
                    raise ValueError(f"{paper_external_code}: missing official answer key")
                answers = json.loads(answers_path.read_text()) if answers_path.is_file() else {}
                answer = answers.get(str(problem_number))
                if not answer and competition_code.startswith("PURPLE_"):
                    raise ValueError(f"{canonical_code}: missing official answer")
                cur.execute(
                    "UPDATE core.problem SET official_answer=%s,answer_type=%s,source_url="
                    "(SELECT problem_url FROM pipeline.pdf_source WHERE paper_external_code=%s) "
                    "WHERE problem_id=%s",
                    (answer, "INTEGER" if competition_code.startswith("PURPLE_") else "TEXT" if answer else None,
                     paper_external_code, pg_problem_id),
                )

            store_images(cur, pg_problem_id, visuals.get(problem_number, []), source_kind="PDF")

            solution_md = q_dir / "solution.md"
            if solution_md.exists():
                solution_text = _clean_crawl_pdf_markdown(
                    solution_md.read_text(encoding="utf-8").replace("\x00", "")
                )
                if solution_text:
                    _upsert_solution(cur, pg_problem_id, "PDF_PARSED", 1, solution_text)
                    s_count += 1

        cur.execute(
            """
            INSERT INTO pipeline.work_item (run_id, item_type, item_key, status, completed_at, metrics)
            VALUES (%s, 'pdf_paper', %s, 'COMPLETED', now(), jsonb_build_object('questions', %s, 'solutions', %s))
            ON CONFLICT (run_id, item_type, item_key) DO NOTHING
            """,
            (run_id, paper_external_code, q_count, s_count),
        )
        cur.execute(
            """
            UPDATE pipeline.pdf_source
            SET ingest_status = 'INGESTED', ingested_at = now(),
                questions_ingested = %s, solutions_ingested = %s, last_error = NULL, updated_at = now()
            WHERE paper_external_code = %s
            """,
            (q_count, s_count, paper_external_code),
        )
        total_q += q_count
        total_s += s_count

    cur.execute(
        """
        UPDATE pipeline.run
        SET status = 'COMPLETED', completed_at = now(),
            expected_items = %s, completed_items = %s, failed_items = %s
        WHERE run_id = %s
        """,
        (len(pending), len(pending) - failed, failed, run_id),
    )
    print(
        f"ingest: papers_processed={len(pending) - failed} failed={failed} "
        f"questions={total_q} solutions={total_s} (run_id={run_id})"
    )


def cmd_status(cur) -> None:
    cur.execute(
        """
        SELECT competition_external_code,
               count(*) AS tracked,
               count(*) FILTER (WHERE download_status = 'DOWNLOADED') AS downloaded,
               count(*) FILTER (WHERE parse_status = 'PARSED') AS parsed,
               count(*) FILTER (WHERE ingest_status = 'INGESTED') AS ingested,
               coalesce(sum(questions_ingested), 0) AS questions_ingested,
               coalesce(sum(solutions_ingested), 0) AS solutions_ingested
        FROM pipeline.pdf_source
        GROUP BY competition_external_code
        ORDER BY competition_external_code
        """
    )
    rows = cur.fetchall()
    header = (
        f"{'competition':<12} {'tracked':>8} {'downloaded':>11} {'parsed':>7} "
        f"{'ingested':>9} {'questions':>10} {'solutions':>10}"
    )
    print(header)
    print("-" * len(header))
    totals = [0] * 6
    for comp, tracked, downloaded, parsed, ingested, q, s in rows:
        print(f"{comp:<12} {tracked:>8} {downloaded:>11} {parsed:>7} {ingested:>9} {q:>10} {s:>10}")
        for i, v in enumerate((tracked, downloaded, parsed, ingested, q, s)):
            totals[i] += v
    print("-" * len(header))
    print(
        f"{'TOTAL':<12} {totals[0]:>8} {totals[1]:>11} {totals[2]:>7} "
        f"{totals[3]:>9} {totals[4]:>10} {totals[5]:>10}"
    )


def cmd_fetch(cur, limit: int) -> None:
    """Opt-in: shells out to the real downloader for PENDING PDF papers. Makes
    real HTTP requests to competition archive sites — run deliberately, not via
    `run`. PENDING HTML papers are handled by cmd_fetch_html instead (no
    Docling/PDF dependency needed for those) — see main()'s dispatch."""
    cur.execute(
        """
        SELECT DISTINCT competition_external_code FROM pipeline.pdf_source
        WHERE download_status = 'PENDING' AND source_kind = 'PDF'
        ORDER BY 1
        LIMIT %s
        """,
        (limit,),
    )
    competitions = [row[0] for row in cur.fetchall()]
    if not competitions:
        print("fetch: nothing PENDING")
        return
    venv_python = INGESTION_ROOT / ".venv" / "bin" / "python"
    for competition in competitions:
        print(f"fetch: running crawl_pdf_papers.py --competition {competition} --limit {limit}")
        subprocess.run(
            [
                str(venv_python),
                "scripts/crawl_pdf_papers.py",
                "--competition",
                competition,
                "--limit",
                str(limit),
            ],
            cwd=INGESTION_ROOT,
            check=False,
        )


class _HtmlTextExtractor(HTMLParser):
    """Minimal stdlib tag-stripper — good enough for a single-paper HTML page
    without assuming any competition-specific markup. Drops <script>/<style>
    content entirely; everything else's text is kept, block-level tags insert
    a newline so paragraphs/problem numbers don't run together."""

    _BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "section", "article"}
    _SKIP_TAGS = {"script", "style", "nav", "header", "footer"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        elif tag in self._BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self.chunks.append(data)

    def text(self) -> str:
        raw = " ".join("".join(self.chunks).split("\n"))
        # Collapse runs of whitespace left over from stripped tags/attrs.
        return re.sub(r" {2,}", " ", re.sub(r"\n{2,}", "\n\n", "".join(self.chunks))).strip()


def _fetch_url_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "mathbank-ingestion/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - operator-provided admin URLs
        raw_html = resp.read().decode(resp.headers.get_content_charset() or "utf-8", errors="replace")
    parser = _HtmlTextExtractor()
    parser.feed(html.unescape(raw_html))
    return parser.text()


def cmd_fetch_html(cur, limit: int) -> None:
    """Opt-in: fetches PENDING HTML papers directly (stdlib urllib + html.parser,
    no Docling/extra deps). Treats the whole page as a single question
    (questions/Q01/problem.md) since generic HTML can't be assumed to have a
    per-question structure the way the AoPS wiki parser (crawl_unmapped.py) or
    Docling PDF splitter (crawl_pdf_papers.py) can rely on for their specific
    sources. A competition whose HTML page genuinely has multiple per-question
    sub-pages needs its own small parser following this same contract
    (write questions/Qnn/problem.md + optional solution.md under crawl_dir),
    not a change to reconcile/ingest."""
    cur.execute(
        """
        SELECT paper_external_code, crawl_dir, problem_url, solution_url
        FROM pipeline.pdf_source
        WHERE download_status = 'PENDING' AND source_kind = 'HTML'
        ORDER BY paper_external_code
        LIMIT %s
        """,
        (limit,),
    )
    rows = cur.fetchall()
    if not rows:
        print("fetch-html: nothing PENDING")
        return

    ok = failed = 0
    for paper_external_code, crawl_dir, problem_url, solution_url in rows:
        q_dir = PDF_CRAWL_DIR / crawl_dir / paper_external_code / "questions" / "Q01"
        try:
            q_dir.mkdir(parents=True, exist_ok=True)
            problem_text = _fetch_url_text(problem_url)
            if not problem_text:
                raise ValueError("fetched page had no extractable text")
            (q_dir / "problem.md").write_text(problem_text, encoding="utf-8")
            if solution_url:
                solution_text = _fetch_url_text(solution_url)
                if solution_text:
                    (q_dir / "solution.md").write_text(solution_text, encoding="utf-8")
            cur.execute(
                """
                UPDATE pipeline.pdf_source
                SET download_status = 'DOWNLOADED', downloaded_at = now(),
                    parse_status = 'PARSED', parsed_at = now(),
                    questions_found = 1, last_error = NULL, updated_at = now()
                WHERE paper_external_code = %s
                """,
                (paper_external_code,),
            )
            ok += 1
            print(f"fetch-html: OK {paper_external_code}")
        except Exception as exc:  # noqa: BLE001 - recorded per-row, loop continues
            cur.execute(
                """
                UPDATE pipeline.pdf_source
                SET download_status = 'FAILED', last_error = %s, updated_at = now()
                WHERE paper_external_code = %s
                """,
                (str(exc)[:500], paper_external_code),
            )
            failed += 1
            print(f"fetch-html: FAIL {paper_external_code}: {exc}")
    print(f"fetch-html: ok={ok} failed={failed}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "command", choices=["discover", "reconcile", "ingest", "status", "run", "fetch"]
    )
    parser.add_argument("--limit", type=int, default=10, help="fetch: competitions to process")
    args = parser.parse_args()

    with _connect() as conn:
        with conn.cursor() as cur:
            if args.command == "discover":
                cmd_discover(cur)
            elif args.command == "reconcile":
                cmd_reconcile(cur)
            elif args.command == "ingest":
                cmd_ingest(cur)
            elif args.command == "status":
                cmd_status(cur)
            elif args.command == "fetch":
                cmd_fetch(cur, args.limit)
                conn.commit()
                cmd_fetch_html(cur, args.limit)
            elif args.command == "run":
                cmd_discover(cur)
                conn.commit()
                cmd_reconcile(cur)
                conn.commit()
                cmd_ingest(cur)
                conn.commit()
                cmd_status(cur)
            conn.commit()


if __name__ == "__main__":
    main()
