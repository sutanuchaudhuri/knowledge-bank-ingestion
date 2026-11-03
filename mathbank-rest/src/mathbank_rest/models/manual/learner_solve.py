"""Refinements of the generated ``mb-learner`` solve-runtime items (requirement 71 WP5, requirement 70 C1 sections 3-4).

The generated models describe the migrated data exactly (and only what the 8 dev sessions showed); these subclasses register
under the same ``ctx``/``item_type`` and replace them. They accept every migrated shape and add what the runtime writes:

* ``SOLVE``      status / mode as ``Literal`` (``DIAGNOSING`` is gone, ``ABANDONED`` added: TUT-S03/S04), nullable position once the
                 attempt ended, ``submitted_at`` / ``completed_at`` / ``outcome_attempt_id``, ``plan_ids``, the ``hint_requested_count``
                 counter, and ``state_version`` (= the item's ``version``: one counter, TUT-S01). While IN_PROGRESS the item is in the
                 sparse open-solve index ``GSI1 OPEN_SOLVE#<0..3> / <last_activity_at>#<aid>`` (abandon-stale job); GSI2 lists a learner's solves.
* ``STEPSTATE``  ``state`` Literal, ``help_level_used`` 0-5, ``attempt_count >= 0``, ``independent_success => help_level_used = 0``
                 (the PostgreSQL CHECKs), free-form ``last_evaluation`` (the evaluator's evidence, written as given), and the GSI2 skill
                 history key ``STUDENT#<sid>#SKILL#<skill> / <last_updated_at>#<aid>#<step>`` (diagnosis A14).
* ``EVENT``      ``event_type`` / ``actor_type`` Literals (every type written today), the per-attempt GSI1 key ``SOLVE#<aid>``.
* ``PROBLEM``    the per-learner cursor: ``attempt_seq``, ``open_solve_attempt_id`` (the one-open-session guard), ``outcome_count``.
* ``SOLVE_OWNER`` pointer ``SOLVE#<aid>/OWNER`` (resolve the owner without a JWT).
"""
from __future__ import annotations

import hashlib
from typing import Any, Literal, get_args
from uuid import UUID

from pydantic import Field, StrictBool, StrictInt, StrictStr, model_validator

from mathbank_rest.models.base import UtcDateTime
from mathbank_rest.models.ddb.learner import LearnerEvent as _GenEvent
from mathbank_rest.models.ddb.learner import LearnerProblem as _GenProblem
from mathbank_rest.models.ddb.learner import LearnerSolve as _GenSolve
from mathbank_rest.models.ddb.learner import LearnerSolveOwner as _GenSolveOwner
from mathbank_rest.models.ddb.learner import LearnerStepstate as _GenStepstate

SolveStatus = Literal["IN_PROGRESS", "SUBMITTED", "COMPLETED", "ABANDONED"]
SolveMode = Literal["SOLVING", "RECOVERY", "REVIEW", "COMPLETED", "ABANDONED"]
StepState = Literal["NOT_SEEN", "PRESENTED", "ATTEMPTED", "SUCCESS_INDEPENDENT", "SUCCESS_WITH_HELP", "FAILED", "DETOURED",
                    "RETRY_PRESENTED", "SKIPPED"]
ActorType = Literal["STUDENT", "TUTOR", "AGENT", "SYSTEM", "ADMIN"]
EventType = Literal[
    "ATTEMPT_STARTED", "PROBLEM_VIEWED",
    "STEP_PRESENTED", "STEP_RESPONSE_SUBMITTED", "STEP_EVALUATED",
    "STEP_COMPLETED_INDEPENDENTLY", "STEP_COMPLETED_WITH_HELP", "STEP_FAILED", "STEP_SKIPPED",
    "HINT_REQUESTED", "HINT_PRESENTED",
    "GAP_DIAGNOSED", "GAP_HYPOTHESIS_CREATED", "GAP_HYPOTHESIS_CONFIRMED", "GAP_HYPOTHESIS_REJECTED", "GAP_HYPOTHESIS_RESOLVED",
    "RECOVERY_PLAN_CREATED", "RECOVERY_ITEM_PRESENTED", "RECOVERY_ITEM_SUBMITTED", "RECOVERY_ITEM_EVALUATED",
    "RECOVERY_PLAN_COMPLETED", "RECOVERY_PLAN_ABORTED", "RECOVERY_PLAN_BRANCHED", "RECOVERY_PLAN_EXHAUSTED",
    "RETURNED_TO_ORIGINAL_STEP", "RETURNED_TO_ORIGINAL_PROBLEM",
    "ATTEMPT_SUBMITTED", "ATTEMPT_COMPLETED", "ATTEMPT_ABANDONED",
]
EVENT_TYPES = frozenset(get_args(EventType))
OPEN_SOLVE_SHARDS = 4
MAX_HELP_LEVEL = 5


# ---------------------------------------------------------------------------------------------- keys

def solve_sk(attempt_id: Any) -> str:
    return f"SOLVE#{attempt_id}"


def step_sk(attempt_id: Any, step_id: str) -> str:
    return f"SOLVE#{attempt_id}#STEP#{step_id}"


def problem_sk(problem_id: Any) -> str:
    return f"PROBLEM#{problem_id}"


def owner_pk(attempt_id: Any) -> str:
    return f"SOLVE#{attempt_id}"


def event_sk(event_time: str, event_id: str) -> str:
    return f"EVT#{event_time}#{event_id}"


def open_shard(attempt_id: Any) -> int:
    """Same hash as the migration (``specs/learner.py::_shard``), so migrated and new open sessions share the shards."""
    return int(hashlib.sha256(str(attempt_id).encode()).hexdigest(), 16) % OPEN_SOLVE_SHARDS


def open_solve_keys(attempt_id: Any, last_activity_at: str) -> dict[str, str]:
    return {"GSI1PK": f"OPEN_SOLVE#{open_shard(attempt_id)}", "GSI1SK": f"{last_activity_at}#{attempt_id}"}


def solves_keys(student_id: Any, attempt_id: Any, started_at: str) -> dict[str, str]:
    return {"GSI2PK": f"STUDENT#{student_id}#SOLVES", "GSI2SK": f"{started_at}#{attempt_id}"}


def skill_keys(student_id: Any, skill_node_id: str | None, last_updated_at: str, attempt_id: Any, step_id: str) -> dict[str, str]:
    if not skill_node_id:
        return {}
    return {"GSI2PK": f"STUDENT#{student_id}#SKILL#{skill_node_id}", "GSI2SK": f"{last_updated_at}#{attempt_id}#{step_id}"}


# ---------------------------------------------------------------------------------------------- items

class LearnerSolve(_GenSolve, ctx="learner", item_type="SOLVE"):
    status: SolveStatus
    current_mode: SolveMode
    current_solution_part_id: StrictStr | None = None
    current_solution_step_id: StrictStr | None = None
    hint_requested_count: StrictInt = Field(default=0, ge=0)
    attempt_number: StrictInt = Field(ge=1)
    plan_ids: list[UUID] = Field(default_factory=list)
    submitted_at: UtcDateTime | None = None
    completed_at: UtcDateTime | None = None
    outcome_attempt_id: UUID | None = None
    version: StrictInt = Field(default=1, ge=1)

    @property
    def state_version(self) -> int:
        """The client-visible ``state_version`` is the item's ``version`` (one counter, the migration's ``state_version``)."""
        return int(self.version or 1)

    @model_validator(mode="after")
    def _open_index(self) -> LearnerSolve:
        open_ = self.status == "IN_PROGRESS"
        if open_ and not (self.GSI1PK or "").startswith("OPEN_SOLVE#"):
            raise ValueError("an IN_PROGRESS solve carries the OPEN_SOLVE GSI1 key")
        if not open_ and self.GSI1PK is not None:
            raise ValueError("only an IN_PROGRESS solve is in the open-solve index")
        return self


class LearnerSolveOwner(_GenSolveOwner, ctx="learner", item_type="SOLVE_OWNER"):
    """``SOLVE#<aid>`` / ``OWNER``: who owns an attempt, for the admin routes that carry no learner token."""


class LearnerStepstate(_GenStepstate, ctx="learner", item_type="STEPSTATE"):
    state: StepState
    attempt_count: StrictInt = Field(default=0, ge=0)
    help_level_used: StrictInt = Field(default=0, ge=0, le=MAX_HELP_LEVEL)
    skill_node_id: StrictStr | None = None
    subconcept_node_id: StrictStr | None = None
    independent_success: StrictBool | None = None
    last_evaluation: dict[str, Any] | None = None
    returned_to_step_count: StrictInt = Field(default=0, ge=0)
    returned_to_problem_count: StrictInt = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _independent_needs_no_help(self) -> LearnerStepstate:
        if self.independent_success is True and self.help_level_used != 0:
            raise ValueError("independent_success requires help_level_used = 0")
        return self


class LearnerEvent(_GenEvent, ctx="learner", item_type="EVENT"):
    event_type: EventType
    actor_type: ActorType
    solve_attempt_id: UUID | None = None
    payload: dict[str, Any] | None = None


class LearnerProblem(_GenProblem, ctx="learner", item_type="PROBLEM"):
    attempt_seq: StrictInt | None = Field(default=None, ge=0)
    outcome_count: StrictInt = Field(default=0, ge=0)
