from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from hashlib import sha256

from geometry_scene.errors import GeometryError
from geometry_scene.schemas import (
    Frame,
    Relation,
    RelationStatus,
    RelationType,
    SceneInput,
    StateDelta,
    StatusChange,
)
from geometry_scene.service import apply_delta, create_scene

from .models import (
    AddProvisionalCurve,
    ApplyDelta,
    CompiledFrame,
    ConstructionProgram,
    CreateScene,
    CurveState,
    LayoutValue,
    Present,
    PromoteCurve,
    Replacement,
    TrustedFacts,
)
from .rendering import render_curves


class CompileError(ValueError):
    def __init__(self, step: int, message: str, code: str = "INVALID_PROGRAM"):
        super().__init__(f"step {step}: {message}")
        self.step = step
        self.code = code


def program_hash(program: ConstructionProgram) -> str:
    return sha256(
        json.dumps(program.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _authorize(relation: Relation, trusted: dict[str, Relation], step: int) -> None:
    if relation.status in {RelationStatus.PROVEN, RelationStatus.DISPROVEN}:
        evidence = trusted.get(relation.id)
        if evidence != relation:
            raise CompileError(
                step, f"{relation.id}: exact trusted evidence required", "UNTRUSTED_FACT"
            )


def _layout(operation: CreateScene) -> tuple[SceneInput, tuple[LayoutValue, ...]]:
    scene = operation.scene
    positions = dict(scene.positions)
    math_names = {variable.name for variable in operation.mathematical_variables}
    layout_names = [variable.name for variable in operation.layout_variables]
    if len(math_names) != len(operation.mathematical_variables):
        raise CompileError(0, "duplicate mathematical variable")
    if len(set(layout_names)) != len(layout_names) or math_names.intersection(layout_names):
        raise CompileError(0, "layout and mathematical variable namespaces must be disjoint")
    used: set[str] = set()
    values = []
    columns = (
        math.ceil(math.sqrt(len(operation.layout_variables))) if operation.layout_variables else 1
    )
    rows = math.ceil(len(operation.layout_variables) / columns) or 1
    cell_width, cell_height = scene.view_box[2] / columns, scene.view_box[3] / rows
    for index, variable in enumerate(operation.layout_variables):
        if used.intersection(variable.points):
            raise CompileError(0, "overlapping layout angle parameterizations are unsupported")
        for name in variable.points:
            if name not in scene.objects or scene.objects[name].type != "POINT":
                raise CompileError(0, f"layout reference {name} is not a point")
            if name in positions:
                raise CompileError(0, "layout parameter cannot overwrite a supplied position")
        if any(
            set(relation.args).intersection(variable.points)
            and relation.status
            in {
                RelationStatus.GIVEN,
                RelationStatus.PROVEN,
                RelationStatus.ASSUMED_FOR_CONSTRUCTION,
            }
            for relation in scene.relations
        ):
            raise CompileError(
                0, "layout angles are limited to mathematically unconstrained points"
            )
        # Optimize readability over a bounded deterministic set, not a mathematical constraint.
        candidates = [
            variable.minimum + (variable.maximum - variable.minimum) * index / 180
            for index in range(181)
        ] + [variable.preference]
        theta = max(
            candidates,
            key=lambda angle: (
                abs(math.sin(math.radians(angle))) - 0.4 * abs(angle - variable.preference) / 180,
                -abs(angle - variable.preference),
                -angle,
            ),
        )
        a, vertex, b = variable.points
        vx = scene.view_box[0] + cell_width * (index % columns + 0.5)
        vy = scene.view_box[1] + cell_height * (index // columns + 0.5)
        radius = min(variable.spacing, cell_width / 4, cell_height / 4)
        positions.update(
            {
                vertex: (vx, vy),
                a: (vx + radius, vy),
                b: (
                    vx + radius * math.cos(math.radians(theta)),
                    vy + radius * math.sin(math.radians(theta)),
                ),
            }
        )
        used.update(variable.points)
        values.append(LayoutValue(name=variable.name, points=variable.points, degrees=theta))
    return scene.model_copy(update={"positions": positions}), tuple(values)


def compile_program(
    program: ConstructionProgram, trusted_facts: TrustedFacts | None = None
) -> tuple[CompiledFrame, ...]:
    trusted = {relation.id: relation for relation in (trusted_facts or TrustedFacts()).relations}
    digest = program_hash(program)
    frames: list[CompiledFrame] = []
    core: Frame | None = None
    curves: dict[str, CurveState] = {}
    replacements: list[Replacement] = []
    layout_values: tuple[LayoutValue, ...] = ()
    for step, operation in enumerate(program.steps):
        try:
            if isinstance(operation, CreateScene):
                for relation in operation.scene.relations:
                    _authorize(relation, trusted, step)
                scene, layout_values = _layout(operation)
                core = create_scene(scene)
            elif core is None:
                raise CompileError(step, "missing initial scene")
            elif isinstance(operation, ApplyDelta):
                for relation in operation.delta.add_relations:
                    _authorize(relation, trusted, step)
                existing_relations = {
                    relation.id: relation for relation in core.math_state.relations
                }
                for change in operation.delta.change_status:
                    relation = existing_relations.get(change.relation_id)
                    if relation is None:
                        raise CompileError(step, "status change references an absent relation")
                    _authorize(
                        relation.model_copy(
                            update={"status": change.status, "provenance": change.provenance}
                        ),
                        trusted,
                        step,
                    )
                core = apply_delta(core, operation.delta)
                if operation.delta.relayout:
                    layout_values = ()
            elif isinstance(operation, AddProvisionalCurve):
                rendered_ids = {node.get("id") for node in ET.fromstring(core.svg).iter()}
                if (
                    operation.id in curves
                    or operation.id in core.scene_state.entities
                    or operation.id in rendered_ids
                ):
                    raise CompileError(step, "duplicate visual ID")
                if any(replacement.curve_id == operation.id for replacement in replacements):
                    raise CompileError(step, "promoted visual IDs cannot be reused")
                if len(curves) >= 32:
                    raise CompileError(step, "provisional curve limit exceeded")
                for name in operation.through:
                    _visible_point(core, name, step)
                curves[operation.id] = CurveState(
                    id=operation.id,
                    through=operation.through,
                    category=operation.category,
                )
                core = apply_delta(core, StateDelta(expected_version=core.version))
            elif isinstance(operation, PromoteCurve):
                curve = curves.get(operation.curve_id)
                fact = trusted.get(operation.trusted_relation_id)
                if curve is None:
                    raise CompileError(step, "promotion references an absent provisional curve")
                if (
                    fact is None
                    or fact.type != RelationType.CONCYCLIC
                    or fact.status != RelationStatus.PROVEN
                    or len(fact.args) != len(curve.through)
                    or set(fact.args) != set(curve.through)
                ):
                    raise CompileError(
                        step,
                        "circle promotion needs matching trusted concyclicity",
                        "UNTRUSTED_FACT",
                    )
                existing = next(
                    (relation for relation in core.math_state.relations if relation.id == fact.id),
                    None,
                )
                if existing and (existing.type != fact.type or existing.args != fact.args):
                    raise CompileError(step, "proof cannot redefine an existing relation")
                delta = StateDelta(
                    expected_version=core.version,
                    add_relations=() if existing else (fact,),
                    change_status=(
                        StatusChange(
                            relation_id=fact.id, status=fact.status, provenance=fact.provenance
                        ),
                    )
                    if existing
                    else (),
                    relayout=operation.relayout,
                )
                core = apply_delta(core, delta)
                circle_id = f"circle_{fact.id}"
                if circle_id not in core.scene_state.entities:
                    raise CompileError(step, "trusted circle was not realized")
                replacements.append(
                    Replacement(
                        curve_id=curve.id,
                        circle_id=circle_id,
                        trusted_relation_id=fact.id,
                    )
                )
                del curves[curve.id]
                if operation.relayout:
                    layout_values = ()
            elif isinstance(operation, Present):
                core = apply_delta(
                    core,
                    StateDelta(
                        expected_version=core.version,
                        visual=operation.visual,
                    ),
                )
            else:
                raise CompileError(step, "unsupported operation")
            if core is None:
                raise CompileError(step, "no compiled scene")
            for curve in curves.values():
                if curve.id in core.scene_state.entities:
                    raise CompileError(step, "provisional ID collides with constructed geometry")
                for name in curve.through:
                    _visible_point(core, name, step)
            current_curves = tuple(curves[key] for key in sorted(curves))
            frames.append(
                CompiledFrame(
                    step=step,
                    core=core,
                    curves=current_curves,
                    layout_values=layout_values,
                    replacements=tuple(replacements),
                    svg=render_curves(core, current_curves),
                    program_hash=digest,
                )
            )
        except GeometryError as exc:
            raise CompileError(step, str(exc), exc.code) from exc
    return tuple(frames)


def _visible_point(frame: Frame, name: str, step: int) -> None:
    entity = frame.scene_state.entities.get(f"point_{name}")
    style = frame.visual_state.styles.get(f"point_{name}")
    if entity is None or style is None or not style.visible or style.opacity <= 0:
        raise CompileError(step, f"provisional curve cannot reveal absent/hidden point {name}")
