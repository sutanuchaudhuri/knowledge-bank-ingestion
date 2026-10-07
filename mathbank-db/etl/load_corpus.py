"""Load the mathbank_data_ingestion corpus (CSV index/taxonomy mirror + crawled
AoPS/PDF problem text) into the mathbank Postgres database.

Idempotent: safe to re-run. Upserts use natural keys (external_code / slug /
canonical_code) carried over from the source spreadsheet IDs and crawl paths.

Run via `make etl` in mathbank-db/ (applies sql/001_schema.sql first).
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from pathlib import Path

import psycopg
from psycopg.types.json import Json
from pdf_assets import paper_images, question_images, store_images

REPO_ROOT = Path(__file__).resolve().parents[2]
INGESTION_ROOT = REPO_ROOT / "mathbank_data_ingestion"
CORPUS_DIR = INGESTION_ROOT / "src" / "mathbank" / "data" / "maths_corpus"
AOPS_CRAWL_DIR = INGESTION_ROOT / "data" / "crawl"
PDF_CRAWL_DIR = INGESTION_ROOT / "data" / "crawl_pdf"

# crawl_pdf/<dir> -> core.competition.external_code. Only competitions with
# actual per-question problem.md/solution.md splits are listed.
PDF_COMPETITION_DIRS = {
    "chmmc": "CHMMC",
    "cmm": "CMM",
    "mpg_oly": "MPG_OLY",
    "pumac": "PUMAC",
    "smt": "SMT",
    "hmmt_feb": "HMMT_FEB",
    "hmmt_nov": "HMMT_NOV",
    "hmmt_inv": "HMMT_INV",
    "purple_ms": "PURPLE_MS",
    "purple_hs": "PURPLE_HS",
    "arml": "ARML",
    "arml_local": "ARML_LOCAL",
    "arml_power": "ARML_POWER",
}

PAPER_ID_RE = re.compile(r"^PAPER_[A-Z]+(?:_[A-Z]+)*_(\d{4})_(.+)$")
MD_HEADER_RE = re.compile(r"^(#{1,2}[^\n]*\n+)+")
MD_IMAGE_BLOCK_RE = re.compile(r"\n+---\n+(!\[[^\n]*\n*)+\s*$")

CONFIDENCE_MAP = {"high": 0.9, "medium": 0.6, "low": 0.3}


def _load_env() -> dict[str, str]:
    # PG_ENV_FILE lets `PG_ENV_FILE=../mathbank-graph/remote.env python
    # etl/load_corpus.py` target Neon instead of the local .env.
    env_path = Path(os.environ.get("PG_ENV_FILE") or Path(__file__).resolve().parents[1] / ".env")
    env: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def confidence_to_numeric(text: str | None) -> float | None:
    if not text:
        return None
    return CONFIDENCE_MAP.get(text.strip().lower())


def read_rows(filename: str):
    path = CORPUS_DIR / filename
    with path.open(newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def load_competitions(cur) -> tuple[int, int]:
    inserted = skipped = 0
    for row in read_rows("competition_catalog.csv"):
        code = row.get("Competition_ID", "").strip()
        name = row.get("Competition", "").strip()
        if not code or not name:
            skipped += 1
            continue
        cur.execute(
            """
            INSERT INTO core.competition (external_code, name, level)
            VALUES (%s, %s, %s)
            ON CONFLICT (external_code) DO UPDATE
              SET name = EXCLUDED.name, level = EXCLUDED.level
            """,
            (code, name, row.get("Event_or_Round") or None),
        )
        inserted += 1
    return inserted, skipped


def load_editions_and_papers(cur) -> tuple[int, int, dict[str, str]]:
    """Returns (papers_inserted, skipped, {external Test_ID: paper_id})."""
    cur.execute("SELECT competition_id, external_code FROM core.competition")
    competition_by_code = {code: cid for cid, code in cur.fetchall() if code}

    inserted = skipped = 0
    paper_ids: dict[str, str] = {}
    edition_cache: dict[tuple[str, int], str] = {}

    for row in read_rows("test_registry.csv"):
        test_id = row.get("Test_ID", "").strip()
        comp_code = row.get("Competition_ID", "").strip()
        year_raw = row.get("Year", "").strip()
        if not test_id or comp_code not in competition_by_code or not year_raw.isdigit():
            skipped += 1
            continue

        year = int(year_raw)
        competition_id = competition_by_code[comp_code]
        edition_key = (competition_id, year)
        edition_id = edition_cache.get(edition_key)
        if edition_id is None:
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
                WHERE competition_id = %s AND year = %s
                  AND season IS NULL AND edition_label IS NULL
                """,
                (competition_id, year),
            )
            edition_id = cur.fetchone()[0]
            edition_cache[edition_key] = edition_id

        paper_code = (row.get("Form") or "SINGLE").strip() or "SINGLE"
        session = (row.get("Session") or "").strip()
        if session and session.lower() != "regular":
            paper_code = f"{paper_code}-{session}"
        question_count_raw = row.get("Question_Count", "").strip()
        question_count = int(question_count_raw) if question_count_raw.isdigit() else None

        cur.execute(
            """
            INSERT INTO core.paper (edition_id, external_code, paper_code, question_count)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (external_code) DO UPDATE
              SET question_count = EXCLUDED.question_count
            RETURNING paper_id
            """,
            (edition_id, test_id, paper_code, question_count),
        )
        paper_ids[test_id] = str(cur.fetchone()[0])
        inserted += 1

    return inserted, skipped, paper_ids


def load_problems(cur, paper_ids: dict[str, str]) -> tuple[int, int]:
    inserted = skipped = 0
    for row in read_rows("question_index.csv"):
        question_id = row.get("Question_ID", "").strip()
        test_id = row.get("Test_ID", "").strip()
        q_number_raw = row.get("Q_Number", "").strip()
        if not question_id or test_id not in paper_ids or not q_number_raw.isdigit():
            skipped += 1
            continue

        paper_id = paper_ids[test_id]
        problem_number = int(q_number_raw)
        source_url = row.get("AoPS_Question_URL") or row.get("Direct_Problem_URL") or None
        official_answer = row.get("Correct_Answer") or None
        difficulty_band = row.get("Difficulty_Band") or None
        classification_status = row.get("Classification_Status") or None
        statement_text = (
            f"[Placeholder] {row.get('Exam_Level', '')} {row.get('Year', '')} "
            f"Problem {problem_number}. Full statement not yet ingested — see source_url."
        ).strip()
        content_hash = hashlib.sha256(statement_text.encode("utf-8")).hexdigest()

        cur.execute(
            """
            INSERT INTO core.problem
              (paper_id, problem_number, canonical_code, statement_text,
               official_answer, source_url, difficulty_band, classification_status,
               content_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (canonical_code) DO UPDATE
              SET official_answer = EXCLUDED.official_answer,
                  source_url = EXCLUDED.source_url,
                  difficulty_band = EXCLUDED.difficulty_band,
                  classification_status = EXCLUDED.classification_status,
                  updated_at = now()
            """,
            (
                paper_id,
                problem_number,
                question_id,
                statement_text,
                official_answer,
                source_url,
                difficulty_band,
                classification_status,
                content_hash,
            ),
        )
        inserted += 1
    return inserted, skipped


def _upsert_solution(cur, problem_id: str, solution_kind: str, revision: int, body_markdown: str,
                     *, only_missing: bool = False) -> None:
    cur.execute(
        """
        INSERT INTO core.solution (problem_id, solution_kind, revision, body_markdown, verification_status)
        VALUES (%s, %s, %s, %s, 'UNVERIFIED')
        ON CONFLICT (problem_id, solution_kind, revision) DO UPDATE
          SET body_markdown = EXCLUDED.body_markdown
        WHERE NOT %s OR trim(coalesce(core.solution.body_markdown,''))=''
        """,
        (problem_id, solution_kind, revision, body_markdown, only_missing),
    )


# Image filenames are sha256(source_url)[:12] (see image_downloader.py), so an
# identical filename reused across many different problem directories means the
# same source URL — i.e. shared site chrome (logo/footer/banner), not a unique
# per-problem diagram. Anything over this threshold is excluded from ingestion.
DECORATIVE_IMAGE_REPEAT_THRESHOLD = 5


def _find_decorative_image_filenames(crawl_dir: Path) -> set[str]:
    counts: dict[str, int] = {}
    for images_dir in crawl_dir.glob("*/*/images"):
        for image_path in images_dir.iterdir():
            if image_path.is_file():
                counts[image_path.name] = counts.get(image_path.name, 0) + 1
    return {name for name, n in counts.items() if n > DECORATIVE_IMAGE_REPEAT_THRESHOLD}


def enrich_problems_from_aops_crawl(cur) -> tuple[int, int]:
    """Backfill real statement/answer/solutions from data/crawl/*/*/parsed.json
    (AoPS wiki pages — the question_index.csv mirror has no full problem text)."""
    cur.execute("SELECT canonical_code, problem_id FROM core.problem")
    problem_by_code = {code: pid for code, pid in cur.fetchall()}

    updated = skipped = 0
    for parsed_path in sorted(AOPS_CRAWL_DIR.glob("*/*/parsed.json")):
        record = json.loads(parsed_path.read_text(encoding="utf-8"))
        question_id = record.get("question_id") or parsed_path.parent.name
        if question_id.startswith("PAPER_"):
            continue
        problem_id = problem_by_code.get(question_id)
        if not problem_id:
            skipped += 1
            continue

        problem_text = (record.get("problem_text") or "").strip().replace("\x00", "")
        answer_value = record.get("answer_value") or None
        if problem_text:
            content_hash = hashlib.sha256(problem_text.encode("utf-8")).hexdigest()
            cur.execute(
                """
                UPDATE core.problem
                SET statement_text = %s, official_answer = COALESCE(%s, official_answer),
                    content_hash = %s, updated_at = now()
                WHERE problem_id = %s
                """,
                (problem_text, answer_value, content_hash, problem_id),
            )

        for i, solution_text in enumerate(record.get("solution_texts") or [], start=1):
            if solution_text and solution_text.strip():
                _upsert_solution(cur, problem_id, "AOPS_COMMUNITY", i, solution_text.strip().replace("\x00", ""))

        manifest_path = parsed_path.parent / "image_manifest.json"
        if manifest_path.is_file():
            verified = question_images(parsed_path.parent, source_kind="AOPS")
            store_images(cur, problem_id, verified, source_kind="AOPS")
        elif (parsed_path.parent / "images").is_dir():
            question_images(parsed_path.parent, source_kind="AOPS")

        updated += 1
    return updated, skipped


def _clean_crawl_pdf_markdown(text: str) -> str:
    """Strip the redundant '# PAPER_..._Qnn — ...' header and trailing image block."""
    text = MD_HEADER_RE.sub("", text, count=1)
    text = MD_IMAGE_BLOCK_RE.sub("", text)
    return text.strip()


def load_pdf_crawl_problems(cur, competition_by_code: dict[str, str]) -> tuple[int, int]:
    """Create/enrich core.problem + core.solution from data/crawl_pdf/<dir>/PAPER_.../questions/Qnn/
    (whole-paper PDFs split and OCR/layout-parsed to markdown — these competitions are not
    yet registered in question_index.csv, so rows are created here rather than matched)."""
    inserted = skipped = 0
    edition_cache: dict[tuple[str, int], str] = {}
    paper_cache: dict[str, str] = {}

    for dir_name, comp_code in PDF_COMPETITION_DIRS.items():
        competition_id = competition_by_code.get(comp_code)
        comp_dir = PDF_CRAWL_DIR / dir_name
        if not competition_id or not comp_dir.is_dir():
            continue

        for paper_dir in sorted(comp_dir.iterdir()):
            if not paper_dir.is_dir():
                continue
            match = PAPER_ID_RE.match(paper_dir.name)
            if not match:
                skipped += 1
                continue
            year = int(match.group(1))
            paper_code = match.group(2)
            paper_id_external = paper_dir.name

            edition_key = (competition_id, year)
            edition_id = edition_cache.get(edition_key)
            if edition_id is None:
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
                    WHERE competition_id = %s AND year = %s
                      AND season IS NULL AND edition_label IS NULL
                    """,
                    (competition_id, year),
                )
                edition_id = cur.fetchone()[0]
                edition_cache[edition_key] = edition_id

            paper_id = paper_cache.get(paper_id_external)
            if paper_id is None:
                cur.execute(
                    """
                    INSERT INTO core.paper (edition_id, external_code, paper_code)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (external_code) DO UPDATE SET paper_code = EXCLUDED.paper_code
                    RETURNING paper_id
                    """,
                    (edition_id, paper_id_external, paper_code),
                )
                paper_id = str(cur.fetchone()[0])
                paper_cache[paper_id_external] = paper_id

            visuals = paper_images(paper_dir)
            for q_dir in sorted((paper_dir / "questions").glob("Q*")):
                problem_md = q_dir / "problem.md"
                if not problem_md.exists():
                    skipped += 1
                    continue
                q_match = re.match(r"Q(\d+)", q_dir.name)
                if not q_match:
                    skipped += 1
                    continue
                problem_number = int(q_match.group(1))
                canonical_code = f"{paper_id_external}_Q{problem_number:02d}"
                raw_text = problem_md.read_text(encoding="utf-8").replace("\x00", "")
                statement_text = _clean_crawl_pdf_markdown(raw_text)
                if not statement_text:
                    skipped += 1
                    continue
                content_hash = hashlib.sha256(statement_text.encode("utf-8")).hexdigest()

                cur.execute(
                    """
                    INSERT INTO core.problem (paper_id, problem_number, canonical_code, statement_text, content_hash)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (canonical_code) DO UPDATE
                      SET statement_text = EXCLUDED.statement_text,
                          content_hash = EXCLUDED.content_hash,
                          updated_at = now()
                    RETURNING problem_id
                    """,
                    (paper_id, problem_number, canonical_code, statement_text, content_hash),
                )
                problem_id = str(cur.fetchone()[0])
                inserted += 1

                store_images(cur, problem_id, visuals.get(problem_number, []), source_kind="PDF")

                solution_md = q_dir / "solution.md"
                if solution_md.exists():
                    raw_solution = solution_md.read_text(encoding="utf-8").replace("\x00", "")
                    solution_text = _clean_crawl_pdf_markdown(raw_solution)
                    if solution_text:
                        _upsert_solution(cur, problem_id, "PDF_PARSED", 1, solution_text)

    return inserted, skipped


def load_concepts(cur) -> tuple[int, int]:
    inserted = skipped = 0
    level_by_node_type = {"Topic": 0, "Subtopic": 1, "Concept": 2}

    for row in read_rows("canonical_topic_hierarchy.csv"):
        node_type = (row.get("Node_Type") or "").strip()
        raw_id = (row.get("Canonical_Topic_ID") or "").strip()
        if node_type not in level_by_node_type or not raw_id:
            skipped += 1
            continue
        name = (
            row.get("Concept_or_Technique")
            or row.get("Subtopic")
            or row.get("Topic")
            or raw_id
        )
        cur.execute(
            """
            INSERT INTO knowledge.concept (slug, name, description, level)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (slug) DO NOTHING
            """,
            (slugify(raw_id), name, row.get("Definition") or None, level_by_node_type[node_type]),
        )
        inserted += cur.rowcount

    for row in read_rows("topic_taxonomy.csv"):
        raw_id = (row.get("Concept_ID") or "").strip()
        name = (row.get("Concept") or "").strip()
        if not raw_id or not name:
            skipped += 1
            continue
        cur.execute(
            """
            INSERT INTO knowledge.concept (slug, name, description, level)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (slug) DO NOTHING
            """,
            (slugify(raw_id), name, row.get("Evidence_Basis") or None, None),
        )
        inserted += cur.rowcount

    return inserted, skipped


def load_techniques(cur) -> tuple[int, int]:
    inserted = skipped = 0
    for row in read_rows("technique_catalog.csv"):
        raw_id = (row.get("Technique_ID") or "").strip()
        name = (row.get("Technique_Name") or "").strip()
        if not raw_id or not name:
            skipped += 1
            continue
        cur.execute(
            """
            INSERT INTO knowledge.technique (slug, name, description)
            VALUES (%s, %s, %s)
            ON CONFLICT (slug) DO UPDATE
              SET description = EXCLUDED.description
            """,
            (slugify(raw_id), name, row.get("Definition") or None),
        )
        inserted += cur.rowcount
    return inserted, skipped


def load_problem_concepts(cur, question_codes: set[str] | None = None) -> tuple[int, int]:
    cur.execute("SELECT canonical_code, problem_id FROM core.problem")
    problem_by_code = {code: pid for code, pid in cur.fetchall()}
    cur.execute("SELECT slug, concept_id FROM knowledge.concept")
    concept_by_slug = {slug: cid for slug, cid in cur.fetchall()}

    inserted = skipped = 0
    for row in read_rows("question_taxonomy_map.csv"):
        if question_codes is not None and row.get("Question_ID") not in question_codes:
            continue
        problem_id = problem_by_code.get((row.get("Question_ID") or "").strip())
        concept_id = concept_by_slug.get(slugify((row.get("Concept_ID") or "").strip()))
        if not problem_id or not concept_id:
            skipped += 1
            continue
        cur.execute(
            """
            INSERT INTO knowledge.problem_concept
              (problem_id, concept_id, role, confidence, assertion_source, review_status)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (problem_id, concept_id, role) DO NOTHING
            """,
            (
                problem_id,
                concept_id,
                "PRIMARY",
                confidence_to_numeric(row.get("Confidence")),
                row.get("Evidence_Source") or "CORPUS_IMPORT",
                "PENDING",
            ),
        )
        if cur.rowcount:
            inserted += 1
        else:
            skipped += 1
    return inserted, skipped


def load_problem_techniques(cur, question_codes: set[str] | None = None) -> tuple[int, int]:
    cur.execute("SELECT canonical_code, problem_id FROM core.problem")
    problem_by_code = {code: pid for code, pid in cur.fetchall()}
    cur.execute("SELECT slug, technique_id FROM knowledge.technique")
    technique_by_slug = {slug: tid for slug, tid in cur.fetchall()}

    inserted = skipped = 0
    for row in read_rows("question_technique_map.csv"):
        if question_codes is not None and row.get("Question_ID") not in question_codes:
            continue
        problem_id = problem_by_code.get((row.get("Question_ID") or "").strip())
        technique_id = technique_by_slug.get(slugify((row.get("Technique_ID") or "").strip()))
        if not problem_id or not technique_id:
            skipped += 1
            continue
        role = (row.get("Role") or "REQUIRED").strip().upper().replace(" ", "_") or "REQUIRED"
        cur.execute(
            """
            INSERT INTO knowledge.problem_technique
              (problem_id, technique_id, role, confidence, assertion_source, review_status)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (problem_id, technique_id, role) DO NOTHING
            """,
            (
                problem_id,
                technique_id,
                role,
                confidence_to_numeric(row.get("Evidence_Confidence")),
                row.get("Evidence_Source") or "CORPUS_IMPORT",
                "PENDING",
            ),
        )
        if cur.rowcount:
            inserted += 1
        else:
            skipped += 1
    return inserted, skipped


def load_concept_relations(cur) -> tuple[int, int]:
    cur.execute("SELECT slug, concept_id FROM knowledge.concept")
    concept_by_slug = {slug: cid for slug, cid in cur.fetchall()}

    inserted = skipped = 0
    for row in read_rows("knowledge_graph_edges.csv"):
        if row.get("From_Type") != "Concept" or row.get("To_Type") != "Concept":
            continue
        from_id = concept_by_slug.get(slugify((row.get("From_ID") or "").strip()))
        to_id = concept_by_slug.get(slugify((row.get("To_ID") or "").strip()))
        if not from_id or not to_id:
            skipped += 1
            continue
        weight_raw = (row.get("Weight") or "").strip()
        try:
            strength = float(weight_raw) if weight_raw else confidence_to_numeric(row.get("Confidence"))
        except ValueError:
            strength = confidence_to_numeric(row.get("Confidence"))
        cur.execute(
            """
            INSERT INTO knowledge.concept_relation
              (from_concept_id, to_concept_id, relation_type, strength, assertion_source, review_status)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (from_concept_id, to_concept_id, relation_type) DO NOTHING
            """,
            (
                from_id,
                to_id,
                row.get("Edge_Type") or "RELATED_TO",
                strength,
                row.get("Evidence_Type") or "CORPUS_IMPORT",
                "PENDING",
            ),
        )
        if cur.rowcount:
            inserted += 1
        else:
            skipped += 1
    return inserted, skipped


def main() -> None:
    env = _load_env()
    # NEON_PG_* (from mathbank-graph/remote.env) target the remote Neon
    # instance; falls back to the local mathbank-db cluster when absent.
    conninfo = (
        f"host={env.get('NEON_PG_HOST', '127.0.0.1')} "
        f"port={env.get('NEON_PG_PORT') or env.get('PG_PORT', '5433')} "
        f"dbname={env.get('NEON_PG_DATABASE') or env.get('APP_DB', 'mathbank')} "
        f"user={env.get('NEON_PG_USER') or env.get('APP_USER', 'mathbank_app')} "
        f"password={env.get('NEON_PG_PASSWORD') or env.get('APP_DB_PASSWORD', '')}"
        + (f" sslmode={env['NEON_PG_SSLMODE']}" if env.get("NEON_PG_SSLMODE") else "")
    )

    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:
            # Progress tracking — see pipeline.run (mathematics_tutor_db_plan's
            # system-of-record for ingestion runs, previously unused by this
            # script). A row left stuck at RUNNING (no completed_at) means the
            # process crashed/was killed mid-run — check the log/error output
            # from that invocation, not this table, for the cause.
            cur.execute(
                "INSERT INTO pipeline.run (run_type, status, started_at, metadata) "
                "VALUES (%s, 'RUNNING', now(), %s) RETURNING run_id",
                ("load_corpus", Json({"target": env.get("NEON_PG_HOST", "local")})),
            )
            run_id = cur.fetchone()[0]
            conn.commit()
            total_inserted = 0
            total_failed = 0

            try:
                steps = [
                    ("competitions", lambda: load_competitions(cur)),
                ]
                for label, fn in steps:
                    inserted, skipped = fn()
                    print(f"{label}: inserted={inserted} skipped={skipped}")
                    total_inserted += inserted
                conn.commit()

                papers_inserted, papers_skipped, paper_ids = load_editions_and_papers(cur)
                print(f"editions+papers: inserted={papers_inserted} skipped={papers_skipped}")
                total_inserted += papers_inserted
                conn.commit()

                problems_inserted, problems_skipped = load_problems(cur, paper_ids)
                print(f"problems: inserted={problems_inserted} skipped={problems_skipped}")
                total_inserted += problems_inserted
                conn.commit()

                cur.execute("SELECT external_code, competition_id FROM core.competition")
                competition_by_code = {code: str(cid) for code, cid in cur.fetchall() if code}

                pdf_inserted, pdf_skipped = load_pdf_crawl_problems(cur, competition_by_code)
                print(f"pdf_crawl_problems: inserted={pdf_inserted} skipped={pdf_skipped}")
                total_inserted += pdf_inserted
                conn.commit()

                aops_updated, aops_skipped = enrich_problems_from_aops_crawl(cur)
                print(f"aops_crawl_enrichment: updated={aops_updated} skipped={aops_skipped}")
                total_inserted += aops_updated
                conn.commit()

                concepts_inserted, concepts_skipped = load_concepts(cur)
                print(f"concepts: inserted={concepts_inserted} skipped={concepts_skipped}")
                total_inserted += concepts_inserted
                conn.commit()

                techniques_inserted, techniques_skipped = load_techniques(cur)
                print(f"techniques: inserted={techniques_inserted} skipped={techniques_skipped}")
                total_inserted += techniques_inserted
                conn.commit()

                pc_inserted, pc_skipped = load_problem_concepts(cur)
                print(f"problem_concept: inserted={pc_inserted} skipped={pc_skipped}")
                total_inserted += pc_inserted
                conn.commit()

                pt_inserted, pt_skipped = load_problem_techniques(cur)
                print(f"problem_technique: inserted={pt_inserted} skipped={pt_skipped}")
                total_inserted += pt_inserted
                conn.commit()

                cr_inserted, cr_skipped = load_concept_relations(cur)
                print(f"concept_relation: inserted={cr_inserted} skipped={cr_skipped}")
                total_inserted += cr_inserted
                conn.commit()
            except Exception as exc:
                total_failed += 1
                cur.execute(
                    "UPDATE pipeline.run SET status='FAILED', completed_at=now(), "
                    "completed_items=%s, failed_items=%s, metadata = metadata || %s "
                    "WHERE run_id=%s",
                    (total_inserted, total_failed, Json({"error": str(exc)[:2000]}), run_id),
                )
                conn.commit()
                raise
            else:
                cur.execute(
                    "UPDATE pipeline.run SET status='COMPLETED', completed_at=now(), "
                    "completed_items=%s WHERE run_id=%s",
                    (total_inserted, run_id),
                )
                conn.commit()


if __name__ == "__main__":
    main()
