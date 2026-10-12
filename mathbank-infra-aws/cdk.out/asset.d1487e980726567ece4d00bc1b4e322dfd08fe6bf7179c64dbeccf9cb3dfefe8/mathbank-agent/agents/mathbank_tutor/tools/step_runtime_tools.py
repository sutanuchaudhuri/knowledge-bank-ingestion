"""Step-runtime tools (runtime_extension/12_TUTOR_AGENT_CONTEXT.md).

The agent is an orchestrator, never the owner of tutoring state: every tool reads or mutates the
deterministic step runtime in mathbank-rest (attempt, current step, hints, diagnosis, recovery) and
returns the server's answer. The agent never sees canonical step text for the current step.

Authentication: the web proxy resolves the signed-in student server-side and passes their REST token
as ADK *temp* state (``temp:student_token``). ADK keeps temp state only in memory for the current
invocation and strips it before persisting the session, so the token never lands in the
``agent_sessions`` tables. Anonymous chats get no token, and these tools return SIGN_IN_REQUIRED.

``state_version`` is read from the runtime inside each mutating tool (optimistic concurrency stays
server-side); the ADK function-call id becomes the Idempotency-Key, so a retried tool call is replayed
instead of applied twice.
"""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import httpx
from google.adk.tools.tool_context import ToolContext

REST_BASE_URL = os.environ.get("MATHBANK_REST_BASE_URL", "http://127.0.0.1:8000")
TOKEN_STATE_KEY = "temp:student_token"

# tutor.runtime_state.current_mode -> spec 12 response mode
MODE_MAP = {"SOLVING": "ORIGINAL_PROBLEM", "DIAGNOSING": "DIAGNOSTIC", "RECOVERY": "RECOVERY",
            "REVIEW": "RETURN_TO_PROBLEM", "COMPLETED": "COMPLETED"}

SIGN_IN_REQUIRED = {
    "error": "SIGN_IN_REQUIRED",
    "message": "Step-by-step tutoring needs a signed-in student. Ask the learner to sign in "
               "(or open the problem's Solve page); do not invent progress.",
}


def _client() -> httpx.Client:
    return httpx.Client(base_url=REST_BASE_URL, timeout=60.0)


def _token(tool_context: ToolContext | None) -> str | None:
    if tool_context is None:
        return None
    try:
        return tool_context.state.get(TOKEN_STATE_KEY) or None
    except Exception:  # noqa: BLE001 — no state in an unusual runner
        return None


def _idempotency_key(tool_context: ToolContext | None, action: str) -> str | None:
    call_id = getattr(tool_context, "function_call_id", None)
    return f"agent:{action}:{call_id}"[:200] if call_id else None


def _error(response: httpx.Response) -> dict:
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, dict):
        return {"error": detail.get("code") or f"HTTP_{response.status_code}", "message": detail.get("message"),
                "status": response.status_code}
    return {"error": f"HTTP_{response.status_code}", "message": detail if isinstance(detail, str) else None,
            "status": response.status_code}


def _call(tool_context: ToolContext | None, method: str, path: str, *, json: dict | None = None,
          action: str | None = None) -> dict:
    token = _token(tool_context)
    if not token:
        return dict(SIGN_IN_REQUIRED)
    headers = {"Authorization": f"Bearer {token}"}
    key = _idempotency_key(tool_context, action) if action else None
    if key:
        headers["Idempotency-Key"] = key
    with _client() as client:
        response = client.request(method, path, json=json, headers=headers)
    if response.status_code >= 400:
        return _error(response)
    return response.json()


def response_mode(runtime: dict) -> str:
    """Spec 12 response mode derived from the server runtime (never stored by the agent)."""
    attempt = runtime.get("attempt") or {}
    if attempt.get("status") in ("SUBMITTED", "COMPLETED"):
        return "COMPLETED"
    mode = MODE_MAP.get(attempt.get("current_mode") or "", "ORIGINAL_PROBLEM")
    recovery = runtime.get("recovery") or {}
    if mode == "RECOVERY" and recovery.get("status") in ("COMPLETED", "EXHAUSTED"):
        return "RETURN_TO_STEP"
    step = runtime.get("current_step") or {}
    if mode == "ORIGINAL_PROBLEM" and step.get("help_level_used"):
        return "STEP_HINT"
    return mode


def summarize_runtime(runtime: dict) -> dict:
    """Compact, student-safe context packet for the model (spec 12 'context assembly')."""
    if "error" in runtime:
        return runtime
    attempt = runtime.get("attempt") or {}
    step = runtime.get("current_step") or {}
    current = None
    if step:
        current = {k: step.get(k) for k in (
            "solution_step_id", "part_label", "step_index_in_part", "global_step_index", "step_type", "goal",
            "skill_name", "is_checkpoint", "state", "help_level_used", "attempt_count", "last_response_text",
            "last_evaluation")}
        if step.get("diagnosis"):
            current["latest_diagnosis"] = step["diagnosis"]
    return {
        "solve_attempt_id": attempt.get("solve_attempt_id") and str(attempt["solve_attempt_id"]),
        "problem_code": attempt.get("problem_code"),
        "problem_statement": attempt.get("statement_text"),
        "attempt_status": attempt.get("status"),
        "runtime_mode": attempt.get("current_mode"),
        "response_mode": response_mode(runtime),
        "state_version": attempt.get("state_version"),
        "current_step": current,
        "recovery": runtime.get("recovery"),
        "progress": runtime.get("progress"),
        "completed_steps": [
            {"global_step_index": t.get("global_step_index"), "state": t.get("state"),
             "reference_text": t.get("reference_text")}
            for t in runtime.get("timeline") or [] if t.get("reference_text")],
    }


def _runtime(tool_context: ToolContext | None, attempt_id: str) -> dict:
    return _call(tool_context, "GET", f"/v1/attempts/{quote(attempt_id, safe='')}/runtime")


def _version(tool_context: ToolContext | None, attempt_id: str) -> tuple[int | None, dict]:
    runtime = _runtime(tool_context, attempt_id)
    if "error" in runtime:
        return None, runtime
    return (runtime.get("attempt") or {}).get("state_version"), runtime


def _with_runtime(tool_context: ToolContext | None, attempt_id: str, result: dict) -> dict:
    if "error" in result:
        return result
    return {"result": result, "runtime": summarize_runtime(_runtime(tool_context, attempt_id))}


# ---------------------------------------------------------------- tools

def start_step_attempt(problem_code: str, tool_context: ToolContext) -> dict:
    """Start (or resume) the signed-in student's step-by-step attempt on a problem that has stored
    solution steps (Prasolov geometry, competition code PRASOLOV_PGV1, e.g. 'PRASOLOV_PGV1_CH02_P072').

    Use when the learner wants to SOLVE a problem with step guidance (not just read it). The server
    decides which step is current; you never invent steps.

    Args:
        problem_code: canonical_code (or problem uuid) of the problem.

    Returns:
        {"result": {"solve_attempt_id", "resumed"}, "runtime": <get_attempt_runtime packet>} or
        {"error": "SIGN_IN_REQUIRED"|code, "message"}.
    """
    student_id = getattr(tool_context, "user_id", None)
    if not _token(tool_context) or not student_id or student_id == "anonymous":
        return dict(SIGN_IN_REQUIRED)
    started = _call(tool_context, "POST",
                    f"/v1/students/{quote(student_id, safe='')}/problems/{quote(problem_code, safe='')}/attempts",
                    action="start")
    if "error" in started:
        return started
    return {"result": {"solve_attempt_id": started.get("solve_attempt_id"), "resumed": started.get("resumed")},
            "runtime": summarize_runtime(started.get("runtime") or {})}


def get_attempt_runtime(solve_attempt_id: str, tool_context: ToolContext) -> dict:
    """Read the authoritative tutoring state for an attempt: the problem statement, the current step's
    goal/skill/type (never its reference text), help used, latest evaluation and diagnosis, recovery
    plan pointer, progress, and the reference text of steps already completed.

    Call this FIRST in every step-tutoring turn and choose your behaviour from ``response_mode``:
    ORIGINAL_PROBLEM (coach the current step), STEP_HINT (hints already used — build on them),
    DIAGNOSTIC, RECOVERY (work the current recovery item), RETURN_TO_STEP (call resume_original_step),
    RETURN_TO_PROBLEM / COMPLETED (summarise).

    Args:
        solve_attempt_id: the attempt uuid (from start_step_attempt or the Solve page context).
    """
    return summarize_runtime(_runtime(tool_context, solve_attempt_id))


def submit_step_response(solve_attempt_id: str, solution_step_id: str, response_text: str,
                         tool_context: ToolContext) -> dict:
    """Submit the learner's OWN words for the current step and have the server grade it. Never submit
    your own solution text as the learner's response. On success the server advances to the next step.

    Args:
        solve_attempt_id: attempt uuid.
        solution_step_id: current_step.solution_step_id from get_attempt_runtime.
        response_text: what the learner wrote, verbatim.

    Returns: {"result": {evaluation_status, evaluation{result, feedback...}, diagnosis?, attempt_completed?},
        "runtime": <updated packet>} or {"error": ...}. STALE_STATE means re-read the runtime.
    """
    version, runtime = _version(tool_context, solve_attempt_id)
    if version is None:
        return runtime
    result = _call(tool_context, "POST",
                   f"/v1/attempts/{quote(solve_attempt_id, safe='')}/steps/{quote(solution_step_id, safe='')}/responses",
                   json={"response_text": response_text, "state_version": version, "evaluate": True},
                   action="respond")
    return _with_runtime(tool_context, solve_attempt_id, result)


def request_step_hint(solve_attempt_id: str, solution_step_id: str, tool_context: ToolContext) -> dict:
    """Escalate help on the current step by ONE level (1 directional, 2 concept reminder, 3 strategic,
    4 near-explicit, 5 reference step) and return the stored/generated hint text. Only call when the
    learner asks for help or is stuck after trying; later success then counts as WITH_HELP.

    Returns: {"result": {help_level, help_kind, hint_text, hint_source}, "runtime": ...}.
    Relay hint_text faithfully; do not jump ahead of the returned level.
    """
    version, runtime = _version(tool_context, solve_attempt_id)
    if version is None:
        return runtime
    result = _call(tool_context, "POST",
                   f"/v1/attempts/{quote(solve_attempt_id, safe='')}/steps/{quote(solution_step_id, safe='')}/hint",
                   json={"state_version": version}, action="hint")
    return _with_runtime(tool_context, solve_attempt_id, result)


def diagnose_step_gap(solve_attempt_id: str, solution_step_id: str, tool_context: ToolContext) -> dict:
    """Ask the server to rank what may be blocking the learner on the current step (the step's own
    skill/technique first, then the skills of steps it builds on). Deterministic and free; repeated
    calls with the same evidence reuse the diagnosis. Present hypotheses as possibilities, not facts.

    Returns: {"gap_diagnosis_id", "hypotheses": [{target_label, rank, ...}], "reused"} or {"error"}.
    """
    return _call(tool_context, "POST",
                 f"/v1/attempts/{quote(solve_attempt_id, safe='')}/steps/{quote(solution_step_id, safe='')}/diagnose",
                 json={"trigger": "STUDENT_REQUEST"})


def start_recovery_plan(solve_attempt_id: str, tool_context: ToolContext, gap_diagnosis_id: str = "") -> dict:
    """Start a short recovery detour from the current step (worked example -> recognise -> use once ->
    in context -> transfer -> return). Only after a diagnosis, or when the learner asks to practise the
    underlying idea. The original step is preserved and resumed afterwards.

    Args:
        solve_attempt_id: attempt uuid.
        gap_diagnosis_id: optional diagnosis id from diagnose_step_gap to target its top hypothesis.

    Returns: {"result": <plan>, "runtime": ...}; NO_RECOVERY_MATERIAL when nothing approved exists.
    """
    version, runtime = _version(tool_context, solve_attempt_id)
    if version is None:
        return runtime
    body: dict[str, Any] = {"state_version": version,
                            "trigger": "DIAGNOSIS" if gap_diagnosis_id else "STUDENT_REQUEST"}
    if gap_diagnosis_id:
        body["gap_diagnosis_id"] = gap_diagnosis_id
    result = _call(tool_context, "POST", f"/v1/attempts/{quote(solve_attempt_id, safe='')}/recovery-plans",
                   json=body, action="recovery")
    return _with_runtime(tool_context, solve_attempt_id, result)


def get_next_recovery_item(recovery_plan_id: str, tool_context: ToolContext) -> dict:
    """The current recovery item (MCQ, subproblem, worked example, or RETURN) with mastery progress.
    Never reveal an MCQ's answer; the item only carries it after it is finished.

    Returns: {"recovery_plan_id", "status", "item", "mastery", "can_return"}.
    """
    return _call(tool_context, "GET", f"/v1/recovery-plans/{quote(recovery_plan_id, safe='')}/next")


def answer_recovery_item(solve_attempt_id: str, recovery_plan_id: str, recovery_plan_item_id: str,
                         tool_context: ToolContext, choice_index: int = -1, response_text: str = "",
                         acknowledged: bool = False) -> dict:
    """Submit the learner's answer to the current recovery item: ``choice_index`` (0-based) for MCQs,
    ``response_text`` (learner's words) for subproblems, ``acknowledged=true`` for worked examples.
    The server grades and adapts the plan (advance, confirm, retry, alternate, or branch).

    Returns: {"result": <graded item + plan>, "runtime": ...}.
    """
    version, runtime = _version(tool_context, solve_attempt_id)
    if version is None:
        return runtime
    body: dict[str, Any] = {"state_version": version}
    if choice_index >= 0:
        body["choice_index"] = choice_index
    if response_text:
        body["response_text"] = response_text
    if acknowledged:
        body["acknowledged"] = True
    result = _call(tool_context, "POST",
                   f"/v1/recovery-plans/{quote(recovery_plan_id, safe='')}/items/"
                   f"{quote(recovery_plan_item_id, safe='')}/responses", json=body, action="recovery-answer")
    return _with_runtime(tool_context, solve_attempt_id, result)


def resume_original_step(solve_attempt_id: str, recovery_plan_id: str, tool_context: ToolContext) -> dict:
    """Return the learner to the exact step the recovery detour started from (plan COMPLETED or
    EXHAUSTED). Then continue coaching that step with the new idea in mind.

    Returns: {"result": {...}, "runtime": ...}.
    """
    version, runtime = _version(tool_context, solve_attempt_id)
    if version is None:
        return runtime
    result = _call(tool_context, "POST", f"/v1/recovery-plans/{quote(recovery_plan_id, safe='')}/resume",
                   json={"state_version": version}, action="resume")
    return _with_runtime(tool_context, solve_attempt_id, result)


STEP_RUNTIME_TOOLS = [
    start_step_attempt, get_attempt_runtime, submit_step_response, request_step_hint, diagnose_step_gap,
    start_recovery_plan, get_next_recovery_item, answer_recovery_item, resume_original_step,
]
