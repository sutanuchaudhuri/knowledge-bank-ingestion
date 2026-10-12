"""Versioned theorem statements with executable, conservative prerequisite checks."""

from __future__ import annotations

from .errors import GeometryError
from .schemas import ESTABLISHED, Relation, RelationType

SNAPSHOT = "geometry-theorems-v1"
CATALOG = {
    "tangent_radius": {
        "statement": "A radius to a tangent contact is perpendicular to the tangent.",
        "prerequisites": ["TANGENT"],
    },
    "midpoint_equal_halves": {
        "statement": "A midpoint divides its segment into equal lengths.",
        "prerequisites": ["MIDPOINT"],
    },
    "midpoint_collinear": {
        "statement": "A midpoint lies on the line of its segment endpoints.",
        "prerequisites": ["MIDPOINT"],
    },
    "aa_similarity": {
        "statement": "Two corresponding equal-angle pairs imply triangle similarity.",
        "prerequisites": ["EQUAL_ANGLE", "EQUAL_ANGLE"],
    },
    "straight_angle_collinear": {
        "statement": "A 180 degree angle has collinear endpoints and vertex.",
        "prerequisites": ["ANGLE_MEASURE"],
    },
}


def lookup(theorem_id: str | None = None) -> dict:
    if theorem_id is None:
        return {"snapshot": SNAPSHOT, "theorems": CATALOG}
    if theorem_id not in CATALOG:
        raise GeometryError(f"unknown theorem: {theorem_id}")
    return {"id": theorem_id, "snapshot": SNAPSHOT, **CATALOG[theorem_id]}


def establish(theorem_id: str, conclusion: Relation, facts, objects, premise_ids):
    lookup(theorem_id)
    premises = []
    for name in premise_ids:
        relation = next((r for r in facts if r.id == name), None)
        if relation is None or relation.status not in ESTABLISHED:
            raise GeometryError(f"theorem prerequisite not established: {name}")
        premises.append(relation)
    valid = False
    if theorem_id == "tangent_radius" and len(premises) == 1:
        tangent = premises[0]
        if tangent.type == RelationType.TANGENT:
            p, t, circle = tangent.args
            o = objects[circle].refs[0]
            valid = conclusion.type == RelationType.PERPENDICULAR and conclusion.args == (
                o,
                t,
                p,
                t,
            )
    elif theorem_id.startswith("midpoint_") and len(premises) == 1:
        midpoint = premises[0]
        if midpoint.type == RelationType.MIDPOINT:
            m, a, b = midpoint.args
            valid = (
                theorem_id == "midpoint_equal_halves"
                and conclusion.type == RelationType.EQUAL_LENGTH
                and conclusion.args == (a, m, m, b)
            ) or (
                theorem_id == "midpoint_collinear"
                and conclusion.type == RelationType.COLLINEAR
                and set(conclusion.args) == {a, m, b}
            )
    elif theorem_id == "straight_angle_collinear" and len(premises) == 1:
        angle = premises[0]
        valid = (
            angle.type == RelationType.ANGLE_MEASURE
            and angle.value == 180
            and conclusion.type == RelationType.COLLINEAR
            and set(conclusion.args) == set(angle.args)
        )
    elif theorem_id == "aa_similarity" and len(premises) == 2:
        if conclusion.type == RelationType.SIMILAR:
            a, b, c, d, e, f = conclusion.args
            expected = {(a, b, c, d, e, f), (a, c, b, d, f, e)}
            valid = (
                all(p.type == RelationType.EQUAL_ANGLE for p in premises)
                and {p.args for p in premises} == expected
            )
    if not valid:
        raise GeometryError(f"theorem {theorem_id} does not justify this conclusion")
