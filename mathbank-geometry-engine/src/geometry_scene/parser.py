from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

import yaml

from .errors import GeometryError
from .schemas import MathObject, Relation, RelationStatus, RelationType, SceneInput

STATUS_MAP = {
    "given": RelationStatus.GIVEN,
    "known": RelationStatus.GIVEN,
    "definition": RelationStatus.GIVEN,
    "construction": RelationStatus.ASSUMED_FOR_CONSTRUCTION,
    "proven": RelationStatus.PROVEN,
    "target": RelationStatus.TARGET_TO_PROVE,
    "unknown": RelationStatus.UNKNOWN,
}


def load_document(path: Path):
    if path.stat().st_size > 1024 * 1024:
        raise GeometryError("input document exceeds 1 MiB")
    if path.suffix.lower() == ".json":
        value = json.loads(path.read_text())
    elif path.suffix.lower() in (".yaml", ".yml"):
        value = yaml.safe_load(path.read_text())
    else:
        raise GeometryError("input extension must be .json, .yaml or .yml")
    if not isinstance(value, dict):
        raise GeometryError("input must be an object")
    return value


def parse_fact(fact: str, status, index):
    fact = fact.strip().replace("_", "")
    patterns = [
        (r"([A-Z]\d*) = circumcenter\(([A-Z])([A-Z])([A-Z])\)", RelationType.CIRCUMCENTER),
        (r"([A-Z]\d*) is midpoint of ([A-Z]\d*) ?([A-Z]\d*)", RelationType.MIDPOINT),
        (r"([A-Z]),([A-Z]),([A-Z])(?:,([A-Z]))? are concyclic", RelationType.CONCYCLIC),
        (r"([A-Z]),([A-Z]),([A-Z]) are collinear", RelationType.COLLINEAR),
        (r"([A-Z])([A-Z]) parallel ([A-Z])([A-Z])", RelationType.PARALLEL),
        (r"([A-Z])([A-Z]) perpendicular ([A-Z])([A-Z])", RelationType.PERPENDICULAR),
        (r"([A-Z])([A-Z])([A-Z]) is a triangle", RelationType.TRIANGLE),
        (
            r"([A-Z])([A-Z])([A-Z])([A-Z]) is (?:a convex quadrilateral|convex)",
            RelationType.QUADRILATERAL,
        ),
        (
            r"triangle ([A-Z])([A-Z])([A-Z]) is similar to triangle ([A-Z])([A-Z])([A-Z])",
            RelationType.SIMILAR,
        ),
        (r"segment ([A-Z])([A-Z]) and \2([A-Z]) form a straight line", RelationType.COLLINEAR),
    ]
    for pattern, kind in patterns:
        match = re.fullmatch(pattern, fact, re.IGNORECASE)
        if match:
            return Relation(
                id=f"context_{index}",
                type=kind,
                args=tuple(a for a in match.groups() if a),
                status=status,
                provenance=fact,
            )
    raise GeometryError(
        f"unsupported/ambiguous context fact at index {index}; supply typed relations"
    )


def parse_input(value: SceneInput) -> SceneInput:
    if value.objects or value.relations:
        return value
    if not value.context:
        raise GeometryError("text-only parsing is not reliable; supply typed context facts or DSL")
    objects, relations, deferred = {}, [], []
    for index, item in enumerate(value.context):
        kind = item.get("type")
        fact = item.get("fact")
        if kind in ("focus", "visual_preference"):
            continue
        if kind not in STATUS_MAP or not isinstance(fact, str):
            raise GeometryError(f"invalid context entry {index}")
        relation = parse_fact(fact, STATUS_MAP[kind], index)
        relations.append(relation)
        for name in relation.args:
            objects[name] = MathObject()
        if kind == "definition":
            deferred.append(relation.id)
    return value.model_copy(
        update={
            "objects": objects,
            "relations": tuple(relations),
            "deferred_relations": tuple(deferred),
        }
    )


def parse_dsl(document):
    # Pack's concise scene/object/status spellings normalize into one strict contract.
    value = deepcopy(document)
    if "scene" in value:
        scene = value.pop("scene")
        value["scene_id"] = scene["id"]
        value["rendering_mode"] = scene.get("rendering_mode", "EXACT_OR_CONSTRAINED").upper()
    if "targets" in value:
        value["relations"] = [*value.get("relations", []), *value.pop("targets")]
    for name, obj in value.get("objects", {}).items():
        value["objects"][name] = {**obj, "type": obj.get("type", "POINT").upper()}
    relations = []
    for index, relation in enumerate(value.get("relations", [])):
        kind = relation["type"].upper()
        relations.append(
            {
                **relation,
                "id": relation.get("id", f"relation_{index}"),
                "type": "CONCYCLIC" if kind == "CYCLIC" else kind,
                "status": relation["status"].upper(),
            }
        )
    value["relations"] = relations
    return parse_input(SceneInput.model_validate(value))
