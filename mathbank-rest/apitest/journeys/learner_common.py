"""Helpers shared by the learner journeys (learner_*.py). This module registers no journey.

Everything records through `ctx.api.expect` / `ctx.rec.add` so a failed check shows up in the report; nothing here raises on an HTTP
failure. Response shapes are asserted with small declarative specs (`shape_problems`).
"""
from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from apitest.context import Ctx

PASSWORD = "Apitest-Passw0rd!1"
NEW_PASSWORD = "Apitest-N3w-Passw0rd!2"

NUM = (int, float)
OPT_STR = (str, type(None))
OPT_INT = (int, type(None))
OPT_NUM = (int, float, type(None))
ANY = object

# Keys that must never appear in any learner-facing response.
SECRET_KEYS = frozenset({"password", "password_hash", "token_version", "tv", "current_password", "new_password"})
# Canonical solution text and grader internals a learner must not see before earning them.
SOLUTION_KEYS = frozenset({"step_text", "reference_step", "canonical_step_text", "body_markdown"})
ANSWER_KEYS = frozenset({"correct_choice_index", "correct_value", "correct_answer", "answer_key", "correct_choices", "is_correct_choice"})
DIAGNOSIS_INTERNALS = frozenset({"failure_mode", "failure_location", "confidence", "evidence", "ai_rerank", "diagnoser_version",
                                 "target_skill_id", "raw_score"})


class N:
    """Spec wrapper: the value may be null, otherwise it must satisfy `spec`."""

    def __init__(self, spec):
        self.spec = spec


def shape_problems(data: Any, spec: Any, where: str = "$") -> list[str]:
    if isinstance(spec, N):
        return [] if data is None else shape_problems(data, spec.spec, where)
    if isinstance(spec, dict):
        if not isinstance(data, dict):
            return [f"{where}: expected object, got {type(data).__name__}"]
        out: list[str] = []
        for key, sub in spec.items():
            if key not in data:
                out.append(f"{where}.{key}: missing")
            else:
                out += shape_problems(data[key], sub, f"{where}.{key}")
        return out
    if isinstance(spec, list):
        if not isinstance(data, list):
            return [f"{where}: expected array, got {type(data).__name__}"]
        out = []
        for i, item in enumerate(data[:5]):
            out += shape_problems(item, spec[0], f"{where}[{i}]")
        return out
    types = spec if isinstance(spec, tuple) else (spec,)
    if ANY in types:
        return []
    if isinstance(data, bool) and bool not in types:
        return [f"{where}: expected {_names(types)}, got bool"]
    if not isinstance(data, types):
        return [f"{where}: expected {_names(types)}, got {type(data).__name__}"]
    return []


def _names(types: tuple) -> str:
    return "|".join(t.__name__ for t in types)


def find_keys(data: Any, names: frozenset[str] | set[str], where: str = "$") -> list[str]:
    """Paths of every dict key named in `names`, anywhere in a JSON document."""
    hits: list[str] = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k in names:
                hits.append(f"{where}.{k}")
            hits += find_keys(v, names, f"{where}.{k}")
    elif isinstance(data, list):
        for i, v in enumerate(data):
            hits += find_keys(v, names, f"{where}[{i}]")
    return hits


@dataclass
class Res:
    r: Any
    ok: bool

    @property
    def status(self) -> int | None:
        return self.r.status_code if self.r is not None else None

    @property
    def data(self) -> Any:
        if self.r is None:
            return None
        try:
            return self.r.json()
        except ValueError:
            return None

    @property
    def detail(self) -> Any:
        d = self.data
        return d.get("detail") if isinstance(d, dict) else None


def check(ctx: Ctx, case: str, ok: bool, note: str = "", path: str = "-") -> bool:
    ctx.rec.add(case=case, method="CHECK", path=path, status=None, ms=0, ok=bool(ok), note=note, body="")
    return bool(ok)


def call(ctx: Ctx, case: str, method: str, path: str, ok: set[int] | int | range, *, spec: Any = None,
         leak: frozenset[str] | set[str] | None = SECRET_KEYS, note: str = "", **kw) -> Res:
    """HTTP call recorded as `case`; on an accepted status the body is checked against `spec` and scanned for `leak` keys."""
    r = ctx.api.expect(case, method, path, ok, note=note, **kw)
    allowed = {ok} if isinstance(ok, int) else set(ok)
    res = Res(r, r is not None and r.status_code in allowed)
    if res.ok:
        data = res.data
        if spec is not None:
            problems = shape_problems(data, spec)
            ctx.rec.add(case=f"shape: {case}", method="SHAPE", path=path, status=res.status, ms=0, ok=not problems,
                        note="; ".join(problems[:6]), body="")
        if leak and data is not None:
            hits = find_keys(data, leak)
            if hits:
                ctx.rec.add(case=f"leak: {case}", method="LEAK", path=path, status=res.status, ms=0, ok=False,
                            note="forbidden keys in response: " + ", ".join(hits[:6]), body=str(data)[:400])
    return res


def claims(token: str) -> dict:
    return jwt.decode(token, options={"verify_signature": False})


def forge_token(sub: str, *, tv: int | None = None, expires_in: int = 3600, secret: str | None = None) -> str:
    """A token signed with the server's own secret (the harness shares the server's configuration) unless `secret` is given."""
    from mathbank_rest.config import settings

    now = datetime.now(UTC)
    payload: dict[str, Any] = {"sub": sub, "iat": now - timedelta(hours=2), "exp": now + timedelta(seconds=expires_in)}
    if tv is not None:
        payload["tv"] = tv
    return jwt.encode(payload, secret or settings.jwt_secret, algorithm=settings.jwt_algorithm)


# ------------------------------------------------------------------------------------------------------ identity

AUTH_SPEC = {"access_token": str, "token_type": str, "student_id": str, "first_name": OPT_STR, "last_name": OPT_STR,
             "display_name": OPT_STR}
PROFILE_SPEC = {"student_id": str, "email": str, "first_name": str, "last_name": str, "display_name": OPT_STR, "status": str,
                "created_at": str, "last_login_at": OPT_STR, "grade": OPT_STR, "phone": OPT_STR}


@dataclass
class Learner:
    email: str
    password: str
    token: str
    student_id: str
    first_name: str
    last_name: str


def new_email(ctx: Ctx, tag: str = "l") -> str:
    # Ctx.unique_email() uses the reserved `.test` TLD, which the API's EmailStr validation rejects (422).
    return f"apitest.{tag}.{ctx.run_id}.{secrets.token_hex(3)}@example.com"


def register(ctx: Ctx, tag: str = "l", *, first: str = "Ada", last: str = "Lovelace") -> Learner | None:
    email = new_email(ctx, tag)
    res = call(ctx, f"register learner {tag}", "POST", "/v1/learner/register", 201, spec=AUTH_SPEC,
               json={"email": email, "password": PASSWORD, "first_name": first, "last_name": last})
    if not res.ok:
        return None
    d = res.data
    return Learner(email, PASSWORD, d["access_token"], d["student_id"], first, last)


def new_uuid() -> str:
    return str(uuid.uuid4())


# ------------------------------------------------------------------------------------------------------ solve runtime

PROBLEM_SPEC = {"canonical_code": str, "problem_number": OPT_INT, "official_answer": OPT_STR, "source_url": OPT_STR,
                "paper_code": OPT_STR, "year": OPT_INT, "competition": str}
FALLBACK_SOLVE_CODE = "PRASOLOV_PGV1_CH01_P001"

RUNTIME_SPEC = {
    "attempt": {"solve_attempt_id": str, "student_id": str, "problem_id": str, "attempt_number": int, "status": str,
                "started_at": str, "submitted_at": OPT_STR, "completed_at": OPT_STR, "current_solution_part_id": OPT_STR,
                "current_solution_step_id": OPT_STR, "recovery_plan_id": OPT_STR, "current_recovery_plan_id": OPT_STR,
                "state_version": int, "current_mode": str, "problem_code": str, "statement_text": str},
    "current_step": N({"solution_step_id": str, "solution_part_id": str, "part_label": OPT_STR, "global_step_index": int,
                       "step_type": str, "skill_name": OPT_STR, "is_checkpoint": bool, "goal": str, "state": str,
                       "help_level_used": int, "attempt_count": int, "last_response_text": OPT_STR}),
    "seen_steps": [{"solution_step_id": str, "global_step_index": int, "state": str, "help_level_used": int}],
    "timeline": [{"solution_step_id": str, "global_step_index": int, "state": str, "help_level_used": int, "is_current": bool}],
    "recovery": ANY,
    "progress": {"total_steps": int, "completed_steps": int, "remaining_steps": int},
}
START_SPEC = {"solve_attempt_id": str, "resumed": bool, "replayed": bool, "runtime": RUNTIME_SPEC}
SAVE_SPEC = {"event_id": str, "state": str, "evaluation_status": str, "state_version": int, "replayed": bool}
OUTCOME_SPEC = {"state": str, "independent_success": bool, "current_step_id": OPT_STR, "attempt_completed": bool,
                "state_version": int, "replayed": bool}


def solve_problem_code(ctx: Ctx) -> str:
    """A problem that has published solution steps, found through the public API (memoised for the run)."""
    if "solve_problem_code" in ctx.fixtures:
        return ctx.fixtures["solve_problem_code"]
    code = FALLBACK_SOLVE_CODE
    comps = call(ctx, "list competitions", "GET", "/v1/competitions", 200, spec=[{"external_code": str, "name": str}])
    for comp in comps.data or []:
        if str(comp.get("external_code", "")).startswith("PRASOLOV"):
            ps = call(ctx, f"list problems of {comp['external_code']}", "GET", "/v1/problems", 200, spec=[PROBLEM_SPEC],
                      params={"competition": comp["external_code"], "limit": 3})
            if ps.ok and ps.data:
                code = ps.data[0]["canonical_code"]
            break
    ctx.fixtures["solve_problem_code"] = code
    return code


def start_solve(ctx: Ctx, lr: Learner, case: str = "start solve attempt", *, key: str | None = None) -> Res:
    code = solve_problem_code(ctx)
    return call(ctx, case, "POST", f"/v1/students/{lr.student_id}/problems/{code}/attempts", 201, spec=START_SPEC, token=lr.token,
                leak=SECRET_KEYS | SOLUTION_KEYS, headers={"Idempotency-Key": key} if key else None)


def get_runtime(ctx: Ctx, lr: Learner, aid: str, case: str = "get attempt runtime") -> Res:
    return call(ctx, case, "GET", f"/v1/attempts/{aid}/runtime", 200, spec=RUNTIME_SPEC, token=lr.token,
                leak=SECRET_KEYS | SOLUTION_KEYS)


def state_version(res: Res) -> int | None:
    return res.data["attempt"]["state_version"] if res.ok and res.data else None


def save_response(ctx: Ctx, lr: Learner, aid: str, step: str, sv: int, text: str = "Draw the midline through the midpoints of the legs.",
                  *, evaluate: bool = False, case: str = "save step response", key: str | None = None) -> Res:
    return call(ctx, case, "POST", f"/v1/attempts/{aid}/steps/{step}/responses", 200, spec=SAVE_SPEC, token=lr.token,
                json={"response_text": text, "state_version": sv, "evaluate": evaluate},
                headers={"Idempotency-Key": key} if key else None)


def admin_outcome(ctx: Ctx, aid: str, step: str, sv: int, result: str = "SUCCESS", case: str = "record step outcome (admin)",
                  *, key: str | None = None) -> Res:
    return call(ctx, case, "POST", f"/v1/attempts/{aid}/steps/{step}/outcome", 200, spec=OUTCOME_SPEC, admin=True,
                json={"result": result, "state_version": sv}, headers={"Idempotency-Key": key} if key else None)


def student_ids_in(data: Any) -> set[str]:
    return set(find_values(data, "student_id"))


def find_values(data: Any, key: str) -> list[Any]:
    out: list[Any] = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k == key:
                out.append(v)
            out += find_values(v, key)
    elif isinstance(data, list):
        for v in data:
            out += find_values(v, key)
    return out
