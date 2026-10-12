"""Offline subject, safety, persistence and indexing acceptance tests."""
from __future__ import annotations

import copy
import json
import shutil
import xml.etree.ElementTree as ET
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from mathbank_rest import artifact_runtime as ar

ADMIN = {"role": "ADMIN", "student_id": None}
STUDENT = {"role": "STUDENT", "student_id": str(uuid4())}
PROFILE_READER = ar.embedding_profile


@pytest.fixture(autouse=True)
def offline_embedding_profile(monkeypatch):
    monkeypatch.setattr(ar, "embedding_profile", lambda: {
        "provider": "direct_openai", "model": "text-embedding-3-small", "dimensions": 1536,
    })


def plan_payload(subject="GEOMETRY"):
    elements = {
        "GEOMETRY": [
            {"kind": "POINT", "id": "point_A", "x": 150, "y": 180, "label": "A"},
            {"kind": "POINT", "id": "point_B", "x": 400, "y": 180, "label": "B", "contact": True},
            {"kind": "SEGMENT", "id": "segment_AB", "start": "point_A", "end": "point_B", "auxiliary": True},
            {"kind": "CIRCLE", "id": "circle_1", "cx": 400, "cy": 300, "radius": 120},
            {"kind": "ANGLE", "id": "angle_B", "vertex": "point_B", "start_degrees": 0,
             "end_degrees": 90, "label": "90"},
        ],
        "ALGEBRA": [
            {"kind": "EQUATION", "id": "eq_line_1", "latex": "2x+3=7", "reason": "Starting equation",
             "terms": [{"id": "term_x", "latex": "2x"}, {"id": "term_rest", "latex": "+3=7"}],
             "linked_step_id": "step-1"},
            {"kind": "EQUATION", "id": "eq_line_2", "latex": "x=2", "reason": "Subtract then divide"},
        ],
        "COMBINATORICS": [
            {"kind": "NODE", "id": "tree_node_1", "x": 400, "y": 100, "label": "All cases"},
            {"kind": "NODE", "id": "tree_node_2", "x": 180, "y": 240, "label": "Case A"},
            {"kind": "NODE", "id": "tree_node_3", "x": 600, "y": 240, "label": "Case B"},
            {"kind": "EDGE", "id": "branch_A", "start": "tree_node_1", "end": "tree_node_2"},
            {"kind": "EDGE", "id": "branch_B", "start": "tree_node_1", "end": "tree_node_3"},
        ],
        "NUMBER_THEORY": [
            {"kind": "CELL", "id": "residue_0", "row": 0, "column": 0, "label": "0 (mod 7)"},
            {"kind": "CELL", "id": "residue_1", "row": 0, "column": 1, "label": "1 (mod 7)"},
            {"kind": "EQUATION", "id": "eq_mod", "latex": r"8\equiv1\pmod{7}", "reason": "Reduce modulo seven"},
        ],
    }[subject]
    return {
        "subject": subject, "topic": "test concept", "title": f"{subject} demonstration",
        "summary": "Instructional test", "elements": elements, "concept_ids": ["concept-1"],
        "skill_ids": ["skill-1"], "theorem_ids": ["theorem-1"],
        "overlays": [{"id": "focus_1", "caption": "Identify the active part", "linked_step_id": "step-1",
                      "explanation_text": "Reasoning here", "concept_tag": "test concept",
                      "actions": [{"action": "HIGHLIGHT", "targets": [elements[0]["id"]]}]}],
        **({"number_theory_mode": "MODULAR", "modulus": 7} if subject == "NUMBER_THEORY" else {}),
    }


@pytest.fixture
def object_root(monkeypatch):
    # Deliberately not pytest tmp_path: scratch objects stay inside the project.
    root = Path(__file__).parent / f".artifact-objects-{uuid4().hex}"
    monkeypatch.setenv("MATHBANK_OBJECT_BACKEND", "filesystem")
    monkeypatch.setenv("MATHBANK_OBJECT_ROOT", str(root))
    yield root
    shutil.rmtree(root, ignore_errors=True)


@pytest.mark.parametrize("subject", ["GEOMETRY", "ALGEBRA", "COMBINATORICS", "NUMBER_THEORY"])
def test_subject_profiles_are_structured_and_deterministic(subject):
    plan = ar.ArtifactPlan.model_validate(plan_payload(subject))
    bundle_id = uuid4()
    result = ar.generate(plan, bundle_id)
    assert result["validation"]["valid"]
    assert result["rule_profile_id"] == subject.lower() + "_v1"
    assert result == ar.generate(plan, bundle_id)
    svg = result["assets"][0]["data"]
    assert ar.svg_errors(svg) == []
    manifest = result["manifest"]
    frame = manifest["frames"][0]
    assert frame["ordinal"] == 0 and frame["step_number"] == 1
    assert frame["linked_step_id"] == "step-1" and frame["caption"]
    assert manifest["state_mode"] == "RESET_TO_BASE_EACH_FRAME"
    assert set(frame["actions"][0]["targets"]) <= set(manifest["element_id_map"])
    assert "object_key" not in result


def test_geometry_rules_dots_contacts_extensions_circles():
    svg = ar.generate(ar.ArtifactPlan.model_validate(plan_payload()))["assets"][0]["data"].decode()
    assert 'r="3"' in svg and 'r="5"' in svg
    assert 'stroke-dasharray="6 5"' in svg
    assert 'stroke="#94a3b8" stroke-width="1"' in svg
    assert 'id="angle_B"' in svg and 'id="label_point_A"' in svg


def test_algebra_alignment_and_targetable_terms():
    payload = plan_payload("ALGEBRA")
    payload["overlays"][0]["actions"] = [{"action": "EMPHASIZE_TERM", "targets": ["term_x"]}]
    result = ar.generate(ar.ArtifactPlan.model_validate(payload))
    root = ET.fromstring(result["assets"][0]["data"])
    ns = {"s": "http://www.w3.org/2000/svg"}
    lines = [g.find("s:text", ns) for g in root.findall("s:g/s:g", ns)]
    assert [line.attrib["x"] for line in lines] == ["70", "70"]
    assert result["manifest"]["element_id_map"]["term_x"] == "TERM"
    latex = next(a["data"].decode() for a in result["assets"] if a["asset_type"] == "LATEX_CARD")
    assert latex.startswith(r"\begin{aligned}") and r"\\\text{2}" in latex
    assert result["manifest"]["latex_lines"][0]["terms"][0]["id"] == "term_x"


@pytest.mark.parametrize("action", [
    "HIGHLIGHT", "DIM", "SHOW", "HIDE", "LABEL", "RELABEL", "MARK_EQUAL",
    "MARK_PARALLEL", "MARK_PERPENDICULAR", "SHOW_RATIO", "FOCUS_REGION",
    "EMPHASIZE_EQUATION_LINE", "EMPHASIZE_TERM",
])
def test_every_declared_overlay_action_is_validated_and_preserved(action, object_root):
    payload = plan_payload("ALGEBRA" if action.startswith("EMPHASIZE") else "GEOMETRY")
    if action.startswith("EMPHASIZE"):
        targets = ["term_x"] if action == "EMPHASIZE_TERM" else ["eq_line_1"]
    elif action.startswith("MARK"):
        payload["elements"] = payload["elements"][:3] + [
            {"kind": "POINT", "id": "point_C", "x": 400, "y": 400, "label": "C"},
            {"kind": "SEGMENT", "id": "segment_BC", "start": "point_B", "end": "point_C"},
        ]
        targets = ["segment_AB", "segment_BC"]
        if action == "MARK_PARALLEL":
            payload["elements"] += [{"kind": "POINT", "id": "point_D", "x": 150, "y": 400, "label": "D"},
                                    {"kind": "SEGMENT", "id": "segment_CD", "start": "point_C", "end": "point_D"}]
            targets = ["segment_AB", "segment_CD"]
    else:
        targets = ["point_A"]
    spec = {"action": action, "targets": targets}
    if action in ("LABEL", "RELABEL"):
        spec["label"] = "Corresponding vertex"
    if action == "SHOW_RATIO":
        spec["latex"] = r"\frac{AB}{BC}"
    if action == "FOCUS_REGION":
        spec["region"] = [100, 100, 400, 400]
    payload["overlays"][0]["actions"] = [spec]
    generated = ar.generate(ar.ArtifactPlan.model_validate(payload))
    saved = generated["manifest"]["frames"][0]["actions"][0]
    assert saved["action"] == action and saved["targets"] == targets
    conn = Connection()
    req = ar.create_request(conn, ar.ArtifactPlan.model_validate(payload), ADMIN)
    bundle = ar.generate_request(conn, UUID(req["artifact_request_id"]), ADMIN, publish=True)
    rendered = ar.frame_svg(conn, UUID(bundle["artifact_bundle_id"]), 0, STUDENT)
    assert ar.svg_errors(rendered) == []
    assert b"Identify the active part" in rendered


def test_explicit_frame_order_and_steps_stay_stable():
    payload = plan_payload("ALGEBRA")
    second = copy.deepcopy(payload["overlays"][0])
    second.update(id="focus_2", caption="Complete transformation", linked_step_id="step-2")
    second["actions"] = [{"action": "EMPHASIZE_EQUATION_LINE", "targets": ["eq_line_2"]}]
    payload["overlays"].append(second)
    payload["frames"] = [
        {"overlay_id": "focus_2", "duration_ms": 2000, "transition": "FADE"},
        {"overlay_id": "focus_1", "duration_ms": 1000},
    ]
    frames = ar.generate(ar.ArtifactPlan.model_validate(payload))["manifest"]["frames"]
    assert [f["ordinal"] for f in frames] == [0, 1]
    assert [f["step_number"] for f in frames] == [2, 1]
    assert [f["linked_step_id"] for f in frames] == ["step-2", "step-1"]


def test_frame_svg_is_published_scoped_and_resets_base_each_frame(object_root):
    payload = plan_payload()
    second = copy.deepcopy(payload["overlays"][0])
    second.update(id="dim", caption="Dim the vertex")
    second["actions"] = [{"action": "DIM", "targets": ["point_A"]}]
    payload["overlays"].append(second)
    conn = Connection()
    req = ar.create_request(conn, ar.ArtifactPlan.model_validate(payload), ADMIN)
    bundle = ar.generate_request(conn, UUID(req["artifact_request_id"]), ADMIN)
    bid = UUID(bundle["artifact_bundle_id"])
    with pytest.raises(ar.ArtifactError):
        ar.frame_svg(conn, bid, 0, STUDENT)
    ar.publish_bundle(conn, bid, ADMIN)
    first = ar.frame_svg(conn, bid, 0, STUDENT)
    second = ar.frame_svg(conn, bid, 1, STUDENT)
    assert b"#bae6fd" in first and b"#bae6fd" not in second
    assert b'opacity="0.25"' in second
    with pytest.raises(ar.ArtifactError) as exc:
        ar.frame_svg(conn, bid, 2, STUDENT)
    assert exc.value.status_code == 404


@pytest.mark.parametrize("action", ["MARK_PARALLEL", "MARK_PERPENDICULAR"])
def test_marker_claims_must_match_geometric_relation(action):
    payload = plan_payload()
    payload["overlays"][0]["actions"] = [{
        "action": action, "targets": ["segment_AB", "segment_AC"],
    }]
    payload["elements"] += [
        {"kind": "POINT", "id": "point_C", "x": 600, "y": 450, "label": "C"},
        {"kind": "SEGMENT", "id": "segment_AC", "start": "point_A", "end": "point_C"},
    ]
    report = ar.validate_plan(ar.ArtifactPlan.model_validate(payload))
    assert not report["valid"] and any("contradicts" in e for e in report["errors"])


def test_geometry_labels_move_off_diagonal_structural_lines():
    payload = plan_payload()
    payload["elements"] = [
        {"kind": "POINT", "id": "A", "x": 200, "y": 300, "label": "A"},
        {"kind": "POINT", "id": "B", "x": 400, "y": 100, "label": "B"},
        {"kind": "SEGMENT", "id": "AB", "start": "A", "end": "B"},
    ]
    payload["overlays"][0]["actions"][0]["targets"] = ["A"]
    result = ar.generate(ar.ArtifactPlan.model_validate(payload))
    root = ET.fromstring(result["assets"][0]["data"])
    ns = {"s": "http://www.w3.org/2000/svg"}
    label = root.find(".//s:text[@id='label_A']", ns)
    assert float(label.attrib["y"]) > 300  # The initial upper-right position crossed AB.


@pytest.mark.parametrize("mutation,needle", [
    (lambda p: p["elements"][2].update(end="ghost"), "endpoints"),
    (lambda p: p["overlays"][0]["actions"][0].update(targets=["ghost"]), "targets"),
    (lambda p: p.update(frames=[{"overlay_id": "ghost"}]), "frame"),
    (lambda p: p["elements"][1].update(x=151, y=181), "too close"),
    (lambda p: p["elements"][3].update(radius=800), "canvas"),
    (lambda p: p["elements"][1].update(id="point_A"), "unique"),
    (lambda p: p["overlays"][0]["actions"][0].update(action="EMPHASIZE_EQUATION_LINE"), "equations"),
    (lambda p: p["elements"][0].update(id="base_layer"), "reserved"),
])
def test_plan_validation_errors_before_generation(mutation, needle):
    payload = plan_payload()
    mutation(payload)
    plan = ar.ArtifactPlan.model_validate(payload)
    report = ar.validate_plan(plan)
    assert not report["valid"] and needle in " ".join(report["errors"])
    with pytest.raises(ar.ArtifactError):
        ar.generate(plan)


@pytest.mark.parametrize("latex", [
    r"\input{/etc/passwd}", r"\href{https://example.org}{x}", r"\write18{sh}",
    r"\newcommand{\x}{1}", r"\csname input\endcsname", r"\begin{document}x\end{document}",
    r"\frac{1}{2", "x<script>", "$x$", "x% comment",
])
def test_latex_rejects_unsafe_or_unsupported_commands(latex):
    payload = plan_payload("ALGEBRA")
    payload["elements"][0].update(latex=latex, terms=[])
    assert not ar.validate_plan(ar.ArtifactPlan.model_validate(payload))["valid"]


@pytest.mark.parametrize("svg", [
    b'<svg><script>alert(1)</script></svg>',
    b'<svg><image href="file:///etc/passwd"/></svg>',
    b'<svg onload="alert(1)"/>',
    b'<svg><foreignObject/></svg>',
    b'<svg><text style="color:red">x</text></svg>',
    b'<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg>&x;</svg>',
    b'<svg><g id="same"/><g id="same"/></svg>',
    b'<svg><path fill="url(https://example.org/x)"/></svg>',
    b'<svg><path fill="u\\72l(//example.org/x)"/></svg>',
    b'<svg><line x1="expression(alert(1))"/></svg>',
])
def test_svg_rejects_active_content_and_entities(svg):
    assert ar.svg_errors(svg)


def test_subject_context_and_shape_rejection():
    payload = plan_payload("NUMBER_THEORY")
    del payload["modulus"]
    assert not ar.validate_plan(ar.ArtifactPlan.model_validate(payload))["valid"]
    payload = plan_payload()
    payload["subject"] = "ALGEBRA"
    assert not ar.validate_plan(ar.ArtifactPlan.model_validate(payload))["valid"]
    payload["elements"] = [{"kind": "IMAGE", "url": "https://example.org"}]
    with pytest.raises(ValidationError):
        ar.ArtifactPlan.model_validate(payload)
    payload = plan_payload("NUMBER_THEORY")
    payload["modulus"] = 5
    assert any("modulus differs" in e for e in ar.validate_plan(ar.ArtifactPlan.model_validate(payload))["errors"])


def test_factor_tree_prime_validation_and_euclidean_profile():
    payload = plan_payload("COMBINATORICS")
    payload.update(subject="NUMBER_THEORY", number_theory_mode="FACTOR_TREE")
    payload["elements"][0]["label"] = "12"
    payload["elements"][1].update(label="2", prime=True)
    payload["elements"][2].update(label="6", prime=False)
    assert ar.generate(ar.ArtifactPlan.model_validate(payload))["validation"]["valid"]
    payload["elements"][2]["prime"] = True
    assert not ar.validate_plan(ar.ArtifactPlan.model_validate(payload))["valid"]
    payload = plan_payload("ALGEBRA")
    payload.update(subject="NUMBER_THEORY", number_theory_mode="EUCLIDEAN")
    payload["elements"] = [
        {"kind": "EQUATION", "id": "eq_1", "latex": "31=4(7)+3", "reason": "Quotient 4, remainder 3"},
        {"kind": "EQUATION", "id": "eq_2", "latex": "7=2(3)+1", "reason": "Quotient 2, remainder 1"},
    ]
    payload["overlays"][0]["actions"][0]["targets"] = ["eq_1"]
    assert ar.generate(ar.ArtifactPlan.model_validate(payload))["validation"]["valid"]


@pytest.mark.parametrize("field,value", [
    ("linked_problem_id", "not-a-uuid"), ("parent_bundle_id", "../../file"),
    ("title", "x" * 201), ("elements", []),
    ("concept_ids", ["x"] * 65), ("overlays", [{}] * 65),
])
def test_bounded_strict_domain(field, value):
    payload = plan_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        ar.ArtifactPlan.model_validate(payload)


class Result:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def mappings(self):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return self.rows


class Connection:
    """Record bound SQL and emulate rows; no live SQL or embedding provider is used."""
    def __init__(self):
        self.calls = []
        self.requests = {}
        self.bundles = {}
        self.assets = {}
        self.frames = {}
        self.embeddings = {}
        self.fail_asset_insert = False

    def execute(self, statement, params):
        sql = " ".join(str(statement).split())
        params = copy.deepcopy(params)
        self.calls.append((sql, params))
        if sql.startswith("INSERT INTO artifact_runtime.artifact_request"):
            row = {**params, "artifact_request_id": params["id"], "owner_student_id": params["owner"],
                   "status": "REQUESTED", "spec": json.loads(params["spec"])}
            self.requests[params["id"]] = row
            return Result([row])
        if sql.startswith("SELECT * FROM artifact_runtime.artifact_request"):
            return Result([self.requests[params["id"]]] if params["id"] in self.requests else [])
        if sql.startswith("INSERT INTO artifact_runtime.artifact_bundle"):
            self.bundles[params["bid"]] = {**params, "artifact_bundle_id": params["bid"],
                "artifact_request_id": params["rid"], "search_text": params["search"],
                "metadata": json.loads(params["metadata"])}
        elif sql.startswith("SELECT * FROM artifact_runtime.artifact_bundle"):
            row = self.bundles.get(params["id"])
            return Result([row] if row and (params["admin"] or row["status"] == "PUBLISHED") else [])
        elif sql.startswith("SELECT artifact_bundle_id FROM artifact_runtime.artifact_bundle"):
            return Result([b for b in self.bundles.values() if b["artifact_request_id"] == params.get("id")])
        elif sql.startswith("INSERT INTO artifact_runtime.artifact_asset"):
            if self.fail_asset_insert:
                raise RuntimeError("simulated rollback")
            self.assets[params["artifact_asset_id"]] = {
                **params, "artifact_bundle_id": params["bid"], "element_ids": json.loads(params["ids"])}
        elif sql.startswith("SELECT * FROM artifact_runtime.artifact_asset"):
            return Result([a for a in self.assets.values()
                if a["artifact_bundle_id"] == params.get("bundle", params.get("id"))
                and ("bundle" not in params or a["artifact_asset_id"] == params["id"])])
        elif sql.startswith("INSERT INTO artifact_runtime.frame_sequence"):
            self.frames[params["bid"]] = {"manifest_asset_id": params["aid"]}
        elif sql.startswith("SELECT manifest_asset_id"):
            return Result([self.frames[params["id"]]] if params["id"] in self.frames else [])
        elif sql.startswith("UPDATE artifact_runtime.artifact_request"):
            self.requests[params["rid"]]["status"] = "GENERATED"
        elif sql.startswith("UPDATE artifact_runtime.artifact_bundle"):
            self.bundles[params["id"]]["status"] = "PUBLISHED"
        elif sql.startswith("INSERT INTO artifact_runtime.artifact_embedding"):
            self.embeddings[params["id"]] = params
        elif sql.startswith("SELECT embedding::text"):
            row = self.embeddings.get(params["id"])
            return Result([{"embedding": row["vector"], "search_text_sha256": row["hash"]}] if row else [])
        elif sql.startswith("SELECT b.artifact_bundle_id"):
            rows = [dict(b) for bid, b in self.bundles.items() if bid in self.embeddings
                    and (params["admin"] or b["status"] == "PUBLISHED")
                    and self.embeddings[bid]["hash"] == sha256(b["search_text"].encode()).hexdigest()
                    and (params.get("subject") is None or b["subject"] == params["subject"])]
            return Result(rows)
        return Result()


def test_request_generate_store_validate_publish_and_index_sql_flow(object_root):
    conn = Connection()
    plan = ar.ArtifactPlan.model_validate(plan_payload("ALGEBRA"))
    req = ar.create_request(conn, plan, STUDENT)
    request_id = UUID(req["artifact_request_id"])
    assert ar.get_request(conn, request_id, STUDENT)["owner_student_id"] == STUDENT["student_id"]
    with pytest.raises(ar.ArtifactError) as exc:
        ar.get_request(conn, request_id, {"role": "STUDENT", "student_id": str(uuid4())})
    assert exc.value.status_code == 404
    with pytest.raises(ar.ArtifactError) as exc:
        ar.generate_request(conn, request_id, STUDENT)
    assert exc.value.status_code == 403
    keys = []
    bundle = ar.generate_request(conn, request_id, ADMIN, object_keys=keys)
    bundle_id = UUID(bundle["artifact_bundle_id"])
    assert len(keys) == 4 and bundle["status"] == "DRAFT"
    assert ar.validate_bundle(conn, bundle_id, ADMIN)["valid"]
    with pytest.raises(ar.ArtifactError):
        ar.get_bundle(conn, bundle_id, STUDENT)
    assert ar.publish_bundle(conn, bundle_id, ADMIN)["status"] == "PUBLISHED"
    assert ar.get_bundle(conn, bundle_id, STUDENT)["status"] == "PUBLISHED"
    assert all("object_key" not in a for a in ar.list_assets(conn, bundle_id, STUDENT))
    assert ar.get_frames(conn, bundle_id, STUDENT)["frames"][0]["linked_step_id"] == "step-1"
    replay = ar.generate_request(conn, request_id, ADMIN)
    assert replay["artifact_bundle_id"] == str(bundle_id)
    body = ar.IndexBody(embedding=[1.0] + [0.0] * 1535,
                       search_text_sha256=bundle["search_text_sha256"])
    assert ar.index_bundle(conn, bundle_id, body, ADMIN)["status"] == "INDEXED"
    tables = {sql.split()[2] for sql, _ in conn.calls if sql.startswith("INSERT INTO")}
    assert {f"artifact_runtime.{table}" for table in (
        "artifact_request", "artifact_bundle", "artifact_asset", "artifact_metadata", "overlay_state",
        "frame_sequence", "artifact_annotation", "artifact_lineage", "validation_result",
        "artifact_search_tag", "artifact_embedding")} <= tables
    assert not any("embedding" in sql for sql, _ in conn.calls
                   if sql.startswith("INSERT") and "artifact_embedding" not in sql)
    for sql, params in conn.calls:
        if sql.startswith("INSERT INTO artifact_runtime.artifact_asset "):
            assert ":object_key" in sql and ":sha256" in sql
        assert str(plan.linked_problem_id) not in sql or plan.linked_problem_id is None


def test_publication_revalidates_bytes_and_integrity(object_root):
    conn = Connection()
    request = ar.create_request(conn, ar.ArtifactPlan.model_validate(plan_payload()), ADMIN)
    bundle = ar.generate_request(conn, UUID(request["artifact_request_id"]), ADMIN)
    bid = UUID(bundle["artifact_bundle_id"])
    asset = next(a for a in conn.assets.values() if a["render_format"] == "SVG")
    (object_root / asset["object_key"]).write_bytes(b"<svg><script/></svg>")
    with pytest.raises(ar.ArtifactError) as exc:
        ar.publish_bundle(conn, bid, ADMIN)
    assert exc.value.code == "ASSET_INTEGRITY_FAILED"
    asset.update(sha256=sha256(b"<svg><script/></svg>").hexdigest(), size_bytes=20)
    asset["size_bytes"] = len(b"<svg><script/></svg>")
    report = ar.validate_bundle(conn, bid, ADMIN)
    assert not report["valid"] and any("unsafe SVG" in e for e in report["errors"])


def test_semantic_is_explicit_and_never_lexical_fallback():
    conn = Connection()
    body = ar.SearchBody(query="circle", subject="GEOMETRY", concept_id="concept-1", asset_type="SVG_DIAGRAM")
    result = ar.search(conn, body, STUDENT, semantic=True)
    assert result["status"] == "UNAVAILABLE" and result["reason"] == "QUERY_EMBEDDING_REQUIRED"
    assert not conn.calls
    result = ar.search(conn, body.model_copy(update={"query_embedding": [1.0] + [0.0] * 1535}),
                       STUDENT, semantic=True)
    assert result["reason"] == "NO_INDEXED_VECTORS_FOR_FILTERS"
    sql, params = conn.calls[-1]
    assert "<=>" in sql and "ts_rank" not in sql and "status = 'PUBLISHED'" in sql
    assert params["model"] == "text-embedding-3-small" and params["admin"] is False
    assert "e.dimensions = :dimensions" in sql and params["dimensions"] == 1536 and "search_text_sha256" in sql
    ar.search(conn, body, STUDENT)
    sql, params = conn.calls[-1]
    assert "plainto_tsquery" in sql and "<=>" not in sql
    assert "tag_type='concept'" in sql and "a.asset_type=:asset_type" in sql
    assert "OFFSET :offset" in sql and params["offset"] == 0
    ar.search(conn, body.model_copy(update={"offset": 40}), STUDENT)
    assert conn.calls[-1][1]["offset"] == 40


@pytest.mark.parametrize("embedding", [
    [0.0] * 1536, [1.0] * 1535, [float("nan")] * 1536, [1e-300] * 1536, [1e308] * 1536,
])
def test_embeddings_require_1536_finite_nonzero_values(embedding):
    with pytest.raises(ValidationError):
        ar.IndexBody(embedding=embedding, search_text_sha256="0" * 64)


def test_stale_index_source_rejected_and_semantic_similarity_unavailable(object_root):
    conn = Connection()
    req = ar.create_request(conn, ar.ArtifactPlan.model_validate(plan_payload()), ADMIN)
    bundle = ar.generate_request(conn, UUID(req["artifact_request_id"]), ADMIN, publish=True)
    bid = UUID(bundle["artifact_bundle_id"])
    with pytest.raises(ar.ArtifactError) as exc:
        ar.index_bundle(conn, bid, ar.IndexBody(
            embedding=[1.0] + [0.0] * 1535, search_text_sha256="0" * 64), ADMIN)
    assert exc.value.status_code == 409
    assert ar.similar(conn, bid, ar.SearchBody(), STUDENT)["reason"] == "SOURCE_NOT_INDEXED"


def test_explicit_provider_indexing_and_semantic_query_use_mock_only(object_root, monkeypatch):
    calls = []

    def embedder(source):
        calls.append(source)
        return [1.0] + [0.0] * 1535

    monkeypatch.setattr(ar, "EMBEDDER", embedder)
    conn = Connection()
    req = ar.create_request(conn, ar.ArtifactPlan.model_validate(plan_payload()), ADMIN)
    bundle = ar.generate_request(conn, UUID(req["artifact_request_id"]), ADMIN, publish=True)
    bid = UUID(bundle["artifact_bundle_id"])
    body = ar.SearchBody(query="tangent circle", generate_embedding=True)
    assert ar.search(conn, body, STUDENT, semantic=True)["reason"] == "NO_INDEXED_VECTORS_FOR_FILTERS"
    assert calls == []  # Even an explicit opt-in must not pay when there is no eligible index.
    index = ar.IndexBody(generate_embedding=True, search_text_sha256=bundle["search_text_sha256"])
    assert ar.index_bundle(conn, bid, index, ADMIN)["embedding_source"] == "PROVIDER_EXPLICIT"
    assert calls == [bundle["search_text"]]
    result = ar.search(conn, body, STUDENT, semantic=True)
    assert result["status"] == "AVAILABLE" and result["mode"] == "SEMANTIC"
    assert calls[-1] == "tangent circle"
    calls.clear()
    assert ar.similar(conn, bid, body, STUDENT)["results"] == []
    assert calls == []  # Similarity uses the indexed source, not a newly embedded query.


def test_provider_failure_is_explicit_and_never_lexical(object_root, monkeypatch):
    conn = Connection()
    req = ar.create_request(conn, ar.ArtifactPlan.model_validate(plan_payload()), ADMIN)
    bundle = ar.generate_request(conn, UUID(req["artifact_request_id"]), ADMIN, publish=True)
    bid = UUID(bundle["artifact_bundle_id"])
    ar.index_bundle(conn, bid, ar.IndexBody(
        embedding=[1.0] + [0.0] * 1535, search_text_sha256=bundle["search_text_sha256"]), ADMIN)

    def unavailable(source):
        raise RuntimeError("provider offline")

    monkeypatch.setattr(ar, "EMBEDDER", unavailable)
    result = ar.search(conn, ar.SearchBody(query="circle", generate_embedding=True), STUDENT, semantic=True)
    assert result["status"] == "UNAVAILABLE" and result["reason"] == "EMBEDDING_UNAVAILABLE"
    assert not any("ts_rank" in sql for sql, _ in conn.calls)
    with pytest.raises(ar.ArtifactError) as exc:
        ar.index_bundle(conn, bid, ar.IndexBody(
            generate_embedding=True, search_text_sha256=bundle["search_text_sha256"]), ADMIN)
    assert exc.value.status_code == 503 and exc.value.code == "EMBEDDING_UNAVAILABLE"


def test_explicit_embedding_routes_through_branch_ai_gateway(monkeypatch):
    from mathbank_rest import runtime_ai

    calls = []
    vector = [1.0] + [0.0] * 1535
    monkeypatch.setattr(ar, "embedding_profile", lambda: {
        "provider": "gateway", "model": "gte-large-en", "dimensions": 1536,
    })

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(data=[SimpleNamespace(embedding=vector)])

    monkeypatch.setattr(runtime_ai, "gateway_client", lambda: SimpleNamespace(
        embeddings=SimpleNamespace(create=create)), raising=False)
    assert ar._openai_embedding("artifact semantic source") == vector
    assert calls == [{"model": "gte-large-en", "input": ["artifact semantic source"]}]


def test_direct_embeddings_use_shared_agent_openai_endpoint_client(monkeypatch):
    from mathbank_rest import runtime_ai

    calls = []
    vector = [1.0] + [0.0] * 1535

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(data=[SimpleNamespace(embedding=vector)])

    monkeypatch.setattr(runtime_ai, "speech_client", lambda: SimpleNamespace(
        embeddings=SimpleNamespace(create=create)))
    monkeypatch.setattr(runtime_ai, "gateway_client",
                        lambda: pytest.fail("direct provider must never call gateway"), raising=False)
    assert ar._openai_embedding("direct agent endpoint") == vector
    assert calls == [{"model": "text-embedding-3-small", "input": ["direct agent endpoint"],
                      "dimensions": 1536}]


def test_gateway_dimension_must_be_verified_before_calls(monkeypatch):
    monkeypatch.setattr(ar, "dotenv_values", lambda *args, **kwargs: {})
    monkeypatch.setenv("ARTIFACT_EMBEDDING_PROVIDER", "gateway")
    monkeypatch.setenv("ARTIFACT_EMBEDDING_MODEL", "gte-large-en")
    monkeypatch.delenv("ARTIFACT_EMBEDDING_DIMENSIONS", raising=False)
    with pytest.raises(ar.ArtifactError) as exc:
        PROFILE_READER()
    assert exc.value.code == "EMBEDDING_CONFIGURATION_UNAVAILABLE"
    monkeypatch.setenv("ARTIFACT_EMBEDDING_DIMENSIONS", "1024")
    assert PROFILE_READER() == {"provider": "gateway", "model": "gte-large-en", "dimensions": 1024}


def test_gateway_dimensions_couple_sql_index_query_and_output_validation(object_root, monkeypatch):
    monkeypatch.setattr(ar, "embedding_profile", lambda: {
        "provider": "gateway", "model": "gte-large-en", "dimensions": 1024,
    })
    monkeypatch.setattr(ar, "EMBEDDER", lambda source: [1.0] + [0.0] * 1023)
    conn = Connection()
    req = ar.create_request(conn, ar.ArtifactPlan.model_validate(plan_payload()), ADMIN)
    bundle = ar.generate_request(conn, UUID(req["artifact_request_id"]), ADMIN, publish=True)
    bid = UUID(bundle["artifact_bundle_id"])
    body = ar.IndexBody(generate_embedding=True, model="gte-large-en", dimensions=1024,
                        search_text_sha256=bundle["search_text_sha256"])
    assert ar.index_bundle(conn, bid, body, ADMIN)["dimensions"] == 1024
    assert conn.embeddings[str(bid)]["dimensions"] == 1024
    result = ar.search(conn, ar.SearchBody(query="circle", generate_embedding=True,
                       model="gte-large-en", dimensions=1024), STUDENT, True)
    assert result["status"] == "AVAILABLE" and result["model"] == "gte-large-en"
    assert ar.search(conn, ar.SearchBody(query_embedding=[1.0] * 1536), STUDENT, True)["reason"] == "EMBEDDING_PROFILE_MISMATCH"
    monkeypatch.setattr(ar, "EMBEDDER", lambda source: [1.0] * 1536)
    with pytest.raises(ar.ArtifactError) as exc:
        ar.index_bundle(conn, bid, body, ADMIN)
    assert exc.value.code == "EMBEDDING_UNAVAILABLE"

@pytest.mark.parametrize("body", [
    {}, {"embedding": [1.0] * 1536, "generate_embedding": True},
])
def test_indexing_requires_exactly_one_explicit_embedding_source(body):
    with pytest.raises(ValidationError):
        ar.IndexBody(**body, search_text_sha256="0" * 64)


def test_request_links_must_reference_an_existing_problem():
    payload = plan_payload()
    payload["linked_problem_id"] = str(uuid4())
    with pytest.raises(ar.ArtifactError) as exc:
        ar.create_request(Connection(), ar.ArtifactPlan.model_validate(payload), STUDENT)
    assert exc.value.code == "INVALID_PROBLEM_REFERENCE"


def test_lineage_and_generate_replay_publication(object_root):
    conn = Connection()
    req = ar.create_request(conn, ar.ArtifactPlan.model_validate(plan_payload()), ADMIN)
    parent = ar.generate_request(conn, UUID(req["artifact_request_id"]), ADMIN)
    assert parent["version"] == 1 and parent["status"] == "DRAFT"
    assert ar.generate_request(conn, UUID(req["artifact_request_id"]), ADMIN, publish=True)["status"] == "PUBLISHED"
    payload = plan_payload()
    payload["parent_bundle_id"] = parent["artifact_bundle_id"]
    payload["title"] = "An extended demonstration"
    req = ar.create_request(conn, ar.ArtifactPlan.model_validate(payload), ADMIN)
    child = ar.generate_request(conn, UUID(req["artifact_request_id"]), ADMIN)
    assert child["version"] == 2 and child["parent_bundle_id"] == parent["artifact_bundle_id"]
    lineage = [params for sql, params in conn.calls if sql.startswith("INSERT INTO artifact_runtime.artifact_lineage")]
    assert lineage[-1]["parent_bundle_id"] == parent["artifact_bundle_id"]
    assert len(lineage[-1]["hash"]) == 64

def test_migration_is_additive_independent_and_metadata_only():
    root = Path(__file__).resolve().parents[2]
    sql = (root / "mathbank-db/sql/022_artifact_runtime.sql").read_text()
    assert "CREATE SCHEMA IF NOT EXISTS artifact_runtime" in sql
    assert "vector_dims(embedding) = dimensions" in sql and "embedding vector NOT NULL" in sql
    assert "REFERENCES learner.student_profile" in sql and "REFERENCES core.problem" in sql
    assert "attempt_media." not in sql and "bytea" not in sql.lower()
