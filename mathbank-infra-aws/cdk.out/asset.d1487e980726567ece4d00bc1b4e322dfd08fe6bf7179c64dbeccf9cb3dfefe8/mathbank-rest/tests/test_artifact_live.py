"""Opt-in Neon SQL acceptance: synthetic learner, mock objects/vectors, unconditional rollback."""
from __future__ import annotations

import os
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from mathbank_rest import artifact_runtime as runtime
from mathbank_rest import object_store
from mathbank_rest.db.postgres import engine

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_ARTIFACT_LIVE") != "1", reason="explicit Neon rollback-only opt-in"
)


@pytest.fixture
def fixture(monkeypatch):
    objects = {}

    def put(data, suffix):
        key = f"{uuid4().hex}.{suffix.removeprefix('.')}"
        objects[key] = data
        return {"object_key": key, "sha256": sha256(data).hexdigest(), "size_bytes": len(data)}

    monkeypatch.setattr(object_store, "put_bytes", put)
    monkeypatch.setattr(object_store, "read_bytes", lambda key: objects[key])
    monkeypatch.setattr(object_store, "delete_object", lambda key: objects.pop(key, None))
    monkeypatch.setattr(runtime, "embedding_profile", lambda: {
        "provider": "direct_openai", "model": "text-embedding-3-small", "dimensions": 1536,
    })
    monkeypatch.setattr(runtime, "EMBEDDER", lambda source: pytest.fail("no paid live provider calls"))
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            student = conn.execute(text(
                "INSERT INTO learner.student_profile(email,password_hash,display_name) "
                "VALUES (:email,'synthetic-not-login-capable','Artifact rollback test') RETURNING student_id"
            ), {"email": f"artifact-rollback-{uuid4()}@example.invalid"}).scalar_one()
            yield conn, {"role": "STUDENT", "student_id": str(student)}, objects
        finally:
            transaction.rollback()


def test_real_sql_request_generation_manifest_search_index_and_ownership(fixture):
    conn, student, objects = fixture
    admin = {"role": "ADMIN", "student_id": None}
    token = "artifactrollback" + uuid4().hex
    plan = runtime.ArtifactPlan(
        subject="ALGEBRA", topic=token, title=token, summary="Synthetic rollback-only artifact",
        elements=[{"kind": "EQUATION", "id": "eq1", "latex": "x+1=3", "reason": "Starting equation"},
                  {"kind": "EQUATION", "id": "eq2", "latex": "x=2", "reason": "Subtract one"}],
        concept_ids=[token],
        overlays=[{"id": "focus", "caption": "Subtract one", "linked_step_id": "synthetic-step",
                   "actions": [{"action": "EMPHASIZE_EQUATION_LINE", "targets": ["eq2"]}]}],
    )
    request = runtime.create_request(conn, plan, student)
    request_id = UUID(str(request["artifact_request_id"]))
    assert runtime.get_request(conn, request_id, student)["subject"] == "ALGEBRA"
    with pytest.raises(runtime.ArtifactError) as exc:
        runtime.get_request(conn, request_id, {"role": "STUDENT", "student_id": str(uuid4())})
    assert exc.value.status_code == 404
    bundle = runtime.generate_request(conn, request_id, admin)
    bundle_id = UUID(str(bundle["artifact_bundle_id"]))
    assert bundle["status"] == "DRAFT" and len(objects) == 4
    with pytest.raises(runtime.ArtifactError):
        runtime.get_bundle(conn, bundle_id, student)
    assert runtime.validate_bundle(conn, bundle_id, admin)["valid"]
    runtime.publish_bundle(conn, bundle_id, admin)
    assert runtime.get_bundle(conn, bundle_id, student)["status"] == "PUBLISHED"
    assets = runtime.list_assets(conn, bundle_id, student)
    assert {a["asset_type"] for a in assets} == {
        "SVG_DIAGRAM", "LATEX_CARD", "FRAME_SEQUENCE", "MANIM_EXPORT_SPEC",
    }
    assert all("object_key" not in a for a in assets)
    manifest = runtime.get_frames(conn, bundle_id, student)
    assert manifest["frames"][0]["linked_step_id"] == "synthetic-step"
    assert runtime.svg_errors(runtime.frame_svg(conn, bundle_id, 0, student)) == []
    lexical = runtime.search(conn, runtime.SearchBody(query=token), student)
    assert str(bundle_id) in {str(r["artifact_bundle_id"]) for r in lexical["results"]}
    unindexed = runtime.search(conn, runtime.SearchBody(
        query_embedding=[1.0] + [0.0] * 1535, concept_id=token), student, semantic=True)
    assert unindexed["reason"] == "NO_INDEXED_VECTORS_FOR_FILTERS"
    runtime.index_bundle(conn, bundle_id, runtime.IndexBody(
        embedding=[1.0] + [0.0] * 1535, search_text_sha256=bundle["search_text_sha256"]), admin)
    indexed = conn.execute(text(
        "SELECT model,dimensions,vector_dims(embedding) AS actual FROM artifact_runtime.artifact_embedding "
        "WHERE artifact_bundle_id=:id"), {"id": bundle_id}).mappings().one()
    assert dict(indexed) == {"model": "text-embedding-3-small", "dimensions": 1536, "actual": 1536}
    semantic = runtime.search(conn, runtime.SearchBody(
        query_embedding=[1.0] + [0.0] * 1535, concept_id=token), student, semantic=True)
    assert semantic["status"] == "AVAILABLE"
    assert str(semantic["results"][0]["artifact_bundle_id"]) == str(bundle_id)
    assert semantic["results"][0]["score"] == pytest.approx(1.0)
