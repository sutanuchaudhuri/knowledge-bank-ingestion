"""Declarative widget registry, validator and deterministic composer (fluid 08–12/19/20, dist 13).

Widgets are data, never code: a WidgetSpec is ``{widget_type, version, title, data_refs, config,
interaction, persistence, source_lineage}`` and is rendered only by a whitelisted renderer in the
shared ``mathbank-widgets`` package. Anything that looks like executable/markup content (script,
raw HTML, CSS, JSX, event handlers, ``javascript:`` URLs, KaTeX ``\\href``…) is rejected here, before
it is stored or shown. This module is pure: database reference checks are injected as callbacks.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Callable

SPEC_VERSION = "1"
MAX_SPEC_BYTES = 64_000
MAX_ELEMENTS = 300
PERSISTENCE = ("STATIC", "SESSION", "EPHEMERAL")
PRIMITIVES = ("POINT", "SEGMENT", "RAY", "LINE", "CIRCLE", "ARC", "POLYGON", "ANGLE", "LABEL",
              "AUXILIARY_CONSTRUCTION")
OPERATIONS = ("HIGHLIGHT", "DIM", "SHOW", "HIDE", "PULSE", "TRACE", "MARK_EQUAL", "MARK_PARALLEL",
              "MARK_PERPENDICULAR", "SHOW_RATIO")

# widget_type -> allowed config keys and allowed data_refs keys (fluid 09 registry).
REGISTRY: dict[str, dict] = {
    "GEOMETRY_DIAGRAM": {"config": {"elements", "operations", "view_box", "caption"}, "refs": {"problem_id"},
                         "label": "Geometry construction"},
    "GEOMETRY_OVERLAY": {"config": {"elements", "operations", "view_box", "caption"},
                         "refs": {"problem_image_id", "problem_id"}, "label": "Diagram with overlay"},
    "COORDINATE_GRAPH": {"config": {"curves", "points", "x_range", "y_range", "caption"}, "refs": set(),
                         "label": "Coordinate graph"},
    "KNOWLEDGE_GRAPH": {"config": {"nodes", "edges", "caption"}, "refs": {"concept_id"}, "label": "Concept map"},
    "REASONING_DAG": {"config": {"nodes", "edges", "current", "caption"}, "refs": {"problem_id"},
                      "label": "Reasoning DAG"},
    "NUMBER_LINE": {"config": {"min", "max", "points", "intervals", "caption"}, "refs": set(), "label": "Number line"},
    "TABLE": {"config": {"columns", "rows", "caption"}, "refs": set(), "label": "Table"},
    "FORMULA_CARD": {"config": {"latex", "items", "caption"}, "refs": set(), "label": "Formula card"},
    "TIMELINE": {"config": {"items", "caption"}, "refs": set(), "label": "Timeline"},
    "BAR_CHART": {"config": {"bars", "max", "caption"}, "refs": set(), "label": "Bar chart"},
    "POLL_RESULT": {"config": {"prompt", "options", "counts", "percentages", "response_count", "correct_option",
                               "reveal", "caption"}, "refs": {"activity_instance_id"}, "label": "Poll result"},
    "STEP_PROGRESS": {"config": {"steps", "current", "caption"}, "refs": {"problem_id"}, "label": "Step progress"},
    "COMPARISON": {"config": {"left", "right", "rows", "caption"}, "refs": set(), "label": "Comparison"},
}
TOP_LEVEL_KEYS = {"widget_type", "version", "title", "data_refs", "config", "interaction", "persistence",
                  "source_lineage"}
INTERACTION_KEYS = {"selectable", "zoom", "student_events"}

FORBIDDEN_KEYS = {"script", "javascript", "eval", "raw_html", "html", "innerhtml", "dangerouslysetinnerhtml",
                  "jsx", "css", "arbitrary_css", "style", "component", "code", "function", "src_code", "template"}
_FORBIDDEN_VALUE = re.compile(
    r"<\s*/?\s*(script|iframe|img|svg|style|object|embed|link|meta|form|input|a)\b"
    r"|javascript\s*:|vbscript\s*:|data\s*:\s*text/html"
    r"|\\(href|url|includegraphics|htmlClass|htmlId|htmlStyle|htmlData)\b"
    r"|\bon[a-z]+\s*=\s*[\"'`]", re.IGNORECASE)


def registry() -> list[dict]:
    return [{"widget_type": t, "label": r["label"], "config_keys": sorted(r["config"]),
             "data_refs": sorted(r["refs"]), "version": SPEC_VERSION} for t, r in REGISTRY.items()]


def content_hash(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _walk(value, path: str, errors: list[str], depth: int = 0) -> None:
    if depth > 12:
        errors.append(f"{path}: nesting too deep")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            low = str(key).lower()
            if low in FORBIDDEN_KEYS or re.match(r"^on[a-z_]", low):
                errors.append(f"{path}.{key}: forbidden key (widgets are declarative data only)")
                continue
            _walk(item, f"{path}.{key}", errors, depth + 1)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk(item, f"{path}[{index}]", errors, depth + 1)
    elif isinstance(value, str):
        if _FORBIDDEN_VALUE.search(value):
            errors.append(f"{path}: forbidden markup/script content")
    elif isinstance(value, float) and not math.isfinite(value):
        errors.append(f"{path}: non-finite number")


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _geometry(config: dict, errors: list[str]) -> None:
    elements = config.get("elements", [])
    if not isinstance(elements, list):
        errors.append("config.elements must be a list")
        return
    if len(elements) > MAX_ELEMENTS:
        errors.append(f"config.elements exceeds {MAX_ELEMENTS}")
    ids: dict[str, str] = {}
    for i, el in enumerate(elements):
        if not isinstance(el, dict) or not isinstance(el.get("id"), str) or not el.get("id"):
            errors.append(f"elements[{i}]: needs a string id")
            continue
        kind = el.get("kind")
        if kind not in PRIMITIVES:
            errors.append(f"elements[{i}] ({el['id']}): unknown primitive {kind!r}")
            continue
        if el["id"] in ids:
            errors.append(f"elements[{i}]: duplicate id {el['id']}")
        ids[el["id"]] = kind
    points = {k for k, v in ids.items() if v == "POINT"}

    def need_points(el: dict, keys: tuple[str, ...]) -> None:
        for key in keys:
            if el.get(key) not in points:
                errors.append(f"{el['id']}: {key}={el.get(key)!r} must reference a POINT id")

    for el in elements:
        if not isinstance(el, dict) or el.get("kind") not in PRIMITIVES or not el.get("id"):
            continue
        kind = el["kind"]
        if kind in ("POINT", "LABEL"):
            if not (_number(el.get("x")) and _number(el.get("y"))):
                errors.append(f"{el['id']}: x and y must be numbers")
        elif kind in ("SEGMENT", "RAY", "LINE", "AUXILIARY_CONSTRUCTION"):
            need_points(el, ("from", "to"))
        elif kind == "CIRCLE":
            need_points(el, ("center",))
            if not _number(el.get("radius")) and el.get("through") not in points:
                errors.append(f"{el['id']}: CIRCLE needs a numeric radius or a through point")
        elif kind in ("ARC", "ANGLE"):
            need_points(el, ("center", "from", "to") if kind == "ARC" else ("vertex", "from", "to"))
        elif kind == "POLYGON":
            pts = el.get("points")
            if not isinstance(pts, list) or len(pts) < 3 or any(p not in points for p in pts):
                errors.append(f"{el['id']}: POLYGON needs >= 3 POINT ids")
    _operations(config.get("operations", []), ids, errors)


def _operations(operations, ids: dict[str, str], errors: list[str]) -> None:
    if not isinstance(operations, list):
        errors.append("operations must be a list")
        return
    for i, op in enumerate(operations):
        if not isinstance(op, dict) or op.get("op") not in OPERATIONS:
            errors.append(f"operations[{i}]: op must be one of {', '.join(OPERATIONS)}")
            continue
        targets = op.get("targets")
        if not isinstance(targets, list) or not targets:
            errors.append(f"operations[{i}]: targets must be a non-empty list of element ids")
            continue
        missing = [t for t in targets if t not in ids]
        if missing:
            errors.append(f"operations[{i}]: unknown element ids {missing}")
        if op["op"] in ("MARK_EQUAL", "MARK_PARALLEL", "MARK_PERPENDICULAR", "SHOW_RATIO") and len(targets) < 2:
            errors.append(f"operations[{i}]: {op['op']} needs at least two targets")


def validate_operations(spec: dict, operations) -> list[str]:
    """Validate a live widget-state update against the elements declared in its spec."""
    errors: list[str] = []
    _walk(operations, "operations", errors)
    ids = {el.get("id"): el.get("kind") for el in (spec.get("config") or {}).get("elements", [])
           if isinstance(el, dict)}
    _operations(operations, ids, errors)
    return errors


def validate(spec: dict, ref_checker: Callable[[str, str], str | None] | None = None,
             audience: str = "STUDENT") -> dict:
    """Return ``{valid, errors, warnings, normalized}``. ``ref_checker(kind, value)`` returns an error or None."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(spec, dict):
        return {"valid": False, "errors": ["spec must be an object"], "warnings": [], "normalized": None}
    try:
        size = len(json.dumps(spec))
    except (TypeError, ValueError):
        return {"valid": False, "errors": ["spec must be JSON-serialisable"], "warnings": [], "normalized": None}
    if size > MAX_SPEC_BYTES:
        errors.append(f"spec is {size} bytes; limit {MAX_SPEC_BYTES}")
    _walk(spec, "spec", errors)
    unknown = set(spec) - TOP_LEVEL_KEYS
    if unknown:
        errors.append(f"unknown top-level keys {sorted(unknown)}")
    widget_type = spec.get("widget_type")
    entry = REGISTRY.get(widget_type)
    if entry is None:
        errors.append(f"widget_type {widget_type!r} is not in the registry")
    if str(spec.get("version", SPEC_VERSION)) != SPEC_VERSION:
        errors.append(f"unsupported spec version {spec.get('version')!r}")
    if spec.get("persistence", "SESSION") not in PERSISTENCE:
        errors.append("persistence must be STATIC, SESSION or EPHEMERAL")
    config = spec.get("config") or {}
    refs = spec.get("data_refs") or {}
    interaction = spec.get("interaction") or {}
    for name, value in (("config", config), ("data_refs", refs), ("interaction", interaction)):
        if not isinstance(value, dict):
            errors.append(f"{name} must be an object")
    if isinstance(interaction, dict) and set(interaction) - INTERACTION_KEYS:
        errors.append(f"interaction keys must be within {sorted(INTERACTION_KEYS)}")
    if entry and isinstance(config, dict):
        extra = set(config) - entry["config"]
        if extra:
            errors.append(f"config keys {sorted(extra)} are not allowed for {widget_type}")
        if widget_type in ("GEOMETRY_DIAGRAM", "GEOMETRY_OVERLAY"):
            _geometry(config, errors)
        if widget_type == "FORMULA_CARD" and not (config.get("latex") or config.get("items")):
            errors.append("FORMULA_CARD needs latex or items")
        if widget_type == "TABLE" and not isinstance(config.get("rows", []), list):
            errors.append("TABLE rows must be a list")
        if widget_type == "BAR_CHART":
            bars = config.get("bars", [])
            if not isinstance(bars, list) or any(not isinstance(b, dict) or not _number(b.get("value")) for b in bars):
                errors.append("BAR_CHART bars need numeric value")
    if entry and isinstance(refs, dict):
        extra = set(refs) - entry["refs"]
        if extra:
            errors.append(f"data_refs {sorted(extra)} are not allowed for {widget_type}")
        if widget_type == "GEOMETRY_OVERLAY" and not refs.get("problem_image_id"):
            warnings.append("GEOMETRY_OVERLAY without problem_image_id renders the overlay alone")
        if ref_checker:
            for kind, value in refs.items():
                problem = ref_checker(kind, str(value))
                if problem:
                    errors.append(f"data_refs.{kind}: {problem}")
    if audience == "STUDENT" and isinstance(refs, dict) and refs.get("solution_hidden"):
        errors.append("solution-hidden content is not visible to students")
    normalized = None
    if not errors:
        normalized = {"widget_type": widget_type, "version": SPEC_VERSION, "title": spec.get("title") or entry["label"],
                      "data_refs": refs, "config": config, "interaction": interaction,
                      "persistence": spec.get("persistence", "SESSION"),
                      "source_lineage": spec.get("source_lineage") or {}}
    return {"valid": not errors, "errors": errors, "warnings": warnings, "normalized": normalized}


# ------------------------------------------------------------------ deterministic composer

def _line_circle(p: tuple[float, float], d: tuple[float, float], c: tuple[float, float], r: float):
    """Both intersections of the line p + t·d with the circle (c, r), ordered by distance from p."""
    fx, fy = p[0] - c[0], p[1] - c[1]
    a = d[0] ** 2 + d[1] ** 2
    b = 2 * (fx * d[0] + fy * d[1])
    cc = fx ** 2 + fy ** 2 - r ** 2
    disc = math.sqrt(max(b * b - 4 * a * cc, 0.0))
    ts = sorted(((-b - disc) / (2 * a), (-b + disc) / (2 * a)), key=abs)
    return [(round(p[0] + t * d[0], 2), round(p[1] + t * d[1], 2)) for t in ts]


def _pt(pid: str, xy: tuple[float, float], label: str | None = None) -> dict:
    return {"id": pid, "kind": "POINT", "x": xy[0], "y": xy[1], "label": label or pid}


def power_of_point_template() -> dict:
    """Two secants and a tangent from an external point P: PA·PB = PC·PD = PT² (computed coordinates)."""
    o, r, p = (42.0, 50.0), 26.0, (92.0, 62.0)
    a, b = _line_circle(p, (o[0] - p[0], o[1] - 4 - p[1]), o, r)
    c, d = _line_circle(p, (o[0] - p[0], o[1] - 30 - p[1]), o, r)
    dist = math.dist(p, o)
    angle = math.atan2(o[1] - p[1], o[0] - p[0]) + math.asin(r / dist)
    tangent_len = math.sqrt(dist ** 2 - r ** 2)
    t = (round(p[0] + tangent_len * math.cos(angle), 2), round(p[1] + tangent_len * math.sin(angle), 2))
    elements = [_pt("O", o), _pt("P", p), _pt("A", a), _pt("B", b), _pt("C", c), _pt("D", d), _pt("T", t),
                {"id": "circle", "kind": "CIRCLE", "center": "O", "radius": r},
                {"id": "PB", "kind": "SEGMENT", "from": "P", "to": "B"},
                {"id": "PD", "kind": "SEGMENT", "from": "P", "to": "D"},
                {"id": "PT", "kind": "SEGMENT", "from": "P", "to": "T"},
                {"id": "OT", "kind": "AUXILIARY_CONSTRUCTION", "from": "O", "to": "T"}]
    return {"widget_type": "GEOMETRY_DIAGRAM", "version": SPEC_VERSION, "title": "Power of a point",
            "data_refs": {}, "config": {"elements": elements, "view_box": [0, 0, 110, 100],
                                        "operations": [{"op": "HIGHLIGHT", "targets": ["PB", "PD"]},
                                                       {"op": "MARK_PERPENDICULAR", "targets": ["OT", "PT"]}],
                                        "caption": r"$PA \cdot PB = PC \cdot PD = PT^2$"},
            "interaction": {"selectable": True, "zoom": True}, "persistence": "SESSION",
            "source_lineage": {"template_id": "POWER_OF_POINT"}}


def intersecting_chords_template() -> dict:
    o, r, p = (50.0, 50.0), 34.0, (58.0, 44.0)
    a, b = _line_circle(p, (1.0, 0.35), o, r)
    c, d = _line_circle(p, (-0.3, 1.0), o, r)
    elements = [_pt("O", o), _pt("P", p), _pt("A", a), _pt("B", b), _pt("C", c), _pt("D", d),
                {"id": "circle", "kind": "CIRCLE", "center": "O", "radius": r},
                {"id": "AB", "kind": "SEGMENT", "from": "A", "to": "B"},
                {"id": "CD", "kind": "SEGMENT", "from": "C", "to": "D"}]
    return {"widget_type": "GEOMETRY_DIAGRAM", "version": SPEC_VERSION, "title": "Intersecting chords",
            "data_refs": {}, "config": {"elements": elements, "view_box": [0, 0, 100, 100],
                                        "operations": [{"op": "HIGHLIGHT", "targets": ["AB", "CD"]}],
                                        "caption": r"$PA \cdot PB = PC \cdot PD$"},
            "interaction": {"selectable": True, "zoom": True}, "persistence": "SESSION",
            "source_lineage": {"template_id": "INTERSECTING_CHORDS"}}


def triangle_template() -> dict:
    a, b, c = (15.0, 85.0), (90.0, 85.0), (40.0, 18.0)
    elements = [_pt("A", a), _pt("B", b), _pt("C", c),
                {"id": "ABC", "kind": "POLYGON", "points": ["A", "B", "C"]},
                {"id": "angA", "kind": "ANGLE", "vertex": "A", "from": "B", "to": "C"}]
    return {"widget_type": "GEOMETRY_DIAGRAM", "version": SPEC_VERSION, "title": "Triangle ABC",
            "data_refs": {}, "config": {"elements": elements, "view_box": [0, 0, 100, 100], "operations": [],
                                        "caption": r"$\triangle ABC$"},
            "interaction": {"selectable": True, "zoom": True}, "persistence": "SESSION",
            "source_lineage": {"template_id": "TRIANGLE"}}


TEMPLATES = {"POWER_OF_POINT": power_of_point_template, "INTERSECTING_CHORDS": intersecting_chords_template,
             "TRIANGLE": triangle_template}


def poll_result_spec(prompt: str, aggregate: dict, correct_option: str | None, instance_id: str) -> dict:
    return {"widget_type": "POLL_RESULT", "version": SPEC_VERSION, "title": "Class responses",
            "data_refs": {"activity_instance_id": instance_id},
            "config": {"prompt": prompt, "options": list(aggregate.get("option_counts", {})),
                       "counts": aggregate.get("option_counts", {}),
                       "percentages": aggregate.get("option_percentages", {}),
                       "response_count": aggregate.get("response_count", 0),
                       "correct_option": correct_option, "reveal": correct_option is not None},
            "interaction": {}, "persistence": "SESSION", "source_lineage": {"activity_instance_id": instance_id}}


def compose(intent: str, context: dict | None = None) -> dict:
    """FAST-path deterministic widget composition (fluid 10/20, dist 12). Never calls a model.

    Priority (dist 11): existing problem diagram (+overlay) → deterministic template → chart/table →
    fallback formula card. Returns ``{spec, strategy}``.
    """
    context = context or {}
    text_ = (intent or "").lower()
    if context.get("aggregate") is not None:
        return {"strategy": "POLL_AGGREGATE",
                "spec": poll_result_spec(context.get("prompt", ""), context["aggregate"],
                                         context.get("correct_option"), context.get("activity_instance_id", ""))}
    if re.search(r"power of (a |the )?point|secant|tangent", text_):
        return {"strategy": "TEMPLATE", "spec": power_of_point_template()}
    if re.search(r"chord", text_):
        return {"strategy": "TEMPLATE", "spec": intersecting_chords_template()}
    if context.get("steps") and re.search(r"progress|steps?|where am i|roadmap", text_):
        steps = [{"label": s.get("label"), "status": s.get("status", "PENDING")} for s in context["steps"]]
        return {"strategy": "STEP_PROGRESS",
                "spec": {"widget_type": "STEP_PROGRESS", "version": SPEC_VERSION, "title": "Solution progress",
                         "data_refs": {"problem_id": context["problem_id"]} if context.get("problem_id") else {},
                         "config": {"steps": steps, "current": context.get("current", 0)},
                         "interaction": {}, "persistence": "SESSION", "source_lineage": {"intent": intent}}}
    if context.get("problem_image_id"):
        return {"strategy": "EXISTING_DIAGRAM",
                "spec": {"widget_type": "GEOMETRY_OVERLAY", "version": SPEC_VERSION,
                         "title": context.get("title") or "Problem diagram",
                         "data_refs": {"problem_image_id": context["problem_image_id"],
                                       **({"problem_id": context["problem_id"]} if context.get("problem_id") else {})},
                         "config": {"elements": [], "operations": [], "caption": context.get("caption") or ""},
                         "interaction": {"zoom": True}, "persistence": "SESSION",
                         "source_lineage": {"intent": intent, "problem_image_id": context["problem_image_id"]}}}
    if re.search(r"triangle", text_):
        return {"strategy": "TEMPLATE", "spec": triangle_template()}
    if context.get("rows") and context.get("columns"):
        return {"strategy": "TABLE",
                "spec": {"widget_type": "TABLE", "version": SPEC_VERSION, "title": context.get("title") or "Table",
                         "data_refs": {}, "config": {"columns": context["columns"], "rows": context["rows"]},
                         "interaction": {}, "persistence": "SESSION", "source_lineage": {"intent": intent}}}
    latex = context.get("latex") or ""
    return {"strategy": "FALLBACK_FORMULA",
            "spec": {"widget_type": "FORMULA_CARD", "version": SPEC_VERSION, "title": context.get("title") or "Key idea",
                     "data_refs": {}, "config": {"latex": latex or intent or "No visual available",
                                                 "caption": "" if latex else "Fallback card — no matching visual"},
                     "interaction": {}, "persistence": "EPHEMERAL", "source_lineage": {"intent": intent}}}
