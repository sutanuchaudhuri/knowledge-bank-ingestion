"""Pydantic request/response contracts for mathbank-ml-inference's REST API
(requirements/56 §2/§3).

Mirrors (does not import) mathbank-ml-training's contracts.py for the shared `Explanation`
shape — see that module's own docstring for why these are two copies for now rather than
one shared package.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Explanation(BaseModel):
    """requirements/01 §7 / requirements/56 §3 — mandatory on every prediction/
    recommendation response. The type system (this field being required, not
    `| None = None`) is what actually enforces "every recommendation must be
    explainable," not just documentation."""

    model_config = ConfigDict(extra="forbid")

    reason_codes: list[str]
    supporting_features: dict
    confidence: float = Field(ge=0.0, le=1.0)
    data_sufficiency: Literal["READY", "PARTIAL", "NOT_READY"]
    alternative: str | None = None
    what_data_would_change_this: list[str] = Field(default_factory=list)
    model_key: str
    model_version: str


class MLUnavailable(BaseModel):
    """Structured placeholder response every not-yet-implemented endpoint returns
    (requirements/56 §2) instead of a bare 500, so a partial frontend integration can
    already render a "coming soon" EmptyState."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["NOT_IMPLEMENTED"] = "NOT_IMPLEMENTED"
    todo_ref: str
    design_doc_ref: str


# ---------------------------------------------------------------------------
# Student-facing (requirements/56 §2, requirements/14 §2/§4)
# ---------------------------------------------------------------------------


class StudentStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: str
    as_of_time: datetime
    mastery_by_domain: dict[str, Literal["EXCELLENT", "STRONG", "DEVELOPING", "SCRATCHY", "WEAK", "UNKNOWN"]]
    misconception_trend: dict[str, list[float]]
    explanation: Explanation


class RecommendationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str
    entity_id: str
    title: str
    rank: int
    estimated_minutes: int | None = None
    explanation: Explanation


class RecommendationsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: str
    recommendations: list[RecommendationItem]


class ExamStrategyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: str
    exam_family: str
    predicted_score: float | None = None
    readiness: float = Field(ge=0.0, le=1.0)
    pacing_notes: list[str]
    explanation: Explanation


class GeneratedExamRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exam_family: str
    target_length: int = Field(gt=0)


class GeneratedExamResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_exam_id: str
    problem_ids: list[str]
    explanation: Explanation


class DataReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: str | None = None
    use_case: str
    status: Literal["READY", "PARTIAL", "NOT_READY"]
    confidence: float = Field(ge=0.0, le=1.0)
    blocking_signals: list[str]
    recommended_data: list[str]


# ---------------------------------------------------------------------------
# Admin-facing (requirements/56 §2, requirements/14 §3/§5/§6/§7)
# ---------------------------------------------------------------------------


class CohortClusterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cluster_model_version: str
    clusters: list[dict]  # TODO: promote to a typed CohortClusterSummary once requirements/58's
                           # cluster_validation gate is implemented — loose for now.


class CourseEffectivenessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_release_id: str
    pre_post_effect: float
    transfer_effect: float
    sample_size: int
    summary_text: str  # TODO: must use associative, not causal, language (requirements/08 §8)


class ModelRegistryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    models: list[dict]  # TODO: promote to contracts.ModelRegistryEntry once the training
                         # project's registry writer is implemented.


class TrainingRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: list[dict]  # TODO: promote to contracts.TrainingRun


class TutorPolicyStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_version: str
    stage: int
    action_vocabulary_version: str
    offline_eval_summary: dict | None = None


class ScoreTutorActionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation: dict
    allowed_action_ids: list[str]


class ScoreTutorActionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scores: dict[str, float]
    explanation: Explanation
