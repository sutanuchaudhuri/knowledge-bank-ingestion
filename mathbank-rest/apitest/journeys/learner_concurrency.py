"""Concurrency on the DynamoDB-backed write paths: racing duplicates must resolve to exactly one winner, never a 5xx or a duplicate row."""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from apitest.context import Ctx
from apitest.journeys import journey
from apitest.journeys.learner_common import (
    PASSWORD,
    Res,
    call,
    check,
    get_runtime,
    new_email,
    new_uuid,
    register,
    solve_problem_code,
    start_solve,
)

N = 6


def race(fns: list[Callable[[], Res]]) -> list[Res]:
    with ThreadPoolExecutor(max_workers=len(fns)) as pool:
        return [f.result() for f in [pool.submit(fn) for fn in fns]]


def statuses(results: list[Res]) -> dict[int | None, int]:
    return dict(Counter(r.status for r in results))


@journey("learner_concurrency")
def learner_concurrency(ctx: Ctx) -> None:
    # --- duplicate registration race: one account, the rest 409
    email = new_email(ctx, "race")
    body = {"email": email, "password": PASSWORD, "first_name": "Race", "last_name": "Condition"}
    results = race([lambda: call(ctx, "register the same email concurrently", "POST", "/v1/learner/register", {201, 409}, json=body)] * N)
    check(ctx, "concurrent duplicate register: exactly one 201, the rest 409", statuses(results).get(201) == 1 and statuses(results).get(409) == N - 1,
          f"statuses={statuses(results)}")
    winners = [r for r in results if r.status == 201]
    if winners:
        lg = call(ctx, "login after the registration race", "POST", "/v1/learner/login", 200, json={"email": email, "password": PASSWORD})
        if lg.ok:
            check(ctx, "login resolves to the winning registration", lg.data["student_id"] == winners[0].data["student_id"])

    lr = register(ctx, "racer")
    if lr is None:
        return
    code = solve_problem_code(ctx)

    # --- concurrent starts of the same problem: a single open attempt
    starts = race([lambda: start_solve(ctx, lr, "start the same problem concurrently")] * N)
    ids = {r.data["solve_attempt_id"] for r in starts if r.ok}
    check(ctx, "concurrent attempt starts: every request succeeded", all(r.ok for r in starts), f"statuses={statuses(starts)}")
    check(ctx, "concurrent attempt starts: exactly one open attempt is created", len(ids) == 1, f"attempt ids={sorted(ids)}")
    open_list = call(ctx, "list in-progress solve attempts after the race", "GET", "/v1/learner/solve-attempts", 200, token=lr.token, params={"status": "IN_PROGRESS"})
    if open_list.ok:
        check(ctx, "only one IN_PROGRESS solve attempt is listed", len(open_list.data["items"]) == 1, f"items={len(open_list.data['items'])}")
    if len(ids) < 1:
        return
    aid = sorted(ids)[0]
    rt = get_runtime(ctx, lr, aid)
    if not rt.ok:
        return
    step, sv = rt.data["attempt"]["current_solution_step_id"], rt.data["attempt"]["state_version"]

    # --- optimistic concurrency: same state_version, one winner
    saves = race([lambda i=i: call(ctx, "save a response concurrently (same state_version)", "POST", f"/v1/attempts/{aid}/steps/{step}/responses",
                                   {200, 409}, token=lr.token,
                                   json={"response_text": f"racing answer {i}", "state_version": sv, "evaluate": False}) for i in range(N)])
    check(ctx, "same state_version raced: exactly one save wins, the rest 409", statuses(saves).get(200) == 1 and statuses(saves).get(409) == N - 1,
          f"statuses={statuses(saves)}")
    rt = get_runtime(ctx, lr, aid, "runtime after the save race")
    if not rt.ok:
        return
    sv2 = rt.data["attempt"]["state_version"]
    check(ctx, "the race advanced the state_version exactly once", sv2 == sv + 1, f"{sv} -> {sv2}")

    outs = race([lambda: call(ctx, "record the same outcome concurrently (admin)", "POST", f"/v1/attempts/{aid}/steps/{step}/outcome", {200, 409},
                              admin=True, json={"result": "SUCCESS", "state_version": sv2}) for _ in range(N)])
    check(ctx, "same outcome raced: exactly one wins, the rest 409", statuses(outs).get(200) == 1 and statuses(outs).get(409) == N - 1, f"statuses={statuses(outs)}")
    rt = get_runtime(ctx, lr, aid, "runtime after the outcome race")
    if rt.ok:
        check(ctx, "the outcome race completed exactly one step", rt.data["progress"]["completed_steps"] == 1, f"progress={rt.data['progress']}")

    hints = race([lambda: call(ctx, "request a hint concurrently (same state_version)", "POST", f"/v1/attempts/{aid}/steps/{rt.data['attempt']['current_solution_step_id']}/hint",
                               {200, 409}, token=lr.token, json={"state_version": rt.data["attempt"]["state_version"]}) for _ in range(3)]) if rt.ok else []
    if hints:
        check(ctx, "hint raced on one state_version: exactly one escalation", statuses(hints).get(200) == 1, f"statuses={statuses(hints)}")

    # --- enrollment race
    enr = race([lambda: call(ctx, "enroll concurrently", "POST", "/v1/micro-courses/MC-MARKOV-STREAKS/enroll", 201, token=lr.token) for _ in range(N)])
    eids = {r.data["enrollment_id"] for r in enr if r.ok}
    check(ctx, "concurrent enroll: a single enrollment results", len(eids) == 1 and all(r.ok for r in enr), f"enrollment ids={sorted(eids)} statuses={statuses(enr)}")
    lst = call(ctx, "list enrollments after the race", "GET", "/v1/learner/micro-course-enrollments", 200, token=lr.token)
    if lst.ok:
        check(ctx, "enrollment list shows one enrollment", lst.data["total"] == 1, f"total={lst.data['total']}")
    if eids:
        eid = sorted(eids)[0]
        cur = call(ctx, "get enrollment before the advance race", "GET", f"/v1/micro-courses/enrollments/{eid}", 200, token=lr.token)
        if cur.ok:
            adv = race([lambda: call(ctx, "advance the same state_version concurrently", "POST", f"/v1/micro-courses/enrollments/{eid}/advance", {200, 409},
                                     token=lr.token, json={"expected_state_version": cur.data["state_version"], "action": "CONTINUE"}) for _ in range(N)])
            check(ctx, "advance raced on one state_version: exactly one wins", statuses(adv).get(200) == 1, f"statuses={statuses(adv)}")

    # --- attempt logging with one Idempotency-Key
    key = new_uuid()
    logs = race([lambda: call(ctx, "log an attempt concurrently with one Idempotency-Key", "POST", "/v1/learner/attempts", {201, 409}, token=lr.token,
                              json={"problem_code": code, "is_correct": True}, headers={"Idempotency-Key": key}) for _ in range(N)])
    check(ctx, "concurrent attempt logging with one key: no 5xx", all(r.status in (201, 409) for r in logs), f"statuses={statuses(logs)}")
    atts = call(ctx, "list attempts after the idempotent race", "GET", "/v1/learner/attempts", 200, token=lr.token)
    if atts.ok:
        manual = [a for a in atts.data if a["source"] != "step_runtime"]
        check(ctx, "one Idempotency-Key raced: exactly one logged attempt", len(manual) == 1, f"logged attempts={len(manual)} statuses={statuses(logs)}")

    # --- parallel password changes: at most one succeeds per token version
    pw = race([lambda i=i: call(ctx, "change password concurrently", "POST", "/v1/learner/me/password", {200, 403, 409, 429}, token=lr.token,
                                json={"current_password": PASSWORD, "new_password": f"Apitest-Race-{i}-Passw0rd!"}) for i in range(3)])
    check(ctx, "concurrent password changes: no more than one succeeds", statuses(pw).get(200, 0) <= 1, f"statuses={statuses(pw)}")
    lost = [r for r in pw if r.status == 409]
    check(ctx, "a lost password-change race returns a client-facing message, not a store-internal condition_failed/op key",
          all(r.detail not in ("condition_failed", None) and "op" not in (r.data or {}) for r in lost), f"409 bodies={[r.data for r in lost]}")
