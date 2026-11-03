"""Deterministic student step runtime (v2 Phase 6).

Spec: runtime_extension/08 (events), 09 (step state machine), 13 (REST), 16 (idempotency,
optimistic concurrency, outbox), 17 (hidden-solution security).

The tutor agent never owns this state: it reads and mutates it through these functions (via REST),
exactly like the web workspace. Every function takes an open SQLAlchemy connection inside a
transaction, so callers control commit/rollback (routes commit; live tests roll back).

Security rule: nothing returned to a student contains canonical ``step_text`` of any step; future
steps are reported only as counts.
"""
from __future__ import annotations

import json
import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

# The pure logic (state machine, guards, payload builders, errors) lives in step_logic so the DynamoDB backend shares it without SQL;
# everything is re-exported here, so ``step_runtime.<name>`` keeps working for the SQL modules and the tests.
from mathbank_rest.step_logic import (  # noqa: F401
    CURRENT_STEP_KEYS,
    DONE_STATES,
    HELP_LEVELS,
    INTERNAL_ACTORS,
    MAX_HELP_LEVEL,
    OUTCOMES,
    STUDENT_EVALUATION_FIELDS,
    SUCCESS_STATES,
    IdempotencyKeyReused,
    InvalidTransition,
    NotFound,
    RuntimeError_,
    StateVersionConflict,
    StepRef,
    build_runtime_view,
    check_version,
    next_step,
    outcome_transition,
    request_hash,
    require_current_step,
    returned_from_detour,
    steps_from_dag,
)
from mathbank_rest.step_logic import student_evaluation as _student_evaluation  # noqa: F401

log = logging.getLogger(__name__)

# Prasolov solutions often say "similar to heading a)" or "Similarly, ...": not self-contained, so such
# text is never used as a recovery question, answer key, worked example or probe (PostgreSQL ARE, case-insensitive).
CROSS_REFERENCE_STUB_RE = (
    r"(similar(ly)?\s+to\s+(that\s+of\s+)?(the\s+)?(solution|reasoning|proof|heading|problem|case)"
    r"|^\s*(we\s+)?(similarly|analogously)\M"
    r"|analogous(ly)?\s+to\s+(the\s+)?(solution|problem|heading|case)"
    r"|\mheading\s+[a-z][)]"
    r"|is\s+(proved|solved)\s+(similarly|analogously))"
)

# ---------------------------------------------------------------- persistence helpers

def _replay(conn: Connection, student_id: UUID, key: str | None, operation: str, body: dict) -> dict | None:
    if not key:
        return None
    row = conn.execute(text(
        "SELECT operation, request_hash, response FROM learner.idempotency_record "
        "WHERE student_id = :s AND idempotency_key = :k"), {"s": str(student_id), "k": key}).mappings().first()
    if row is None:
        return None
    if row["operation"] != operation or row["request_hash"] != request_hash(operation, body):
        raise IdempotencyKeyReused("Idempotency-Key was already used for a different request")
    return {**row["response"], "replayed": True}


def _remember(conn: Connection, student_id: UUID, key: str | None, operation: str, body: dict,
              response: dict) -> dict:
    if key:
        conn.execute(text(
            "INSERT INTO learner.idempotency_record (student_id, idempotency_key, operation, request_hash, response) "
            "VALUES (:s, :k, :op, :h, CAST(:r AS jsonb))"),
            {"s": str(student_id), "k": key, "op": operation, "h": request_hash(operation, body),
             "r": json.dumps(response, default=str)})
    return {**response, "replayed": False}


def _event(conn: Connection, student_id: UUID, attempt_id: UUID | str | None, event_type: str, actor: str,
           *, step_id: str | None = None, payload: dict | None = None, key: str | None = None) -> str:
    return str(conn.execute(text(
        "INSERT INTO learner.event (student_id, solve_attempt_id, event_type, actor_type, solution_step_id, "
        "payload, idempotency_key) VALUES (:s, :a, :t, :actor, :step, CAST(:p AS jsonb), :k) RETURNING event_id"),
        {"s": str(student_id), "a": str(attempt_id) if attempt_id else None, "t": event_type, "actor": actor,
         "step": step_id, "p": json.dumps(payload or {}, default=str), "k": key}).scalar_one())


def _outbox(conn: Connection, event_type: str, aggregate_type: str, aggregate_id: str, payload: dict) -> None:
    conn.execute(text(
        "INSERT INTO pipeline.outbox_event (event_type, aggregate_type, aggregate_id, payload) "
        "VALUES (:t, :at, :aid, CAST(:p AS jsonb))"),
        {"t": event_type, "at": aggregate_type, "aid": aggregate_id, "p": json.dumps(payload, default=str)})


def _content():
    from mathbank_rest import stores

    return stores.get_store("content")


def _dag(conn: Connection, problem_id: str) -> dict:
    return _content().get_solution_dag(problem_id=problem_id, conn=conn)


def _steps(conn: Connection, problem_id: str) -> tuple[list[StepRef], dict[str, set[str]]]:
    return steps_from_dag(_dag(conn, problem_id))


def _states(conn: Connection, attempt_id: str) -> dict[str, dict]:
    return {r["solution_step_id"]: dict(r) for r in conn.execute(text(
        "SELECT * FROM learner.attempt_step_state WHERE solve_attempt_id = :a"), {"a": attempt_id}).mappings()}


def _lock_attempt(conn: Connection, attempt_id: UUID | str, student_id: UUID | None) -> dict:
    """Lock the session row; a student may only touch their own attempts (others look like 404)."""
    row = conn.execute(text(
        "SELECT a.*, r.state_version, r.current_mode FROM learner.solve_attempt a "
        "JOIN tutor.runtime_state r ON r.solve_attempt_id = a.solve_attempt_id "
        "WHERE a.solve_attempt_id = CAST(:a AS uuid) FOR UPDATE OF a, r"), {"a": str(attempt_id)}).mappings().first()
    if row is None or (student_id is not None and str(row["student_id"]) != str(student_id)):
        raise NotFound("attempt not found")
    return dict(row)


def _check_version(attempt: dict, state_version: int) -> None:
    check_version(attempt["state_version"], state_version)


def _require_current_step(attempt: dict, step_id: str) -> None:
    require_current_step(attempt["status"], attempt.get("current_mode"), attempt["current_solution_step_id"], step_id)


def _present(conn: Connection, attempt: dict, step: StepRef, actor: str) -> None:
    conn.execute(text(
        "INSERT INTO learner.attempt_step_state (solve_attempt_id, solution_step_id, state, first_seen_at) "
        "VALUES (:a, :s, 'PRESENTED', now()) "
        "ON CONFLICT (solve_attempt_id, solution_step_id) DO UPDATE SET "
        "  state = CASE WHEN learner.attempt_step_state.state = 'FAILED' THEN 'RETRY_PRESENTED' "
        "               ELSE learner.attempt_step_state.state END, last_updated_at = now()"),
        {"a": str(attempt["solve_attempt_id"]), "s": step.solution_step_id})
    _event(conn, attempt["student_id"], attempt["solve_attempt_id"], "STEP_PRESENTED", actor,
           step_id=step.solution_step_id)


def _set_position(conn: Connection, attempt: dict, step: StepRef | None, mode: str | None = None) -> int:
    conn.execute(text(
        "UPDATE learner.solve_attempt SET current_solution_part_id = :part, current_solution_step_id = :step "
        "WHERE solve_attempt_id = :a"),
        {"a": str(attempt["solve_attempt_id"]), "part": step.solution_part_id if step else None,
         "step": step.solution_step_id if step else None})
    return conn.execute(text(
        "UPDATE tutor.runtime_state SET current_step_id = :step, state_version = state_version + 1, "
        "current_mode = coalesce(:mode, current_mode), updated_at = now() "
        "WHERE solve_attempt_id = :a RETURNING state_version"),
        {"a": str(attempt["solve_attempt_id"]), "step": step.solution_step_id if step else None,
         "mode": mode}).scalar_one()


def _bump_version(conn: Connection, attempt_id) -> int:
    return conn.execute(text(
        "UPDATE tutor.runtime_state SET state_version = state_version + 1, updated_at = now() "
        "WHERE solve_attempt_id = :a RETURNING state_version"), {"a": str(attempt_id)}).scalar_one()


# ---------------------------------------------------------------- read model

def get_runtime(conn: Connection, attempt_id: UUID | str, student_id: UUID | None) -> dict:
    """Student-safe runtime view: the current step's metadata, never canonical step text."""
    attempt = conn.execute(text(
        "SELECT a.solve_attempt_id, a.student_id, a.problem_id, a.attempt_number, a.status, a.started_at, "
        "       a.submitted_at, a.completed_at, a.current_solution_part_id, a.current_solution_step_id, "
        "       a.recovery_plan_id, r.current_recovery_plan_id, r.state_version, r.current_mode, "
        "       p.canonical_code AS problem_code, p.statement_text "
        "  FROM learner.solve_attempt a JOIN tutor.runtime_state r USING (solve_attempt_id) "
        "  JOIN core.problem p ON p.problem_id = a.problem_id WHERE a.solve_attempt_id = CAST(:a AS uuid)"),
        {"a": str(attempt_id)}).mappings().first()
    if attempt is None or (student_id is not None and str(attempt["student_id"]) != str(student_id)):
        raise NotFound("attempt not found")
    attempt = dict(attempt)
    dag = _dag(conn, str(attempt["problem_id"]))
    attempt_id = str(attempt["solve_attempt_id"])
    from mathbank_rest import step_diagnosis, step_recovery

    return build_runtime_view(
        attempt, dag, _states(conn, attempt_id),
        step_lookup=lambda step_id: _content().get_step_details([step_id]).get(step_id),
        diagnosis_for_step=lambda step_id: step_diagnosis.student_view(step_diagnosis.latest_for_step(conn, attempt_id, step_id)),
        recovery=step_recovery.recovery_summary(conn, attempt_id))


# ---------------------------------------------------------------- mutations

def start_attempt(conn: Connection, student_id: UUID, problem_id: UUID | str,
                  idempotency_key: str | None = None) -> dict:
    """Start (or resume) the student's open solving session for a problem."""
    body = {"problem_id": str(problem_id)}
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"solve:{student_id}:{problem_id}"})
    replay = _replay(conn, student_id, idempotency_key, "start_attempt", body)
    if replay:
        return replay
    existing = conn.execute(text(
        "SELECT solve_attempt_id FROM learner.solve_attempt WHERE student_id = :s AND problem_id = CAST(:p AS uuid) "
        "AND status = 'IN_PROGRESS'"), {"s": str(student_id), "p": str(problem_id)}).scalar()
    if existing:
        _event(conn, student_id, existing, "PROBLEM_VIEWED", "STUDENT", payload={"resumed": True})
        response = {"solve_attempt_id": str(existing), "resumed": True}
        return _remember(conn, student_id, idempotency_key, "start_attempt", body, response)
    steps, prereqs = _steps(conn, str(problem_id))
    if not steps:
        raise InvalidTransition("problem has no published solution steps for the step runtime")
    attempt_id = conn.execute(text(
        "INSERT INTO learner.solve_attempt (student_id, problem_id, attempt_number) "
        "SELECT :s, CAST(:p AS uuid), coalesce(max(attempt_number), 0) + 1 FROM learner.solve_attempt "
        " WHERE student_id = :s AND problem_id = CAST(:p AS uuid) RETURNING solve_attempt_id"),
        {"s": str(student_id), "p": str(problem_id)}).scalar_one()
    conn.execute(text(
        "INSERT INTO tutor.runtime_state (student_id, solve_attempt_id, current_problem_id) "
        "VALUES (:s, :a, CAST(:p AS uuid))"), {"s": str(student_id), "a": str(attempt_id), "p": str(problem_id)})
    _event(conn, student_id, attempt_id, "ATTEMPT_STARTED", "STUDENT", payload=body, key=idempotency_key)
    _event(conn, student_id, attempt_id, "PROBLEM_VIEWED", "STUDENT", payload={"resumed": False})
    attempt = _lock_attempt(conn, attempt_id, student_id)
    first = next_step(steps, {}, prereqs)
    _present(conn, attempt, first, "SYSTEM")
    _set_position(conn, attempt, first)
    _outbox(conn, "ATTEMPT_STARTED", "solve_attempt", str(attempt_id),
            {"student_id": str(student_id), "problem_id": str(problem_id)})
    response = {"solve_attempt_id": str(attempt_id), "resumed": False}
    return _remember(conn, student_id, idempotency_key, "start_attempt", body, response)


def submit_step_response(conn: Connection, student_id: UUID, attempt_id: UUID | str, step_id: str,
                         response_text: str, state_version: int, idempotency_key: str | None = None) -> dict:
    """Persist a student's response for the current step. Evaluation is a separate step (Phase 8)."""
    body = {"attempt_id": str(attempt_id), "step_id": step_id, "response_text": response_text,
            "state_version": state_version}
    attempt = _lock_attempt(conn, attempt_id, student_id)
    replay = _replay(conn, student_id, idempotency_key, "step_response", body)
    if replay:
        return replay
    _check_version(attempt, state_version)
    _require_current_step(attempt, step_id)
    conn.execute(text(
        "UPDATE learner.attempt_step_state SET state = 'ATTEMPTED', attempt_count = attempt_count + 1, "
        "  first_attempted_at = coalesce(first_attempted_at, now()), last_response_text = :r, "
        "  last_updated_at = now() WHERE solve_attempt_id = :a AND solution_step_id = :s"),
        {"a": str(attempt_id), "s": step_id, "r": response_text})
    event_id = _event(conn, student_id, attempt_id, "STEP_RESPONSE_SUBMITTED", "STUDENT", step_id=step_id,
                      payload={"response": response_text}, key=idempotency_key)
    version = _bump_version(conn, attempt_id)
    response = {"event_id": event_id, "state": "ATTEMPTED", "evaluation_status": "PENDING",
                "state_version": version}
    return _remember(conn, student_id, idempotency_key, "step_response", body, response)


def request_hint(conn: Connection, student_id: UUID, attempt_id: UUID | str, step_id: str,
                 state_version: int, idempotency_key: str | None = None) -> dict:
    """Escalate help by one level (max 5). Any help makes later success non-independent."""
    body = {"attempt_id": str(attempt_id), "step_id": step_id, "state_version": state_version}
    attempt = _lock_attempt(conn, attempt_id, student_id)
    replay = _replay(conn, student_id, idempotency_key, "hint", body)
    if replay:
        return replay
    _check_version(attempt, state_version)
    _require_current_step(attempt, step_id)
    level = conn.execute(text(
        "UPDATE learner.attempt_step_state SET help_level_used = least(help_level_used + 1, :max), "
        "  last_updated_at = now() WHERE solve_attempt_id = :a AND solution_step_id = :s "
        "RETURNING help_level_used"), {"a": str(attempt_id), "s": step_id, "max": MAX_HELP_LEVEL}).scalar_one()
    _event(conn, student_id, attempt_id, "HINT_REQUESTED", "STUDENT", step_id=step_id,
           payload={"help_level": level, "help_kind": HELP_LEVELS[level]}, key=idempotency_key)
    version = _bump_version(conn, attempt_id)
    # hint_text is attached by the caller after commit (step_tutor.get_or_create_hint), outside the row lock
    response = {"help_level": level, "help_kind": HELP_LEVELS[level], "hint_text": None,
                "state_version": version}
    return _remember(conn, student_id, idempotency_key, "hint", body, response)


def record_step_outcome(conn: Connection, attempt_id: UUID | str, step_id: str, result: str, state_version: int,
                        *, actor: str = "TUTOR", evaluation: dict | None = None,
                        idempotency_key: str | None = None) -> dict:
    """Apply an evaluated outcome (from the evaluator/agent, never self-graded by the student) and advance."""
    if actor not in INTERNAL_ACTORS:
        raise InvalidTransition("step outcomes are recorded by the tutor/evaluator, not the student")
    attempt = _lock_attempt(conn, attempt_id, None)
    student_id = attempt["student_id"]
    body = {"attempt_id": str(attempt_id), "step_id": step_id, "result": result, "state_version": state_version,
            "evaluation": evaluation or {}}
    replay = _replay(conn, student_id, idempotency_key, "step_outcome", body)
    if replay:
        return replay
    _check_version(attempt, state_version)
    _require_current_step(attempt, step_id)
    state_row = _states(conn, str(attempt_id)).get(step_id, {})
    new_state, event_type, independent = outcome_transition(result, state_row.get("help_level_used", 0))
    conn.execute(text(
        "UPDATE learner.attempt_step_state SET state = :st, independent_success = :ind, "
        "  last_evaluation = CAST(:ev AS jsonb), last_updated_at = now() "
        "WHERE solve_attempt_id = :a AND solution_step_id = :s"),
        {"a": str(attempt_id), "s": step_id, "st": new_state, "ind": independent,
         "ev": json.dumps({"result": result, **(evaluation or {})})})
    _event(conn, student_id, attempt_id, "STEP_EVALUATED", actor, step_id=step_id,
           payload={"result": result, "evaluation": evaluation or {}}, key=idempotency_key)
    _event(conn, student_id, attempt_id, event_type, actor, step_id=step_id,
           payload={"help_level_used": state_row.get("help_level_used", 0)})
    _outbox(conn, "STEP_EVALUATED", "solve_attempt", str(attempt_id),
            {"student_id": str(student_id), "solution_step_id": step_id, "result": result, "state": new_state})
    gap_changes, diagnosis = _diagnosis_hooks(conn, attempt, step_id, result, independent, actor, state_row)
    steps, prereqs = _steps(conn, str(attempt["problem_id"]))
    states = {k: v["state"] for k, v in _states(conn, str(attempt_id)).items()}
    upcoming = next_step(steps, states, prereqs)
    completed = upcoming is None
    if new_state in DONE_STATES and _returned_from_detour(conn, attempt_id, step_id):
        _event(conn, student_id, attempt_id, "RETURNED_TO_ORIGINAL_PROBLEM", "SYSTEM", step_id=step_id,
               payload={"next_step_id": upcoming.solution_step_id if upcoming else None})
    if upcoming is not None:  # a FAILED current step is re-presented as RETRY_PRESENTED
        _present(conn, attempt, upcoming, "SYSTEM")
    version = _set_position(conn, attempt, upcoming, "COMPLETED" if completed else None)
    outcome = _complete(conn, attempt, states) if completed else None
    response = {"state": new_state, "independent_success": independent,
                "current_step_id": upcoming.solution_step_id if upcoming else None,
                "attempt_completed": completed, "outcome_attempt": outcome, "state_version": version,
                "student_id": str(student_id), "problem_id": str(attempt["problem_id"]),
                "gap_status_changes": gap_changes, "diagnosis": diagnosis}
    return _remember(conn, student_id, idempotency_key, "step_outcome", body, response)


def _returned_from_detour(conn: Connection, attempt_id: UUID | str, step_id: str) -> bool:
    """True once per detour: the step was resumed after recovery and the original problem now moves on."""
    return bool(conn.execute(text(
        "SELECT count(*) FILTER (WHERE event_type = 'RETURNED_TO_ORIGINAL_STEP') > "
        "       count(*) FILTER (WHERE event_type = 'RETURNED_TO_ORIGINAL_PROBLEM') "
        "  FROM learner.event WHERE solve_attempt_id = CAST(:a AS uuid) AND solution_step_id = :s "
        "   AND event_type IN ('RETURNED_TO_ORIGINAL_STEP', 'RETURNED_TO_ORIGINAL_PROBLEM')"),
        {"a": str(attempt_id), "s": step_id}).scalar())


def record_hint_presented(conn: Connection, student_id: UUID | str, attempt_id: UUID | str, step_id: str,
                          level: int, hint_source: str | None) -> None:
    """HINT_PRESENTED: the hint text actually reached the student (HINT_REQUESTED is the escalation)."""
    _event(conn, student_id, attempt_id, "HINT_PRESENTED", "TUTOR", step_id=step_id,
           payload={"help_level": level, "help_kind": HELP_LEVELS.get(level), "hint_source": hint_source})


def abandon_stale_attempts(conn: Connection, idle_days: int = 30, limit: int = 500) -> list[str]:
    """Mark IN_PROGRESS attempts with no learner event for ``idle_days`` as ABANDONED (spec 08 lifecycle).
    The student can start a fresh attempt later; the old timeline stays for review."""
    rows = conn.execute(text(
        "SELECT a.solve_attempt_id::text, a.student_id::text, coalesce(last.t, a.started_at) AS last_seen "
        "  FROM learner.solve_attempt a "
        "  CROSS JOIN LATERAL (SELECT max(e.event_time) AS t FROM learner.event e "
        "                       WHERE e.solve_attempt_id = a.solve_attempt_id) last "
        " WHERE a.status = 'IN_PROGRESS' "
        "   AND coalesce(last.t, a.started_at) < now() - make_interval(days => :d) "
        " ORDER BY 3 LIMIT :n FOR UPDATE OF a SKIP LOCKED"), {"d": idle_days, "n": limit}).all()
    for attempt_id, student_id, last_seen in rows:
        conn.execute(text("UPDATE learner.solve_attempt SET status = 'ABANDONED' WHERE solve_attempt_id = :a "
                          "AND status = 'IN_PROGRESS'"), {"a": attempt_id})
        conn.execute(text(
            "UPDATE pedagogy.recovery_plan SET status = 'ABORTED', ended_at = now(), updated_at = now() "
            " WHERE solve_attempt_id = CAST(:a AS uuid) AND status IN ('ACTIVE', 'SUSPENDED')"), {"a": attempt_id})
        _event(conn, student_id, attempt_id, "ATTEMPT_ABANDONED", "SYSTEM",
               payload={"idle_days": idle_days, "last_activity_at": last_seen})
        _outbox(conn, "ATTEMPT_ABANDONED", "solve_attempt", attempt_id, {"student_id": student_id})
    return [r[0] for r in rows]


def _diagnosis_hooks(conn: Connection, attempt: dict, step_id: str, result: str, independent: bool, actor: str,
                     state_row: dict) -> tuple[list[dict], dict | None]:
    """Phase 9: move open gap hypotheses on this skill, then auto-diagnose a repeatedly failed step.
    Runs in a savepoint so a diagnosis problem can never block recording the graded outcome."""
    from mathbank_rest import step_diagnosis  # local import: step_diagnosis imports this module

    changes: list[dict] = []
    diagnosis = None
    try:
        with conn.begin_nested():
            changes = step_diagnosis.update_gap_statuses(conn, attempt, step_id, result, independent, actor)
            if step_diagnosis.should_auto_diagnose(result, state_row.get("attempt_count", 0),
                                                   state_row.get("help_level_used", 0)):
                diagnosis = step_diagnosis.student_view(
                    step_diagnosis.diagnose_locked(conn, attempt, step_id, "AUTO", "SYSTEM"))
    except Exception as exc:  # noqa: BLE001
        log.warning("gap diagnosis skipped for %s: %s", step_id, type(exc).__name__)
        return [], None
    return changes, diagnosis


def _complete(conn: Connection, attempt: dict, states: dict[str, str]) -> dict:
    """Close the session and write one legacy learner.attempt row so mastery scoring sees it."""
    attempt_id = str(attempt["solve_attempt_id"])
    hints = conn.execute(text(
        "SELECT count(*) FROM learner.event WHERE solve_attempt_id = :a AND event_type = 'HINT_REQUESTED'"),
        {"a": attempt_id}).scalar_one()
    is_correct = bool(states) and all(s in SUCCESS_STATES for s in states.values())
    legacy = conn.execute(text(
        "INSERT INTO learner.attempt (student_id, problem_id, is_correct, hint_count, time_spent_seconds, source) "
        "SELECT student_id, problem_id, :ok, :hints, "
        "       greatest(0, extract(epoch FROM now() - started_at))::int, 'step_runtime' "
        "  FROM learner.solve_attempt WHERE solve_attempt_id = :a RETURNING attempt_id"),
        {"a": attempt_id, "ok": is_correct, "hints": hints}).scalar_one()
    conn.execute(text(
        "UPDATE learner.solve_attempt SET status = 'COMPLETED', completed_at = now(), "
        "  submitted_at = coalesce(submitted_at, now()), outcome_attempt_id = :o WHERE solve_attempt_id = :a"),
        {"a": attempt_id, "o": str(legacy)})
    _event(conn, attempt["student_id"], attempt_id, "ATTEMPT_COMPLETED", "SYSTEM",
           payload={"is_correct": is_correct, "hint_count": hints, "outcome_attempt_id": str(legacy)})
    _outbox(conn, "ATTEMPT_COMPLETED", "solve_attempt", str(attempt_id),
            {"student_id": str(attempt["student_id"]), "is_correct": is_correct})
    return {"attempt_id": str(legacy), "is_correct": is_correct, "hint_count": hints}


def submit_attempt(conn: Connection, student_id: UUID, attempt_id: UUID | str, state_version: int,
                   idempotency_key: str | None = None) -> dict:
    """Student hands in the attempt early; remaining steps stay as they are for review."""
    body = {"attempt_id": str(attempt_id), "state_version": state_version}
    attempt = _lock_attempt(conn, attempt_id, student_id)
    replay = _replay(conn, student_id, idempotency_key, "submit_attempt", body)
    if replay:
        return replay
    _check_version(attempt, state_version)
    if attempt["status"] != "IN_PROGRESS":
        raise InvalidTransition(f"attempt is {attempt['status']}")
    if attempt["current_mode"] == "RECOVERY":
        raise InvalidTransition("leave the recovery detour before handing in the attempt")
    conn.execute(text(
        "UPDATE learner.solve_attempt SET status = 'SUBMITTED', submitted_at = now() WHERE solve_attempt_id = :a"),
        {"a": str(attempt_id)})
    _event(conn, student_id, attempt_id, "ATTEMPT_SUBMITTED", "STUDENT", key=idempotency_key)
    conn.execute(text("UPDATE tutor.runtime_state SET current_mode = 'REVIEW' WHERE solve_attempt_id = :a"),
                 {"a": str(attempt_id)})
    version = _bump_version(conn, attempt_id)
    response = {"status": "SUBMITTED", "state_version": version}
    return _remember(conn, student_id, idempotency_key, "submit_attempt", body, response)


def list_events(conn: Connection, student_id: UUID, *, attempt_id: UUID | str | None = None,
                limit: int = 100) -> list[dict]:
    rows = conn.execute(text(
        "SELECT event_id, solve_attempt_id, event_type, event_time, actor_type, solution_step_id, payload "
        "  FROM learner.event WHERE student_id = :s "
        "   AND (CAST(:a AS uuid) IS NULL OR solve_attempt_id = CAST(:a AS uuid)) "
        " ORDER BY event_time DESC LIMIT :n"),
        {"s": str(student_id), "a": str(attempt_id) if attempt_id else None, "n": min(max(limit, 1), 500)})
    return [dict(r) for r in rows.mappings()]


# ---------------------------------------------------------------- SQL reads of the SolvePostgres store (the learner-store seam)

def resolve_problem(conn: Connection, problem_ref: str) -> str:
    """A problem uuid or canonical code to its uuid (content reads of the DynamoDB backend go through the content store)."""
    row = conn.execute(text(
        "SELECT problem_id::text FROM core.problem WHERE problem_id::text = :r OR canonical_code = :r LIMIT 1"),
        {"r": problem_ref}).scalar()
    if row is None:
        raise NotFound("problem not found")
    return row


def attempt_owner(conn: Connection, attempt_id: UUID | str) -> dict | None:
    row = conn.execute(text(
        "SELECT student_id, problem_id FROM learner.solve_attempt WHERE solve_attempt_id = CAST(:a AS uuid)"),
        {"a": str(attempt_id)}).mappings().first()
    return None if row is None else dict(row)


def list_events_page(conn: Connection, student_id: UUID, *, attempt_id: UUID | str | None = None, limit: int = 100,
                     after: str | None = None, cursor: str | None = None) -> tuple[list[dict], str | None]:
    """Keyset page of the event feed: newest first, or oldest first after the ``after`` instant. The cursor is a signed token."""
    from mathbank_rest.stores import ddb

    limit = min(max(limit, 1), 500)
    forward = after is not None
    bound = {"s": str(student_id), "a": str(attempt_id) if attempt_id else "", "f": forward}
    params: dict = {"s": str(student_id), "a": str(attempt_id) if attempt_id else None, "n": limit + 1}
    where = "student_id = :s AND (CAST(:a AS uuid) IS NULL OR solve_attempt_id = CAST(:a AS uuid))"
    if cursor:
        c = ddb.verify_token(cursor, **bound)
        params |= {"ct": c["t"], "ci": c["i"]}
        where += f" AND (event_time, event_id) {'>' if forward else '<'} (CAST(:ct AS timestamptz), CAST(:ci AS uuid))"
    elif after is not None:
        params["after"] = after
        where += " AND event_time > CAST(:after AS timestamptz)"
    rows = [dict(r) for r in conn.execute(text(
        "SELECT event_id, solve_attempt_id, event_type, event_time, actor_type, solution_step_id, payload "
        f"  FROM learner.event WHERE {where} "
        f" ORDER BY event_time {'ASC' if forward else 'DESC'}, event_id {'ASC' if forward else 'DESC'} LIMIT :n"),
        params).mappings()]
    token = None
    if len(rows) > limit:
        rows = rows[:limit]
        token = ddb.sign_token({**bound, "t": rows[-1]["event_time"].isoformat(), "i": str(rows[-1]["event_id"])})
    return rows, token


def list_solve_attempts(conn: Connection, student_id: UUID, status: str | None = None, *, limit: int = 50,
                        offset: int = 0) -> list[dict]:
    return [dict(r) for r in conn.execute(text(
        "SELECT a.solve_attempt_id, a.problem_id, p.canonical_code AS problem_code, a.attempt_number, a.status, "
        "       r.current_mode, a.started_at, a.submitted_at, a.completed_at, r.state_version "
        "  FROM learner.solve_attempt a JOIN tutor.runtime_state r USING (solve_attempt_id) "
        "  JOIN core.problem p ON p.problem_id = a.problem_id "
        " WHERE a.student_id = :s AND (CAST(:st AS text) IS NULL OR a.status = :st) "
        " ORDER BY a.started_at DESC, a.solve_attempt_id DESC LIMIT :n OFFSET :o"),
        {"s": str(student_id), "st": status, "n": limit, "o": offset}).mappings()]
