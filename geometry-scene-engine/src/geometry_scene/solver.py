from __future__ import annotations

import math

import numpy as np
from scipy.optimize import least_squares

from .constraints import TOLERANCE, circumcenter, cosine, cross, maximum_residual, residuals
from .errors import GeometryError
from .schemas import ESTABLISHED, RelationType


def solve(math_state, positions, locked, seed, view_box, minimum_angle=None):
    points = {key: np.array(value, dtype=float) for key, value in positions.items()}
    names = sorted(key for key, obj in math_state.objects.items() if obj.type == "POINT")
    rng = np.random.default_rng(seed)
    for name in names:
        if name not in points:
            points[name] = rng.uniform([100, 90], [520, 390])
    active = [r for r in math_state.relations if r.status in ESTABLISHED]
    triangles = [r.args for r in active if r.type == RelationType.TRIANGLE]
    triangles += [r.args[1:] for r in active if r.type == RelationType.CIRCUMCENTER]

    def angle_penalties(candidate):
        if minimum_angle is None:
            return []
        limit = math.cos(math.radians(minimum_angle))
        return [
            max(0, cosine(candidate[a], candidate[b], candidate[c]) - limit)
            for triangle in triangles
            for a, b, c in (
                triangle,
                (triangle[1], triangle[2], triangle[0]),
                (triangle[2], triangle[0], triangle[1]),
            )
        ]

    for relation in active:
        if set(relation.args) & locked or all(name in positions for name in relation.args):
            continue
        if relation.type == RelationType.QUADRILATERAL:
            for name, point in zip(relation.args, [(100, 100), (460, 90), (510, 360), (150, 310)]):
                points[name] = np.array(point, dtype=float) + rng.uniform(-4, 4, 2)
        elif relation.type == RelationType.TRIANGLE:
            for name, point in zip(relation.args, [(230, 80), (100, 340), (510, 300)]):
                points[name] = np.array(point, dtype=float) + rng.uniform(-4, 4, 2)
    for relation in active:
        if relation.type == RelationType.CONCYCLIC and not set(relation.args) & locked:
            for index, name in enumerate(relation.args):
                angle = -2.5 + (seed % 23) * 0.002 + 2 * math.pi * index / len(relation.args)
                points[name] = np.array([320 + 155 * math.cos(angle), 240 + 155 * math.sin(angle)])
        elif relation.type == RelationType.COLLINEAR and not set(relation.args) & locked:
            a, b, c = relation.args
            direction = points[c] - points[a]
            if direction @ direction < 1e-8:
                raise GeometryError("collinear endpoints are coincident")
            fraction = float((points[b] - points[a]) @ direction / (direction @ direction))
            points[b] = points[a] + direction * np.clip(fraction, 0.15, 0.85)
    derived = set()
    pending = [
        r
        for r in active
        if r.type
        in {
            RelationType.MIDPOINT,
            RelationType.CIRCUMCENTER,
            RelationType.ALTITUDE,
            RelationType.INTERSECTION,
            RelationType.EXTENSION,
        }
    ]
    while pending:
        ready = [r for r in pending if not any(dep.args[0] in r.args[1:] for dep in pending)]
        if not ready:
            raise GeometryError("cyclic construction dependencies")
        for relation in ready:
            name = relation.args[0]
            if name in locked:
                pending.remove(relation)
                continue
            values = [points[a] for a in relation.args[1:]]
            if relation.type == RelationType.MIDPOINT:
                result = sum(values) / 2
            elif relation.type == RelationType.CIRCUMCENTER:
                result = circumcenter(*values)
            elif relation.type == RelationType.EXTENSION:
                a, b = values
                result = b + (b - a) * 0.6
            elif relation.type == RelationType.ALTITUDE:
                a, b, c = values
                u = c - b
                if u @ u < 1e-8:
                    raise GeometryError("altitude base has coincident points")
                result = b + u * ((a - b) @ u) / (u @ u)
            else:
                a, b, c, d = values
                u, v = b - a, d - c
                denominator = cross(u, v)
                if abs(denominator) < 1e-8:
                    raise GeometryError("intersection lines are parallel or coincident")
                result = a + u * cross(c - a, v) / denominator
            points[name] = result
            derived.add(name)
            pending.remove(relation)
    free = [name for name in names if name not in locked]
    start = np.concatenate([points[name] for name in free]) if free else np.array([])
    iterations = 0
    if free and (
        any(maximum_residual(r, points, math_state.objects) > TOLERANCE for r in active)
        or any(v > TOLERANCE for v in angle_penalties(points))
    ):
        fixed = dict(points)

        def objective(vector):
            candidate = {
                **fixed,
                **{name: vector[2 * i : 2 * i + 2] for i, name in enumerate(free)},
            }
            mathematical = [
                item for r in active for item in residuals(r, candidate, math_state.objects)
            ]
            separation = [
                max(0.0, 16 - float(np.linalg.norm(candidate[a] - candidate[b]))) / 100
                for i, a in enumerate(names)
                for b in names[i + 1 :]
            ]
            return [
                *mathematical,
                *separation,
                *angle_penalties(candidate),
                *((vector - start) * 1e-9),
            ]

        xmin, ymin, width, height = view_box
        lower = np.tile([xmin + 24, ymin + 24], len(free))
        upper = np.tile([xmin + width - 24, ymin + height - 24], len(free))
        if np.any(start < lower) or np.any(start > upper):
            raise GeometryError("initial free points exceed solver viewport bounds")
        fit = least_squares(
            objective,
            start,
            bounds=(lower, upper),
            max_nfev=400,
            ftol=1e-12,
            xtol=1e-12,
            gtol=1e-12,
        )
        iterations = fit.nfev
        points.update({name: fit.x[2 * i : 2 * i + 2] for i, name in enumerate(free)})
    errors = {r.id: maximum_residual(r, points, math_state.objects) for r in active}
    if any(v > TOLERANCE for v in angle_penalties(points)):
        raise GeometryError("minimum-angle constraint conflicts with the current realization")
    if any(not np.isfinite(p).all() for p in points.values()):
        raise GeometryError("solver returned nonfinite coordinates")
    return {name: tuple(float(v) for v in p) for name, p in points.items()}, {
        "method": "analytic-construction+bounded-least-squares",
        "seed": seed,
        "iterations": iterations,
        "locked_points": sorted(locked),
        "analytic_points": sorted(derived),
        "residuals": errors,
        "converged": all(v <= TOLERANCE for v in errors.values()),
    }
