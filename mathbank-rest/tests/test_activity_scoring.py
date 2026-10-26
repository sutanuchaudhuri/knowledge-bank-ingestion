"""Pure deterministic scorer tests; no database, network or model calls."""
import pytest

from mathbank_rest import activity_scoring as scoring
from mathbank_rest.activity_scoring import AR_OPTIONS, UnsupportedActivity, evaluate, runtime_kind

# Five golden Assertion–Reason cases (SOC-ASMT-02). Mathematical content is standard and
# self-checking, but these are test fixtures: staff approval is still recorded separately.
GOLDEN_AR = [
    ("AR1", "The equation x+y+z=5 has 21 nonnegative integer solutions.",
     "Each solution corresponds to an arrangement of five stars and two bars, and C(7,2)=21.",
     True, True, True),
    ("AR2", "The sum of the interior angles of a triangle is 180 degrees.",
     "Every equilateral triangle has three equal sides.", True, True, False),
    ("AR3", "For every integer n, n^2 - n is even.",
     "Every perfect square is even.", True, False, False),
    ("AR4", "Every prime number is odd.",
     "2 is the only even prime.", False, True, False),
    ("AR5", "The product of two irrational numbers is always irrational.",
     "Every square root of an integer is irrational.", False, False, False),
]


def ar_policy(assertion_true, reason_true, reason_explains):
    case = scoring.ar_case(assertion_true, reason_true, reason_explains)
    return {"correct_index": scoring.AR_CASES.index(case), "explanation": "Golden case.",
            "assertion_reason": {"assertion_true": assertion_true, "reason_true": reason_true,
                                 "reason_explains": reason_explains}}


@pytest.mark.parametrize("case,assertion,reason,a_true,r_true,explains", GOLDEN_AR)
def test_golden_assertion_reason_cases(case, assertion, reason, a_true, r_true, explains):
    assert assertion and reason
    policy = ar_policy(a_true, r_true, explains)
    assert scoring.AR_CASES[policy["correct_index"]] == case
    assert runtime_kind("MCQ", list(AR_OPTIONS), policy) == "ASSERTION_REASON"
    right = evaluate("MCQ", list(AR_OPTIONS), policy, {"selected_indices": [policy["correct_index"]]})
    assert right.verdict == "CORRECT"
    assert right.evidence["assertion_truth_correct"] and right.evidence["reason_truth_correct"]
    for other in range(5):
        if other == policy["correct_index"]:
            continue
        wrong = evaluate("MCQ", list(AR_OPTIONS), policy, {"selected_indices": [other]})
        assert wrong.verdict == "INCORRECT" and wrong.evidence["selected_case"] == scoring.AR_CASES[other]


def test_assertion_reason_keeps_truth_and_entailment_judgments_separate():
    policy = ar_policy(True, True, True)
    evidence = evaluate("MCQ", list(AR_OPTIONS), policy, {"selected_indices": [1]}).evidence
    assert evidence == {"selected_case": "AR2", "expected_case": "AR1", "assertion_truth_correct": True,
                        "reason_truth_correct": True, "entailment_correct": False}
    evidence = evaluate("MCQ", list(AR_OPTIONS), ar_policy(True, False, False), {"selected_indices": [0]}).evidence
    assert evidence["assertion_truth_correct"] and not evidence["reason_truth_correct"]
    assert evidence["entailment_correct"] is None


@pytest.mark.parametrize("policy", [
    {"correct_index": 1, "assertion_reason": {"assertion_true": True, "reason_true": True, "reason_explains": True}},
    {"correct_index": 0, "assertion_reason": {"assertion_true": "yes", "reason_true": True, "reason_explains": True}},
])
def test_inconsistent_assertion_reason_policy_is_unsupported(policy):
    with pytest.raises(UnsupportedActivity):
        runtime_kind("MCQ", list(AR_OPTIONS), policy)
    with pytest.raises(UnsupportedActivity):
        runtime_kind("MCQ", ["A", "B"], ar_policy(True, True, True))


def test_existing_mcq_and_numeric_semantics_are_preserved():
    assert evaluate("MCQ", ["a", "b", "c"], {"correct_index": 2}, {"selected_indices": [2]}).is_correct
    assert evaluate("MCQ", ["a", "b", "c"], {"correct_index": 2}, {"selected_indices": [0]}).is_correct is False
    assert scoring.score_choice_index(["a", "b"], {"correct_index": 1}, 1)
    with pytest.raises(ValueError):
        scoring.score_choice_index(["a", "b"], {"correct_index": 1}, 2)
    assert scoring.score_numeric({"correct_value": 21}, 21.0)
    assert not scoring.score_numeric({"correct_value": 21}, 21.001)
    assert not scoring.score_numeric({}, 21)
    assert evaluate("NUMERIC", [], {"correct_value": 0.5}, {"value": 0.5}).verdict == "CORRECT"


def test_multiselect_requires_exact_set_and_free_form_abstains():
    policy = {"correct_indices": [0, 2]}
    assert evaluate("MULTISELECT", ["a", "b", "c"], policy, {"selected_indices": [2, 0]}).verdict == "CORRECT"
    assert evaluate("MULTISELECT", ["a", "b", "c"], policy, {"selected_indices": [0]}).verdict == "INCORRECT"
    free = evaluate("SHORT_RESPONSE", [], {}, {"text": "Because of symmetry."})
    assert free.verdict == "UNCERTAIN" and free.is_correct is None


@pytest.mark.parametrize("activity_type,options,policy", [
    ("LIVE_POLL", [{"label": "A"}], {"correct_option": "A"}),
    ("MCQ", ["only"], {"correct_index": 0}),
    ("MCQ", ["a", "b"], {"correct_index": 5}),
    ("MCQ", ["a", "b"], {"correct_index": True}),
    ("MULTISELECT", ["a", "b"], {"correct_indices": []}),
    ("NUMERIC", [], {"correct_value": "21"}),
    ("NUMERIC", [], {"correct_value": float("nan")}),
])
def test_unscoreable_activities_are_rejected(activity_type, options, policy):
    with pytest.raises(UnsupportedActivity):
        runtime_kind(activity_type, options, policy)


@pytest.mark.parametrize("response", [
    {}, {"selected_indices": []}, {"selected_indices": [0, 0]}, {"selected_indices": [9]},
    {"selected_indices": [0, 1]}, {"value": 1},
])
def test_malformed_choice_responses_are_rejected(response):
    with pytest.raises(ValueError):
        evaluate("MCQ", ["a", "b"], {"correct_index": 0}, response)
