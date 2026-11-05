"""Isolation and auth hygiene: learner B can never read or change learner A's data; bad tokens are 401; admin routes reject learners."""
from __future__ import annotations

import jwt

from apitest.context import Ctx
from apitest.journeys import journey
from apitest.journeys.learner_common import (
    call,
    check,
    claims,
    forge_token,
    get_runtime,
    new_uuid,
    register,
    save_response,
    solve_problem_code,
    start_solve,
)

DENIED = {403, 404}


def denied(ctx: Ctx, case: str, method: str, path: str, token: str, **kw) -> None:
    call(ctx, f"B cannot {case} -> 403/404", method, path, DENIED, token=token, **kw)


@journey("learner_isolation")
def learner_isolation(ctx: Ctx) -> None:
    a, b = register(ctx, "isoA"), register(ctx, "isoB")
    if a is None or b is None:
        return
    code = solve_problem_code(ctx)

    # --- A builds state in every area
    start_key = new_uuid()
    st = start_solve(ctx, a, key=start_key)
    if not st.ok:
        return
    aid = st.data["solve_attempt_id"]
    step = st.data["runtime"]["attempt"]["current_solution_step_id"]
    sv = st.data["runtime"]["attempt"]["state_version"]
    sv_saved = save_response(ctx, a, aid, step, sv, "A's private working.")
    if not sv_saved.ok:
        return
    sv = sv_saved.data["state_version"]
    call(ctx, "A diagnoses own step", "POST", f"/v1/attempts/{aid}/steps/{step}/diagnose", 200, token=a.token, json={})
    rt = get_runtime(ctx, a, aid)
    sv = rt.data["attempt"]["state_version"] if rt.ok else sv
    cp = call(ctx, "A creates a recovery plan", "POST", f"/v1/attempts/{aid}/recovery-plans", 201, token=a.token, json={"state_version": sv, "trigger": "STUDENT_REQUEST"})
    pid = cp.data["recovery_plan"]["recovery_plan_id"] if cp.ok else new_uuid()
    item = cp.data["recovery_plan"]["items"][0]["recovery_plan_item_id"] if cp.ok else new_uuid()
    sv_plan = cp.data["state_version"] if cp.ok else sv
    enr = call(ctx, "A enrolls in a micro-course", "POST", "/v1/micro-courses/MC-MARKOV-STREAKS/enroll", 201, token=a.token,
               headers={"Idempotency-Key": new_uuid()})
    eid = enr.data["enrollment_id"] if enr.ok else new_uuid()
    esv = enr.data["state_version"] if enr.ok else 1
    act = enr.data["current_state"]["activities"][0]["activity_id"] if enr.ok else new_uuid()
    ra = call(ctx, "A starts a tutor route attempt", "POST", "/v1/tutor/route-attempts", 201, token=a.token, json={"problem_code": code})
    rid = ra.data["route_attempt_id"] if ra.ok else new_uuid()
    la = call(ctx, "A logs an attempt", "POST", "/v1/learner/attempts", 201, token=a.token, json={"problem_code": code, "is_correct": True})
    a_outcome = la.data["attempt"]["attempt_id"] if la.ok else None

    # --- B tries every A-owned resource
    base = f"/v1/attempts/{aid}"
    sp = f"{base}/steps/{step}"
    denied(ctx, "read A's attempt", "GET", base, b.token)
    denied(ctx, "read A's attempt runtime", "GET", f"{base}/runtime", b.token)
    denied(ctx, "save a response on A's attempt", "POST", f"{sp}/responses", b.token, json={"response_text": "hijack", "state_version": sv, "evaluate": False})
    denied(ctx, "request a hint on A's attempt", "POST", f"{sp}/hint", b.token, json={"state_version": sv})
    denied(ctx, "list hints of A's attempt", "GET", f"{sp}/hints", b.token)
    denied(ctx, "diagnose A's step", "POST", f"{sp}/diagnose", b.token, json={})
    denied(ctx, "list A's diagnoses", "GET", f"{base}/diagnoses", b.token)
    denied(ctx, "submit A's attempt", "POST", f"{base}/submit", b.token, json={"state_version": sv})
    denied(ctx, "create a recovery plan on A's attempt", "POST", f"{base}/recovery-plans", b.token, json={"state_version": sv, "trigger": "STUDENT_REQUEST"})
    denied(ctx, "list recovery plans of A's attempt", "GET", f"{base}/recovery-plans", b.token)
    denied(ctx, "read A's recovery plan", "GET", f"/v1/recovery-plans/{pid}", b.token)
    denied(ctx, "read A's next recovery item", "GET", f"/v1/recovery-plans/{pid}/next", b.token)
    denied(ctx, "answer A's recovery item", "POST", f"/v1/recovery-plans/{pid}/items/{item}/responses", b.token, json={"state_version": sv_plan, "acknowledged": True})
    denied(ctx, "abort A's recovery plan", "POST", f"/v1/recovery-plans/{pid}/abort", b.token, json={"state_version": sv_plan})
    denied(ctx, "resume A's recovery plan", "POST", f"/v1/recovery-plans/{pid}/resume", b.token, json={"state_version": sv_plan})
    enr_base = f"/v1/micro-courses/enrollments/{eid}"
    denied(ctx, "read A's enrollment", "GET", enr_base, b.token)
    denied(ctx, "advance A's enrollment", "POST", f"{enr_base}/advance", b.token, json={"expected_state_version": esv, "action": "CONTINUE"})
    denied(ctx, "abandon A's enrollment", "POST", f"{enr_base}/abandon", b.token)
    denied(ctx, "answer an activity in A's enrollment", "POST", f"{enr_base}/activity-responses", b.token, json={"activity_id": act, "choice_index": 0})
    denied(ctx, "answer a learning item in A's enrollment", "POST", f"{enr_base}/responses", b.token, json={"learning_item_id": "x", "choice_index": 0})
    denied(ctx, "record an interaction event in A's enrollment", "POST", f"{enr_base}/interaction-events", b.token,
           json={"interaction_instance_id": new_uuid(), "event_type": "X", "semantic_action": "y"})
    denied(ctx, "ask for help in A's enrollment", "POST", f"{enr_base}/item-help", b.token, json={"item_kind": "activity", "item_id": act, "intent": "give_up"})
    denied(ctx, "read A's route attempt", "GET", f"/v1/tutor/route-attempts/{rid}", b.token)
    denied(ctx, "assist A's route attempt", "POST", f"/v1/tutor/route-attempts/{rid}/assist", b.token, json={"expected_version": 1, "hint_level": 1})
    denied(ctx, "read A's event stream by student id", "GET", f"/v1/students/{a.student_id}/events", b.token)
    denied(ctx, "start an attempt as A (path student id)", "POST", f"/v1/students/{a.student_id}/problems/{code}/attempts", b.token)
    denied(ctx, "mark an unknown/foreign notification read", "POST", f"/v1/notifications/{new_uuid()}/read", b.token)

    # --- the same Idempotency-Key from another learner must not replay A's result
    b_start = start_solve(ctx, b, "B starts the same problem with A's Idempotency-Key", key=start_key)
    if b_start.ok:
        check(ctx, "idempotency keys are scoped per learner: B gets its own attempt, never A's",
              b_start.data["solve_attempt_id"] != aid and b_start.data["runtime"]["attempt"]["student_id"] == b.student_id and b_start.data["replayed"] is False,
              f"B id={b_start.data['solve_attempt_id']} A id={aid} replayed={b_start.data['replayed']} student={b_start.data['runtime']['attempt']['student_id']}")
    b_enr = call(ctx, "B enrolls with A's enroll Idempotency-Key", "POST", "/v1/micro-courses/MC-MARKOV-STREAKS/enroll", 201, token=b.token,
                 headers={"Idempotency-Key": new_uuid()})
    if b_enr.ok:
        check(ctx, "B's enrollment is a different enrollment from A's", b_enr.data["enrollment_id"] != eid)

    # --- B's own lists never contain A's ids
    leaks: dict[str, list] = {}
    for label, path in (("solve-attempts", "/v1/learner/solve-attempts"), ("attempts", "/v1/learner/attempts"), ("events", "/v1/learner/events"),
                        ("micro-course-enrollments", "/v1/learner/micro-course-enrollments"), ("route-attempts", "/v1/learner/route-attempts"),
                        ("mastery", "/v1/learner/mastery"), ("recovery plans of B's attempt", f"/v1/attempts/{b_start.data['solve_attempt_id']}/recovery-plans"
                         if b_start.ok else "/v1/learner/mastery")):
        r = call(ctx, f"B lists {label}", "GET", path, 200, token=b.token)
        if r.ok:
            blob = str(r.data)
            hits = [x for x in (aid, eid, rid, pid, a.student_id, a_outcome) if x and x in blob]
            if hits:
                leaks[label] = hits
    check(ctx, "B's lists contain none of A's attempt/enrollment/route/plan/student ids", not leaks, f"leaked={leaks}")
    ev = call(ctx, "B reads events filtered by A's attempt id", "GET", "/v1/learner/events", 200, token=b.token, params={"attempt_id": aid})
    if ev.ok:
        check(ctx, "events filtered by A's attempt id are empty for B", ev.data["items"] == [], f"items={ev.data['items'][:2]}")
    me = call(ctx, "B reads own profile", "GET", "/v1/learner/me", 200, token=b.token)
    if me.ok:
        check(ctx, "B's profile is B's", me.data["student_id"] == b.student_id and a.student_id not in str(me.data))

    # --- A's data is untouched by every attempt above
    rt_after = get_runtime(ctx, a, aid, "A's runtime after B's attempts")
    if rt_after.ok:
        check(ctx, "A's attempt is unchanged by B's attempts (state_version, step, status, still in recovery)",
              rt_after.data["attempt"]["state_version"] == sv_plan and rt_after.data["attempt"]["current_solution_step_id"] == step
              and rt_after.data["attempt"]["status"] == "IN_PROGRESS" and rt_after.data["attempt"]["current_mode"] == "RECOVERY",
              f"expected version {sv_plan}; attempt={rt_after.data['attempt']}")
    en_after = call(ctx, "A's enrollment after B's attempts", "GET", enr_base, 200, token=a.token)
    if en_after.ok:
        check(ctx, "A's enrollment is unchanged (version, status)", en_after.data["state_version"] == esv and en_after.data["enrollment_status"] == "IN_PROGRESS",
              f"version={en_after.data['state_version']} status={en_after.data['enrollment_status']}")
    pl_after = call(ctx, "A's plan after B's attempts", "GET", f"/v1/recovery-plans/{pid}", 200, token=a.token)
    if pl_after.ok:
        check(ctx, "A's recovery plan is still ACTIVE", pl_after.data["status"] == "ACTIVE", f"status={pl_after.data['status']}")


@journey("learner_auth_hygiene")
def learner_auth_hygiene(ctx: Ctx) -> None:
    a = register(ctx, "hyg")
    if a is None:
        return
    st = start_solve(ctx, a)
    aid = st.data["solve_attempt_id"] if st.ok else new_uuid()
    step = st.data["runtime"]["attempt"]["current_solution_step_id"] if st.ok else "X/STEP-1"
    me = "/v1/learner/me"

    bearer = lambda t: {"Authorization": f"Bearer {t}"}  # noqa: E731
    call(ctx, "no Authorization header -> 401", "GET", me, 401)
    call(ctx, "garbage bearer token -> 401", "GET", me, 401, headers=bearer("garbage"))
    call(ctx, "empty bearer token -> 401", "GET", me, 401, headers={"Authorization": "Bearer"})
    call(ctx, "Basic scheme -> 401", "GET", me, 401, headers={"Authorization": "Basic dXNlcjpwYXNz"})
    call(ctx, "JWT-looking garbage -> 401", "GET", me, 401, headers=bearer("aaaa.bbbb.cccc"))
    call(ctx, "expired token -> 401", "GET", me, 401, headers=bearer(forge_token(a.student_id, expires_in=-60)))
    call(ctx, "token signed with another secret -> 401", "GET", me, 401, headers=bearer(forge_token(a.student_id, secret="not-the-server-secret-0123456789abcdef")))
    call(ctx, "validly signed token for an unknown student -> 401", "GET", me, 401, headers=bearer(forge_token(new_uuid())))
    call(ctx, "validly signed token whose sub is not a uuid -> 401 (not 500)", "GET", me, 401, headers=bearer(forge_token("not-a-uuid")))
    call(ctx, "validly signed token with a future tv -> 401", "GET", me, 401, headers=bearer(forge_token(a.student_id, tv=99)))
    call(ctx, "validly signed token with a negative tv -> 401", "GET", me, 401, headers=bearer(forge_token(a.student_id, tv=-1)))
    unsigned = jwt.encode({"sub": a.student_id, "exp": 9999999999}, key=None, algorithm="none")
    call(ctx, "unsigned (alg=none) token -> 401", "GET", me, 401, headers=bearer(unsigned))
    call(ctx, "valid register token still works", "GET", me, 200, token=a.token)
    call(ctx, "token without tv works while the account's token_version is 0", "GET", me, 200, headers=bearer(forge_token(a.student_id)))
    call(ctx, "token with tv=0 works while the account's token_version is 0", "GET", me, 200, headers=bearer(forge_token(a.student_id, tv=0)))

    # --- the same expired/garbage credentials on a spread of other learner endpoints
    for method, path in (("GET", "/v1/learner/attempts"), ("GET", "/v1/learner/solve-attempts"), ("GET", "/v1/learner/mastery"),
                         ("GET", "/v1/learner/events"), ("GET", f"/v1/attempts/{aid}/runtime"), ("GET", "/v1/notifications/me"),
                         ("POST", "/v1/learner/attempts"), ("POST", f"/v1/attempts/{aid}/submit"),
                         ("POST", "/v1/micro-courses/MC-MARKOV-STREAKS/enroll"), ("GET", "/v1/learner/route-attempts")):
        body = {"problem_code": "X", "is_correct": True, "state_version": 1} if method == "POST" else None
        call(ctx, f"expired token on {method} {path} -> 401", method, path, 401, json=body, headers=bearer(forge_token(a.student_id, expires_in=-60)))
        call(ctx, f"garbage token on {method} {path} -> 401", method, path, 401, json=body, headers=bearer("garbage"))

    # --- admin-only routes
    admin_gets = (f"/v1/admin/attempts/{aid}/runtime", f"/v1/admin/attempts/{aid}/diagnoses", "/v1/admin/knowledge-gaps",
                  f"/v1/admin/students/{a.student_id}/knowledge-gaps", "/v1/admin/recovery-plans", f"/v1/admin/recovery-plans/{new_uuid()}")
    for path in admin_gets:
        call(ctx, f"learner token on {path} -> 401/403", "GET", path, {401, 403}, token=a.token)
        call(ctx, f"no credentials on {path} -> 401", "GET", path, 401)
        call(ctx, f"wrong admin key on {path} -> 401", "GET", path, 401, headers={"X-Admin-Api-Key": "wrong-key"})
        call(ctx, f"learner JWT presented as the admin key on {path} -> 401", "GET", path, 401, headers={"X-Admin-Api-Key": a.token})
    outcome = f"/v1/attempts/{aid}/steps/{step}/outcome"
    call(ctx, "learner token on the step outcome route -> 401/403", "POST", outcome, {401, 403}, token=a.token, json={"result": "SUCCESS", "state_version": 2})
    call(ctx, "no credentials on the step outcome route -> 401", "POST", outcome, 401, json={"result": "SUCCESS", "state_version": 2})

    # --- the admin key is not a learner identity
    for method, path, body in (("GET", me, None), ("GET", "/v1/notifications/me", None), ("GET", "/v1/learner/mastery", None),
                               ("POST", "/v1/learner/attempts", {"problem_code": solve_problem_code(ctx), "is_correct": True}),
                               ("GET", f"/v1/attempts/{aid}/runtime", None), ("POST", "/v1/learner/me/password", {"current_password": "x", "new_password": "yyyyyyyy"})):
        call(ctx, f"admin key alone on {method} {path} -> 401 (not a learner)", method, path, 401, admin=True, json=body)
    check(ctx, "admin key is configured for the harness", bool(ctx.admin_key), "ADMIN_API_KEY missing: admin checks are meaningless")
    a_claims = claims(a.token)
    check(ctx, "register token expiry is in the future and bounded", 0 < a_claims["exp"] - a_claims["iat"] <= 60 * 60 * 24 * 31, f"claims={a_claims}")
