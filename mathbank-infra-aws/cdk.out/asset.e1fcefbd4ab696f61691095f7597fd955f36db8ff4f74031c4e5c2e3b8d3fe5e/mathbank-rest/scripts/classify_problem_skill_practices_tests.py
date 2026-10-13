"""ENR-3 (requirements/51): classification pass for knowledge.problem_skill's near-empty
PRACTICES/TESTS relation types (confirmed live, requirements/50 DGAP-1/DGAP-2: only 2
PRACTICES and 1 TESTS row existed, against 38,105 REQUIRES rows for 12,542 problems x 6,208
skills).

Classification rule (explicit, auditable, derived from an EXISTING signal already present
on every REQUIRES row -- not a new LLM call, not a guess):
  - role='primary' AND required_level >= 4  -> also insert a TESTS row
    (the problem's primary, highest-rigor skill -- the one it specifically assesses mastery of)
  - role='primary' AND required_level = 3   -> also insert a PRACTICES row
    (a primary pedagogical focus of the problem, at a more moderate rigor)
  - everything else (role='supporting', or primary at required_level <= 2 or NULL) is left
    as REQUIRES only -- these read as prerequisite/contextual, not the problem's own focus.

Honesty note (this directly addresses a caution this project's own requirements/51 §8 raised
against "fabricating pedagogically unverified claims"): every inserted row is explicitly
marked review_status='PENDING' and approval_method='automatic', with a distinct, traceable
`source` value -- this is an automatic, auditable INFERENCE from an existing human/assistant-
authored signal (role + required_level), not a claim of new verified pedagogical fact. It
does not modify or remove any existing REQUIRES row; both coexist (the table's primary key is
(problem_id, skill_id, relation_type, role), so this is purely additive).

Idempotent: ON CONFLICT DO NOTHING on the natural key; safe to re-run.
"""
from __future__ import annotations

import argparse

from sqlalchemy import text

from mathbank_rest.db.postgres import engine

SOURCE = "classification:primary-role-required-level-v1"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes; default is dry-run.")
    args = parser.parse_args()

    with engine.connect() as conn:
        tests_candidates = conn.execute(text("""
            SELECT count(*) FROM knowledge.problem_skill
            WHERE relation_type='REQUIRES' AND role='primary' AND required_level >= 4
        """)).scalar_one()
        practices_candidates = conn.execute(text("""
            SELECT count(*) FROM knowledge.problem_skill
            WHERE relation_type='REQUIRES' AND role='primary' AND required_level = 3
        """)).scalar_one()
        existing_tests = conn.execute(text(
            "SELECT count(*) FROM knowledge.problem_skill WHERE relation_type='TESTS'"
        )).scalar_one()
        existing_practices = conn.execute(text(
            "SELECT count(*) FROM knowledge.problem_skill WHERE relation_type='PRACTICES'"
        )).scalar_one()

    print(f"TESTS candidates (primary, required_level>=4): {tests_candidates} (existing TESTS rows: {existing_tests})")
    print(f"PRACTICES candidates (primary, required_level=3): {practices_candidates} (existing PRACTICES rows: {existing_practices})")

    if not args.apply:
        print("Dry run only -- pass --apply to write. No changes made.")
        return

    with engine.begin() as conn:
        tests_result = conn.execute(text("""
            INSERT INTO knowledge.problem_skill
                (problem_id, skill_id, relation_type, role, required_level, importance,
                 source, confidence, review_status, approval_method)
            SELECT problem_id, skill_id, 'TESTS', role, required_level, importance,
                   :source, 0.6, 'PENDING', 'automatic'
            FROM knowledge.problem_skill
            WHERE relation_type='REQUIRES' AND role='primary' AND required_level >= 4
            ON CONFLICT (problem_id, skill_id, relation_type, role) DO NOTHING
        """), {"source": SOURCE})
        practices_result = conn.execute(text("""
            INSERT INTO knowledge.problem_skill
                (problem_id, skill_id, relation_type, role, required_level, importance,
                 source, confidence, review_status, approval_method)
            SELECT problem_id, skill_id, 'PRACTICES', role, required_level, importance,
                   :source, 0.6, 'PENDING', 'automatic'
            FROM knowledge.problem_skill
            WHERE relation_type='REQUIRES' AND role='primary' AND required_level = 3
            ON CONFLICT (problem_id, skill_id, relation_type, role) DO NOTHING
        """), {"source": SOURCE})

    print(f"TESTS rows inserted: {tests_result.rowcount}")
    print(f"PRACTICES rows inserted: {practices_result.rowcount}")


if __name__ == "__main__":
    main()
