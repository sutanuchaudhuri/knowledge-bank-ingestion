"""Core router mounted through existing real auth; deterministic memory test double."""

from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from geometry_scene.errors import VersionConflict
from geometry_scene.repository import ReplayConflict, SceneNotFound
from geometry_scene.service import apply_delta, create_scene
from test_geometry_storage import PAYLOAD

from mathbank_rest import security
from mathbank_rest.geometry_storage import GeometryStorageError, get_geometry_repository
from mathbank_rest.routers import geometry_scenes


class MemoryRepository:
    def __init__(self):
        self.saved = {}
        self.receipts = {}
        self.runs = {}

    def _replay(self, owner, key, request):
        if key and (owner, key) in self.receipts:
            before, frame = self.receipts[owner, key]
            if before != request:
                raise ReplayConflict("different request")
            return frame, True

    def _save(self, owner, key, request, frame):
        self.saved[owner, frame.scene_state.scene_id, frame.version] = frame
        if key:
            self.receipts[owner, key] = request, frame
        return frame, False

    def create(self, request, owner, key=None):
        replay = self._replay(owner, key, request)
        if replay:
            return replay
        return self._save(owner, key, request, create_scene(request))

    def apply(self, scene_id, delta, owner, key=None):
        replay = self._replay(owner, key, delta)
        if replay:
            return replay
        previous = self.current(scene_id, owner)
        if previous.version != delta.expected_version:
            raise VersionConflict("stale version")
        return self._save(owner, key, delta, apply_delta(previous, delta))

    def read(self, scene_id, version, owner):
        try:
            return self.saved[owner, scene_id, version]
        except KeyError:
            raise SceneNotFound("scene/version not found") from None

    def current(self, scene_id, owner):
        versions = [v for o, s, v in self.saved if o == owner and s == scene_id]
        if not versions:
            raise SceneNotFound("scene not found")
        return self.read(scene_id, max(versions), owner)

    def frames(self, scene_id, owner):
        self.current(scene_id, owner)
        return [{"version": v} for o, s, v in self.saved if o == owner and s == scene_id]

    def read_run(self, owner, run_id):
        if (owner, run_id) not in self.runs:
            raise SceneNotFound("run not found")
        return self.runs[owner, run_id]

    def review_run(self, owner, run_id, review):
        self.read_run(owner, run_id)
        return {"review": review}

    def list_runs(self, owner, limit=50):
        return [{"run_id": run} for o, run in self.runs if o == owner][:limit]


@pytest.fixture
def api(monkeypatch):
    repo = MemoryRepository()
    app = FastAPI()
    app.include_router(geometry_scenes.router)
    app.dependency_overrides[get_geometry_repository] = lambda: repo
    monkeypatch.setattr(security.settings, "admin_api_key", "geometry-test-admin")

    def decode(token):
        if token in {"learner-a", "learner-b"}:
            return token
        raise ValueError("bad token")

    monkeypatch.setattr(security, "decode_access_token", decode)
    return TestClient(app), repo


AUTH = {"Authorization": "Bearer learner-a"}
ADMIN = {"X-Admin-Api-Key": "geometry-test-admin"}
BASE = "/v1/geometry-scenes"


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("POST", "", PAYLOAD),
        ("POST", "/geometry_test/deltas", {"expected_version": 0}),
        ("GET", "/geometry_test", None),
        ("GET", "/geometry_test/versions/0", None),
        ("GET", "/geometry_test/versions/0/render", None),
        ("POST", "/geometry_test/versions/0/validate", None),
        ("GET", "/geometry_test/frames", None),
        ("GET", "/debug/runs/run?owner=student:learner-a", None),
        ("GET", "/debug/runs?owner=student:learner-a", None),
        ("POST", "/debug/runs/run/review?owner=student:learner-a", {"decision": "REJECTED"}),
    ],
)
def test_every_path_requires_existing_auth(api, method, path, payload):
    client, repo = api
    assert client.request(method, BASE + path, json=payload).status_code == 401
    assert not repo.saved


def test_seven_paths_cas_receipts_and_safe_headers(api):
    client, repo = api
    headers = {**AUTH, "Idempotency-Key": "create"}
    response = client.post(BASE, json=PAYLOAD, headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert not body["replayed"]
    assert "all_positions" not in body["scene_state"]["solver_diagnostics"]
    assert repo.read("geometry_test", 0, "learner-a").scene_state.solver_diagnostics["all_positions"]
    assert client.post(BASE, json=PAYLOAD, headers=headers).json()["replayed"]
    changed = {**PAYLOAD, "seed": 19}
    assert client.post(BASE, json=changed, headers=headers).status_code == 409
    render = client.get(body["frame_asset"]["content_path"], headers=AUTH)
    assert render.status_code == 200 and render.text == body["svg"]
    assert render.headers["content-type"].startswith("image/svg+xml")
    assert render.headers["cache-control"] == "private, no-store"
    assert render.headers["x-content-type-options"] == "nosniff"
    assert render.headers["content-security-policy"] == "default-src 'none'; sandbox"
    path = BASE + "/geometry_test"
    assert client.get(path, headers=AUTH).json()["version"] == 0
    assert client.get(path + "/versions/0", headers=AUTH).json()["version"] == 0
    assert client.post(path + "/versions/0/validate", headers=AUTH).json()["valid"]
    headers = {**AUTH, "Idempotency-Key": "delta"}
    delta = {"expected_version": 0}
    assert client.post(path + "/deltas", json=delta, headers=headers).json()["version"] == 1
    assert client.post(path + "/deltas", json=delta, headers=headers).json()["replayed"]
    assert client.post(path + "/deltas", json=delta, headers=AUTH).status_code == 409
    assert len(client.get(path + "/frames", headers=AUTH).json()["frames"]) == 2
    assert repo.read("geometry_test", 0, "learner-a").version == 0


@pytest.mark.parametrize("status", ["PROVEN", "DISPROVEN"])
def test_learner_cannot_publish_proof_status_through_structured_api(api, status):
    client, repo = api
    payload = {
        **PAYLOAD,
        "relations": [
            {"id": "claim", "type": "EQUAL_LENGTH", "args": ["A", "B", "A", "B"], "status": status}
        ],
    }
    response = client.post(BASE, json=payload, headers=AUTH)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UNTRUSTED_GEOMETRY_STATUS"
    assert not repo.saved
    client.post(BASE, json=PAYLOAD, headers=AUTH)
    response = client.post(
        BASE + "/geometry_test/deltas",
        json={
            "expected_version": 0,
            "change_status": [
                {"relation_id": "claim", "status": status, "provenance": "Caller assertion"}
            ],
        },
        headers=AUTH,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UNTRUSTED_GEOMETRY_STATUS"


def test_structured_authority_guard_rejects_invalid_shapes_without_server_error(api):
    client, _ = api
    for payload in ([], {"relations": None}, {"relations": [3]}):
        assert client.post(BASE, json=payload, headers=AUTH).status_code == 422


@pytest.mark.parametrize(
    "suffix,method,body",
    [
        ("", "GET", None),
        ("/versions/0", "GET", None),
        ("/versions/0/render", "GET", None),
        ("/frames", "GET", None),
        ("/versions/0/validate", "POST", None),
        ("/deltas", "POST", {"expected_version": 0}),
    ],
)
def test_cross_owner_denied_including_staff_default_scope(api, suffix, method, body):
    client, _ = api
    client.post(BASE, json=PAYLOAD, headers=AUTH)
    for headers in ({"Authorization": "Bearer learner-b"}, ADMIN):
        assert (
            client.request(
                method, BASE + "/geometry_test" + suffix, json=body, headers=headers
            ).status_code
            == 404
        )


def test_debug_evidence_staff_only_and_review_does_not_publish(api):
    client, repo = api
    repo.runs["learner-a", "run"] = {"candidate": "private"}
    path = BASE + "/debug/runs/run?owner=learner-a"
    assert client.get(path, headers=AUTH).status_code == 403
    assert client.get(path, headers=ADMIN).json() == {"candidate": "private"}
    listing = BASE + "/debug/runs?owner=learner-a"
    assert client.get(listing, headers=AUTH).status_code == 403
    assert client.get(listing, headers=ADMIN).json()["runs"] == [{"run_id": "run"}]
    review = BASE + "/debug/runs/run/review?owner=learner-a"
    assert client.post(review, json={"decision": "ACCEPTED"}, headers=AUTH).status_code == 403
    assert client.post(review, json={"decision": "REJECTED"}, headers=ADMIN).status_code == 200
    assert not repo.saved


def test_storage_failure_remains_explicit_503(api):
    client, repo = api
    repo.create = Mock(side_effect=GeometryStorageError("private storage unavailable"))
    response = client.post(BASE, json=PAYLOAD, headers=AUTH)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "GEOMETRY_STORAGE_UNAVAILABLE"


def test_invalid_bearer_is_rejected(api):
    client, _ = api
    assert (
        client.post(BASE, json=PAYLOAD, headers={"Authorization": "Bearer invalid"}).status_code
        == 401
    )
