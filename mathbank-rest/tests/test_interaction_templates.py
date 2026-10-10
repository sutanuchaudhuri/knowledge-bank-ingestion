"""Live-DB tests for the interaction template library (requirements/41) and its
dependency on the micro-course platform (requirements/40). Gated behind
ROUTE_DB_TESTS=1 like the sibling tutoring-route tests; every test runs inside
a rolled-back transaction so nothing persists against the shared database.
"""

import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from mathbank_rest import interaction_catalog, interaction_runtime, interaction_validators
from mathbank_rest.db.postgres import engine


@pytest.fixture
def live_conn():
    if os.environ.get("ROUTE_DB_TESTS") != "1":
        pytest.skip("Opt-in rollback-only interaction-template integration checks")
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            yield conn
        finally:
            transaction.rollback()


def test_seed_catalog_load_is_idempotent(live_conn):
    before = interaction_catalog.load_all(live_conn)
    after = interaction_catalog.load_all(live_conn)
    assert before == after
    assert before["interaction_templates"] == 20
    assert before["icon_tokens"] == 25


def markov_fixture(conn):
    """Builds one real TRANSITION_MATRIX_EDITOR_V1 instance bound to a fresh
    misconception + APPROVED evidence rule, returns the ids needed by tests."""
    interaction_catalog.load_all(conn)
    student_id = conn.execute(
        text("SELECT student_id FROM learner.student_profile LIMIT 1")
    ).scalar_one()
    version_id = conn.execute(
        text("""
        SELECT interaction_template_version_id FROM visual.interaction_template_version v
        JOIN visual.interaction_template t USING (interaction_template_id)
        WHERE t.template_key='TRANSITION_MATRIX_EDITOR_V1'
    """)
    ).scalar_one()
    mis_id = conn.execute(
        text("""
        INSERT INTO knowledge.misconception (canonical_code, name, description)
        VALUES (:code, 'Row sum confusion', 'Believes rows need not sum to 1')
        RETURNING misconception_id
    """),
        {"code": f"MC-TEST-{uuid4().hex[:8]}"},
    ).scalar_one()
    instance_id = conn.execute(
        text("""
        INSERT INTO visual.interaction_instance
        (interaction_template_version_id, canonical_code, title, instance_config,
         learning_objective, success_criteria, content_hash, created_by)
        VALUES (:v, :code, 'Markov Matrix', '{}', 'Build a valid transition matrix', '{}', 'h', 'test')
        RETURNING interaction_instance_id
    """),
        {"v": version_id, "code": f"INT-TEST-{uuid4().hex[:8]}"},
    ).scalar_one()
    conn.execute(
        text("""
        INSERT INTO visual.interaction_instance_misconception
            (interaction_instance_id, misconception_id, role)
        VALUES (:i, :m, 'CAN_REVEAL')
    """),
        {"i": instance_id, "m": mis_id},
    )
    conn.execute(
        text("""
        INSERT INTO pedagogy.misconception_evidence_rule
        (misconception_id, interaction_template_version_id, semantic_action, error_signature,
         predicate_json, evidence_weight, requires_probe, review_status)
        VALUES (:m, :v, 'SUBMIT_ROW', 'ROW_SUM_INVALID', '{}', 0.35, true, 'APPROVED')
    """),
        {"m": mis_id, "v": version_id},
    )
    return {
        "student_id": student_id,
        "version_id": version_id,
        "instance_id": instance_id,
        "misconception_id": mis_id,
    }


def test_transition_matrix_row_sum_invalid_detected():
    result = interaction_runtime.evaluate_transition_matrix_row([0.3, 0.4, 0.5])
    assert result["outcome"] == "ERROR"
    assert result["error_signature"] == "ROW_SUM_INVALID"


def test_transition_matrix_negative_probability_detected():
    result = interaction_runtime.evaluate_transition_matrix_row([-0.1, 0.6, 0.5])
    assert result["error_signature"] == "NEGATIVE_PROBABILITY"


def test_transition_matrix_valid_row_is_correct():
    result = interaction_runtime.evaluate_transition_matrix_row([0.3, 0.3, 0.4])
    assert result["outcome"] == "CORRECT"
    assert result["error_signature"] is None


def test_one_wrong_answer_never_confirms_misconception_alone(live_conn):
    fixture = markov_fixture(live_conn)
    evaluation = interaction_runtime.evaluate_transition_matrix_row([0.3, 0.4, 0.5])
    event_id = interaction_runtime.record_interaction_event(
        live_conn,
        fixture["student_id"],
        fixture["instance_id"],
        "SUBMIT_ROW",
        {"row": [0.3, 0.4, 0.5]},
        evaluation,
    )
    evidence = interaction_runtime.apply_evidence(
        live_conn,
        fixture["student_id"],
        event_id,
        fixture["version_id"],
        "SUBMIT_ROW",
        evaluation["error_signature"],
    )
    assert evidence["confirmed"] is False
    assert 0 < evidence["after"] < interaction_runtime.CONFIRMATION_THRESHOLD


def test_repeated_errors_accumulate_to_confirmed_misconception(live_conn):
    fixture = markov_fixture(live_conn)
    confirmed_at = None
    for attempt in range(1, 5):
        evaluation = interaction_runtime.evaluate_transition_matrix_row([0.3, 0.4, 0.5])
        event_id = interaction_runtime.record_interaction_event(
            live_conn,
            fixture["student_id"],
            fixture["instance_id"],
            "SUBMIT_ROW",
            {"row": [0.3, 0.4, 0.5]},
            evaluation,
        )
        evidence = interaction_runtime.apply_evidence(
            live_conn,
            fixture["student_id"],
            event_id,
            fixture["version_id"],
            "SUBMIT_ROW",
            evaluation["error_signature"],
        )
        if evidence["confirmed"]:
            confirmed_at = attempt
            break
    assert confirmed_at is not None and confirmed_at > 1, (
        "misconception must never confirm on the first wrong answer"
    )


def test_feedback_ladder_progresses_with_attempts():
    stages = [
        interaction_runtime.select_feedback(None, None, attempt, "ROW_SUM_INVALID")["stage"]
        for attempt in range(1, 4)
    ]
    assert stages[0] != stages[1] != stages[2]
    assert stages[0] == "neutral structural clue"


def test_validate_scene_spec_rejects_unknown_object_reference(live_conn):
    scene_id = live_conn.execute(
        text("""
        INSERT INTO visual.scene_spec (canonical_code, version, scene_schema_version, scene_json, content_hash, created_by)
        VALUES (:code, 1, 'v1', CAST(:scene AS jsonb), 'h', 'test') RETURNING scene_spec_id
    """),
        {
            "code": f"SCENE-TEST-{uuid4().hex[:8]}",
            "scene": '{"objects":[{"id":"a","type":"STATE_NODE"}],"timeline":[{"at_ms":0,"action":"SHOW","targets":["missing"]}]}',
        },
    ).scalar_one()
    errors = interaction_validators.validate_scene_spec(live_conn, scene_id)
    assert any("unknown object" in e for e in errors)


def test_validate_interaction_template_version_flags_placeholder_schema(live_conn):
    interaction_catalog.load_all(live_conn)
    # SINGLE_SELECT_V1 is not one of the reference templates published by
    # scripts/seed_reference_courses.py, so it stays a DRAFT placeholder here.
    version_id = live_conn.execute(
        text("""
        SELECT interaction_template_version_id FROM visual.interaction_template_version v
        JOIN visual.interaction_template t USING (interaction_template_id)
        WHERE t.template_key='SINGLE_SELECT_V1'
    """)
    ).scalar_one()
    errors = interaction_validators.validate_interaction_template_version(live_conn, version_id)
    assert any("placeholder" in e for e in errors)


def test_rest_router_requires_admin_auth():
    from fastapi.testclient import TestClient

    from mathbank_rest.main import app

    client = TestClient(app)
    assert client.get("/v1/admin/interaction-templates").status_code == 401


def test_rest_router_lists_templates_with_auth():
    import os as _os

    from fastapi.testclient import TestClient

    from mathbank_rest.main import app

    key = _os.environ.get("ADMIN_API_KEY")
    if not key:
        pytest.skip("ADMIN_API_KEY not set in this environment")
    client = TestClient(app)
    response = client.get("/v1/admin/interaction-templates", headers={"X-Admin-Api-Key": key})
    assert response.status_code == 200
    assert len(response.json()) >= 1
    if os.environ.get("ROUTE_DB_TESTS") != "1":
        pytest.skip("Opt-in: writes real catalog nodes to the shared Neo4j graph")
    from mathbank_rest import interaction_template_projection as itp

    first = itp.project()
    second = itp.project()
    assert first["nodes"] == second["nodes"]
    assert first["edges"] == second["edges"]
    diff = itp.verify()
    assert diff["missing_nodes"] == []
    assert diff["stale_nodes"] == []
    assert diff["missing_edges"] == []
    assert diff["stale_edges"] == []
