"""Refined item models of ``mb-learner`` for route attempts, feedback and agent links (requirement 71 WP5, design C1).

Subclasses of the generated models with the same ``ctx``/``item_type`` keywords, so they replace the generated ones in
``ITEM_MODELS`` (see ``models/overrides.py``). Every refinement still accepts every item the migration wrote
(``mathbank-db/aws/dynamo/specs/learner.py``): ROUTE (+ ``UNIQUE#open_route``), AGENTLINK (+ ``UNIQUE#agent_session``). ``FEEDBACK``,
its sentinel, owner pointer and ``RETRIEVAL_EXCLUSION`` had no live rows when the models were generated, so they are written
here from the migration transform and the design.

Enums are ``Literal`` types validated before every write; the PostgreSQL CHECK constraints become validators
(``learner.pedagogy_feedback``: paired review fields, ``feedback_negative_review_check``).
"""
from __future__ import annotations

from typing import Any, ClassVar, Literal, Self
from uuid import UUID

from pydantic import Field, StrictInt, StrictStr, model_validator

from mathbank_rest.models.base import DdbItem, S3Ref, UtcDateTime
from mathbank_rest.models.ddb.audit import AuditAudit
from mathbank_rest.models.ddb.learner import (
    LearnerAgentlink,
    LearnerRoute,
    LearnerUniqueAgentSession,
    LearnerUniqueOpenRoute,
)

_UUID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_STUDENT_PK = f"^STUDENT#{_UUID}$"

RouteStatus = Literal["IN_PROGRESS", "FINISHED", "ABANDONED"]
FeedbackStatus = Literal["PENDING", "RESOLVED", "DISMISSED"]
RetrievalVerdict = Literal["UNCLASSIFIED", "IRRELEVANT", "RELEVANT"]
ErrorKind = Literal["UNCLASSIFIED", "METADATA", "RETRIEVAL", "INSUFFICIENT_EVIDENCE"]
AgentSurface = Literal["HOME_CHAT", "SOLVE_WORKSPACE", "OTHER"]
WITHDRAWN_NOTE = "withdrawn by learner"


# ------------------------------------------------------------------------------------------------ ROUTE

class RouteItem(LearnerRoute, ctx="learner", item_type="ROUTE"):
    """``learner.route_attempt``: a cursor through a published route release (CHECK ``current_step > 0``, ``version > 0``)."""

    status: Literal["IN_PROGRESS", "FINISHED", "ABANDONED"]
    current_step: StrictInt = Field(ge=1)
    tutor_explained_steps: list[StrictInt]
    version: StrictInt = Field(ge=1)
    finished_at: UtcDateTime | None = None

    @model_validator(mode="after")
    def _finished_pairs_with_finished_at(self) -> Self:
        if (self.status == "FINISHED") != (self.finished_at is not None):
            raise ValueError("finished_at is set exactly when status is FINISHED")
        return self


class UniqueOpenRoute(LearnerUniqueOpenRoute, ctx="learner", item_type="UNIQUE_OPEN_ROUTE"):
    """At most one IN_PROGRESS attempt per student and release (replaces the missing partial unique index, LRN-F21)."""

    PK: str = Field(pattern=_STUDENT_PK)
    SK: str = Field(pattern=f"^UNIQUE#open_route#{_UUID}$")


# ------------------------------------------------------------------------------------------------ FEEDBACK

class FeedbackItem(DdbItem, ctx="learner", item_type="FEEDBACK"):
    """``learner.pedagogy_feedback``; GSI1 ``FEEDBACK#<status>`` / ``<created_at>#<feedback_id>`` feeds the admin queue."""

    type: Literal["FEEDBACK"] = "FEEDBACK"
    PK: str = Field(pattern=_STUDENT_PK)
    SK: str = Field(pattern=f"^FEEDBACK#{_UUID}$")
    OFFLOADED: ClassVar[frozenset[str]] = frozenset({"audit_snapshot", "review_note"})
    student_id: UUID
    feedback_id: UUID
    problem_id: UUID
    problem_code: StrictStr | None = None
    topic: StrictStr = Field(min_length=1, max_length=200)
    reason: StrictStr = Field(min_length=10, max_length=2000)
    status: Literal["PENDING", "RESOLVED", "DISMISSED"]
    feedback_type: Literal["RETRIEVAL_IRRELEVANT"] = "RETRIEVAL_IRRELEVANT"
    audit_snapshot: dict[str, Any] | None = None
    audit_snapshot_ref: S3Ref | None = None
    review_note: StrictStr | None = Field(default=None, min_length=10, max_length=2000)
    review_note_ref: S3Ref | None = None
    created_at: UtcDateTime
    reviewed_at: UtcDateTime | None = None
    reviewed_by: StrictStr | None = None
    retrieval_verdict: Literal["UNCLASSIFIED", "IRRELEVANT", "RELEVANT"] = "UNCLASSIFIED"
    error_kind: Literal["UNCLASSIFIED", "METADATA", "RETRIEVAL", "INSUFFICIENT_EVIDENCE"] = "UNCLASSIFIED"
    requested_node_id: StrictStr | None = None
    version: StrictInt = Field(ge=1)

    @model_validator(mode="after")
    def _review_pairing(self) -> Self:
        has_note = self.review_note is not None or self.review_note_ref is not None
        if self.status == "PENDING":
            if has_note or self.reviewed_at is not None or self.reviewed_by is not None:
                raise ValueError("a PENDING report has no review fields")
            if self.retrieval_verdict != "UNCLASSIFIED":
                raise ValueError("a retrieval verdict requires a completed review")
        elif not has_note or self.reviewed_at is None:
            raise ValueError("a reviewed report needs review_note and reviewed_at")
        return self


class UniqueFeedback(DdbItem, ctx="learner", item_type="UNIQUE_FEEDBACK"):
    """UNIQUE (student, problem, topic, reason): ``sha256(topic|reason)`` of the trimmed values."""

    type: Literal["UNIQUE_FEEDBACK"] = "UNIQUE_FEEDBACK"
    PK: str = Field(pattern=_STUDENT_PK)
    SK: str = Field(pattern=f"^UNIQUE#feedback#{_UUID}#[0-9a-f]{{64}}$")
    student_id: UUID
    feedback_id: UUID


class FeedbackOwner(DdbItem, ctx="learner", item_type="FEEDBACK_OWNER"):
    """``FEEDBACK#<id>`` / ``OWNER``: resolves the owner of a report for the admin review."""

    type: Literal["FEEDBACK_OWNER"] = "FEEDBACK_OWNER"
    PK: str = Field(pattern=f"^FEEDBACK#{_UUID}$")
    SK: Literal["OWNER"] = "OWNER"
    student_id: UUID


class RetrievalExclusion(DdbItem, ctx="learner", item_type="RETRIEVAL_EXCLUSION"):
    """Problems a reviewer found irrelevant for a taxonomy node; excluded for every learner (RESOLVED + IRRELEVANT)."""

    type: Literal["RETRIEVAL_EXCLUSION"] = "RETRIEVAL_EXCLUSION"
    PK: str = Field(pattern=r"^RETRIEVAL_EXCLUSION#[^#]+$")
    SK: str = Field(pattern=f"^PROBLEM#{_UUID}$")
    requested_node_id: StrictStr
    problem_id: UUID
    problem_code: StrictStr | None = None
    feedback_ids: list[StrictStr]


# ------------------------------------------------------------------------------------------------ AGENT LINKS

class AgentLinkItem(LearnerAgentlink, ctx="learner", item_type="AGENTLINK"):
    """``learner.agent_session_link``; GSI1 ``AGENTLINKS`` / ``<created_at>#<link_id>`` feeds the admin list."""

    surface: Literal["HOME_CHAT", "SOLVE_WORKSPACE", "OTHER"]
    context: dict[str, Any] | None = None


class UniqueAgentSession(LearnerUniqueAgentSession, ctx="learner", item_type="UNIQUE_AGENT_SESSION"):
    """UNIQUE (app, session id) with the owner inside; global partition ``UNIQUE#agent_session#<app>#<session>``."""

    PK: str = Field(pattern=r"^UNIQUE#agent_session#[^#]+#[^#]+$")


# ------------------------------------------------------------------------------------------------ mb-audit

class FeedbackAudit(AuditAudit):
    """Audit record of a staff mutation of a learner entity, written to ``mb-audit`` in the mutation's own transaction.

    Unregistered on purpose (no ``item_type`` keyword): it only widens the generated ``AUDIT`` model, which describes the migrated
    Socratic rows, to the other entity types. Same keys as ``mathbank-db/aws/dynamo/specs/staff.py::audit``."""

    PK: str = Field(pattern=f"^ENTITY#[A-Z_]+#{_UUID}$")
    after_state: Any | None = None
    migrated_from: StrictStr | None = None
    source_table: StrictStr | None = None
