"""Admin: the learner directory, per-student views, account control, erasure, rebuilds and learner analytics (requirement 70 C1,
requirement 71 WP5; findings LRN-E02/E04/E05/E08/E09/E16/E17/E19/E20/E21, LRN-F05, LRN-S01/S08, ANL-E02/E03).

Auth: every route needs the admin credential (staff session or ``X-Admin-Api-Key``); everything that shows or changes a student needs
the ``manage_users`` capability (the service key holds it). The acting identity is ``Actor.id`` (``staff:<id>`` or
``service:admin-key``), never a client-supplied name, and is recorded in the ``mb-audit`` entry of each mutation (in the mutation's own
transaction where the store owns it). A learner JWT is not an admin credential.

``LEARNER_STORE=postgres`` runs today's equivalent where the store has one and answers 501 where only the DynamoDB design has the
operation (``stores/learner/admin.py``). Diagnosis and recovery views are served only when the store provides them.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from mathbank_rest import security, stores
from mathbank_rest.config import settings
from mathbank_rest.security import Actor, admin_actor, require_admin_api_key
from mathbank_rest.stores.errors import StoreNotImplemented

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin-learner"], dependencies=[Depends(require_admin_api_key)])

ManageUsers = Annotated[Actor, Depends(admin_actor("manage_users"))]
AnyStaff = Annotated[Actor, Depends(require_admin_api_key)]
Limit = Annotated[int, Query(ge=1, le=200)]
Token = Annotated[str | None, Query(max_length=2000)]
DAILY_DEFAULT_DAYS = 30


def _store():
    return stores.get_store("learner")


def _student_or_404(student_id: UUID) -> dict:
    found = _store().get_admin_student(student_id)
    if found is None:
        raise HTTPException(status_code=404, detail="no such student")
    return found


def _optional(method: str, hint: str):
    """A store operation another work package provides; 501 until it does."""
    store = _store()
    fn = getattr(store, method, None)
    if fn is None or getattr(store, "backend", "postgres") != "dynamodb":
        raise StoreNotImplemented(f"{hint} is not available on this learner store", method=method)
    return fn


def _audit(actor: Actor, action: str, entity_type: str, entity_id: str, before: dict | None, after: dict | None) -> None:
    """Audit of a mutation whose own transaction the store does not own: written right after it, a failure is logged, not hidden
    behind a response that would suggest the mutation did not happen."""
    try:
        _store().record_admin_audit(actor.id, action, entity_type, entity_id, before, after)
    except Exception:
        logger.exception("audit record %s for %s %s could not be written", action, entity_type, entity_id)


# ------------------------------------------------------------------ directory and profile (A5, A3)

@router.get("/learner/students")
def list_students(
    actor: ManageUsers, q: Annotated[str | None, Query(max_length=200)] = None,
    status: Literal["ACTIVE", "DISABLED", "DELETED", "ERASING"] | None = None, limit: Limit = 50, next_token: Token = None,
) -> dict:
    """Staff search: ``q`` matches e-mail, names (substring) or an exact student id. ``{items, limit, next_token}``; the signed
    ``next_token`` is bound to this listing."""
    return _store().list_admin_students(q=q, status=status, limit=limit, next_token=next_token)


@router.get("/learner/students/{student_id}")
def get_student(student_id: UUID, actor: ManageUsers) -> dict:
    """The profile without ``password_hash`` or ``search_blob``; status and token version included."""
    return _student_or_404(student_id)


# ------------------------------------------------------------------ per-student views (A6, A8, A13, A17, A21, A25, A32)

@router.get("/learner/students/{student_id}/attempts")
def list_student_attempts(student_id: UUID, actor: ManageUsers, limit: Limit = 50, offset: Annotated[int, Query(ge=0)] = 0) -> dict:
    _student_or_404(student_id)
    return {"items": _store().list_attempts(student_id, limit=limit, offset=offset), "limit": limit, "offset": offset}


@router.get("/learner/students/{student_id}/mastery")
def get_student_mastery(student_id: UUID, actor: ManageUsers) -> dict:
    _student_or_404(student_id)
    return _store().get_mastery_summary(student_id)


@router.get("/learner/students/{student_id}/events")
def list_student_events(student_id: UUID, actor: ManageUsers, attempt_id: UUID | None = None, limit: Limit = 100,
                        next_token: Token = None) -> dict:
    """Newest first with the FULL payload (the learner feed is allow-listed)."""
    _student_or_404(student_id)
    return _store().list_events_page(student_id, attempt_id=attempt_id, limit=limit, next_token=next_token, student_view=False)


@router.get("/learner/students/{student_id}/solve-attempts")
def list_student_solve_attempts(student_id: UUID, actor: ManageUsers,
                                status: Literal["IN_PROGRESS", "SUBMITTED", "COMPLETED", "ABANDONED"] | None = None,
                                limit: Limit = 50, next_token: Token = None) -> dict:
    _student_or_404(student_id)
    return _store().list_solve_attempts(student_id, status, limit=limit, next_token=next_token)


@router.get("/learner/students/{student_id}/misconceptions")
def list_student_misconceptions(student_id: UUID, actor: ManageUsers) -> dict:
    """Running confidence per misconception, strongest first (LRN-E20, admin half)."""
    from mathbank_rest.routers.micro_courses import learner_call

    _student_or_404(student_id)
    return learner_call("list_misconceptions", str(student_id))


@router.get("/learner/students/{student_id}/knowledge-gaps")
def list_student_gaps(student_id: UUID, actor: ManageUsers,
                      status: Literal["UNRESOLVED", "CONFIRMED", "REJECTED", "RESOLVED"] | None = None, limit: Limit = 100):
    fn = _optional("list_student_gaps", "the knowledge-gap listing")
    _student_or_404(student_id)
    return fn(student_id, status=status, limit=limit)


@router.get("/learner/students/{student_id}/recovery-plans")
def list_student_recovery_plans(student_id: UUID, actor: ManageUsers, status: str | None = None, limit: Limit = 100):
    fn = _optional("admin_plans", "the recovery-plan listing")
    _student_or_404(student_id)
    return fn(student_id=student_id, status=status, limit=limit)


@router.get("/learner/interaction-events")
def list_interaction_events(
    actor: ManageUsers, student_id: UUID | None = None, enrollment_id: UUID | None = None,
    after: Annotated[str | None, Query(max_length=64, description="ISO-8601: only events strictly after it")] = None,
    include_payload: bool = False, limit: Limit = 50, next_token: Token = None,
) -> dict:
    """Interaction telemetry (LRN-E19). Give ``enrollment_id`` (its owner is resolved) and/or ``student_id``; never a full scan."""
    store = _store()
    if student_id is None and enrollment_id is None:
        raise HTTPException(status_code=422, detail="give student_id or enrollment_id")
    if enrollment_id is not None:
        owner = store.get_enrollment_reset_info(str(enrollment_id))
        if owner is None or (student_id is not None and owner["student_id"] != str(student_id)):
            raise HTTPException(status_code=404, detail="no such enrollment")
        student_id = UUID(owner["student_id"])
    return store.list_admin_interaction_events(student_id=student_id, enrollment_id=None if enrollment_id is None else str(enrollment_id),
                                               after=after, limit=limit, next_token=next_token, include_payload=include_payload)


# ------------------------------------------------------------------ account control (T4, token version)

class ReasonBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=500)


def _set_status(student_id: UUID, new_status: str, actor: Actor, body: ReasonBody | None) -> dict:
    try:
        result = _store().set_account_status(student_id, new_status, actor.id, body.reason if body else None)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="no such student")
    security.invalidate_student_status(student_id)
    return result


@router.post("/learner/students/{student_id}/disable")
def disable_student(student_id: UUID, actor: ManageUsers, body: ReasonBody | None = None) -> dict:
    """Disable the account: every issued token stops working at once and login is refused (token version bumped)."""
    return _set_status(student_id, "DISABLED", actor, body)


@router.post("/learner/students/{student_id}/reactivate")
@router.post("/learner/students/{student_id}/enable")
def reactivate_student(student_id: UUID, actor: ManageUsers, body: ReasonBody | None = None) -> dict:
    """Re-enable a disabled account. Tokens issued before the disable stay revoked; the student signs in again."""
    return _set_status(student_id, "ACTIVE", actor, body)


@router.post("/learner/students/{student_id}/revoke-tokens")
def revoke_tokens(student_id: UUID, actor: ManageUsers) -> dict:
    """Sign the student out everywhere (token version + 1) without disabling the account."""
    try:
        result = _store().revoke_student_tokens(student_id, actor.id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="no such student")
    security.invalidate_student_status(student_id)
    return result


# ------------------------------------------------------------------ erasure (T36)

@router.post("/learner/students/{student_id}/erase", status_code=202)
def erase_student(student_id: UUID, response: Response, actor: ManageUsers, body: ReasonBody | None = None) -> dict:
    """Request the erasure of a student (MST-08). The account becomes ``ERASING`` at once (tokens rejected, e-mail still reserved) and
    the erasure worker deletes the partition, the e-mail and Cognito reservations and the stored files, then writes a tombstone.
    Repeating the request returns the same job; 200 once the erasure is done."""
    job = _store().request_erasure(student_id, actor.id, body.reason if body else None)
    security.invalidate_student_status(student_id)
    done = job["status"] == "DONE"
    if done:
        response.status_code = 200
    return {"job_id": job["job_id"], "student_id": str(student_id), "status": "ERASED" if done else "ERASING",
            "requested_at": job["requested_at"], "requested_by": job["requested_by"], "erased_at": job["erased_at"]}


@router.get("/learner/students/{student_id}/erasure")
def get_erasure(student_id: UUID, actor: ManageUsers) -> dict:
    job = _store().get_erasure_job(student_id)
    if job is None:
        raise HTTPException(status_code=404, detail="no erasure was requested for this student")
    return {**job, "status": "ERASED" if job["status"] == "DONE" else "ERASING"}


# ------------------------------------------------------------------ rebuilds and maintenance (T35, LRN-E17/E21, ANL-E03)

@router.post("/learner/students/{student_id}/mastery/rebuild")
def rebuild_student_mastery(student_id: UUID, actor: ManageUsers) -> dict:
    """Recompute this student's concept and technique scores from the evidence (one student is bounded work, done inline)."""
    return _store().rebuild_mastery(student_id, actor.id)


@router.post("/learner/mastery/rebuild")
def rebuild_mastery(actor: ManageUsers, student_id: UUID | None = None) -> dict:
    """``?student_id=`` rebuilds one student. All students is bulk work: run ``learner_consumers.rebuild_handler`` (kind ``mastery``)."""
    if student_id is None:
        raise HTTPException(status_code=422, detail="student_id is required here; the bulk rebuild is the rebuild_handler worker")
    return _store().rebuild_mastery(student_id, actor.id)


@router.post("/learner/idempotency-records/purge")
def purge_idempotency(actor: ManageUsers, student_id: UUID | None = None) -> dict:
    """Delete one student's expired receipts. Everybody's expire through DynamoDB TTL (7 days), so no bulk purge exists."""
    if student_id is None:
        raise HTTPException(status_code=422, detail="student_id is required; receipts of all students expire through the table TTL")
    return _store().purge_idempotency(student_id, actor.id)


class ImportAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    problem_code: str = Field(min_length=1, max_length=200, description="core.problem.canonical_code, e.g. AIME_1983_Q01")
    is_correct: bool
    submitted_answer: str | None = None
    time_spent_seconds: int | None = Field(default=None, ge=0)
    hint_count: int = Field(default=0, ge=0)


@router.post("/learner/students/{student_id}/attempts:import", status_code=201)
def import_attempt(student_id: UUID, body: ImportAttempt, actor: ManageUsers,
                   idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)] = None) -> dict:
    """Record a legacy/bulk outcome for a student without learner self-grading (LRN-E02): ``source`` is fixed to ``import``; mastery of
    every tag of the problem is updated with it."""
    _student_or_404(student_id)
    store = _store()
    problem_id = store.get_problem_id_by_code(body.problem_code)
    if problem_id is None:
        raise HTTPException(status_code=404, detail=f"no problem with code {body.problem_code!r}")
    result = store.record_outcome(student_id=student_id, problem_id=problem_id, is_correct=body.is_correct,
                                  submitted_answer=body.submitted_answer, time_spent_seconds=body.time_spent_seconds,
                                  hint_count=body.hint_count, source="import", idempotency_key=idempotency_key)
    _audit(actor, "STUDENT_ATTEMPT_IMPORTED", "STUDENT", str(student_id), None,
           {"problem_code": body.problem_code, "is_correct": body.is_correct, "source": "import"})
    return result


# ------------------------------------------------------------------ analytics (A41, A42)

@router.get("/analytics/learner-daily-activity")
def learner_daily_activity(
    actor: AnyStaff, student_id: UUID | None = None, date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None, group_by: Literal["day"] | None = None,
    limit: Limit = 50, next_token: Token = None,
) -> dict:
    """Engagement counters per student and UTC day (default: the last 30 days, at most 366). With ``student_id``: that student's days.
    Without: one directory page of ``limit`` students (``next_token`` continues); ``group_by=day`` sums the page per day."""
    end = date_to or datetime.now(UTC).date()
    start = date_from or end - timedelta(days=DAILY_DEFAULT_DAYS - 1)
    return _store().list_admin_daily_activity(date_from=start, date_to=end, student_id=student_id, limit=limit, next_token=next_token,
                                              group_by=group_by)


class RebuildDaily(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: UUID


@router.post("/analytics/learner-daily-activity/rebuild")
def rebuild_daily_activity(body: RebuildDaily, actor: ManageUsers) -> dict:
    """Recompute one student's daily counters from its events (audited). All students: ``learner_consumers.rebuild_handler``
    (kind ``daily``)."""
    return _store().rebuild_daily_activity(body.student_id, actor.id)


@router.get("/analytics/weak-concepts")
def weak_concepts(actor: AnyStaff, min_students: Annotated[int, Query(ge=1)] = 1, limit: Annotated[int, Query(ge=1, le=100)] = 20) -> dict:
    """Cohort weak concepts (no PII), lowest average first; a concept needs at least ``cohort_min_students`` learners."""
    floor = settings.cohort_min_students
    results = _store().get_cohort_weak_concepts(min_students=max(min_students, floor), limit=limit)
    body: dict[str, Any] = {"results": results, "suppressed": not results, "cohort_min_students": floor}
    if not results:
        body["note"] = f"No concept has at least {floor} learners; aggregates below that size are withheld."
    return body
