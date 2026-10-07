"""Declarative subject artifacts, private objects, immutable lineage and explicit indexing.

Generation and validation are deterministic and offline. Embeddings are accepted only through
explicit indexing/semantic commands. Provider, model and verified dimensions are configured;
retrieval never silently calls a provider or substitutes lexical results for semantic results.
"""
from __future__ import annotations

import json
import math
import os
import re
import xml.etree.ElementTree as ET
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4, uuid5

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator
from sqlalchemy import text

from mathbank_rest import object_store

VERSION = "declarative-artifacts-v1"
EMBEDDING_MODEL: Literal["text-embedding-3-small"] = "text-embedding-3-small"
Subject = Literal["GEOMETRY", "ALGEBRA", "COMBINATORICS", "NUMBER_THEORY"]
Short = Annotated[str, Field(min_length=1, max_length=200)]
Text = Annotated[str, Field(max_length=2000)]
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")]
Coordinate = Annotated[float, Field(ge=0, le=2000, allow_inf_nan=False)]
Tags = Annotated[list[Short], Field(max_length=64)]


class Domain(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Point(Domain):
    kind: Literal["POINT"]
    id: Identifier
    x: Coordinate
    y: Coordinate
    label: Short
    contact: bool = False


class Segment(Domain):
    kind: Literal["SEGMENT", "EDGE"]
    id: Identifier
    start: Identifier
    end: Identifier
    auxiliary: bool = False


class Circle(Domain):
    kind: Literal["CIRCLE"]
    id: Identifier
    cx: Coordinate
    cy: Coordinate
    radius: Annotated[float, Field(gt=0, le=900, allow_inf_nan=False)]


class Angle(Domain):
    kind: Literal["ANGLE"]
    id: Identifier
    vertex: Identifier
    start_degrees: Annotated[float, Field(ge=0, le=360, allow_inf_nan=False)]
    end_degrees: Annotated[float, Field(ge=0, le=360, allow_inf_nan=False)]
    radius: Annotated[float, Field(ge=8, le=80, allow_inf_nan=False)] = 20
    label: Short


class Node(Domain):
    kind: Literal["NODE"]
    id: Identifier
    x: Coordinate
    y: Coordinate
    label: Short
    prime: bool = False


class Cell(Domain):
    kind: Literal["CELL"]
    id: Identifier
    row: Annotated[int, Field(ge=0, le=20)]
    column: Annotated[int, Field(ge=0, le=10)]
    label: Short


class Term(Domain):
    id: Identifier
    latex: Annotated[str, Field(min_length=1, max_length=1000)]


class Equation(Domain):
    kind: Literal["EQUATION"]
    id: Identifier
    latex: Annotated[str, Field(min_length=1, max_length=1000)]
    reason: Short
    linked_step_id: Short | None = None
    terms: Annotated[list[Term], Field(max_length=32)] = Field(default_factory=list)


Element = Annotated[Point | Segment | Circle | Angle | Node | Cell | Equation,
                    Field(discriminator="kind")]
ActionName = Literal[
    "HIGHLIGHT", "DIM", "SHOW", "HIDE", "LABEL", "RELABEL", "MARK_EQUAL",
    "MARK_PARALLEL", "MARK_PERPENDICULAR", "SHOW_RATIO", "FOCUS_REGION",
    "EMPHASIZE_EQUATION_LINE", "EMPHASIZE_TERM",
]


class Action(Domain):
    action: ActionName
    targets: Annotated[list[Identifier], Field(min_length=1, max_length=16)]
    label: Short | None = None
    latex: Annotated[str, Field(max_length=1000)] | None = None
    region: Annotated[list[Coordinate], Field(min_length=4, max_length=4)] | None = None

    @model_validator(mode="after")
    def payload(self):
        if self.action in ("LABEL", "RELABEL") and not self.label:
            raise ValueError("label actions require label")
        if self.action == "SHOW_RATIO" and not self.latex:
            raise ValueError("SHOW_RATIO requires latex")
        if self.action == "FOCUS_REGION" and self.region is None:
            raise ValueError("FOCUS_REGION requires [x, y, width, height]")
        return self


class Overlay(Domain):
    id: Identifier
    caption: Short
    linked_step_id: Short | None = None
    explanation_text: Text = ""
    concept_tag: Short = "instruction"
    hint_tag: Short | None = None
    actions: Annotated[list[Action], Field(min_length=1, max_length=16)]


class Frame(Domain):
    overlay_id: Identifier
    duration_ms: Annotated[int, Field(ge=100, le=30000)] = 1000
    transition: Literal["NONE", "FADE", "HIGHLIGHT"] = "NONE"


class ArtifactPlan(Domain):
    subject: Subject
    topic: Short
    subtopic: Short | None = None
    title: Short
    summary: Text = ""
    difficulty_band: Short = "UNSPECIFIED"
    grade_band: Short = "UNSPECIFIED"
    goal_type: Short = "DEMONSTRATE"
    request_source: Short = "AUTHORING"
    linked_problem_id: UUID | None = None
    linked_solution_step_id: Short | None = None
    parent_bundle_id: UUID | None = None
    concept_ids: Tags = Field(default_factory=list)
    skill_ids: Tags = Field(default_factory=list)
    theorem_ids: Tags = Field(default_factory=list)
    width: Annotated[int, Field(ge=240, le=2000)] = 800
    height: Annotated[int, Field(ge=240, le=2000)] = 600
    elements: Annotated[list[Element], Field(min_length=1, max_length=128)]
    overlays: Annotated[list[Overlay], Field(max_length=64)] = Field(default_factory=list)
    frames: Annotated[list[Frame], Field(max_length=128)] = Field(default_factory=list)
    modulus: Annotated[int, Field(ge=2, le=1000000)] | None = None
    number_theory_mode: Literal["MODULAR", "FACTOR_TREE", "EUCLIDEAN", "DIVISIBILITY"] | None = None


class GenerateBody(Domain):
    publish: bool = False


Vector = Annotated[list[Annotated[float, Field(ge=-1000000, le=1000000, allow_inf_nan=False)]],
                   Field(min_length=1, max_length=8192)]


class IndexBody(Domain):
    embedding: Vector | None = None
    generate_embedding: bool = False
    model: Short = EMBEDDING_MODEL
    dimensions: Annotated[int, Field(ge=1, le=8192)] = 1536
    search_text_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

    @model_validator(mode="after")
    def nonzero(self):
        if (self.embedding is None) == (not self.generate_embedding):
            raise ValueError("supply embedding or explicitly set generate_embedding=true, not both")
        if self.embedding is not None and not any(abs(v) >= 1e-12 for v in self.embedding):
            raise ValueError("embedding norm is too small for pgvector cosine distance")
        if self.embedding is not None and len(self.embedding) != self.dimensions:
            raise ValueError("embedding length differs from declared dimensions")
        return self


class SearchBody(Domain):
    query: Annotated[str, Field(max_length=2000)] = ""
    subject: Subject | None = None
    concept_id: Short | None = None
    skill_id: Short | None = None
    theorem_id: Short | None = None
    difficulty_band: Short | None = None
    asset_type: Literal["SVG_DIAGRAM", "LATEX_CARD", "FRAME_SEQUENCE", "MANIM_EXPORT_SPEC"] | None = None
    limit: Annotated[int, Field(ge=1, le=100)] = 20
    offset: Annotated[int, Field(ge=0, le=100000)] = 0
    query_embedding: Vector | None = None
    generate_embedding: bool = False
    model: Short = EMBEDDING_MODEL
    dimensions: Annotated[int, Field(ge=1, le=8192)] = 1536

    @model_validator(mode="after")
    def nonzero(self):
        if self.generate_embedding and (not self.query.strip() or self.query_embedding is not None):
            raise ValueError("embedding generation requires query text and no supplied query_embedding")
        if self.query_embedding is not None and not any(abs(v) >= 1e-12 for v in self.query_embedding):
            raise ValueError("query embedding norm is too small for pgvector cosine distance")
        if self.query_embedding is not None and len(self.query_embedding) != self.dimensions:
            raise ValueError("query embedding length differs from declared dimensions")
        return self


class ArtifactError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code, self.status_code = code, status_code


def embedding_profile() -> dict:
    values = dotenv_values(Path(__file__).resolve().parents[3] / ".env", interpolate=False)
    def setting(name, default=""):
        return os.environ.get(name, values.get(name) or default)
    provider = setting("ARTIFACT_EMBEDDING_PROVIDER", "direct_openai")
    model = setting("ARTIFACT_EMBEDDING_MODEL", EMBEDDING_MODEL if provider == "direct_openai" else "")
    dimensions = setting("ARTIFACT_EMBEDDING_DIMENSIONS", "1536" if provider == "direct_openai" else "")
    if provider not in ("direct_openai", "gateway") or not model or not str(dimensions).isdecimal():
        raise ArtifactError("EMBEDDING_CONFIGURATION_UNAVAILABLE",
                            "configure artifact embedding provider, model and verified dimensions", 503)
    dimension = int(dimensions)
    if not 1 <= dimension <= 8192 or len(model) > 200:
        raise ArtifactError("EMBEDDING_CONFIGURATION_UNAVAILABLE", "invalid embedding model/dimensions", 503)
    return {"provider": provider, "model": model, "dimensions": dimension}


def _openai_embedding(source: str) -> list[float]:
    profile = embedding_profile()
    if profile["provider"] == "gateway":
        from mathbank_rest.runtime_ai import gateway_client
        api = gateway_client()
    else:
        from mathbank_rest.runtime_ai import speech_client
        api = speech_client()

    kwargs = {"model": profile["model"], "input": [source]}
    if profile["provider"] == "direct_openai" and profile["model"].startswith("text-embedding-3-"):
        kwargs["dimensions"] = profile["dimensions"]
    response = api.embeddings.create(**kwargs)
    return response.data[0].embedding


EMBEDDER = _openai_embedding


def _embed(source: str, profile: dict) -> list[float]:
    # Byte bounds conservatively cap input tokens, without silently dropping instructional text.
    if len(source.encode()) > 8000:
        raise ArtifactError("EMBEDDING_SOURCE_TOO_LARGE",
                            "explicit provider indexing supports at most 8000 UTF-8 bytes; supply a vector for larger sources")
    try:
        values = TypeAdapter(Vector).validate_python(EMBEDDER(source))
        if len(values) != profile["dimensions"]:
            raise ValueError("provider vector dimension mismatch")
        if not any(abs(v) >= 1e-12 for v in values):
            raise ValueError("zero vector")
        return values
    except Exception:  # noqa: BLE001 -- provider failures must not expose credentials or become lexical results
        raise ArtifactError("EMBEDDING_UNAVAILABLE", "explicit embedding provider unavailable", 503) from None


_LATEX_COMMANDS = frozenset({
    "frac", "dfrac", "tfrac", "sqrt", "cdot", "times", "div", "pm", "mp", "le", "leq",
    "ge", "geq", "ne", "neq", "approx", "equiv", "cong", "sim", "simeq", "propto",
    "in", "notin", "subset", "subseteq", "supset", "supseteq", "cup", "cap", "forall",
    "exists", "neg", "land", "lor", "mid", "nmid", "sum", "prod", "int", "lim", "sin",
    "cos", "tan", "log", "ln", "exp", "min", "max", "gcd", "lcm", "mod", "bmod", "pmod",
    "alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "theta", "lambda", "mu",
    "pi", "rho", "sigma", "tau", "phi", "varphi", "omega", "Gamma", "Delta", "Theta",
    "Lambda", "Pi", "Sigma", "Phi", "Omega", "ell", "angle", "triangle", "parallel",
    "perp", "infty", "rightarrow", "leftarrow", "leftrightarrow", "implies", "iff",
    "to", "mapsto", "text", "mathrm", "mathbf", "mathit", "mathbb", "mathcal", "mathsf",
    "operatorname", "overline", "underline", "hat", "bar", "vec", "left", "right",
    "big", "Big", "bigg", "Bigg", "quad", "qquad", "displaystyle", "cdots", "ldots",
    "vdots", "ddots", "begin", "end", "binom", "boxed", "overset", "underset",
    "overbrace", "underbrace",
})


def latex_errors(value: str) -> list[str]:
    errors = []
    if any(ord(c) < 32 and c not in "\n\t" for c in value) or any(c in value for c in "<>%$"):
        errors.append("LaTeX contains forbidden characters")
    for command in re.findall(r"\\([A-Za-z]+|.)", value):
        if command not in _LATEX_COMMANDS and command not in ("\\", "{", "}", ",", ";", "!", " "):
            errors.append(f"unsupported LaTeX command: {command}")
    stack = []
    for match in re.finditer(r"(?<!\\)[{}]", value):
        if match.group() == "{":
            stack.append("{")
        elif stack:
            stack.pop()
        else:
            errors.append("unbalanced LaTeX braces")
    if stack:
        errors.append("unbalanced LaTeX braces")
    environments = re.findall(r"\\(begin|end)\{([^}]+)\}", value)
    env_stack = []
    for op, name in environments:
        if name not in ("aligned", "gathered", "cases", "matrix", "pmatrix", "bmatrix"):
            errors.append(f"unsupported LaTeX environment: {name}")
        if op == "begin":
            env_stack.append(name)
        elif not env_stack or env_stack.pop() != name:
            errors.append("unbalanced LaTeX environment")
    if env_stack:
        errors.append("unbalanced LaTeX environment")
    return errors


_SVG_TAGS = {"svg", "g", "circle", "line", "path", "rect", "text", "tspan"}
_SVG_ATTRS = {"xmlns", "id", "viewBox", "width", "height", "x", "y", "x1", "x2", "y1",
              "y2", "cx", "cy", "r", "rx", "d", "fill", "stroke", "stroke-width",
              "stroke-dasharray", "font-size", "font-family", "text-anchor", "opacity"}


def svg_errors(data: bytes) -> list[str]:
    if len(data) > 512000:
        return ["SVG exceeds 512000 bytes"]
    if b"<!" in data or b"<?" in data:
        return ["SVG declarations/entities are forbidden"]
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return ["invalid SVG XML"]
    errors, ids = [], set()
    if root.tag not in ("svg", "{http://www.w3.org/2000/svg}svg"):
        errors.append("SVG root required")
    for node in root.iter():
        tag = node.tag.removeprefix("{http://www.w3.org/2000/svg}")
        if tag not in _SVG_TAGS:
            errors.append(f"unsafe SVG element: {tag}")
        for attr, val in node.attrib.items():
            if attr not in _SVG_ATTRS or re.search(r"url\s*\(|(?:https?|data|javascript):", val, re.IGNORECASE):
                errors.append(f"unsafe SVG attribute: {attr}")
            if attr in ("fill", "stroke") and not re.fullmatch(r"none|#[0-9A-Fa-f]{3,8}", val):
                errors.append(f"unsafe SVG paint: {attr}")
            if attr in {"width", "height", "x", "y", "x1", "x2", "y1", "y2", "cx", "cy",
                        "r", "rx", "stroke-width", "font-size", "opacity"} and (
                not re.fullmatch(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", val)
            ):
                errors.append(f"invalid numeric SVG attribute: {attr}")
        if "id" in node.attrib:
            identifier = node.attrib["id"]
            if identifier in ids or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", identifier):
                errors.append("duplicate or invalid SVG id")
            ids.add(identifier)
    return errors


def _geometry_labels(plan: ArtifactPlan) -> tuple[dict[str, tuple[float, float]], list[str]]:
    """Place short labels clear of structural segments, vertices and circle outlines."""
    points = {e.id: e for e in plan.elements if isinstance(e, Point)}
    segments = [(points[e.start], points[e.end]) for e in plan.elements
                if isinstance(e, Segment) and e.start in points and e.end in points]
    circles = [e for e in plan.elements if isinstance(e, Circle)]
    occupied: list[tuple[float, float, float, float]] = []
    positions, errors = {}, []

    def intersects_segment(box, a, b):
        low, high = 0.0, 1.0
        for start, delta, minimum, maximum in (
            (a.x, b.x - a.x, box[0] - 3, box[2] + 3),
            (a.y, b.y - a.y, box[1] - 3, box[3] + 3),
        ):
            if delta == 0:
                if not minimum <= start <= maximum:
                    return False
            else:
                first, last = sorted(((minimum - start) / delta, (maximum - start) / delta))
                low, high = max(low, first), min(high, last)
                if low > high:
                    return False
        return True

    def clear(box):
        left, top, right, bottom = box
        if left < 5 or top < 5 or right > plan.width - 5 or bottom > plan.height - 5:
            return False
        if any(not (right + 4 < a or left - 4 > c or bottom + 4 < b or top - 4 > d)
               for a, b, c, d in occupied):
            return False
        if any(intersects_segment(box, a, b) for a, b in segments):
            return False
        if any(math.hypot(p.x - max(left, min(p.x, right)),
                          p.y - max(top, min(p.y, bottom))) < 8 for p in points.values()):
            return False
        for circle in circles:
            minimum = math.hypot(circle.cx - max(left, min(circle.cx, right)),
                                 circle.cy - max(top, min(circle.cy, bottom)))
            maximum = max(math.hypot(circle.cx - x, circle.cy - y)
                          for x in (left, right) for y in (top, bottom))
            if minimum <= circle.radius + 3 and maximum >= circle.radius - 3:
                return False
        return True

    for e in plan.elements:
        if isinstance(e, Point):
            width = len(e.label) * 9
            candidates = [(e.x + 9, e.y - 9), (e.x + 9, e.y + 24),
                          (e.x - width - 9, e.y - 9), (e.x - width - 9, e.y + 24),
                          (e.x - width / 2, e.y - 18), (e.x - width / 2, e.y + 32)]
        elif isinstance(e, Angle) and e.vertex in points:
            width = len(e.label) * 9
            point = points[e.vertex]
            start, end = math.radians(e.start_degrees), math.radians(e.end_degrees)
            extent = (end - start) % (2 * math.pi)
            middle = start + extent / 2
            candidates = [(point.x + (e.radius + d) * math.cos(middle + offset) - width / 2,
                           point.y + (e.radius + d) * math.sin(middle + offset) + 5)
                          for offset in (0, -extent / 6, extent / 6, -extent / 3, extent / 3)
                          for d in (22, 40, 58, 76)]
        else:
            continue
        for x, y in candidates:
            box = (x, y - 16, x + width, y + 2)
            if clear(box):
                positions[e.id] = (x, y)
                occupied.append(box)
                break
        else:
            errors.append(f"{e.id}: label collides with structural content; adjust the layout")
    return positions, errors


def _segment_geometry(plan: ArtifactPlan, segment: Segment) -> tuple[float, float, float, float]:
    elements = {e.id: e for e in plan.elements}
    start, end = elements[segment.start], elements[segment.end]
    return start.x, start.y, end.x - start.x, end.y - start.y


def validate_plan(plan: ArtifactPlan) -> dict:
    errors: list[str] = []
    elements = {e.id: e for e in plan.elements}
    if len(elements) != len(plan.elements):
        errors.append("element IDs must be unique")
    reserved = {"base_layer", "annotation_layer", "overlay_layer", "interaction_layer", "modulus_context"}
    if reserved.intersection(elements) or any(e.id.startswith(("label_", "step_")) for e in plan.elements):
        errors.append("element ID uses a reserved layer/annotation identifier")
    allowed = {
        "GEOMETRY": {"POINT", "SEGMENT", "CIRCLE", "ANGLE", "EQUATION"},
        "ALGEBRA": {"EQUATION"},
        "COMBINATORICS": {"NODE", "EDGE", "CELL", "EQUATION"},
        "NUMBER_THEORY": {"POINT", "SEGMENT", "NODE", "EDGE", "CELL", "EQUATION"},
    }[plan.subject]
    for e in plan.elements:
        if e.kind not in allowed:
            errors.append(f"{e.kind} is unsupported for {plan.subject}")
        if isinstance(e, Segment):
            if not all(isinstance(elements.get(ref), (Point, Node)) for ref in (e.start, e.end)):
                errors.append(f"{e.id}: segment/edge endpoints must reference points/nodes")
            if e.start == e.end:
                errors.append(f"{e.id}: endpoints must be distinct")
            if isinstance(elements.get(e.start), (Point, Node)) and isinstance(elements.get(e.end), (Point, Node)):
                _, _, dx, dy = _segment_geometry(plan, e)
                if math.hypot(dx, dy) < 1:
                    errors.append(f"{e.id}: segment endpoints coincide")
        if isinstance(e, Angle):
            if not isinstance(elements.get(e.vertex), Point):
                errors.append(f"{e.id}: angle vertex must reference a point")
            if e.start_degrees == e.end_degrees:
                errors.append(f"{e.id}: angle must have nonzero extent")
        if isinstance(e, (Point, Node)):
            if not 20 <= e.x <= plan.width - 50 or not 30 <= e.y <= plan.height - 40:
                errors.append(f"{e.id}: point/node and label need canvas margin")
            if isinstance(e, Node) and len(e.label) > 16:
                errors.append(f"{e.id}: node label exceeds readable layout")
            if isinstance(e, Point) and len(e.label) > 8:
                errors.append(f"{e.id}: point label exceeds readable layout")
        if isinstance(e, Circle) and (min(e.cx - e.radius, e.cy - e.radius) < 10 or (
                e.cx + e.radius > plan.width - 10 or e.cy + e.radius > plan.height - 10
            )):
            errors.append(f"{e.id}: circle exceeds canvas")
        if isinstance(e, Equation):
            errors.extend(f"{e.id}: {message}" for message in latex_errors(e.latex))
            if e.terms and "".join(t.latex for t in e.terms) != e.latex:
                errors.append(f"{e.id}: term fragments must reproduce the equation exactly")
            for term in e.terms:
                if term.id in elements or term.id in reserved or term.id.startswith(("label_", "step_")):
                    errors.append(f"{term.id}: duplicate/reserved term ID")
                elements[term.id] = term
                errors.extend(latex_errors(term.latex))
        if isinstance(e, Cell) and (40 + (e.column + 1) * 120 > plan.width or
                                   60 + (e.row + 1) * 45 > plan.height):
            errors.append(f"{e.id}: cell exceeds canvas")
        if isinstance(e, Cell) and len(e.label) > 12:
            errors.append(f"{e.id}: cell label exceeds readable layout")
    points = [e for e in plan.elements if isinstance(e, (Point, Node))]
    for i, a in enumerate(points):
        for b in points[i + 1:]:
            if math.hypot(a.x - b.x, a.y - b.y) < (60 if isinstance(a, Node) else 35):
                errors.append(f"labels/points too close: {a.id}, {b.id}")
    cells = [(e.row, e.column) for e in plan.elements if isinstance(e, Cell)]
    if len(cells) != len(set(cells)):
        errors.append("table cells must have distinct row/column positions")
    equations = [e for e in plan.elements if isinstance(e, Equation)]
    if equations and 80 + len(equations) * 48 > plan.height:
        errors.append("equation stack exceeds canvas; split into bundles")
    if plan.subject == "GEOMETRY" and not any(isinstance(e, Point) for e in plan.elements):
        errors.append("geometry requires explicit labelled vertices/contact points")
    if plan.subject == "GEOMETRY":
        errors.extend(_geometry_labels(plan)[1])
    if plan.subject == "COMBINATORICS" and not any(isinstance(e, (Node, Cell)) for e in plan.elements):
        errors.append("combinatorics requires labelled cases/nodes/cells")
    if plan.subject == "NUMBER_THEORY":
        if plan.number_theory_mode is None:
            errors.append("number theory requires number_theory_mode")
        if plan.number_theory_mode == "MODULAR" and plan.modulus is None:
            errors.append("modular artifacts require explicit modulus")
        if plan.number_theory_mode == "MODULAR" and plan.modulus is not None:
            for e in equations:
                if any(int(m) != plan.modulus for m in re.findall(r"\\pmod\{(\d+)\}", e.latex)):
                    errors.append(f"{e.id}: congruence modulus differs from declared context")
        if plan.number_theory_mode == "FACTOR_TREE":
            if not any(isinstance(e, Node) for e in plan.elements) or not any(
                e.kind == "EDGE" for e in plan.elements
            ):
                errors.append("factor trees require nodes and edges")
            for e in plan.elements:
                if isinstance(e, Node) and e.prime:
                    if not e.label.isdecimal() or not 2 <= int(e.label) <= 1000000:
                        errors.append(f"{e.id}: prime nodes require an integer from 2 to 1000000")
                    elif any(int(e.label) % d == 0 for d in range(2, math.isqrt(int(e.label)) + 1)):
                        errors.append(f"{e.id}: declared prime is composite")
        if plan.number_theory_mode == "EUCLIDEAN" and not equations:
            errors.append("Euclidean artifacts require equation steps with quotient/remainder context")
    elif plan.modulus is not None or plan.number_theory_mode is not None:
        errors.append("number theory context is unsupported for this subject")
    overlay_ids = {o.id for o in plan.overlays}
    if len(overlay_ids) != len(plan.overlays):
        errors.append("overlay IDs must be unique")
    for o in plan.overlays:
        if len(o.caption) * 8 > plan.width - 50:
            errors.append(f"{o.id}: caption exceeds readable canvas width")
        if len(o.actions) > 8:
            errors.append(f"{o.id}: too many simultaneous changes; split the overlay")
        for a in o.actions:
            if not set(a.targets).issubset(elements):
                errors.append(f"{o.id}: unknown overlay targets")
            if a.action == "EMPHASIZE_EQUATION_LINE" and not all(
                isinstance(elements.get(t), Equation) for t in a.targets
            ):
                errors.append(f"{o.id}: equation emphasis must target equations")
            if a.action == "EMPHASIZE_TERM" and not all(
                isinstance(elements.get(t), Term) for t in a.targets
            ):
                errors.append(f"{o.id}: term emphasis must target declared equation terms")
            if a.action in ("MARK_PARALLEL", "MARK_PERPENDICULAR") and (
                len(set(a.targets)) != 2 or not all(isinstance(elements.get(t), Segment) for t in a.targets)
            ):
                errors.append(f"{o.id}: parallel/perpendicular marks require two distinct segments")
            elif a.action in ("MARK_PARALLEL", "MARK_PERPENDICULAR"):
                first, second = (elements[t] for t in a.targets)
                if all(isinstance(elements.get(ref), (Point, Node))
                       for segment in (first, second) for ref in (segment.start, segment.end)):
                    x1, y1, dx1, dy1 = _segment_geometry(plan, first)
                    x2, y2, dx2, dy2 = _segment_geometry(plan, second)
                    scale = math.hypot(dx1, dy1) * math.hypot(dx2, dy2)
                    if scale > 0:
                        if a.action == "MARK_PARALLEL" and abs(dx1 * dy2 - dy1 * dx2) > scale * 1e-6:
                            errors.append(f"{o.id}: parallel marker contradicts segment geometry")
                        if a.action == "MARK_PERPENDICULAR":
                            if abs(dx1 * dx2 + dy1 * dy2) > scale * 1e-6:
                                errors.append(f"{o.id}: perpendicular marker contradicts segment geometry")
                            else:
                                determinant = dx1 * dy2 - dy1 * dx2
                                t = ((x2 - x1) * dy2 - (y2 - y1) * dx2) / determinant
                                u = ((x2 - x1) * dy1 - (y2 - y1) * dx1) / determinant
                                if not (0 <= t <= 1 and 0 <= u <= 1):
                                    errors.append(f"{o.id}: perpendicular segments must intersect on the canvas")
            if a.action == "MARK_EQUAL" and (
                len(set(a.targets)) < 2 or not all(isinstance(elements.get(t), (Segment, Angle)) for t in a.targets)
                or len({type(elements.get(t)) for t in a.targets}) != 1
            ):
                errors.append(f"{o.id}: equality marks require distinct segments or distinct angles")
            if a.latex:
                errors.extend(latex_errors(a.latex))
            if a.region and (a.region[2] <= 0 or a.region[3] <= 0 or
                             a.region[0] + a.region[2] > plan.width or
                             a.region[1] + a.region[3] > plan.height):
                errors.append(f"{o.id}: focus region exceeds canvas")
        if {e.id for e in plan.elements}.issubset(
            {t for a in o.actions if a.action == "HIDE" for t in a.targets}
        ):
            errors.append(f"{o.id}: overlay hides all instructional elements")
    for frame in plan.frames:
        if frame.overlay_id not in overlay_ids:
            errors.append("frame references unknown overlay")
    return {"valid": not errors, "errors": errors, "warnings": [],
            "validator_version": VERSION, "checks": ["STRUCTURAL", "SAFETY", "LAYOUT", "SUBJECT_RULES"]}


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _svg(plan: ArtifactPlan) -> bytes:
    root = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg",
                             "viewBox": f"0 0 {plan.width} {plan.height}",
                             "width": str(plan.width), "height": str(plan.height)})
    base = ET.SubElement(root, "g", {"id": "base_layer"})
    annotation = ET.SubElement(root, "g", {"id": "annotation_layer",
                                         "font-family": "sans-serif", "font-size": "16"})
    ET.SubElement(root, "g", {"id": "overlay_layer"})
    ET.SubElement(root, "g", {"id": "interaction_layer"})
    mapping = {e.id: e for e in plan.elements}
    label_positions = _geometry_labels(plan)[0] if plan.subject == "GEOMETRY" else {}

    def label(identifier, x, y, value):
        ET.SubElement(annotation, "text", {"id": identifier, "x": str(x), "y": str(y)}).text = value

    equation_ordinal = 0
    for e in plan.elements:
        group = ET.SubElement(base, "g", {"id": e.id})
        if isinstance(e, (Point, Node)):
            node = isinstance(e, Node)
            ET.SubElement(group, "circle", {"cx": str(e.x), "cy": str(e.y),
                                          "r": "22" if node else ("5" if e.contact else "3"),
                                          "fill": "#e0f2fe" if node else "#0f172a",
                                          "stroke": "#0284c7" if node and e.prime else "#334155",
                                          "stroke-width": "2"})
            if node:
                ET.SubElement(group, "text", {"x": str(e.x), "y": str(e.y + 5),
                                             "text-anchor": "middle", "font-size": "14"}).text = e.label
            else:
                x, y = label_positions.get(e.id, (e.x + 9, e.y - 9))
                label("label_" + e.id, x, y, e.label)
        elif isinstance(e, Segment):
            a, b = mapping[e.start], mapping[e.end]
            attrs = {"x1": str(a.x), "y1": str(a.y), "x2": str(b.x), "y2": str(b.y),
                     "stroke": "#334155", "stroke-width": "2"}
            if e.auxiliary:
                attrs["stroke-dasharray"] = "6 5"
            ET.SubElement(group, "line", attrs)
        elif isinstance(e, Circle):
            ET.SubElement(group, "circle", {"cx": str(e.cx), "cy": str(e.cy), "r": str(e.radius),
                                          "fill": "none", "stroke": "#94a3b8", "stroke-width": "1"})
        elif isinstance(e, Angle):
            point = mapping[e.vertex]
            start, end = math.radians(e.start_degrees), math.radians(e.end_degrees)
            x1, y1 = point.x + e.radius * math.cos(start), point.y + e.radius * math.sin(start)
            x2, y2 = point.x + e.radius * math.cos(end), point.y + e.radius * math.sin(end)
            large = int((e.end_degrees - e.start_degrees) % 360 > 180)
            ET.SubElement(group, "path", {"d": f"M{x1},{y1} A{e.radius},{e.radius} 0 {large} 1 {x2},{y2}",
                                        "fill": "none", "stroke": "#0284c7", "stroke-width": "1"})
            middle = start + ((end - start) % (2 * math.pi)) / 2
            x, y = label_positions.get(e.id, (
                point.x + (e.radius + 16) * math.cos(middle),
                point.y + (e.radius + 16) * math.sin(middle)))
            label("label_" + e.id, x, y, e.label)
        elif isinstance(e, Cell):
            x, y = 40 + e.column * 120, 60 + e.row * 45
            ET.SubElement(group, "rect", {"x": str(x), "y": str(y), "width": "120", "height": "45",
                                        "fill": "#f8fafc", "stroke": "#94a3b8"})
            ET.SubElement(group, "text", {"x": str(x + 10), "y": str(y + 28),
                                         "font-size": "14"}).text = e.label
        elif isinstance(e, Equation):
            equation_ordinal += 1
            equation_text = ET.SubElement(group, "text", {
                "x": "70", "y": str(80 + equation_ordinal * 48), "font-size": "18"})
            if e.terms:
                for term in e.terms:
                    ET.SubElement(equation_text, "tspan", {"id": term.id}).text = term.latex
            else:
                equation_text.text = e.latex
            label(f"step_{equation_ordinal}", 30, 80 + equation_ordinal * 48,
                  str(equation_ordinal))
    if plan.modulus:
        label("modulus_context", 30, 30, f"Modulus: {plan.modulus}")
    return ET.tostring(root, encoding="utf-8")


def generate(plan: ArtifactPlan, bundle_id: UUID | None = None) -> dict:
    report = validate_plan(plan)
    if not report["valid"]:
        raise ArtifactError("INVALID_ARTIFACT_PLAN", "; ".join(report["errors"]))
    bundle_id = bundle_id or uuid4()
    svg = _svg(plan)
    report["errors"].extend(svg_errors(svg))
    equations = [e for e in plan.elements if isinstance(e, Equation)]
    latex = r"\begin{aligned}" + r"\\".join(
        r"\text{" + str(i + 1) + r"}\quad & " + e.latex for i, e in enumerate(equations)
    ) + r"\end{aligned}" if equations else None
    if latex:
        report["errors"].extend(latex_errors(latex))
    report["valid"] = not report["errors"]
    if not report["valid"]:
        raise ArtifactError("UNSAFE_GENERATED_ARTIFACT", "; ".join(report["errors"]))
    svg_id = uuid5(bundle_id, "base_svg")
    semantic_elements: dict[str, str] = {e.id: e.kind for e in plan.elements}
    semantic_elements.update({t.id: "TERM" for e in equations for t in e.terms})
    assets = [{"artifact_asset_id": str(svg_id), "asset_type": "SVG_DIAGRAM",
               "mime_type": "image/svg+xml", "render_format": "SVG", "suffix": "svg",
               "data": svg, "element_ids": list(semantic_elements),
               "width": plan.width, "height": plan.height}]
    if latex:
        assets.append({"artifact_asset_id": str(uuid5(bundle_id, "latex")), "asset_type": "LATEX_CARD",
                       "mime_type": "text/plain", "render_format": "LATEX", "suffix": "tex",
                       "data": latex.encode(), "element_ids": [e.id for e in equations],
                       "width": None, "height": None})
    overlays = [
        {**o.model_dump(mode="json"), "overlay_state_id": str(uuid5(bundle_id, "overlay_" + o.id)),
         "base_asset_id": str(svg_id), "ordinal": i, "step_number": i + 1}
        for i, o in enumerate(plan.overlays)
    ]
    overlay_map = {o["id"]: o for o in overlays}
    frames = plan.frames or [Frame(overlay_id=o.id) for o in plan.overlays]
    manifest: dict = {
        "frame_sequence_id": str(uuid5(bundle_id, "frames")), "artifact_bundle_id": str(bundle_id),
        "base_asset_id": str(svg_id), "state_mode": "RESET_TO_BASE_EACH_FRAME",
        "element_id_map": semantic_elements,
        "latex_asset_id": str(uuid5(bundle_id, "latex")) if latex else None,
        "latex_lines": [{"element_id": e.id, "latex": e.latex, "step_number": i + 1,
                         "reason": e.reason, "linked_step_id": e.linked_step_id,
                         "terms": [t.model_dump() for t in e.terms]}
                        for i, e in enumerate(equations)],
        "frames": [{**f.model_dump(), "ordinal": i, "step_number": overlay_map[f.overlay_id]["step_number"],
                    "overlay_state_id": overlay_map[f.overlay_id]["overlay_state_id"],
                    "caption": overlay_map[f.overlay_id]["caption"],
                    "linked_step_id": overlay_map[f.overlay_id]["linked_step_id"],
                    "actions": overlay_map[f.overlay_id]["actions"],
                    "explanation_text": overlay_map[f.overlay_id]["explanation_text"],
                    "concept_tag": overlay_map[f.overlay_id]["concept_tag"],
                    "hint_tag": overlay_map[f.overlay_id]["hint_tag"]}
                   for i, f in enumerate(frames)],
    }
    assets.append({"artifact_asset_id": str(uuid5(bundle_id, "manifest")),
                   "asset_type": "FRAME_SEQUENCE", "mime_type": "application/json",
                   "render_format": "JSON", "suffix": "json", "data": _json(manifest).encode(),
                   "element_ids": [], "width": None, "height": None})
    export = {"base_asset_ref": str(svg_id), "ordered_frame_refs": [f["overlay_state_id"] for f in manifest["frames"]],
              "element_id_map": manifest["element_id_map"], "timing_hints": [f.duration_ms for f in frames],
              "transition_hints": [f.transition for f in frames], "renderer_execution": "DEFERRED"}
    assets.append({"artifact_asset_id": str(uuid5(bundle_id, "manim")), "asset_type": "MANIM_EXPORT_SPEC",
                   "mime_type": "application/json", "render_format": "JSON", "suffix": "json",
                   "data": _json(export).encode(), "element_ids": [], "width": None, "height": None})
    search_text = " ".join([plan.title, plan.summary, plan.topic, plan.subtopic or "",
                            *plan.concept_ids, *plan.skill_ids, *plan.theorem_ids,
                            *[e.label for e in plan.elements if hasattr(e, "label")],
                            *[e.latex + " " + e.reason for e in equations],
                            *[o.caption + " " + o.explanation_text for o in plan.overlays]])
    return {"artifact_bundle_id": str(bundle_id), "assets": assets, "overlays": overlays,
            "manifest": manifest, "validation": report, "search_text": search_text,
            "rule_profile_id": f"{plan.subject.lower()}_v1"}


def _one(conn, sql, params) -> dict | None:
    row = conn.execute(text(sql), params).mappings().first()
    return dict(row) if row is not None else None


def create_request(conn, plan: ArtifactPlan, actor: dict) -> dict:
    # Reject malformed references before writing a request, not only during publication.
    report = validate_plan(plan)
    if not report["valid"]:
        raise ArtifactError("INVALID_ARTIFACT_PLAN", "; ".join(report["errors"]))
    if plan.linked_problem_id and _one(
        conn, "SELECT problem_id FROM core.problem WHERE problem_id = CAST(:id AS uuid)",
        {"id": str(plan.linked_problem_id)},
    ) is None:
        raise ArtifactError("INVALID_PROBLEM_REFERENCE", "linked problem does not exist")
    request_id = str(uuid4())
    params = {**plan.model_dump(mode="json"), "id": request_id,
              "owner": actor["student_id"], "created_by": actor["student_id"] or "admin",
              "spec": _json(plan.model_dump(mode="json"))}
    row = _one(conn, """
        INSERT INTO artifact_runtime.artifact_request
        (artifact_request_id, owner_student_id, created_by, request_source, subject, topic, subtopic,
         goal_type, linked_problem_id, linked_solution_step_id, spec)
        VALUES (CAST(:id AS uuid), CAST(:owner AS uuid), :created_by, :request_source, :subject,
                :topic, :subtopic, :goal_type, CAST(:linked_problem_id AS uuid), :linked_solution_step_id,
                CAST(:spec AS jsonb)) RETURNING *
    """, params)
    if row is None:
        raise ArtifactError("REQUEST_WRITE_FAILED", "request was not persisted", 503)
    return row


def get_request(conn, request_id: UUID, actor: dict, lock: bool = False) -> dict:
    row = _one(conn, "SELECT * FROM artifact_runtime.artifact_request "
               "WHERE artifact_request_id = CAST(:id AS uuid)" + (" FOR UPDATE" if lock else ""),
               {"id": str(request_id)})
    if row is None or (actor["role"] != "ADMIN" and str(row["owner_student_id"]) != actor["student_id"]):
        raise ArtifactError("REQUEST_NOT_FOUND", "request not found", 404)
    return row


def get_bundle(conn, bundle_id: UUID, actor: dict) -> dict:
    row = _one(conn, "SELECT * FROM artifact_runtime.artifact_bundle "
               "WHERE artifact_bundle_id = CAST(:id AS uuid) "
               "AND (:admin OR status = 'PUBLISHED')", {"id": str(bundle_id), "admin": actor["role"] == "ADMIN"})
    if row is None:
        raise ArtifactError("BUNDLE_NOT_FOUND", "published bundle not found", 404)
    row["search_text_sha256"] = sha256(row["search_text"].encode()).hexdigest()
    return row


def list_assets(conn, bundle_id: UUID, actor: dict) -> list[dict]:
    get_bundle(conn, bundle_id, actor)
    rows = conn.execute(text("SELECT * FROM artifact_runtime.artifact_asset "
                             "WHERE artifact_bundle_id = CAST(:id AS uuid) ORDER BY asset_type"),
                        {"id": str(bundle_id)}).mappings().all()
    return [{k: v for k, v in dict(row).items() if k != "object_key"} for row in rows]


def asset_bytes(conn, bundle_id: UUID, asset_id: UUID, actor: dict) -> tuple[dict, bytes]:
    get_bundle(conn, bundle_id, actor)
    row = _one(conn, "SELECT * FROM artifact_runtime.artifact_asset "
               "WHERE artifact_bundle_id = CAST(:bundle AS uuid) AND artifact_asset_id = CAST(:id AS uuid)",
               {"bundle": str(bundle_id), "id": str(asset_id)})
    if row is None:
        raise ArtifactError("ASSET_NOT_FOUND", "asset not found", 404)
    try:
        data = object_store.read_bytes(row["object_key"])
    except (OSError, ValueError):
        raise ArtifactError("ASSET_UNAVAILABLE", "private asset unavailable", 503) from None
    if sha256(data).hexdigest() != row["sha256"] or len(data) != row["size_bytes"]:
        raise ArtifactError("ASSET_INTEGRITY_FAILED", "private asset integrity failed", 503)
    return row, data


def get_frames(conn, bundle_id: UUID, actor: dict) -> dict:
    get_bundle(conn, bundle_id, actor)
    row = _one(conn, "SELECT manifest_asset_id FROM artifact_runtime.frame_sequence "
               "WHERE artifact_bundle_id = CAST(:id AS uuid)", {"id": str(bundle_id)})
    if row is None:
        raise ArtifactError("FRAMES_NOT_FOUND", "frame sequence not found", 404)
    _, data = asset_bytes(conn, bundle_id, UUID(str(row["manifest_asset_id"])), actor)
    manifest = json.loads(data)
    for frame in manifest["frames"]:
        frame["content_path"] = f"/v1/artifacts/bundles/{bundle_id}/frames/{frame['ordinal']}/content"
    return manifest


def frame_svg(conn, bundle_id: UUID, ordinal: int, actor: dict) -> bytes:
    """Render validated declarative overlays without executing browser code or a TeX renderer."""
    bundle = get_bundle(conn, bundle_id, actor)
    manifest = get_frames(conn, bundle_id, actor)
    for frame in manifest["frames"]:
        frame.pop("content_path", None)
    if not 0 <= ordinal < len(manifest["frames"]):
        raise ArtifactError("FRAME_NOT_FOUND", "frame ordinal not found", 404)
    request = get_request(conn, UUID(str(bundle["artifact_request_id"])),
                          {"role": "ADMIN", "student_id": None})
    plan = ArtifactPlan.model_validate(request["spec"])
    expected = generate(plan, bundle_id)
    if manifest != expected["manifest"]:
        raise ArtifactError("FRAME_INTEGRITY_FAILED", "stored frame manifest differs from validated source", 503)
    _, data = asset_bytes(conn, bundle_id, UUID(manifest["base_asset_id"]), actor)
    if data != expected["assets"][0]["data"] or svg_errors(data):
        raise ArtifactError("FRAME_INTEGRITY_FAILED", "base SVG differs from validated source", 503)
    root = ET.fromstring(data)
    ns = "{http://www.w3.org/2000/svg}"
    # Strip the fixed namespace to retain simple, browser-safe SVG serialization.
    for node in root.iter():
        node.tag = node.tag.removeprefix(ns)
    root.set("xmlns", "http://www.w3.org/2000/svg")
    targets = {node.attrib["id"]: node for node in root.iter() if "id" in node.attrib}
    layer = targets["overlay_layer"]
    elements = {e.id: e for e in plan.elements}
    frame = manifest["frames"][ordinal]

    def add(tag, attrs, value=None):
        node = ET.SubElement(layer, tag, {k: str(v) for k, v in attrs.items()})
        node.text = value
        return node

    def anchor(identifier):
        e = elements.get(identifier)
        if isinstance(e, (Point, Node)):
            return e.x, e.y
        if isinstance(e, Circle):
            return e.cx, e.cy
        if isinstance(e, Segment):
            a, b = elements[e.start], elements[e.end]
            return (a.x + b.x) / 2, (a.y + b.y) / 2
        if isinstance(e, Angle):
            p = elements[e.vertex]
            return p.x + e.radius, p.y + e.radius
        if isinstance(e, Cell):
            return 100 + e.column * 120, 82 + e.row * 45
        equations = [item for item in plan.elements if isinstance(item, Equation)]
        for i, equation in enumerate(equations):
            if identifier == equation.id or any(t.id == identifier for t in equation.terms):
                return 70, 128 + i * 48
        return 30, 50

    for action in frame["actions"]:
        name = action["action"]
        if name == "FOCUS_REGION":
            x, y, width, height = action["region"]
            add("rect", {"x": x, "y": y, "width": width, "height": height, "fill": "none",
                         "stroke": "#f59e0b", "stroke-width": 3, "stroke-dasharray": "8 5"})
            continue
        if name == "SHOW_RATIO":
            add("text", {"x": 30, "y": plan.height - 55, "font-size": 18, "fill": "#0369a1"},
                action["latex"])
            continue
        if name == "MARK_PERPENDICULAR":
            first, second = (elements[t] for t in action["targets"])
            x1, y1, dx1, dy1 = _segment_geometry(plan, first)
            x2, y2, dx2, dy2 = _segment_geometry(plan, second)
            determinant = dx1 * dy2 - dy1 * dx2
            t = ((x2 - x1) * dy2 - (y2 - y1) * dx2) / determinant
            u = ((x2 - x1) * dy1 - (y2 - y1) * dx1) / determinant
            x, y = x1 + t * dx1, y1 + t * dy1
            sign1, sign2 = (1 if t <= 0.5 else -1), (1 if u <= 0.5 else -1)
            length1, length2 = math.hypot(dx1, dy1), math.hypot(dx2, dy2)
            ax, ay = dx1 / length1 * sign1, dy1 / length1 * sign1
            bx, by = dx2 / length2 * sign2, dy2 / length2 * sign2
            add("path", {"d": f"M{x+10*ax},{y+10*ay} L{x+10*ax+10*bx},{y+10*ay+10*by} "
                        f"L{x+10*bx},{y+10*by}", "fill": "none", "stroke": "#0284c7", "stroke-width": 2})
            continue
        for identifier in action["targets"]:
            target = targets[identifier]
            if name in ("HIGHLIGHT", "EMPHASIZE_EQUATION_LINE", "EMPHASIZE_TERM"):
                for node in target.iter():
                    if "stroke" in node.attrib:
                        node.set("stroke", "#0284c7")
                        node.set("stroke-width", "3")
                    if node.tag in ("text", "tspan"):
                        node.set("fill", "#0369a1")
                    elif node.tag in ("circle", "rect") and node.get("fill") != "none":
                        node.set("fill", "#bae6fd")
            elif name in ("DIM", "HIDE", "SHOW"):
                opacity = {"DIM": "0.25", "HIDE": "0", "SHOW": "1"}[name]
                target.set("opacity", opacity)
                if "label_" + identifier in targets:
                    targets["label_" + identifier].set("opacity", opacity)
            elif name in ("LABEL", "RELABEL"):
                label_node = targets.get("label_" + identifier)
                if name == "RELABEL" and label_node is not None:
                    label_node.text = action["label"]
                else:
                    x, y = anchor(identifier)
                    add("text", {"x": x + 10, "y": y - 24, "font-size": 16, "fill": "#0369a1"},
                        action["label"])
            elif name in ("MARK_EQUAL", "MARK_PARALLEL"):
                x, y = anchor(identifier)
                element = elements[identifier]
                if isinstance(element, Segment):
                    a, b = elements[element.start], elements[element.end]
                    dx, dy = b.x - a.x, b.y - a.y
                    length = math.hypot(dx, dy)
                    if length == 0:
                        raise ArtifactError("INVALID_MARKER", "marker endpoints coincide")
                    ux, uy = dx / length, dy / length
                    px, py = -uy, ux
                    if name == "MARK_EQUAL":
                        add("line", {"x1": x - 6 * px, "y1": y - 6 * py,
                                     "x2": x + 6 * px, "y2": y + 6 * py,
                                     "stroke": "#0284c7", "stroke-width": 2})
                    elif name == "MARK_PARALLEL":
                        add("path", {"d": f"M{x-6*ux+4*px},{y-6*uy+4*py} L{x+4*ux},{y+4*uy} "
                                    f"L{x-6*ux-4*px},{y-6*uy-4*py}",
                                     "fill": "none", "stroke": "#0284c7", "stroke-width": 2})
                else:
                    add("text", {"x": x + 5, "y": y - 5, "font-size": 18, "fill": "#0369a1"}, "=")
    add("text", {"x": 25, "y": plan.height - 20, "font-size": 16, "fill": "#334155"},
        f"{frame['step_number']}. {frame['caption']}")
    rendered = ET.tostring(root, encoding="utf-8")
    if svg_errors(rendered):
        raise ArtifactError("UNSAFE_FRAME", "frame rendering failed safety validation", 503)
    return rendered


def generate_request(conn, request_id: UUID, actor: dict, publish: bool = False,
                     object_keys: list[str] | None = None) -> dict:
    if actor["role"] != "ADMIN":
        raise ArtifactError("ADMIN_REQUIRED", "only staff may generate reusable bundles", 403)
    request = get_request(conn, request_id, actor, lock=True)
    if request["status"] == "GENERATED":
        row = _one(conn, "SELECT artifact_bundle_id FROM artifact_runtime.artifact_bundle "
                   "WHERE artifact_request_id = CAST(:id AS uuid)", {"id": str(request_id)})
        if row is None:
            raise ArtifactError("BUNDLE_UNAVAILABLE", "generated bundle missing", 503)
        bid = UUID(str(row["artifact_bundle_id"]))
        return publish_bundle(conn, bid, actor) if publish else get_bundle(conn, bid, actor)
    plan = ArtifactPlan.model_validate(request["spec"])
    version = 1
    if plan.parent_bundle_id:
        parent = get_bundle(conn, plan.parent_bundle_id, actor)
        if parent["subject"] != plan.subject:
            raise ArtifactError("INVALID_LINEAGE", "parent bundle subject must match")
        version = parent["version"] + 1
    output = generate(plan)
    bid = output["artifact_bundle_id"]
    metadata = {
        "concept_ids": plan.concept_ids, "skill_ids": plan.skill_ids, "theorem_ids": plan.theorem_ids,
        "linked_problem_ids": [str(plan.linked_problem_id)] if plan.linked_problem_id else [],
        "linked_solution_step_ids": [plan.linked_solution_step_id] if plan.linked_solution_step_id else [],
        "step_count": len(output["manifest"]["frames"]), "overlay_count": len(output["overlays"]),
        "frame_count": len(output["manifest"]["frames"]), "has_latex": any(
            a["asset_type"] == "LATEX_CARD" for a in output["assets"]),
        "has_svg": True, "has_animation_manifest": True,
        "generator_version": VERSION,
    }
    params = {**plan.model_dump(mode="json"), "bid": bid, "rid": str(request_id),
              "status": "PUBLISHED" if publish else "DRAFT",
              "review": "APPROVED" if publish else "VALIDATED", "agent": VERSION,
              "profile": output["rule_profile_id"], "search": output["search_text"],
              "metadata": _json(metadata), "version": version}
    conn.execute(text("""
        INSERT INTO artifact_runtime.artifact_bundle
        (artifact_bundle_id, artifact_request_id, parent_bundle_id, subject, topic, subtopic, title,
         summary, difficulty_band, grade_band, status, review_state, created_by_agent, rule_profile_id,
         annotation_profile_id, search_text, metadata, published_at, version)
        VALUES (CAST(:bid AS uuid), CAST(:rid AS uuid), CAST(:parent_bundle_id AS uuid), :subject, :topic,
                :subtopic, :title, :summary, :difficulty_band, :grade_band, :status, :review, :agent,
                :profile, 'step_annotations_v1', :search, CAST(:metadata AS jsonb),
                CASE WHEN :status = 'PUBLISHED' THEN now() ELSE NULL END, :version)
    """), params)
    for asset in output["assets"]:
        stored = object_store.put_bytes(asset["data"], asset["suffix"])
        if object_keys is not None:
            object_keys.append(stored["object_key"])
        conn.execute(text("""
            INSERT INTO artifact_runtime.artifact_asset
            (artifact_asset_id, artifact_bundle_id, asset_type, object_key, sha256, size_bytes,
             mime_type, render_format, width, height, element_ids)
            VALUES (CAST(:artifact_asset_id AS uuid), CAST(:bid AS uuid), :asset_type, :object_key,
                    :sha256, :size_bytes, :mime_type, :render_format, :width, :height, CAST(:ids AS jsonb))
        """), {**{k: v for k, v in asset.items() if k not in ("data", "suffix")},
               **stored, "bid": bid, "ids": _json(asset["element_ids"])})
        conn.execute(text("""
            INSERT INTO artifact_runtime.artifact_metadata
            (artifact_asset_id, subject, concept_ids, skill_ids, theorem_ids, step_labels,
             rule_profile_id, annotation_profile_id, search_text)
            VALUES (CAST(:aid AS uuid), :subject, :concept_ids, :skill_ids, :theorem_ids, :steps,
                    :profile, 'step_annotations_v1', :search)
        """), {**params, "aid": asset["artifact_asset_id"], "steps": [o.caption for o in plan.overlays]})
    for o in output["overlays"]:
        conn.execute(text("""
            INSERT INTO artifact_runtime.overlay_state
            (overlay_state_id, artifact_bundle_id, base_asset_id, ordinal, actions, caption, linked_step_id)
            VALUES (CAST(:overlay_state_id AS uuid), CAST(:bid AS uuid), CAST(:base_asset_id AS uuid),
                    :ordinal, CAST(:actions AS jsonb), :caption, :linked_step_id)
        """), {**o, "bid": bid, "actions": _json(o["actions"])})
        conn.execute(text("""
            INSERT INTO artifact_runtime.artifact_annotation
            (artifact_bundle_id, ordinal, step_number, caption, concept_tag, hint_tag,
             explanation_text, linked_step_id)
            VALUES (CAST(:bid AS uuid), :ordinal, :step_number, :caption, :concept_tag, :hint_tag,
                    :explanation_text, :linked_step_id)
        """), {**o, "bid": bid})
    manifest = output["manifest"]
    conn.execute(text("""
        INSERT INTO artifact_runtime.frame_sequence
        (frame_sequence_id, artifact_bundle_id, manifest_asset_id, ordered_overlay_state_ids)
        VALUES (CAST(:fid AS uuid), CAST(:bid AS uuid), CAST(:aid AS uuid), CAST(:overlays AS uuid[]))
    """), {"fid": manifest["frame_sequence_id"], "bid": bid,
           "aid": str(uuid5(UUID(bid), "manifest")),
           "overlays": [f["overlay_state_id"] for f in manifest["frames"]]})
    conn.execute(text("""
        INSERT INTO artifact_runtime.artifact_lineage
        (artifact_bundle_id, artifact_request_id, parent_bundle_id, generator_version, source_spec_sha256)
        VALUES (CAST(:bid AS uuid), CAST(:rid AS uuid), CAST(:parent_bundle_id AS uuid), :agent, :hash)
    """), {**params, "hash": sha256(_json(plan.model_dump(mode="json")).encode()).hexdigest()})
    _record_validation(conn, bid, output["validation"])
    for kind, tags in (("concept", plan.concept_ids), ("skill", plan.skill_ids), ("theorem", plan.theorem_ids)):
        for tag in set(tags):
            conn.execute(text("INSERT INTO artifact_runtime.artifact_search_tag "
                              "(artifact_bundle_id, tag_type, tag) VALUES (CAST(:bid AS uuid), :kind, :tag)"),
                         {"bid": bid, "kind": kind, "tag": tag})
    conn.execute(text("UPDATE artifact_runtime.artifact_request SET status = 'GENERATED' "
                      "WHERE artifact_request_id = CAST(:rid AS uuid)"), {"rid": str(request_id)})
    return get_bundle(conn, UUID(bid), actor)


def _record_validation(conn, bid: str, report: dict) -> None:
    conn.execute(text("INSERT INTO artifact_runtime.validation_result "
                      "(artifact_bundle_id, valid, validator_version, report) "
                      "VALUES (CAST(:bid AS uuid), :valid, :version, CAST(:report AS jsonb))"),
                 {"bid": bid, "valid": report["valid"], "version": VERSION, "report": _json(report)})


def validate_bundle(conn, bundle_id: UUID, actor: dict) -> dict:
    bundle = get_bundle(conn, bundle_id, actor)
    request = get_request(conn, UUID(str(bundle["artifact_request_id"])), {"role": "ADMIN", "student_id": None})
    plan = ArtifactPlan.model_validate(request["spec"])
    report = validate_plan(plan)
    expected = generate(plan, bundle_id)
    assets = list_assets(conn, bundle_id, actor)
    known = {str(a["artifact_asset_id"]): a for a in expected["assets"]}
    if {str(a["artifact_asset_id"]) for a in assets} != set(known):
        report["errors"].append("missing or unexpected bundle assets")
    for a in assets:
        _, data = asset_bytes(conn, bundle_id, UUID(str(a["artifact_asset_id"])), actor)
        expected_asset = known.get(str(a["artifact_asset_id"]))
        if expected_asset is None or data != expected_asset["data"] or any(
            a[k] != expected_asset[k] for k in ("asset_type", "render_format", "mime_type", "element_ids")
        ):
            report["errors"].append("stored artifact differs from validated declarative source")
        if a["render_format"] == "SVG":
            report["errors"].extend(svg_errors(data))
        if a["render_format"] == "LATEX":
            report["errors"].extend(latex_errors(data.decode()))
    report["valid"] = not report["errors"]
    if actor["role"] == "ADMIN":
        _record_validation(conn, str(bundle_id), report)
    return report


def publish_bundle(conn, bundle_id: UUID, actor: dict) -> dict:
    if actor["role"] != "ADMIN":
        raise ArtifactError("ADMIN_REQUIRED", "only staff may publish reusable bundles", 403)
    conn.execute(text("SELECT artifact_bundle_id FROM artifact_runtime.artifact_bundle "
                      "WHERE artifact_bundle_id = CAST(:id AS uuid) FOR UPDATE"), {"id": str(bundle_id)})
    report = validate_bundle(conn, bundle_id, actor)
    if not report["valid"]:
        raise ArtifactError("VALIDATION_FAILED", "; ".join(report["errors"]))
    conn.execute(text("UPDATE artifact_runtime.artifact_bundle SET status = 'PUBLISHED', "
                      "review_state = 'APPROVED', published_at = COALESCE(published_at, now()) "
                      "WHERE artifact_bundle_id = CAST(:id AS uuid)"), {"id": str(bundle_id)})
    return get_bundle(conn, bundle_id, actor)


def index_bundle(conn, bundle_id: UUID, body: IndexBody, actor: dict) -> dict:
    if actor["role"] != "ADMIN":
        raise ArtifactError("ADMIN_REQUIRED", "only staff may index reusable bundles", 403)
    bundle = get_bundle(conn, bundle_id, actor)
    if bundle["search_text_sha256"] != body.search_text_sha256:
        raise ArtifactError("STALE_SEARCH_TEXT", "embedding source hash does not match bundle search text", 409)
    profile = embedding_profile()
    if body.model != profile["model"] or body.dimensions != profile["dimensions"]:
        raise ArtifactError("EMBEDDING_PROFILE_MISMATCH", "requested model/dimensions differ from configured profile")
    embedding = body.embedding if body.embedding is not None else _embed(bundle["search_text"], profile)
    conn.execute(text("""
        INSERT INTO artifact_runtime.artifact_embedding
        (artifact_bundle_id, model, dimensions, search_text_sha256, embedding)
        VALUES (CAST(:id AS uuid), :model, :dimensions, :hash, CAST(:vector AS vector))
        ON CONFLICT (artifact_bundle_id) DO UPDATE SET embedding = EXCLUDED.embedding,
            model = EXCLUDED.model, dimensions = EXCLUDED.dimensions,
            search_text_sha256 = EXCLUDED.search_text_sha256, indexed_at = now()
    """), {"id": str(bundle_id), "model": body.model, "hash": body.search_text_sha256,
           "vector": _json(embedding), "dimensions": profile["dimensions"]})
    return {"artifact_bundle_id": str(bundle_id), "status": "INDEXED", "model": body.model,
            "dimensions": profile["dimensions"], "provider": profile["provider"],
            "embedding_source": "PROVIDER_EXPLICIT" if body.generate_embedding else "SUPPLIED_VECTOR"}


def search(conn, body: SearchBody, actor: dict, semantic: bool = False) -> dict:
    mode = "SEMANTIC" if semantic else "LEXICAL"
    if semantic and body.query_embedding is None and not body.generate_embedding:
        return {"mode": mode, "status": "UNAVAILABLE", "reason": "QUERY_EMBEDDING_REQUIRED", "results": []}
    filters = ["(:admin OR b.status = 'PUBLISHED')"]
    params = {**body.model_dump(), "admin": actor["role"] == "ADMIN"}
    for key in ("subject", "difficulty_band"):
        if params[key] is not None:
            filters.append(f"b.{key} = :{key}")
    for key, kind in (("concept_id", "concept"), ("skill_id", "skill"), ("theorem_id", "theorem")):
        if params[key] is not None:
            filters.append("EXISTS (SELECT 1 FROM artifact_runtime.artifact_search_tag t "
                           f"WHERE t.artifact_bundle_id=b.artifact_bundle_id AND t.tag_type='{kind}' AND t.tag=:{key})")
    if body.asset_type:
        filters.append("EXISTS (SELECT 1 FROM artifact_runtime.artifact_asset a "
                       "WHERE a.artifact_bundle_id=b.artifact_bundle_id AND a.asset_type=:asset_type)")
    join = ""
    if semantic:
        try:
            profile = embedding_profile()
        except ArtifactError as exc:
            return {"mode": mode, "status": "UNAVAILABLE", "reason": exc.code, "results": []}
        if body.model != profile["model"] or body.dimensions != profile["dimensions"]:
            return {"mode": mode, "status": "UNAVAILABLE", "reason": "EMBEDDING_PROFILE_MISMATCH", "results": []}
        join = "JOIN artifact_runtime.artifact_embedding e ON e.artifact_bundle_id=b.artifact_bundle_id"
        filters += ["e.model = :model", "e.dimensions = :dimensions",
                    "e.search_text_sha256 = encode(sha256(convert_to(b.search_text, 'UTF8')), 'hex')"]
        if body.generate_embedding:
            available = _one(conn, "SELECT b.artifact_bundle_id "
                             f"FROM artifact_runtime.artifact_bundle b {join} "
                             f"WHERE {' AND '.join(filters)} LIMIT 1", params)
            if available is None:
                return {"mode": mode, "status": "UNAVAILABLE",
                        "reason": "NO_INDEXED_VECTORS_FOR_FILTERS", "results": []}
            try:
                params["vector"] = _json(_embed(body.query, profile))
            except ArtifactError as exc:
                return {"mode": mode, "status": "UNAVAILABLE", "reason": exc.code, "results": []}
        else:
            params["vector"] = _json(body.query_embedding)
        rank = "1 - (e.embedding <=> CAST(:vector AS vector))"
    else:
        rank = "ts_rank_cd(to_tsvector('simple', b.search_text), plainto_tsquery('simple', :query))"
        if body.query:
            filters.append("to_tsvector('simple', b.search_text) @@ plainto_tsquery('simple', :query)")
    rows = conn.execute(text(f"""
        SELECT b.artifact_bundle_id, b.subject, b.topic, b.title, b.summary, b.status, b.metadata,
               {rank} AS score
        FROM artifact_runtime.artifact_bundle b {join}
        WHERE {' AND '.join(filters)}
        ORDER BY score DESC, b.artifact_bundle_id LIMIT :limit OFFSET :offset
    """), params).mappings().all()
    if semantic and not rows:
        if body.offset and _one(conn, "SELECT b.artifact_bundle_id "
                                f"FROM artifact_runtime.artifact_bundle b {join} "
                                f"WHERE {' AND '.join(filters)} LIMIT 1", params) is not None:
            return {"mode": mode, "status": "AVAILABLE", "results": [],
                    "model": profile["model"], "dimensions": profile["dimensions"]}
        return {"mode": mode, "status": "UNAVAILABLE", "reason": "NO_INDEXED_VECTORS_FOR_FILTERS", "results": []}
    return {"mode": mode, "status": "AVAILABLE", "results": [dict(row) for row in rows],
            **({"model": profile["model"], "dimensions": profile["dimensions"],
                "provider": profile["provider"]} if semantic else {})}


def similar(conn, bundle_id: UUID, body: SearchBody, actor: dict) -> dict:
    bundle = get_bundle(conn, bundle_id, actor)
    try:
        profile = embedding_profile()
    except ArtifactError as exc:
        return {"mode": "SEMANTIC", "status": "UNAVAILABLE", "reason": exc.code, "results": []}
    row = _one(conn, "SELECT embedding::text AS embedding, search_text_sha256 FROM artifact_runtime.artifact_embedding "
               "WHERE artifact_bundle_id = CAST(:id AS uuid) AND model = :model AND dimensions = :dimensions",
               {"id": str(bundle_id), "model": profile["model"], "dimensions": profile["dimensions"]})
    if row is None or row["search_text_sha256"] != bundle["search_text_sha256"]:
        return {"mode": "SEMANTIC", "status": "UNAVAILABLE", "reason": "SOURCE_NOT_INDEXED", "results": []}
    result = search(conn, body.model_copy(update={
        "query_embedding": json.loads(row["embedding"]), "generate_embedding": False,
        "model": profile["model"], "dimensions": profile["dimensions"],
    }), actor, True)
    result["results"] = [r for r in result["results"] if str(r["artifact_bundle_id"]) != str(bundle_id)]
    return result
