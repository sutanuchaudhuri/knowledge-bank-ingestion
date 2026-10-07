"""Student step runtime REST (v2 Phase 6) — runtime_extension/13.

Students act through their JWT on their own attempts only (path ``student_id`` must equal the
token subject). ``POST .../outcome`` records an *evaluated* step result: it is an internal
tutor/evaluator endpoint guarded by the admin API key until the Phase 8 step evaluator exists, so a
student can never self-grade. Since Phase 8 a submitted response is graded automatically by the
step evaluator (``step_tutor``) *after* the response commits, outside the row lock, and applied with
the returned ``state_version``; hints carry generated text (levels 1–4, cached per step) or the
reference step (level 5). Mutations accept an ``Idempotency-Key`` header and require the
``state_version`` they last saw (stale → 409 STATE_VERSION_CONFLICT).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from mathbank_rest import mastery, security, step_diagnosis, step_recovery, step_runtime, step_tutor
from mathbank_rest.db.postgres import engine
from mathbank_rest.db.problem_images import STUDENT_IMAGE_FILTER, list_images
from mathbank_rest.db.problem_sources import (
    highlighted_page,
    highlighted_pdf,
    problem_location,
    source_metadata,
    source_pdf,
    source_record,
)
from mathbank_rest.db.step_search import similar_steps_for_step

router = APIRouter(prefix="/v1", tags=["step-runtime"])
log = logging.getLogger(__name__)

# Injectable model calls (tests replace these; production uses OpenAI via the project .env key).
EVALUATOR = step_tutor.openai_evaluator
HINT_WRITER = step_tutor.openai_hint_writer
RERANKER = step_diagnosis.openai_reranker  # used only when DIAGNOSIS_LLM_RERANK is on
IMAGE_ROOT = Path(__file__).resolve().parents[4]

IdempotencyKey = Header(default=None, alias="Idempotency-Key", max_length=200)


class StepResponseRequest(BaseModel):
    response_text: str = Field(min_length=1, max_length=10_000)
    state_version: int = Field(ge=1)
    evaluate: bool = Field(True, description="Grade with the step evaluator right after saving")


class VersionedRequest(BaseModel):
    state_version: int = Field(ge=1)


class StepOutcomeRequest(BaseModel):
    result: Literal["SUCCESS", "FAILED", "SKIPPED"]
    state_version: int = Field(ge=1)
    actor_type: Literal["TUTOR", "AGENT", "SYSTEM", "ADMIN"] = "TUTOR"
    evaluation: dict = Field(default_factory=dict, description="Evaluator evidence (confidence, error type, ...)")


def _run(fn, *args, **kwargs):
    try:
        with engine.begin() as conn:
            return fn(conn, *args, **kwargs)
    except step_runtime.RuntimeError_ as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from None


def _same_student(path_student_id: UUID, current: UUID) -> None:
    if path_student_id != current:
        raise HTTPException(status_code=403, detail="students may only access their own runtime")


def _resolve_problem(conn, problem_ref: str) -> str:
    row = conn.execute(text(
        "SELECT problem_id::text FROM core.problem WHERE problem_id::text = :r OR canonical_code = :r LIMIT 1"),
        {"r": problem_ref}).scalar()
    if row is None:
        raise step_runtime.NotFound("problem not found")
    return row


@router.post("/students/{student_id}/problems/{problem_ref}/attempts", status_code=201)
def start_attempt(student_id: UUID, problem_ref: str, idempotency_key: str | None = IdempotencyKey,
                  current: UUID = Depends(security.get_current_student_id)) -> dict:
    """Start the step-by-step session for a problem (uuid or canonical code), or resume the open one."""
    _same_student(student_id, current)

    def op(conn):
        problem_id = _resolve_problem(conn, problem_ref)
        started = step_runtime.start_attempt(conn, student_id, problem_id, idempotency_key)
        return {**started, "runtime": step_runtime.get_runtime(conn, started["solve_attempt_id"], student_id)}

    return _run(op)


@router.get("/attempts/{attempt_id}")
@router.get("/attempts/{attempt_id}/runtime")
def get_runtime(attempt_id: UUID, current: UUID = Depends(security.get_current_student_id)) -> dict:
    """Current step metadata, your own responses and progress counts — never canonical step text."""
    return _run(step_runtime.get_runtime, attempt_id, current)


def _with_mastery(result: dict) -> dict:
    if result.get("attempt_completed") and not result.get("replayed"):
        result["updated_mastery"] = mastery.recompute_mastery_for_problem(
            UUID(result["student_id"]), UUID(result["problem_id"]))
    return result


@router.post("/attempts/{attempt_id}/steps/{step_id:path}/responses")
def submit_step_response(attempt_id: UUID, step_id: str, body: StepResponseRequest,
                         idempotency_key: str | None = IdempotencyKey,
                         current: UUID = Depends(security.get_current_student_id)) -> dict:
    """Save the response, then grade it (unless ``evaluate=false``) and advance on success.

    ``evaluation_status``: EVALUATED, PENDING (not requested / superseded by a newer action) or
    UNAVAILABLE (model error; the response is kept and the student can resubmit).
    """
    saved = _run(step_runtime.submit_step_response, current, attempt_id, step_id, body.response_text,
                 body.state_version, idempotency_key)
    if not body.evaluate or saved.get("replayed"):
        return saved
    try:
        with engine.connect() as conn:
            verdict = step_tutor.evaluate_step(conn, str(attempt_id), step_id, EVALUATOR)
    except Exception as exc:  # noqa: BLE001 — model/network failure must not lose the saved response
        log.warning("step evaluation failed for %s/%s: %s", attempt_id, step_id, type(exc).__name__)
        return {**saved, "evaluation_status": "UNAVAILABLE"}
    try:
        outcome = _run(step_runtime.record_step_outcome, attempt_id, step_id, verdict["result"],
                       saved["state_version"], actor="TUTOR", evaluation=verdict,
                       idempotency_key=f"{idempotency_key}:evaluation" if idempotency_key else None)
    except HTTPException as exc:
        if exc.status_code == 409:
            return {**saved, "evaluation_status": "PENDING"}
        raise
    outcome = _with_mastery(outcome)
    if outcome.get("diagnosis"):
        outcome["diagnosis"] = _reranked(outcome["diagnosis"])
    return {**saved, **{k: v for k, v in outcome.items() if k not in ("student_id", "problem_id")},
            "evaluation_status": "EVALUATED",
            "evaluation": step_runtime._student_evaluation(verdict)}


def _hint_text(attempt_id: UUID, step_id: str, level: int) -> dict:
    try:
        with engine.begin() as conn:
            return step_tutor.get_or_create_hint(conn, str(attempt_id), step_id, level, HINT_WRITER)
    except Exception as exc:  # noqa: BLE001
        log.warning("hint generation failed for %s level %s: %s", step_id, level, type(exc).__name__)
        return {"hint_text": None, "hint_source": "UNAVAILABLE"}


@router.post("/attempts/{attempt_id}/steps/{step_id:path}/hint")
def request_hint(attempt_id: UUID, step_id: str, body: VersionedRequest,
                 idempotency_key: str | None = IdempotencyKey,
                 current: UUID = Depends(security.get_current_student_id)) -> dict:
    """Escalate help one level (1–5) and return its text: 1 directional, 2 concept reminder,
    3 strategic, 4 near-explicit, 5 the reference step itself. Any help → later success is WITH_HELP."""
    escalated = _run(step_runtime.request_hint, current, attempt_id, step_id, body.state_version, idempotency_key)
    hint = _hint_text(attempt_id, step_id, escalated["help_level"])
    if hint.get("hint_text") and not escalated.get("replayed"):
        try:
            with engine.begin() as conn:
                step_runtime.record_hint_presented(conn, current, attempt_id, step_id, escalated["help_level"],
                                                   hint.get("hint_source"))
        except Exception as exc:  # noqa: BLE001 — the hint is delivered even if the audit event fails
            log.warning("HINT_PRESENTED not recorded for %s: %s", step_id, type(exc).__name__)
    return {**escalated, **hint}


@router.get("/attempts/{attempt_id}/steps/{step_id:path}/hints")
def list_hints(attempt_id: UUID, step_id: str, current: UUID = Depends(security.get_current_student_id)) -> dict:
    """Hints already revealed to this student for a step (levels 1..help_level_used), for refresh/restore."""
    runtime = _run(step_runtime.get_runtime, attempt_id, current)
    used = next((t["help_level_used"] for t in runtime["timeline"] if t["solution_step_id"] == step_id), None)
    if used is None:
        raise HTTPException(status_code=404, detail="step is not part of this attempt")
    hints = [{"help_level": lvl, "help_kind": step_runtime.HELP_LEVELS[lvl], **_hint_text(attempt_id, step_id, lvl)}
             for lvl in range(1, used + 1)]
    return {"solution_step_id": step_id, "help_level_used": used, "hints": hints}


@router.post("/attempts/{attempt_id}/steps/{step_id:path}/outcome",
             dependencies=[Depends(security.require_admin_api_key)])
def record_step_outcome(attempt_id: UUID, step_id: str, body: StepOutcomeRequest,
                        idempotency_key: str | None = IdempotencyKey) -> dict:
    """Internal (X-Admin-Api-Key): apply an evaluated result and advance to the next eligible step."""
    return _with_mastery(_run(step_runtime.record_step_outcome, attempt_id, step_id, body.result,
                              body.state_version, actor=body.actor_type, evaluation=body.evaluation,
                              idempotency_key=idempotency_key))


class DiagnoseRequest(BaseModel):
    trigger: Literal["STUDENT_REQUEST"] = "STUDENT_REQUEST"


@router.post("/attempts/{attempt_id}/steps/{step_id:path}/diagnose")
def diagnose_step(attempt_id: UUID, step_id: str, body: DiagnoseRequest | None = None,
                  current: UUID = Depends(security.get_current_student_id)) -> dict:
    """Rank what may be blocking you on a presented step (local skill first, then the skills of the steps
    it builds on). Deterministic and free; identical evidence returns the existing diagnosis
    (``reused``). Every hypothesis is persisted; this does not change mode or ``state_version``."""
    def op(conn):
        d = step_diagnosis.diagnose_step(conn, current, attempt_id, step_id, "STUDENT_REQUEST")
        return {**step_diagnosis.student_view(d), "reused": d["reused"]}

    view = _run(op)
    return _reranked(view) | {"reused": view["reused"]}


def _reranked(view: dict | None) -> dict | None:
    """Optional AI re-rank after the rules diagnosis committed (outside the attempt lock; best effort)."""
    if not view or not step_diagnosis.rerank_enabled() or len(view.get("hypotheses") or []) < 2:
        return view
    try:
        if step_diagnosis.rerank_diagnosis(engine, view["gap_diagnosis_id"], RERANKER) is None:
            return view
        with engine.connect() as conn:
            return step_diagnosis.student_view(step_diagnosis._diagnosis_row(conn, view["gap_diagnosis_id"]))
    except Exception as exc:  # noqa: BLE001 — the rules order stands
        log.warning("diagnosis re-rank skipped: %s", type(exc).__name__)
        return view


@router.get("/attempts/{attempt_id}/diagnoses")
def list_diagnoses(attempt_id: UUID, current: UUID = Depends(security.get_current_student_id)) -> list[dict]:
    """Your diagnoses for this attempt, newest first (student view: no failure modes or raw scores)."""
    return [step_diagnosis.student_view(d) for d in _run(step_diagnosis.list_diagnoses, current, attempt_id)]


@router.get("/admin/attempts/{attempt_id}/diagnoses", dependencies=[Depends(security.require_admin_api_key)])
def admin_list_diagnoses(attempt_id: UUID) -> list[dict]:
    """Internal (X-Admin-Api-Key): full diagnoses with failure modes, confidences and evidence."""
    return _run(step_diagnosis.list_diagnoses, None, attempt_id)


@router.get("/admin/students/{student_id}/knowledge-gaps", dependencies=[Depends(security.require_admin_api_key)])
def admin_student_gaps(student_id: UUID,
                       status: Literal["UNRESOLVED", "CONFIRMED", "REJECTED", "RESOLVED"] | None = None,
                       limit: int = Query(100, ge=1, le=500)) -> list[dict]:
    """Internal (X-Admin-Api-Key): a student's knowledge-gap hypotheses across attempts."""
    return _run(step_diagnosis.list_student_gaps, student_id, status, limit)


@router.get("/admin/knowledge-gaps", dependencies=[Depends(security.require_admin_api_key)])
def admin_gap_overview(status: Literal["UNRESOLVED", "CONFIRMED", "REJECTED", "RESOLVED"] | None = None,
                       student: str | None = Query(None, max_length=200, description="e-mail substring or student uuid"),
                       limit: int = Query(100, ge=1, le=500)) -> dict:
    """Internal (X-Admin-Api-Key): knowledge gaps across students — status totals, the most common open
    targets, and recent hypotheses with their diagnosis and latest recovery plan."""
    return _run(step_diagnosis.admin_gap_overview, status=status, student=student, limit=limit)


# ---------------------------------------------------------------- recovery plans (Phase 10)

class RecoveryCreateRequest(BaseModel):
    state_version: int = Field(ge=1)
    trigger: Literal["DIAGNOSIS", "STUDENT_REQUEST"] = "STUDENT_REQUEST"
    gap_diagnosis_id: UUID | None = None


class RecoveryItemResponse(BaseModel):
    state_version: int = Field(ge=1)
    choice_index: int | None = Field(None, ge=0, le=20, description="MCQ items")
    response_text: str | None = Field(None, max_length=10_000, description="Subproblem items")
    acknowledged: bool = Field(False, description="Worked-example items")


@router.post("/attempts/{attempt_id}/recovery-plans", status_code=201)
def create_recovery_plan(attempt_id: UUID, body: RecoveryCreateRequest, idempotency_key: str | None = IdempotencyKey,
                         current: UUID = Depends(security.get_current_student_id)) -> dict:
    """Start a detour from the current step: worked example → recognise → use once → use in context →
    transfer → return. Persisted before the first item is shown; the step becomes DETOURED and the
    runtime enters RECOVERY. If a detour is already running it is returned (``resumed``).
    409 NO_RECOVERY_MATERIAL when no approved practice exists for the target skill."""
    return _run(step_recovery.create_plan, current, attempt_id, body.state_version, trigger=body.trigger,
                gap_diagnosis_id=str(body.gap_diagnosis_id) if body.gap_diagnosis_id else None,
                idempotency_key=idempotency_key)


@router.get("/attempts/{attempt_id}/recovery-plans")
def list_recovery_plans(attempt_id: UUID, current: UUID = Depends(security.get_current_student_id)) -> list[dict]:
    """Your detours for this attempt, newest first."""
    return _run(step_recovery.list_attempt_plans, current, attempt_id)


@router.get("/recovery-plans/{plan_id}")
def get_recovery_plan(plan_id: UUID, current: UUID = Depends(security.get_current_student_id)) -> dict:
    """Plan, stage progress and mastery-policy progress. Item content only for the current item and
    finished items; answers only after an item is finished."""
    return _run(step_recovery.get_plan, current, plan_id)


@router.get("/recovery-plans/{plan_id}/next")
def next_recovery_item(plan_id: UUID, current: UUID = Depends(security.get_current_student_id)) -> dict:
    return _run(step_recovery.next_item, current, plan_id)


@router.post("/recovery-plans/{plan_id}/items/{item_id}/responses")
def answer_recovery_item(plan_id: UUID, item_id: UUID, body: RecoveryItemResponse,
                         idempotency_key: str | None = IdempotencyKey,
                         current: UUID = Depends(security.get_current_student_id)) -> dict:
    """Answer the current item. MCQs are graded deterministically, subproblems by the step evaluator
    (outside the attempt lock), worked examples by acknowledging. The plan then adapts: advance,
    confirmation item, retry, alternate item or a prerequisite branch."""
    response = {k: v for k, v in (("choice_index", body.choice_index), ("response_text", body.response_text),
                                   ("acknowledged", body.acknowledged or None)) if v is not None}
    ctx = _run(step_recovery.prepare_item_response, current, plan_id, str(item_id), response, body.state_version,
               idempotency_key)
    if "replay" in ctx:
        return ctx["replay"]
    try:
        grade = step_recovery.grade_item(ctx, response, EVALUATOR)
    except step_runtime.RuntimeError_ as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from None
    except Exception as exc:  # noqa: BLE001 — model/network failure: nothing was recorded, the student can resend
        log.warning("recovery grading failed for %s: %s", item_id, type(exc).__name__)
        raise HTTPException(status_code=503, detail={"code": "EVALUATION_UNAVAILABLE",
                                                     "message": "the tutor could not check this right now; try again"})
    return _run(step_recovery.apply_item_response, current, plan_id, str(item_id), response, grade,
                body.state_version, idempotency_key)


@router.post("/recovery-plans/{plan_id}/resume")
def resume_from_recovery(plan_id: UUID, body: VersionedRequest, idempotency_key: str | None = IdempotencyKey,
                         current: UUID = Depends(security.get_current_student_id)) -> dict:
    """Return to the exact step the detour started from (the plan must be COMPLETED or EXHAUSTED)."""
    return _run(step_recovery.leave_recovery, current, plan_id, body.state_version, idempotency_key=idempotency_key)


@router.post("/recovery-plans/{plan_id}/abort")
def abort_recovery(plan_id: UUID, body: VersionedRequest, idempotency_key: str | None = IdempotencyKey,
                   current: UUID = Depends(security.get_current_student_id)) -> dict:
    """Leave the detour early: open plans end ABORTED, remaining items SKIPPED, back to the origin step."""
    return _run(step_recovery.leave_recovery, current, plan_id, body.state_version, abort=True,
                idempotency_key=idempotency_key)


@router.get("/admin/recovery-plans", dependencies=[Depends(security.require_admin_api_key)])
def admin_recovery_plans(student_id: UUID | None = None,
                         status: Literal["ACTIVE", "SUSPENDED", "COMPLETED", "EXHAUSTED", "ABORTED", "SUPERSEDED"] | None = None,
                         limit: int = Query(100, ge=1, le=500)) -> list[dict]:
    """Internal (X-Admin-Api-Key): recovery plans with item outcome counts."""
    return _run(step_recovery.admin_plans, student_id=student_id, status=status, limit=limit)


@router.get("/admin/recovery-plans/{plan_id}", dependencies=[Depends(security.require_admin_api_key)])
def admin_recovery_plan(plan_id: UUID) -> dict:
    """Internal (X-Admin-Api-Key): one plan with grader evidence for every item."""
    return _run(step_recovery.admin_plan_detail, plan_id)


@router.post("/attempts/{attempt_id}/submit")
def submit_attempt(attempt_id: UUID, body: VersionedRequest, idempotency_key: str | None = IdempotencyKey,
                   current: UUID = Depends(security.get_current_student_id)) -> dict:
    return _run(step_runtime.submit_attempt, current, attempt_id, body.state_version, idempotency_key)


@router.get("/students/{student_id}/events")
def list_events(student_id: UUID, attempt_id: UUID | None = None, limit: int = Query(100, ge=1, le=500),
                current: UUID = Depends(security.get_current_student_id)) -> list[dict]:
    _same_student(student_id, current)
    return _run(step_runtime.list_events, student_id, attempt_id=attempt_id, limit=limit)


@router.get("/solution-steps/{step_id:path}/practice")
def practice_for_step(step_id: str, limit: int = Query(5, ge=1, le=20), same_skill: bool = True,
                      _: UUID = Depends(security.get_current_student_id)) -> dict:
    """Similar steps from *other* problems exercising the same skill (hybrid vector + lexical, no step text)."""
    try:
        return similar_steps_for_step(step_id, limit=limit, same_skill=same_skill)
    except LookupError:
        raise HTTPException(status_code=404, detail="solution step not found") from None


@router.get("/problems/by-code/{code}/diagrams")
def list_problem_diagrams(code: str) -> list[dict]:
    """Problem-statement diagrams (never solution diagrams) for the workspace."""
    with engine.connect() as conn:
        return list_images(conn, code)


@router.get("/problems/by-code/{code}/source")
def get_problem_source(code: str) -> dict | None:
    with engine.connect() as conn:
        record = source_record(conn, code)
    if record is None:
        raise HTTPException(status_code=404, detail="problem not found")
    return source_metadata(record, code)


@router.get("/problems/by-code/{code}/source-pdf", response_class=FileResponse)
def get_problem_source_pdf(code: str):
    with engine.connect() as conn:
        record = source_record(conn, code)
    path = source_pdf(record) if record is not None else None
    if path is None:
        raise HTTPException(status_code=404, detail="original PDF is not cached")
    return FileResponse(path, media_type="application/pdf", content_disposition_type="inline",
                        filename="original-problem-document.pdf", headers={"Cache-Control": "no-cache"})


@router.get("/problems/by-code/{code}/source-highlight")
def get_problem_source_highlight(code: str, page: int | None = Query(default=None, ge=1)):
    from fastapi.responses import Response

    with engine.connect() as conn:
        record = source_record(conn, code)
    path = source_pdf(record) if record else None
    location = problem_location(path, record, code) if path else None
    if location is None:
        raise HTTPException(status_code=404, detail="verified problem location is unavailable")
    if page is not None:
        location = next((region for region in location["pages"] if region["page"] == page), None)
        if location is None:
            raise HTTPException(status_code=404, detail="verified problem page is unavailable")
    return Response(highlighted_page(path, location), media_type="image/png",
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/problems/by-code/{code}/source-marked-pdf")
def get_problem_source_marked_pdf(code: str):
    from fastapi.responses import Response

    with engine.connect() as conn:
        record = source_record(conn, code)
    path = source_pdf(record) if record else None
    location = problem_location(path, record, code) if path else None
    if location is None:
        raise HTTPException(status_code=404, detail="verified problem location is unavailable")
    return Response(highlighted_pdf(path, location), media_type="application/pdf",
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                             "Content-Disposition": 'inline; filename="highlighted-source.pdf"'})


@router.get("/problem-images/{image_id}", response_class=FileResponse)
def get_problem_image(image_id: UUID):
    with engine.connect() as conn:
        path = conn.execute(text(f"SELECT i.local_path FROM core.problem_image i "
                                 f"WHERE i.problem_image_id = :i AND {STUDENT_IMAGE_FILTER}"),
                            {"i": str(image_id)}).scalar()
    if path and path.startswith("object-store:"):
        from fastapi.responses import Response
        from mathbank_rest import object_store
        try:
            data = object_store.read_bytes(path.removeprefix("object-store:"))
        except object_store.ObjectStoreError:
            raise HTTPException(503, detail="Published image storage is unavailable.") from None
        return Response(data, media_type="image/png",
                        headers={"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"})
    resolved = (IMAGE_ROOT / path).resolve() if path else None
    if resolved is None or not resolved.is_file() or IMAGE_ROOT not in resolved.parents:
        raise HTTPException(status_code=404, detail="image not found")
    return FileResponse(resolved, headers={"Cache-Control": "no-cache"})
