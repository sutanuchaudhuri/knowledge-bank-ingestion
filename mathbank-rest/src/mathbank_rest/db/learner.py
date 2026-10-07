"""Read/write queries against the learner.* schema (student login + state).

Raw SQL via SQLAlchemy Core, same convention as db/queries.py — the schema is
managed by mathbank-db/sql/003_learner_schema.sql, not by this service.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text

from mathbank_rest.db.postgres import engine


def get_student_by_email(email: str) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT student_id, email, password_hash, first_name, last_name, display_name, status "
                "FROM learner.student_profile WHERE email = :email"
            ),
            {"email": email},
        ).mappings().first()
        return dict(row) if row else None


def create_student(*, email: str, password_hash: str, first_name: str, last_name: str) -> dict:
    display_name = f"{first_name} {last_name}".strip()
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "INSERT INTO learner.student_profile (email, password_hash, first_name, last_name, display_name) "
                "VALUES (:email, :password_hash, :first_name, :last_name, :display_name) "
                "RETURNING student_id, email, first_name, last_name, display_name, status, created_at"
            ),
            {
                "email": email, "password_hash": password_hash,
                "first_name": first_name, "last_name": last_name, "display_name": display_name,
            },
        ).mappings().first()
        return dict(row)


def touch_last_login(student_id: UUID) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE learner.student_profile SET last_login_at = :now WHERE student_id = :id"
            ),
            {"now": datetime.now(timezone.utc), "id": str(student_id)},
        )


def get_student_profile(student_id: UUID) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT student_id, email, first_name, last_name, display_name, status, created_at, last_login_at "
                "FROM learner.student_profile WHERE student_id = :id"
            ),
            {"id": str(student_id)},
        ).mappings().first()
        return dict(row) if row else None


def get_problem_id_by_code(canonical_code: str) -> UUID | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT problem_id FROM core.problem WHERE canonical_code = :code"),
            {"code": canonical_code},
        ).first()
        return row[0] if row else None


def insert_attempt(
    *,
    student_id: UUID,
    problem_id: UUID,
    is_correct: bool,
    submitted_answer: str | None,
    time_spent_seconds: int | None,
    hint_count: int,
    source: str,
) -> dict:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "INSERT INTO learner.attempt "
                "(student_id, problem_id, is_correct, submitted_answer, time_spent_seconds, "
                " hint_count, source) "
                "VALUES (:student_id, :problem_id, :is_correct, :submitted_answer, "
                " :time_spent_seconds, :hint_count, :source) "
                "RETURNING attempt_id, attempted_at"
            ),
            {
                "student_id": str(student_id),
                "problem_id": str(problem_id),
                "is_correct": is_correct,
                "submitted_answer": submitted_answer,
                "time_spent_seconds": time_spent_seconds,
                "hint_count": hint_count,
                "source": source,
            },
        ).mappings().first()
        return dict(row)


def list_attempts(student_id: UUID, *, limit: int = 50, offset: int = 0) -> list[dict]:
    """Past attempts for a student, most recent first, with problem context
    joined in so the UI doesn't need a second round-trip per row."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT a.attempt_id, a.is_correct, a.submitted_answer, a.time_spent_seconds, "
                "       a.hint_count, a.attempted_at, a.source, "
                "       p.canonical_code, p.problem_number, p.difficulty_band, "
                "       comp.name AS competition, ed.year "
                "FROM learner.attempt a "
                "JOIN core.problem p ON p.problem_id = a.problem_id "
                "JOIN core.paper pa ON pa.paper_id = p.paper_id "
                "JOIN core.competition_edition ed ON ed.edition_id = pa.edition_id "
                "JOIN core.competition comp ON comp.competition_id = ed.competition_id "
                "WHERE a.student_id = :id "
                "ORDER BY a.attempted_at DESC "
                "LIMIT :limit OFFSET :offset"
            ),
            {"id": str(student_id), "limit": limit, "offset": offset},
        ).mappings()
        return [dict(r) for r in rows]


def get_concepts_and_techniques_for_problem(problem_id: UUID) -> dict:
    """Which concepts/techniques a problem is tagged with — mastery fans out to these."""
    with engine.connect() as conn:
        concept_ids = [
            r[0]
            for r in conn.execute(
                text(
                    "SELECT concept_id FROM knowledge.problem_concept WHERE problem_id = :id"
                ),
                {"id": str(problem_id)},
            ).all()
        ]
        technique_ids = [
            r[0]
            for r in conn.execute(
                text(
                    "SELECT technique_id FROM knowledge.problem_technique WHERE problem_id = :id"
                ),
                {"id": str(problem_id)},
            ).all()
        ]
    return {"concept_ids": concept_ids, "technique_ids": technique_ids}


def get_attempts_for_concept(student_id: UUID, concept_id: UUID) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT a.is_correct, a.attempted_at, a.hint_count, p.difficulty_band "
                "FROM learner.attempt a "
                "JOIN knowledge.problem_concept pc ON pc.problem_id = a.problem_id "
                "JOIN core.problem p ON p.problem_id = a.problem_id "
                "WHERE a.student_id = :student_id AND pc.concept_id = :concept_id "
                "AND a.is_correct IS NOT NULL "
                "ORDER BY a.attempted_at"
            ),
            {"student_id": str(student_id), "concept_id": str(concept_id)},
        ).mappings()
        return [dict(r) for r in rows]


def get_attempts_for_technique(student_id: UUID, technique_id: UUID) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT a.is_correct, a.attempted_at, a.hint_count, p.difficulty_band "
                "FROM learner.attempt a "
                "JOIN knowledge.problem_technique pt ON pt.problem_id = a.problem_id "
                "JOIN core.problem p ON p.problem_id = a.problem_id "
                "WHERE a.student_id = :student_id AND pt.technique_id = :technique_id "
                "AND a.is_correct IS NOT NULL "
                "ORDER BY a.attempted_at"
            ),
            {"student_id": str(student_id), "technique_id": str(technique_id)},
        ).mappings()
        return [dict(r) for r in rows]


def upsert_concept_mastery(
    *, student_id: UUID, concept_id: UUID, mastery_score: float, attempts_count: int, correct_count: int,
    last_attempt_at: datetime,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO learner.concept_mastery "
                "(student_id, concept_id, mastery_score, attempts_count, correct_count, last_attempt_at) "
                "VALUES (:student_id, :concept_id, :mastery_score, :attempts_count, :correct_count, :last_attempt_at) "
                "ON CONFLICT (student_id, concept_id) DO UPDATE SET "
                " mastery_score = EXCLUDED.mastery_score, "
                " attempts_count = EXCLUDED.attempts_count, "
                " correct_count = EXCLUDED.correct_count, "
                " last_attempt_at = EXCLUDED.last_attempt_at, "
                " updated_at = now()"
            ),
            {
                "student_id": str(student_id),
                "concept_id": str(concept_id),
                "mastery_score": mastery_score,
                "attempts_count": attempts_count,
                "correct_count": correct_count,
                "last_attempt_at": last_attempt_at,
            },
        )


def upsert_technique_mastery(
    *, student_id: UUID, technique_id: UUID, mastery_score: float, attempts_count: int,
    correct_count: int, last_attempt_at: datetime,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO learner.technique_mastery "
                "(student_id, technique_id, mastery_score, attempts_count, correct_count, last_attempt_at) "
                "VALUES (:student_id, :technique_id, :mastery_score, :attempts_count, :correct_count, :last_attempt_at) "
                "ON CONFLICT (student_id, technique_id) DO UPDATE SET "
                " mastery_score = EXCLUDED.mastery_score, "
                " attempts_count = EXCLUDED.attempts_count, "
                " correct_count = EXCLUDED.correct_count, "
                " last_attempt_at = EXCLUDED.last_attempt_at, "
                " updated_at = now()"
            ),
            {
                "student_id": str(student_id),
                "technique_id": str(technique_id),
                "mastery_score": mastery_score,
                "attempts_count": attempts_count,
                "correct_count": correct_count,
                "last_attempt_at": last_attempt_at,
            },
        )


def get_mastery_summary(student_id: UUID) -> dict:
    with engine.connect() as conn:
        concepts = conn.execute(
            text(
                "SELECT c.slug, c.name, m.mastery_score, m.attempts_count, m.correct_count, m.last_attempt_at "
                "FROM learner.concept_mastery m JOIN knowledge.concept c ON c.concept_id = m.concept_id "
                "WHERE m.student_id = :id ORDER BY m.mastery_score ASC"
            ),
            {"id": str(student_id)},
        ).mappings()
        techniques = conn.execute(
            text(
                "SELECT t.slug, t.name, m.mastery_score, m.attempts_count, m.correct_count, m.last_attempt_at "
                "FROM learner.technique_mastery m JOIN knowledge.technique t ON t.technique_id = m.technique_id "
                "WHERE m.student_id = :id ORDER BY m.mastery_score ASC"
            ),
            {"id": str(student_id)},
        ).mappings()
        return {"concepts": [dict(r) for r in concepts], "techniques": [dict(r) for r in techniques]}


def get_cohort_weak_concepts(*, min_students: int = 1, limit: int = 20) -> list[dict]:
    """Aggregate (no PII) view across every student's concept_mastery — surfaces
    which concepts the whole cohort struggles with, lowest average mastery first.
    Useful at the platform level (is this a hard concept, a thin corpus of
    practice problems, or a retrieval gap?) rather than any one student's view.
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT c.slug, c.name, "
                "       COUNT(DISTINCT m.student_id) AS student_count, "
                "       CAST(AVG(m.mastery_score) AS DOUBLE PRECISION) AS avg_mastery_score, "
                "       SUM(m.attempts_count) AS total_attempts "
                "FROM learner.concept_mastery m "
                "JOIN knowledge.concept c ON c.concept_id = m.concept_id "
                "GROUP BY c.slug, c.name "
                "HAVING COUNT(DISTINCT m.student_id) >= :min_students "
                "ORDER BY avg_mastery_score ASC "
                "LIMIT :limit"
            ),
            {"min_students": min_students, "limit": limit},
        ).mappings()
        return [dict(r) for r in rows]
