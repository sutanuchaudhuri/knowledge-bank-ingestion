"""WP1 actor + audit fixes (VIS-F02, VIS-F04 widget reads, ART-F03, KNP-F06) — offline, no database."""
from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from test_artifact_runtime import Connection as ArtifactConnection
from test_artifact_runtime import plan_payload

from mathbank_rest import artifact_runtime as ar
from mathbank_rest import security
from mathbank_rest.config import settings
from mathbank_rest.db import pedagogy_admin as pdb
from mathbank_rest.main import app
from mathbank_rest.routers import artifacts as artifacts_router
from mathbank_rest.routers import fluid
from mathbank_rest.routers import interaction_templates as templates
from mathbank_rest.security import Actor

client = TestClient(app)
KEY = {"X-Admin-Api-Key": settings.admin_api_key}
SERVICE = "service:admin-key"
STAFF = Actor("staff", "staff:42", "Alice", frozenset({"publish", "review"}))


@pytest.fixture(autouse=True)
def _reset():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def object_root(monkeypatch):
    root = Path(__file__).parent / f".artifact-objects-{uuid4().hex}"
    monkeypatch.setenv("MATHBANK_OBJECT_BACKEND", "filesystem")
    monkeypatch.setenv("MATHBANK_OBJECT_ROOT", str(root))
    yield root
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def embedding_profile(monkeypatch):
    monkeypatch.setattr(ar, "embedding_profile", lambda: {
        "provider": "test", "model": "text-embedding-3-small", "dimensions": 1536})


def as_staff():
    app.dependency_overrides[security.require_admin_api_key] = lambda: STAFF


class Res:
    def __init__(self, value=None, rowcount=1):
        self.value = value
        self.rowcount = rowcount

    def mappings(self):
        return self

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value

    one_or_none = scalar_one_or_none
    one = scalar_one

    def first(self):
        return self.value

    def scalars(self):
        return list(self.value or [])


class Conn:
    """Substring-matched fake connection: the first rule whose key appears in the SQL answers."""

    def __init__(self, rules=()):
        self.rules = list(rules)
        self.calls: list[tuple[str, dict]] = []
        self.connection = MagicMock()

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        self.calls.append((sql, params or {}))
        for needle, result in self.rules:
            if needle in sql:
                return result(sql, params) if callable(result) else result
        return Res()

    def sql(self, needle):
        return [(s, p) for s, p in self.calls if needle in s]


class FakeEngine:
    def __init__(self, conn):
        self.conn = conn

    @contextmanager
    def begin(self):
        yield self.conn

    connect = begin


def audit_recorder(monkeypatch, *modules):
    calls = []

    def record(conn, actor_type, actor_id, action, entity_type, entity_id, **kwargs):
        calls.append({"conn": conn, "actor_type": actor_type, "actor_id": actor_id, "action": action,
                      "entity_type": entity_type, "entity_id": entity_id, **kwargs})
        return "req"

    for module in modules:
        monkeypatch.setattr(module, "record_audit_event", record)
    return calls


# ── VIS-F02: template publish ────────────────────────────────────────────────────────────────────────────────────

VERSION_ID = str(uuid4())


def publish_conn(status="DRAFT", updated=1):
    return Conn([
        ("FOR UPDATE", Res(status)),
        ("UPDATE visual.interaction_template_version", Res(rowcount=updated)),
        ("SELECT status FROM visual.interaction_template_version", Res(status)),
    ])


def use_engine(monkeypatch, module, conn):
    monkeypatch.setattr(module, "engine", FakeEngine(conn))


def test_template_publish_records_service_actor_and_audit(monkeypatch):
    conn = publish_conn()
    use_engine(monkeypatch, templates, conn)
    monkeypatch.setattr(templates.interaction_validators, "validate_interaction_template_version",
                        lambda c, i: [])
    audits = audit_recorder(monkeypatch, templates)
    response = client.post(f"/v1/admin/interaction-templates/versions/{VERSION_ID}/publish", headers=KEY)
    assert response.status_code == 200 and response.json()["status"] == "PUBLISHED"
    (sql, params), = conn.sql("UPDATE visual.interaction_template_version")
    assert "reviewed_by=:actor" in sql and params["actor"] == SERVICE
    assert audits == [{
        "conn": conn, "actor_type": "ADMIN", "actor_id": SERVICE, "action": "PUBLISH",
        "entity_type": "interaction_template_version", "entity_id": VERSION_ID,
        "before_state": {"status": "DRAFT"}, "after_state": {"status": "PUBLISHED"},
    }]


def test_template_publish_records_staff_actor(monkeypatch):
    as_staff()
    conn = publish_conn()
    use_engine(monkeypatch, templates, conn)
    monkeypatch.setattr(templates.interaction_validators, "validate_interaction_template_version",
                        lambda c, i: [])
    audits = audit_recorder(monkeypatch, templates)
    assert client.post(f"/v1/admin/interaction-templates/versions/{VERSION_ID}/publish").status_code == 200
    assert conn.sql("UPDATE visual.interaction_template_version")[0][1]["actor"] == "staff:42"
    assert audits[0]["actor_id"] == "staff:42"


def test_template_publish_wrong_state_is_409_and_not_audited(monkeypatch):
    conn = publish_conn(status="PUBLISHED", updated=0)
    use_engine(monkeypatch, templates, conn)
    monkeypatch.setattr(templates.interaction_validators, "validate_interaction_template_version",
                        lambda c, i: [])
    audits = audit_recorder(monkeypatch, templates)
    response = client.post(f"/v1/admin/interaction-templates/versions/{VERSION_ID}/publish", headers=KEY)
    assert response.status_code == 409 and audits == []


def test_template_publish_unknown_version_is_404(monkeypatch):
    use_engine(monkeypatch, templates, Conn([("SELECT status", Res(None))]))
    audits = audit_recorder(monkeypatch, templates)
    response = client.post(f"/v1/admin/interaction-templates/versions/{VERSION_ID}/publish", headers=KEY)
    assert response.status_code == 404 and audits == []


# ── VIS-F02: instance approve ────────────────────────────────────────────────────────────────────────────────────

INSTANCE_ID = str(uuid4())


def test_instance_approve_sets_approved_by_and_audits(monkeypatch):
    as_staff()
    conn = Conn([("FOR UPDATE", Res("PENDING_REVIEW")), ("UPDATE visual.interaction_instance", Res(rowcount=1)),
                 ("SELECT review_status", Res("PENDING_REVIEW"))])
    use_engine(monkeypatch, templates, conn)
    monkeypatch.setattr(templates.interaction_validators, "validate_interaction_instance", lambda c, i: [])
    audits = audit_recorder(monkeypatch, templates)
    response = client.post(f"/v1/admin/interaction-templates/instances/{INSTANCE_ID}/approve")
    assert response.status_code == 200 and response.json()["status"] == "APPROVED"
    (sql, params), = conn.sql("UPDATE visual.interaction_instance")
    assert "approved_by=:actor" in sql and params["actor"] == "staff:42"
    assert audits == [{
        "conn": conn, "actor_type": "ADMIN", "actor_id": "staff:42", "action": "APPROVE",
        "entity_type": "interaction_instance", "entity_id": INSTANCE_ID,
        "before_state": {"review_status": "PENDING_REVIEW"}, "after_state": {"review_status": "APPROVED"},
    }]


def test_instance_approve_already_approved_is_409(monkeypatch):
    conn = Conn([("FOR UPDATE", Res("APPROVED")), ("UPDATE visual.interaction_instance", Res(rowcount=0)),
                 ("SELECT review_status", Res("APPROVED"))])
    use_engine(monkeypatch, templates, conn)
    monkeypatch.setattr(templates.interaction_validators, "validate_interaction_instance", lambda c, i: [])
    audits = audit_recorder(monkeypatch, templates)
    response = client.post(f"/v1/admin/interaction-templates/instances/{INSTANCE_ID}/approve", headers=KEY)
    assert response.status_code == 409 and audits == []


# ── VIS-F02: scene approve / promote / create-instance ───────────────────────────────────────────────────────────

SCENE_ID = str(uuid4())


def test_scene_approve_ignores_client_name_and_uses_actor(monkeypatch):
    as_staff()
    conn = Conn([("FOR UPDATE", Res("DRAFT")), ("UPDATE visual.scene_spec", Res(rowcount=1)),
                 ("SELECT status", Res("DRAFT"))])
    use_engine(monkeypatch, templates, conn)
    monkeypatch.setattr(templates.interaction_validators, "validate_scene_spec", lambda c, i: [])
    asset = MagicMock()
    monkeypatch.setattr(templates, "approve_scene_and_validate_asset", asset)
    audits = audit_recorder(monkeypatch, templates)
    response = client.post(f"/v1/admin/interaction-templates/scenes/{SCENE_ID}/approve?approved_by=mallory")
    assert response.status_code == 200
    (_, params), = conn.sql("UPDATE visual.scene_spec")
    assert params == {"id": SCENE_ID, "approved_by": "staff:42"}
    asset.assert_called_once_with(conn, SCENE_ID, "staff:42")
    assert [(a["actor_id"], a["action"], a["entity_type"], a["entity_id"]) for a in audits] == [
        ("staff:42", "APPROVE", "scene_spec", SCENE_ID)]


def test_scene_approve_wrong_state_is_409_and_does_not_validate_the_asset(monkeypatch):
    conn = Conn([("FOR UPDATE", Res("APPROVED")), ("UPDATE visual.scene_spec", Res(rowcount=0)),
                 ("SELECT status", Res("APPROVED"))])
    use_engine(monkeypatch, templates, conn)
    monkeypatch.setattr(templates.interaction_validators, "validate_scene_spec", lambda c, i: [])
    asset = MagicMock()
    monkeypatch.setattr(templates, "approve_scene_and_validate_asset", asset)
    audits = audit_recorder(monkeypatch, templates)
    response = client.post(f"/v1/admin/interaction-templates/scenes/{SCENE_ID}/approve", headers=KEY)
    assert response.status_code == 409 and audits == []
    asset.assert_not_called()


def test_scene_approve_unknown_scene_is_404(monkeypatch):
    use_engine(monkeypatch, templates, Conn([("SELECT status", Res(None))]))
    assert client.post(f"/v1/admin/interaction-templates/scenes/{SCENE_ID}/approve",
                       headers=KEY).status_code == 404


def test_scene_promote_and_create_instance_ignore_client_created_by(monkeypatch):
    as_staff()
    promote = MagicMock(return_value="scene-1")
    monkeypatch.setattr(templates, "promote_render_job", promote)
    response = client.post("/v1/admin/interaction-templates/scenes/promote",
                           json={"render_job_id": "job-1", "canonical_code": "C1", "created_by": "mallory"})
    assert response.status_code == 200
    promote.assert_called_once_with(render_job_id="job-1", canonical_code="C1", created_by="staff:42")

    use_engine(monkeypatch, templates, Conn())
    create = MagicMock(return_value="inst-1")
    monkeypatch.setattr(templates, "create_video_explainer_instance", create)
    response = client.post(f"/v1/admin/interaction-templates/scenes/{SCENE_ID}/create-instance",
                           json={"canonical_code": "C1", "title": "T", "learning_objective": "O",
                                 "created_by": "mallory"})
    assert response.status_code == 200
    assert create.call_args.kwargs["created_by"] == "staff:42"


def test_promotion_service_audits_promote_and_instance_creation(monkeypatch):
    from mathbank_rest import scene_spec_promotion as promotion

    audits = audit_recorder(monkeypatch, promotion)
    job = MagicMock(status_code=200)
    job.json.return_value = {"status": "DONE", "scene_spec_json": {"scene_key": "k"}}
    monkeypatch.setattr(promotion.httpx, "get", lambda *a, **k: job)
    monkeypatch.setattr(promotion.httpx, "post", lambda *a, **k: MagicMock())
    monkeypatch.setattr(promotion.object_store, "put_bytes",
                        lambda data, ext: {"object_key": "k", "sha256": "h", "size_bytes": 1})
    ids = iter(["asset-1", "scene-1"])
    conn = Conn([("SELECT scene_spec_id FROM visual.scene_spec", Res(None)),
                 ("MAX(version)", Res(1)),
                 ("INSERT INTO visual.", lambda sql, p: Res(next(ids)))])
    monkeypatch.setattr(promotion, "engine", FakeEngine(conn))
    assert promotion.promote_render_job(render_job_id="job-1", canonical_code="C1",
                                        created_by="staff:42") == "scene-1"
    assert audits[0]["actor_id"] == "staff:42" and audits[0]["action"] == "PROMOTE"
    assert audits[0]["entity_type"] == "scene_spec" and audits[0]["entity_id"] == "scene-1"

    audits.clear()
    monkeypatch.setattr(promotion, "_ensure_video_explainer_template", lambda c, by: "ver-1")
    conn = Conn([("FROM visual.scene_spec", Res({"status": "APPROVED", "scene_json": {"scene_key": "k"}})),
                 ("INSERT INTO visual.interaction_instance", Res("inst-1"))])
    assert promotion.create_video_explainer_instance(
        conn, scene_spec_id="scene-1", canonical_code="C2", title="T", learning_objective="O",
        created_by="staff:42") == "inst-1"
    assert [(a["actor_id"], a["action"], a["entity_type"], a["entity_id"]) for a in audits] == [
        ("staff:42", "CREATE", "interaction_instance", "inst-1")]


# ── VIS-F02: widget review ───────────────────────────────────────────────────────────────────────────────────────

SPEC_ID = str(uuid4())


def review_conn(lifecycle="VALIDATED", updated=1):
    return Conn([("FOR UPDATE", Res((lifecycle,))), ("UPDATE visual.widget_spec", Res(rowcount=updated))])


def test_widget_review_uses_actor_not_client_reviewer_and_audits(monkeypatch):
    as_staff()
    conn = review_conn()
    use_engine(monkeypatch, fluid, conn)
    audits = audit_recorder(monkeypatch, fluid)
    response = client.post(f"/v1/widgets/specs/{SPEC_ID}/review",
                           json={"decision": "NOMINATE", "reviewer": "mallory"})
    assert response.status_code == 200 and response.json()["lifecycle"] == "PROMOTION_CANDIDATE"
    (_, params), = conn.sql("UPDATE visual.widget_spec")
    assert params["r"] == "staff:42"
    assert audits == [{
        "conn": conn, "actor_type": "ADMIN", "actor_id": "staff:42", "action": "NOMINATE",
        "entity_type": "widget_spec", "entity_id": SPEC_ID,
        "before_state": {"lifecycle": "VALIDATED"},
        "after_state": {"lifecycle": "PROMOTION_CANDIDATE", "persistence": "unchanged"},
    }]


def test_widget_review_service_key_is_recorded_not_admin(monkeypatch):
    conn = review_conn("PROMOTION_CANDIDATE")
    use_engine(monkeypatch, fluid, conn)
    audits = audit_recorder(monkeypatch, fluid)
    response = client.post(f"/v1/widgets/specs/{SPEC_ID}/review", json={"decision": "PROMOTE"}, headers=KEY)
    assert response.status_code == 200 and response.json()["persistence"] == "STATIC"
    assert conn.sql("UPDATE visual.widget_spec")[0][1]["r"] == SERVICE
    assert audits[0]["actor_id"] == SERVICE and audits[0]["action"] == "PROMOTE"


@pytest.mark.parametrize("lifecycle,decision,status", [
    ("VALIDATED", "PROMOTE", 409), ("REJECTED", "REJECT", 409), (None, "REJECT", 404)])
def test_widget_review_conflicts_do_not_report_success(monkeypatch, lifecycle, decision, status):
    conn = Conn([("FOR UPDATE", Res((lifecycle,) if lifecycle else None))])
    use_engine(monkeypatch, fluid, conn)
    audits = audit_recorder(monkeypatch, fluid)
    response = client.post(f"/v1/widgets/specs/{SPEC_ID}/review", json={"decision": decision}, headers=KEY)
    assert response.status_code == status and audits == [] and not conn.sql("UPDATE visual.widget_spec")


def test_widget_review_update_matching_no_row_is_409(monkeypatch):
    use_engine(monkeypatch, fluid, review_conn(updated=0))
    audits = audit_recorder(monkeypatch, fluid)
    response = client.post(f"/v1/widgets/specs/{SPEC_ID}/review", json={"decision": "NOMINATE"}, headers=KEY)
    assert response.status_code == 409 and audits == []


def test_widget_store_ignores_x_actor_id_header(monkeypatch):
    as_staff()
    use_engine(monkeypatch, fluid, Conn())
    store = MagicMock(return_value={"widget_spec_id": "w"})
    monkeypatch.setattr(fluid.live_runtime, "store_widget_spec", store)
    response = client.post("/v1/widgets/specs", json={"spec": {}, "source_type": "INSTRUCTOR_CREATED"},
                           headers={"X-Actor-Id": "mallory"})
    assert response.status_code == 201
    assert store.call_args.args[3] == "staff:42"


# ── VIS-F04: widget spec reads are scoped to the learner's sessions ─────────────────────────────────────────────

LEARNER = uuid4()
SESSION = str(uuid4())


def bearer(student_id: UUID) -> dict:
    return {"Authorization": "Bearer " + security.create_access_token(student_id)}


def spec_row(persistence="SESSION", lifecycle="SHOWN", session=SESSION):
    return {"widget_spec_id": SPEC_ID, "widget_type": "POLL_RESULT", "lifecycle": lifecycle,
            "persistence": persistence, "live_session_id": session,
            "spec": {"config": {"correct_option": "B", "reveal": True}},
            "created_by": "instructor-1", "reviewed_by": "staff:9", "reviewed_at": None}


def spec_conn(row, member):
    return Conn([("FROM visual.widget_spec", Res(row)), ("FROM live.participant", Res((1,) if member else None))])


def test_learner_cannot_read_another_sessions_widget(monkeypatch):
    conn = spec_conn(spec_row(), member=False)
    use_engine(monkeypatch, fluid, conn)
    response = client.get(f"/v1/widgets/specs/{SPEC_ID}", headers=bearer(LEARNER))
    assert response.status_code == 403
    assert "correct_option" not in response.text
    (_, params), = conn.sql("FROM live.participant")
    assert params == {"s": SESSION, "st": str(LEARNER)}


def test_learner_participant_reads_session_widget_without_staff_identities(monkeypatch):
    use_engine(monkeypatch, fluid, spec_conn(spec_row(), member=True))
    response = client.get(f"/v1/widgets/specs/{SPEC_ID}", headers=bearer(LEARNER))
    assert response.status_code == 200
    body = response.json()
    assert body["spec"]["config"]["correct_option"] == "B"
    assert not {"created_by", "reviewed_by", "reviewed_at"} & set(body)


def test_learner_reads_static_widget_without_membership(monkeypatch):
    conn = spec_conn(spec_row(persistence="STATIC"), member=False)
    use_engine(monkeypatch, fluid, conn)
    assert client.get(f"/v1/widgets/specs/{SPEC_ID}", headers=bearer(LEARNER)).status_code == 200
    assert not conn.sql("FROM live.participant")


def test_learner_cannot_read_widget_without_a_session(monkeypatch):
    use_engine(monkeypatch, fluid, spec_conn(spec_row(session=None), member=True))
    assert client.get(f"/v1/widgets/specs/{SPEC_ID}", headers=bearer(LEARNER)).status_code == 403


def test_learner_gets_404_for_rejected_widget(monkeypatch):
    use_engine(monkeypatch, fluid, spec_conn(spec_row(persistence="STATIC", lifecycle="REJECTED"), member=True))
    assert client.get(f"/v1/widgets/specs/{SPEC_ID}", headers=bearer(LEARNER)).status_code == 404


def test_staff_reads_any_widget_with_full_row(monkeypatch):
    use_engine(monkeypatch, fluid, spec_conn(spec_row(), member=False))
    response = client.get(f"/v1/widgets/specs/{SPEC_ID}", headers=KEY)
    assert response.status_code == 200 and response.json()["created_by"] == "instructor-1"


# ── ART-F03: artifact generate / publish / index ─────────────────────────────────────────────────────────────────

def audit_rows(conn):
    return [p for s, p in conn.calls if s.startswith("INSERT INTO audit.action_log")]


def test_artifact_lifecycle_records_actor_and_audit_rows(object_root, embedding_profile):
    conn = ArtifactConnection()
    admin = {"role": "ADMIN", "student_id": None, "actor_id": "staff:42"}
    request = ar.create_request(conn, ar.ArtifactPlan.model_validate(plan_payload("ALGEBRA")), admin)
    assert conn.requests[request["artifact_request_id"]]["created_by"] == "staff:42"
    request_id = UUID(request["artifact_request_id"])
    bundle = ar.generate_request(conn, request_id, admin, object_keys=[])
    bundle_id = bundle["artifact_bundle_id"]
    ar.publish_bundle(conn, UUID(bundle_id), admin)
    ar.index_bundle(conn, UUID(bundle_id), ar.IndexBody(
        embedding=[1.0] + [0.0] * 1535, search_text_sha256=bundle["search_text_sha256"]), admin)
    rows = audit_rows(conn)
    assert [(r["action"], r["actor_type"], r["actor_id"], r["entity_type"], r["entity_id"]) for r in rows] == [
        ("GENERATE", "ADMIN", "staff:42", "artifact_bundle", bundle_id),
        ("PUBLISH", "ADMIN", "staff:42", "artifact_bundle", bundle_id),
        ("INDEX", "ADMIN", "staff:42", "artifact_bundle", bundle_id),
    ]
    assert '"status":"DRAFT"' in rows[0]["after"] and '"status":"DRAFT"' in rows[1]["before"]
    assert '"status":"PUBLISHED"' in rows[1]["after"]


def test_artifact_failed_publish_writes_no_audit_row(object_root):
    conn = ArtifactConnection()
    with pytest.raises(ar.ArtifactError):
        ar.publish_bundle(conn, uuid4(), {"role": "ADMIN", "student_id": None, "actor_id": "staff:42"})
    assert audit_rows(conn) == []


@pytest.mark.parametrize("path,body", [
    ("requests/{id}/generate", {"publish": False}),
    ("bundles/{id}/publish", None),
    ("bundles/{id}/index", {"search_text_sha256": "a" * 64, "model": "m", "dimensions": 1536,
                            "embedding": [1.0] * 1536}),
])
def test_artifact_routes_pass_the_real_actor(monkeypatch, path, body):
    seen = {}

    def capture(conn, *args, **kwargs):
        seen["actor"] = next(a for a in args if isinstance(a, dict) and "role" in a)
        return {}

    for name in ("generate_request", "publish_bundle", "index_bundle"):
        monkeypatch.setattr(artifacts_router.runtime, name, capture)
    monkeypatch.setattr(artifacts_router, "engine", FakeEngine(Conn()))
    target = f"/v1/artifacts/{path.format(id=uuid4())}"
    assert client.post(target, json=body, headers=KEY).status_code == 200
    assert seen["actor"] == {"role": "ADMIN", "student_id": None, "actor_id": SERVICE}
    app.dependency_overrides.clear()
    as_staff()
    assert client.post(target, json=body).status_code == 200
    assert seen["actor"]["actor_id"] == "staff:42"


def test_staff_or_student_exposes_service_actor_id_and_learner_still_cannot_publish(monkeypatch):
    assert fluid.staff_or_student(None, settings.admin_api_key) == {
        "role": "ADMIN", "student_id": None, "actor_id": SERVICE}
    monkeypatch.setattr(artifacts_router, "engine", FakeEngine(Conn()))
    assert client.post(f"/v1/artifacts/bundles/{uuid4()}/publish", headers=bearer(LEARNER)).status_code in (401, 403)


# ── KNP-F06: pedagogy governance identity ────────────────────────────────────────────────────────────────────────

PKEY = {"skill_id": str(uuid4())}
PBODY = {"kind": "skill", "key": PKEY, "expected_revision": "a" * 64, "review_status": "REJECTED",
         "note": "Reviewed against the source text."}


def test_reviewer_constant_is_gone():
    assert not hasattr(pdb, "REVIEWER")


def test_change_decision_records_actor_as_reviewer_and_audits(monkeypatch):
    before = {"skill_id": PKEY["skill_id"], "review_status": "PENDING"}
    after = {**before, "review_status": "REJECTED"}
    conn = Conn([("FOR UPDATE", Res(before)), ("SELECT to_jsonb", Res(after))])
    audits = audit_recorder(monkeypatch, pdb)
    result = pdb.change_decision(conn, "skill", PKEY, pdb.revision(before), "REJECTED", "Because.", "staff:42")
    assert result == after
    (_, params), = conn.sql("INSERT INTO knowledge.pedagogy_review_event")
    assert params["reviewer"] == "staff:42"
    assert [(a["actor_type"], a["actor_id"], a["action"], a["entity_type"]) for a in audits] == [
        ("ADMIN", "staff:42", "PEDAGOGY_REVIEW", "skill")]
    assert audits[0]["after_state"]["review_status"] == "REJECTED"
    assert audits[0]["before_state"]["review_status"] == "PENDING"


def test_review_route_passes_actor_through(monkeypatch):
    decide = MagicMock(return_value={"review_status": "REJECTED"})
    monkeypatch.setattr(pdb, "decide", decide)
    assert client.post("/v1/admin/pedagogy/review", json=PBODY, headers=KEY).status_code == 200
    assert decide.call_args.args[-1] == SERVICE
    as_staff()
    assert client.post("/v1/admin/pedagogy/review", json={**PBODY, "reviewer": "mallory"}).status_code == 422
    assert client.post("/v1/admin/pedagogy/review", json=PBODY).status_code == 200
    assert decide.call_args.args[-1] == "staff:42"


def test_bulk_starter_edit_and_publish_routes_pass_actor(monkeypatch):
    as_staff()
    ops = {name: MagicMock(return_value={}) for name in ("bulk_decide", "approve_starter", "edit", "publish")}
    for name, op in ops.items():
        monkeypatch.setattr(pdb, name, op)
    item = {"kind": "skill", "key": PKEY, "expected_revision": "a" * 64}
    note = "Reviewed against the source text."
    assert client.post("/v1/admin/pedagogy/bulk-review",
                       json={"items": [item], "review_status": "REVIEWED", "note": note}).status_code == 200
    assert client.post("/v1/admin/pedagogy/approve-starter",
                       json={"expected_fingerprint": "b" * 64, "note": note}).status_code == 200
    assert client.post("/v1/admin/pedagogy/edit", json={
        "kind": "skill", "key": PKEY, "expected_revision": "a" * 64, "changes": {"name": "n"},
        "note": note}).status_code == 200
    assert client.post("/v1/admin/pedagogy/publish", json={"expected_fingerprint": "b" * 64}).status_code == 200
    assert all(op.call_args.args[-1] == "staff:42" for op in ops.values())


def test_apply_bulk_forwards_actor_to_every_decision(monkeypatch):
    changes = MagicMock()
    monkeypatch.setattr(pdb, "change_decision", changes)
    monkeypatch.setattr(pdb, "validate_graph", MagicMock())
    item = {"kind": "skill", "key": PKEY, "expected_revision": "a" * 64}
    pdb.apply_bulk(MagicMock(), [item], "REVIEWED", "note text here", "staff:42")
    assert changes.call_args.args[-1] == "staff:42"


def publish_fixture(monkeypatch, conn):
    projector = MagicMock()
    projector.project_pedagogy.return_value = (3, 4)
    monkeypatch.setattr(pdb, "operator_module", lambda name: projector if name == "projector" else MagicMock())
    monkeypatch.setattr(pdb, "engine", FakeEngine(conn))
    monkeypatch.setattr(pdb, "driver", MagicMock())
    monkeypatch.setattr(pdb, "lock_authoring", lambda c: None)
    monkeypatch.setattr(pdb, "validate_graph", lambda c: None)
    monkeypatch.setattr(pdb, "fingerprint", lambda c: "fp")
    return audit_recorder(monkeypatch, pdb)


def test_publish_records_actor_as_publisher_and_audits(monkeypatch):
    conn = Conn([("INSERT INTO knowledge.pedagogy_publication", Res({"publication_id": "pub-1"}))])
    audits = publish_fixture(monkeypatch, conn)
    result = pdb.publish("fp", ["P1"], "staff:42")
    assert result["publication"] == {"publication_id": "pub-1"}
    (_, params), = conn.sql("INSERT INTO knowledge.pedagogy_publication")
    assert params["publisher"] == "staff:42"
    assert [(a["actor_type"], a["actor_id"], a["action"], a["entity_type"], a["entity_id"]) for a in audits] == [
        ("ADMIN", "staff:42", "PEDAGOGY_PUBLISH", "pedagogy_publication", "pub-1")]
    assert audits[0]["after_state"]["skills_projected"] == 3


def test_anonymous_publication_is_recorded_as_anonymous_not_admin_key(monkeypatch):
    conn = Conn([("INSERT INTO knowledge.pedagogy_publication", Res({"publication_id": "pub-2"}))])
    audits = publish_fixture(monkeypatch, conn)
    pdb.publish("fp", ["P1"])
    (_, params), = conn.sql("INSERT INTO knowledge.pedagogy_publication")
    assert params["publisher"] == "anonymous"
    assert (audits[0]["actor_type"], audits[0]["actor_id"]) == ("SYSTEM", "anonymous")
    assert "shared-admin-api-key" not in repr(conn.calls)


def test_enrichment_publication_path_defaults_to_anonymous(monkeypatch):
    from mathbank_rest import publication

    seen = {}
    monkeypatch.setattr(publication, "engine", FakeEngine(Conn()))
    monkeypatch.setattr(publication, "fingerprint", lambda c: "fp")
    monkeypatch.setattr(publication, "publish", lambda *a, **k: seen.update(args=a, kwargs=k))
    publication.publish_current(["P1"])
    assert "staff" not in repr(seen) and "admin" not in repr(seen)
    assert pdb.publish.__defaults__[-1] == "anonymous"


def test_edit_records_actor_and_audits(monkeypatch):
    before = {"skill_id": PKEY["skill_id"], "name": "old"}
    after = {**before, "name": "new"}
    conn = Conn([("FOR UPDATE", Res(before)), ("SELECT to_jsonb", Res(after))])
    monkeypatch.setattr(pdb, "engine", FakeEngine(conn))
    monkeypatch.setattr(pdb, "lock_authoring", lambda c: None)
    monkeypatch.setattr(pdb, "validate_graph", lambda c: None)
    audits = audit_recorder(monkeypatch, pdb)
    pdb.edit("skill", PKEY, pdb.revision(before), {"name": "new"}, "Correcting the name.", "staff:42")
    (_, params), = conn.sql("INSERT INTO knowledge.pedagogy_review_event")
    assert params["reviewer"] == "staff:42"
    assert [(a["actor_id"], a["action"], a["entity_type"]) for a in audits] == [
        ("staff:42", "PEDAGOGY_EDIT", "skill")]
    assert audits[0]["after_state"]["changes"] == {"name": "new"}


def test_reclassify_route_audits_actor(monkeypatch):
    from mathbank_rest import enrichment

    as_staff()
    monkeypatch.setattr(enrichment, "enrich_problem", lambda code, force: {"status": "DONE"})
    conn = Conn()
    monkeypatch.setattr(pdb, "engine", FakeEngine(conn))
    audits = audit_recorder(monkeypatch, pdb)
    assert client.post("/v1/admin/pedagogy/reclassify", json={"problem_code": "P-1"}).status_code == 200
    assert [(a["actor_id"], a["action"], a["entity_type"], a["entity_id"]) for a in audits] == [
        ("staff:42", "PEDAGOGY_RECLASSIFY", "problem", "P-1")]
