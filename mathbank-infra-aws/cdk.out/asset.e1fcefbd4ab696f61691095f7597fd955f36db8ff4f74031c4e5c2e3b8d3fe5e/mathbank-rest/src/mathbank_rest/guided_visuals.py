"""Statement-verified geometric definitions and bounded instructional intents."""

import re

Q31 = "PRASOLOV_PGV1_CH06_P031"


def circumcenter_setup(problem: dict) -> dict | None:
    if problem["canonical_code"] != Q31:
        return None
    statement = re.sub(r"\s+", " ", problem.get("statement_text", "")).lower()
    # This authored parser deliberately rejects missing/reordered definitions.
    if not all(re.search(pattern, statement) for pattern in (
        r"convex quadrilateral abcd",
        r"centers a_?1,?\s*b_?1,?\s*c_?1 and d_?1",
        r"circumscribed circles of triangles bcd,\s*cda,\s*dab and abc,\s*respectively",
        r"points a_?2,?\s*b_?2,?\s*c_?2 and d_?2 are similarly defined",
    )):
        return None
    definitions = []
    for level in (1, 2):
        parent = [letter if level == 1 else f"{letter}1" for letter in "ABCD"]
        for index, letter in enumerate("ABCD"):
            triangle = [parent[(index + offset) % 4] for offset in (1, 2, 3)]
            definitions.append({
                "id": f"{letter}{level}", "type": "circumcenter", "triangle": triangle,
                "level": level, "provenance": "canonical-statement-definition",
            })
    return {
        "version": "circumcenter-iteration-v1", "problem_code": Q31,
        "base": {"type": "convex-quadrilateral", "vertices": list("ABCD")},
        "definitions": definitions, "iterations": 2,
        "coordinate_policy": "illustrative-nondegenerate-not-source",
    }


def visual_intent(problem: dict, index: int) -> dict | None:
    setup = circumcenter_setup(problem)
    if setup is None:
        return None
    goals = [
        ("DEFINE_A1", ["quadrilateral_ABCD", "triangle_BCD", "A1"]),
        ("SHARED_CD", ["triangle_BCD", "triangle_CDA", "A1", "B1", "segment_CD"]),
        ("EQUAL_RADII", ["triangle_BCD", "A1", "radius_A1C", "radius_A1D"]),
        ("ITERATE_CIRCUMCENTERS", ["quadrilateral_A1B1C1D1", "A1", "B1", "C1", "D1"]),
    ]
    goal, required = goals[min(index, 3)]
    return {
        "artifact_goal": "TEACH_CURRENT_OBJECT", "subject": "geometry",
        "problem_code": Q31, "current_step": goal, "must_show": required,
        "max_level": 1 if index < 3 else 2, "frame_mode": "progressive",
        "forbidden_claims": ["similarity-proof", "derived-scale-factor"],
        "setup": setup,
    }
