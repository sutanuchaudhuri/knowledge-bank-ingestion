from __future__ import annotations

import numpy as np

from .constraints import circumcenter
from .errors import GeometryError
from .schemas import ESTABLISHED, Entity, RelationType


def check_references(math_state):
    objects = math_state.objects
    if len(objects) > 64 or len(math_state.relations) > 128:
        raise GeometryError("scene limit exceeded: 64 objects / 128 relations")
    ids = [r.id for r in math_state.relations]
    if len(ids) != len(set(ids)):
        raise GeometryError("duplicate relation ID")
    for name, obj in objects.items():
        if any(ref not in objects or objects[ref].type != "POINT" for ref in obj.refs):
            raise GeometryError(f"invalid center reference for {name}")
    for relation in math_state.relations:
        for index, arg in enumerate(relation.args):
            expected = "CIRCLE" if relation.type == RelationType.TANGENT and index == 2 else "POINT"
            if arg not in objects or objects[arg].type != expected:
                raise GeometryError(f"{relation.id}: {arg} must refer to {expected}")


def plan(math_state, points, previous, deferred=()):
    entities = dict(previous)

    def add(entity):
        existing = entities.get(entity.id)
        if existing and (existing.type != entity.type or existing.refs != entity.refs):
            raise GeometryError(f"semantic ID collision: {entity.id}")
        entities[entity.id] = entity

    def segment(a, b, role="PRIMARY"):
        add(Entity(id=f"segment_{a}{b}", type="SEGMENT", refs=(a, b), role=role))

    deferred_points = {
        r.args[0]
        for r in math_state.relations
        if r.id in deferred and r.type in {RelationType.CIRCUMCENTER, RelationType.MIDPOINT}
    }
    for name, position in points.items():
        if name not in deferred_points:
            add(
                Entity(id=f"point_{name}", type="POINT", refs=(name,), x=position[0], y=position[1])
            )
    for name, obj in math_state.objects.items():
        if obj.type == "CIRCLE":
            position = points[obj.refs[0]]
            add(
                Entity(
                    id=f"circle_{name}",
                    type="CIRCLE",
                    refs=obj.refs,
                    x=position[0],
                    y=position[1],
                    radius=obj.radius,
                )
            )
    for relation in math_state.relations:
        if relation.status not in ESTABLISHED or relation.id in deferred:
            continue
        args = relation.args
        kind = relation.type
        if kind in (RelationType.TRIANGLE, RelationType.QUADRILATERAL):
            prefix = "triangle" if len(args) == 3 else "quadrilateral"
            add(
                Entity(
                    id=f"{prefix}_{''.join(args)}",
                    type="POLYGON",
                    refs=args,
                    relation_id=relation.id,
                )
            )
            for a, b in zip(args, (*args[1:], args[0])):
                segment(a, b)
        elif kind == RelationType.CONCYCLIC:
            center = circumcenter(*(np.array(points[a]) for a in args[:3]))
            radius = float(np.linalg.norm(np.array(points[args[0]]) - center))
            add(
                Entity(
                    id=f"circle_{relation.id}",
                    type="CIRCLE",
                    refs=args,
                    x=float(center[0]),
                    y=float(center[1]),
                    radius=radius,
                    relation_id=relation.id,
                )
            )
        elif kind == RelationType.CIRCUMCENTER:
            o, a, b, c = args
            add(
                Entity(
                    id=f"triangle_{a}{b}{c}",
                    type="POLYGON",
                    refs=(a, b, c),
                    role="AUXILIARY",
                    relation_id=relation.id,
                )
            )
        elif kind == RelationType.MIDPOINT:
            m, a, b = args
            segment(a, m)
            segment(m, b)
            add(
                Entity(
                    id=f"mark_midpoint_{relation.id}",
                    type="EQUAL_LENGTH_MARK",
                    refs=(a, m, m, b),
                    relation_id=relation.id,
                )
            )
        elif kind == RelationType.TANGENT:
            p, t, circle = args
            o = math_state.objects[circle].refs[0]
            segment(p, t)
            segment(o, t, "AUXILIARY")
            point = entities[f"point_{t}"]
            entities[point.id] = point.model_copy(update={"role": "CONTACT"})
        elif kind == RelationType.COLLINEAR:
            add(Entity(id=f"line_{''.join(args)}", type="LINE", refs=args, relation_id=relation.id))
        elif kind == RelationType.EXTENSION:
            e, a, b = args
            segment(a, b)
            add(
                Entity(
                    id=f"extension_{b}{e}",
                    type="SEGMENT",
                    refs=(b, e),
                    role="EXTENSION",
                    relation_id=relation.id,
                )
            )
        elif kind == RelationType.ALTITUDE:
            h, a, b, c = args
            segment(a, h, "AUXILIARY")
            add(
                Entity(
                    id=f"right_angle_{relation.id}",
                    type="RIGHT_ANGLE_MARK",
                    refs=(a, h, b, c),
                    relation_id=relation.id,
                )
            )
        elif kind in (
            RelationType.PERPENDICULAR,
            RelationType.PARALLEL,
            RelationType.EQUAL_LENGTH,
            RelationType.EQUAL_ANGLE,
            RelationType.SIMILAR,
        ):
            if kind in (
                RelationType.PARALLEL,
                RelationType.PERPENDICULAR,
                RelationType.EQUAL_LENGTH,
            ):
                for a, b in zip(args[::2], args[1::2]):
                    if f"segment_{a}{b}" not in entities and f"segment_{b}{a}" not in entities:
                        segment(a, b)
            mark = {
                RelationType.PERPENDICULAR: "RIGHT_ANGLE_MARK",
                RelationType.PARALLEL: "PARALLEL_MARK",
                RelationType.EQUAL_LENGTH: "EQUAL_LENGTH_MARK",
                RelationType.EQUAL_ANGLE: "ANGLE_MARK",
                RelationType.SIMILAR: "CORRESPONDENCE_MARK",
            }[kind]
            add(Entity(id=f"mark_{relation.id}", type=mark, refs=args, relation_id=relation.id))
    if len(entities) > 256:
        raise GeometryError("scene limit exceeded: 256 entities")
    return entities
