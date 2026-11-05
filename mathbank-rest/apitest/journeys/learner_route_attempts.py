"""Tutor route attempts (published routes + hint library; no LLM is involved) and the learner's route-attempt list."""
from __future__ import annotations

from apitest.context import Ctx
from apitest.journeys import journey
from apitest.journeys.learner_common import ANY, OPT_STR, call, check, new_uuid, register, solve_problem_code

VIEW_SPEC = {"route_attempt_id": str, "route_release_id": str, "version": int, "current_step": int, "status": str,
             "tutor_explained_steps": list, "mastery_recorded": bool}
ROW_SPEC = {"route_attempt_id": str, "route_release_id": str, "problem_code": OPT_STR, "status": str, "current_step": int,
            "tutor_explained_steps": list, "version": int, "created_at": str, "updated_at": str, "finished_at": OPT_STR}
LIST_SPEC = {"items": [ROW_SPEC], "next_token": OPT_STR}


@journey("learner_route_attempts")
def learner_route_attempts(ctx: Ctx) -> None:
    lr = register(ctx, "route")
    if lr is None:
        return
    code = solve_problem_code(ctx)
    empty = call(ctx, "route attempts of a fresh learner", "GET", "/v1/learner/route-attempts", 200, spec=LIST_SPEC, token=lr.token)
    if empty.ok:
        check(ctx, "fresh learner has no route attempts", empty.data["items"] == [] and empty.data["next_token"] is None, f"data={empty.data}")

    call(ctx, "start route attempt without a token -> 401", "POST", "/v1/tutor/route-attempts", 401, json={"problem_code": code})
    call(ctx, "start route attempt with a lower-case code -> 422", "POST", "/v1/tutor/route-attempts", 422, token=lr.token, json={"problem_code": "prasolov"})
    call(ctx, "start route attempt for a problem with no published route -> 404/409", "POST", "/v1/tutor/route-attempts", {404, 409}, token=lr.token,
         json={"problem_code": "NO_SUCH_PROBLEM_X99"})
    key = new_uuid()
    st = call(ctx, "start route attempt", "POST", "/v1/tutor/route-attempts", 201, spec=VIEW_SPEC, token=lr.token, json={"problem_code": code},
              headers={"Idempotency-Key": key})
    if not st.ok:
        return
    rid, release = st.data["route_attempt_id"], st.data["route_release_id"]
    check(ctx, "start: version 1, step 1, nothing explained, mastery not recorded", st.data["version"] == 1 and st.data["current_step"] == 1
          and st.data["tutor_explained_steps"] == [] and st.data["mastery_recorded"] is False, f"data={st.data}")
    rep = call(ctx, "start route attempt replay (same Idempotency-Key)", "POST", "/v1/tutor/route-attempts", {200, 201}, token=lr.token,
               json={"problem_code": code}, headers={"Idempotency-Key": key})
    if rep.ok:
        check(ctx, "start replay: same attempt, Idempotent-Replayed header set", rep.data["route_attempt_id"] == rid
              and rep.r.headers.get("Idempotent-Replayed") == "true", f"id={rep.data['route_attempt_id']} header={rep.r.headers.get('Idempotent-Replayed')}")
    res = call(ctx, "start route attempt again (resumes the open one)", "POST", "/v1/tutor/route-attempts", 200, token=lr.token, json={"problem_code": code})
    if res.ok:
        check(ctx, "start again: the open attempt is resumed (200), not duplicated", res.data["route_attempt_id"] == rid)

    cur = call(ctx, "get route attempt", "GET", f"/v1/tutor/route-attempts/{rid}", 200, spec=VIEW_SPEC, token=lr.token)
    if cur.ok:
        check(ctx, "get: same attempt and release", cur.data["route_attempt_id"] == rid and cur.data["route_release_id"] == release)
    call(ctx, "get unknown route attempt -> 404", "GET", f"/v1/tutor/route-attempts/{new_uuid()}", 404, token=lr.token)
    call(ctx, "get route attempt without a token -> 401", "GET", f"/v1/tutor/route-attempts/{rid}", 401)

    lst = call(ctx, "list route attempts", "GET", "/v1/learner/route-attempts", 200, spec=LIST_SPEC, token=lr.token)
    if lst.ok:
        check(ctx, "list: the one open attempt with the problem code", len(lst.data["items"]) == 1 and lst.data["items"][0]["route_attempt_id"] == rid
              and lst.data["items"][0]["problem_code"] == code and lst.data["items"][0]["status"] == "IN_PROGRESS", f"items={lst.data['items']}")
        check(ctx, "route status vocabulary is the same in the attempt view and in the learner list",
              st.data["status"] == lst.data["items"][0]["status"],
              f"view={st.data['status']!r} list={lst.data['items'][0]['status']!r}")
    byrel = call(ctx, "list route attempts by route_release_id", "GET", "/v1/learner/route-attempts", 200, token=lr.token, params={"route_release_id": release})
    if byrel.ok:
        check(ctx, "release filter returns the attempt", len(byrel.data["items"]) == 1)
    call(ctx, "list route attempts FINISHED (none yet)", "GET", "/v1/learner/route-attempts", 200, token=lr.token, params={"status": "FINISHED"})
    call(ctx, "list route attempts invalid status -> 422", "GET", "/v1/learner/route-attempts", 422, token=lr.token, params={"status": "NOPE"})
    call(ctx, "list route attempts malformed release id -> 422", "GET", "/v1/learner/route-attempts", 422, token=lr.token, params={"route_release_id": "x"})
    call(ctx, "list route attempts garbage next_token -> 4xx (not 5xx)", "GET", "/v1/learner/route-attempts", range(400, 500), token=lr.token, params={"next_token": "garbage"})
    call(ctx, "list route attempts limit 0 -> clamped to 1", "GET", "/v1/learner/route-attempts", 200, token=lr.token, params={"limit": 0})

    # --- assist: published hint library
    ap = f"/v1/tutor/route-attempts/{rid}/assist"
    call(ctx, "assist with hint_level 0 -> 422", "POST", ap, 422, token=lr.token, json={"expected_version": 1, "hint_level": 0})
    call(ctx, "assist with hint_level 6 -> 422", "POST", ap, 422, token=lr.token, json={"expected_version": 1, "hint_level": 6})
    call(ctx, "assist with a string expected_version -> 422", "POST", ap, 422, token=lr.token, json={"expected_version": "1", "hint_level": 1})
    call(ctx, "assist with a stale expected_version -> 409", "POST", ap, 409, token=lr.token, json={"expected_version": 9, "hint_level": 1})
    call(ctx, "assist without a token -> 401", "POST", ap, 401, json={"expected_version": 1, "hint_level": 1})
    call(ctx, "assist an unknown attempt -> 404", "POST", f"/v1/tutor/route-attempts/{new_uuid()}/assist", 404, token=lr.token,
         json={"expected_version": 1, "hint_level": 1})
    version, step = 1, 1
    call(ctx, "assist: advance with a hint level below 5 -> 409 (explain the step first)", "POST", ap, 409, token=lr.token,
         json={"expected_version": version, "hint_level": 1, "advance": True})
    a1 = call(ctx, "assist: hint level 1 without advancing", "POST", ap, 200, token=lr.token, json={"expected_version": version, "hint_level": 1},
              spec={**VIEW_SPEC, "hint": ANY, "hint_level": int, "source": str})
    if a1.ok:
        check(ctx, "assist (no advance): same step, version +1, hint from the published library", a1.data["current_step"] == step
              and a1.data["version"] == version + 1 and a1.data["source"] == "published-hint-library" and a1.data["hint_level"] == 1, f"data={a1.data}")
        version = a1.data["version"]
    finished = False
    for _ in range(15):
        step_now = None
        ar = call(ctx, "assist: advance to the next step (requires hint level 5)", "POST", ap, 200, token=lr.token,
                  json={"expected_version": version, "hint_level": 5, "advance": True},
                  spec={**VIEW_SPEC, "hint": ANY})
        if not ar.ok:
            return
        check(ctx, "advance: version increments by one", ar.data["version"] == version + 1, f"{version} -> {ar.data['version']}")
        version = ar.data["version"]
        if ar.data["status"].lower() in ("finished", "complete", "completed"):
            finished = True
            break
        step_now = ar.data["current_step"]
        if step_now is None:
            break
    check(ctx, "advancing through every instructed step finishes the route attempt", finished, f"last status={ar.data['status']!r} step={ar.data['current_step']}")
    fin = call(ctx, "list route attempts FINISHED", "GET", "/v1/learner/route-attempts", 200, spec=LIST_SPEC, token=lr.token, params={"status": "FINISHED"})
    if fin.ok and finished:
        check(ctx, "list: the finished attempt appears with finished_at", [i["route_attempt_id"] for i in fin.data["items"]] == [rid]
              and fin.data["items"][0]["finished_at"] is not None, f"items={fin.data['items']}")
    call(ctx, "assist a finished attempt -> 409", "POST", ap, {404, 409}, token=lr.token, json={"expected_version": version, "hint_level": 1})
    again = call(ctx, "start a route attempt again after finishing -> new attempt", "POST", "/v1/tutor/route-attempts", {200, 201}, token=lr.token,
                 json={"problem_code": code})
    if again.ok and finished:
        check(ctx, "after finishing, a new attempt is created (201) at step 1", again.r.status_code == 201 and again.data["route_attempt_id"] != rid
              and again.data["current_step"] == 1, f"status={again.r.status_code} id={again.data['route_attempt_id']}")
