import copy

import pytest
from pydantic import ValidationError

from mathbank_rest import step_recovery
from mathbank_rest.db.retrieval_audit import power_structure
from mathbank_rest.practice_selection import load_profile, rank_candidates
from mathbank_rest.routers.pedagogy import TopicPracticeRequest


def candidate(code, structure="one", confidence=0.8, difficulty=3):
    return {"canonical_code": code, "node_type": "TECHNIQUE", "confidence": confidence,
            "difficulty": difficulty, "structure_key": structure, "skill_ids": ["S"]}


def test_threshold_is_exact_and_origin_is_excluded():
    rows = rank_candidates([candidate("P0"), candidate("LOW", confidence=0.799), candidate("OK")],
                           profile=load_profile(), limit=10, exclude_codes=["P0"])
    assert [c["canonical_code"] for c in rows] == ["OK"]
    assert rows[0]["signals"]["semantic_similarity"] is None
    assert rows[0]["signals"]["prerequisite_fit"] is None
    assert rows[0]["signals"]["previous_exposure"] is None


def test_diversity_and_exposure_preference_are_deterministic():
    rows = rank_candidates([candidate("A"), candidate("B"), candidate("C", "different")],
                           profile=load_profile(), limit=3, exposed_codes=["A"])
    assert [c["canonical_code"] for c in rows] == ["B", "C", "A"]
    assert rows[1]["signals"]["structural_diversity"] == 1
    assert rows[-1]["signals"]["previous_exposure"] == 0


def test_versioned_weights_can_change_fit_and_unknown_profile_fails():
    profile = load_profile()
    rows = [candidate("A_HARD", difficulty=5), candidate("B_EASY", difficulty=1)]
    assert rank_candidates(rows, profile=profile, limit=1, target_difficulty=1)[0]["canonical_code"] == "B_EASY"
    changed = copy.deepcopy(profile)
    changed["weights"]["difficulty_fit"] = 0
    assert rank_candidates(rows, profile=changed, limit=1, target_difficulty=1)[0]["canonical_code"] == "A_HARD"
    with pytest.raises(ValueError):
        load_profile("unknown")
    with pytest.raises(ValidationError):
        TopicPracticeRequest(topic="Power of point", student_id="forged")
    with pytest.raises(ValidationError):
        TopicPracticeRequest(topic="Power of point", target_difficulty=6)


def test_power_structure_does_not_mistake_prime_powers_for_geometry():
    result = power_structure("An equiangular polygon where n is not a power of a prime",
                             [{"solution_step_id": "wrong", "step_text": "Use vector projections and induction."}])
    assert result["status"] == "REVIEW_REQUIRED" and not result["evidence_step_ids"]
    good = power_structure("Two chords of a circle intersect at P",
                           [{"solution_step_id": "right", "step_text": r"PA \cdot PB = PC \cdot PD"}])
    assert good["status"] == "SUPPORTED_SIGNATURE" and good["evidence_step_ids"] == ["right"]
    assert power_structure("Vectors", [{"solution_step_id": "algebra", "step_text": "AB*CD=EF*GH"}])["status"] == "REVIEW_REQUIRED"


def test_recovery_questions_do_not_copy_solution_seed_but_allow_known_givens():
    seed = "Draw the tangent from the external point to the circle and use the product equality."
    assert not step_recovery.safe_recovery_question({"question_text": seed, "answer_or_solution_seed": seed})
    assert step_recovery.safe_recovery_question({"question_text": "What should you try next?", "answer_or_solution_seed": seed})
    assert step_recovery.safe_recovery_question({"question_text": seed, "answer_or_solution_seed": seed, "statement_text": seed})
