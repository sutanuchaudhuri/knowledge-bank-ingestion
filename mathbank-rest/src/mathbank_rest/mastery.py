"""Mastery score computation — time-decayed, difficulty-weighted accuracy.

Formula per mathematics_tutor_db_plan/agent/18_future_student_profile_and_mastery.md
section 5. Pure functions here are unit-tested directly (no DB); the
recompute_* functions do the DB read/upsert round-trip and are what the
learner router calls after each attempt is recorded.

Simplifications vs the full design doc (tracked as follow-ups there):
- `is_correct` is boolean in this schema (no PARTIAL credit yet).
- `problem_concept`/`problem_technique` role/confidence weighting is not
  wired in yet (every linked concept/technique is treated as PRIMARY).
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from uuid import UUID

from mathbank_rest.db import learner as learner_db

HALF_LIFE_DAYS = 45.0

# core.problem.difficulty_band is a free-text label (e.g. "AIME D3 / Entry
# (Q1-5)"), not a numeric scale. This keyword heuristic maps it to [0, 1];
# unrecognized/missing bands fall back to the midpoint (0.5) rather than
# skewing mastery up or down for problems we can't classify.
_DIFFICULTY_KEYWORDS: list[tuple[str, float]] = [
    ("entry", 0.15),
    ("easy", 0.2),
    ("early", 0.25),
    ("medium", 0.5),
    ("mid", 0.5),
    ("late", 0.75),
    ("hard", 0.85),
    ("difficult", 0.85),
    ("challenge", 0.95),
]


def normalized_difficulty(difficulty_band: str | None) -> float:
    if not difficulty_band:
        return 0.5
    band = difficulty_band.lower()
    for keyword, value in _DIFFICULTY_KEYWORDS:
        if keyword in band:
            return value
    return 0.5


def correctness_weight(is_correct: bool) -> float:
    return 1.0 if is_correct else 0.0


def recency_weight(attempted_at: datetime, *, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    if attempted_at.tzinfo is None:
        attempted_at = attempted_at.replace(tzinfo=timezone.utc)
    days_since = max((now - attempted_at).total_seconds() / 86400.0, 0.0)
    return math.exp(-days_since / HALF_LIFE_DAYS)


def difficulty_weight(difficulty_band: str | None) -> float:
    return 1.0 + 0.5 * normalized_difficulty(difficulty_band)


def compute_mastery_score(attempts: list[dict], *, now: datetime | None = None) -> float:
    """attempts: rows with is_correct / attempted_at / difficulty_band (see db/learner.py)."""
    if not attempts:
        return 0.0
    numerator = 0.0
    denominator = 0.0
    for a in attempts:
        rw = recency_weight(a["attempted_at"], now=now)
        dw = difficulty_weight(a.get("difficulty_band"))
        numerator += correctness_weight(a["is_correct"]) * rw * dw
        denominator += rw * dw
    if denominator == 0.0:
        return 0.0
    return max(0.0, min(1.0, numerator / denominator))


def recompute_concept_mastery(student_id: UUID, concept_id: UUID) -> float:
    attempts = learner_db.get_attempts_for_concept(student_id, concept_id)
    score = compute_mastery_score(attempts)
    correct_count = sum(1 for a in attempts if a["is_correct"])
    last_attempt_at = attempts[-1]["attempted_at"] if attempts else datetime.now(timezone.utc)
    learner_db.upsert_concept_mastery(
        student_id=student_id,
        concept_id=concept_id,
        mastery_score=score,
        attempts_count=len(attempts),
        correct_count=correct_count,
        last_attempt_at=last_attempt_at,
    )
    return score


def recompute_technique_mastery(student_id: UUID, technique_id: UUID) -> float:
    attempts = learner_db.get_attempts_for_technique(student_id, technique_id)
    score = compute_mastery_score(attempts)
    correct_count = sum(1 for a in attempts if a["is_correct"])
    last_attempt_at = attempts[-1]["attempted_at"] if attempts else datetime.now(timezone.utc)
    learner_db.upsert_technique_mastery(
        student_id=student_id,
        technique_id=technique_id,
        mastery_score=score,
        attempts_count=len(attempts),
        correct_count=correct_count,
        last_attempt_at=last_attempt_at,
    )
    return score


def recompute_mastery_for_problem(student_id: UUID, problem_id: UUID) -> dict:
    """Called right after an attempt is recorded — fans out to every concept/technique
    the problem is tagged with (knowledge.problem_concept / problem_technique)."""
    linked = learner_db.get_concepts_and_techniques_for_problem(problem_id)
    concept_scores = {
        str(cid): recompute_concept_mastery(student_id, cid) for cid in linked["concept_ids"]
    }
    technique_scores = {
        str(tid): recompute_technique_mastery(student_id, tid) for tid in linked["technique_ids"]
    }
    return {"concepts": concept_scores, "techniques": technique_scores}
