"""Learner solve runtime over DynamoDB: step-by-step attempts, hints, diagnoses, admin outcomes, submit, recovery plans."""
from __future__ import annotations

from apitest.context import Ctx
from apitest.journeys import journey
from apitest.journeys.learner_common import (
    ANSWER_KEYS,
    DIAGNOSIS_INTERNALS,
    NUM,
    OPT_STR,
    SECRET_KEYS,
    SOLUTION_KEYS,
    admin_outcome,
    call,
    check,
    get_runtime,
    new_uuid,
    register,
    save_response,
    start_solve,
    state_version,
    find_keys,
)

HINT_SPEC = {"help_level": int, "help_kind": str, "hint_text": OPT_STR, "state_version": int, "replayed": bool, "hint_source": str}
HINTS_SPEC = {"solution_step_id": str, "help_level_used": int,
              "hints": [{"help_level": int, "help_kind": str, "hint_text": OPT_STR, "hint_source": str}]}
DIAGNOSIS_VIEW_SPEC = {
    "gap_diagnosis_id": str, "solution_step_id": str, "trigger": str, "created_at": str, "recommended_action": str,
    "recommended_action_label": str, "ranked_by": str, "probes": list,
    "hypotheses": [{"rank": int, "knowledge_gap_id": str, "focus": str, "focus_label": str, "target_label": str, "likelihood": str,
                    "status": str}],
}
ADMIN_DIAGNOSIS_SPEC = {"gap_diagnosis_id": str, "student_id": str, "solve_attempt_id": str, "solution_step_id": str, "trigger": str,
                        "recommended_action": str, "evidence": dict, "probes": list, "diagnoser_version": str,
                        "hypotheses": [{"knowledge_gap_id": str, "rank": int, "failure_location": str, "failure_mode": str,
                                        "confidence": NUM}]}
ADMIN_RUNTIME_SPEC = {"attempt": dict, "current_step_id": OPT_STR, "progress": dict, "recovery": object,
                      "steps": [{"solution_step_id": str, "global_step_index": int, "state": str, "help_level_used": int,
                                 "is_current": bool}]}
PLAN_SPEC = {
    "recovery_plan_id": str, "solve_attempt_id": str, "status": str, "trigger": str, "target_label": str, "current_item_ordinal": int,
    "created_at": str, "mastery": {"independent_successes": int, "independent_successes_required": int, "transfer_passed": bool,
                                   "transfer_required": bool, "met": bool},
    "origin": {"problem_code": str, "solution_step_id": str, "global_step_index": int}, "can_return": bool,
    "items": [{"recovery_plan_item_id": str, "ordinal": int, "stage": str, "item_kind": str, "is_transfer": bool, "status": str,
               "tries": int}],
}
PLAN_CREATE_SPEC = {"recovery_plan": PLAN_SPEC, "replayed": bool, "resumed": bool, "state_version": int}
NEXT_SPEC = {"recovery_plan_id": str, "status": str, "item": object}
ITEM_RESPONSE_SPEC = {"result": {"result": str, "verdict": str}, "decision": str, "transition": str, "state_version": int,
                      "recovery_plan": PLAN_SPEC}
LEAVE_SPEC = {"returned_to_step_id": OPT_STR, "recovery_plan_id": str, "plan_status": str, "state_version": int, "replayed": bool}
EVENT_SPEC = [{"event_id": str, "solve_attempt_id": str, "event_type": str, "event_time": str, "actor_type": str, "payload": dict}]


@journey("learner_solve_steps")
def learner_solve_steps(ctx: Ctx) -> None:
    lr = register(ctx, "solve")
    if lr is None:
        return
    key = new_uuid()
    st = start_solve(ctx, lr, key=key)
    if not st.ok:
        return
    aid = st.data["solve_attempt_id"]
    rt = st.data["runtime"]
    attempt = rt["attempt"]
    step, sv = attempt["current_solution_step_id"], attempt["state_version"]
    base = f"/v1/attempts/{aid}"
    check(ctx, "start: new attempt, not resumed/replayed", not st.data["resumed"] and not st.data["replayed"], f"data flags={st.data['resumed']}/{st.data['replayed']}")
    check(ctx, "start: IN_PROGRESS / SOLVING / attempt_number 1",
          attempt["status"] == "IN_PROGRESS" and attempt["current_mode"] == "SOLVING" and attempt["attempt_number"] == 1, f"attempt={attempt}")
    check(ctx, "start: attempt belongs to the caller", attempt["student_id"] == lr.student_id)
    tl = rt["timeline"]
    check(ctx, "start: only the first step is presented, the rest LOCKED",
          tl[0]["state"] == "PRESENTED" and all(t["state"] == "LOCKED" for t in tl[1:]), f"states={[t['state'] for t in tl]}")
    check(ctx, "start: progress.total_steps equals the timeline length", rt["progress"]["total_steps"] == len(tl))
    check(ctx, "start: locked steps expose no skill/goal text", all("goal" not in t and "step_text" not in t for t in tl[1:]))

    replay = start_solve(ctx, lr, "start attempt: same Idempotency-Key replays", key=key)
    if replay.ok:
        check(ctx, "start replay: same attempt, replayed=true", replay.data["solve_attempt_id"] == aid and replay.data["replayed"] is True,
              f"data={replay.data['solve_attempt_id']} replayed={replay.data['replayed']}")
    resume = start_solve(ctx, lr, "start attempt: second start resumes the open attempt")
    if resume.ok:
        check(ctx, "start again: resumed=true, same attempt", resume.data["resumed"] is True and resume.data["solve_attempt_id"] == aid,
              f"resumed={resume.data['resumed']} id={resume.data['solve_attempt_id']}")

    code = attempt["problem_code"]
    by_uuid = call(ctx, "start by problem uuid resumes the open attempt", "POST", f"/v1/students/{lr.student_id}/problems/{attempt['problem_id']}/attempts",
                   201, token=lr.token)
    if by_uuid.ok:
        check(ctx, "start by uuid: same open attempt", by_uuid.data["solve_attempt_id"] == aid and by_uuid.data["resumed"] is True)
    call(ctx, "start for an unknown problem code -> 404", "POST", f"/v1/students/{lr.student_id}/problems/NO_SUCH_PROBLEM/attempts", 404, token=lr.token)
    call(ctx, "start for a problem uuid that does not exist -> 404", "POST", f"/v1/students/{lr.student_id}/problems/{new_uuid()}/attempts", 404, token=lr.token)
    call(ctx, "start for a problem without published steps -> 409", "POST", f"/v1/students/{lr.student_id}/problems/AIME_1983_Q01/attempts", 409, token=lr.token)
    call(ctx, "start with a malformed student id -> 422", "POST", f"/v1/students/not-a-uuid/problems/{code}/attempts", 422, token=lr.token)
    call(ctx, "start without a token -> 401", "POST", f"/v1/students/{lr.student_id}/problems/{code}/attempts", 401)

    a1 = call(ctx, "get attempt (alias)", "GET", base, 200, token=lr.token, leak=SECRET_KEYS | SOLUTION_KEYS)
    a2 = get_runtime(ctx, lr, aid)
    if a1.ok and a2.ok:
        check(ctx, "GET /attempts/{id} equals GET /attempts/{id}/runtime", a1.data["attempt"] == a2.data["attempt"])
    call(ctx, "get runtime of an unknown attempt -> 404", "GET", f"/v1/attempts/{new_uuid()}/runtime", 404, token=lr.token)
    call(ctx, "get runtime with a malformed id -> 422", "GET", "/v1/attempts/not-a-uuid/runtime", 422, token=lr.token)
    call(ctx, "get runtime without a token -> 401", "GET", f"{base}/runtime", 401)

    adm = call(ctx, "admin attempt runtime", "GET", f"/v1/admin/attempts/{aid}/runtime", 200, spec=ADMIN_RUNTIME_SPEC, admin=True,
               leak=SECRET_KEYS | SOLUTION_KEYS)
    if adm.ok:
        check(ctx, "admin runtime omits the statement text", "statement_text" not in adm.data["attempt"])
    call(ctx, "admin attempt runtime with a learner token -> 401/403", "GET", f"/v1/admin/attempts/{aid}/runtime", {401, 403}, token=lr.token)
    call(ctx, "admin attempt runtime with a wrong admin key -> 401", "GET", f"/v1/admin/attempts/{aid}/runtime", 401,
         headers={"X-Admin-Api-Key": "definitely-not-the-key"})

    # --- steps that are not the current one
    locked = tl[1]["solution_step_id"] if len(tl) > 1 else None
    if locked:
        lp = f"{base}/steps/{locked}"
        call(ctx, "save a response on a LOCKED step -> 409/404", "POST", f"{lp}/responses", {404, 409}, token=lr.token,
             json={"response_text": "skipping ahead", "state_version": sv, "evaluate": False})
        call(ctx, "hint on a LOCKED step -> 409/404", "POST", f"{lp}/hint", {404, 409}, token=lr.token, json={"state_version": sv})
        call(ctx, "diagnose a LOCKED step -> 409/404", "POST", f"{lp}/diagnose", {404, 409}, token=lr.token, json={})
        call(ctx, "admin outcome on a LOCKED step -> 409/404", "POST", f"{lp}/outcome", {404, 409}, admin=True, json={"result": "SUCCESS", "state_version": sv})
        lh = call(ctx, "list hints of a LOCKED step", "GET", f"{lp}/hints", {200, 404, 409}, token=lr.token)
        if lh.status == 200:
            check(ctx, "hints of a LOCKED step reveal nothing", lh.data["help_level_used"] == 0 and lh.data["hints"] == [], f"data={lh.data}")
    after_locked = get_runtime(ctx, lr, aid, "runtime after the LOCKED-step probes")
    if after_locked.ok:
        check(ctx, "LOCKED-step probes changed nothing", after_locked.data["attempt"]["state_version"] == sv
              and after_locked.data["timeline"][1]["state"] == "LOCKED", f"attempt={after_locked.data['attempt']}")

    # --- save a response (no LLM)
    sp = f"{base}/steps/{step}"
    call(ctx, "save response with a stale state_version -> 409", "POST", f"{sp}/responses", 409, token=lr.token,
         json={"response_text": "stale", "state_version": max(1, sv - 1), "evaluate": False})
    call(ctx, "save blank response -> 422", "POST", f"{sp}/responses", 422, token=lr.token,
         json={"response_text": "", "state_version": sv, "evaluate": False})
    call(ctx, "save response over 10000 chars -> 422", "POST", f"{sp}/responses", 422, token=lr.token,
         json={"response_text": "x" * 10_001, "state_version": sv, "evaluate": False})
    call(ctx, "save response to a step outside the attempt -> 404/409", "POST", f"{base}/steps/NOPE/STEP-9.9-Z-99/responses", {404, 409},
         token=lr.token, json={"response_text": "x", "state_version": sv, "evaluate": False})
    rkey = new_uuid()
    saved = save_response(ctx, lr, aid, step, sv, "Take the midpoints P, Q of the legs; the midline PQ is parallel to the bases.", key=rkey)
    if not saved.ok:
        return
    check(ctx, "save: state ATTEMPTED, evaluation PENDING (evaluate=false)", saved.data["state"] == "ATTEMPTED"
          and saved.data["evaluation_status"] == "PENDING" and saved.data["replayed"] is False, f"data={saved.data}")
    check(ctx, "save: state_version advanced", saved.data["state_version"] > sv, f"{sv} -> {saved.data['state_version']}")
    sv = saved.data["state_version"]
    again = save_response(ctx, lr, aid, step, sv - 1, "Take the midpoints P, Q of the legs; the midline PQ is parallel to the bases.",
                          case="save response: same Idempotency-Key replays", key=rkey)
    if again.ok:
        check(ctx, "save replay: replayed=true, version unchanged", again.data["replayed"] is True and again.data["state_version"] == sv,
              f"data={again.data}")

    # --- hints
    call(ctx, "hint with a stale state_version -> 409", "POST", f"{sp}/hint", 409, token=lr.token, json={"state_version": max(1, sv - 2)})
    call(ctx, "hint for a step outside the attempt -> 404/409", "POST", f"{base}/steps/NOPE/STEP-9.9-Z-99/hint", {404, 409}, token=lr.token,
         json={"state_version": sv})
    h1 = call(ctx, "hint level 1 (published/generated text)", "POST", f"{sp}/hint", 200, spec=HINT_SPEC, token=lr.token,
              json={"state_version": sv}, leak=SECRET_KEYS)
    if h1.ok:
        check(ctx, "hint 1: level 1 DIRECTIONAL_PROMPT with text and a bumped state_version",
              h1.data["help_level"] == 1 and h1.data["help_kind"] == "DIRECTIONAL_PROMPT" and (h1.data["hint_text"] or "").strip()
              and h1.data["state_version"] > sv, f"data={h1.data}")
        sv = h1.data["state_version"]
        check(ctx, "hint 1 text is not the canonical step", h1.data["hint_source"] != "REFERENCE", f"hint_source={h1.data['hint_source']}")
    h2 = call(ctx, "hint level 2", "POST", f"{sp}/hint", 200, spec=HINT_SPEC, token=lr.token, json={"state_version": sv})
    if h2.ok:
        check(ctx, "hint 2 escalates to level 2 and delivers text (hint_source UNAVAILABLE = generation failed but the level was spent)",
              h2.data["help_level"] == 2 and bool((h2.data["hint_text"] or "").strip()), f"data={h2.data}")
        sv = h2.data["state_version"]
    hl = call(ctx, "list revealed hints", "GET", f"{sp}/hints", 200, spec=HINTS_SPEC, token=lr.token)
    if hl.ok:
        check(ctx, "hints list matches the escalation", hl.data["help_level_used"] == 2 and [h["help_level"] for h in hl.data["hints"]] == [1, 2],
              f"data={hl.data}")
    call(ctx, "list hints for a step outside the attempt -> 404", "GET", f"{base}/steps/NOPE/STEP-9.9-Z-99/hints", 404, token=lr.token)

    # --- diagnose (deterministic) and the learner/admin views
    d1 = call(ctx, "diagnose current step", "POST", f"{sp}/diagnose", 200, spec={**DIAGNOSIS_VIEW_SPEC, "reused": bool}, token=lr.token,
              json={}, leak=SECRET_KEYS | DIAGNOSIS_INTERNALS)
    d2 = call(ctx, "diagnose again with identical evidence (reused)", "POST", f"{sp}/diagnose", 200, token=lr.token, json={})
    if d1.ok and d2.ok:
        check(ctx, "diagnose: identical evidence returns the same diagnosis", d2.data["gap_diagnosis_id"] == d1.data["gap_diagnosis_id"]
              and d2.data["reused"] is True and d1.data["reused"] is False, f"{d1.data['reused']}/{d2.data['reused']}")
        check(ctx, "diagnose: hypotheses are ranked 1..n", [h["rank"] for h in d1.data["hypotheses"]] == list(range(1, len(d1.data["hypotheses"]) + 1)))
    call(ctx, "diagnose with an unknown trigger -> 422", "POST", f"{sp}/diagnose", 422, token=lr.token, json={"trigger": "ADMIN"})
    call(ctx, "diagnose without a token -> 401", "POST", f"{sp}/diagnose", 401, json={})
    dl = call(ctx, "list diagnoses (learner view)", "GET", f"{base}/diagnoses", 200, spec=[DIAGNOSIS_VIEW_SPEC], token=lr.token,
              leak=SECRET_KEYS | DIAGNOSIS_INTERNALS)
    if dl.ok and d1.ok:
        check(ctx, "diagnoses list contains the diagnosis", any(x["gap_diagnosis_id"] == d1.data["gap_diagnosis_id"] for x in dl.data))
    ad = call(ctx, "list diagnoses (admin view)", "GET", f"/v1/admin/attempts/{aid}/diagnoses", 200, spec=[ADMIN_DIAGNOSIS_SPEC], admin=True)
    if ad.ok:
        check(ctx, "admin diagnoses are keyed to this learner", all(x["student_id"] == lr.student_id for x in ad.data))
    call(ctx, "admin diagnoses with a learner token -> 401/403", "GET", f"/v1/admin/attempts/{aid}/diagnoses", {401, 403}, token=lr.token)
    call(ctx, "admin knowledge-gaps overview with a learner token -> 401/403", "GET", "/v1/admin/knowledge-gaps", {401, 403}, token=lr.token)
    call(ctx, "admin student knowledge-gaps with a learner token -> 401/403", "GET", f"/v1/admin/students/{lr.student_id}/knowledge-gaps",
         {401, 403}, token=lr.token)
    gaps = call(ctx, "admin student knowledge-gaps", "GET", f"/v1/admin/students/{lr.student_id}/knowledge-gaps", 200, admin=True)
    if gaps.ok:
        check(ctx, "knowledge gaps: the diagnosis produced at least one hypothesis", len(gaps.data) >= 1, f"count={len(gaps.data)}")
    call(ctx, "admin knowledge-gaps overview", "GET", "/v1/admin/knowledge-gaps", 200, admin=True)

    # --- outcomes are admin-only
    call(ctx, "outcome with a learner token -> 401/403 (a learner can never self-grade)", "POST", f"{sp}/outcome", {401, 403}, token=lr.token,
         json={"result": "SUCCESS", "state_version": sv})
    call(ctx, "outcome with no credentials -> 401", "POST", f"{sp}/outcome", 401, json={"result": "SUCCESS", "state_version": sv})
    call(ctx, "outcome with an invalid result -> 422", "POST", f"{sp}/outcome", 422, admin=True, json={"result": "MAYBE", "state_version": sv})
    call(ctx, "outcome with a stale state_version -> 409", "POST", f"{sp}/outcome", 409, admin=True,
         json={"result": "SUCCESS", "state_version": max(1, sv - 3)})
    okey = new_uuid()
    out = admin_outcome(ctx, aid, step, sv, key=okey)
    if not out.ok:
        return
    check(ctx, "outcome: SUCCESS after hints is SUCCESS_WITH_HELP, not independent",
          out.data["state"] == "SUCCESS_WITH_HELP" and out.data["independent_success"] is False, f"data={out.data}")
    check(ctx, "outcome: advances to a different current step", out.data["current_step_id"] not in (None, step), f"current={out.data['current_step_id']}")
    out_replay = admin_outcome(ctx, aid, step, sv, case="outcome: same Idempotency-Key replays", key=okey)
    if out_replay.ok:
        check(ctx, "outcome replay: replayed=true and unchanged version", out_replay.data["replayed"] is True
              and out_replay.data["state_version"] == out.data["state_version"], f"data={out_replay.data}")
    rt2 = get_runtime(ctx, lr, aid, "runtime after the first outcome")
    if not rt2.ok:
        return
    step2, sv = rt2.data["attempt"]["current_solution_step_id"], rt2.data["attempt"]["state_version"]
    check(ctx, "runtime: progress shows 1 completed step", rt2.data["progress"]["completed_steps"] == 1, f"progress={rt2.data['progress']}")
    check(ctx, "runtime: step 1 is SUCCESS_WITH_HELP in the timeline", rt2.data["timeline"][0]["state"] == "SUCCESS_WITH_HELP",
          f"states={[t['state'] for t in rt2.data['timeline']]}")

    # --- LLM-backed evaluation: exactly one call in the run
    ev = call(ctx, "save response with evaluate=true (LLM evaluator)", "POST", f"{base}/steps/{step2}/responses", 200,
              spec={**{k: v for k, v in {"event_id": str, "state": str, "evaluation_status": str, "state_version": int}.items()}},
              token=lr.token, json={"response_text": "Apply similar triangles to the two triangles cut off by the midline to get the segment (a-b)/2.",
                                    "state_version": sv, "evaluate": True}, leak=SECRET_KEYS | SOLUTION_KEYS)
    if ev.ok:
        check(ctx, "evaluate=true: evaluation_status is EVALUATED (UNAVAILABLE means the model call failed)",
              ev.data["evaluation_status"] == "EVALUATED", f"evaluation_status={ev.data['evaluation_status']} data={str(ev.data)[:300]}")
        check(ctx, "evaluate=true: the response does not expose student_id/problem_id of the outcome",
              "student_id" not in ev.data and "problem_id" not in ev.data)
        if ev.data["evaluation_status"] == "EVALUATED":
            check(ctx, "evaluate=true: a student-view evaluation object is returned", isinstance(ev.data.get("evaluation"), dict),
                  f"keys={sorted(ev.data)}")
            check(ctx, "evaluate=true: evaluation view hides grader internals", not find_keys(ev.data.get("evaluation"), DIAGNOSIS_INTERNALS),
                  f"hits={find_keys(ev.data.get('evaluation'), DIAGNOSIS_INTERNALS)}")
    rt3 = get_runtime(ctx, lr, aid, "runtime after evaluation")
    if not rt3.ok:
        return
    sv = rt3.data["attempt"]["state_version"]

    prac = call(ctx, "practice for a step (same-skill steps of other problems)", "GET", f"/v1/solution-steps/{step}/practice", 200,
                spec={"anchor": dict, "embedding_available": bool, "results": list}, token=lr.token, params={"limit": 3},
                leak=SECRET_KEYS | SOLUTION_KEYS)
    if prac.ok:
        check(ctx, "practice: honours limit and never returns the anchor's own problem step text", len(prac.data["results"]) <= 3)
    call(ctx, "practice without a token -> 401", "GET", f"/v1/solution-steps/{step}/practice", 401)
    call(ctx, "practice for an unknown step -> 404", "GET", "/v1/solution-steps/NOPE/STEP-9.9-Z-99/practice", 404, token=lr.token)

    # --- submit
    call(ctx, "submit with a stale state_version -> 409", "POST", f"{base}/submit", 409, token=lr.token, json={"state_version": max(1, sv - 3)})
    skey = new_uuid()
    sub = call(ctx, "submit attempt (partial work)", "POST", f"{base}/submit", 200, spec={"status": str, "state_version": int, "replayed": bool},
               token=lr.token, json={"state_version": sv}, headers={"Idempotency-Key": skey})
    if sub.ok:
        check(ctx, "submit: status SUBMITTED", sub.data["status"] == "SUBMITTED", f"data={sub.data}")
        rep = call(ctx, "submit replay with the same Idempotency-Key", "POST", f"{base}/submit", 200, token=lr.token,
                   json={"state_version": sv}, headers={"Idempotency-Key": skey})
        if rep.ok:
            check(ctx, "submit replay: replayed=true", rep.data["replayed"] is True, f"data={rep.data}")
        call(ctx, "submit a second time without a key -> 409 (already submitted)", "POST", f"{base}/submit", {200, 409}, token=lr.token,
             json={"state_version": sub.data["state_version"]})
        late = get_runtime(ctx, lr, aid, "runtime after submit")
        if late.ok:
            check(ctx, "after submit: attempt status SUBMITTED, mode REVIEW", late.data["attempt"]["status"] == "SUBMITTED"
                  and late.data["attempt"]["current_mode"] == "REVIEW", f"attempt={late.data['attempt']}")
            call(ctx, "save response after submit -> 409", "POST", f"{base}/steps/{step2}/responses", 409, token=lr.token,
                 json={"response_text": "too late", "state_version": late.data["attempt"]["state_version"], "evaluate": False})
        nxt = start_solve(ctx, lr, "start the problem again after submitting (a second attempt)")
        if nxt.ok:
            check(ctx, "second start: a new attempt number 2", nxt.data["solve_attempt_id"] != aid
                  and nxt.data["runtime"]["attempt"]["attempt_number"] == 2 and nxt.data["resumed"] is False,
                  f"id={nxt.data['solve_attempt_id']} number={nxt.data['runtime']['attempt']['attempt_number']}")


@journey("learner_solve_complete")
def learner_solve_complete(ctx: Ctx) -> None:
    """Drive every step to an independent success with admin outcomes (no LLM), then read everything the learner sees afterwards."""
    lr = register(ctx, "complete")
    if lr is None:
        return
    st = start_solve(ctx, lr)
    if not st.ok:
        return
    aid = st.data["solve_attempt_id"]
    total = st.data["runtime"]["progress"]["total_steps"]
    last = None
    for _ in range(total + 3):
        rt = get_runtime(ctx, lr, aid, "runtime before the next step")
        if not rt.ok:
            return
        cur, sv = rt.data["attempt"]["current_solution_step_id"], rt.data["attempt"]["state_version"]
        if cur is None or rt.data["attempt"]["status"] != "IN_PROGRESS":
            break
        saved = save_response(ctx, lr, aid, cur, sv, "Working through this step on my own.")
        if not saved.ok:
            return
        last = admin_outcome(ctx, aid, cur, saved.data["state_version"])
        if not last.ok:
            return
        check(ctx, "independent step: SUCCESS_INDEPENDENT with no help", last.data["state"] == "SUCCESS_INDEPENDENT"
              and last.data["independent_success"] is True, f"data={last.data}")
        if last.data["attempt_completed"]:
            break
    if last is None or not last.data["attempt_completed"]:
        check(ctx, "attempt completes after every step succeeds", False, f"last outcome={last.data if last else None}")
        return
    outcome = last.data.get("outcome_attempt")
    check(ctx, "completion records an outcome attempt", isinstance(outcome, dict) and "attempt_id" in outcome, f"outcome_attempt={outcome}")
    done = get_runtime(ctx, lr, aid, "runtime after completion")
    if done.ok:
        check(ctx, "completed attempt: no current step, all steps counted", done.data["attempt"]["current_solution_step_id"] is None
              and done.data["progress"]["completed_steps"] == total, f"attempt={done.data['attempt']} progress={done.data['progress']}")
        check(ctx, "completed attempt: status is COMPLETED", done.data["attempt"]["status"] == "COMPLETED", f"status={done.data['attempt']['status']}")
        sv = done.data["attempt"]["state_version"]
        call(ctx, "submit an already completed attempt", "POST", f"/v1/attempts/{aid}/submit", {200, 409}, token=lr.token,
             json={"state_version": sv})

    # --- everything the learner can read afterwards
    sa = call(ctx, "list solve attempts", "GET", "/v1/learner/solve-attempts", 200, token=lr.token,
              spec={"items": [{"solve_attempt_id": str, "problem_id": str, "problem_code": str, "attempt_number": int, "status": str,
                               "current_mode": str, "started_at": str, "state_version": int}], "limit": int, "next_token": OPT_STR})
    if sa.ok:
        check(ctx, "solve-attempts lists the attempt", any(i["solve_attempt_id"] == aid for i in sa.data["items"]), f"items={sa.data['items']}")
    flt = call(ctx, "list solve attempts filtered by status", "GET", "/v1/learner/solve-attempts", 200, token=lr.token,
               params={"status": "COMPLETED"})
    if flt.ok:
        check(ctx, "status filter returns only COMPLETED", all(i["status"] == "COMPLETED" for i in flt.data["items"]) and flt.data["items"],
              f"items={flt.data['items']}")
    call(ctx, "list solve attempts with an invalid status -> 422", "GET", "/v1/learner/solve-attempts", 422, token=lr.token, params={"status": "NOPE"})
    call(ctx, "list solve attempts limit 0 -> 422", "GET", "/v1/learner/solve-attempts", 422, token=lr.token, params={"limit": 0})
    call(ctx, "list solve attempts without a token -> 401", "GET", "/v1/learner/solve-attempts", 401)

    la = call(ctx, "list attempt outcomes", "GET", "/v1/learner/attempts", 200, token=lr.token,
              spec=[{"attempt_id": str, "is_correct": bool, "hint_count": int, "attempted_at": str, "source": str, "canonical_code": str}])
    if la.ok and isinstance(outcome, dict):
        mine = [a for a in la.data if a["attempt_id"] == outcome.get("attempt_id")]
        check(ctx, "attempt outcomes include the completed solve (source step_runtime, correct)",
              len(mine) == 1 and mine[0]["source"] == "step_runtime" and mine[0]["is_correct"] is True, f"matches={mine}")

    ms = call(ctx, "mastery summary", "GET", "/v1/learner/mastery", 200, token=lr.token,
              spec={"concepts": [{"slug": str, "name": str, "mastery_score": NUM, "attempts_count": int, "correct_count": int}],
                    "techniques": [{"slug": str, "name": str, "mastery_score": NUM, "attempts_count": int, "correct_count": int}]})
    if ms.ok:
        rows = ms.data["concepts"] + ms.data["techniques"]
        check(ctx, "mastery: tagged concepts/techniques updated by the completed solve", len(rows) >= 1 and all(r["attempts_count"] >= 1 for r in rows),
              f"rows={len(rows)}")
        check(ctx, "mastery: scores are within 0..1 and correct<=attempts",
              all(0 <= r["mastery_score"] <= 1 and r["correct_count"] <= r["attempts_count"] for r in rows), f"rows={rows[:3]}")
        check(ctx, "mastery: an all-independent solve scores > 0", any(r["mastery_score"] > 0 for r in rows), f"rows={rows[:3]}")
    ip = call(ctx, "mastery improvement plan", "GET", "/v1/learner/mastery/improvement-plan", 200, token=lr.token, params={"max_focus_areas": 2},
              spec={"student_id": str, "focus_areas": [{"kind": str, "slug": str, "name": str, "mastery_score": NUM, "tier": str,
                                                          "recommended_problems": list}]})
    if ip.ok:
        check(ctx, "improvement plan is for the caller and honours max_focus_areas",
              ip.data["student_id"] == lr.student_id and len(ip.data["focus_areas"]) <= 2, f"n={len(ip.data['focus_areas'])}")
    call(ctx, "improvement plan without a token -> 401", "GET", "/v1/learner/mastery/improvement-plan", 401)

    pp = call(ctx, "practice progress", "GET", "/v1/learner/practice-progress", 200, token=lr.token,
              spec={"items": [{"kind": str, "slug": str, "name": str, "available": int, "attempted": int, "remaining": int}]})
    if pp.ok:
        check(ctx, "practice progress: available = attempted + remaining for every theme",
              all(i["available"] == i["attempted"] + i["remaining"] for i in pp.data["items"]))
        check(ctx, "practice progress: the solved problem counts as attempted in at least one theme",
              any(i["attempted"] >= 1 for i in pp.data["items"]), "no theme has attempted >= 1 after a completed solve")

    ev = call(ctx, "learner events (newest first)", "GET", "/v1/learner/events", 200, token=lr.token,
              spec={"items": EVENT_SPEC, "limit": int, "next_token": OPT_STR}, leak=SECRET_KEYS | DIAGNOSIS_INTERNALS)
    if ev.ok and ev.data["items"]:
        items = ev.data["items"]
        times = [i["event_time"] for i in items]
        check(ctx, "events are newest first", times == sorted(times, reverse=True))
        types = {i["event_type"] for i in items}
        check(ctx, "events include the solve lifecycle", {"STEP_PRESENTED"} <= types, f"types={sorted(types)}")
        page = call(ctx, "learner events page of 2", "GET", "/v1/learner/events", 200, token=lr.token, params={"limit": 2, "attempt_id": aid})
        if page.ok:
            check(ctx, "events: attempt filter + limit honoured", len(page.data["items"]) <= 2
                  and all(e["solve_attempt_id"] == aid for e in page.data["items"]), f"n={len(page.data['items'])}")
            if page.data.get("next_token"):
                p2 = call(ctx, "learner events next page", "GET", "/v1/learner/events", 200, token=lr.token,
                          params={"limit": 2, "attempt_id": aid, "next_token": page.data["next_token"]})
                if p2.ok:
                    ids1 = {e["event_id"] for e in page.data["items"]}
                    check(ctx, "events: next page does not repeat the first page", not ids1 & {e["event_id"] for e in p2.data["items"]})
        oldest = sorted(times)[0]
        aft = call(ctx, "learner events after an instant (oldest first)", "GET", "/v1/learner/events", 200, token=lr.token,
                   params={"after": oldest, "limit": 50})
        if aft.ok:
            at = [e["event_time"] for e in aft.data["items"]]
            check(ctx, "events after: strictly later than the instant, oldest first", all(t > oldest for t in at) and at == sorted(at), f"{at[:3]}")
    call(ctx, "learner events limit 0 -> 422", "GET", "/v1/learner/events", 422, token=lr.token, params={"limit": 0})
    call(ctx, "learner events limit 501 -> 422", "GET", "/v1/learner/events", 422, token=lr.token, params={"limit": 501})
    old = call(ctx, "per-student events (legacy path)", "GET", f"/v1/students/{lr.student_id}/events", 200, spec=EVENT_SPEC, token=lr.token,
               leak=SECRET_KEYS | DIAGNOSIS_INTERNALS)
    if old.ok and ev.ok:
        check(ctx, "legacy events and /learner/events agree on the newest event",
              old.data and ev.data["items"] and old.data[0]["event_id"] == ev.data["items"][0]["event_id"])
    call(ctx, "events of another student id -> 403", "GET", f"/v1/students/{new_uuid()}/events", 403, token=lr.token)

    act = call(ctx, "daily activity", "GET", "/v1/learner/activity", 200, token=lr.token,
               spec={"items": [{"activity_date": str}], "total": int, "limit": int, "offset": int})
    if act.ok:
        check(ctx, "daily activity: counters are written by the learner-analytics stream consumer, not by the API", True,
              f"items after a completed solve = {len(act.data['items'])} (empty when no stream consumer is attached to mb-learner-test)")
    call(ctx, "daily activity from after to -> 422", "GET", "/v1/learner/activity", 422, token=lr.token,
         params={"from": "2026-11-03", "to": "2026-11-01"})
    call(ctx, "daily activity range over 366 days -> 422", "GET", "/v1/learner/activity", 422, token=lr.token,
         params={"from": "2024-01-01", "to": "2026-11-01"})
    call(ctx, "daily activity malformed date -> 422", "GET", "/v1/learner/activity", 422, token=lr.token, params={"from": "yesterday"})
    mc = call(ctx, "misconceptions", "GET", "/v1/learner/misconceptions", 200, token=lr.token, spec={"items": list, "total": int})
    if mc.ok:
        check(ctx, "misconceptions: total matches items", mc.data["total"] == len(mc.data["items"]))


@journey("learner_recovery")
def learner_recovery(ctx: Ctx) -> None:
    """Recovery detour: create, next item, answer items (MCQ graded deterministically), abort / resume, lists."""
    lr = register(ctx, "recovery")
    if lr is None:
        return
    st = start_solve(ctx, lr)
    if not st.ok:
        return
    aid = st.data["solve_attempt_id"]
    base = f"/v1/attempts/{aid}"
    sv = st.data["runtime"]["attempt"]["state_version"]
    call(ctx, "create recovery plan with a stale state_version -> 409", "POST", f"{base}/recovery-plans", 409, token=lr.token,
         json={"state_version": max(1, sv - 1), "trigger": "STUDENT_REQUEST"})
    call(ctx, "create recovery plan with an unknown trigger -> 422", "POST", f"{base}/recovery-plans", 422, token=lr.token,
         json={"state_version": sv, "trigger": "MAGIC"})
    pkey = new_uuid()
    cp = call(ctx, "create recovery plan", "POST", f"{base}/recovery-plans", 201, spec=PLAN_CREATE_SPEC, token=lr.token,
              json={"state_version": sv, "trigger": "STUDENT_REQUEST"}, headers={"Idempotency-Key": pkey},
              leak=SECRET_KEYS | ANSWER_KEYS)
    if not cp.ok:
        return
    plan = cp.data["recovery_plan"]
    pid, sv = plan["recovery_plan_id"], cp.data["state_version"]
    items = plan["items"]
    check(ctx, "plan: ACTIVE, first item presented, last stage returns to the step", plan["status"] == "ACTIVE"
          and items[0]["status"] == "PRESENTED" and items[-1]["stage"] == "RETURN_TO_STEP", f"status={plan['status']} stages={[i['stage'] for i in items]}")
    check(ctx, "plan: items are ordinal 1..n and only the first carries content", [i["ordinal"] for i in items] == list(range(1, len(items) + 1))
          and all("content" not in i for i in items[1:]))
    check(ctx, "plan: no answers or grader keys in any item", not find_keys(plan, ANSWER_KEYS | {"correct_choice", "answer"}),
          f"hits={find_keys(plan, ANSWER_KEYS)}")
    rt = get_runtime(ctx, lr, aid, "runtime during recovery")
    if rt.ok:
        check(ctx, "runtime: mode RECOVERY with the plan attached", rt.data["attempt"]["current_mode"] == "RECOVERY"
              and rt.data["attempt"]["current_recovery_plan_id"] == pid, f"attempt={rt.data['attempt']}")
        cur_step = rt.data["attempt"]["current_solution_step_id"]
        call(ctx, "submit the attempt while a recovery plan is active -> 409", "POST", f"{base}/submit", 409, token=lr.token, json={"state_version": sv})
        call(ctx, "save a step response while in RECOVERY -> 409", "POST", f"{base}/steps/{cur_step}/responses", 409, token=lr.token,
             json={"response_text": "answering the main step mid-detour", "state_version": sv, "evaluate": False})
        call(ctx, "request a hint while in RECOVERY -> 409", "POST", f"{base}/steps/{cur_step}/hint", 409, token=lr.token, json={"state_version": sv})
    again = call(ctx, "create recovery plan again while one is active (returns it, resumed)", "POST", f"{base}/recovery-plans", 201, token=lr.token,
                 json={"state_version": sv, "trigger": "STUDENT_REQUEST"})
    if again.ok:
        check(ctx, "second create: resumed=true, same plan", again.data["resumed"] is True and again.data["recovery_plan"]["recovery_plan_id"] == pid,
              f"resumed={again.data['resumed']}")
    rep = call(ctx, "create recovery plan replay (same Idempotency-Key)", "POST", f"{base}/recovery-plans", 201, token=lr.token,
               json={"state_version": cp.data["state_version"] - 1, "trigger": "STUDENT_REQUEST"}, headers={"Idempotency-Key": pkey})
    if rep.ok:
        check(ctx, "plan create replay: replayed=true, same plan", rep.data["replayed"] is True
              and rep.data["recovery_plan"]["recovery_plan_id"] == pid, f"replayed={rep.data['replayed']}")
    lst = call(ctx, "list recovery plans of the attempt", "GET", f"{base}/recovery-plans", 200, spec=[PLAN_SPEC], token=lr.token)
    if lst.ok:
        check(ctx, "plan list: exactly the one plan", [p["recovery_plan_id"] for p in lst.data] == [pid], f"ids={[p['recovery_plan_id'] for p in lst.data]}")
    gp = call(ctx, "get recovery plan", "GET", f"/v1/recovery-plans/{pid}", 200, spec=PLAN_SPEC, token=lr.token, leak=SECRET_KEYS | ANSWER_KEYS)
    nx = call(ctx, "next recovery item", "GET", f"/v1/recovery-plans/{pid}/next", 200, spec=NEXT_SPEC, token=lr.token, leak=SECRET_KEYS | ANSWER_KEYS)
    call(ctx, "get unknown recovery plan -> 404", "GET", f"/v1/recovery-plans/{new_uuid()}", 404, token=lr.token)
    call(ctx, "recovery plan without a token -> 401", "GET", f"/v1/recovery-plans/{pid}", 401)
    ap = call(ctx, "admin list recovery plans", "GET", "/v1/admin/recovery-plans", 200, admin=True, params={"student_id": lr.student_id})
    if ap.ok:
        check(ctx, "admin plan list contains the plan", any(p["recovery_plan_id"] == pid for p in ap.data), f"n={len(ap.data)}")
    call(ctx, "admin recovery plan detail", "GET", f"/v1/admin/recovery-plans/{pid}", 200, admin=True)
    call(ctx, "admin recovery plans with a learner token -> 401/403", "GET", "/v1/admin/recovery-plans", {401, 403}, token=lr.token)
    call(ctx, "admin recovery plan detail with a learner token -> 401/403", "GET", f"/v1/admin/recovery-plans/{pid}", {401, 403}, token=lr.token)
    if not (nx.ok and gp.ok):
        return

    # --- answer items: the worked example by acknowledging, MCQs by trying each option (the key is never shown)
    item = nx.data["item"]
    completed_by_answers = False
    probed: set[str] = set()
    for _ in range(30):
        if not item:
            break
        iid, kind, content = item["recovery_plan_item_id"], item["item_kind"], item.get("content") or {}
        answer_path = f"/v1/recovery-plans/{pid}/items/{iid}/responses"
        options = content.get("choices") or content.get("options")
        if kind != "THEORY" and not options:
            break
        if kind not in probed:
            probed.add(kind)
            call(ctx, f"answer a {kind} item with a stale state_version -> 409", "POST", answer_path, 409, token=lr.token,
                 json={"state_version": max(1, sv - 3), "acknowledged": True, "choice_index": 0})
            call(ctx, f"answer a {kind} item that is not the current one -> 4xx", "POST",
                 f"/v1/recovery-plans/{pid}/items/{new_uuid()}/responses", range(400, 500), token=lr.token,
                 json={"state_version": sv, "acknowledged": True, "choice_index": 0})
            if options:
                call(ctx, "answer an MCQ with an out-of-range choice_index -> 4xx", "POST", answer_path, range(400, 500), token=lr.token,
                     json={"state_version": sv, "choice_index": 99})
            empty = call(ctx, f"answer a {kind} item with an empty answer -> 4xx", "POST", answer_path, range(400, 500), token=lr.token,
                         json={"state_version": sv})
            if empty.status == 200:
                sv = empty.data["state_version"]
                n = call(ctx, "next recovery item", "GET", f"/v1/recovery-plans/{pid}/next", 200, spec=NEXT_SPEC, token=lr.token)
                if not n.ok:
                    return
                item = n.data["item"]
                continue
        body: dict = {"state_version": sv}
        if kind == "THEORY":
            body["acknowledged"] = True
        else:
            body["choice_index"] = item.get("tries", 0) % len(options)
        r = call(ctx, f"answer recovery item ({kind})", "POST", answer_path, 200, spec=ITEM_RESPONSE_SPEC,
                 token=lr.token, json=body, leak=SECRET_KEYS | ANSWER_KEYS)
        if not r.ok:
            return
        sv = r.data["state_version"]
        if r.data["recovery_plan"]["status"] != "ACTIVE":
            completed_by_answers = True
            break
        n = call(ctx, "next recovery item", "GET", f"/v1/recovery-plans/{pid}/next", 200, spec=NEXT_SPEC, token=lr.token, leak=SECRET_KEYS | ANSWER_KEYS)
        if not n.ok:
            return
        item = n.data["item"]
        if item and item["item_kind"] == "RETURN":
            break

    final = call(ctx, "get recovery plan after answering", "GET", f"/v1/recovery-plans/{pid}", 200, spec=PLAN_SPEC, token=lr.token)
    rt = get_runtime(ctx, lr, aid, "runtime after answering")
    if rt.ok:
        sv = rt.data["attempt"]["state_version"]
    if final.ok and final.data["can_return"]:
        res = call(ctx, "resume from a finished recovery plan", "POST", f"/v1/recovery-plans/{pid}/resume", 200, spec=LEAVE_SPEC, token=lr.token,
                   json={"state_version": sv})
        if res.ok:
            check(ctx, "resume: plan leaves ACTIVE and the learner returns to the origin step", res.data["plan_status"] != "ACTIVE"
                  and res.data["returned_to_step_id"] == plan["origin"]["solution_step_id"], f"data={res.data}")
            sv = res.data["state_version"]
    else:
        call(ctx, "resume an unfinished plan -> 409", "POST", f"/v1/recovery-plans/{pid}/resume", 409, token=lr.token, json={"state_version": sv})
        check(ctx, "recovery plan reached a finished state by answering", False,
              f"plan still {final.data['status'] if final.ok else '?'} after the answer loop (completed_by_answers={completed_by_answers})")
        ab = call(ctx, "abort the unfinished plan", "POST", f"/v1/recovery-plans/{pid}/abort", 200, spec=LEAVE_SPEC, token=lr.token,
                  json={"state_version": sv})
        if ab.ok:
            sv = ab.data["state_version"]

    # --- a second plan: abort path
    rt = get_runtime(ctx, lr, aid, "runtime before the second plan")
    if not rt.ok:
        return
    sv = rt.data["attempt"]["state_version"]
    cp2 = call(ctx, "create a second recovery plan", "POST", f"{base}/recovery-plans", 201, spec=PLAN_CREATE_SPEC, token=lr.token,
               json={"state_version": sv, "trigger": "STUDENT_REQUEST"})
    if not cp2.ok:
        return
    pid2, sv = cp2.data["recovery_plan"]["recovery_plan_id"], cp2.data["state_version"]
    check(ctx, "second plan is a new plan", pid2 != pid)
    call(ctx, "abort with a stale state_version -> 409", "POST", f"/v1/recovery-plans/{pid2}/abort", 409, token=lr.token, json={"state_version": max(1, sv - 5)})
    akey = new_uuid()
    ab = call(ctx, "abort the open plan", "POST", f"/v1/recovery-plans/{pid2}/abort", 200, spec=LEAVE_SPEC, token=lr.token, json={"state_version": sv},
              headers={"Idempotency-Key": akey})
    if ab.ok:
        check(ctx, "abort: plan ABORTED and back on the origin step", ab.data["plan_status"] == "ABORTED"
              and ab.data["returned_to_step_id"] == cp2.data["recovery_plan"]["origin"]["solution_step_id"], f"data={ab.data}")
        ab2 = call(ctx, "abort replay with the same Idempotency-Key", "POST", f"/v1/recovery-plans/{pid2}/abort", 200, token=lr.token,
                   json={"state_version": sv}, headers={"Idempotency-Key": akey})
        if ab2.ok:
            check(ctx, "abort replay: replayed=true", ab2.data["replayed"] is True, f"data={ab2.data}")
        call(ctx, "abort an already aborted plan -> 409", "POST", f"/v1/recovery-plans/{pid2}/abort", {409}, token=lr.token,
             json={"state_version": ab.data["state_version"]})
        call(ctx, "resume an aborted plan -> 409", "POST", f"/v1/recovery-plans/{pid2}/resume", 409, token=lr.token,
             json={"state_version": ab.data["state_version"]})
        done = get_runtime(ctx, lr, aid, "runtime after abort")
        if done.ok:
            check(ctx, "after abort: mode SOLVING again, no active plan", done.data["attempt"]["current_mode"] == "SOLVING"
                  and done.data["attempt"]["current_recovery_plan_id"] is None, f"attempt={done.data['attempt']}")
    lst = call(ctx, "list recovery plans (both)", "GET", f"{base}/recovery-plans", 200, spec=[PLAN_SPEC], token=lr.token)
    if lst.ok:
        check(ctx, "plan list: both plans, newest first", [p["recovery_plan_id"] for p in lst.data][:1] == [pid2] and len(lst.data) == 2,
              f"ids={[p['recovery_plan_id'] for p in lst.data]}")
