"""Seed 3 demo student profiles with realistic names + varied attempt history,
for the student-profile UI (requirements/12_STUDENT_PROFILE_AND_ADMIN_LOGIN_UI_REQUIREMENTS.md).

Each profile is deliberately different so the UI has something real to show:
  - Maya Chen       — "strong": mostly correct, few/no hints
  - Daniel Osei      — "struggling": mostly incorrect, many hints
  - Priya Patel      — "mixed": a realistic blend, some concepts solid, some weak

Idempotent: skips any demo student whose email already exists (re-running
just confirms the password and prints the credentials again).

Usage:
    cd mathbank-rest && .venv/bin/python scripts/seed_demo_students.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import text

from mathbank_rest import mastery, security
from mathbank_rest.db import learner as learner_db
from mathbank_rest.db.postgres import engine

DEMO_PASSWORD = "Demo1234!"

DEMO_STUDENTS = [
    {"email": "maya.chen@example.com", "first_name": "Maya", "last_name": "Chen", "profile": "strong"},
    {"email": "daniel.osei@example.com", "first_name": "Daniel", "last_name": "Osei", "profile": "struggling"},
    {"email": "priya.patel@example.com", "first_name": "Priya", "last_name": "Patel", "profile": "mixed"},
]

# (is_correct_probability, hint_count_range) per profile — deliberately caricatured
# so the mastery/weakness breakdown is obviously different between the three.
PROFILE_SHAPE = {
    "strong": {"p_correct": 0.9, "hint_range": (0, 1)},
    "struggling": {"p_correct": 0.25, "hint_range": (1, 4)},
    "mixed": {"p_correct": 0.55, "hint_range": (0, 3)},
}


def _demo_problem_pool(limit: int = 18) -> list[dict]:
    """A spread of already-classified AIME problems to simulate attempts against."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT DISTINCT p.problem_id, p.canonical_code "
                "FROM core.problem p "
                "JOIN knowledge.problem_concept pc ON pc.problem_id = p.problem_id "
                "JOIN core.paper pa ON pa.paper_id = p.paper_id "
                "JOIN core.competition_edition ed ON ed.edition_id = pa.edition_id "
                "JOIN core.competition comp ON comp.competition_id = ed.competition_id "
                "WHERE comp.external_code = 'AIME' "
                "ORDER BY p.canonical_code "
                "LIMIT :limit"
            ),
            {"limit": limit},
        ).mappings()
        return [dict(r) for r in rows]


def _ensure_student(email: str, first_name: str, last_name: str) -> dict:
    existing = learner_db.get_student_by_email(email)
    if existing is not None:
        print(f"  already exists: {email} ({existing['student_id']})")
        return existing
    password_hash = security.hash_password(DEMO_PASSWORD)
    student = learner_db.create_student(
        email=email, password_hash=password_hash, first_name=first_name, last_name=last_name
    )
    print(f"  created: {email} ({student['student_id']})")
    return student


def _simulate_attempts(student_id, problems: list[dict], profile: str) -> None:
    shape = PROFILE_SHAPE[profile]
    rng = random.Random(f"{student_id}-{profile}")  # deterministic per student
    for problem in problems:
        is_correct = rng.random() < shape["p_correct"]
        hint_count = rng.randint(*shape["hint_range"]) if not is_correct else rng.randint(0, 1)
        attempt = learner_db.insert_attempt(
            student_id=student_id,
            problem_id=problem["problem_id"],
            is_correct=is_correct,
            submitted_answer=None,
            time_spent_seconds=rng.randint(60, 900),
            hint_count=hint_count,
            source="seed_demo_students",
        )
        mastery.recompute_mastery_for_problem(student_id, problem["problem_id"])
        print(f"    {problem['canonical_code']}: correct={is_correct} hints={hint_count}")


def main() -> None:
    problems = _demo_problem_pool()
    if not problems:
        print("No classified AIME problems found — seed the corpus first.")
        return
    print(f"Using {len(problems)} problems as the shared attempt pool.\n")

    for demo in DEMO_STUDENTS:
        print(f"=== {demo['first_name']} {demo['last_name']} ({demo['profile']}) ===")
        student = _ensure_student(demo["email"], demo["first_name"], demo["last_name"])
        # Each profile attempts a different-sized subset so attempt counts differ too.
        n = {"strong": 12, "struggling": 8, "mixed": 15}[demo["profile"]]
        _simulate_attempts(student["student_id"], problems[:n], demo["profile"])
        print()

    print("Demo login credentials (all three share the same password):")
    print(f"  password: {DEMO_PASSWORD}")
    for demo in DEMO_STUDENTS:
        print(f"  {demo['email']}  ({demo['first_name']} {demo['last_name']})")


if __name__ == "__main__":
    main()
