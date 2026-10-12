"""Point-in-time-safe reads from PostgreSQL (requirements/55 §2 EXTRACT stage,
requirements/13 §2).

Rules these functions MUST follow once implemented (requirements/03 §4 leakage rules):
- Every query takes an explicit `as_of_time` and only reads rows with
  `created_at <= as_of_time` (or the equivalent event timestamp column).
- Never join to future attempts, future course completions, or post-timestamp
  hint/solution reveal state.
- Use a read-only Postgres role (see ../config.py, .env.example).
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from mathbank_ml_training.config import Settings


def get_engine(settings: Settings) -> Engine:
    """Builds a read-only SQLAlchemy engine for the configured Postgres instance.

    TODO (requirements/55 §2): confirm the `mathbank_ml_readonly` role actually has
    SELECT-only grants on the tables this package reads (learner.*, pedagogy.*,
    knowledge.*, activity.*, quiz.*) before this is ever pointed at a non-dev database —
    do not reuse mathbank-rest's read/write app role.
    """
    url = (
        f"postgresql+psycopg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )
    return create_engine(url, pool_pre_ping=True)


def extract_learner_attempts(engine: Engine, *, student_id: str, as_of_time: datetime) -> list[dict]:
    """Extracts raw attempt/event rows for one student, truncated at `as_of_time`.

    TODO (requirements/03 §1 "student mastery" features, requirements/02 §2 event
    contract): write the actual SQL. Must read from `learner.attempt`, `quiz.response`,
    and `learner.micro_course_state_event` (the three attempt-shaped sources this repo
    already has — confirmed by reading mathbank-rest/src/mathbank_rest/db/learner.py's
    own UNION ALL pattern across these tables, built in an earlier session for mastery
    scoring; reuse that same union, do not reinvent it).
    """
    raise NotImplementedError(
        "requirements/55 §2 EXTRACT stage — see docstring for the exact tables to union"
    )


def extract_exam_sessions(engine: Engine, *, student_id: str, as_of_time: datetime) -> list[dict]:
    """Extracts exam session + per-question timing rows (requirements/02 §3).

    TODO: blocked until `learner.exam_session`/`learner.exam_question_event` exist with
    adequate coverage — check requirements/09's data-readiness gate before assuming this
    table is populated richly enough to be useful (requirements/58 §3).
    """
    raise NotImplementedError("requirements/55 §2 EXTRACT stage — exam session tables")


def extract_content_catalog(engine: Engine, *, content_hash_watermark: str | None = None) -> list[dict]:
    """Extracts problem/course/route rows for content-feature building (requirements/03
    §1 "problem behavior"/"course/route").

    TODO: implement against knowledge.*/pedagogy.* canonical tables, filtered to
    APPROVED/PUBLISHED content only (never train features from unreviewed draft content).
    """
    raise NotImplementedError("requirements/55 §2 EXTRACT stage — content catalog")
