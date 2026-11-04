"""Refinements of the generated ``mb-exam`` items (requirement 71 WP6, requirement 70 C2 sections 3-4) and the key builders of the area.

The generated models describe the migrated data exactly; these subclasses register under the same ``ctx``/``item_type`` and replace
them. They accept every migrated shape and add what the runtime writes:

* ``PAPER``           status / ``answer_disclosure`` / style / types as Literals, the CHECKs of ``quiz.paper`` (count 1-20, band, time limit
                      60-36000, resume ordinal > 0), the counters, ``diagnosis_version``, ``version``; GSI1 = my papers, GSI2 = admin status list.
* ``DRAFT``           new: an unsubmitted answer, expires 90 days after its last save.
* ``QUESTION``        learner-safe fields + tag ids/slugs (skills too), ``diagram_*``, ``pool_question_id``.
* ``QUESTION_SECRET`` the answer key, solution and sources (server-only); never in a learner-reachable body.
* ``RESPONSE``        ``grading_method`` incl. ``HUMAN_OVERRIDE``, fractional confidence, ``regrades`` history.
* ``QUIZ_EVIDENCE``   one per tag of an answered question; the band may be absent (practice without a requested band).
* ``RESPONSE_EVENT`` / ``GENERATION_EVENT`` / ``DIAGNOSIS``  enums as Literals; diagnosis lists stay free-form like the jsonb they came from.
"""
from __future__ import annotations

from typing import Any, ClassVar, Literal
from uuid import UUID

from pydantic import Field, StrictFloat, StrictInt, StrictStr, model_validator

from mathbank_rest.models.base import DdbItem, JsonDoc, S3Ref, UtcDateTime
from mathbank_rest.models.ddb.exam import (
    ExamDiagnosis as _GenDiagnosis,
)
from mathbank_rest.models.ddb.exam import (
    ExamGenerationEvent as _GenGenerationEvent,
)
from mathbank_rest.models.ddb.exam import (
    ExamPaper as _GenPaper,
)
from mathbank_rest.models.ddb.exam import (
    ExamQuestion as _GenQuestion,
)
from mathbank_rest.models.ddb.exam import (
    ExamQuestionSecret as _GenSecret,
)
from mathbank_rest.models.ddb.exam import (
    ExamQuizEvidence as _GenEvidence,
)
from mathbank_rest.models.ddb.exam import (
    ExamResponse as _GenResponse,
)
from mathbank_rest.models.ddb.exam import (
    ExamResponseEvent as _GenResponseEvent,
)

Style = Literal["AIME", "HMMT", "PROOF_BASED", "TOPIC_BASED", "SKILL_BASED", "MIXED"]
PaperStatus = Literal["GENERATING", "READY", "IN_PROGRESS", "SUBMITTED", "GRADED", "FAILED"]
Disclosure = Literal["IMMEDIATE", "AFTER_SUBMIT"]
AgentFramework = Literal["OPENAI_DIRECT", "STRANDS_BEDROCK"]
QuestionType = Literal["MCQ", "FREE_TEXT", "PROOF"]
Band = Literal["easy", "medium", "hard", "very_hard"]
GradingMethod = Literal["EXACT_MATCH", "LLM_GRADED", "PENDING_HUMAN_REVIEW", "HUMAN_OVERRIDE"]
EventType = Literal["VIEW", "SELECT_OPTION", "DESELECT_OPTION", "TEXT_CHANGE", "SKIP", "FINAL_SUBMIT"]
Phase = Literal["INTAKE", "TOPIC_RESOLVE", "DIFFICULTY_SIGNAL", "POOL_LOOKUP", "DRAFT_QUESTION", "CRITIC_REVIEW",
                "AGGREGATE_DIVERSITY_CHECK", "AGGREGATE_FIX", "PERSIST", "DONE", "FAILED"]
GenerationStatus = Literal["STARTED", "DONE", "FAILED"]

DRAFT_TTL_DAYS = 90
GENERATION_EVENT_TTL_DAYS = 180


# ---------------------------------------------------------------------------------------------- keys

def paper_sk(quiz_id: Any) -> str:
    return f"QUIZ#{quiz_id}"


def question_sk(quiz_id: Any, question_id: Any) -> str:
    return f"QUIZ#{quiz_id}#P#Q#{question_id}"


def response_sk(quiz_id: Any, question_id: Any) -> str:
    return f"QUIZ#{quiz_id}#P#RESP#{question_id}"


def draft_sk(quiz_id: Any, question_id: Any) -> str:
    return f"QUIZ#{quiz_id}#P#DRAFT#{question_id}"


def secret_sk(quiz_id: Any, question_id: Any) -> str:
    return f"QUIZ#{quiz_id}#S#KEY#{question_id}"


def event_sk(quiz_id: Any, created_at: str, event_id: Any) -> str:
    return f"QUIZ#{quiz_id}#T#EVT#{created_at}#{event_id}"


def generation_sk(quiz_id: Any, ordinal: int) -> str:
    return f"QUIZ#{quiz_id}#T#GEN#{int(ordinal):06d}"


def diagnosis_sk(quiz_id: Any, version: int) -> str:
    return f"QUIZ#{quiz_id}#X#DIAG#{int(version):04d}"


def evidence_sk(kind: str, tag_id: Any, attempted_at: str, response_id: Any) -> str:
    return f"QEVID#{kind}#{tag_id}#{attempted_at}#{response_id}"


def owner_pk(quiz_id: Any) -> str:
    return f"QUIZ#{quiz_id}"


def response_owner_pk(response_id: Any) -> str:
    return f"RESPONSE#{response_id}"


def paper_keys(student_id: Any, quiz_id: Any, created_at: str, status: str) -> dict[str, str]:
    """GSI1: my papers newest first. GSI2: the admin list by status and creation time."""
    return {"GSI1PK": f"STUDENT#{student_id}#PAPERS", "GSI1SK": f"{created_at}#{quiz_id}",
            "GSI2PK": f"PAPER_STATUS#{status}", "GSI2SK": f"{created_at}#{quiz_id}"}


# ---------------------------------------------------------------------------------------------- items

class ExamPaperItem(_GenPaper, ctx="exam", item_type="PAPER"):
    style: Style
    status: PaperStatus
    answer_disclosure: Disclosure
    agent_framework: AgentFramework
    requested_question_count: StrictInt = Field(ge=1, le=20)
    requested_question_types: list[QuestionType] = Field(min_length=1)
    target_skill_slugs: list[StrictStr]
    difficulty_band: Band | None = None
    time_limit_seconds: StrictInt | None = Field(default=None, ge=60, le=36000)
    resume_question_ordinal: StrictInt | None = Field(default=None, ge=1)
    question_count: StrictInt = Field(ge=0)
    answered_count: StrictInt = Field(ge=0)
    correct_count: StrictInt = Field(ge=0)
    diagnosis_version: StrictInt = Field(ge=0)
    version: StrictInt = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _keys(self) -> ExamPaperItem:
        if self.GSI1PK != f"STUDENT#{self.student_id}#PAPERS" or self.GSI2PK != f"PAPER_STATUS#{self.status}":
            raise ValueError("a PAPER carries GSI1 STUDENT#<sid>#PAPERS and GSI2 PAPER_STATUS#<status>")
        return self


class ExamDraft(DdbItem, ctx="exam", item_type="DRAFT"):
    type: Literal["DRAFT"] = "DRAFT"
    PK: str = Field(pattern='^STUDENT#[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    SK: str = Field(pattern='^QUIZ#[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}#P#DRAFT#'
                            '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    OFFLOADED: ClassVar[frozenset[str]] = frozenset({"raw_response"})
    quiz_id: UUID
    question_id: UUID
    student_id: UUID
    raw_response: dict[str, Any] | None = None
    raw_response_ref: S3Ref | None = None
    updated_at: UtcDateTime
    ttl: StrictInt = Field(ge=0)


class ExamQuestionItem(_GenQuestion, ctx="exam", item_type="QUESTION"):
    ordinal: StrictInt = Field(ge=1)
    question_type: QuestionType
    points: StrictInt | StrictFloat = Field(default=1, gt=0)
    difficulty_band: Band | None = None
    skill_ids: list[UUID] | None = None
    skill_slugs: list[StrictStr] | None = None
    diagram_object_key: StrictStr | None = None
    diagram_sha256: StrictStr | None = None
    pool_question_id: UUID | None = None


class ExamQuestionSecretItem(_GenSecret, ctx="exam", item_type="QUESTION_SECRET"):
    solution_created_at: UtcDateTime | None = None
    solution_object_key: StrictStr | None = None
    solution_object_sha256: StrictStr | None = None
    revision_log: list[dict[str, Any]] | None = None
    solution_latex: Any | None = None


class Regrade(JsonDoc):
    """One admin regrade (E10): who changed the verdict, to what and why."""

    is_correct: bool
    actor: StrictStr | None = None
    reason: StrictStr | None = None
    at: UtcDateTime | None = None


class ExamResponseItem(_GenResponse, ctx="exam", item_type="RESPONSE"):
    response_type: QuestionType
    grading_method: GradingMethod
    grading_confidence: StrictInt | StrictFloat = Field(ge=0, le=1)
    time_spent_seconds: StrictInt | None = Field(default=None, ge=0)
    object_key: StrictStr | None = None
    object_sha256: StrictStr | None = None
    ordinal: StrictInt = Field(ge=1)
    regrades: list[Regrade] = Field(default_factory=list)
    version: StrictInt = Field(default=1, ge=1)


class ExamQuizEvidenceItem(_GenEvidence, ctx="exam", item_type="QUIZ_EVIDENCE"):
    difficulty_band: Band | None = None

    @model_validator(mode="after")
    def _one_tag(self) -> ExamQuizEvidenceItem:
        if (self.concept_id is None) == (self.technique_id is None):
            raise ValueError("QUIZ_EVIDENCE carries exactly one of concept_id / technique_id")
        return self


class ExamResponseEventItem(_GenResponseEvent, ctx="exam", item_type="RESPONSE_EVENT"):
    event_type: EventType
    option_key: StrictStr | None = Field(default=None, max_length=10)
    ordinal: StrictInt = Field(ge=1)


class ExamGenerationEventItem(_GenGenerationEvent, ctx="exam", item_type="GENERATION_EVENT"):
    phase: Phase
    status: GenerationStatus
    ordinal: StrictInt = Field(ge=1, le=999_999)


class ExamDiagnosisItem(_GenDiagnosis, ctx="exam", item_type="DIAGNOSIS"):
    pacing_notes: list[dict[str, Any]] | None = None
    reasoning_guidance: list[dict[str, Any]] | None = None
    improvement_areas: list[dict[str, Any]] | None = None
    version: StrictInt = Field(default=1, ge=1)
