"""Refinements of the outcome, mastery, evidence and analytics items of ``mb-learner`` (requirement 71 WP5, requirement 70 C1).

Same pattern as ``learner_identity``: subclasses of the generated models registered under the same ``(ctx, item_type)``. They add the enums
and CHECK constraints the PostgreSQL schema never enforced (``mastery_score`` in [0, 1], ``correct_count <= attempts_count``,
``steps_succeeded <= steps_evaluated`` ...) and the attributes the design needs but the migration never wrote (``mastery_pending`` on
OUTCOME, ``sum_attempts`` on COHORT). Each constraint holds for every migrated item: the migration normalises ``source`` and writes
the evidence and scores from the same rows the formula reads.
"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator

from mathbank_rest.models.ddb import learner as generated

OutcomeSource = Literal["web", "agent_chat", "import", "step_runtime", "multimodal_approved", "quiz"]
OUTCOME_SOURCES: frozenset[str] = frozenset(OutcomeSource.__args__)
TagKind = Literal["C", "T"]
EvidenceSource = Literal["OUT", "QZ"]
MASTERY_FORMULA_VERSION = 1                      # mastery.py: half-life 45 d, difficulty weight, hint penalty
DAILY_COUNTERS = ("attempts_started", "attempts_completed", "attempts_abandoned", "steps_evaluated", "steps_succeeded",
                  "gaps_diagnosed", "knowledge_gaps_created", "recovery_plans_created", "recovery_plans_completed")


class LearnerOutcome(generated.LearnerOutcome, ctx="learner", item_type="OUTCOME"):
    """Immutable (append-only) record of one graded or ungraded piece of work. ``is_correct`` is null for unassessed multimodal work."""

    source: OutcomeSource
    legacy_source: StrictStr | None = Field(default=None, max_length=200)     # the free-text source of a row whose source was normalised
    is_correct: StrictBool | None = None
    hint_count: StrictInt = Field(ge=0)
    time_spent_seconds: StrictInt | None = Field(default=None, ge=0)
    mastery_pending: StrictBool | None = None            # T7/T12 overflow: MASTERY and MEVID follow in a second transaction
    solve_attempt_id: UUID | None = None


OutcomeItem = LearnerOutcome


class LearnerMevid(generated.LearnerMevid, ctx="learner", item_type="MEVID"):
    """One graded evidence row for one tag (the unit `mastery.compute_mastery_score` consumes)."""

    tag_kind: TagKind
    src_kind: EvidenceSource
    hint_count: StrictInt = Field(ge=0)
    difficulty_band: StrictStr | None = None
    difficulty_weight: StrictFloat = Field(ge=1.0, le=1.5)


MevidItem = LearnerMevid


class LearnerMastery(generated.LearnerMastery, ctx="learner", item_type="MASTERY"):
    """The running score of one concept (``C``) or technique (``T``); rewritten in the same transaction as its evidence."""

    tag_kind: TagKind
    mastery_score: StrictFloat = Field(ge=0.0, le=1.0)
    attempts_count: StrictInt = Field(ge=0)
    correct_count: StrictInt = Field(ge=0)
    formula_version: StrictInt = Field(ge=1)

    @model_validator(mode="after")
    def _consistent(self) -> LearnerMastery:
        if self.correct_count > self.attempts_count:
            raise ValueError("correct_count exceeds attempts_count")
        if self.SK != f"MASTERY#{self.tag_kind}#{self.tag_id}":
            raise ValueError("SK does not match tag_kind/tag_id")
        return self


MasteryItem = LearnerMastery


class LearnerDaily(generated.LearnerDaily, ctx="learner", item_type="DAILY"):
    """Engagement counters of one UTC day, maintained by the ``learner-analytics`` stream consumer (never by request paths)."""

    attempts_started: StrictInt = Field(ge=0)
    attempts_completed: StrictInt = Field(ge=0)
    attempts_abandoned: StrictInt = Field(ge=0)
    steps_evaluated: StrictInt = Field(ge=0)
    steps_succeeded: StrictInt = Field(ge=0)
    gaps_diagnosed: StrictInt = Field(ge=0)
    knowledge_gaps_created: StrictInt = Field(ge=0)
    recovery_plans_created: StrictInt = Field(ge=0)
    recovery_plans_completed: StrictInt = Field(ge=0)

    @model_validator(mode="after")
    def _consistent(self) -> LearnerDaily:
        if self.steps_succeeded > self.steps_evaluated:
            raise ValueError("steps_succeeded exceeds steps_evaluated")
        return self


DailyItem = LearnerDaily


class LearnerCohort(generated.LearnerCohort, ctx="learner", item_type="COHORT"):
    """Per-concept aggregate for the admin weak-concepts view (no PII); maintained by the ``mastery-cohort`` consumer."""

    n_students: StrictInt = Field(ge=0)
    sum_score: StrictFloat = Field(ge=0.0)
    sum_attempts: StrictInt | None = Field(default=None, ge=0)


CohortItem = LearnerCohort
