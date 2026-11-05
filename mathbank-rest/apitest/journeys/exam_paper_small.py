"""A small exam through the one-call import route (POST /papers), left partly unanswered: validation without stray shells, the
terminal-state refusals (EXAM_NOT_EDITABLE vs ALREADY_ANSWERED), unanswered rows in the review, three diagnosis versions."""
from __future__ import annotations

from apitest.context import Ctx
from apitest.journeys import journey
from apitest.journeys.exam_common import (BASE, call, check, get_paper, good, import_paper, js, marker, mcq, onboard, paper_body, poll, qids,
                                          respond, scan, svc)


@journey("exam_paper_small")
def exam_paper_small(ctx: Ctx) -> None:
    me = onboard(ctx, "small")
    if me is None:
        return
    sid, token = me.sid, me.token

    def mine_ids() -> list[str]:
        r = ctx.api.call("GET", f"{BASE}/papers/mine", admin=True, params={"student_id": sid})[0]
        return [x["quiz_id"] for x in js(r)] if r is not None and r.status_code == 200 else []

    # ---- import-time validation: nothing may be left behind
    base = {**paper_body(sid, count=2), "questions": [mcq(ctx, 1), mcq(ctx, 2)]}
    svc(ctx, "import: unknown style", "POST", "/papers", 422, code="INVALID_STYLE", json={**base, "style": "NOPE"})
    svc(ctx, "import: question count 21", "POST", "/papers", 422, json={**base, "requested_question_count": 21})
    svc(ctx, "import: no questions", "POST", "/papers", 422, json={**base, "questions": []})
    svc(ctx, "import: 21 questions", "POST", "/papers", 422, json={**base, "questions": [mcq(ctx, i) for i in range(21)]})
    svc(ctx, "import: bad paper difficulty band", "POST", "/papers", 422, code="INVALID_DIFFICULTY_BAND", json={**base, "difficulty_band": "extreme"})
    svc(ctx, "import: time limit 59s", "POST", "/papers", 422, json={**base, "time_limit_seconds": 59})
    svc(ctx, "import: unknown top-level field", "POST", "/papers", 422, json={**base, "role": "admin"})
    svc(ctx, "import: unknown student", "POST", "/papers", 404, code="NOT_FOUND", json={**base, "student_id": "00000000-0000-4000-8000-0000000000dd"})
    svc(ctx, "import: question without a correct_answer", "POST", "/papers", 422,
        json={**base, "questions": [{k: v for k, v in mcq(ctx, 1).items() if k != "correct_answer"}]})
    before = mine_ids()
    svc(ctx, "import: unknown question type", "POST", "/papers", 422, code="INVALID_QUESTION_TYPE",
        json={**base, "questions": [mcq(ctx, 1, question_type="ESSAY")]})
    svc(ctx, "import: unknown question difficulty band", "POST", "/papers", 422, code="INVALID_DIFFICULTY_BAND",
        json={**base, "questions": [mcq(ctx, 1, difficulty_band="legendary")]})
    after = poll(ctx, "mine after the refused imports", "GET", f"{BASE}/papers/mine", lambda rows: True, admin=True, params={"student_id": sid})
    stray = [x for x in after or [] if x["quiz_id"] not in before]
    check(ctx, "refused import leaves no GENERATING shell behind (docstring: 'no stray GENERATING shell')", not stray,
          f"{len(stray)} stray paper(s) after two refused imports: {[(s['status'], s['title']) for s in stray]}")

    # ---- the paper: 4 MCQ, answer 2, leave 2
    questions = [mcq(ctx, n) for n in range(1, 5)]
    imp = import_paper(ctx, sid, questions, case="import 4-question paper", title="apitest small", time_limit_seconds=600)
    if not good(imp):
        return
    scan(ctx, "import response", imp)
    v = js(imp)
    qid, ids = v["quiz_id"], qids(imp)
    path = f"/papers/{qid}"
    check(ctx, "import: READY with 4 questions", v["status"] == "READY" and len(ids) == 4 and v["time_limit_seconds"] == 600, str(v["status"]))
    check(ctx, "no progress yet: no resume position, not started", v["resume_question_ordinal"] in (None, 0, 1) and v["started_at"] is None,
          f"{v['resume_question_ordinal']} {v['started_at']}")

    svc(ctx, "progress: ordinal with no question", "PUT", f"{path}/progress", 404, code="NOT_FOUND", json={"student_id": sid, "current_question_ordinal": 9})
    p = svc(ctx, "progress without a draft", "PUT", f"{path}/progress", 200, json={"student_id": sid, "current_question_ordinal": 2})
    check(ctx, "progress answer", good(p) and js(p) == {"saved": True, "current_question_ordinal": 2}, str(js(p)))
    g = get_paper(ctx, sid, qid, "get after progress")
    check(ctx, "IN_PROGRESS with resume ordinal 2 and started_at", good(g) and js(g)["status"] == "IN_PROGRESS" and js(g)["resume_question_ordinal"] == 2
          and js(g)["started_at"], str(js(g) and {k: js(g)[k] for k in ("status", "resume_question_ordinal", "started_at")}))
    started_at = js(g)["started_at"] if good(g) else None
    svc(ctx, "progress again (started_at must not move)", "PUT", f"{path}/progress", 200, json={"student_id": sid, "current_question_ordinal": 3})
    g2 = get_paper(ctx, sid, qid, "get after second progress")
    check(ctx, "started_at is set once", good(g2) and js(g2)["started_at"] == started_at and js(g2)["resume_question_ordinal"] == 3, str(js(g2) and js(g2)["started_at"]))

    r = respond(ctx, sid, qid, ids[0], {"selected_key": "B"}, "respond q1 (correct)", 200)
    check(ctx, "respond answer", good(r) and js(r) == {"saved": True, "question_id": ids[0], "answered_count": 1}, str(js(r)))
    r = respond(ctx, sid, qid, ids[1], {"selected_key": "A"}, "respond q2 (wrong)", 200, token=token)
    check(ctx, "second respond counts", good(r) and js(r)["answered_count"] == 2, str(js(r)))
    bogus = respond(ctx, sid, qid, ids[2], {"selected_key": "ZZ"}, "respond with a key that is not an option", {200, 422})
    if bogus is not None and bogus.status_code == 200:
        check(ctx, "an answer that is not one of the options is refused (drafts are validated the same way)", False,
              "POST respond selected_key='ZZ' on a 3-option MCQ was accepted and graded wrong; PUT progress rejects the same value with INVALID_DRAFT")
    respond(ctx, sid, qid, "00000000-0000-4000-8000-0000000000ee", {"selected_key": "A"}, "respond: unknown question", 404, code="NOT_FOUND")

    ans_after = 3 if bogus is not None and bogus.status_code == 200 else 2
    svc(ctx, "diagnosis while open", "POST", f"{path}/diagnosis", 409, code="NOT_GRADED",
        json={"student_id": sid, "time_management_verdict": "x", "generated_by": "apitest"})
    fail_open = svc(ctx, "fail on a READY/IN_PROGRESS paper changes nothing", "POST", f"{path}/fail", 200,
                    json={"student_id": sid, "error_message": "late failure"})
    check(ctx, "fail on an open paper keeps its status", good(fail_open) and js(fail_open)["status"] == "IN_PROGRESS", str(js(fail_open) and js(fail_open)["status"]))

    sub = svc(ctx, "submit with unanswered questions", "POST", f"{path}/submit", 200, params={"student_id": sid})
    if not good(sub):
        return
    rv = js(sub)
    rows = {x["ordinal"]: x for x in rv["questions"]}
    check(ctx, "review: totals", rv["total"] == 4 and rv["answered_count"] == ans_after and rv["score"] == 1, str({k: rv[k] for k in ("total", "answered_count", "score")}))
    check(ctx, "review: answered rows graded, unanswered rows empty",
          rows[1]["is_correct"] is True and rows[2]["is_correct"] is False and rows[4]["student_response"] is None and rows[4]["is_correct"] is None
          and rows[4]["correct_answer"] == {"correct_key": "B"}, str(rows[4]))
    check(ctx, "review: option explanations released after submit", marker(ctx) in " ".join(rows[1]["option_explanations"].values()), str(rows[1]["option_explanations"]))

    # an unanswered question can no longer be answered once the exam is submitted
    respond(ctx, sid, qid, ids[3], {"selected_key": "B"}, "respond to an unanswered question after submit", 409, code="EXAM_NOT_EDITABLE")
    respond(ctx, sid, qid, ids[3], {"selected_key": "B"}, "respond (learner) to an unanswered question after submit", 409, code="EXAM_NOT_EDITABLE", token=token)
    respond(ctx, sid, qid, ids[0], {"selected_key": "A"}, "respond to an answered question after submit", 409, code="ALREADY_ANSWERED")
    svc(ctx, "progress after submit", "PUT", f"{path}/progress", 409, code="EXAM_NOT_EDITABLE", json={"student_id": sid, "current_question_ordinal": 1})
    call(ctx, "learner progress after submit", "PUT", f"/v1/quiz/{qid}/progress", 409, code="EXAM_NOT_EDITABLE", token=token, json={"current_question_ordinal": 1})
    svc(ctx, "fail after submit changes nothing", "POST", f"{path}/fail", 200, json={"student_id": sid, "error_message": "too late"})
    late = get_paper(ctx, sid, qid, "get after late fail")
    check(ctx, "paper is still GRADED after a late fail", good(late) and js(late)["status"] == "GRADED", str(js(late) and js(late)["status"]))
    svc(ctx, "finalize a submitted paper", "POST", f"{path}/finalize", 404, code="NOT_FOUND", json={"student_id": sid, "questions": [mcq(ctx, 9)]})

    # ---- diagnosis history: every write is a new version, reads return the latest
    for n in (1, 2, 3):
        w = svc(ctx, f"diagnosis write #{n}", "POST", f"{path}/diagnosis", 200,
                json={"student_id": sid, "time_management_verdict": f"v{n}", "generated_by": f"agent-{n}", "pacing_notes": [{"n": n}]})
        check(ctx, f"diagnosis #{n} echo", good(w) and js(w)["time_management_verdict"] == f"v{n}" and js(w)["generated_by"] == f"agent-{n}", str(js(w)))
    last = svc(ctx, "diagnosis latest", "GET", f"{path}/diagnosis", 200, params={"student_id": sid})
    check(ctx, "latest diagnosis is #3", good(last) and js(last)["time_management_verdict"] == "v3" and js(last)["pacing_notes"] == [{"n": 3}], str(js(last)))
    ll = call(ctx, "learner diagnosis latest", "GET", f"/v1/quiz/{qid}/diagnosis", 200, token=token)
    check(ctx, "learner sees the same diagnosis", good(ll) and good(last) and js(ll) == js(last), "differs")

    # ---- an untouched READY paper: fail does nothing, diagnosis refused, mine ordering and limit
    ready = import_paper(ctx, sid, [mcq(ctx, 7)], case="import 1-question paper")
    if good(ready):
        rid = js(ready)["quiz_id"]
        f = svc(ctx, "fail a READY paper", "POST", f"/papers/{rid}/fail", 200, json={"student_id": sid, "error_message": "nope"})
        check(ctx, "fail leaves a READY paper READY", good(f) and js(f)["status"] == "READY", str(js(f) and js(f)["status"]))
        svc(ctx, "diagnosis on a READY paper", "POST", f"/papers/{rid}/diagnosis", 409, code="NOT_GRADED",
            json={"student_id": sid, "time_management_verdict": "x", "generated_by": "apitest"})
        poll(ctx, "mine: newest first", "GET", f"{BASE}/papers/mine", lambda rows: [x["quiz_id"] for x in rows][:2] == [rid, qid], admin=True, params={"student_id": sid})
        two = svc(ctx, "mine limit=1", "GET", "/papers/mine", 200, params={"student_id": sid, "limit": 1})
        check(ctx, "limit=1 returns one paper", good(two) and len(js(two)) == 1, str(js(two)))
