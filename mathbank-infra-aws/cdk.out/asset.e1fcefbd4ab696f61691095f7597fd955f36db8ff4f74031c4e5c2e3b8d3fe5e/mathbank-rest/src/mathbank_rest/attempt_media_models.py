from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

StepType = Literal[
    "SETUP",
    "OBSERVATION",
    "CONSTRUCTION",
    "THEOREM_SELECTION",
    "THEOREM_APPLICATION",
    "ANGLE_RELATION",
    "LENGTH_RELATION",
    "SIMILARITY_CLAIM",
    "CONGRUENCE_CLAIM",
    "RATIO",
    "ALGEBRA",
    "CASE",
    "INTERMEDIATE_RESULT",
    "CONCLUSION",
    "QUESTION_OR_UNCERTAINTY",
]
AlignmentType = Literal[
    "MATCHES_SOLUTION_STEP",
    "VALID_ALTERNATE_STEP",
    "PARTIAL_STEP",
    "PREREQUISITE_STEP",
    "IRRELEVANT_STEP",
    "UNSUPPORTED_LEAP",
    "UNMATCHED_BUT_PLAUSIBLE",
]
Correctness = Literal["CORRECT", "PARTIALLY_CORRECT", "INCORRECT", "UNJUSTIFIED", "UNCERTAIN"]


class Versioned(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class Region(BaseModel):
    model_config = ConfigDict(extra="forbid")
    region_id: UUID = Field(default_factory=uuid4)
    media_asset_id: UUID
    page_number: int | None = Field(default=None, ge=1, le=10)
    x_norm: float | None = Field(default=None, ge=0, le=1)
    y_norm: float | None = Field(default=None, ge=0, le=1)
    width_norm: float | None = Field(default=None, gt=0, le=1)
    height_norm: float | None = Field(default=None, gt=0, le=1)
    start_ms: int | None = Field(default=None, ge=0, le=120_000)
    end_ms: int | None = Field(default=None, gt=0, le=120_000)
    region_type: Literal[
        "MATH_LINE",
        "PROSE_LINE",
        "DIAGRAM_LABEL",
        "DIAGRAM_MARK",
        "SCRATCH",
        "CANCELLED",
        "TABLE",
        "ARROW_OR_CALLOUT",
        "SPEECH",
        "KEYFRAME",
    ] = "MATH_LINE"
    reading_order: int = Field(default=0, ge=0)
    confidence: float = Field(default=1, ge=0, le=1)

    @model_validator(mode="after")
    def grounded(self):
        spatial = (self.x_norm, self.y_norm, self.width_norm, self.height_norm)
        if self.page_number is not None:
            if (
                any(v is None for v in spatial)
                or self.start_ms is not None
                or self.end_ms is not None
            ):
                raise ValueError("Spatial evidence needs a full page rectangle, not timestamps")
            if (
                self.x_norm + self.width_norm > 1.000001
                or self.y_norm + self.height_norm > 1.000001
            ):
                raise ValueError("Rectangle extends beyond the original page")
        elif self.start_ms is None or self.end_ms is None or self.end_ms <= self.start_ms:
            raise ValueError("Temporal evidence needs an exact increasing timestamp interval")
        elif any(v is not None for v in spatial):
            raise ValueError("Temporal evidence cannot contain a page rectangle")
        return self


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid", revalidate_instances="always")
    step_id: UUID = Field(default_factory=uuid4)
    ordinal: int = Field(ge=1, le=100)
    plain_text: str = Field(default="", max_length=4000)
    latex_text: str = Field(default="", max_length=8000)
    step_type: StepType = "OBSERVATION"
    confidence: float = Field(default=1, ge=0, le=1)
    evidence_ids: list[UUID] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def nonempty(self):
        if not self.plain_text.strip() and not self.latex_text.strip():
            raise ValueError("A step must contain text or LaTeX")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("Duplicate evidence links")
        return self


class Transcript(Versioned):
    steps: list[Step] = Field(max_length=100)
    regions: list[Region] | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def ordered(self):
        if [s.ordinal for s in self.steps] != list(range(1, len(self.steps) + 1)):
            raise ValueError("Step ordinals must follow their array order, starting at 1")
        if len({s.step_id for s in self.steps}) != len(self.steps):
            raise ValueError("Duplicate step IDs")
        return self


class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_id: UUID
    correctness: Correctness
    alignment_type: AlignmentType
    canonical_solution_step_id: str | None = Field(default=None, max_length=200)
    confidence: float = Field(ge=0, le=1)
    why: str = Field(min_length=1, max_length=4000)
    failure_mode: str = Field(default="", max_length=200)
    next_action: str = Field(min_length=1, max_length=1000)
    evidence_ids: list[UUID] = Field(min_length=1, max_length=30)


class Override(Versioned):
    step_id: UUID
    correctness: Correctness
    why: str = Field(min_length=1, max_length=4000)
    next_action: str = Field(min_length=1, max_length=1000)
    alignment_type: AlignmentType = "UNMATCHED_BUT_PLAUSIBLE"
