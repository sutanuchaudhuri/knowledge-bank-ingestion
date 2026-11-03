"""Pure step-runtime logic shared by both learner-store backends (requirement 71 WP5).

Nothing here touches a database: the state machine (``outcome_transition``, ``next_step``), the idempotency request hash, the
guards on an attempt aggregate, the student-facing payload builders (runtime view, evaluation, event feed) and the
domain errors. ``step_runtime`` (the PostgreSQL SQL layer) re-exports all of it, so existing imports keep working, and
``stores/learner/solve.py`` (the DynamoDB backend) imports it directly.

Security rule (spec 17): nothing returned to a student contains canonical ``step_text`` of a step that is not finished; future steps
are reported only as counts.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from mathbank_rest.step_tutor import step_goal

STUDENT_EVALUATION_FIELDS = ("result", "verdict", "feedback", "feedback_redacted")
CURRENT_STEP_KEYS = ("solution_step_id", "solution_part_id", "part_label", "global_step_index", "step_index_in_part",
                     "step_type", "tutor_role", "skill_node_id", "skill_name", "subconcept_node_id", "is_checkpoint")
DONE_STATES = frozenset({"SUCCESS_INDEPENDENT", "SUCCESS_WITH_HELP", "SKIPPED"})
SUCCESS_STATES = frozenset({"SUCCESS_INDEPENDENT", "SUCCESS_WITH_HELP"})
MAX_HELP_LEVEL = 5
HELP_LEVELS = {
    0: "NO_HELP", 1: "DIRECTIONAL_PROMPT", 2: "CONCEPT_REMINDER",
    3: "STRATEGIC_HINT", 4: "NEAR_EXPLICIT_STEP", 5: "FULL_REVEAL",
}
OUTCOMES = frozenset({"SUCCESS", "FAILED", "SKIPPED"})
INTERNAL_ACTORS = frozenset({"TUTOR", "AGENT", "SYSTEM", "ADMIN"})


class RuntimeError_(Exception):
    """Base error carrying a stable machine-readable code for the REST layer."""

    status_code = 400
    code = "RUNTIME_ERROR"


class NotFound(RuntimeError_):
    status_code = 404
    code = "NOT_FOUND"


class StateVersionConflict(RuntimeError_):
    status_code = 409
    code = "STATE_VERSION_CONFLICT"


class InvalidTransition(RuntimeError_):
    status_code = 409
    code = "INVALID_TRANSITION"


class IdempotencyKeyReused(RuntimeError_):
    status_code = 422
    code = "IDEMPOTENCY_KEY_REUSED"


# ---------------------------------------------------------------- state machine

@dataclass(frozen=True)
class StepRef:
    solution_step_id: str
    solution_part_id: str
    global_step_index: int


def student_evaluation(evaluation: dict | None) -> dict | None:
    """Teacher evidence and diagnosis codes stay server-side; the student sees verdict + feedback."""
    if not evaluation:
        return None
    return {k: evaluation[k] for k in STUDENT_EVALUATION_FIELDS if k in evaluation}


def outcome_transition(result: str, help_level_used: int) -> tuple[str, str, bool | None]:
    """Map an evaluated outcome to (new step state, event type, independent_success)."""
    if result not in OUTCOMES:
        raise ValueError(f"unknown outcome {result!r}")
    if result == "SUCCESS":
        if help_level_used == 0:
            return "SUCCESS_INDEPENDENT", "STEP_COMPLETED_INDEPENDENTLY", True
        return "SUCCESS_WITH_HELP", "STEP_COMPLETED_WITH_HELP", False
    if result == "FAILED":
        return "FAILED", "STEP_FAILED", None
    return "SKIPPED", "STEP_SKIPPED", None


def next_step(steps: list[StepRef], states: dict[str, str],
              prerequisites: dict[str, set[str]]) -> StepRef | None:
    """First unfinished step (in solution order) whose hard DEPENDS_ON prerequisites are all done.

    A FAILED step is unfinished, so it stays current until it succeeds or is skipped.
    Returns None when every step is done.
    """
    unfinished = [s for s in steps if states.get(s.solution_step_id) not in DONE_STATES]
    for step in unfinished:
        if all(states.get(p) in DONE_STATES for p in prerequisites.get(step.solution_step_id, ())):
            return step
    return unfinished[0] if unfinished else None


def request_hash(operation: str, body: dict) -> str:
    return hashlib.sha256(json.dumps([operation, body], sort_keys=True, default=str).encode()).hexdigest()


def steps_from_dag(dag: dict) -> tuple[list[StepRef], dict[str, set[str]]]:
    """Ordered steps and the hard DEPENDS_ON prerequisites of a published solution DAG (content store shape)."""
    steps = [StepRef(s["solution_step_id"], s["solution_part_id"], s["global_step_index"]) for s in dag["steps"]]
    prereqs: dict[str, set[str]] = {}
    for d in dag["dependencies"]:
        if d["relationship_type"] == "DEPENDS_ON" and d["review_status"] != "REJECTED":
            prereqs.setdefault(d["to_step_id"], set()).add(d["from_step_id"])
    return steps, prereqs


def check_version(current: int, supplied: int) -> None:
    if current != supplied:
        raise StateVersionConflict(f"state_version {supplied} is stale; current is {current}. Refetch the runtime.")


def require_current_step(status: str, mode: str | None, current_step_id: str | None, step_id: str) -> None:
    if status != "IN_PROGRESS":
        raise InvalidTransition(f"attempt is {status}")
    if mode == "RECOVERY":
        raise InvalidTransition("a recovery detour is running: finish it or leave it to continue this step")
    if current_step_id != step_id:
        raise InvalidTransition("only the current step accepts this action")


def returned_from_detour(returned_to_step_count: int, returned_to_problem_count: int) -> bool:
    """True once per detour: the step was resumed after recovery and the original problem now moves on."""
    return returned_to_step_count > returned_to_problem_count


def attempt_is_correct(states: dict[str, str]) -> bool:
    return bool(states) and all(s in SUCCESS_STATES for s in states.values())


# ---------------------------------------------------------------- payload builders

def build_runtime_view(attempt: dict, dag: dict, states: dict[str, dict], *,
                       step_lookup: Callable[[str], dict | None],
                       diagnosis_for_step: Callable[[str], dict | None],
                       recovery: dict) -> dict:
    """Student-safe runtime view: the current step's metadata, never canonical step text of an unfinished step.

    ``attempt`` is the ``attempt`` block of the response (ids, status, position, state_version, mode, problem_code,
    statement_text); ``states`` maps step id -> {state, help_level_used, attempt_count, last_response_text, last_evaluation};
    ``step_lookup`` finds a step outside the published DAG (withdrawn after the attempt started); ``diagnosis_for_step`` returns
    the student view of the latest diagnosis of a step; ``recovery`` is the recovery summary.
    """
    steps = [StepRef(s["solution_step_id"], s["solution_part_id"], s["global_step_index"]) for s in dag["steps"]]
    by_step = {s["solution_step_id"]: s for s in dag["steps"]}
    current = None
    current_id = attempt["current_solution_step_id"]
    if current_id:
        row = by_step.get(current_id)
        if row is None:  # not part of the published DAG (e.g. withdrawn after the attempt started): no part label
            row = step_lookup(current_id)
        row = {k: row.get(k) for k in CURRENT_STEP_KEYS}
        state = states.get(current_id, {})
        current = {**row, "goal": step_goal(row["step_type"]), "state": state.get("state", "NOT_SEEN"),
                   "help_level_used": state.get("help_level_used", 0),
                   "attempt_count": state.get("attempt_count", 0),
                   "last_response_text": state.get("last_response_text"),
                   "last_evaluation": student_evaluation(state.get("last_evaluation"))}
        current["diagnosis"] = diagnosis_for_step(current_id)
    seen = [
        {"solution_step_id": s.solution_step_id, "global_step_index": s.global_step_index,
         "state": states[s.solution_step_id]["state"],
         "help_level_used": states[s.solution_step_id]["help_level_used"],
         "your_response": states[s.solution_step_id]["last_response_text"]}
        for s in steps if s.solution_step_id in states
    ]
    done = sum(1 for s in steps if states.get(s.solution_step_id, {}).get("state") in DONE_STATES)
    timeline = []
    for s in steps:  # spec 17: future steps are opaque; completed steps reveal the reference text
        state = states.get(s.solution_step_id, {})
        m = by_step.get(s.solution_step_id, {})
        status = state.get("state", "LOCKED")
        entry = {"solution_step_id": s.solution_step_id, "global_step_index": s.global_step_index,
                 "part_label": m.get("part_label"), "step_index_in_part": m.get("step_index_in_part"),
                 "state": status,
                 "help_level_used": state.get("help_level_used", 0),
                 "is_current": s.solution_step_id == current_id}
        if status != "LOCKED":
            entry |= {"step_type": m.get("step_type"), "skill_name": m.get("skill_name"),
                      "your_response": state.get("last_response_text")}
        if status in DONE_STATES:
            entry["reference_text"] = m.get("step_text")
        timeline.append(entry)
    return {
        "attempt": attempt, "current_step": current, "seen_steps": seen, "timeline": timeline,
        "recovery": recovery,
        "progress": {"total_steps": len(steps), "completed_steps": done, "remaining_steps": len(steps) - done},
    }


# Learner event feed (LRN-F01): the stored payload is the teacher's; a student sees only these keys per event type.
EVENT_STUDENT_PAYLOAD_ALLOWLIST: dict[str, tuple[str, ...]] = {
    "ATTEMPT_STARTED": ("problem_id",),
    "PROBLEM_VIEWED": ("resumed",),
    "STEP_RESPONSE_SUBMITTED": ("response",),
    "STEP_COMPLETED_INDEPENDENTLY": ("help_level_used",),
    "STEP_COMPLETED_WITH_HELP": ("help_level_used",),
    "STEP_FAILED": ("help_level_used",),
    "STEP_SKIPPED": ("help_level_used",),
    "HINT_REQUESTED": ("help_level", "help_kind"),
    "HINT_PRESENTED": ("help_level", "help_kind"),
    "RETURNED_TO_ORIGINAL_PROBLEM": ("next_step_id",),
    "ATTEMPT_COMPLETED": ("is_correct", "hint_count"),
    "GAP_HYPOTHESIS_CREATED": ("knowledge_gap_id", "rank", "target_label", "likelihood_label"),
    "GAP_HYPOTHESIS_CONFIRMED": ("knowledge_gap_id", "rank", "target_label", "likelihood_label"),
    "GAP_HYPOTHESIS_REJECTED": ("knowledge_gap_id", "rank", "target_label", "likelihood_label"),
    "GAP_HYPOTHESIS_RESOLVED": ("knowledge_gap_id", "rank", "target_label", "likelihood_label"),
    "RECOVERY_ITEM_EVALUATED": ("result", "tries", "decision"),
}


def student_event_payload(event_type: str, payload: dict | None) -> dict:
    """The learner's view of an event payload: an allow-list per event type, unknown types give ``{}``."""
    payload = payload or {}
    if event_type == "STEP_EVALUATED":
        out = {k: payload[k] for k in ("result",) if k in payload}
        evaluation = student_evaluation(payload.get("evaluation"))
        if evaluation:
            out["evaluation"] = {k: evaluation[k] for k in ("verdict", "feedback", "feedback_redacted") if k in evaluation}
        return out
    return {k: payload[k] for k in EVENT_STUDENT_PAYLOAD_ALLOWLIST.get(event_type, ()) if k in payload}


def public(value: Any) -> Any:
    """JSON-safe copy (UUID / datetime to text) for receipts stored in an idempotency record."""
    return json.loads(json.dumps(value, default=str))
