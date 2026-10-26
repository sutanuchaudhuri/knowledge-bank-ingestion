"""Deterministic scoring for `activity.definition` rows, shared by every runtime.

One evaluator for the micro-course runtime and the Socratic preview (requirement 65
SOC-ASMT-01: no parallel score engine). Kinds map onto the existing activity types:

| activity_type          | policy keys                           | runtime kind        |
|------------------------|---------------------------------------|---------------------|
| MCQ                    | correct_index                         | SINGLE_CHOICE       |
| MCQ + assertion_reason | assertion_true/reason_true/explains   | ASSERTION_REASON    |
| MULTISELECT            | correct_indices                       | MULTI_SELECT        |
| NUMERIC                | correct_value                         | NUMERIC_EXACT       |
| SHORT_RESPONSE         | (none; never auto-graded)             | FREE_FORM_REASONING |

Assertion–Reason is a five-option MCQ whose answer is *derived* from separate truth and
entailment judgments (SOC-ASMT-02), so the same row still works as an ordinary MCQ in the
micro-course runtime. Policies never leave REST; callers expose only `public_options`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["SINGLE_CHOICE", "MULTI_SELECT", "ASSERTION_REASON", "FREE_FORM_REASONING", "NUMERIC_EXACT"]
Verdict = Literal["CORRECT", "INCORRECT", "UNCERTAIN"]

# Exact-match tolerance used by the micro-course runtime since migration 032; kept unchanged.
NUMERIC_EXACT_TOLERANCE = 1e-9

AR_CASES = ("AR1", "AR2", "AR3", "AR4", "AR5")
AR_OPTIONS = (
    "Both A and R are true, and R is the correct explanation of A.",
    "Both A and R are true, but R is not the correct explanation of A.",
    "A is true, but R is false.",
    "A is false, but R is true.",
    "Both A and R are false.",
)


class UnsupportedActivity(ValueError):
    """The activity type or its correctness policy cannot be scored deterministically."""


@dataclass(frozen=True)
class Evaluation:
    verdict: Verdict
    # Private evidence (truth/entailment judgments, selected case). Never sent pre-answer.
    evidence: dict = field(default_factory=dict)

    @property
    def is_correct(self) -> bool | None:
        return None if self.verdict == "UNCERTAIN" else self.verdict == "CORRECT"


def ar_case(assertion_true: bool, reason_true: bool, reason_explains: bool) -> str:
    if assertion_true and reason_true:
        return "AR1" if reason_explains else "AR2"
    if assertion_true:
        return "AR3"
    return "AR4" if reason_true else "AR5"


def _bool(policy: dict, key: str) -> bool:
    value = policy.get(key)
    if not isinstance(value, bool):
        raise UnsupportedActivity(f"assertion_reason.{key} must be a boolean")
    return value


def _index(value: object, size: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < size:
        raise UnsupportedActivity("correct index is outside the available options")
    return value


def _option_texts(options: list) -> list[str]:
    if not isinstance(options, list) or any(not isinstance(option, str) for option in options):
        raise UnsupportedActivity("choice options must be a list of strings")
    return options


def runtime_kind(activity_type: str, options: list, policy: dict) -> Kind:
    """Validate the stored policy and return its runtime kind; raise if unscoreable."""
    policy = policy or {}
    if activity_type == "MCQ":
        texts = _option_texts(options)
        if len(texts) < 2:
            raise UnsupportedActivity("a choice activity needs at least two options")
        correct = _index(policy.get("correct_index"), len(texts))
        ar = policy.get("assertion_reason")
        if ar is None:
            return "SINGLE_CHOICE"
        if not isinstance(ar, dict) or len(texts) != 5:
            raise UnsupportedActivity("Assertion–Reason requires five options and structured judgments")
        expected = ar_case(_bool(ar, "assertion_true"), _bool(ar, "reason_true"), _bool(ar, "reason_explains"))
        if AR_CASES[correct] != expected:
            raise UnsupportedActivity("correct_index disagrees with the Assertion–Reason judgments")
        return "ASSERTION_REASON"
    if activity_type == "MULTISELECT":
        texts = _option_texts(options)
        indices = policy.get("correct_indices")
        if not isinstance(indices, list) or not indices or len(set(map(str, indices))) != len(indices):
            raise UnsupportedActivity("MULTISELECT requires unique correct_indices")
        for index in indices:
            _index(index, len(texts))
        return "MULTI_SELECT"
    if activity_type == "NUMERIC":
        value = policy.get("correct_value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise UnsupportedActivity("NUMERIC requires a finite correct_value")
        return "NUMERIC_EXACT"
    if activity_type == "SHORT_RESPONSE":
        return "FREE_FORM_REASONING"
    raise UnsupportedActivity(f"{activity_type} is not a scoreable activity type")


def score_choice_index(options: list, policy: dict, choice_index: int) -> bool:
    """Micro-course MCQ semantics: one index compared with `correct_index`."""
    if choice_index < 0 or choice_index >= len(options or []):
        raise ValueError("choice_index is outside the available options")
    return choice_index == (policy or {}).get("correct_index")


def score_numeric(policy: dict, value: float) -> bool:
    """Micro-course NUMERIC semantics: exact within NUMERIC_EXACT_TOLERANCE."""
    correct_value = (policy or {}).get("correct_value")
    return correct_value is not None and abs(float(value) - float(correct_value)) < NUMERIC_EXACT_TOLERANCE


def evaluate(activity_type: str, options: list, policy: dict, response: dict) -> Evaluation:
    """Score a `{selected_indices}` / `{value}` / `{text}` response against a validated policy."""
    kind = runtime_kind(activity_type, options, policy)
    if kind == "FREE_FORM_REASONING":
        text = response.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("a written response is required")
        # Rubric assistance (SOC-ASMT-05) is model-backed and not yet available: abstain.
        return Evaluation("UNCERTAIN", {"reason": "FREE_FORM_NOT_AUTO_SCORED"})
    if kind == "NUMERIC_EXACT":
        value = response.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("a finite numeric value is required")
        return Evaluation("CORRECT" if score_numeric(policy, value) else "INCORRECT")
    selected = response.get("selected_indices")
    if not isinstance(selected, list) or not selected or len(set(selected)) != len(selected):
        raise ValueError("select at least one option, each at most once")
    for index in selected:
        _index(index, len(options))
    if kind == "MULTI_SELECT":
        correct = set(policy["correct_indices"]) == set(selected)
        return Evaluation("CORRECT" if correct else "INCORRECT")
    if len(selected) != 1:
        raise ValueError("select exactly one option")
    correct = score_choice_index(options, policy, selected[0])
    if kind == "SINGLE_CHOICE":
        return Evaluation("CORRECT" if correct else "INCORRECT")
    ar = policy["assertion_reason"]
    expected, chosen = AR_CASES[policy["correct_index"]], AR_CASES[selected[0]]
    # Each case encodes (assertion_true, reason_true, reason_explains); compare separately.
    judgments = {case: (case in ("AR1", "AR2", "AR3"), case in ("AR1", "AR2", "AR4"), case == "AR1")
                 for case in AR_CASES}
    mine, key = judgments[chosen], judgments[expected]
    evidence = {
        "selected_case": chosen, "expected_case": expected,
        "assertion_truth_correct": mine[0] == key[0], "reason_truth_correct": mine[1] == key[1],
        # Entailment is only judged when the key has both statements true.
        "entailment_correct": (mine[2] == key[2]) if ar["assertion_true"] and ar["reason_true"] else None,
    }
    return Evaluation("CORRECT" if correct else "INCORRECT", evidence)
