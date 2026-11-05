"""Edge payloads the exam agent can really send: minimal questions (only the required fields), unicode / LaTeX round trips, the 10 000
character draft limit, an oversized solution (DynamoDB item limit) and an MCQ with many options."""
from __future__ import annotations

from apitest.context import Ctx
from apitest.journeys import journey
from apitest.journeys.exam_common import (check, finalize, get_paper, good, import_paper, js, marker, mcq, onboard, qids, scan, start_paper, status_of, svc)

TEXT = "Prove that ∑_{k=1}^{n} k = n(n+1)/2 — 日本語 עברית 🧮 \"quotes\" 'single' \\ backslash\nnew line\ttab"
LATEX = r"\sum_{k=1}^{n} k = \frac{n(n+1)}{2}"


@journey("exam_edge_cases")
def exam_edge_cases(ctx: Ctx) -> None:
    me = onboard(ctx, "edge")
    if me is None:
        return
    sid = me.sid
    m = marker(ctx)

    # ---- minimal questions: only the required fields of ImportQuestion
    minimal = [
        {"question_type": "MCQ", "prompt_text": f"[{ctx.run_id}] minimal mcq", "options": [{"key": "A", "text": "1"}, {"key": "B", "text": "2"}],
         "correct_answer": {"correct_key": "B"}, "solution_text": f"{m} s"},
        {"question_type": "FREE_TEXT", "prompt_text": f"[{ctx.run_id}] minimal free text", "correct_answer": {}, "solution_text": f"{m} s"},
        {"question_type": "PROOF", "prompt_text": f"[{ctx.run_id}] minimal proof", "correct_answer": {"grading_rubric": f"{m} r"}, "solution_text": f"{m} s"},
    ]
    imp = svc(ctx, "import minimal questions", "POST", "/papers", 200, json={
        "student_id": sid, "style": "MIXED", "title": "apitest minimal", "requested_question_count": 3,
        "requested_question_types": ["MCQ", "FREE_TEXT", "PROOF"], "generated_by": "apitest", "questions": minimal})
    if good(imp):
        scan(ctx, "minimal import", imp)
        v = js(imp)
        check(ctx, "minimal paper: READY, no time limit, 3 questions", v["status"] == "READY" and v["time_limit_seconds"] is None and len(v["questions"]) == 3, str(v["status"]))
        sub = svc(ctx, "submit the minimal paper", "POST", f"/papers/{v['quiz_id']}/submit", 200, params={"student_id": sid})
        if good(sub):
            rows = js(sub)["questions"]
            check(ctx, "minimal review: defaults filled in, nothing null that a client iterates", all(r["solution_steps"] == [] and r["option_explanations"] == {} and
                                                                                                    isinstance(r["inspiration_sources"], list) for r in rows), str(rows[0]))

    # ---- unicode / LaTeX must round-trip byte for byte, in the learner view and in the review
    q = mcq(ctx, 3, prompt_text=f"[{ctx.run_id}] {TEXT}", prompt_latex=LATEX,
            options=[{"key": "A", "text": "∅"}, {"key": "B", "text": "\\{1,2\\}"}, {"key": "C", "text": "日本"}], solution_text=f"{m} {TEXT}")
    imp = import_paper(ctx, sid, [q], case="import unicode question", title="apitest ünïcödé ✓")
    if good(imp):
        v = js(imp)
        got = v["questions"][0]
        check(ctx, "unicode title round-trips", v["title"] == "apitest ünïcödé ✓", v["title"])
        check(ctx, "unicode / LaTeX prompt and options round-trip exactly",
              got["prompt_text"] == q["prompt_text"] and got["prompt_latex"] == LATEX and got["options"] == q["options"], f"{got['prompt_text']!r} {got['prompt_latex']!r}")
        sub = svc(ctx, "submit the unicode paper", "POST", f"/papers/{v['quiz_id']}/submit", 200, params={"student_id": sid})
        if good(sub):
            check(ctx, "unicode solution round-trips in the review", js(sub)["questions"][0]["solution_text"] == q["solution_text"], "differs")

    # ---- the draft limits
    long_q = [mcq(ctx, 1), {**mcq(ctx, 2), "question_type": "PROOF", "options": None, "correct_answer": {"grading_rubric": f"{m} r"}, "option_explanations": {}}]
    imp = import_paper(ctx, sid, long_q, case="import for draft limits", title="apitest drafts")
    if good(imp):
        qid, ids = js(imp)["quiz_id"], qids(imp)
        path = f"/papers/{qid}/progress"
        ok = svc(ctx, "draft of exactly 10000 characters", "PUT", path, 200,
                 json={"student_id": sid, "current_question_ordinal": 2, "question_id": ids[1], "response_text": "é" * 10000})
        scan(ctx, "10000-char draft", ok)
        svc(ctx, "draft of 10001 characters", "PUT", path, 422, json={"student_id": sid, "current_question_ordinal": 2, "response_text": "x" * 10001})
        g = get_paper(ctx, sid, qid, "get with the long draft")
        if good(g):
            check(ctx, "the long draft is returned intact", js(g)["questions"][1]["draft_response"] == {"response_text": "é" * 10000}, "draft differs")
        svc(ctx, "both selected_key and response_text on an MCQ", "PUT", path, 422, code="INVALID_DRAFT",
            json={"student_id": sid, "current_question_ordinal": 1, "selected_key": "A", "response_text": "x"})

    # ---- many options
    wide = mcq(ctx, 4, options=[{"key": chr(65 + i), "text": f"option {i}"} for i in range(26)], correct_answer={"correct_key": "Z"})
    r = import_paper(ctx, sid, [wide], case="import a 26-option MCQ", title="apitest wide")
    if good(r):
        check(ctx, "26 options are stored", len(js(r)["questions"][0]["options"]) == 26, "options lost")

    # ---- shapes the agent legitimately sends that the typed item models might not know (option E, extra revision-log / answer-key keys)
    five = mcq(ctx, 6, options=[{"key": k, "text": f"opt {k}"} for k in "ABCDE"], correct_answer={"correct_key": "E"},
               option_explanations={k: f"{m} why {k}" for k in "ABCDE"})
    r = import_paper(ctx, sid, [five], case="import a 5-option MCQ with an explanation per option", title="apitest five options")
    if good(r):
        sub = svc(ctx, "submit the 5-option paper", "POST", f"/papers/{js(r)['quiz_id']}/submit", 200, params={"student_id": sid})
        if good(sub):
            check(ctx, "all five option explanations survive", set(js(sub)["questions"][0]["option_explanations"]) == set("ABCDE"),
                  str(js(sub)["questions"][0]["option_explanations"]))
    import_paper(ctx, sid, [mcq(ctx, 7, revision_log=[{"round": 1, "verdict": "APPROVE", "feedback": "ok", "critic": "gpt", "scores": {"clarity": 5}}])],
                 case="import a revision log with extra keys", title="apitest revision log")
    import_paper(ctx, sid, [mcq(ctx, 8, correct_answer={"correct_key": "B", "confidence": 0.9})], case="import an answer key with an extra field",
                 title="apitest answer key")

    # ---- an oversized solution: DynamoDB items are limited to 400 KB, so this is a client error that must be refused cleanly
    qid = start_paper(ctx, sid, count=1, case="start (oversized question)")
    if qid is not None:
        big = finalize(ctx, sid, qid, [mcq(ctx, 5, solution_text=f"{m} " + "x" * 450_000)], case="finalize: 450 KB solution", status={200, 413, 422})
        state = status_of(ctx, sid, qid)
        if big is not None and big.status_code in (413, 422):
            check(ctx, "a refused oversized finalize leaves the shell GENERATING", state == "GENERATING", f"state {state}")
        elif big is not None and big.status_code >= 500:
            check(ctx, "an oversized question (client error) must not destroy the paper", state == "GENERATING", f"HTTP {big.status_code}, paper is now {state}")
