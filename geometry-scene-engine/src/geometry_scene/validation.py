from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET

import numpy as np

from .constraints import TOLERANCE, cosine, cross, maximum_residual
from .errors import GeometryError
from .policy import label_bounds, overlaps
from .renderer import LAYERS, NS, render
from .schemas import ESTABLISHED, RelationType, ValidationRecord

MARK_KINDS = {
    "RIGHT_ANGLE_MARK": {RelationType.PERPENDICULAR, RelationType.ALTITUDE},
    "EQUAL_LENGTH_MARK": {RelationType.EQUAL_LENGTH, RelationType.MIDPOINT},
    "PARALLEL_MARK": {RelationType.PARALLEL},
    "CORRESPONDENCE_MARK": {RelationType.SIMILAR},
    "ANGLE_MARK": {RelationType.EQUAL_ANGLE},
}

CLAIM_WORDS = {
    RelationType.COLLINEAR: r"collinear|collinearity|straight line|lie on (?:one|the same) line",
    RelationType.PARALLEL: r"parallel|parallelism",
    RelationType.PERPENDICULAR: r"perpendicular|perpendicularity|orthogonal|right angle",
    RelationType.EQUAL_LENGTH: r"equal|equality|congruent|congruence|same length",
    RelationType.EQUAL_ANGLE: r"equal|equality|congruent|congruence|same angle",
    RelationType.SIMILAR: r"similar|similarity",
    RelationType.CONCYCLIC: r"cyclic|concyclic|cyclicity|concyclicity|same circle",
}


def caption_errors(math_state, text):
    if not text or re.fullmatch(
        r"(?:goal|target|question)\s*:\s*[^.!]+[.?]?|"
        r"(?:prove|show)\s+(?:that\s+)?[^.!]+[.?]?",
        text.strip(),
        re.IGNORECASE,
    ):
        return []
    errors = []
    for relation in math_state.relations:
        if relation.status in ESTABLISHED or relation.type not in CLAIM_WORDS:
            continue
        words = CLAIM_WORDS[relation.type]
        if not re.search(r"\b(?:" + words + r")\b", text, re.IGNORECASE):
            continue
        if re.fullmatch(
            r"(?:collinearity|parallelism|similarity|cyclicity)(?: of [A-Za-z, ]+)? "
            r"(?:is )?(?:not yet established|unproved|unproven|a target to prove)[.!]?",
            text.strip(),
            re.IGNORECASE,
        ):
            continue
        mentioned = any(re.search(rf"\b{re.escape(arg)}\b", text) for arg in relation.args)
        other_named = any(
            re.search(rf"\b{re.escape(point)}\b", text)
            for point in math_state.objects
            if point not in relation.args
        )
        if mentioned or not other_named:
            errors.append(f"caption may assert unestablished relation: {relation.id}")
    return errors


def validate(math_state, scene, visual, svg):
    errors, warnings, numerical = [], [], {}
    errors.extend(caption_errors(math_state, visual.caption))
    for overlay in visual.overlays:
        errors.extend(caption_errors(math_state, overlay.caption))
    points = {e.refs[0]: np.array([e.x, e.y]) for e in scene.entities.values() if e.type == "POINT"}
    # Deferred definitions are computed for numerical truth, not forced onto the current frame.
    definitions = scene.solver_diagnostics.get("all_positions", {})
    all_points = {**{key: np.array(value) for key, value in definitions.items()}, **points}
    relations = {r.id: r for r in math_state.relations}
    minimum_angle = scene.solver_diagnostics.get("minimum_angle_degrees")
    if minimum_angle is not None:
        for relation in math_state.relations:
            if relation.status not in ESTABLISHED:
                continue
            triangle = (
                relation.args
                if relation.type == "TRIANGLE"
                else relation.args[1:]
                if relation.type == "CIRCUMCENTER"
                else None
            )
            if triangle:
                try:
                    values = [all_points[p] for p in triangle]
                    if any(
                        cosine(values[i - 1], values[i], values[(i + 1) % 3])
                        > math.cos(math.radians(minimum_angle)) + TOLERANCE
                        for i in range(3)
                    ):
                        errors.append(f"minimum-angle constraint violation: {relation.id}")
                except (GeometryError, KeyError):
                    errors.append(f"minimum-angle validation could not resolve {relation.id}")
    for overlay in visual.overlays:
        if any(target not in scene.entities for target in overlay.targets):
            errors.append(f"overlay reference does not resolve: {overlay.id}")
    marker_keys = set()
    for relation in math_state.relations:
        try:
            value = maximum_residual(relation, all_points, math_state.objects)
            numerical[relation.id] = value
            if relation.status in ESTABLISHED and value > TOLERANCE:
                errors.append(f"constraint violation: {relation.id} residual={value:.6g}")
            forbidden = relation.status not in ESTABLISHED
            testable = relation.type not in (
                RelationType.TRIANGLE,
                RelationType.QUADRILATERAL,
                RelationType.CONCYCLIC,
                RelationType.SIMILAR,
            ) or (relation.type == RelationType.CONCYCLIC and len(relation.args) == 4)
            if forbidden and testable and value < 1e-4 and all(a in points for a in relation.args):
                errors.append(f"numerical proof leakage: {relation.id}")
        except (GeometryError, KeyError) as exc:
            errors.append(f"{relation.id}: {exc}")
    for relation in math_state.relations:
        if relation.status not in ESTABLISHED:
            continue
        if relation.type in (RelationType.TRIANGLE, RelationType.QUADRILATERAL):
            vertices = [all_points[a] for a in relation.args]
            signs = [
                cross(
                    vertices[(i + 1) % len(vertices)] - vertices[i],
                    vertices[(i + 2) % len(vertices)] - vertices[(i + 1) % len(vertices)],
                )
                for i in range(len(vertices))
            ]
            if min(abs(v) for v in signs) < 1 or not (
                all(v > 0 for v in signs) or all(v < 0 for v in signs)
            ):
                errors.append(f"degenerate/nonconvex polygon: {relation.id}")
    names = list(points)
    for index, a in enumerate(names):
        for b in names[index + 1 :]:
            if np.linalg.norm(points[a] - points[b]) < 8:
                errors.append(f"coincident/visually indistinct points: {a}, {b}")
    boxes = []
    xmin, ymin, width, height = visual.view_box
    for name, entity in scene.entities.items():
        style = visual.styles.get(name)
        if style is None:
            errors.append(f"missing visual style: {name}")
            continue
        if entity.role == "CONTACT" and entity.type == "POINT" and not style.visible:
            errors.append(f"invisible contact point: {name}")
        if not style.visible:
            continue
        if any(ref not in points for ref in entity.refs):
            errors.append(f"entity refers to unconstructed point: {name}")
        neutral_angle = (
            entity.type == "ANGLE_MARK" and len(entity.refs) == 3 and not entity.relation_id
        )
        if entity.type in MARK_KINDS and not neutral_angle:
            key = (entity.type, entity.refs)
            if key in marker_keys:
                errors.append(f"overlapping duplicate markers: {name}")
            marker_keys.add(key)
            relation = relations.get(entity.relation_id)
            if not relation or relation.status not in ESTABLISHED:
                errors.append(f"unjustified marker/proof leakage: {name}")
            elif relation.type not in MARK_KINDS[entity.type]:
                errors.append(f"marker relation type mismatch: {name}")
            else:
                expected = relation.args
                if relation.type == RelationType.MIDPOINT:
                    m, a, b = relation.args
                    expected = (a, m, m, b)
                elif relation.type == RelationType.ALTITUDE:
                    h, a, b, c = relation.args
                    expected = (a, h, b, c)
                if entity.refs != expected:
                    errors.append(f"marker references differ from justified relation: {name}")
        if entity.relation_id:
            relation = relations.get(entity.relation_id)
            if relation is None or relation.status not in ESTABLISHED:
                errors.append(f"visible entity asserts unestablished relation: {name}")
        if entity.type in ("CIRCLE", "ARC"):
            if style.emphasis != "HIGHLIGHT" and (
                style.opacity > 0.5 or style.emphasis not in ("BACKGROUND", "DIM")
            ):
                errors.append(f"excessive circle prominence: {name}")
            for relation in math_state.relations:
                if (
                    relation.type == RelationType.CONCYCLIC
                    and relation.status not in ESTABLISHED
                    and all(a in points for a in relation.args)
                    and all(
                        abs(np.linalg.norm(points[a] - [entity.x, entity.y]) - entity.radius) < 1e-4
                        for a in relation.args
                    )
                ):
                    errors.append(f"definitive circle proof leakage: {relation.id}")
        if entity.role == "CONTACT" and entity.type == "POINT" and style.opacity < 0.7:
            errors.append(f"indistinct contact point: {name}")
        if (
            entity.role in ("EXTENSION", "AUXILIARY")
            and entity.type in ("SEGMENT", "LINE", "RAY")
            and style.line_style != "DASHED"
        ):
            errors.append(f"auxiliary/extension must stay dashed: {name}")
        if entity.type == "POINT":
            if not (
                xmin + 5 <= entity.x <= xmin + width - 5
                and ymin + 5 <= entity.y <= ymin + height - 5
            ):
                errors.append(f"offscreen point: {name}")
            if style.label and style.label_position:
                box = label_bounds(style.label_position, style.label)
                if (
                    box[0] < xmin
                    or box[1] < ymin
                    or box[2] > xmin + width
                    or box[3] > ymin + height
                ):
                    errors.append(f"clipped label: {name}")
                if any(overlaps(box, b) for b in boxes):
                    errors.append(f"label collision: {name}")
                boxes.append(box)
        if (
            entity.type in ("SEGMENT", "LINE", "RAY")
            and all(a in points for a in entity.refs)
            and np.linalg.norm(points[entity.refs[-1]] - points[entity.refs[0]]) < 8
        ):
            errors.append(f"short important segment: {name}")
    for entity in scene.entities.values():
        if entity.role == "CONTACT" and (
            not visual.styles[entity.id].visible or visual.styles[entity.id].opacity < 0.5
        ):
            errors.append(f"invisible contact point: {entity.id}")
    try:
        root = ET.fromstring(svg)
        ids = [n.attrib["id"] for n in root.iter() if "id" in n.attrib]
        if root.tag != f"{{{NS}}}svg" or len(ids) != len(set(ids)):
            errors.append("invalid SVG root or duplicate element IDs")
        if not set(LAYERS).issubset(ids) or not set(scene.entities).issubset(ids):
            errors.append("SVG missing layers or semantic entities")
        if svg != render(scene, visual):
            errors.append("SVG differs from the saved scene/visual state")
    except (ET.ParseError, ValueError, ZeroDivisionError, KeyError) as exc:
        errors.append(f"SVG structure/render failure: {type(exc).__name__}")
    if any(not math.isfinite(v) for v in numerical.values()):
        errors.append("nonfinite numerical validation")
    return ValidationRecord(
        valid=not errors, errors=tuple(errors), warnings=tuple(warnings), residuals=numerical
    )
