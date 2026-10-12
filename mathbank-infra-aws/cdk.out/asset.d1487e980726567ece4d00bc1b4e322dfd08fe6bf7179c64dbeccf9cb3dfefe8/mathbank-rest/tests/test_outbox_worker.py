"""Outbox consumers + stale-attempt job (runtime_extension/08 and 16).

Live tests (MATHBANK_LIVE_STEP_RUNTIME_TEST=1) run in one transaction that always rolls back.
"""
from __future__ import annotations

import os
from contextlib import nullcontext
from uuid import uuid4

import pytest
from sqlalchemy import text

from mathbank_rest import outbox_worker as ow
from mathbank_rest import step_runtime as rt


def test_consumers_subscribe_to_spec_16_events():
    subscribed = {t for c in ow.CONSUMERS for t in c.event_types}
    assert {"CONTENT_PACKAGE_IMPORTED", "SOLUTION_STEP_CHANGED", "LEARNING_ITEM_PUBLISHED", "ATTEMPT_STARTED",
            "STEP_EVALUATED", "KNOWLEDGE_GAP_CREATED", "RECOVERY_PLAN_CREATED",
            "RECOVERY_PLAN_COMPLETED"} <= subscribed
    assert len({c.name for c in ow.CONSUMERS}) == len(ow.CONSUMERS)


def test_projection_targets_match_migration_018_checks():
    targets = {t for rules in ow.PROJECTIONS.values() for t, _, _ in rules}
    scopes = {s for rules in ow.PROJECTIONS.values() for _, s, _ in rules}
    assert targets <= {"GRAPH_TEXTBOOK_STEPS", "STEP_EMBEDDINGS", "LEARNING_ITEM_EMBEDDINGS", "GRAPH_LEARNING_ITEMS"}
    assert scopes <= {"BOOK", "PACKAGE", "PROBLEM", "STEP", "LEARNING_ITEM"}


class _Recorder:
    def __init__(self):
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((str(statement), params))


def test_analytics_ignores_events_without_student():
    conn = _Recorder()
    ow._analytics(conn, {"event_type": "ATTEMPT_STARTED", "payload": {}, "created_at": "2024-01-01T00:00:00Z"})
    assert conn.calls == []


def test_analytics_counts_step_success():
    conn = _Recorder()
    ow._analytics(conn, {"event_type": "STEP_EVALUATED", "created_at": "2024-01-01T00:00:00Z",
                         "payload": {"student_id": str(uuid4()), "result": "SUCCESS"}})
    sql, params = conn.calls[0]
    assert "steps_evaluated" in sql and params["ok"] == 1


def test_projection_uses_book_code_or_aggregate():
    conn = _Recorder()
    ow._projection(conn, {"event_type": "CONTENT_PACKAGE_IMPORTED", "aggregate_id": "pkg", "outbox_event_id": "e",
                          "payload": {"book_code": "PRASOLOV_PGV1"}})
    assert {p["sid"] for _, p in conn.calls} == {"PRASOLOV_PGV1"} and len(conn.calls) == 4
    conn = _Recorder()
    ow._projection(conn, {"event_type": "LEARNING_ITEM_PUBLISHED", "aggregate_id": "LI-1", "outbox_event_id": "e",
                          "payload": {}})
    assert {(p["t"], p["sid"]) for _, p in conn.calls} == {
        ("LEARNING_ITEM_EMBEDDINGS", "LI-1"), ("GRAPH_LEARNING_ITEMS", "LI-1")}


# ---------------------------------------------------------------- live (rolled back)

live = pytest.mark.skipif(os.getenv("MATHBANK_LIVE_STEP_RUNTIME_TEST") != "1", reason="Live Postgres opt-in")


@pytest.fixture
def live_conn():
    from mathbank_rest.db.postgres import engine

    with engine.connect() as conn:
        tx = conn.begin()
        try:
            yield conn
        finally:
            tx.rollback()


def _student(conn):
    return conn.execute(text(
        "INSERT INTO learner.student_profile (email, password_hash, first_name, last_name, display_name) "
        "VALUES (:e, 'x', 'Live', 'Test', 'Live Test') RETURNING student_id"),
        {"e": f"live-{uuid4()}@example.invalid"}).scalar_one()


@live
def test_live_events_consumers_and_abandonment(live_conn):
    conn = live_conn
    student = _student(conn)
    problem = conn.execute(text(
        "SELECT problem_id::text FROM pedagogy.solution_step WHERE publication_status = 'PUBLISHED' "
        "GROUP BY problem_id HAVING count(*) >= 2 ORDER BY problem_id LIMIT 1")).scalar_one()
    attempt = rt.start_attempt(conn, student, problem, "ow-start")["solve_attempt_id"]
    rt.start_attempt(conn, student, problem, "ow-start-2")  # resume -> PROBLEM_VIEWED(resumed)
    runtime = rt.get_runtime(conn, attempt, student)
    step, version = runtime["current_step"]["solution_step_id"], runtime["attempt"]["state_version"]
    hint = rt.request_hint(conn, student, attempt, step, version, None)
    rt.record_hint_presented(conn, student, attempt, step, hint["help_level"], "test")
    rt.record_step_outcome(conn, attempt, step, "SUCCESS", hint["state_version"])
    types = [e["event_type"] for e in rt.list_events(conn, student, attempt_id=attempt, limit=200)]
    assert types.count("PROBLEM_VIEWED") == 2 and "HINT_PRESENTED" in types

    factory = lambda: nullcontext(conn)  # noqa: E731 — same rolled-back transaction
    ow.drain_all(factory)
    row = conn.execute(text(
        "SELECT attempts_started, steps_evaluated, steps_succeeded FROM analytics.learner_daily_activity "
        " WHERE student_id = :s"), {"s": student}).one()
    assert tuple(row) == (1, 1, 1)
    assert ow.drain_all(factory) == {c.name: 0 for c in ow.CONSUMERS}  # exactly-once per consumer
    row2 = conn.execute(text("SELECT attempts_started FROM analytics.learner_daily_activity WHERE student_id = :s"),
                        {"s": student}).scalar_one()
    assert row2 == 1

    abandoned = rt.abandon_stale_attempts(conn, idle_days=-1, limit=10_000)  # everything counts as idle
    assert attempt in abandoned
    assert conn.execute(text("SELECT status FROM learner.solve_attempt WHERE solve_attempt_id = :a"),
                        {"a": attempt}).scalar_one() == "ABANDONED"
    ow.drain_all(factory)
    assert conn.execute(text("SELECT attempts_abandoned FROM analytics.learner_daily_activity WHERE student_id = :s"),
                        {"s": student}).scalar_one() == 1
