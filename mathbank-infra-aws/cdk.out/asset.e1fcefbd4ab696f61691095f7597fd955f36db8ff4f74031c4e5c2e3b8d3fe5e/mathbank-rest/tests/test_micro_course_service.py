import hashlib
import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from mathbank_rest.micro_course_service import _policy_errors, validate_state_graph


@pytest.fixture
def live_conn():
    if os.environ.get("ROUTE_DB_TESTS") != "1":
        pytest.skip("Opt-in rollback-only micro-course integration checks")
    from mathbank_rest.db.postgres import engine

    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            yield conn
        finally:
            transaction.rollback()


def states(*entries):
    return [
        {
            "state_id": state_id,
            "state_key": state_key,
            "ordinal": ordinal,
            "required": required,
        }
        for state_id, state_key, ordinal, required in entries
    ]


def transition(source, target, transition_id="t"):
    return {
        "transition_id": transition_id,
        "from_state_id": source,
        "to_state_id": target,
    }


def test_state_graph_accepts_reachable_required_states_and_terminal():
    errors = validate_state_graph(
        states(("s1", "start", 0, True), ("s2", "finish", 1, True)),
        [transition("s1", "s2")],
    )

    assert errors == []


def test_state_graph_rejects_unreachable_required_state():
    errors = validate_state_graph(
        states(("s1", "start", 0, True), ("s2", "orphan", 1, True)),
        [],
    )

    assert any("orphan is unreachable" in error for error in errors)


def test_state_graph_rejects_required_cycle_without_terminal_exit():
    errors = validate_state_graph(
        states(("s1", "start", 0, True), ("s2", "loop", 1, True)),
        [transition("s1", "s2"), transition("s2", "s1", "t2")],
    )

    assert any("start has no path to a terminal state" in error for error in errors)
    assert any("loop has no path to a terminal state" in error for error in errors)


def test_state_graph_allows_optional_unreachable_state():
    errors = validate_state_graph(
        states(("s1", "start", 0, True), ("s2", "optional", 1, False)),
        [],
    )

    assert errors == []


def test_state_graph_rejects_cross_release_transition_endpoint():
    errors = validate_state_graph(
        states(("s1", "start", 0, True)),
        [transition("s1", "outside")],
    )

    assert any("crosses release boundary" in error for error in errors)


def test_runtime_policy_requires_explicitly_disabled_dynamic_content_actions():
    errors = _policy_errors(
        {
            "may_create_quiz": False,
            "may_search_web": False,
            "may_recommend_media": False,
            "may_generate_diagram": False,
            "may_add_course_state": False,
        },
        "release",
        require_explicit=True,
    )

    assert errors == []


def test_runtime_policy_rejects_dynamic_content_actions():
    errors = _policy_errors(
        {"may_search_web": True},
        "release",
        require_explicit=True,
    )

    assert any("may_search_web=true" in error for error in errors)
    assert len(errors) == 5


def test_admin_micro_course_api_requires_admin_key():
    from fastapi.testclient import TestClient

    from mathbank_rest.main import app

    response = TestClient(app).get("/v1/admin/micro-courses")

    assert response.status_code == 401


def test_admin_course_api_passes_metadata_to_shared_service(monkeypatch):
    from fastapi.testclient import TestClient

    from mathbank_rest.main import app
    from mathbank_rest.routers import micro_courses
    from mathbank_rest.security import require_admin_api_key

    calls = []
    monkeypatch.setattr(
        micro_courses,
        "_call",
        lambda operation, *args, **kwargs: calls.append((operation, args, kwargs)) or "course-id",
    )
    app.dependency_overrides[require_admin_api_key] = lambda: None
    try:
        response = TestClient(app).post(
            "/v1/admin/micro-courses",
            json={
                "canonical_code": "MC-API",
                "title": "API course",
                "created_by": "pytest",
                "metadata": {"collection": "reference"},
                "targets": [{"target_type": "CONCEPT", "target_id": str(uuid4())}],
            },
        )
    finally:
        app.dependency_overrides.pop(require_admin_api_key, None)

    assert response.status_code == 201
    assert response.json() == {"micro_course_id": "course-id"}
    assert calls[0][0] is micro_courses.courses.create_course
    assert calls[0][2]["metadata"] == {"collection": "reference"}


def test_student_catalog_returns_only_public_published_course_records(monkeypatch):
    from fastapi.testclient import TestClient

    from mathbank_rest.main import app
    from mathbank_rest.routers import micro_courses

    monkeypatch.setattr(
        micro_courses,
        "_call",
        lambda operation, *args, **kwargs: [
            {"canonical_code": "MC-TEST", "title": "Published lesson"}
        ],
    )
    response = TestClient(app).get("/v1/micro-courses")

    assert response.status_code == 200
    assert response.json() == [{"canonical_code": "MC-TEST", "title": "Published lesson"}]


def test_missing_student_course_returns_not_found(monkeypatch):
    from fastapi.testclient import TestClient

    from mathbank_rest import micro_course_service
    from mathbank_rest.main import app
    from mathbank_rest.routers import micro_courses

    def missing_course(*args, **kwargs):
        raise micro_course_service.MicroCourseNotFound("published micro-course not found")

    monkeypatch.setattr(micro_courses.courses, "get_published_course", missing_course)
    response = TestClient(app).get("/v1/micro-courses/missing-course")

    assert response.status_code == 404


def test_admin_can_bind_approved_interaction(monkeypatch):
    from fastapi.testclient import TestClient

    from mathbank_rest.main import app
    from mathbank_rest.routers import micro_courses
    from mathbank_rest.security import require_admin_api_key

    calls = []
    monkeypatch.setattr(micro_courses, "_call", lambda operation, *args, **kwargs: calls.append((operation, args, kwargs)))
    app.dependency_overrides[require_admin_api_key] = lambda: None
    try:
        response = TestClient(app).post(
            f"/v1/admin/micro-courses/states/{uuid4()}/interactions",
            json={"interaction_instance_id": str(uuid4()), "ordinal": 0, "required": True},
        )
    finally:
        app.dependency_overrides.pop(require_admin_api_key, None)

    assert response.status_code == 201
    assert response.json() == {"status": "BOUND"}
    assert calls[0][0] is micro_courses.courses.attach_interaction


def test_admin_asset_upload_registers_private_object(monkeypatch):
    from fastapi.testclient import TestClient

    from mathbank_rest.main import app
    from mathbank_rest.routers import micro_courses
    from mathbank_rest.security import require_admin_api_key

    calls = []
    monkeypatch.setattr(
        micro_courses.object_store,
        "put_bytes",
        lambda data, suffix: {
            "object_key": "a" * 32 + "." + suffix,
            "sha256": "d" * 64,
            "size_bytes": len(data),
        },
    )
    monkeypatch.setattr(
        micro_courses,
        "_call",
        lambda operation, *args, **kwargs: calls.append((operation, args, kwargs)) or "asset-id",
    )
    app.dependency_overrides[require_admin_api_key] = lambda: None
    try:
        response = TestClient(app).post(
            f"/v1/admin/micro-courses/states/{uuid4()}/assets?title=Course+image&reviewed_by=pytest&admin_confirmed=true",
            content=b"png-bytes",
            headers={"Content-Type": "image/png"},
        )
    finally:
        app.dependency_overrides.pop(require_admin_api_key, None)

    assert response.status_code == 201
    assert response.json()["status"] == "VALID"
    assert calls[0][0] is micro_courses.courses.register_uploaded_asset
    assert calls[0][1][1] == "a" * 32 + ".png"
    assert calls[0][1][2] == "image/png"


def test_admin_asset_upload_requires_explicit_review_confirmation(monkeypatch):
    from fastapi.testclient import TestClient

    from mathbank_rest.main import app
    from mathbank_rest.routers import micro_courses
    from mathbank_rest.security import require_admin_api_key

    storage_calls = []
    monkeypatch.setattr(
        micro_courses.object_store,
        "put_bytes",
        lambda *args: storage_calls.append(args),
    )
    app.dependency_overrides[require_admin_api_key] = lambda: None
    try:
        response = TestClient(app).post(
            f"/v1/admin/micro-courses/states/{uuid4()}/assets?title=Course+image&reviewed_by=pytest",
            content=b"png-bytes",
            headers={"Content-Type": "image/png"},
        )
    finally:
        app.dependency_overrides.pop(require_admin_api_key, None)

    assert response.status_code == 422
    assert storage_calls == []


def test_published_asset_stream_checks_digest_and_is_private(monkeypatch):
    from fastapi.testclient import TestClient

    from mathbank_rest.main import app
    from mathbank_rest.routers import micro_courses

    data = b"image-content"
    asset_id = uuid4()
    monkeypatch.setattr(
        micro_courses,
        "_call",
        lambda operation, *args, **kwargs: {
            "object_key": "b" * 32 + ".png",
            "mime_type": "image/png",
            "content_hash": hashlib.sha256(data).hexdigest(),
            "object_size_bytes": len(data),
        },
    )
    monkeypatch.setattr(micro_courses.object_store, "read_bytes", lambda key: data)

    response = TestClient(app).get(f"/v1/micro-courses/demo/assets/{asset_id}/content")

    assert response.status_code == 200
    assert response.content == data
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_course_authoring_review_publish_and_student_reader(live_conn):
    from mathbank_rest import micro_course_service as courses

    technique_id = live_conn.execute(
        text("SELECT technique_id FROM knowledge.technique LIMIT 1")
    ).scalar_one_or_none()
    concept_id = live_conn.execute(
        text("SELECT concept_id FROM knowledge.concept LIMIT 1")
    ).scalar_one_or_none()
    if technique_id is None or concept_id is None:
        pytest.skip("Canonical technique and concept seed rows are required")

    code = f"MC-TEST-{uuid4().hex[:12].upper()}"
    course_id = courses.create_course(
        live_conn,
        code,
        "Rollback-only service test",
        "pytest",
        [
            {"target_type": "TECHNIQUE", "target_id": str(technique_id), "role": "PRIMARY"},
            {"target_type": "CONCEPT", "target_id": str(concept_id), "role": "PRIMARY"},
        ],
        metadata={"reference": "rollback-test"},
    )
    release_id = courses.create_release(live_conn, code, "pytest")
    module_id = courses.add_module(live_conn, release_id, "M001", 0, "Foundations")
    first_state = courses.add_state(
        live_conn,
        release_id,
        "S001",
        0,
        "ORIENTATION",
        "Start",
        module_id=module_id,
        agent_policy=courses.DEFAULT_AGENT_POLICY,
    )
    end_state = courses.add_state(
        live_conn,
        release_id,
        "S002",
        1,
        "SUMMARY",
        "Finish",
        module_id=module_id,
        agent_policy=courses.DEFAULT_AGENT_POLICY,
    )
    courses.bind_state_target(
        live_conn, first_state, "TECHNIQUE", str(technique_id), "TEACHES"
    )
    courses.bind_state_target(
        live_conn, end_state, "CONCEPT", str(concept_id), "REVIEWS"
    )
    courses.add_transition(live_conn, release_id, first_state, end_state, "NEXT")
    asset_id = courses.register_uploaded_asset(
        live_conn,
        first_state,
        "c" * 32 + ".png",
        "image/png",
        "e" * 64,
        12,
        "Test image",
        "IMAGE",
        "SUPPORT",
        "pytest",
    )

    assert courses.validate_release(live_conn, release_id) == []
    assert courses.review_release(live_conn, release_id, "APPROVED", "pytest") == {
        "status": "APPROVED",
        "errors": [],
    }
    published = courses.publish_release(live_conn, release_id, "pytest")
    assert published["status"] == "PUBLISHED"
    assert len(published["content_hash"]) == 64
    assert courses.get_published_course(live_conn, code)["states"][0]["state_key"] == "S001"
    published_course = courses.get_published_course(live_conn, code)
    published_asset = published_course["states"][0]["assets"][0]
    assert str(published_asset["asset_id"]) == asset_id
    assert published_asset["private_object"] is True
    assert courses.get_published_asset(live_conn, code, asset_id)["object_size_bytes"] == 12
    with (
        pytest.raises(DBAPIError, match="asset used by a published micro-course is immutable"),
        live_conn.begin_nested(),
    ):
        live_conn.execute(
            text("UPDATE visual.asset SET title='Changed' WHERE asset_id=:id"),
            {"id": asset_id},
        )
    with (
        pytest.raises(DBAPIError, match="identity of a published micro-course is immutable"),
        live_conn.begin_nested(),
    ):
        live_conn.execute(
            text("UPDATE pedagogy.micro_course SET metadata='{}'::jsonb WHERE micro_course_id=:id"),
            {"id": course_id},
        )
    assert any(row["canonical_code"] == code for row in courses.list_published_courses(live_conn))
    assert any(row["canonical_code"] == code for row in courses.list_courses(live_conn))
    assert courses.get_course(live_conn, code)["metadata"] == {"reference": "rollback-test"}
    technique_slug = live_conn.execute(
        text("SELECT slug FROM knowledge.technique WHERE technique_id=:id"),
        {"id": technique_id},
    ).scalar_one()
    assert courses.search_canonical_targets(
        live_conn, "TECHNIQUE", technique_slug, limit=1
    )[0]["id"] == technique_id
    with pytest.raises(courses.MicroCourseConflict, match="only DRAFT"):
        courses.add_state(live_conn, release_id, "S003", 2, "SUMMARY", "Too late")
    assert live_conn.execute(
        text("""
        SELECT count(*) FROM pipeline.outbox_event
        WHERE event_type='MICRO_COURSE_PUBLISHED' AND aggregate_id=:id
    """),
        {"id": release_id},
    ).scalar_one() == 1
    assert course_id


def test_audit_log_records_create_review_publish(live_conn):
    from mathbank_rest import micro_course_service as courses

    technique_id = live_conn.execute(
        text("SELECT technique_id FROM knowledge.technique LIMIT 1")
    ).scalar_one_or_none()
    if technique_id is None:
        pytest.skip("Canonical technique seed row is required")

    code = f"MC-AUDIT-{uuid4().hex[:12].upper()}"
    course_id = courses.create_course(
        live_conn, code, "Audit test course", "pytest",
        [{"target_type": "TECHNIQUE", "target_id": str(technique_id), "role": "PRIMARY"}],
    )
    release_id = courses.create_release(live_conn, code, "pytest")
    courses.add_state(live_conn, release_id, "S001", 0, "ORIENTATION", "Start")
    assert courses.validate_release(live_conn, release_id) == []
    courses.review_release(live_conn, release_id, "APPROVED", "pytest")
    courses.publish_release(live_conn, release_id, "pytest")

    actions = {
        row["action"]
        for row in live_conn.execute(
            text("""
            SELECT action FROM audit.action_log
            WHERE entity_id IN (:course_id, :release_id)
        """),
            {"course_id": course_id, "release_id": release_id},
        ).mappings()
    }
    assert actions == {"COURSE_CREATED", "RELEASE_REVIEW_APPROVED", "RELEASE_PUBLISHED"}


def test_deactivate_reactivate_hides_and_restores_from_catalog(live_conn):
    from mathbank_rest import micro_course_service as courses

    technique_id = live_conn.execute(
        text("SELECT technique_id FROM knowledge.technique LIMIT 1")
    ).scalar_one_or_none()
    if technique_id is None:
        pytest.skip("Canonical technique seed row is required")

    code = f"MC-DEACT-{uuid4().hex[:12].upper()}"
    courses.create_course(
        live_conn, code, "Deactivation test course", "pytest",
        [{"target_type": "TECHNIQUE", "target_id": str(technique_id), "role": "PRIMARY"}],
    )
    release_id = courses.create_release(live_conn, code, "pytest")
    courses.add_state(live_conn, release_id, "S001", 0, "ORIENTATION", "Start")
    courses.review_release(live_conn, release_id, "APPROVED", "pytest")
    courses.publish_release(live_conn, release_id, "pytest")

    assert any(row["canonical_code"] == code for row in courses.list_published_courses(live_conn))
    courses.deactivate_course(live_conn, code, "pytest")
    assert not any(row["canonical_code"] == code for row in courses.list_published_courses(live_conn))
    with pytest.raises(courses.MicroCourseNotFound):
        courses.get_published_course(live_conn, code)
    with pytest.raises(courses.MicroCourseConflict, match="already deactivated"):
        courses.deactivate_course(live_conn, code, "pytest")
    # Deactivation must not trip the published-identity-immutability guard.
    courses.reactivate_course(live_conn, code, "pytest")
    assert any(row["canonical_code"] == code for row in courses.list_published_courses(live_conn))
    assert courses.get_course(live_conn, code)["is_active"] is True


def test_diff_releases_reports_added_and_changed_states(live_conn):
    from mathbank_rest import micro_course_service as courses

    technique_id = live_conn.execute(
        text("SELECT technique_id FROM knowledge.technique LIMIT 1")
    ).scalar_one_or_none()
    if technique_id is None:
        pytest.skip("Canonical technique seed row is required")

    code = f"MC-DIFF-{uuid4().hex[:12].upper()}"
    courses.create_course(
        live_conn, code, "Diff test course", "pytest",
        [{"target_type": "TECHNIQUE", "target_id": str(technique_id), "role": "PRIMARY"}],
    )
    release_a = courses.create_release(live_conn, code, "pytest")
    courses.add_state(live_conn, release_a, "S001", 0, "ORIENTATION", "Start")
    courses.review_release(live_conn, release_a, "APPROVED", "pytest")
    courses.publish_release(live_conn, release_a, "pytest")

    release_b = courses.create_release(live_conn, code, "pytest", parent_release_id=release_a)
    courses.add_state(live_conn, release_b, "S001", 0, "ORIENTATION", "Start (renamed)")
    courses.add_state(live_conn, release_b, "S002", 1, "SUMMARY", "Finish")

    diff = courses.diff_releases(live_conn, release_a, release_b)
    assert diff["states_added"] == ["S002"]
    assert diff["states_removed"] == []
    assert len(diff["states_changed"]) == 1
    assert diff["states_changed"][0]["state_key"] == "S001"
    assert diff["states_changed"][0]["before"]["title"] == "Start"
    assert diff["states_changed"][0]["after"]["title"] == "Start (renamed)"

    with pytest.raises(courses.MicroCourseNotFound):
        courses.diff_releases(live_conn, release_a, str(uuid4()))


def test_course_activity_and_interaction_event_signals(live_conn):
    from mathbank_rest import micro_course_service as courses

    technique_id = live_conn.execute(
        text("SELECT technique_id FROM knowledge.technique LIMIT 1")
    ).scalar_one_or_none()
    student_id = live_conn.execute(
        text("SELECT student_id FROM learner.student_profile LIMIT 1")
    ).scalar_one_or_none()
    version_id = live_conn.execute(
        text("""
        SELECT interaction_template_version_id FROM visual.interaction_template_version v
        JOIN visual.interaction_template t USING (interaction_template_id)
        WHERE t.template_key='SINGLE_SELECT_V1'
    """)
    ).scalar_one_or_none()
    if technique_id is None or student_id is None or version_id is None:
        pytest.skip("Canonical technique/student/template seed rows are required")
    from mathbank_rest import interaction_catalog

    interaction_catalog.load_all(live_conn)

    code = f"MC-ACTIVITY-{uuid4().hex[:12].upper()}"
    courses.create_course(
        live_conn, code, "Activity test course", "pytest",
        [{"target_type": "TECHNIQUE", "target_id": str(technique_id), "role": "PRIMARY"}],
    )
    release_id = courses.create_release(live_conn, code, "pytest")
    state_id = courses.add_state(live_conn, release_id, "S001", 0, "VISUAL", "Explore")

    # A real, approved interaction instance bound to a PUBLISHED template version.
    live_conn.execute(
        text("""
        UPDATE visual.interaction_template_version
        SET input_schema=CAST(:schema AS jsonb), state_schema=CAST(:schema AS jsonb),
            event_schema=CAST(:schema AS jsonb), output_schema=CAST(:schema AS jsonb),
            accessibility_policy=CAST(:schema AS jsonb)
        WHERE interaction_template_version_id=:id AND status != 'PUBLISHED'
    """),
        {"id": version_id, "schema": '{"ok": true}'},
    )
    live_conn.execute(
        text("""
        UPDATE visual.interaction_template_version SET status='PUBLISHED', published_at=now()
        WHERE interaction_template_version_id=:id AND status IN ('DRAFT','REVIEWED')
    """),
        {"id": version_id},
    )
    instance_id = live_conn.execute(
        text("""
        INSERT INTO visual.interaction_instance
            (interaction_template_version_id, canonical_code, title, instance_config,
             learning_objective, success_criteria, content_hash, created_by, review_status)
        VALUES (:v, :code, 'Test instance', '{}', 'Objective', '{}', 'h', 'pytest', 'APPROVED')
        RETURNING interaction_instance_id
    """),
        {"v": version_id, "code": f"INT-TEST-{uuid4().hex[:8]}"},
    ).scalar_one()
    courses.attach_interaction(live_conn, state_id, str(instance_id), 0)

    # A real, attached quiz activity.
    activity_id = live_conn.execute(
        text("""
        INSERT INTO activity.definition
            (activity_type, prompt, options, correctness_policy, source_type, persistence_mode, created_by)
        VALUES ('MCQ', 'Test prompt?', CAST(:options AS jsonb), CAST(:policy AS jsonb),
                'INSTRUCTOR_CREATED', 'STATIC', 'pytest')
        RETURNING activity_id
    """),
        {"options": '["A", "B"]', "policy": '{"correct_index": 0}'},
    ).scalar_one()
    courses.attach_activity(live_conn, state_id, str(activity_id), 0, "ENTRY_CHECK", required=False)

    courses.review_release(live_conn, release_id, "APPROVED", "pytest")
    courses.publish_release(live_conn, release_id, "pytest")

    runtime = courses.start_enrollment(live_conn, code, str(student_id))
    enrollment_id = runtime["enrollment_id"]
    response = courses.submit_activity_response(live_conn, enrollment_id, str(student_id), str(activity_id), choice_index=0)
    assert response["is_correct"] is True

    event_id = courses.record_interaction_event(
        live_conn, enrollment_id, str(student_id), str(instance_id),
        event_type="CONTROL_SETTLED", semantic_action="ADJUST_CONTROL",
        control_key="x", action_payload={"value": 1},
    )
    assert event_id
    outbox_count = live_conn.execute(
        text("SELECT count(*) FROM pipeline.outbox_event WHERE event_type='LEARNER_SIGNAL'")
    ).scalar_one()
    assert outbox_count >= 1

    activity_stats = courses.get_course_activity(live_conn, code)
    assert activity_stats["total_enrollments"] == 1
    assert activity_stats["in_progress"] == 1
    quiz = next(q for q in activity_stats["quiz_accuracy"] if q["activity_id"] == str(activity_id))
    assert quiz["attempts"] == 1
    assert quiz["correct"] == 1

    with pytest.raises(courses.MicroCourseNotFound):
        courses.record_interaction_event(
            live_conn, str(uuid4()), str(student_id), str(instance_id),
            event_type="X", semantic_action="Y",
        )


def test_course_preview_shows_unpublished_draft_content(live_conn):
    """AMC-14: admin preview must render a DRAFT release in the same reader shape as
    the public endpoint, while the public endpoint keeps rejecting it as not found."""
    from mathbank_rest import micro_course_service as courses

    technique_id = live_conn.execute(
        text("SELECT technique_id FROM knowledge.technique LIMIT 1")
    ).scalar_one_or_none()
    if technique_id is None:
        pytest.skip("Canonical technique seed row is required")

    code = f"MC-PREVIEW-{uuid4().hex[:12].upper()}"
    courses.create_course(
        live_conn, code, "Preview test course", "pytest",
        [{"target_type": "TECHNIQUE", "target_id": str(technique_id), "role": "PRIMARY"}],
    )
    release_id = courses.create_release(live_conn, code, "pytest")
    courses.add_state(live_conn, release_id, "S001", 0, "ORIENTATION", "Start here")

    with pytest.raises(courses.MicroCourseNotFound):
        courses.get_published_course(live_conn, code)

    preview = courses.get_course_preview(live_conn, code)
    assert preview["canonical_code"] == code
    assert preview["release_status"] == "DRAFT"
    assert preview["version"] == 1
    assert [s["state_key"] for s in preview["states"]] == ["S001"]

    preview_by_id = courses.get_course_preview(live_conn, code, release_id)
    assert str(preview_by_id["release_id"]) == release_id

    with pytest.raises(courses.MicroCourseNotFound):
        courses.get_course_preview(live_conn, code, str(uuid4()))
