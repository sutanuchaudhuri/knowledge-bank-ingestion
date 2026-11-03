"""Refinements of the generated ``mb-learner`` micro-course items (requirement 71 WP5, requirement 70 C1 sections 3-4).

The generated models describe the migrated data exactly; these subclasses register under the same ``ctx``/``item_type`` and replace
them. They accept every migrated shape and add what the runtime writes:

* ``ENROLL``             ``status`` Literal, ``last_responses`` (the latest response per item, typed), ``response_seq`` (a counter of response
                         writes: a response never changes the client-visible ``state_version``, which is the item's ``version`` and
                         changes only on advance / abandon / reset), the sparse GSI1 key ``MC_RELEASE#<release_id>`` / ``<status>#<started_at>#<eid>``.
* ``ENROLL_OWNER``      pointer ``ENROLL#<eid>`` / ``OWNER`` (admin routes carry no learner token).
* ``UNIQUE_OPEN_ENROLL`` the one-open-enrollment-per-course sentinel in the learner's partition (LRN-S05).
* ``MCEVENT``           ``event_type`` / ``actor_type`` Literals (LRN-S06), the per-release feed key ``MC_RELEASE#<release_id>#EVT``.
* ``IXEVENT``           raw interaction telemetry plus the deterministic ``evaluation_outcome`` / ``error_signature`` (LRN-F19).
* ``MISCSTATE``         running misconception confidence per learner and misconception, ``confidence`` in [0, 1], ``confirmed`` (new type: the
                         migration derived it from evidence rows that never existed in production, LRN-F20).
* ``MISCEVID``          one weighted piece of misconception evidence (append-only), weight in [-1, 1], confidences in [0, 1].
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, get_args
from uuid import UUID

from pydantic import Field, StrictBool, StrictInt, StrictStr, model_validator

from mathbank_rest.models.base import DdbItem, JsonDoc, UtcDateTime
from mathbank_rest.models.ddb.learner import LearnerEnroll as _GenEnroll
from mathbank_rest.models.ddb.learner import LearnerEnrollOwner as _GenEnrollOwner
from mathbank_rest.models.ddb.learner import LearnerIxevent as _GenIxevent
from mathbank_rest.models.ddb.learner import LearnerMcevent as _GenMcevent
from mathbank_rest.models.ddb.learner import LearnerUniqueOpenEnroll as _GenOpenEnroll

EnrollStatus = Literal["IN_PROGRESS", "COMPLETED", "ABANDONED"]
McEventType = Literal["ENROLLED", "STATE_CHANGED", "COMPLETED", "QUIZ_RESPONSE", "ACTIVITY_RESPONSE", "ABANDONED", "RESET"]
McActorType = Literal["STUDENT", "ADMIN", "SYSTEM"]
ResponseKind = Literal["QUIZ_RESPONSE", "ACTIVITY_RESPONSE"]
EvaluationOutcome = Literal["CORRECT", "ERROR"]
EvidenceType = Literal["OBSERVED_ERROR", "DIAGNOSTIC_RESPONSE", "REPEATED_PATTERN", "CORRECTIVE_SUCCESS", "TRANSFER_FAILURE"]
MC_EVENT_TYPES = frozenset(get_args(McEventType))
EVIDENCE_TYPES = frozenset(get_args(EvidenceType))
Confidence = Annotated[float, Field(ge=0, le=1)]
EvidenceWeight = Annotated[float, Field(ge=-1, le=1)]


# ---------------------------------------------------------------------------------------------- keys

def enroll_sk(enrollment_id: Any) -> str:
    return f"ENROLL#{enrollment_id}"


def enroll_owner_pk(enrollment_id: Any) -> str:
    return f"ENROLL#{enrollment_id}"


def open_enroll_sk(micro_course_id: Any) -> str:
    return f"UNIQUE#open_enroll#{micro_course_id}"


def enroll_keys(release_id: Any, status: str, started_at: str, enrollment_id: Any) -> dict[str, str]:
    return {"GSI1PK": f"MC_RELEASE#{release_id}", "GSI1SK": f"{status}#{started_at}#{enrollment_id}"}


def mcevent_sk(enrollment_id: Any, created_at: str, event_id: Any) -> str:
    return f"ENROLL#{enrollment_id}#EVT#{created_at}#{event_id}"


def mcevent_keys(release_id: Any, created_at: str, event_id: Any) -> dict[str, str]:
    return {"GSI1PK": f"MC_RELEASE#{release_id}#EVT", "GSI1SK": f"{created_at}#{event_id}"}


def ixevent_prefix(enrollment_id: Any, instance_id: Any) -> str:
    return f"ENROLL#{enrollment_id}#IX#{instance_id}#"


def ixevent_sk(enrollment_id: Any, instance_id: Any, created_at: str, event_id: Any) -> str:
    return f"{ixevent_prefix(enrollment_id, instance_id)}{created_at}#{event_id}"


def miscstate_sk(misconception_id: Any) -> str:
    return f"MISCSTATE#{misconception_id}"


def miscevid_sk(misconception_id: Any, created_at: str, evidence_id: Any) -> str:
    return f"MISC#{misconception_id}#{created_at}#{evidence_id}"


# ---------------------------------------------------------------------------------------------- ENROLL

class LastResponsePayload(JsonDoc):
    is_correct: StrictBool
    choice_index: StrictInt | None = None
    activity_id: UUID | None = None
    gave_up: StrictBool | None = None
    learning_item_id: StrictStr | None = None
    value: float | None = None


class LastResponse(JsonDoc):
    created_at: UtcDateTime
    event_id: UUID
    kind: ResponseKind
    payload: LastResponsePayload
    state_id: UUID | None = None


class LearnerEnroll(_GenEnroll, ctx="learner", item_type="ENROLL"):
    status: EnrollStatus
    last_responses: dict[str, LastResponse] | None = None
    response_seq: StrictInt | None = Field(default=None, ge=0)
    version: StrictInt = Field(default=1, ge=1)

    @property
    def state_version(self) -> int:
        """The client-visible ``state_version`` is the item's ``version`` (one counter, the migration's ``state_version``)."""
        return int(self.version or 1)

    @model_validator(mode="after")
    def _release_index(self) -> LearnerEnroll:
        if self.GSI1PK is not None and self.GSI1PK != f"MC_RELEASE#{self.release_id}":
            raise ValueError("GSI1PK must be MC_RELEASE#<release_id>")
        if self.GSI1SK is not None and not self.GSI1SK.startswith(f"{self.status}#"):
            raise ValueError("GSI1SK must start with the enrollment status")
        return self


class LearnerEnrollOwner(_GenEnrollOwner, ctx="learner", item_type="ENROLL_OWNER"):
    """``ENROLL#<eid>`` / ``OWNER``: who owns an enrollment, for the admin routes that carry no learner token."""


class LearnerUniqueOpenEnroll(_GenOpenEnroll, ctx="learner", item_type="UNIQUE_OPEN_ENROLL"):
    """``STUDENT#<sid>`` / ``UNIQUE#open_enroll#<course_id>``: exists while the learner has an IN_PROGRESS enrollment in the course."""


# ---------------------------------------------------------------------------------------------- events

class LearnerMcevent(_GenMcevent, ctx="learner", item_type="MCEVENT"):
    event_type: McEventType
    actor_type: McActorType
    state_id: UUID | None = None


class LearnerIxevent(_GenIxevent, ctx="learner", item_type="IXEVENT"):
    SK: str = Field(pattern=r"^ENROLL#(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|NONE)#IX#"
                            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}#[^#]+#"
                            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    enrollment_id: UUID | None = None
    course_state_id: UUID | None = None
    event_type: StrictStr = Field(min_length=1, max_length=100)
    semantic_action: StrictStr = Field(min_length=1, max_length=100)
    control_key: StrictStr | None = Field(default=None, max_length=100)
    object_id: StrictStr | None = Field(default=None, max_length=200)
    action_payload: dict[str, Any] | None = None
    evaluation_outcome: EvaluationOutcome | None = None
    error_signature: StrictStr | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _evaluation(self) -> LearnerIxevent:
        if self.error_signature is not None and self.evaluation_outcome != "ERROR":
            raise ValueError("error_signature requires evaluation_outcome ERROR")
        return self


# ---------------------------------------------------------------------------------------------- misconceptions

class LearnerMiscstate(DdbItem, ctx="learner", item_type="MISCSTATE"):
    type: Literal["MISCSTATE"] = "MISCSTATE"
    PK: str = Field(pattern=r"^STUDENT#[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    SK: str = Field(pattern=r"^MISCSTATE#[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    student_id: UUID
    misconception_id: UUID
    confidence: Confidence
    confirmed: StrictBool
    last_evidence_id: UUID | None = None
    updated_at: UtcDateTime | None = None
    version: StrictInt = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _keys(self) -> LearnerMiscstate:
        if self.SK != miscstate_sk(self.misconception_id):
            raise ValueError("SK must be MISCSTATE#<misconception_id>")
        return self


class LearnerMiscevid(DdbItem, ctx="learner", item_type="MISCEVID"):
    type: Literal["MISCEVID"] = "MISCEVID"
    PK: str = Field(pattern=r"^STUDENT#[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    SK: str = Field(pattern=r"^MISC#[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}#[^#]+#"
                            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    student_id: UUID
    evidence_id: UUID
    misconception_id: UUID
    interaction_event_id: UUID | None = None
    evidence_type: EvidenceType
    evidence_weight: EvidenceWeight
    confidence_before: Confidence | None = None
    confidence_after: Confidence | None = None
    created_at: UtcDateTime

    @model_validator(mode="after")
    def _keys(self) -> LearnerMiscevid:
        if not self.SK.startswith(f"MISC#{self.misconception_id}#"):
            raise ValueError("SK must be MISC#<misconception_id>#<created_at>#<evidence_id>")
        return self
