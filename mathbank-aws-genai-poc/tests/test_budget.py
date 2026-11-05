import pytest

from mathbank_genai_poc.budget import AudioBudget, BudgetExhausted


def test_grant_record_and_exhaust(tmp_path):
    budget = AudioBudget(tmp_path / "usage.json", 100)
    assert budget.grant(120) == 100
    budget.record(75.5, "time_limit")
    assert budget.grant(120) == pytest.approx(24.5)
    budget.record(20, "stopped")
    with pytest.raises(BudgetExhausted):
        budget.grant(120)
    reopened = AudioBudget(tmp_path / "usage.json", 100)
    assert reopened.used() == pytest.approx(95.5)
    assert [s["reason"] for s in reopened._read()["sessions"]] == ["time_limit", "stopped"]


def test_negative_durations_are_not_credited(tmp_path):
    budget = AudioBudget(tmp_path / "usage.json", 50)
    budget.record(-5, "clock")
    assert budget.used() == 0
