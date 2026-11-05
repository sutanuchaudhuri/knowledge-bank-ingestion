"""The learner-bearer quiz routes (/v1/quiz/*): generate (LLM-backed, called once), mine, get, progress, respond, review, diagnosis —
on an exam paper imported by the service and on a practice quiz the learner generates."""
from __future__ import annotations

from apitest.context import Ctx
from apitest.journeys import journey
from apitest.journeys.exam_common import call, check, good, import_paper, js, marker, mcq, poll, qids, register, scan, svc

PRACTICE_ALLOWED = frozenset({"is_correct", "feedback", "solution", "solution_text", "key_insight"})     # a practice respond discloses by design


def _in(rows, qid):
    return any(r.get("quiz_id") == qid for r in rows or [])


@journey("exam_quiz_learner")
def exam_quiz_learner(ctx: Ctx) -> None:
    me = register(ctx, "quizlearner")
    if me is None:
        return
    sid, token = me.sid, me.token

    # ---- request validation and credentials of generate (no LLM is reached by any of these)
    call(ctx, "generate: unknown style", "POST", "/v1/quiz/generate", 422, code="INVALID_STYLE", token=token, json={"style": "NOPE"})
    call(ctx, "generate: unknown question type", "POST", "/v1/quiz/generate", 422, code="INVALID_QUESTION_TYPE", token=token,
         json={"style": "AIME", "question_types": ["ESSAY"]})
    call(ctx, "generate: 21 questions", "POST", "/v1/quiz/generate", 422, token=token, json={"style": "AIME", "question_count": 21})
    call(ctx, "generate: unknown field", "POST", "/v1/quiz/generate", 422, token=token, json={"style": "AIME", "student_id": sid})
    call(ctx, "generate: no credentials", "POST", "/v1/quiz/generate", {401, 403}, json={"style": "AIME"})

    # ---- an exam paper, seen through the learner routes (QUZ-E08 diagnosis, QUZ-E09 progress)
    imp = import_paper(ctx, sid, [mcq(ctx, n) for n in range(1, 4)], case="import exam for the learner", title="apitest learner exam")
    if good(imp):
        qid, ids = js(imp)["quiz_id"], qids(imp)
        poll(ctx, "learner mine lists the exam", "GET", "/v1/quiz/mine", lambda rows: _in(rows, qid), token=token)
        got = call(ctx, "learner get exam", "GET", f"/v1/quiz/{qid}", 200, token=token)
        scan(ctx, "learner get exam", got)
        check(ctx, "learner view of an exam", good(got) and js(got)["exam_mode"] is True and js(got)["status"] == "READY" and len(js(got)["questions"]) == 3, str(js(got)))
        p = call(ctx, "learner progress with a draft", "PUT", f"/v1/quiz/{qid}/progress", 200, token=token,
                 json={"current_question_ordinal": 1, "question_id": ids[0], "selected_key": "C"})
        scan(ctx, "learner progress", p)
        check(ctx, "learner progress answer", good(p) and js(p) == {"saved": True, "current_question_ordinal": 1}, str(js(p)))
        g2 = call(ctx, "learner get shows the draft", "GET", f"/v1/quiz/{qid}", 200, token=token)
        check(ctx, "draft visible to its learner only through draft_response", good(g2) and js(g2)["questions"][0]["draft_response"] == {"selected_key": "C"}
              and js(g2)["status"] == "IN_PROGRESS", str(js(g2) and js(g2)["questions"][0]))
        r = call(ctx, "learner respond in an exam", "POST", f"/v1/quiz/{qid}/questions/{ids[0]}/respond", 200, token=token, json={"selected_key": "B"})
        scan(ctx, "learner respond in an exam", r)
        check(ctx, "exam respond hides correctness", good(r) and js(r) == {"saved": True, "question_id": ids[0], "answered_count": 1}, str(js(r)))
        call(ctx, "learner respond again", "POST", f"/v1/quiz/{qid}/questions/{ids[0]}/respond", 409, code="ALREADY_ANSWERED", token=token, json={"selected_key": "A"})
        rv = call(ctx, "learner review before submit", "GET", f"/v1/quiz/{qid}/review", 409, code="EXAM_IN_PROGRESS", token=token)
        check(ctx, "refusal carries no secret", rv is not None and marker(ctx) not in rv.text, "marker in body")
        call(ctx, "learner diagnosis before submit", "GET", f"/v1/quiz/{qid}/diagnosis", 404, code="NOT_FOUND", token=token)
        svc(ctx, "service submits", "POST", f"/papers/{qid}/submit", 200, params={"student_id": sid})
        rv = call(ctx, "learner review after submit", "GET", f"/v1/quiz/{qid}/review", 200, token=token)
        check(ctx, "learner review is complete", good(rv) and js(rv)["total"] == 3 and js(rv)["answered_count"] == 1 and js(rv)["score"] == 1
              and js(rv)["questions"][2]["student_response"] is None, str(js(rv) and {k: js(rv)[k] for k in ("total", "answered_count", "score")}))
        svc(ctx, "service writes a diagnosis", "POST", f"/papers/{qid}/diagnosis", 200,
            json={"student_id": sid, "time_management_verdict": "learner can read this", "generated_by": "apitest"})
        d = call(ctx, "learner diagnosis", "GET", f"/v1/quiz/{qid}/diagnosis", 200, token=token)
        check(ctx, "learner diagnosis shape", good(d) and {"quiz_id", "time_management_verdict", "pacing_notes", "reasoning_guidance", "improvement_areas",
                                                          "generated_by", "created_at"} <= set(js(d)), str(js(d)))
        call(ctx, "learner progress after submit", "PUT", f"/v1/quiz/{qid}/progress", 409, code="EXAM_NOT_EDITABLE", token=token,
             json={"current_question_ordinal": 2})

    # ---- practice quiz: one real LLM-backed generate (2 MCQ), answered through the learner routes
    gen = call(ctx, "generate a practice quiz (LLM)", "POST", "/v1/quiz/generate", 200, token=token,
               json={"style": "AIME", "question_count": 2, "question_types": ["MCQ"]})
    if not good(gen):
        return
    scan(ctx, "generate response", gen)
    quiz = js(gen)
    pid, pids = quiz["quiz_id"], qids(gen)
    check(ctx, "generate: a READY practice quiz of the requested size", quiz["status"] == "READY" and quiz["exam_mode"] is False and len(pids) == 2, str({k: quiz[k] for k in ("status", "exam_mode")}))
    check(ctx, "generate: MCQ questions carry options", all(q["question_type"] == "MCQ" and q["options"] for q in quiz["questions"]), str(quiz["questions"][:1]))
    poll(ctx, "mine lists the practice quiz", "GET", "/v1/quiz/mine", lambda rows: _in(rows, pid), token=token)
    got = call(ctx, "get the practice quiz", "GET", f"/v1/quiz/{pid}", 200, token=token)
    scan(ctx, "get the practice quiz", got)
    call(ctx, "progress on a practice quiz", "PUT", f"/v1/quiz/{pid}/progress", 200, token=token, json={"current_question_ordinal": 2})
    first = quiz["questions"][0]["options"][0]["key"]
    r = call(ctx, "practice respond q1", "POST", f"/v1/quiz/{pid}/questions/{pids[0]}/respond", 200, token=token, json={"selected_key": first})
    if good(r):
        scan(ctx, "practice respond (by-design disclosure only)", r, allow=PRACTICE_ALLOWED)
        b = js(r)
        check(ctx, "practice respond: grading + solution, no key table", {"is_correct", "grading_method", "confidence", "feedback", "solution"} == set(b)
              and set(b["solution"]) == {"solution_text", "key_insight"}, str(sorted(b)))
    call(ctx, "practice respond again", "POST", f"/v1/quiz/{pid}/questions/{pids[0]}/respond", 409, code="ALREADY_ANSWERED", token=token, json={"selected_key": first})
    rv = call(ctx, "practice review while open", "GET", f"/v1/quiz/{pid}/review", 200, token=token)
    check(ctx, "a practice review is open before the last answer", good(rv) and js(rv)["answered_count"] == 1 and js(rv)["total"] == 2, str(js(rv)))
    call(ctx, "practice respond q2", "POST", f"/v1/quiz/{pid}/questions/{pids[1]}/respond", 200, token=token, json={"selected_key": first})
    done = call(ctx, "practice quiz after the last answer", "GET", f"/v1/quiz/{pid}", 200, token=token)
    check(ctx, "a practice quiz is GRADED once every question is answered", good(done) and js(done)["status"] == "GRADED", str(js(done) and js(done)["status"]))
    call(ctx, "practice progress after GRADED", "PUT", f"/v1/quiz/{pid}/progress", 409, code="EXAM_NOT_EDITABLE", token=token, json={"current_question_ordinal": 1})
    call(ctx, "practice diagnosis before any", "GET", f"/v1/quiz/{pid}/diagnosis", 404, code="NOT_FOUND", token=token)
    svc(ctx, "diagnosis on a graded practice quiz", "POST", f"/papers/{pid}/diagnosis", 200,
        json={"student_id": sid, "time_management_verdict": "practice ok", "generated_by": "apitest"})
    call(ctx, "practice diagnosis", "GET", f"/v1/quiz/{pid}/diagnosis", 200, token=token)
    poll(ctx, "mine reports the graded practice quiz", "GET", "/v1/quiz/mine",
         lambda rows: any(r["quiz_id"] == pid and r["status"] == "GRADED" and r["question_count"] == 2 for r in rows), token=token)
