"""Shared conservative Power-of-a-Point structural audit for import and runtime."""

import re

POWER = "TECH.GEO.POWER_OF_A_POINT"
PRODUCT = re.compile(
    r"\b[A-Z]{2}\s*(?:\\cdot|[·*])\s*[A-Z]{2}\s*=\s*[A-Z]{2}\s*(?:\\cdot|[·*])\s*[A-Z]{2}\b"
)
TANGENT = re.compile(r"\b[A-Z]{2}\s*(?:\^?\{?2\}?|²)\s*=\s*[A-Z]{2}\s*(?:\\cdot|[·*])\s*[A-Z]{2}\b")
RADIUS = re.compile(r"\bR\s*(?:\^?\{?2\}?|²)\s*[−-]\s*[A-Z]{2}\s*(?:\^?\{?2\}?|²)")


def power_structure(statement: str, steps: list[dict]) -> dict:
    text_ = statement + "\n" + "\n".join(step.get("step_text") or "" for step in steps)
    circle = bool(re.search(r"\bcircle|circumcircle|chords?|secants?|tangents?\b", text_, re.IGNORECASE))
    kinds: set[str] = set()
    evidence_ids = []
    for step in steps:
        value = step.get("step_text") or ""
        found = False
        if circle and PRODUCT.search(value):
            kinds.add("SEGMENT_PRODUCT")
            found = True
        if circle and TANGENT.search(value):
            kinds.add("TANGENT_SECANT_PRODUCT")
            found = True
        if circle and RADIUS.search(value):
            kinds.add("POWER_EQUALITY")
            found = True
        if circle and re.search(r"radical (axis|axes).*equal.*power|equal.*power.*radical (axis|axes)", value, re.IGNORECASE):
            kinds.add("RADICAL_AXIS_POWER_COMPARISON")
            found = True
        if found:
            evidence_ids.append(step["solution_step_id"])
    return {"structural_signatures": sorted(kinds), "evidence_step_ids": evidence_ids[:20],
            "status": "SUPPORTED_SIGNATURE" if kinds else "REVIEW_REQUIRED",
            "limitation": "Heuristic signatures are not proof. Missing signatures require source/solution review, not automatic rejection."}
