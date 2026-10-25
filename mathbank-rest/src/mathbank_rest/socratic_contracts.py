"""Strict draft IR; preserves prototype fields without claiming full workflow runtime."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Key = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
NodeType = Literal[
    "START", "DISCOVERY", "QUIZ", "LESSON", "TOPIC", "INTERACTION", "HINT", "FEEDBACK",
    "AI_DECISION", "DETERMINISTIC_GATE", "PREREQUISITE_PROBE", "REMEDIATION", "BRANCH",
    "RETURN", "TRANSFER", "REFLECT", "COMPLETE", "HUMAN_REVIEW",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(StrictModel):
    problem_code: str | None = Field(default=None, min_length=1, max_length=200)
    solution_id: UUID | None = None
    solution_revision: int | None = Field(default=None, ge=1)
    route_release_id: UUID | None = None

    @model_validator(mode="after")
    def explicit_revision(self):
        if self.solution_id and (not self.problem_code or self.solution_revision is None):
            raise ValueError("A selected solution requires a problem and explicit solution revision.")
        if self.solution_revision is not None and not self.solution_id:
            raise ValueError("A revision requires its solution.")
        if self.route_release_id and not self.solution_id:
            raise ValueError("A route requires an explicit solution revision.")
        return self


class Node(StrictModel):
    key: Key
    label: str = Field(min_length=1, max_length=200)
    type: NodeType
    prompt: str = Field(max_length=12000)
    topic: str | None = Field(default=None, max_length=200)
    objective: str | None = Field(default=None, max_length=4000)
    source_claim_ref: str | None = Field(default=None, max_length=200)
    activity_ref: str | None = Field(default=None, max_length=200)
    accessible_alternative: str | None = Field(default=None, max_length=12000)


class Edge(StrictModel):
    from_key: Key
    to_key: Key
    outcome: Literal["ALWAYS", "SUCCESS", "RETRY", "UNCERTAIN"]
    priority: int = Field(strict=True, ge=0, le=10000)
    annotation: str | None = Field(default=None, max_length=4000)


class Program(StrictModel):
    schema_version: Literal["socratic.prototype.v1"] = "socratic.prototype.v1"
    strategy_code: Key
    source: Source
    entry: Key
    nodes: list[Node] = Field(min_length=2, max_length=200)
    edges: list[Edge] = Field(max_length=1000)
    fallback_key: Key
    max_transitions: int = Field(strict=True, ge=1, le=500)

    @model_validator(mode="after")
    def graph_integrity(self):
        keys = {node.key for node in self.nodes}
        if len(keys) != len(self.nodes):
            raise ValueError("Node keys must be unique.")
        if self.entry not in keys or self.fallback_key not in keys:
            raise ValueError("Entry and fallback must identify nodes in this draft.")
        starts = [node.key for node in self.nodes if node.type == "START"]
        if starts != [self.entry]:
            raise ValueError("Exactly one START must be the entry.")
        if not any(node.type == "COMPLETE" for node in self.nodes):
            raise ValueError("A completion node is required.")
        seen = set()
        for edge in self.edges:
            if edge.from_key not in keys or edge.to_key not in keys:
                raise ValueError("Edges cannot reference missing or cross-workflow nodes.")
            guard = (edge.from_key, edge.outcome, edge.priority)
            if guard in seen:
                raise ValueError("Rule outcome/priority is ambiguous at its source.")
            seen.add(guard)
        return self


class CreateWorkflow(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def nonblank(self):
        if not self.title.strip() or not self.domain.strip():
            raise ValueError("Title and domain cannot be blank.")
        return self


class UpdateWorkflow(StrictModel):
    expected_hash: Digest
    program: Program


class ValidateWorkflow(StrictModel):
    expected_hash: Digest


class WorkflowSummary(StrictModel):
    workflow_id: UUID
    title: str
    domain: str
    content_hash: Digest
    revision: int
    updated_at: datetime


class Workflow(WorkflowSummary):
    program: Program
    prototype_only: Literal[True] = True


class WorkflowPage(StrictModel):
    workflows: list[WorkflowSummary]
    has_more: bool


class ResourceSolution(StrictModel):
    solution_id: UUID
    revision: int
    verification_status: str


class ResourceRoute(StrictModel):
    route_release_id: UUID
    solution_id: UUID
    status: Literal["PUBLISHED"]
    approach_name: str


class Resource(StrictModel):
    problem_id: UUID
    canonical_code: str
    statement_text: str
    solutions: list[ResourceSolution]
    routes: list[ResourceRoute]


class ResourcePage(StrictModel):
    resources: list[Resource]
    has_more: bool


class Strategy(StrictModel):
    code: str
    domain: str
    label: str
    status: Literal["DRAFT"]
    phases: list[str]


class Validation(StrictModel):
    valid: bool
    findings: list[str]
    scope: Literal["DRAFT_STRUCTURE_ONLY"] = "DRAFT_STRUCTURE_ONLY"


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def content_digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def initial_program(strategy_code: str) -> Program:
    return Program(
        strategy_code=strategy_code, source=Source(), entry="start", fallback_key="review",
        max_transitions=30,
        nodes=[
            Node(key="start", label="Start", type="START", prompt="Define the learning objective."),
            Node(key="review", label="Human review", type="HUMAN_REVIEW", prompt="Review the draft evidence."),
            Node(key="complete", label="Complete", type="COMPLETE", prompt="Reflect on the learning journey."),
        ],
        edges=[
            Edge(from_key="start", to_key="review", outcome="ALWAYS", priority=0),
            Edge(from_key="review", to_key="complete", outcome="ALWAYS", priority=0),
        ],
    )
