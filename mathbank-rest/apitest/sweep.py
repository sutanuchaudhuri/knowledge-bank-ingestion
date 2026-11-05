"""Contract sweep over every operation of the app, over real HTTP, against real data (mode dev-readonly).

Per operation, where applicable:

* auth-none / auth-bad   secured ops reject missing and garbage credentials with 401/403 (never 2xx, never 5xx)
* not-found              well-formed random ids -> 4xx, never 5xx
* invalid-body           ops with a body, empty `{}` -> <500 (a 2xx/423 means the op accepted it / tried to write)
* happy                  GET (and the read-only POSTs) with fixtures found in real dev data -> 200 and a parseable body
* cross-tenant           student B's token on student A's resource -> 403/404, never 200

Coverage is reported honestly: an op with no usable fixture is listed as `skipped`, not passed.
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from apitest.context import Ctx
from apitest.discover import discover

HTTP_METHODS = ("get", "post", "put", "patch", "delete")
READ_POSTS = {"/v1/search/problems", "/v1/search/concepts", "/v1/quiz-integration/question-pool/match"}
SLOW_MS = 5000


def _find(obj: Any, *keys: str) -> Any:
    """First value for any of `keys`, searching dicts/lists depth-first."""
    if isinstance(obj, dict):
        for k in keys:
            if obj.get(k) not in (None, ""):
                return obj[k]
        for v in obj.values():
            hit = _find(v, *keys)
            if hit not in (None, ""):
                return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = _find(v, *keys)
            if hit not in (None, ""):
                return hit
    return None


def _secured(op: dict) -> bool:
    return bool(op.get("security"))


def _scheme_names(op: dict) -> set[str]:
    return {k for d in (op.get("security") or []) for k in d}


def _dummy(name: str) -> str:
    if name.endswith("_id") or name in ("id", "plan_id"):
        return str(uuid.uuid4())
    if "slug" in name:
        return "no-such-slug"
    if name in ("code", "canonical_code", "problem_ref"):
        return "NO_SUCH_CODE"
    return "x"


def _query_defaults(op: dict, fx: dict) -> dict:
    out = {}
    for p in op.get("parameters", []):
        if p["in"] == "query" and p.get("required"):
            s = p.get("schema", {})
            out[p["name"]] = (s.get("enum") or [None])[0] or ("a" if s.get("type") == "string" else 1)
    return out


def _fill(path: str, values: dict) -> str | None:
    names = re.findall(r"{(\w+)}", path)
    if any(values.get(n) in (None, "") for n in names):
        return None
    return re.sub(r"{(\w+)}", lambda m: str(values[m.group(1)]), path)


def _params(path: str) -> list[str]:
    return re.findall(r"{(\w+)}", path)


def build_fixtures(ctx: Ctx) -> dict:
    """Real ids for every path parameter we can find: dev data first, then public lists, then student A's own lists."""
    from apitest.client import Api

    api: Api = ctx.api
    raw = discover(api_profile())
    fx: dict = {"raw": raw, "A": raw["students"][0], "B": raw["students"][1] if len(raw["students"]) > 1 else None}
    a = fx["A"]
    values: dict[str, Any] = {"student_id": a["id"], "cognito_sub": next((s["cognito_sub"] for s in raw["students"] if s["cognito_sub"]), None)}

    def get(path: str, token: str | None = None, **kw):
        r, _, _ = api.call("GET", path, token=token, **kw)
        return r.json() if r is not None and r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json") else None

    values["canonical_code"] = values["code"] = values["problem_ref"] = _find(get("/v1/problems", params={"limit": 3}), "canonical_code")
    values["slug"] = _find(get("/v1/concepts", params={"limit": 3}), "slug")
    values["concept_slug"] = values["slug"]
    values["technique_slug"] = _find(get("/v1/techniques", params={"limit": 3}), "slug")
    values["micro_code"] = _find(get("/v1/micro-courses", params={"limit": 3}), "canonical_code")
    values["theorem_slug"] = _find(get("/v1/theorems/search", params={"q": "a", "limit": 3}), "slug")
    tok = a["token"]
    solve = get("/v1/learner/solve-attempts", tok)
    values["attempt_id"] = _find(solve, "solve_attempt_id", "attempt_id", "id") or _find(get("/v1/learner/attempts", tok), "attempt_id", "id")
    if values["attempt_id"]:
        rt = get(f"/v1/attempts/{values['attempt_id']}/runtime", tok)
        values["step_id"] = _find(rt, "step_id")
        values["plan_id"] = _find(get(f"/v1/attempts/{values['attempt_id']}/recovery-plans", tok), "plan_id", "id")
    values["enrollment_id"] = _find(get("/v1/learner/micro-course-enrollments", tok), "enrollment_id", "id")
    values["feedback_id"] = _find(get("/v1/learner/feedback", tok), "feedback_id", "id")
    values["notification_id"] = _find(get("/v1/notifications/me", tok), "notification_id", "id")
    for status in ("GRADED", "IN_PROGRESS", "READY", "FAILED"):
        if status in raw["papers"]:
            values["quiz_id"], values["question_id"] = raw["papers"][status]["quiz_id"], raw["papers"][status]["question_id"]
            fx["quiz_owner"] = {"id": raw["papers"][status]["student_id"], "token": raw["papers"][status]["token"]}
            break
    fx["values"] = values
    return fx


def api_profile() -> str:
    import os

    return os.environ.get("MB_AWS_PROFILE", "aws-sutanu-admin")


def run(ctx: Ctx, only: list[str] | None = None) -> None:
    from mathbank_rest.config import settings  # noqa: F401  (process env is already configured by the runner)
    from mathbank_rest.models.manual.exam_pool import STYLES

    api, rec = ctx.api, ctx.rec
    spec = api.http.get("/openapi.json").json()
    ops = [(m.upper(), p, op) for p, item in sorted(spec["paths"].items()) for m, op in item.items() if m in HTTP_METHODS]
    rec.suite = "sweep:inventory"
    rec.add(case="openapi parsed", method="GET", path="/openapi.json", status=200, ms=0, ok=bool(ops), note=f"{len(ops)} operations")

    fx = build_fixtures(ctx)
    values, A, B = fx["values"], fx["A"], fx["B"]
    owner = fx.get("quiz_owner") or A
    skipped: list[str] = []
    read_bodies = {
        "/v1/search/problems": {"query": "triangle with equal sides area", "limit": 3},
        "/v1/search/concepts": {"query": "modular arithmetic", "limit": 3},
        "/v1/quiz-integration/question-pool/match": {"student_id": A["id"], "style": STYLES[0], "limit": 3},
    }
    print(f"fixtures: student {A['id']} ({A['items']} items), params resolved: "
          f"{sorted(k for k, v in values.items() if v)}; unresolved: {sorted(k for k, v in values.items() if not v)}")

    def creds(op: dict, student_token: str | None) -> dict:
        names = _scheme_names(op)
        if "APIKeyHeader" in names:
            return {"admin": True}
        return {"token": student_token}

    for method, path, op in ops:
        if path in ("/health", "/health/stores", "/openapi.json"):
            continue
        tag = f"{method} {path}"
        secured = _secured(op)
        has_body = bool(op.get("requestBody"))
        names = _params(path)
        pv = dict(values)
        if "quiz_id" in names or "question_id" in names:
            pv["student_id"] = owner["id"]
        token = (owner if "quiz" in path else A)["token"]
        dummy = {n: _dummy(n) for n in names}
        dummy_path = _fill(path, dummy) or path

        # ---- authentication
        if secured:
            rec.suite = "sweep:auth"
            api.expect(f"no credentials {tag}", method, dummy_path, {401, 403}, json={} if has_body else None)
            api.expect(f"garbage credentials {tag}", method, dummy_path, {401, 403}, token="garbage.token.value",
                       json={} if has_body else None, headers={"X-Admin-Api-Key": "definitely-not-the-key"})

        # ---- unknown ids / empty bodies (valid credentials)
        if names or has_body:
            rec.suite = "sweep:negative"
            kw = creds(op, token) if secured else {}
            if method == "GET" and names:
                r = api.expect(f"unknown id {tag}", method, dummy_path, set(range(400, 500)), **kw)
                if r is not None and r.status_code == 200:
                    rec.exchanges[-1].note = "200 for a well-formed unknown id (empty result?)"
            elif has_body:
                r = api.expect(f"empty body {tag}", method, dummy_path, set(range(200, 500)), json={}, **kw)
                if r is not None and r.status_code in (423,):
                    rec.exchanges[-1].note = "write attempted; guard blocked it"

        # ---- happy path with real data
        rec.suite = "sweep:happy"
        if method == "GET" or path in READ_POSTS:
            real = _fill(path, pv)
            if real is None:
                skipped.append(f"{tag} (no fixture for {', '.join(n for n in names if pv.get(n) in (None, ''))})")
                continue
            kw = creds(op, token) if secured else {}
            body = read_bodies.get(path)
            r = api.expect(f"happy {tag}", method, real, {200}, json=body, params=_query_defaults(op, fx), **kw)
            if r is not None and r.status_code == 200:
                e = rec.exchanges[-1]
                if "json" in r.headers.get("content-type", ""):
                    try:
                        r.json()
                    except ValueError:
                        e.ok, e.note = False, "invalid JSON body"
                if e.ms > SLOW_MS:
                    e.note = (e.note + " " if e.note else "") + f"slow ({e.ms} ms)"
            # ---- cross-tenant: another learner (or a learner on an admin op) must not read the resource
            scoped = any(n in names for n in ("student_id", "attempt_id", "quiz_id", "enrollment_id", "plan_id", "notification_id"))
            if r is not None and r.status_code == 200 and secured and scoped:
                owner_id = (owner if "quiz" in path else A)["id"]
                other = next((s for s in fx["raw"]["students"] if s["id"] != owner_id), None)
                if other:
                    rec.suite = "sweep:isolation"
                    api.expect(f"other learner {tag}", method, real, {401, 403, 404}, json=body, token=other["token"])

    rec.suite = "sweep:coverage"
    rec.add(case="operations without a fixture (not exercised on the happy path)", method="-", path="-", status=None, ms=0, ok=True,
            note=f"{len(skipped)} skipped: " + "; ".join(skipped))
    try:
        hs, _, _ = api.call("GET", "/health/stores")
        blocked = (hs.json() if hs is not None else {}).get("blocked_writes", [])
        rec.add(case="AWS writes attempted and refused by the guard", method="GET", path="/health/stores", status=200, ms=0, ok=True,
                note=", ".join(blocked) or "none")
    except Exception as exc:  # noqa: BLE001
        rec.add(case="blocked writes readout", method="GET", path="/health/stores", status=None, ms=0, ok=False, note=str(exc))
