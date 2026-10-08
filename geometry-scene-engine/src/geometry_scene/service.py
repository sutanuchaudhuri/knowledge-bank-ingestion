from __future__ import annotations

from hashlib import sha256
from importlib.metadata import version as package_version

from .errors import GeometryError, InvalidFrame, VersionConflict
from .parser import parse_input
from .planner import check_references, plan
from .policy import apply_policy
from .renderer import render
from .schemas import Frame, MathState, SceneInput, SceneState, StateDelta, VisualState
from .solver import solve
from .validation import validate


def _build(
    math,
    scene_id,
    version,
    seed,
    mode,
    positions,
    locked,
    entities,
    previous_visual,
    visual_delta,
    history,
    deferred=(),
    delta=None,
    minimum_angle=None,
):
    check_references(math)
    try:
        points, diagnostics = solve(
            math, positions, locked, seed, previous_visual.view_box, minimum_angle
        )
    except GeometryError as exc:
        exc.details.update(
            {
                "stage": "solver",
                "math_state": math.model_dump(mode="json"),
                "input_positions": positions,
                "locked_points": sorted(locked),
                "seed": seed,
                "rendering_mode": str(mode),
                "minimum_angle_degrees": minimum_angle,
                "previous_visual_state": previous_visual.model_dump(mode="json"),
                "applied_delta": delta.model_dump(mode="json") if delta else None,
            }
        )
        raise
    diagnostics["all_positions"] = {name: list(point) for name, point in points.items()}
    diagnostics["minimum_angle_degrees"] = minimum_angle
    diagnostics["tool_versions"] = {
        "schema": "1",
        "engine": "0.1.0",
        "policy": "1",
        **{name: package_version(name) for name in ("numpy", "scipy", "pydantic")},
    }
    try:
        generated = plan(math, points, entities, deferred)
    except GeometryError as exc:
        exc.details.update(
            {
                "stage": "construction_planner",
                "math_state": math.model_dump(mode="json"),
                "solver_diagnostics": diagnostics,
                "previous_entities": {
                    key: value.model_dump(mode="json") for key, value in entities.items()
                },
                "deferred_relations": list(deferred),
                "applied_delta": delta.model_dump(mode="json") if delta else None,
            }
        )
        raise
    for entity in generated.values():
        if any(ref not in points for ref in entity.refs):
            raise GeometryError(f"invalid entity reference: {entity.id}")
    scene = SceneState(
        scene_id=scene_id,
        version=version,
        seed=seed,
        rendering_mode=mode,
        entities=generated,
        constraints=tuple(r.id for r in math.relations),
        construction_history=history,
        solver_diagnostics=diagnostics,
        deferred_relations=tuple(deferred),
    )
    try:
        visual = apply_policy(math, scene, previous_visual, visual_delta)
    except GeometryError as exc:
        exc.details.update(
            {
                "stage": "visual_policy",
                "math_state": math.model_dump(mode="json"),
                "scene_state": scene.model_dump(mode="json"),
                "previous_visual_state": previous_visual.model_dump(mode="json"),
                "render_policy": visual_delta.model_dump(mode="json"),
                "applied_delta": delta.model_dump(mode="json") if delta else None,
            }
        )
        raise
    try:
        svg = render(scene, visual)
    except (KeyError, ZeroDivisionError, TypeError, ValueError) as exc:
        raise GeometryError(
            f"invalid render geometry: {type(exc).__name__}",
            {
                "stage": "renderer",
                "math_state": math.model_dump(mode="json"),
                "scene_state": scene.model_dump(mode="json"),
                "visual_state": visual.model_dump(mode="json"),
                "applied_delta": delta.model_dump(mode="json") if delta else None,
            },
        ) from exc
    report = validate(math, scene, visual, svg)
    frame = Frame(
        math_state=math,
        scene_state=scene,
        visual_state=visual,
        svg=svg,
        validation=report,
        applied_delta=delta,
        linked_solution_step_id=delta.linked_solution_step_id if delta else None,
    )
    if not report.valid:
        raise InvalidFrame("; ".join(report.errors), frame)
    return frame


def create_scene(request: SceneInput) -> Frame:
    request = parse_input(request.model_copy(deep=True))
    check_references(
        MathState(
            objects=request.objects,
            relations=request.relations,
            version=0,
            problem_text=request.problem_text,
            context=request.context,
        )
    )
    for name in request.positions:
        if name not in request.objects or request.objects[name].type != "POINT":
            raise GeometryError(f"position must identify a defined point: {name}")
    ids = [e.id for e in request.entities]
    if len(ids) != len(set(ids)):
        raise GeometryError("duplicate scene entity ID")
    identifier = (
        request.scene_id or "scene_" + sha256(request.model_dump_json().encode()).hexdigest()[:24]
    )
    math = MathState(
        objects=request.objects,
        relations=request.relations,
        version=0,
        problem_text=request.problem_text,
        context=request.context,
    )
    return _build(
        math,
        identifier,
        0,
        request.seed,
        request.rendering_mode,
        request.positions,
        set(request.positions),
        {e.id: e for e in request.entities},
        VisualState(version=0, styles={}, view_box=request.view_box),
        request.visual,
        (),
        request.deferred_relations,
        minimum_angle=request.minimum_angle_degrees,
    )


def apply_delta(previous: Frame, delta: StateDelta) -> Frame:
    previous = previous.model_copy(deep=True)
    if previous.version != delta.expected_version:
        raise VersionConflict(
            f"expected version {delta.expected_version}; current {previous.version}"
        )
    if not validate_frame(previous).valid:
        raise GeometryError("previous saved frame is invalid")
    objects = dict(previous.math_state.objects)
    for name, obj in delta.add_objects.items():
        if name in objects and objects[name] != obj:
            raise GeometryError(f"cannot replace semantic object: {name}")
        objects[name] = obj
    relations = {r.id: r for r in previous.math_state.relations}
    for relation in delta.add_relations:
        if relation.id in relations:
            raise GeometryError(f"relation ID already exists: {relation.id}; use change_status")
        relations[relation.id] = relation
    for change in delta.change_status:
        if change.relation_id not in relations:
            raise GeometryError(f"unknown relation: {change.relation_id}")
        if relations[change.relation_id].status == "GIVEN" and change.status != "GIVEN":
            raise GeometryError(f"cannot change a supplied given: {change.relation_id}")
        relations[change.relation_id] = relations[change.relation_id].model_copy(
            update={
                "status": change.status,
                "provenance": change.provenance,
            }
        )
    version = previous.version + 1
    math = previous.math_state.model_copy(
        update={
            "objects": objects,
            "relations": tuple(relations.values()),
            "version": version,
        }
    )
    entities = dict(previous.scene_state.entities)
    for entity in delta.add_entities:
        if entity.id in entities and entities[entity.id] != entity:
            raise GeometryError(f"cannot replace semantic entity: {entity.id}")
        entities[entity.id] = entity
    positions = previous.scene_state.solver_diagnostics["all_positions"]
    if delta.relayout and delta.realization_seed is not None:
        positions = {}
    locked = (
        set() if delta.relayout else {e.refs[0] for e in entities.values() if e.type == "POINT"}
    )
    history = (*previous.scene_state.construction_history, delta.model_dump(mode="json"))
    deferred = set(previous.scene_state.deferred_relations)
    for name in delta.activate_relations:
        if name not in relations:
            raise GeometryError(f"unknown construction relation: {name}")
        deferred.discard(name)
    frame = _build(
        math,
        previous.scene_state.scene_id,
        version,
        previous.scene_state.seed if delta.realization_seed is None else delta.realization_seed,
        previous.scene_state.rendering_mode
        if delta.rendering_mode is None
        else delta.rendering_mode,
        positions,
        locked,
        entities,
        previous.visual_state,
        delta.visual,
        history,
        tuple(sorted(deferred)),
        delta=delta,
        minimum_angle=delta.minimum_angle_degrees
        if delta.minimum_angle_degrees is not None
        else previous.scene_state.solver_diagnostics.get("minimum_angle_degrees"),
    )
    for name in delta.ensure_entities:
        if name not in frame.scene_state.entities:
            raise GeometryError(f"required semantic entity absent: {name}")
    return frame


def validate_frame(frame: Frame):
    if not (frame.math_state.version == frame.scene_state.version == frame.visual_state.version):
        raise GeometryError("state versions do not agree")
    check_references(frame.math_state)
    return validate(frame.math_state, frame.scene_state, frame.visual_state, frame.svg)
