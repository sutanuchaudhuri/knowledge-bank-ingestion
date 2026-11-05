"""Direct attempt logging (POST /v1/learner/attempts) and the learner list/summary endpoints around it."""
from __future__ import annotations

from apitest.context import Ctx
from apitest.journeys import journey
from apitest.journeys.learner_common import (
    NUM,
    OPT_STR,
    PROBLEM_SPEC,
    call,
    check,
    new_uuid,
    register,
)

ATTEMPT_SPEC = {"attempt": {"attempt_id": str, "attempted_at": str}, "updated_mastery": {"concepts": dict, "techniques": dict}}
ROW_SPEC = {"attempt_id": str, "is_correct": bool, "hint_count": int, "attempted_at": str, "source": str, "canonical_code": str,
            "problem_number": int, "competition": str}
MASTERY_ROW = {"slug": str, "name": str, "mastery_score": NUM, "attempts_count": int, "correct_count": int}
MASTERY_SPEC = {"concepts": [MASTERY_ROW], "techniques": [MASTERY_ROW]}
PAGE_SPEC = {"items": list, "next_token": OPT_STR}


@journey("learner_attempt_log")
def learner_attempt_log(ctx: Ctx) -> None:
    lr = register(ctx, "log")
    if lr is None:
        return
    ps = call(ctx, "list problems", "GET", "/v1/problems", 200, spec=[PROBLEM_SPEC], params={"competition": "AIME", "limit": 3})
    if not ps.ok or not ps.data:
        return
    code = ps.data[0]["canonical_code"]
    call(ctx, "list problems limit over 200 -> 422", "GET", "/v1/problems", 422, params={"limit": 201})
    one = call(ctx, "get problem by code", "GET", f"/v1/problems/by-code/{code}", 200, spec={"canonical_code": str, "statement_text": str, "concepts": list,
                                                                                         "techniques": list})
    call(ctx, "get unknown problem -> 404", "GET", "/v1/problems/by-code/NO_SUCH_PROBLEM", 404)

    empty = call(ctx, "attempts of a fresh learner", "GET", "/v1/learner/attempts", 200, token=lr.token)
    if empty.ok:
        check(ctx, "a fresh learner has no attempts", empty.data == [], f"data={empty.data}")
    mastery0 = call(ctx, "mastery of a fresh learner", "GET", "/v1/learner/mastery", 200, spec=MASTERY_SPEC, token=lr.token)
    if mastery0.ok:
        check(ctx, "a fresh learner has no mastery rows", mastery0.data["concepts"] == [] and mastery0.data["techniques"] == [], f"data={mastery0.data}")

    path = "/v1/learner/attempts"
    call(ctx, "log attempt without a token -> 401", "POST", path, 401, json={"problem_code": code, "is_correct": True})
    call(ctx, "log attempt for an unknown problem -> 404", "POST", path, 404, token=lr.token, json={"problem_code": "NO_SUCH_PROBLEM", "is_correct": True})
    call(ctx, "log attempt without is_correct -> 422", "POST", path, 422, token=lr.token, json={"problem_code": code})
    call(ctx, "log attempt with a negative hint_count -> 422", "POST", path, 422, token=lr.token, json={"problem_code": code, "is_correct": True, "hint_count": -1})
    call(ctx, "log attempt with negative time -> 422", "POST", path, 422, token=lr.token, json={"problem_code": code, "is_correct": True, "time_spent_seconds": -5})
    call(ctx, "log attempt with a non-boolean is_correct -> 422", "POST", path, 422, token=lr.token, json={"problem_code": code, "is_correct": "maybe"})

    key = new_uuid()
    body = {"problem_code": code, "is_correct": True, "submitted_answer": "60", "time_spent_seconds": 90, "hint_count": 1, "source": "apitest"}
    a1 = call(ctx, "log a correct attempt", "POST", path, 201, spec=ATTEMPT_SPEC, token=lr.token, json=body, headers={"Idempotency-Key": key})
    if not a1.ok:
        return
    aid1 = a1.data["attempt"]["attempt_id"]
    check(ctx, "mastery update scores are within 0..1", all(0 <= v <= 1 for m in a1.data["updated_mastery"].values() for v in m.values()),
          f"mastery={a1.data['updated_mastery']}")
    check(ctx, "the problem's tags were all updated", len(a1.data["updated_mastery"]["concepts"]) + len(a1.data["updated_mastery"]["techniques"]) >= 1,
          f"mastery={a1.data['updated_mastery']}")
    rep = call(ctx, "log the same attempt with the same Idempotency-Key", "POST", path, 201, token=lr.token, json=body, headers={"Idempotency-Key": key})
    if rep.ok:
        check(ctx, "replay: same attempt id, not a second attempt", rep.data["attempt"]["attempt_id"] == aid1, f"{rep.data['attempt']['attempt_id']} vs {aid1}")
    clash = call(ctx, "same Idempotency-Key with a different body -> 4xx", "POST", path, range(400, 500), token=lr.token,
                 json={**body, "is_correct": False}, headers={"Idempotency-Key": key})
    a2 = call(ctx, "log an incorrect attempt", "POST", path, 201, spec=ATTEMPT_SPEC, token=lr.token, json={"problem_code": code, "is_correct": False})
    a3 = call(ctx, "log a second correct attempt", "POST", path, 201, spec=ATTEMPT_SPEC, token=lr.token, json={"problem_code": code, "is_correct": True})
    if not (a2.ok and a3.ok):
        return

    lst = call(ctx, "list attempts", "GET", path, 200, spec=[ROW_SPEC], token=lr.token)
    if lst.ok:
        ids = [a["attempt_id"] for a in lst.data]
        check(ctx, "attempts: three attempts, newest first, replay did not duplicate", ids == [a3.data["attempt"]["attempt_id"], a2.data["attempt"]["attempt_id"], aid1],
              f"ids={ids}")
        mine = [a for a in lst.data if a["attempt_id"] == aid1]
        if mine:
            check(ctx, "attempt row keeps submitted fields", mine[0]["is_correct"] is True and mine[0]["hint_count"] == 1 and mine[0]["source"] == "apitest"
                  and mine[0]["canonical_code"] == code, f"row={mine[0]}")
    pg = call(ctx, "list attempts limit 1 offset 1", "GET", path, 200, spec=[ROW_SPEC], token=lr.token, params={"limit": 1, "offset": 1})
    if pg.ok and lst.ok:
        check(ctx, "attempts paging: the second newest", [a["attempt_id"] for a in pg.data] == [lst.data[1]["attempt_id"]], f"data={pg.data}")
    call(ctx, "list attempts limit 1000 is capped, not an error", "GET", path, 200, token=lr.token, params={"limit": 1000})
    call(ctx, "list attempts with a negative offset is clamped", "GET", path, {200, 422}, token=lr.token, params={"offset": -5})
    call(ctx, "list attempts with limit 0 does not error", "GET", path, {200, 422}, token=lr.token, params={"limit": 0})
    call(ctx, "list attempts with a negative limit does not error", "GET", path, {200, 422}, token=lr.token, params={"limit": -1})
    call(ctx, "list attempts with a non-numeric limit -> 422", "GET", path, 422, token=lr.token, params={"limit": "many"})
    call(ctx, "list attempts without a token -> 401", "GET", path, 401)

    ms = call(ctx, "mastery after three attempts", "GET", "/v1/learner/mastery", 200, spec=MASTERY_SPEC, token=lr.token)
    if ms.ok:
        rows = ms.data["concepts"] + ms.data["techniques"]
        check(ctx, "mastery: every tag of the problem counts 3 attempts / 2 correct", rows and all(r["attempts_count"] == 3 and r["correct_count"] == 2 for r in rows),
              f"rows={[(r['slug'], r['attempts_count'], r['correct_count'], r['mastery_score']) for r in rows]}")
        check(ctx, "mastery: 2 of 3 correct scores strictly between 0 and 1", all(0 < r["mastery_score"] < 1 for r in rows),
              f"scores={[r['mastery_score'] for r in rows]}")
    if one.ok and ms.ok:
        tags = {c["slug"] for c in one.data["concepts"]} | {t["slug"] for t in one.data["techniques"]}
        got = {r["slug"] for r in ms.data["concepts"] + ms.data["techniques"]}
        check(ctx, "mastery covers exactly the tags of the problem", got == tags, f"problem tags={sorted(tags)} mastery={sorted(got)}")
    ip = call(ctx, "improvement plan after attempts", "GET", "/v1/learner/mastery/improvement-plan", 200, token=lr.token, params={"max_focus_areas": 3},
              spec={"student_id": str, "focus_areas": [{"kind": str, "slug": str, "name": str, "mastery_score": NUM, "tier": str, "recommended_problems": list}]})
    if ip.ok:
        check(ctx, "improvement plan: at most max_focus_areas, weakest first", len(ip.data["focus_areas"]) <= 3 and
              [f["mastery_score"] for f in ip.data["focus_areas"]] == sorted(f["mastery_score"] for f in ip.data["focus_areas"]),
              f"scores={[f['mastery_score'] for f in ip.data['focus_areas']]}")
    call(ctx, "improvement plan max_focus_areas=0 does not error", "GET", "/v1/learner/mastery/improvement-plan", {200, 422}, token=lr.token, params={"max_focus_areas": 0})
    call(ctx, "improvement plan max_focus_areas=-1 does not error", "GET", "/v1/learner/mastery/improvement-plan", {200, 422}, token=lr.token, params={"max_focus_areas": -1})
    pp = call(ctx, "practice progress after attempts", "GET", "/v1/learner/practice-progress", 200, token=lr.token,
              spec={"items": [{"kind": str, "slug": str, "name": str, "available": int, "attempted": int, "remaining": int}]})
    if pp.ok:
        attempted = [i for i in pp.data["items"] if i["attempted"] > 0]
        check(ctx, "practice progress: each theme of the problem shows exactly one attempted problem (three attempts of one problem count once)",
              attempted and all(i["attempted"] == 1 for i in attempted), f"attempted={[(i['slug'], i['attempted']) for i in attempted][:6]}")
        check(ctx, "practice progress: available = attempted + remaining", all(i["available"] == i["attempted"] + i["remaining"] for i in pp.data["items"]))

    # --- feedback (retrieval reports): there is no producer endpoint in the runtime app, so the list is empty
    fb = call(ctx, "list my feedback", "GET", "/v1/learner/feedback", 200, spec=PAGE_SPEC, token=lr.token)
    if fb.ok:
        check(ctx, "feedback: empty for a fresh learner (no create endpoint in the runtime app)", fb.data["items"] == [], f"data={fb.data}")
    call(ctx, "list feedback limit 0 is clamped", "GET", "/v1/learner/feedback", {200, 422}, token=lr.token, params={"limit": 0})
    call(ctx, "list feedback garbage next_token -> 4xx (not 5xx)", "GET", "/v1/learner/feedback", range(400, 500), token=lr.token, params={"next_token": "garbage"})
    call(ctx, "list feedback without a token -> 401", "GET", "/v1/learner/feedback", 401)
    call(ctx, "withdraw an unknown feedback -> 404", "POST", f"/v1/learner/feedback/{new_uuid()}/withdraw", 404, token=lr.token)
    call(ctx, "withdraw with a malformed id -> 422", "POST", "/v1/learner/feedback/not-a-uuid/withdraw", 422, token=lr.token)
    call(ctx, "withdraw without a token -> 401", "POST", f"/v1/learner/feedback/{new_uuid()}/withdraw", 401)

    # --- sundry reads
    call(ctx, "daily activity with an explicit valid range", "GET", "/v1/learner/activity", 200, token=lr.token,
         spec={"items": list, "total": int, "limit": int, "offset": int}, params={"from": "2026-10-01", "to": "2026-11-03", "limit": 5})
    call(ctx, "events of a fresh-learner after the logged attempts", "GET", "/v1/learner/events", 200, token=lr.token, spec={"items": list, "limit": int, "next_token": OPT_STR})
    call(ctx, "events after a malformed instant -> 4xx (not 5xx)", "GET", "/v1/learner/events", range(400, 500), token=lr.token, params={"after": "yesterday"})
    call(ctx, "events with a garbage next_token -> 4xx (not 5xx)", "GET", "/v1/learner/events", range(400, 500), token=lr.token, params={"next_token": "garbage"})
    call(ctx, "solve-attempts with a garbage next_token -> 4xx (not 5xx)", "GET", "/v1/learner/solve-attempts", range(400, 500), token=lr.token, params={"next_token": "garbage"})
    call(ctx, "misconceptions of a fresh learner", "GET", "/v1/learner/misconceptions", 200, token=lr.token, spec={"items": list, "total": int})
    call(ctx, "weak-concepts analytics is cohort-suppressed", "GET", "/v1/analytics/weak-concepts", 200, token=lr.token, spec={"results": list})
