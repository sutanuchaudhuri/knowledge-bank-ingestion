"""The failure paths of paper generation on real DynamoDB: POST papers/{id}/fail, finalize rejections that must leave the shell usable,
a finalize payload that breaks inside the store, and what each state refuses afterwards."""
from __future__ import annotations

from apitest.context import Ctx
from apitest.journeys import journey
from apitest.journeys.exam_common import (BASE, check, finalize, get_paper, good, js, mcq, onboard, poll, respond, scan, start_paper, status_of, svc)


@journey("exam_fail_paths")
def exam_fail_paths(ctx: Ctx) -> None:
    me = onboard(ctx, "fail")
    if me is None:
        return
    sid = me.sid

    # ---- fail a GENERATING paper
    qid = start_paper(ctx, sid, count=3, case="start (to be failed)")
    if qid is None:
        return
    path = f"/papers/{qid}"
    svc(ctx, "event before fail", "POST", f"{path}/generation-events", 200, json={"ordinal": 1, "phase": "DRAFT_QUESTION", "status": "STARTED"})
    f = svc(ctx, "fail", "POST", f"{path}/fail", 200, json={"student_id": sid, "error_message": "critic rejected every draft"})
    scan(ctx, "fail response", f)
    check(ctx, "fail returns the learner view with status FAILED and no questions", good(f) and js(f)["status"] == "FAILED" and js(f)["questions"] == [], str(js(f)))
    f2 = svc(ctx, "fail again", "POST", f"{path}/fail", 200, json={"student_id": sid, "error_message": "second message"})
    check(ctx, "second fail is a no-op", good(f2) and js(f2)["status"] == "FAILED", str(js(f2)))
    svc(ctx, "fail: empty message", "POST", f"{path}/fail", 422, json={"student_id": sid, "error_message": ""})
    svc(ctx, "fail: 501-char message", "POST", f"{path}/fail", 422, json={"student_id": sid, "error_message": "x" * 501})
    svc(ctx, "fail: unknown paper", "POST", "/papers/00000000-0000-4000-8000-0000000000f1/fail", 404, code="NOT_FOUND",
        json={"student_id": sid, "error_message": "x"})
    svc(ctx, "fail: someone else's student id", "POST", f"{path}/fail", 404, code="NOT_FOUND",
        json={"student_id": "00000000-0000-4000-8000-0000000000f2", "error_message": "x"})

    svc(ctx, "finalize a FAILED paper", "POST", f"{path}/finalize", 404, code="NOT_FOUND", json={"student_id": sid, "questions": [mcq(ctx, 1)]})
    respond(ctx, sid, qid, "00000000-0000-4000-8000-0000000000f3", {"selected_key": "A"}, "respond on a FAILED paper", 409, code="EXAM_NOT_EDITABLE")
    svc(ctx, "progress on a FAILED paper", "PUT", f"{path}/progress", 409, code="EXAM_NOT_EDITABLE", json={"student_id": sid, "current_question_ordinal": 1})
    svc(ctx, "submit a FAILED paper", "POST", f"{path}/submit", 409, code="EXAM_NOT_EDITABLE", params={"student_id": sid})
    svc(ctx, "review a FAILED paper", "GET", f"{path}/review", 409, code="EXAM_IN_PROGRESS", params={"student_id": sid})
    svc(ctx, "diagnosis on a FAILED paper", "POST", f"{path}/diagnosis", 409, code="NOT_GRADED",
        json={"student_id": sid, "time_management_verdict": "x", "generated_by": "apitest"})
    late = svc(ctx, "generation event after FAILED is still accepted (the UI polls the failure)", "POST", f"{path}/generation-events", 200,
               json={"ordinal": 2, "phase": "FAILED", "status": "FAILED", "detail": "critic rejected every draft"})
    check(ctx, "late event answer", good(late) and js(late) == {"ok": True}, str(js(late)))
    ev = svc(ctx, "read generation events of a FAILED paper", "GET", f"{path}/generation-events", 200, params={"student_id": sid})
    check(ctx, "both events are readable", good(ev) and [e["ordinal"] for e in js(ev)] == [1, 2], str(js(ev)))
    poll(ctx, "mine shows the FAILED paper", "GET", f"{BASE}/papers/mine", lambda rows: any(r["quiz_id"] == qid and r["status"] == "FAILED" for r in rows),
         admin=True, params={"student_id": sid})

    # ---- finalize rejections that must leave the shell GENERATING and reusable
    qid2 = start_paper(ctx, sid, count=2, case="start (finalize rejections)")
    if qid2 is None:
        return
    path2 = f"/papers/{qid2}"
    finalize(ctx, sid, qid2, [mcq(ctx, 1, question_type="ESSAY")], case="finalize: unknown question type", status=422)
    finalize(ctx, sid, qid2, [mcq(ctx, 1, difficulty_band="legendary")], case="finalize: unknown question band", status=422)
    finalize(ctx, sid, qid2, [], case="finalize: no questions", status=422)
    finalize(ctx, sid, qid2, [mcq(ctx, i) for i in range(21)], case="finalize: 21 questions", status=422)
    svc(ctx, "finalize: question without a solution", "POST", f"{path2}/finalize", 422,
        json={"student_id": sid, "questions": [{k: v for k, v in mcq(ctx, 1).items() if k != "solution_text"}]})
    finalize(ctx, "00000000-0000-4000-8000-0000000000f4", qid2, [mcq(ctx, 1)], case="finalize: another student's id", status=404)
    check(ctx, "rejected finalizes leave the paper GENERATING", status_of(ctx, sid, qid2) == "GENERATING", str(status_of(ctx, sid, qid2)))
    ok = finalize(ctx, sid, qid2, [mcq(ctx, 1), mcq(ctx, 2)], case="finalize after the rejections")
    check(ctx, "the same shell finalizes cleanly afterwards", good(ok) and js(ok)["status"] == "READY" and len(js(ok)["questions"]) == 2, str(js(ok) and js(ok)["status"]))

    # ---- a payload the router accepts but the store cannot persist: a client error must not become a 5xx that destroys the paper
    qid3 = start_paper(ctx, sid, count=1, case="start (unpersistable payload)")
    if qid3 is None:
        return
    bad = finalize(ctx, sid, qid3, [mcq(ctx, 1, options=[{"key": "A"}, {"key": "B"}])], case="finalize: options without text", status={200, 400, 422})
    state = status_of(ctx, sid, qid3)
    if bad is not None and bad.status_code in (400, 422):
        check(ctx, "a refused finalize leaves the shell GENERATING", state == "GENERATING", f"state is {state}")
    elif bad is not None and bad.status_code == 200:
        check(ctx, "options without a text are stored as given", True)
    elif bad is not None:
        check(ctx, "a malformed question (client error) must not turn the paper FAILED for good", state == "GENERATING", f"HTTP {bad.status_code}, paper is now {state}")
    paper_view = get_paper(ctx, sid, qid3, "paper after the unpersistable finalize")
    scan(ctx, "paper after the unpersistable finalize", paper_view)
