from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from geometry_scene.api import create_app
from geometry_scene.errors import VersionConflict
from geometry_scene.repository import Repository, SceneNotFound
from geometry_scene.schemas import SceneInput, StateDelta

TOKEN = "geometry-test-token-not-a-secret"
ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = json.loads((ROOT / "fixtures/09_midpoint_auxiliary.json").read_text())["initial"]


@pytest.fixture
def api(tmp_path):
    store = Repository(tmp_path / "scenes.sqlite3")
    return TestClient(create_app(store, TOKEN)), store


def test_api_requires_auth_and_round_trips_frames(api):
    client, store = api
    assert client.post("/v1/geometry-scenes", json=PAYLOAD).status_code == 401
    headers = {"Authorization": "Bearer " + TOKEN, "Idempotency-Key": "test-create"}
    response = client.post("/v1/geometry-scenes", json=PAYLOAD, headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    scene_id = body["scene_id"]
    replay = client.post("/v1/geometry-scenes", json=PAYLOAD, headers=headers).json()
    assert replay["replayed"] is True
    image = client.get(body["frame_asset"]["content_path"], headers=headers)
    assert image.status_code == 200 and "<svg" in image.text
    assert image.headers["cache-control"] == "private, no-store"
    assert (
        client.get(f"/v1/geometry-scenes/{scene_id}/versions/0", headers=headers).status_code == 200
    )
    assert client.post(
        f"/v1/geometry-scenes/{scene_id}/versions/0/validate", headers=headers
    ).json()["valid"]
    assert (
        len(client.get(f"/v1/geometry-scenes/{scene_id}/frames", headers=headers).json()["frames"])
        == 1
    )
    path = f"/v1/geometry-scenes/{scene_id}/deltas"
    changed = client.post(
        path, json={"expected_version": 0}, headers={**headers, "Idempotency-Key": "delta"}
    )
    assert changed.status_code == 200 and changed.json()["version"] == 1
    assert (
        client.post(
            path, json={"expected_version": 0}, headers={**headers, "Idempotency-Key": "other"}
        ).status_code
        == 409
    )
    assert client.post(
        path, json={"expected_version": 0}, headers={**headers, "Idempotency-Key": "delta"}
    ).json()["replayed"]
    assert store.read(scene_id, 0, "standalone").version == 0


def test_repository_ownership_and_restart(api):
    _, store = api
    frame, _ = store.create(SceneInput.model_validate(PAYLOAD), "learner-a")
    with pytest.raises(SceneNotFound):
        store.read(frame.scene_state.scene_id, 0, "learner-b")
    reopened = Repository(store.path)
    assert reopened.read(frame.scene_state.scene_id, 0, "learner-a") == frame


def test_receipt_payload_conflict(api):
    client, _ = api
    headers = {"Authorization": "Bearer " + TOKEN, "Idempotency-Key": "same"}
    assert client.post("/v1/geometry-scenes", json=PAYLOAD, headers=headers).status_code == 201
    changed = {**PAYLOAD, "seed": 18}
    assert client.post("/v1/geometry-scenes", json=changed, headers=headers).status_code == 409


def test_concurrent_delta_has_exactly_one_winner(api):
    _, store = api
    frame, _ = store.create(SceneInput.model_validate(PAYLOAD), "learner-a")

    def update():
        try:
            return store.apply(
                frame.scene_state.scene_id, StateDelta(expected_version=0), "learner-a"
            )[0].version
        except VersionConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: update(), range(2)))
    assert sorted(results, key=str) == [1, "conflict"]


def test_invalid_frame_is_reported_without_persistence(api):
    client, store = api
    data = json.loads((ROOT / "fixtures/10_broken_to_straight.json").read_text())["initial"]
    data["positions"]["Y"] = [470, 180]
    headers = {"Authorization": "Bearer " + TOKEN}
    response = client.post("/v1/geometry-scenes", json=data, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"]["validation"]["valid"] is False
    with store._connect() as conn:
        assert conn.execute("SELECT count(*) FROM scenes").fetchone()[0] == 0
