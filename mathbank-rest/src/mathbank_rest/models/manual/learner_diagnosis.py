"""Refinements of the generated ``mb-learner`` diagnosis and recovery items (requirement 71 WP5, requirement 70 C1 sections 3-4).

The generated models describe the migrated data exactly (3 diagnoses, 3 gaps, 19 plans in ``dev``); these subclasses register under
the same ``ctx``/``item_type`` and replace them. They accept every migrated shape and add what the runtime writes:

* ``DIAG``            append-only diagnosis of one step: ``trigger`` / ``recommended_action`` Literals, evidence with the context the
                      diagnoser saw, probes, ``ai_rerank`` (set once, conditionally, by the optional LLM re-rank).
* ``UNIQUE_DIAG_FP``  the fingerprint sentinel ``UNIQUE#diag_fp#<aid>#<step>#<fp>`` in the learner's partition: one diagnosis per identical
                      evidence (the PostgreSQL ``UNIQUE (attempt, step, fingerprint)``).
* ``GAP``             one ranked hypothesis, a versioned status machine (UNRESOLVED -> CONFIRMED/REJECTED, CONFIRMED -> RESOLVED). While
                      ``status`` moves, ``GSI1PK`` moves with it (``GAPSTATUS#<status>``, the admin overview index). ``latest_plan_id`` /
                      ``latest_plan_status`` are the denormalised newest recovery plan of the gap. Hypotheses at subconcept / concept level
                      have no skill, so the ``target_skill_*`` attributes are optional (as in the SQL columns).
* ``PLAN``            a recovery plan with its ``items[]`` embedded (<= 20, edited by one CAS update), ``status`` / ``trigger`` Literals, the
                      parent plan of a branch, the sparse GSI1 key ``PLANSTATUS#<status>``. ``items`` may live in S3 (``items_ref``) only through
                      the engine's 350 KB safety net.
* ``PLAN_OWNER``      pointer ``PLAN#<id>`` / ``OWNER`` (admin routes carry no learner token).
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, get_args
from uuid import UUID

from pydantic import Field, StrictBool, StrictInt, StrictStr, model_validator

from mathbank_rest.models.base import JsonDoc, S3Ref, UtcDateTime
from mathbank_rest.models.ddb.learner import LearnerDiag as _GenDiag
from mathbank_rest.models.ddb.learner import LearnerGap as _GenGap
from mathbank_rest.models.ddb.learner import LearnerPlan as _GenPlan
from mathbank_rest.models.ddb.learner import LearnerPlanOwner as _GenPlanOwner
from mathbank_rest.models.ddb.learner import LearnerUniqueDiagFp as _GenDiagFp

DiagTrigger = Literal["AUTO", "STUDENT_REQUEST", "TUTOR"]
RecommendedAction = Literal["RETRY_WITH_HINT", "DIAGNOSTIC_PROBE", "RECOVERY_DETOUR"]
Likelihood = Literal["likely", "possible", "worth checking"]
FailureLocation = Literal["CONCEPT", "SUBCONCEPT", "SKILL", "TECHNIQUE", "PREREQUISITE", "REPRESENTATION"]
FailureMode = Literal["NOT_RECOGNIZED", "MISUNDERSTOOD", "THEOREM_NOT_RECALLED", "WRONG_THEOREM_SELECTED", "CANNOT_EXECUTE",
                      "PROOF_CONNECTION_MISSING", "DIAGRAM_MISREAD", "ALGEBRA_BREAKDOWN", "CASE_MISSED", "OVERCOMPLICATED", "CARELESS"]
GapStatus = Literal["UNRESOLVED", "CONFIRMED", "REJECTED", "RESOLVED"]
PlanStatus = Literal["ACTIVE", "SUSPENDED", "COMPLETED", "EXHAUSTED", "ABORTED", "SUPERSEDED"]
PlanTrigger = Literal["DIAGNOSIS", "STUDENT_REQUEST", "TUTOR", "BRANCH"]
Stage = Literal["FOUNDATION", "RECOGNITION", "ISOLATED_EXECUTION", "GUIDED_APPLICATION", "TRANSFER", "RETURN_TO_STEP"]
ItemKind = Literal["LEARNING_ITEM", "THEORY", "RETURN"]
ItemStatus = Literal["PENDING", "PRESENTED", "PASSED", "FAILED", "SKIPPED"]
GAP_STATUSES = get_args(GapStatus)
PLAN_STATUSES = get_args(PlanStatus)
Confidence = Annotated[float, Field(ge=0, le=1)]


# ---------------------------------------------------------------------------------------------- keys

def diag_sk(attempt_id: Any, created_at: str, diagnosis_id: Any) -> str:
    return f"SOLVE#{attempt_id}#DIAG#{created_at}#{diagnosis_id}"


def diag_prefix(attempt_id: Any) -> str:
    return f"SOLVE#{attempt_id}#DIAG#"


def diag_fp_sk(attempt_id: Any, step_id: str, fingerprint: str) -> str:
    return f"UNIQUE#diag_fp#{attempt_id}#{step_id}#{fingerprint}"


def gap_sk(gap_id: Any) -> str:
    return f"GAP#{gap_id}"


def gap_keys(status: str, created_at: str, gap_id: Any) -> dict[str, str]:
    return {"GSI1PK": f"GAPSTATUS#{status}", "GSI1SK": f"{created_at}#{gap_id}"}


def plan_sk(plan_id: Any) -> str:
    return f"PLAN#{plan_id}"


def plan_owner_pk(plan_id: Any) -> str:
    return f"PLAN#{plan_id}"


def plan_keys(status: str, created_at: str, plan_id: Any) -> dict[str, str]:
    return {"GSI1PK": f"PLANSTATUS#{status}", "GSI1SK": f"{created_at}#{plan_id}"}


# ---------------------------------------------------------------------------------------------- DIAG

class DiagEvidenceCurrent(JsonDoc):
    attempt_count: StrictInt = 0
    failure_location: StrictStr | None = None
    failure_mode: StrictStr | None = None
    help_level: StrictInt = 0
    state: StrictStr
    verdict: StrictStr | None = None


class DiagEvidence(JsonDoc):
    current: DiagEvidenceCurrent
    predecessor_steps: list[StrictStr] = Field(default_factory=list)
    skill_history: dict[str, StrictInt] = Field(default_factory=dict)   # empty when the step has no skill
    subconcept_failures: StrictInt = 0


class DiagProbe(JsonDoc):
    """A short check: a learning item (kind LEARNING_ITEM) or a practice step of another problem (PRACTICE_STEP); codes and metadata only."""

    kind: Literal["LEARNING_ITEM", "PRACTICE_STEP"]
    problem_code: StrictStr | None = None
    learning_item_id: StrictStr | None = None
    transformation_type: StrictStr | None = None
    transformed_form: StrictStr | None = None
    solution_step_id: StrictStr | None = None
    global_step_index: StrictInt | None = None
    step_type: StrictStr | None = None
    skill_name: StrictStr | None = None
    is_checkpoint: StrictBool | None = None


class LearnerDiag(_GenDiag, ctx="learner", item_type="DIAG"):
    trigger: DiagTrigger
    recommended_action: RecommendedAction
    evidence: DiagEvidence | None = None
    probes: list[DiagProbe] | None = None


class LearnerUniqueDiagFp(_GenDiagFp, ctx="learner", item_type="UNIQUE_DIAG_FP"):
    """Fingerprint sentinel: ``diag_sk`` points at the DIAG of the first (and only) diagnosis with this evidence."""


# ---------------------------------------------------------------------------------------------- GAP

class GapEvidence(JsonDoc):
    signals: list[StrictStr] = Field(default_factory=list)


class LearnerGap(_GenGap, ctx="learner", item_type="GAP"):
    rank: StrictInt = Field(ge=1)
    failure_location: FailureLocation
    failure_mode: FailureMode
    confidence: Confidence
    status: GapStatus
    evidence: GapEvidence | None = None
    target_concept_id: StrictStr | None = None
    target_subconcept_id: StrictStr | None = None
    target_skill_id: StrictStr | None = None
    target_skill_node_id: UUID | None = None
    target_label: StrictStr | None = None
    source_step_id: StrictStr | None = None
    latest_plan_status: PlanStatus | None = None
    version: StrictInt = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _status_index(self) -> LearnerGap:
        if self.GSI1PK is not None and self.GSI1PK != f"GAPSTATUS#{self.status}":
            raise ValueError("GSI1PK must follow the status (GAPSTATUS#<status>)")
        return self


# ---------------------------------------------------------------------------------------------- PLAN

class PlanItemResponse(JsonDoc):
    choice_index: StrictInt | None = None
    acknowledged: StrictBool | None = None
    response_text: StrictStr | None = None


class PlanItemResult(JsonDoc):
    result: StrictStr
    verdict: StrictStr
    feedback: StrictStr = ""
    teacher: dict[str, Any] = Field(default_factory=dict)       # grader evidence: never shown to the learner


class PlanItem(JsonDoc):
    recovery_plan_item_id: UUID
    ordinal: StrictInt = Field(ge=1)
    stage: Stage
    item_kind: ItemKind
    learning_item_id: StrictStr | None = None
    worked_step_id: StrictStr | None = None
    is_transfer: StrictBool = False
    required: StrictBool = True
    status: ItemStatus = "PENDING"
    tries: StrictInt = Field(default=0, ge=0)
    independent_success: StrictBool | None = None
    last_response: PlanItemResponse | None = None
    last_result: PlanItemResult | None = None
    added_reason: StrictStr = "PLANNED"
    presented_at: UtcDateTime | None = None
    completed_at: UtcDateTime | None = None
    # copied from the (immutable) learning item when the plan is built; migrated items get them from mb-content on read
    transformation_type: StrictStr | None = None
    transformed_form: StrictStr | None = None
    source_problem_id: UUID | None = None

    @model_validator(mode="after")
    def _kind_matches_reference(self) -> PlanItem:
        if (self.item_kind == "LEARNING_ITEM") != (self.learning_item_id is not None):
            raise ValueError("a plan item has a learning_item_id exactly when it is a LEARNING_ITEM")
        return self


class MasteryPolicy(JsonDoc):
    independent_successes_required: StrictInt = 2
    max_help_level_on_final: StrictInt = 1
    transfer_success_required: StrictBool = True


class PlanMastery(JsonDoc):
    independent_successes: StrictInt
    independent_successes_required: StrictInt
    met: StrictBool
    transfer_passed: StrictBool
    transfer_required: StrictBool


class PlanOutcome(JsonDoc):
    mastery: PlanMastery | None = None


class LearnerPlan(_GenPlan, ctx="learner", item_type="PLAN"):
    status: PlanStatus
    trigger: PlanTrigger
    items: list[PlanItem] | None = None
    items_ref: S3Ref | None = None
    mastery_policy: MasteryPolicy | None = None
    outcome: PlanOutcome | None = None
    parent_recovery_plan_id: UUID | None = None
    target_skill_id: StrictStr | None = None
    target_subconcept_id: StrictStr | None = None
    target_label: StrictStr | None = None
    version: StrictInt = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _items_and_index(self) -> LearnerPlan:
        if self.items is None and self.items_ref is None:
            raise ValueError("a plan has items inline or offloaded")
        if self.GSI1PK is not None and self.GSI1PK != f"PLANSTATUS#{self.status}":
            raise ValueError("GSI1PK must follow the status (PLANSTATUS#<status>)")
        if self.items is not None:
            ordinals = [i.ordinal for i in self.items]
            if len(set(ordinals)) != len(ordinals):
                raise ValueError("plan item ordinals are unique")
        return self


class LearnerPlanOwner(_GenPlanOwner, ctx="learner", item_type="PLAN_OWNER"):
    """``PLAN#<id>`` / ``OWNER``: who owns a plan, for the admin routes that carry no learner token."""
