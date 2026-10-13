"""Shared pydantic data contracts for the IntelliTutor ML/RL platform.

Field-for-field mirror of
documentation/copilot-instructions/intellitutor-ml-rl/02_DATA_MODEL_AND_EVENT_CONTRACTS.md.
Shared verbatim (copy, not a package dependency yet — TODO: once mathbank-ml-inference
also needs these, decide whether to extract a tiny `mathbank-ml-contracts` package or keep
two copies in sync manually; duplicating for now to avoid a premature shared-package
decision before either side's shape has stabilized) with mathbank-ml-inference's own
contracts.py.

None of these models carry business-rule validators yet (e.g. "features_json must contain
key X for feature_set_version Y") — each such rule is a `# TODO:` at the exact field it
would constrain. Only type/required-ness is enforced right now.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# requirements/02 §1 — ml.feature_snapshot / ml.content_feature_snapshot
# ---------------------------------------------------------------------------


class FeatureSnapshot(BaseModel):
    """One student's feature vector as of a point in time (requirements/02 §1,
    requirements/01 §6 "student state is temporal")."""

    model_config = ConfigDict(extra="forbid")

    feature_snapshot_id: UUID
    student_id: str
    as_of_time: datetime
    feature_set_version: str
    lookback_days: int = Field(ge=0)
    # TODO (requirements/55 §3): replace `dict` with a typed per-feature-group model once
    # features/mastery_features.py etc. stabilize their output shape. A loose dict for now
    # intentionally avoids over-specifying a schema that will still change.
    features_json: dict
    source_watermark: str
    created_at: datetime


class ContentFeatureSnapshot(BaseModel):
    """Problem/course/route feature vector (requirements/02 §1)."""

    model_config = ConfigDict(extra="forbid")

    entity_type: Literal["PROBLEM", "COURSE", "ROUTE"]
    entity_id: str
    feature_set_version: str
    features_json: dict
    content_hash: str
    created_at: datetime


# ---------------------------------------------------------------------------
# requirements/02 §1 — ml.training_run / ml.model_registry
# ---------------------------------------------------------------------------


class TrainingRun(BaseModel):
    """One dataset-manifest + training execution (requirements/13 §3,
    requirements/55 §7)."""

    model_config = ConfigDict(extra="forbid")

    training_run_id: UUID
    model_family: str
    model_version: str
    feature_set_version: str
    label_version: str
    dataset_query_hash: str
    train_start: datetime
    train_end: datetime
    validation_start: datetime
    validation_end: datetime
    test_start: datetime
    test_end: datetime
    hyperparameters: dict
    metrics_json: dict
    artifact_uri: str
    git_sha: str
    status: Literal["PENDING", "RUNNING", "SUCCEEDED", "FAILED"]
    created_at: datetime


class ModelRegistryEntry(BaseModel):
    """requirements/02 §1, requirements/13 §5 ("MathBank registry owns business
    approval/deployment stage; external registry (e.g. MLflow) may own binaries/metrics")."""

    model_config = ConfigDict(extra="forbid")

    model_key: str
    model_version: str
    model_family: str
    artifact_uri: str
    feature_set_version: str
    label_version: str
    approval_status: Literal["PENDING", "APPROVED", "REJECTED"]
    approved_by: str | None = None
    approved_at: datetime | None = None
    deployment_stage: Literal["NONE", "SHADOW", "CANARY", "PRODUCTION", "RETIRED"]
    metrics_json: dict


# ---------------------------------------------------------------------------
# requirements/02 §1 — ml.prediction / ml.recommendation
# ---------------------------------------------------------------------------


class Explanation(BaseModel):
    """requirements/01 §7 — every prediction/recommendation must carry this. Mandatory,
    not optional, on both Prediction and Recommendation below, so the type system itself
    blocks an "unexplained" recommendation from ever being considered complete."""

    model_config = ConfigDict(extra="forbid")

    reason_codes: list[str]
    supporting_features: dict
    confidence: float = Field(ge=0.0, le=1.0)
    data_sufficiency: Literal["READY", "PARTIAL", "NOT_READY"]
    alternative: str | None = None
    what_data_would_change_this: list[str] = Field(default_factory=list)


class Prediction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prediction_id: UUID
    student_id: str
    model_key: str
    model_version: str
    prediction_type: str
    target_entity_type: str
    target_entity_id: str
    value_json: dict
    feature_snapshot_id: UUID
    explanation: Explanation
    created_at: datetime


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: UUID
    student_id: str
    recommendation_type: str
    entity_type: str
    entity_id: str
    rank: int
    score: float
    reason_codes: list[str]
    explanation: Explanation
    model_key: str
    model_version: str
    feature_snapshot_id: UUID
    status: Literal["PENDING", "SHOWN", "ACCEPTED", "DISMISSED"]
    created_at: datetime


# ---------------------------------------------------------------------------
# requirements/02 §1 — ml.reward_event / ml.tutor_trajectory / ml.tutor_turn
# requirements/11 §4/§5 — reward is multi-component, never collapsed before storage
# ---------------------------------------------------------------------------


class RewardComponents(BaseModel):
    """requirements/11 §5 — "do not keep only scalar reward." Every component is its own
    field so the reward function can be revised without losing the raw signal."""

    model_config = ConfigDict(extra="forbid")

    immediate_correctness: float = 0.0
    transfer: float = 0.0
    time_cost: float = 0.0
    hint_cost: float = 0.0
    engagement: float = 0.0
    policy_violation: float = 0.0
    total: float = 0.0


class RewardEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reward_event_id: UUID
    student_id: str
    trajectory_id: UUID
    turn_id: UUID
    policy_version: str
    action_id: str
    reward_components: RewardComponents
    delayed_reward: bool
    source: Literal["REAL", "SIMULATED"]
    created_at: datetime


class TutorTrajectory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trajectory_id: UUID
    student_id: str | None = None
    student_profile_id: str | None = None
    source: Literal["REAL", "SIMULATED"]
    course_release_id: UUID | None = None
    route_release_id: UUID | None = None
    start_state_json: dict
    policy_version: str
    outcome_json: dict
    created_at: datetime


class TutorTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trajectory_id: UUID
    turn_index: int = Field(ge=0)
    observation_json: dict
    # requirements/11 §6 — action masks: only approved actions are ever presented, so this
    # list is the *already filtered* allowed set, not the full action vocabulary.
    allowed_action_ids: list[str]
    selected_action_id: str
    action_payload: dict
    student_response_summary: str
    evaluation_json: dict
    reward_json: RewardComponents | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# requirements/02 §1 — ml.data_quality_issue (requirements/09, requirements/58)
# ---------------------------------------------------------------------------


class DataQualityIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_id: UUID
    scope_type: Literal["STUDENT", "COURSE", "EXAM", "COHORT", "GLOBAL"]
    scope_id: str
    signal_key: str
    issue_type: Literal["MISSING", "SPARSE", "STALE", "INCONSISTENT", "BIASED", "LEAKAGE_RISK"]
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    details_json: dict
    recommended_metadata: dict
    status: Literal["OPEN", "ACKNOWLEDGED", "RESOLVED"]
    created_at: datetime


class DataReadinessReport(BaseModel):
    """requirements/09 §1 example shape, requirements/58 §3."""

    model_config = ConfigDict(extra="forbid")

    student_id: str | None = None
    use_case: str
    status: Literal["READY", "PARTIAL", "NOT_READY"]
    confidence: float = Field(ge=0.0, le=1.0)
    blocking_signals: list[str] = Field(default_factory=list)
    recommended_data: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# requirements/58 §2 — cohort clustering (temporal assignment, never a permanent label)
# ---------------------------------------------------------------------------


class CohortAssignment(BaseModel):
    """requirements/08 §6 — "store assignments as student_id/cluster_model_version/
    as_of_time/cluster_id/membership_probability. Do not store a permanent human-readable
    identity label on the student profile." There is deliberately no such label field
    here."""

    model_config = ConfigDict(extra="forbid")

    student_id: str
    cluster_model_version: str
    as_of_time: datetime
    cluster_id: str
    membership_probability: float = Field(ge=0.0, le=1.0)


class InterventionEffect(BaseModel):
    """requirements/08 §8 — pre/post matched comparison. `summary_text` must use
    associative, not causal, language ("associated with", never "caused") unless the
    underlying design is a true experiment — TODO: enforce this with a validator once
    summary_text generation is implemented; for now this is a documented convention only."""

    model_config = ConfigDict(extra="forbid")

    intervention_type: str
    entity_id: str
    pre_post_effect: float
    transfer_effect: float
    time_efficiency_effect: float
    confidence_interval: tuple[float, float]
    sample_size: int = Field(ge=0)
    summary_text: str  # TODO: validate no causal verbs ("caused", "made", "forced") appear


# ---------------------------------------------------------------------------
# requirements/55 §3 — dataset manifest (requirements/13 §3)
# ---------------------------------------------------------------------------


class DatasetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: UUID
    feature_set_version: str
    label_version: str
    source_watermarks: dict[str, str]
    student_cohort_query_hash: str
    content_release_filters: dict
    time_window: tuple[datetime, datetime]
    row_counts: dict[str, int]
    exclusion_counts: dict[str, int]
    # TODO (requirements/55 §7): leakage_checks should become a typed list of named check
    # results (pass/fail + detail) once evaluation/leakage_checks.py has real checks to
    # report; a loose dict for now since no check is implemented yet.
    leakage_checks: dict
    schema_hash: str
