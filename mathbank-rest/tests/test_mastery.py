"""Unit tests for mastery scoring — no DB needed (see mastery.py docstring)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from mathbank_rest.mastery import (
    compute_mastery_score,
    correctness_weight,
    difficulty_weight,
    normalized_difficulty,
    recency_weight,
)


def test_normalized_difficulty_keywords() -> None:
    assert normalized_difficulty("AIME D3 / Entry (Q1-5)") == 0.15
    assert normalized_difficulty("Hard") == 0.85
    assert normalized_difficulty(None) == 0.5
    assert normalized_difficulty("unrecognized label") == 0.5


def test_correctness_weight() -> None:
    assert correctness_weight(True) == 1.0
    assert correctness_weight(False) == 0.0


def test_recency_weight_decays_with_age() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    fresh = recency_weight(now, now=now)
    old = recency_weight(now - timedelta(days=90), now=now)
    assert fresh == 1.0
    assert 0.0 < old < fresh


def test_difficulty_weight_range() -> None:
    assert difficulty_weight(None) == 1.25
    assert difficulty_weight("Entry") < difficulty_weight("Hard")


def test_compute_mastery_score_empty_is_zero() -> None:
    assert compute_mastery_score([]) == 0.0


def test_compute_mastery_score_all_correct_is_high() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    attempts = [
        {"is_correct": True, "attempted_at": now, "difficulty_band": "Medium"}
        for _ in range(5)
    ]
    score = compute_mastery_score(attempts, now=now)
    assert score == 1.0


def test_compute_mastery_score_mixed_is_between_zero_and_one() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    attempts = [
        {"is_correct": True, "attempted_at": now, "difficulty_band": "Hard"},
        {"is_correct": False, "attempted_at": now, "difficulty_band": "Hard"},
    ]
    score = compute_mastery_score(attempts, now=now)
    assert 0.0 < score < 1.0


def test_compute_mastery_score_recent_attempts_dominate() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    attempts = [
        {"is_correct": False, "attempted_at": now - timedelta(days=200), "difficulty_band": "Medium"},
        {"is_correct": True, "attempted_at": now, "difficulty_band": "Medium"},
    ]
    score = compute_mastery_score(attempts, now=now)
    assert score > 0.8  # recent correct attempt should dominate the old incorrect one
