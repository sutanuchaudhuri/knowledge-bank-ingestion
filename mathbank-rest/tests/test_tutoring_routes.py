import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from test_route_contracts import program

from mathbank_rest import route_runtime, solution_guidance
from mathbank_rest.db.postgres import engine
from mathbank_rest.main import app
from mathbank_rest.route_compiler import persist
from mathbank_rest.route_contracts import RouteProgram, program_digest
from mathbank_rest.step_runtime import NotFound, StateVersionConflict


def test_admin_and_attempt_routes_require_authentication():
    client = TestClient(app)
    assert client.get("/v1/admin/tutoring-routes").status_code == 401
    assert client.get(f"/v1/admin/tutoring-routes/{uuid4()}").status_code == 401
    assert client.post("/v1/admin/tutoring-routes/refresh-graph").status_code == 401
    assert (
        client.post("/v1/tutor/route-attempts", json={"problem_code": "AIME_1985_Q01"}).status_code
        == 401
    )
    assert (
        client.post(
            f"/v1/tutor/route-attempts/{uuid4()}/assist",
            json={"hint_level": 5, "expected_version": 1},
        ).status_code
        == 401
    )


def test_guidance_returns_published_route_without_loading_or_generating_references(monkeypatch):
    expected = {"status": "ready", "route_release_id": str(uuid4())}
    monkeypatch.setattr(route_runtime, "plan", lambda code: expected)
    monkeypatch.setattr(
        solution_guidance,
        "load_references",
        lambda code: pytest.fail("Must not dynamically decompose"),
    )
    assert solution_guidance.guidance_plan("PUBLISHED") is expected


def test_semantic_hash_is_independent_of_sql_relation_order():
    value = program()
    value["steps"][1]["depends_on"] = [1]
    one = RouteProgram.model_validate(value)
    assert program_digest(one) == program_digest(RouteProgram.model_validate(one.model_dump()))
    two = one.model_copy(deep=True)
    two.steps[0].instruction.student_prompt = "Changed checkpoint?"
    assert program_digest(one) != program_digest(two)


@pytest.fixture
def live_conn():
    if os.environ.get("ROUTE_DB_TESTS") != "1":
        pytest.skip("Opt-in rollback-only route integration checks")
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            yield conn
        finally:
            transaction.rollback()


def draft(conn):
    source = dict(
        conn.execute(
            text("""
        SELECT s.solution_id::text,s.problem_id::text,p.canonical_code,p.statement_text,
               s.verification_status,coalesce(nullif(trim(s.body_markdown),''),s.body_latex) AS source
        FROM core.solution s JOIN core.problem p USING(problem_id)
        WHERE NOT EXISTS (SELECT 1 FROM pedagogy.solution_route_release r WHERE r.solution_id=s.solution_id)
          AND length(coalesce(nullif(trim(s.body_markdown),''),s.body_latex))>100
        ORDER BY p.canonical_code DESC,s.solution_id LIMIT 1
    """)
        )
        .mappings()
        .one()
    )
    payload = program()
    for step in payload["steps"]:
        step["instruction"] = dict(step["instruction"])
        step["source_quote"] = source["source"][:80]
    payload["steps"][0]["instruction"]["student_prompt"] = "Current checkpoint?"
    payload["steps"][1]["instruction"]["full_explanation"] = "FUTURE_EXPLANATION_SECRET"
    payload["steps"][1]["instruction"]["expected_response"] = "FUTURE_ANSWER_SECRET"
    value = RouteProgram.model_validate(payload)
    release_id = UUID(persist(conn, source, value, str(uuid4())))
    return release_id, source, value


def test_review_publication_and_snapshot_immutability(live_conn):
    conn = live_conn
    release, source, value = draft(conn)
    with pytest.raises(SQLAlchemyError, match="require review"), conn.begin_nested():
        conn.execute(
            text("""
            UPDATE pedagogy.solution_route_release SET status='PUBLISHED',reviewed_by='test',reviewed_at=now()
            WHERE route_release_id=:id
        """),
            {"id": release},
        )
    with pytest.raises(StateVersionConflict):
        route_runtime.review(conn, release, "rollback test", "0" * 64)
    route_runtime.review(conn, release, "rollback test", program_digest(value))
    with pytest.raises(SQLAlchemyError, match="immutable"), conn.begin_nested():
        conn.execute(
            text("DELETE FROM pedagogy.route_step_hint WHERE route_release_id=:id"), {"id": release}
        )
    other, _, _ = draft(conn)
    with pytest.raises(SQLAlchemyError, match="cannot be moved"), conn.begin_nested():
        conn.execute(
            text("""
            UPDATE pedagogy.route_step_hint SET route_release_id=:other WHERE route_release_id=:id
        """),
            {"id": release, "other": other},
        )
    route_runtime.publish(conn, release)
    assert (
        route_runtime.select_published(conn, source["canonical_code"])["route_release_id"]
        == release
    )


def test_graph_metadata_excludes_drafts_and_teaching_prose(live_conn):
    from mathbank_rest.route_projection import metadata

    release, _, value = draft(live_conn)
    other, _, _ = draft(live_conn)
    route_runtime.review(live_conn, release, "rollback test", program_digest(value))
    route_runtime.publish(live_conn, release)
    graph = metadata(live_conn)
    assert any(node["id"] == str(release) for node in graph["nodes"])
    assert not any(node["id"] == str(other) for node in graph["nodes"])
    assert "FUTURE_" not in str(graph)
    assert not any("source_quote" in node["properties"] for node in graph["nodes"])


def test_attempt_ownership_current_step_and_retirement_pin(live_conn):
    conn = live_conn
    release, source, value = draft(conn)
    route_runtime.review(conn, release, "rollback test", program_digest(value))
    route_runtime.publish(conn, release)
    student = conn.execute(
        text("SELECT student_id FROM learner.student_profile LIMIT 1")
    ).scalar_one()
    state = route_runtime.start_attempt(conn, student, source["canonical_code"], release)
    assert "FUTURE_" not in str(state)
    attempt = UUID(state["route_attempt_id"])
    with pytest.raises(NotFound):
        route_runtime.owned_attempt(conn, uuid4(), attempt)
    conn.execute(
        text(
            "UPDATE pedagogy.solution_route_release SET status='RETIRED' WHERE route_release_id=:id"
        ),
        {"id": release},
    )
    with pytest.raises(NotFound):
        route_runtime.start_attempt(conn, student, source["canonical_code"], release)
    hint = route_runtime.assist(conn, student, attempt, 1, 1, False)
    assert hint["current_step"] == 1 and hint["version"] == 2
    assert "FUTURE_" not in str(hint)
    with pytest.raises(StateVersionConflict):
        route_runtime.assist(conn, student, attempt, 1, 5, True)
    advanced = route_runtime.assist(conn, student, attempt, 2, 5, True)
    assert advanced["current_step"] == 2 and advanced["tutor_explained_steps"] == [1]
    assert not advanced["mastery_recorded"]
    assert "FUTURE_" not in str(advanced)


def test_draft_edit_is_atomic_and_hash_guarded(live_conn):
    conn = live_conn
    release, _, value = draft(conn)
    changed = value.model_copy(deep=True)
    changed.steps[0].instruction.student_prompt = "A smaller checkpoint?"
    with pytest.raises(StateVersionConflict):
        route_runtime.edit(conn, release, "0" * 64, changed)
    result = route_runtime.edit(conn, release, program_digest(value), changed)
    loaded = route_runtime.load_program(conn, str(release))
    assert result["content_hash"] == program_digest(loaded) == program_digest(changed)
    route_runtime.review(conn, release, "rollback test", result["content_hash"])
    with pytest.raises(StateVersionConflict):
        route_runtime.edit(conn, release, result["content_hash"], value)
