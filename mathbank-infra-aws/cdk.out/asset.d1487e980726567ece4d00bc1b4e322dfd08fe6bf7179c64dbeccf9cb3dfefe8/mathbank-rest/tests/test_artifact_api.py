"""Router integration without startup handlers, live databases, or paid providers."""

from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_artifact_runtime import STUDENT, Connection, plan_payload
from test_artifact_runtime import object_root as shared_object_root
from test_artifact_runtime import offline_embedding_profile as shared_embedding_profile

from mathbank_rest import object_store, security
from mathbank_rest.routers import artifacts

object_root = shared_object_root
offline_embedding_profile = shared_embedding_profile


class Engine:
    def __init__(self, conn):
        self.conn = conn

    @contextmanager
    def begin(self):
        yield self.conn


@pytest.fixture
def api(monkeypatch):
    app = FastAPI()
    app.include_router(artifacts.router)
    conn = Connection()
    monkeypatch.setattr(artifacts, "engine", Engine(conn))
    monkeypatch.setattr(security.settings, "admin_api_key", "artifact-test-admin")
    monkeypatch.setattr(
        security,
        "decode_access_token",
        lambda token: (
            STUDENT["student_id"]
            if token == "student-test"
            else (_ for _ in ()).throw(ValueError("bad token"))
        ),
    )
    return TestClient(app), conn


ADMIN_HEADERS = {"X-Admin-Api-Key": "artifact-test-admin"}
STUDENT_HEADERS = {"Authorization": "Bearer student-test"}


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("POST", "/requests", plan_payload()),
        ("GET", f"/requests/{uuid4()}", None),
        ("GET", f"/bundles/{uuid4()}", None),
        ("GET", f"/bundles/{uuid4()}/assets", None),
        ("GET", f"/bundles/{uuid4()}/frames", None),
        ("POST", "/search", {}),
        ("POST", "/search/semantic", {}),
        ("POST", "/validate", plan_payload()),
        ("POST", "/geometry-preview", plan_payload()),
        ("POST", "/geometry-preview/content", plan_payload()),
        ("POST", "/preview", plan_payload()),
        ("POST", "/preview/content", plan_payload()),
    ],
)
def test_every_read_and_request_requires_auth(api, method, path, body):
    client, conn = api
    response = client.request(method, "/v1/artifacts" + path, json=body)
    assert response.status_code == 401
    assert not conn.calls


@pytest.mark.parametrize(
    "path,body",
    [
        (f"/requests/{uuid4()}/generate", {}),
        (f"/bundles/{uuid4()}/publish", None),
        (f"/bundles/{uuid4()}/index", {"embedding": [1.0] * 1536, "search_text_sha256": "0" * 64}),
    ],
)
def test_student_cannot_write_reusable_artifacts(api, path, body):
    client, conn = api
    response = client.post("/v1/artifacts" + path, json=body, headers=STUDENT_HEADERS)
    assert response.status_code == 401 and not conn.calls


def test_student_can_draw_ephemeral_geometry_with_true_incircles(api):
    import math
    import re
    from xml.etree import ElementTree as ET

    client, conn = api
    plan = {
        "subject": "GEOMETRY",
        "topic": "Quadrilateral incircles",
        "title": "Construction sketch",
        "summary": "Generated construction sketch; does not assert equal inradii or right angles.",
        "elements": [
            {"kind": "POINT", "id": name, "label": name, "x": x, "y": y}
            for name, x, y in [("A", 100, 100), ("B", 650, 120), ("C", 550, 450), ("D", 140, 400)]
        ]
        + [
            {"kind": "SEGMENT", "id": a + b, "start": a, "end": b, "auxiliary": False}
            for a, b in [("A", "B"), ("B", "C"), ("C", "D"), ("D", "A"), ("A", "C"), ("B", "D")]
        ],
        "incircle_triangles": [["A", "B", "C"], ["B", "C", "D"], ["C", "D", "A"], ["D", "A", "B"]],
    }
    result = client.post("/v1/artifacts/geometry-preview", json=plan, headers=STUDENT_HEADERS)
    assert result.status_code == 200, result.text
    assert result.json()["validation"]["valid"]
    assert result.json()["markdown_block"].startswith("```geometry-artifact\n")
    content = client.post(
        "/v1/artifacts/geometry-preview/content", json=plan, headers=STUDENT_HEADERS
    )
    assert content.status_code == 200, content.text
    assert content.headers["content-type"].startswith("image/svg+xml")
    assert "no-store" in content.headers["cache-control"]
    root = ET.fromstring(content.content)
    circles = [el for el in root.iter() if el.attrib.get("id", "").startswith("incircle_")]
    assert len(circles) == 4
    points = {e["id"]: (e["x"], e["y"]) for e in plan["elements"] if e["kind"] == "POINT"}
    for circle, triangle in zip(circles, plan["incircle_triangles"]):
        shape = next(element for element in circle.iter() if element.tag.endswith("circle"))
        x, y, radius = [float(shape.attrib[key]) for key in ("cx", "cy", "r")]
        for a, b in zip(triangle, triangle[1:] + triangle[:1]):
            ax, ay = points[a]
            bx, by = points[b]
            distance = abs((bx - ax) * (ay - y) - (ax - x) * (by - ay)) / math.hypot(
                bx - ax, by - ay
            )
            assert abs(distance - radius) < 0.01
    assert not re.search(r"<script|onload=", content.text)
    assert not conn.calls  # Neither previews nor drawings write the corpus or object store.
    plan["incircle_triangles"][0] = ["A", "A", "C"]
    assert (
        client.post(
            "/v1/artifacts/geometry-preview", json=plan, headers=STUDENT_HEADERS
        ).status_code
        == 422
    )


@pytest.mark.parametrize("subject", ["ALGEBRA", "COMBINATORICS", "NUMBER_THEORY"])
def test_subject_previews_render_without_publication_or_database_writes(api, subject):
    client, conn = api
    payload = plan_payload(subject)
    response = client.post("/v1/artifacts/preview", json=payload, headers=STUDENT_HEADERS)
    assert response.status_code == 200, response.text
    assert response.json()["validation"]["valid"]
    assert response.json()["rule_profile_id"] == subject.lower() + "_v1"
    assert response.json()["markdown_block"].startswith("```artifact-preview\n")
    image = client.post("/v1/artifacts/preview/content", json=payload, headers=STUDENT_HEADERS)
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/svg+xml")
    assert not conn.calls


def test_strict_uuid_paths_and_input_maxima(api):
    client, conn = api
    for suffix in ("requests/nope", "bundles/nope", "bundles/nope/assets", "bundles/nope/frames"):
        assert client.get("/v1/artifacts/" + suffix, headers=STUDENT_HEADERS).status_code == 422
    bad = plan_payload()
    bad["linked_problem_id"] = "not a UUID"
    assert (
        client.post("/v1/artifacts/requests", json=bad, headers=STUDENT_HEADERS).status_code == 422
    )
    bad = plan_payload()
    bad["elements"] *= 129
    assert (
        client.post("/v1/artifacts/requests", json=bad, headers=STUDENT_HEADERS).status_code == 422
    )
    assert (
        client.post(
            "/v1/artifacts/search", json={"limit": 101}, headers=STUDENT_HEADERS
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/v1/artifacts/search", json={"offset": -1}, headers=STUDENT_HEADERS
        ).status_code
        == 422
    )
    assert not conn.calls


def test_student_request_owner_guard_published_bundle_and_private_asset(api, object_root):
    client, conn = api
    response = client.post("/v1/artifacts/requests", json=plan_payload(), headers=STUDENT_HEADERS)
    assert response.status_code == 201
    rid = response.json()["artifact_request_id"]
    assert conn.requests[rid]["owner_student_id"] == STUDENT["student_id"]
    conn.requests[rid]["owner_student_id"] = str(uuid4())
    assert client.get(f"/v1/artifacts/requests/{rid}", headers=STUDENT_HEADERS).status_code == 404
    conn.requests[rid]["owner_student_id"] = STUDENT["student_id"]
    response = client.post(f"/v1/artifacts/requests/{rid}/generate", json={}, headers=ADMIN_HEADERS)
    assert response.status_code == 200, response.text
    bid = response.json()["artifact_bundle_id"]
    assert client.get(f"/v1/artifacts/bundles/{bid}", headers=STUDENT_HEADERS).status_code == 404
    assert (
        client.get(f"/v1/artifacts/bundles/{bid}/assets", headers=STUDENT_HEADERS).status_code
        == 404
    )
    assert (
        client.post(f"/v1/artifacts/bundles/{bid}/publish", headers=ADMIN_HEADERS).status_code
        == 200
    )
    response = client.get(f"/v1/artifacts/bundles/{bid}/assets", headers=STUDENT_HEADERS)
    assert response.status_code == 200
    assert "object_key" not in response.text
    asset = next(a for a in response.json()["assets"] if a["render_format"] == "SVG")
    response = client.get(asset["content_path"], headers=STUDENT_HEADERS)
    assert response.status_code == 200 and response.content.startswith(b"<svg")
    assert response.headers["cache-control"] == "private, no-store"
    assert "sandbox" in response.headers["content-security-policy"]
    wrong_bundle = str(uuid4())
    assert (
        client.get(
            f"/v1/artifacts/bundles/{wrong_bundle}/assets/{asset['artifact_asset_id']}/content",
            headers=STUDENT_HEADERS,
        ).status_code
        == 404
    )
    frames = client.get(f"/v1/artifacts/bundles/{bid}/frames", headers=STUDENT_HEADERS).json()
    assert frames["frames"][0]["ordinal"] == 0
    assert frames["frames"][0]["content_path"] == f"/v1/artifacts/bundles/{bid}/frames/0/content"
    response = client.get(f"/v1/artifacts/bundles/{bid}/frames/0/content", headers=STUDENT_HEADERS)
    assert response.status_code == 200 and b"#bae6fd" in response.content
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert (
        client.get(
            f"/v1/artifacts/bundles/{bid}/frames/1/content", headers=STUDENT_HEADERS
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/v1/artifacts/bundles/{bid}/frames/128/content", headers=STUDENT_HEADERS
        ).status_code
        == 422
    )


def test_invalid_overlay_and_offline_validation_endpoint(api):
    client, conn = api
    payload = plan_payload()
    payload["overlays"][0]["actions"][0]["targets"] = ["not_declared"]
    response = client.post("/v1/artifacts/validate", json=payload, headers=STUDENT_HEADERS)
    assert response.status_code == 200 and not response.json()["valid"]
    response = client.post("/v1/artifacts/requests", json=payload, headers=STUDENT_HEADERS)
    assert (
        response.status_code == 422 and response.json()["detail"]["code"] == "INVALID_ARTIFACT_PLAN"
    )
    assert not conn.calls


def test_semantic_endpoint_reports_unavailable_without_provider_call(api):
    client, conn = api
    response = client.post(
        "/v1/artifacts/search/semantic", json={"query": "circle"}, headers=STUDENT_HEADERS
    )
    assert response.status_code == 200
    assert response.json() == {
        "mode": "SEMANTIC",
        "status": "UNAVAILABLE",
        "reason": "QUERY_EMBEDDING_REQUIRED",
        "results": [],
    }
    assert not conn.calls


def test_sql_failure_cleans_only_new_objects(api, object_root):
    client, conn = api
    response = client.post("/v1/artifacts/requests", json=plan_payload(), headers=ADMIN_HEADERS)
    rid = response.json()["artifact_request_id"]
    object_root.mkdir(parents=True)
    sentinel = object_root / "unrelated.txt"
    sentinel.write_text("untouched")
    conn.fail_asset_insert = True
    with pytest.raises(RuntimeError, match="simulated rollback"):
        client.post(f"/v1/artifacts/requests/{rid}/generate", json={}, headers=ADMIN_HEADERS)
    assert [p.name for p in object_root.iterdir()] == ["unrelated.txt"]


def test_storage_configuration_errors_are_explicit_and_sanitized(api, monkeypatch):
    client, _ = api
    monkeypatch.setattr(
        object_store, "_config", lambda: {name: "" for name in object_store._CONFIG_NAMES}
    )
    response = client.post("/v1/artifacts/requests", json=plan_payload(), headers=ADMIN_HEADERS)
    rid = response.json()["artifact_request_id"]
    response = client.post(f"/v1/artifacts/requests/{rid}/generate", json={}, headers=ADMIN_HEADERS)
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "OBJECT_STORE_UNAVAILABLE"
    assert "AWS_ENDPOINT_URL_S3" in detail["message"]
    assert "MATHBANK_OBJECT_BUCKET" in detail["message"]
