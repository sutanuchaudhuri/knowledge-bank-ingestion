from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")]
Finite = Annotated[float, Field(allow_inf_nan=False, ge=-10000, le=10000)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RelationStatus(StrEnum):
    GIVEN = "GIVEN"
    ASSUMED_FOR_CONSTRUCTION = "ASSUMED_FOR_CONSTRUCTION"
    PROVEN = "PROVEN"
    UNKNOWN = "UNKNOWN"
    TARGET_TO_PROVE = "TARGET_TO_PROVE"
    DISPROVEN = "DISPROVEN"


ESTABLISHED = frozenset(
    {
        RelationStatus.GIVEN,
        RelationStatus.PROVEN,
        RelationStatus.ASSUMED_FOR_CONSTRUCTION,
    }
)


class RenderingMode(StrEnum):
    EXACT_OR_CONSTRAINED = "EXACT_OR_CONSTRAINED"
    SCHEMATIC = "SCHEMATIC"


class RelationType(StrEnum):
    TRIANGLE = "TRIANGLE"
    QUADRILATERAL = "QUADRILATERAL"
    CONCYCLIC = "CONCYCLIC"
    COLLINEAR = "COLLINEAR"
    MIDPOINT = "MIDPOINT"
    CIRCUMCENTER = "CIRCUMCENTER"
    TANGENT = "TANGENT"
    PARALLEL = "PARALLEL"
    PERPENDICULAR = "PERPENDICULAR"
    EQUAL_LENGTH = "EQUAL_LENGTH"
    EQUAL_ANGLE = "EQUAL_ANGLE"
    SIMILAR = "SIMILAR"
    ANGLE_MEASURE = "ANGLE_MEASURE"
    EXTENSION = "EXTENSION"
    ALTITUDE = "ALTITUDE"
    INTERSECTION = "INTERSECTION"


ARITIES = {
    RelationType.TRIANGLE: {3},
    RelationType.QUADRILATERAL: {4},
    RelationType.CONCYCLIC: {3, 4},
    RelationType.COLLINEAR: {3},
    RelationType.MIDPOINT: {3},
    RelationType.CIRCUMCENTER: {4},
    RelationType.TANGENT: {3},
    RelationType.PARALLEL: {4},
    RelationType.PERPENDICULAR: {4},
    RelationType.EQUAL_LENGTH: {4},
    RelationType.EQUAL_ANGLE: {6},
    RelationType.SIMILAR: {6},
    RelationType.ANGLE_MEASURE: {3},
    RelationType.EXTENSION: {3},
    RelationType.ALTITUDE: {4},
    RelationType.INTERSECTION: {5},
}


class MathObject(Model):
    type: Literal["POINT", "CIRCLE"] = "POINT"
    refs: tuple[Identifier, ...] = ()
    radius: Annotated[float, Field(gt=0, le=10000, allow_inf_nan=False)] | None = None

    @model_validator(mode="after")
    def circle_definition(self):
        if self.type == "CIRCLE" and (len(self.refs) != 1 or self.radius is None):
            raise ValueError("a circle needs one center reference and a positive radius")
        if self.type == "POINT" and (self.refs or self.radius is not None):
            raise ValueError("points cannot carry circle parameters")
        return self


class Relation(Model):
    id: Identifier
    type: RelationType
    args: tuple[Identifier, ...]
    status: RelationStatus
    value: Annotated[float, Field(ge=0, le=180, allow_inf_nan=False)] | None = None
    provenance: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def arity(self):
        if len(self.args) not in ARITIES[self.type]:
            raise ValueError(f"{self.type} requires arity {sorted(ARITIES[self.type])}")
        if self.type == RelationType.ANGLE_MEASURE and self.value is None:
            raise ValueError("ANGLE_MEASURE requires degrees in value")
        if self.type != RelationType.ANGLE_MEASURE and self.value is not None:
            raise ValueError("value is only allowed for ANGLE_MEASURE")
        return self


class MathState(Model):
    objects: dict[Identifier, MathObject]
    relations: tuple[Relation, ...]
    version: int = Field(ge=0)
    problem_text: str = Field(max_length=20000)
    context: tuple[dict, ...] = ()


class Entity(Model):
    id: Identifier
    type: Literal[
        "POINT",
        "SEGMENT",
        "LINE",
        "RAY",
        "POLYGON",
        "CIRCLE",
        "ARC",
        "ANGLE_MARK",
        "RIGHT_ANGLE_MARK",
        "EQUAL_LENGTH_MARK",
        "PARALLEL_MARK",
        "CORRESPONDENCE_MARK",
    ]
    refs: tuple[Identifier, ...] = ()
    role: Literal["PRIMARY", "AUXILIARY", "EXTENSION", "CONTACT"] = "PRIMARY"
    relation_id: Identifier | None = None
    x: Finite | None = None
    y: Finite | None = None
    radius: Annotated[float, Field(gt=0, le=10000, allow_inf_nan=False)] | None = None

    @model_validator(mode="after")
    def geometry_parameters(self):
        minimum = {
            "POINT": 1,
            "SEGMENT": 2,
            "LINE": 2,
            "RAY": 2,
            "POLYGON": 3,
            "ANGLE_MARK": 3,
            "RIGHT_ANGLE_MARK": 4,
            "EQUAL_LENGTH_MARK": 4,
            "PARALLEL_MARK": 4,
            "CORRESPONDENCE_MARK": 6,
        }
        if self.type in minimum and len(self.refs) < minimum[self.type]:
            raise ValueError(f"{self.type} requires at least {minimum[self.type]} references")
        if self.type == "POINT" and (len(self.refs) != 1 or self.x is None or self.y is None):
            raise ValueError("POINT requires one reference and x/y")
        if self.type in ("CIRCLE", "ARC") and (
            self.x is None or self.y is None or self.radius is None
        ):
            raise ValueError("CIRCLE/ARC requires center coordinates and radius")
        if self.type == "ANGLE_MARK" and len(self.refs) not in (3, 6):
            raise ValueError("ANGLE_MARK requires one or two triples")
        if (
            self.type in ("RIGHT_ANGLE_MARK", "EQUAL_LENGTH_MARK", "PARALLEL_MARK")
            and len(self.refs) != 4
        ):
            raise ValueError("line-pair marker requires four references")
        if self.type == "CORRESPONDENCE_MARK" and len(self.refs) != 6:
            raise ValueError("CORRESPONDENCE_MARK requires two triples")
        return self


class SceneState(Model):
    scene_id: Identifier
    version: int = Field(ge=0)
    seed: int
    rendering_mode: RenderingMode
    entities: dict[Identifier, Entity]
    constraints: tuple[Identifier, ...]
    construction_history: tuple[dict, ...] = ()
    deferred_relations: tuple[Identifier, ...] = ()
    solver_diagnostics: dict = Field(default_factory=dict)


class Style(Model):
    visible: bool = True
    opacity: float = Field(default=1, ge=0, le=1, allow_inf_nan=False)
    emphasis: Literal["PRIMARY", "BACKGROUND", "HIGHLIGHT", "DIM"] = "PRIMARY"
    line_style: Literal["SOLID", "DASHED"] = "SOLID"
    render_mode: Literal["FULL_CIRCLE", "VISIBLE_ARC", "CLIPPED_CIRCLE"] = "FULL_CIRCLE"
    label: str | None = Field(default=None, max_length=80)
    label_position: tuple[Finite, Finite] | None = None
    arc_angles: tuple[Finite, Finite] = (0, 90)


class Overlay(Model):
    id: Identifier
    targets: tuple[Identifier, ...] = Field(min_length=1, max_length=32)
    caption: str = Field(default="", max_length=200)


class VisualState(Model):
    version: int = Field(ge=0)
    styles: dict[Identifier, Style]
    focus: tuple[Identifier, ...] = ()
    caption: str = Field(default="", max_length=2000)
    view_box: tuple[Finite, Finite, Finite, Finite] = (0, 0, 640, 480)
    overlays: tuple[Overlay, ...] = Field(default=(), max_length=32)

    @model_validator(mode="after")
    def positive_viewport(self):
        if self.view_box[2] <= 0 or self.view_box[3] <= 0:
            raise ValueError("viewport width and height must be positive")
        return self


class VisualDelta(Model):
    show: tuple[Identifier, ...] = ()
    hide: tuple[Identifier, ...] = ()
    highlight: tuple[Identifier, ...] = ()
    dim: tuple[Identifier, ...] = ()
    focus: tuple[Identifier, ...] = ()
    styles: dict[Identifier, Style] = Field(default_factory=dict)
    caption: str | None = Field(default=None, max_length=2000)
    overlays: tuple[Overlay, ...] = Field(default=(), max_length=32)


class StatusChange(Model):
    relation_id: Identifier
    status: RelationStatus
    provenance: str = Field(min_length=1, max_length=2000)


class StateDelta(Model):
    expected_version: int = Field(ge=0)
    instruction_text: str = Field(default="", max_length=2000)
    add_objects: dict[Identifier, MathObject] = Field(default_factory=dict, max_length=64)
    add_relations: tuple[Relation, ...] = Field(default=(), max_length=128)
    change_status: tuple[StatusChange, ...] = ()
    add_entities: tuple[Entity, ...] = Field(default=(), max_length=256)
    ensure_entities: tuple[Identifier, ...] = ()
    activate_relations: tuple[Identifier, ...] = ()
    visual: VisualDelta = Field(default_factory=VisualDelta)
    relayout: bool = False
    linked_solution_step_id: str | None = Field(default=None, max_length=200)
    realization_seed: int | None = Field(default=None, ge=0, le=2147483647)
    rendering_mode: RenderingMode | None = None
    minimum_angle_degrees: float | None = Field(default=None, ge=1, le=60)

    @model_validator(mode="after")
    def realization_requires_relayout(self):
        if (
            self.realization_seed is not None
            or self.rendering_mode is not None
            or self.minimum_angle_degrees is not None
        ) and not self.relayout:
            raise ValueError("realization changes require explicit relayout")
        return self


class SceneInput(Model):
    scene_id: Identifier | None = None
    problem_text: str = Field(default="", max_length=20000)
    context: tuple[dict, ...] = Field(default=(), max_length=128)
    objects: dict[Identifier, MathObject] = Field(default_factory=dict, max_length=64)
    relations: tuple[Relation, ...] = Field(default=(), max_length=128)
    positions: dict[Identifier, tuple[Finite, Finite]] = Field(default_factory=dict)
    entities: tuple[Entity, ...] = Field(default=(), max_length=256)
    deferred_relations: tuple[Identifier, ...] = ()
    visual: VisualDelta = Field(default_factory=VisualDelta)
    rendering_mode: RenderingMode = RenderingMode.EXACT_OR_CONSTRAINED
    seed: int = Field(default=17, ge=0, le=2147483647)
    view_box: tuple[Finite, Finite, Finite, Finite] = (0, 0, 640, 480)
    minimum_angle_degrees: float | None = Field(default=None, ge=1, le=60)


class ValidationRecord(Model):
    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    residuals: dict[str, float] = Field(default_factory=dict)


class Frame(Model):
    math_state: MathState
    scene_state: SceneState
    visual_state: VisualState
    svg: str
    validation: ValidationRecord
    applied_delta: StateDelta | None = None
    linked_solution_step_id: str | None = None

    @property
    def version(self) -> int:
        return self.scene_state.version
