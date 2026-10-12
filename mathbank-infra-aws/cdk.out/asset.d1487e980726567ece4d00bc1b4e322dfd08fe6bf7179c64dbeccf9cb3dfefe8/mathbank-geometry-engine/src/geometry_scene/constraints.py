from __future__ import annotations

import math

import numpy as np

from .errors import GeometryError
from .schemas import MathObject, Relation, RelationType

TOLERANCE = 1e-6


def circumcenter(a, b, c):
    matrix = 2 * np.array([b - a, c - a])
    if abs(np.linalg.det(matrix)) < 1e-8:
        raise GeometryError("circumcenter requires a nondegenerate triangle")
    return np.linalg.solve(matrix, np.array([b @ b - a @ a, c @ c - a @ a]))


def cross(a, b):
    return float(a[0] * b[1] - a[1] * b[0])


def cosine(a, b, c):
    u, v = a - b, c - b
    denominator = np.linalg.norm(u) * np.linalg.norm(v)
    if denominator < 1e-8:
        raise GeometryError("angle has coincident points")
    return float(np.clip(u @ v / denominator, -1, 1))


def residuals(relation: Relation, points: dict, objects: dict[str, MathObject]) -> list[float]:
    args = relation.args
    kind = relation.type
    if kind == RelationType.TANGENT:
        p, t = (points[a] for a in args[:2])
        circle = objects[args[2]]
        o = points[circle.refs[0]]
        radius = circle.radius
        if radius is None:
            raise GeometryError("tangent requires a circle radius")
        return [
            float((np.linalg.norm(t - o) - radius) / max(radius, 1)),
            float((t - o) @ (p - t) / max(radius * np.linalg.norm(p - t), 1)),
        ]
    values = [points[a] for a in args]
    if kind in (RelationType.TRIANGLE, RelationType.QUADRILATERAL):
        return []
    if kind == RelationType.MIDPOINT:
        m, a, b = values
        return list((m - (a + b) / 2) / 100)
    if kind == RelationType.CIRCUMCENTER:
        o, a, b, c = values
        return list((o - circumcenter(a, b, c)) / 100)
    if kind == RelationType.CONCYCLIC:
        a, b, c, *others = values
        center = circumcenter(a, b, c)
        radius = float(np.linalg.norm(a - center))
        return [float((np.linalg.norm(p - center) - radius) / max(radius, 1)) for p in others]
    if kind in (RelationType.COLLINEAR, RelationType.EXTENSION):
        if kind == RelationType.EXTENSION:
            e, a, b = values
            penalty = min(0, float((e - b) @ (b - a))) / 10000
            return [cross(b - a, e - a) / max(np.linalg.norm(b - a) ** 2, 1), penalty]
        a, b, c = values
        return [cross(b - a, c - a) / max(np.linalg.norm(c - a) ** 2, 1)]
    if kind in (RelationType.PARALLEL, RelationType.PERPENDICULAR, RelationType.EQUAL_LENGTH):
        a, b, c, d = values
        u, v = b - a, d - c
        scale = max(float(np.linalg.norm(u) * np.linalg.norm(v)), 1)
        if kind == RelationType.PARALLEL:
            return [cross(u, v) / scale]
        if kind == RelationType.PERPENDICULAR:
            return [float(u @ v) / scale]
        return [float(np.linalg.norm(u) - np.linalg.norm(v)) / 100]
    if kind == RelationType.ALTITUDE:
        h, a, b, c = values
        return [
            cross(h - b, c - b) / max(np.linalg.norm(c - b) ** 2, 1),
            float((h - a) @ (c - b)) / max(float(np.linalg.norm(c - b) ** 2), 1),
        ]
    if kind == RelationType.INTERSECTION:
        e, a, b, c, d = values
        return [
            cross(e - a, b - a) / max(np.linalg.norm(b - a) ** 2, 1),
            cross(e - c, d - c) / max(np.linalg.norm(d - c) ** 2, 1),
        ]
    if kind in (RelationType.EQUAL_ANGLE, RelationType.SIMILAR):
        a, b, c, d, e, f = values
        result = [cosine(a, b, c) - cosine(d, e, f)]
        if kind == RelationType.SIMILAR:
            result.append(cosine(b, c, a) - cosine(e, f, d))
        return result
    if kind == RelationType.ANGLE_MEASURE:
        if relation.value is None:
            raise GeometryError("angle measure requires a value")
        return [cosine(*values) - math.cos(math.radians(relation.value))]
    raise GeometryError(f"unsupported constraint {kind}")


def maximum_residual(relation, points, objects):
    return max((abs(float(r)) for r in residuals(relation, points, objects)), default=0.0)
