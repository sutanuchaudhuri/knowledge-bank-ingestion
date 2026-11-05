"""Shared helpers of the exam/quiz journeys (apitest/journeys/exam_*.py). Not a journey module itself.

Conventions: every helper records through `ctx.api.expect` / `check`; none raises on an HTTP failure; the learners created here
are fresh per journey (the `test` DynamoDB environment is the only thing written)."""
from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from apitest.context import Ctx

BASE = "/v1/quiz-integration"

# Attributes that must never appear in a body a learner (or the agent proxying one) can reach before the paper is over.
SECRET_KEYS = frozenset({
    "correct_answer", "option_explanations", "revision_log", "inspiration_sources", "solution", "solution_text", "solution_latex",
    "solution_steps", "key_insight", "is_correct", "feedback", "grading_feedback", "grading_rubric", "expected_answer", "correct_key",
    "password_hash", "token_version", "admin_api_key"})
REVIEW_KEYS = {"quiz_id", "style", "title", "score", "total", "answered_count", "questions"}
QUIZ_KEYS = {"quiz_id", "style", "title", "status", "instructions", "exam_mode", "time_limit_seconds", "started_at",
             "resume_question_ordinal", "questions"}
LEARNER_QUESTION_KEYS = {"question_id", "ordinal", "question_type", "prompt_text", "prompt_latex", "options", "points", "has_diagram",
                         "student_response", "draft_response", "answered"}


# ------------------------------------------------------------------------------------------------------ recording helpers

def check(ctx: Ctx, case: str, ok: Any, note: str = "", path: str = "-") -> bool:
    """Record a non-HTTP assertion (a failed one keeps its note as the failure body)."""
    good = bool(ok)
    ctx.rec.add(case=case, method="CHECK", path=path, status=None, ms=0, ok=good, note="" if good else note[:300],
                body="" if good else note[:600])
    return good


def js(r) -> Any:
    try:
        return r.json()
    except Exception:  # noqa: BLE001
        return None


def code_of(r) -> str | None:
    """The machine-readable error code: `detail.code` (QuizError / HTTPException) or the bare `detail` string (StoreError)."""
    body = js(r)
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, dict):
        return detail.get("code")
    return detail if isinstance(detail, str) else None


def call(ctx: Ctx, case: str, method: str, path: str, status: int | set[int], *, code: str | None = None, **kw):
    """`api.expect` plus, for an error response, a check of the machine-readable `detail.code` the agent contract relies on."""
    r = ctx.api.expect(case, method, path, status, **kw)
    if code is not None and r is not None and r.status_code >= 400:
        check(ctx, f"{case}: detail.code", code_of(r) == code, f"got {code_of(r)!r}, expected {code!r} ({r.text[:160]})", path)
    return r


def svc(ctx: Ctx, case: str, method: str, path: str, status: int | set[int], **kw):
    """A service-credential (X-Admin-Api-Key) call under /v1/quiz-integration."""
    return call(ctx, case, method, f"{BASE}{path}", status, admin=True, **kw)


def good(r) -> bool:
    return r is not None and 200 <= r.status_code < 300


def keys_of(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in keys_of(v)}
    if isinstance(value, list):
        return {k for v in value for k in keys_of(v)}
    return set()


def marker(ctx: Ctx) -> str:
    """A token placed in every secret text of the questions this run builds, so a leak is found by substring search."""
    return f"zzsecret{ctx.run_id}"


def scan(ctx: Ctx, case: str, r, *, allow: frozenset[str] = frozenset()) -> None:
    """A learner-reachable body: no answer-key attribute, no secret text and no credential anywhere in it."""
    if r is None or r.status_code >= 300:
        return
    body = js(r)
    leaked = (keys_of(body) & SECRET_KEYS) - allow
    texts = [marker(ctx)]
    if len(ctx.admin_key) >= 8:
        texts.append(ctx.admin_key)
    texts += ["Traceback", "password_hash"]
    found = [t for t in texts if t in r.text]
    check(ctx, f"no leak: {case}", not leaked and not found, f"secret keys {sorted(leaked)} / texts {found} in {r.text[:200]}",
          r.request.url.path)


def poll(ctx: Ctx, case: str, method: str, path: str, predicate: Callable[[Any], bool], *, tries: int = 8, delay: float = 0.6, **kw):
    """Read a GSI-backed (eventually consistent) view until `predicate(json)` holds; records ONE exchange with the final outcome."""
    r, ms_total, last = None, 0, None
    for _ in range(tries):
        r, ms, err = ctx.api.call(method, path, **kw)
        ms_total += ms
        last = js(r) if r is not None else None
        if r is not None and r.status_code == 200 and predicate(last):
            break
        time.sleep(delay)
    ok = r is not None and r.status_code == 200 and predicate(last)
    ctx.rec.add(case=case, method=method, path=path, status=r.status_code if r is not None else None, ms=ms_total, ok=ok,
                note="" if ok else f"predicate never held in {tries} reads (eventually consistent?)", body="" if ok else str(last)[:600])
    return last


# ------------------------------------------------------------------------------------------------------ identities


@dataclass
class Learner:
    sid: str
    token: str
    email: str


def email(ctx: Ctx, tag: str) -> str:
    """A unique address on a domain EmailStr accepts (`ctx.unique_email` uses `.test`, which /v1/learner/register rejects)."""
    return f"apitest+{tag}.{ctx.run_id}.{secrets.token_hex(3)}@example.com"


def onboard(ctx: Ctx, tag: str) -> Learner | None:
    """Service path: students/onboard -> mint-session-token (the bridge the exam agent uses after Cognito sign-in)."""
    addr = email(ctx, tag)
    r = svc(ctx, f"onboard {tag}", "POST", "/students/onboard", 200,
            json={"cognito_sub": str(uuid4()), "first_name": "Api", "last_name": tag.title(), "email": addr, "grade": "10"})
    if not good(r):
        return None
    sid = js(r).get("student_id")
    t = svc(ctx, f"mint token {tag}", "POST", f"/students/{sid}/mint-session-token", 200)
    if not good(t):
        return None
    return Learner(sid=sid, token=js(t)["access_token"], email=addr)


def register(ctx: Ctx, tag: str) -> Learner | None:
    """Self-service path: POST /v1/learner/register."""
    addr = email(ctx, tag)
    r = call(ctx, f"register {tag}", "POST", "/v1/learner/register", 201,
             json={"email": addr, "password": "Apitest-" + secrets.token_hex(6), "first_name": "Api", "last_name": tag.title()})
    if not good(r):
        return None
    d = js(r)
    return Learner(sid=d["student_id"], token=d["access_token"], email=addr)


def content_fixtures(ctx: Ctx) -> dict:
    """Published content (read from dev) the questions can be tagged with: a couple of concept / technique slugs and problem codes."""
    if "exam_content" in ctx.fixtures:
        return ctx.fixtures["exam_content"]
    out: dict[str, list[str]] = {"concepts": [], "techniques": [], "codes": []}
    for key, path, field in (("concepts", "/v1/concepts", "slug"), ("techniques", "/v1/techniques", "slug"),
                             ("codes", "/v1/problems?limit=3", "canonical_code")):
        r = ctx.api.expect(f"discover {key}", "GET", path, 200)
        rows = js(r) if good(r) else None
        if isinstance(rows, dict):
            rows = next((v for v in rows.values() if isinstance(v, list)), [])
        out[key] = [x[field] for x in (rows or []) if isinstance(x, dict) and x.get(field)][:3]
    ctx.fixtures["exam_content"] = out
    return out


# ------------------------------------------------------------------------------------------------------ builders


def mcq(ctx: Ctx, n: int, *, correct: str = "B", **over) -> dict:
    """One finalize question as the exam agent sends it. The secret texts all carry the run marker."""
    m = marker(ctx)
    return {
        "question_type": "MCQ", "prompt_text": f"[{ctx.run_id}] What is {n}+{n}? (MCQ {uuid4().hex[:6]})", "prompt_latex": None,
        "options": [{"key": "A", "text": str(2 * n - 1)}, {"key": "B", "text": str(2 * n)}, {"key": "C", "text": str(2 * n + 1)}],
        "correct_answer": {"correct_key": correct},
        "option_explanations": {"A": f"{m} no", "B": f"{m} yes", "C": f"{m} no"},
        "solution_text": f"{m} {n}+{n}={2 * n}", "solution_steps": ["add", "check"], "key_insight": f"{m} addition",
        "difficulty_band": "hard", "revision_log": [{"round": 1, "verdict": "APPROVE", "feedback": f"{m} fine"}],
        "concept_slugs": [], "technique_slugs": [], "skill_slugs": [], "inspiration_sources": [], "diagram": None,
        "pool_question_id": None, "add_to_pool": False, **over}


def written(ctx: Ctx, n: int, kind: str = "FREE_TEXT", **over) -> dict:
    m = marker(ctx)
    return {**mcq(ctx, n), "question_type": kind, "options": None,
            "prompt_text": f"[{ctx.run_id}] State the value of {n}+{n}. ({kind} {uuid4().hex[:6]})",
            "correct_answer": {"expected_answer": f"{m} {2 * n}", "grading_rubric": f"{m} the sum is {2 * n}"},
            "option_explanations": {}, **over}


def paper_body(sid: str, *, count: int, types: list[str] | None = None, title: str = "apitest exam", **over) -> dict:
    return {"student_id": sid, "style": "MIXED", "title": title, "instructions": "apitest", "requested_question_count": count,
            "requested_question_types": types or ["MCQ"], "difficulty_band": "hard", "generated_by": "apitest-agent",
            "time_limit_seconds": 3600, **over}


def start_paper(ctx: Ctx, sid: str, *, count: int, case: str = "start paper", **over) -> str | None:
    r = svc(ctx, case, "POST", "/papers/start", 200, json=paper_body(sid, count=count, **over))
    return js(r).get("quiz_id") if good(r) else None


def import_paper(ctx: Ctx, sid: str, questions: list[dict], *, case: str = "import paper", **over):
    return svc(ctx, case, "POST", "/papers", 200, json={**paper_body(sid, count=len(questions)), "questions": questions, **over})


def finalize(ctx: Ctx, sid: str, qid: str, questions: list[dict], *, case: str = "finalize", status: int | set[int] = 200, **over):
    return svc(ctx, case, "POST", f"/papers/{qid}/finalize", status,
               json={"student_id": sid, "generated_by": "apitest-agent", "questions": questions, **over})


def qids(r) -> list[str]:
    """question ids of a quiz view, in ordinal order."""
    return [q["question_id"] for q in sorted((js(r) or {}).get("questions", []), key=lambda q: q["ordinal"])]


def get_paper(ctx: Ctx, sid: str, qid: str, case: str = "get paper", status: int | set[int] = 200, **kw):
    return svc(ctx, case, "GET", f"/papers/{qid}", status, params={"student_id": sid}, **kw)


def respond(ctx: Ctx, sid: str, qid: str, question_id: str, body: dict, case: str, status: int | set[int] = 200, *, token: str | None = None,
            **kw):
    """Answer through the service route (student_id in the body) or, with `token`, the learner route."""
    if token:
        return call(ctx, case, "POST", f"/v1/quiz/{qid}/questions/{question_id}/respond", status, token=token, json=body, **kw)
    return svc(ctx, case, "POST", f"/papers/{qid}/questions/{question_id}/respond", status, json={"student_id": sid, **body}, **kw)


def status_of(ctx: Ctx, sid: str, qid: str) -> str | None:
    r = ctx.api.call("GET", f"{BASE}/papers/{qid}", admin=True, params={"student_id": sid})[0]
    return js(r).get("status") if r is not None and r.status_code == 200 else None
