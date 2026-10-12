import pytest

from neural_geometry.examples import examples
from neural_geometry.models import CriticReport, PlanningInput
from neural_geometry.planning import PlanningFailure, plan_and_compile


class Planner:
    def __init__(self):
        self.feedback = []

    def plan(self, request, feedback=()):
        self.feedback.append(feedback)
        return examples()["02_provisional_curve"][0]


class Critic:
    def __init__(self, accepts):
        self.accepts = accepts
        self.calls = 0

    def review(self, request, candidate):
        self.calls += 1
        return CriticReport(
            accepted=self.accepts, findings=() if self.accepts else ("Improve focus",)
        )


REQUEST = PlanningInput(problem_text="Four points", pedagogical_goal="Show a provisional guide")


def test_every_cumulative_frame_is_reviewed_before_acceptance():
    planner, critic = Planner(), Critic(True)
    _, frames, attempts = plan_and_compile(REQUEST, planner, critic)
    assert critic.calls == len(frames) == 2
    assert attempts[-1]["status"] == "ACCEPTED"


def test_critic_rejection_revises_with_feedback_and_stops_at_budget():
    planner, critic = Planner(), Critic(False)
    with pytest.raises(PlanningFailure) as failure:
        plan_and_compile(REQUEST, planner, critic, max_attempts=2)
    assert len(planner.feedback) == 2
    assert planner.feedback[1] == ("Improve focus", "Improve focus")
    assert len(failure.value.attempts) == 2
    assert all(attempt["status"] == "CRITIC_REJECTED" for attempt in failure.value.attempts)


def test_compile_failure_never_reaches_critic():
    class UntrustedPlanner:
        def plan(self, request, feedback=()):
            return examples()["03_trusted_circle_promotion"][0]

    critic = Critic(True)
    with pytest.raises(PlanningFailure) as error:
        plan_and_compile(REQUEST, UntrustedPlanner(), critic, max_attempts=1)
    assert critic.calls == 0
    assert error.value.attempts[0]["code"] == "UNTRUSTED_FACT"


def test_provider_failure_is_explicit_not_mocked_success():
    class OfflinePlanner:
        def plan(self, request, feedback=()):
            raise ConnectionError("provider unavailable")

    with pytest.raises(ConnectionError, match="unavailable"):
        plan_and_compile(REQUEST, OfflinePlanner(), Critic(True))


def test_invalid_budget_rejected_before_provider():
    planner = Planner()
    with pytest.raises(ValueError):
        plan_and_compile(REQUEST, planner, Critic(True), max_attempts=0)
    assert not planner.feedback


def test_planner_cannot_replace_accepted_history():
    previous = examples()["01_free_intersection"][0]
    request = REQUEST.model_copy(update={"previous_program": previous})
    critic = Critic(True)
    with pytest.raises(PlanningFailure) as error:
        plan_and_compile(request, Planner(), critic, max_attempts=1)
    assert error.value.attempts[0]["code"] == "HISTORY_CHANGED"
    assert critic.calls == 0
