from __future__ import annotations

from typing import Annotated, Literal, Protocol

from geometry_scene.schemas import (
    Finite,
    Frame,
    Identifier,
    Model,
    Relation,
    RelationStatus,
    SceneInput,
    StateDelta,
    VisualDelta,
)
from pydantic import Field, model_validator


class MathematicalVariable(Model):
    name: Identifier
    meaning: str = Field(min_length=1, max_length=200)
    unit: Literal["DEGREES", "LENGTH", "UNITLESS"]


class LayoutAngle(Model):
    """A representative angle for unconstrained points, never an ANGLE_MEASURE relation."""

    name: Identifier
    kind: Literal["ANGLE"] = "ANGLE"
    points: tuple[Identifier, Identifier, Identifier]
    minimum: float = Field(default=35, ge=5, le=175, allow_inf_nan=False)
    maximum: float = Field(default=145, ge=5, le=175, allow_inf_nan=False)
    preference: float = Field(default=73, ge=5, le=175, allow_inf_nan=False)
    spacing: float = Field(default=120, ge=20, le=500, allow_inf_nan=False)

    @model_validator(mode="after")
    def valid_interval(self):
        if not self.minimum <= self.preference <= self.maximum:
            raise ValueError("layout preference must lie inside its interval")
        if len(set(self.points)) != 3:
            raise ValueError("layout angle needs three distinct points")
        return self


class CreateScene(Model):
    op: Literal["CREATE_SCENE"] = "CREATE_SCENE"
    scene: SceneInput
    mathematical_variables: tuple[MathematicalVariable, ...] = Field(default=(), max_length=32)
    layout_variables: tuple[LayoutAngle, ...] = Field(default=(), max_length=8)


class ApplyDelta(Model):
    op: Literal["APPLY_DELTA"] = "APPLY_DELTA"
    delta: StateDelta


class AddProvisionalCurve(Model):
    op: Literal["ADD_PROVISIONAL_CURVE"] = "ADD_PROVISIONAL_CURVE"
    id: Identifier
    through: tuple[Identifier, ...] = Field(min_length=3, max_length=16)
    semantic_type: Literal["PROVISIONAL_CURVE"] = "PROVISIONAL_CURVE"
    category: Literal["CONJECTURED", "VISUAL_SUGGESTION", "LAYOUT_SCAFFOLDING"] = (
        "VISUAL_SUGGESTION"
    )

    @model_validator(mode="after")
    def distinct_points(self):
        if len(set(self.through)) != len(self.through):
            raise ValueError("provisional curve points must be distinct")
        return self


class PromoteCurve(Model):
    op: Literal["PROMOTE_CURVE"] = "PROMOTE_CURVE"
    curve_id: Identifier
    trusted_relation_id: Identifier
    relayout: bool = False


class Present(Model):
    op: Literal["PRESENT"] = "PRESENT"
    visual: VisualDelta


Operation = Annotated[
    CreateScene | ApplyDelta | AddProvisionalCurve | PromoteCurve | Present,
    Field(discriminator="op"),
]


class ConstructionProgram(Model):
    schema_version: Literal["nge-ir-1"] = "nge-ir-1"
    id: Identifier
    steps: tuple[Operation, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def starts_once(self):
        if not isinstance(self.steps[0], CreateScene):
            raise ValueError("program must start with CREATE_SCENE")  # noqa: TRY004
        if any(isinstance(step, CreateScene) for step in self.steps[1:]):
            raise ValueError("cumulative programs cannot reset the scene")
        return self


class CurveState(Model):
    id: Identifier
    through: tuple[Identifier, ...]
    category: Literal["CONJECTURED", "VISUAL_SUGGESTION", "LAYOUT_SCAFFOLDING"]
    semantic_type: Literal["PROVISIONAL_CURVE"] = "PROVISIONAL_CURVE"


class LayoutValue(Model):
    name: Identifier
    points: tuple[Identifier, Identifier, Identifier]
    degrees: Finite
    source: Literal["LAYOUT_ONLY"] = "LAYOUT_ONLY"


class Replacement(Model):
    curve_id: Identifier
    circle_id: Identifier
    trusted_relation_id: Identifier
    from_type: Literal["PROVISIONAL_CURVE"] = "PROVISIONAL_CURVE"
    to_type: Literal["CIRCLE"] = "CIRCLE"


class CompiledFrame(Model):
    step: int = Field(ge=0)
    core: Frame
    curves: tuple[CurveState, ...] = ()
    layout_values: tuple[LayoutValue, ...] = ()
    replacements: tuple[Replacement, ...] = ()
    svg: str
    program_hash: str
    compiler_version: Literal["0.1.0"] = "0.1.0"


class PlanningInput(Model):
    problem_text: str = Field(min_length=1, max_length=20000)
    pedagogical_goal: str = Field(min_length=1, max_length=2000)
    previous_program: ConstructionProgram | None = None
    context: tuple[str, ...] = Field(default=(), max_length=128)


class ProgramPlanner(Protocol):
    def plan(
        self, request: PlanningInput, feedback: tuple[str, ...] = ()
    ) -> ConstructionProgram: ...


class CriticReport(Model):
    accepted: bool
    findings: tuple[str, ...] = Field(default=(), max_length=32)


class VisualCritic(Protocol):
    def review(self, request: PlanningInput, candidate: CompiledFrame) -> CriticReport: ...


class TrustedFacts(Model):
    """Supplied by the host's evidence verifier, never accepted from a planner's output."""

    relations: tuple[Relation, ...] = Field(default=(), max_length=128)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [relation.id for relation in self.relations]
        if len(ids) != len(set(ids)):
            raise ValueError("trusted facts must have unique IDs")
        if any(
            relation.status in {RelationStatus.PROVEN, RelationStatus.DISPROVEN}
            and not relation.provenance.strip()
            for relation in self.relations
        ):
            raise ValueError("trusted proof facts require provenance")
        return self
