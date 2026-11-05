"""A full 20-question exam through the service credential and the learner bearer, on real DynamoDB: start -> generation events ->
finalize -> draft/progress -> interaction events -> respond (both routes) -> submit -> review -> diagnosis (versioned) -> mine / mastery."""
from __future__ import annotations

import time

from apitest.context import Ctx
from apitest.journeys import journey
from apitest.journeys.exam_common import (BASE, LEARNER_QUESTION_KEYS, QUIZ_KEYS, REVIEW_KEYS, call, check, content_fixtures, finalize, get_paper,
                                          good, js, marker, mcq, onboard, poll, qids, respond, scan, start_paper, svc, written)

WRITTEN = {15: "FREE_TEXT", 16: "FREE_TEXT", 17: "PROOF"}      # the only LLM-graded answers of this journey


def _mine_row(rows, qid):
    return next((r for r in rows or [] if r.get("quiz_id") == qid), None)


@journey("exam_paper_20q")
def exam_paper_20q(ctx: Ctx) -> None:
    me = onboard(ctx, "p20")
    if me is None:
        return
    sid, token = me.sid, me.token
    fx = content_fixtures(ctx)
    qid = start_paper(ctx, sid, count=20, types=["MCQ", "FREE_TEXT", "PROOF"], title="apitest 20q mock", target_concept_slugs=fx["concepts"][:2])
    if qid is None:
        return
    path = f"/papers/{qid}"

    # ---- the GENERATING shell: nothing can be answered, reviewed, submitted or diagnosed yet
    shell = get_paper(ctx, sid, qid, "shell: get paper")
    if good(shell):
        s = js(shell)
        check(ctx, "shell: GENERATING with no questions", s["status"] == "GENERATING" and s["questions"] == [] and QUIZ_KEYS <= set(s), str(s))
        check(ctx, "shell: exam_mode, time limit and instructions kept", s["exam_mode"] is True and s["time_limit_seconds"] == 3600
              and s["instructions"] == "apitest", str(s))
    learner_shell = call(ctx, "shell: learner get", "GET", f"/v1/quiz/{qid}", 200, token=token)
    check(ctx, "shell: learner and service views agree", good(shell) and good(learner_shell) and js(shell) == js(learner_shell), "views differ")
    some_question = "00000000-0000-4000-8000-000000000001"
    respond(ctx, sid, qid, some_question, {"selected_key": "A"}, "shell: respond", 409, code="EXAM_NOT_EDITABLE")
    svc(ctx, "shell: progress", "PUT", f"{path}/progress", 409, code="EXAM_NOT_EDITABLE", json={"student_id": sid, "current_question_ordinal": 1})
    svc(ctx, "shell: submit", "POST", f"{path}/submit", 409, code="EXAM_NOT_EDITABLE", params={"student_id": sid})
    svc(ctx, "shell: review", "GET", f"{path}/review", 409, code="EXAM_IN_PROGRESS", params={"student_id": sid})
    svc(ctx, "shell: diagnosis write", "POST", f"{path}/diagnosis", 409, code="NOT_GRADED",
        json={"student_id": sid, "time_management_verdict": "x", "generated_by": "apitest"})
    svc(ctx, "shell: diagnosis read", "GET", f"{path}/diagnosis", 404, code="NOT_FOUND", params={"student_id": sid})

    # ---- generation-events: post + get since an ordinal
    phases = ["INTAKE", "TOPIC_RESOLVE", "DIFFICULTY_SIGNAL", "POOL_LOOKUP", "DRAFT_QUESTION", "CRITIC_REVIEW", "DRAFT_QUESTION",
              "CRITIC_REVIEW", "AGGREGATE_DIVERSITY_CHECK", "AGGREGATE_FIX", "PERSIST", "DONE"]
    for i, phase in enumerate(phases, start=1):
        body = {"ordinal": i, "phase": phase, "status": "STARTED" if i % 2 else "DONE", "detail": f"step {i}"}
        if phase in ("DRAFT_QUESTION", "CRITIC_REVIEW"):
            body["question_ordinal"] = i - 3
        r = svc(ctx, f"generation event {i}", "POST", f"{path}/generation-events", 200, json=body)
        if i == 1 and good(r):
            check(ctx, "generation event answer", js(r) == {"ok": True}, str(js(r)))
    dup = svc(ctx, "generation event: duplicate ordinal is a no-op", "POST", f"{path}/generation-events", 200,
              json={"ordinal": 5, "phase": "PERSIST", "status": "FAILED", "detail": "SHOULD NOT REPLACE"})
    check(ctx, "duplicate ordinal answers ok", good(dup) and js(dup) == {"ok": True}, str(js(dup)))
    all_events = svc(ctx, "generation events since 0", "GET", f"{path}/generation-events", 200, params={"student_id": sid, "since_ordinal": 0})
    if good(all_events):
        ev = js(all_events)
        check(ctx, "events come back in ordinal order, all 12", [e["ordinal"] for e in ev] == list(range(1, 13)), str([e["ordinal"] for e in ev]))
        check(ctx, "event shape", {"ordinal", "phase", "status", "question_ordinal", "detail", "created_at"} <= set(ev[0]), str(ev[0]))
        fifth = next((e for e in ev if e["ordinal"] == 5), {})
        check(ctx, "the duplicate did not overwrite event 5", fifth.get("detail") == "step 5" and fifth.get("phase") == "DRAFT_QUESTION", str(fifth))
    tail = svc(ctx, "generation events since 9 (crosses 9 -> 10)", "GET", f"{path}/generation-events", 200, params={"student_id": sid, "since_ordinal": 9})
    check(ctx, "since_ordinal=9 returns 10..12", good(tail) and [e["ordinal"] for e in js(tail)] == [10, 11, 12], str(js(tail)))
    last = svc(ctx, "generation events since 12", "GET", f"{path}/generation-events", 200, params={"student_id": sid, "since_ordinal": 12})
    check(ctx, "since_ordinal=12 returns nothing", good(last) and js(last) == [], str(js(last)))
    svc(ctx, "generation event: bad phase", "POST", f"{path}/generation-events", 422, code="INVALID_PHASE",
        json={"ordinal": 20, "phase": "NOPE", "status": "DONE"})
    svc(ctx, "generation event: bad status", "POST", f"{path}/generation-events", 422, code="INVALID_STATUS",
        json={"ordinal": 20, "phase": "DONE", "status": "MAYBE"})
    svc(ctx, "generation event: ordinal 0", "POST", f"{path}/generation-events", 422, json={"ordinal": 0, "phase": "DONE", "status": "DONE"})
    svc(ctx, "generation event: detail too long", "POST", f"{path}/generation-events", 422,
        json={"ordinal": 21, "phase": "DONE", "status": "DONE", "detail": "x" * 501})
    svc(ctx, "generation event: unknown quiz", "POST", "/papers/00000000-0000-4000-8000-0000000000aa/generation-events", 404, code="NOT_FOUND",
        json={"ordinal": 1, "phase": "INTAKE", "status": "STARTED"})
    svc(ctx, "generation events: foreign student", "GET", f"{path}/generation-events", 404,
        params={"student_id": "00000000-0000-4000-8000-0000000000bb"})
    poll(ctx, "mine lists the GENERATING shell", "GET", f"{BASE}/papers/mine", lambda rows: (_mine_row(rows, qid) or {}).get("status") == "GENERATING",
         admin=True, params={"student_id": sid})

    # ---- finalize 20 questions (17 MCQ, 2 FREE_TEXT, 1 PROOF), a few tagged with real concepts / techniques / source problems
    questions = []
    for n in range(1, 21):
        q = written(ctx, n, WRITTEN[n]) if n in WRITTEN else mcq(ctx, n)
        if n <= 4 and fx["concepts"]:
            q["concept_slugs"] = fx["concepts"][:1]
        if n in (5, 6) and fx["techniques"]:
            q["technique_slugs"] = fx["techniques"][:1]
        if n in (1, 2) and fx["codes"]:
            q["inspiration_sources"] = [{"canonical_code": fx["codes"][0], "note": f"{marker(ctx)} borrowed"}]
        questions.append(q)
    fin = finalize(ctx, sid, qid, questions, case="finalize 20 questions")
    if not good(fin):
        return
    scan(ctx, "finalize response", fin)
    v = js(fin)
    ids = qids(fin)
    check(ctx, "finalize: READY with 20 ordered questions", v["status"] == "READY" and len(ids) == 20
          and [q["ordinal"] for q in v["questions"]] == list(range(1, 21)), f"{v['status']} {len(ids)}")
    check(ctx, "finalize: learner question allow-list", all(set(q) == LEARNER_QUESTION_KEYS for q in v["questions"]),
          str({k for q in v["questions"] for k in set(q) ^ LEARNER_QUESTION_KEYS}))
    check(ctx, "finalize: types preserved, options only on MCQ",
          all(q["question_type"] == WRITTEN.get(q["ordinal"], "MCQ") and (q["options"] is None) == (q["ordinal"] in WRITTEN)
              for q in v["questions"]), "type/options mismatch")
    check(ctx, "finalize: nothing answered yet", all(q["answered"] is False and q["student_response"] is None and q["draft_response"] is None
                                                      for q in v["questions"]), "answered/draft present")
    svc(ctx, "finalize again -> 404", "POST", f"{path}/finalize", 404, code="NOT_FOUND",
        json={"student_id": sid, "questions": questions[:1]})
    q = {n: ids[n - 1] for n in range(1, 21)}

    shell_get = get_paper(ctx, sid, qid, "get paper after finalize")
    scan(ctx, "get paper (service)", shell_get)
    lg = call(ctx, "learner get", "GET", f"/v1/quiz/{qid}", 200, token=token)
    scan(ctx, "get paper (learner)", lg)
    check(ctx, "service and learner views agree", good(shell_get) and good(lg) and js(shell_get) == js(lg), "views differ")
    for case, route, kw in (("mine (service)", f"{BASE}/papers/mine", {"admin": True, "params": {"student_id": sid}}),
                            ("mine (learner)", "/v1/quiz/mine", {"token": token})):
        scan(ctx, case, call(ctx, case, "GET", route, 200, **kw))

    # ---- draft + progress
    prog = svc(ctx, "progress with a draft", "PUT", f"{path}/progress", 200,
               json={"student_id": sid, "current_question_ordinal": 1, "question_id": q[1], "selected_key": "B"})
    check(ctx, "progress answer", good(prog) and js(prog) == {"saved": True, "current_question_ordinal": 1}, str(js(prog)))
    scan(ctx, "progress response", prog)
    svc(ctx, "progress: invalid MCQ key", "PUT", f"{path}/progress", 422, code="INVALID_DRAFT",
        json={"student_id": sid, "current_question_ordinal": 1, "selected_key": "Z"})
    svc(ctx, "progress: question_id of another ordinal", "PUT", f"{path}/progress", 422, code="INVALID_DRAFT",
        json={"student_id": sid, "current_question_ordinal": 1, "question_id": q[2], "selected_key": "A"})
    call(ctx, "learner progress: text draft for an MCQ", "PUT", f"/v1/quiz/{qid}/progress", 422, code="INVALID_DRAFT", token=token,
         json={"current_question_ordinal": 2, "response_text": "four"})
    svc(ctx, "progress: ordinal 21 is out of range", "PUT", f"{path}/progress", 422, json={"student_id": sid, "current_question_ordinal": 21})
    call(ctx, "learner progress: unknown field", "PUT", f"/v1/quiz/{qid}/progress", 422, token=token,
         json={"current_question_ordinal": 2, "bogus": 1})
    lp = call(ctx, "learner progress: text draft for FREE_TEXT", "PUT", f"/v1/quiz/{qid}/progress", 200, token=token,
              json={"current_question_ordinal": 15, "question_id": q[15], "response_text": "draft 30"})
    check(ctx, "learner progress answer", good(lp) and js(lp) == {"saved": True, "current_question_ordinal": 15}, str(js(lp)))
    mid = get_paper(ctx, sid, qid, "get paper with drafts")
    scan(ctx, "get paper with drafts", mid)
    if good(mid):
        m = js(mid)
        by = {x["ordinal"]: x for x in m["questions"]}
        check(ctx, "first progress moved the paper to IN_PROGRESS", m["status"] == "IN_PROGRESS" and m["started_at"] is not None, f"{m['status']} {m['started_at']}")
        check(ctx, "resume position is the last saved one", m["resume_question_ordinal"] == 15, str(m["resume_question_ordinal"]))
        check(ctx, "drafts are returned to the learner", by[1]["draft_response"] == {"selected_key": "B"} and by[15]["draft_response"] == {"response_text": "draft 30"}
              and by[1]["answered"] is False, str((by[1], by[15])))

    # ---- interaction events
    now_ms = int(time.time() * 1000)
    timeline = [(1, "VIEW", None, now_ms), (1, "SELECT_OPTION", "A", now_ms + 5), (1, "DESELECT_OPTION", "A", now_ms + 9),
                (1, "SELECT_OPTION", "B", now_ms + 12), (2, "VIEW", None, now_ms + 20), (15, "VIEW", None, None),
                (15, "TEXT_CHANGE", None, now_ms + 50), (2, "SKIP", None, now_ms + 8 * 86_400_000), (2, "VIEW", None, now_ms + 60)]
    for n, kind, key, ts in timeline:
        r = svc(ctx, f"event {kind} q{n}", "POST", f"{path}/questions/{q[n]}/events", 200,
                json={"student_id": sid, "event_type": kind, "option_key": key, "client_timestamp_ms": ts})
        if good(r):
            body = js(r)
            check(ctx, f"event {kind} answer", body.get("event_type") == kind and body.get("option_key") == key and body.get("event_id"), str(body))
    svc(ctx, "event: unknown type", "POST", f"{path}/questions/{q[1]}/events", 422, code="INVALID_EVENT_TYPE",
        json={"student_id": sid, "event_type": "NOPE"})
    svc(ctx, "event: option_key too long", "POST", f"{path}/questions/{q[1]}/events", 422,
        json={"student_id": sid, "event_type": "SELECT_OPTION", "option_key": "K" * 11})
    svc(ctx, "event: unknown question", "POST", f"{path}/questions/00000000-0000-4000-8000-0000000000cc/events", 404, code="NOT_FOUND",
        json={"student_id": sid, "event_type": "VIEW"})
    evs = svc(ctx, "get events", "GET", f"{path}/events", 200, params={"student_id": sid})
    scan(ctx, "events", evs)
    if good(evs):
        e = js(evs)
        check(ctx, "events: all posted, oldest first, in posting order", [x["event_type"] for x in e] == [t[1] for t in timeline],
              str([x["event_type"] for x in e]))
        check(ctx, "events: created_at never goes backwards", [x["created_at"] for x in e] == sorted(x["created_at"] for x in e), "unsorted")
        skew = next((x for x in e if x["event_type"] == "SKIP"), {})
        check(ctx, "events: a client clock 8 days off is not trusted (stored null)", skew.get("client_timestamp_ms") is None, str(skew))
        check(ctx, "events: a sane client clock is kept", e[1]["client_timestamp_ms"] == now_ms + 5, str(e[1]))
    after_skip = get_paper(ctx, sid, qid, "get paper after SKIP")
    if good(after_skip):
        check(ctx, "SKIP leaves the other drafts alone", next(x for x in js(after_skip)["questions"] if x["ordinal"] == 1)["draft_response"] == {"selected_key": "B"},
              "draft of q1 vanished")

    # ---- respond: alternate the service and the learner route; the exam body never carries correctness
    mcq_correct, count = 0, 0
    mid_mine_checked = False
    for n in range(1, 21):
        body = {"response_text": f"{2 * n}", "time_spent_seconds": 10 + n} if n in WRITTEN else {"selected_key": "B" if n % 3 else "A", "time_spent_seconds": 10 + n}
        if n not in WRITTEN and n % 3:
            mcq_correct += 1
        r = respond(ctx, sid, qid, q[n], body, f"respond q{n} ({'learner' if n % 2 == 0 else 'service'})", 200, token=token if n % 2 == 0 else None)
        count += 1
        if good(r):
            scan(ctx, f"respond q{n}", r)
            check(ctx, f"respond q{n}: exam body is just saved/question_id/answered_count",
                  js(r) == {"saved": True, "question_id": q[n], "answered_count": count}, str(js(r)))
        if n == 1 and good(r):
            respond(ctx, sid, qid, q[1], {"selected_key": "A"}, "duplicate respond (service)", 409, code="ALREADY_ANSWERED")
            respond(ctx, sid, qid, q[1], {"selected_key": "A"}, "duplicate respond (learner)", 409, code="ALREADY_ANSWERED", token=token)
            svc(ctx, "progress draft on an answered question", "PUT", f"{path}/progress", 409, code="ALREADY_ANSWERED",
                json={"student_id": sid, "current_question_ordinal": 1, "selected_key": "A"})
            row = None
            for _ in range(8):                           # GSI1 is eventually consistent: wait for the IN_PROGRESS row, then judge it
                rows = js(ctx.api.call("GET", "/v1/quiz/mine", token=token)[0]) or []
                row = _mine_row(rows, qid)
                if row and row.get("status") == "IN_PROGRESS":
                    break
                time.sleep(0.6)
            if row and row.get("status") == "IN_PROGRESS" and not mid_mine_checked:
                mid_mine_checked = True
                check(ctx, "LEAK: /v1/quiz/mine hides correct_count while the exam is open (the answer was correct)",
                      not row.get("correct_count"), f"correct_count={row.get('correct_count')} after one correct answer: {row}")
            elif not mid_mine_checked:
                check(ctx, "mine row reached IN_PROGRESS", False, str(row))
        if n == 15 and good(r):
            check(ctx, "LLM-graded answer in an exam is saved without grading detail", set(js(r)) == {"saved", "question_id", "answered_count"}, str(js(r)))
    call(ctx, "respond: empty body", "POST", f"/v1/quiz/{qid}/questions/{q[3]}/respond", 422, token=token, json={})
    call(ctx, "respond: negative time_spent", "POST", f"{BASE}/papers/{qid}/questions/{q[3]}/respond", 422, admin=True,
         json={"student_id": sid, "selected_key": "A", "time_spent_seconds": -1})
    done = get_paper(ctx, sid, qid, "get paper, all answered")
    scan(ctx, "get paper, all answered", done)
    if good(done):
        d = js(done)
        check(ctx, "an exam stays IN_PROGRESS until it is submitted (no auto-grade)", d["status"] == "IN_PROGRESS", d["status"])
        check(ctx, "all 20 are answered and drafts are gone", all(x["answered"] and x["student_response"] and x["draft_response"] is None
                                                                   for x in d["questions"]), "answered/draft mismatch")
    for case, route, kw in (("review before submit (service)", f"{path}/review", {"admin": True, "params": {"student_id": sid}}),
                            ("review before submit (learner)", f"/v1/quiz/{qid}/review", {"token": token})):
        r = call(ctx, case, "GET", route if route.startswith("/v1/quiz/") else f"{BASE}{route}", 409, code="EXAM_IN_PROGRESS", **kw)
        check(ctx, f"{case}: refusal carries no secret", r is not None and marker(ctx) not in r.text, "marker in refusal")
    di = svc(ctx, "diagnosis-input while open", "GET", f"{path}/diagnosis-input", 200, params={"student_id": sid})
    if good(di):
        check(ctx, "diagnosis-input has all 20 questions", len(js(di)["questions"]) == 20, str(len(js(di)["questions"])))

    # ---- submit and review
    sub = svc(ctx, "submit", "POST", f"{path}/submit", 200, params={"student_id": sid})
    if not good(sub):
        return
    review = js(sub)
    check(ctx, "submit returns the review", REVIEW_KEYS <= set(review) and review["total"] == 20 and review["answered_count"] == 20, str(sorted(review)))
    check(ctx, "score = every correct MCQ (+ at most the 3 LLM-graded)", mcq_correct <= review["score"] <= mcq_correct + 3,
          f"score {review['score']} vs {mcq_correct} correct MCQ")
    rq = {x["ordinal"]: x for x in review["questions"]}
    check(ctx, "review is ordered by ordinal", [x["ordinal"] for x in review["questions"]] == list(range(1, 21)), "unordered")
    check(ctx, "review: MCQ correctness matches what was answered",
          all(rq[n]["is_correct"] is bool(n % 3) for n in range(1, 21) if n not in WRITTEN), str({n: rq[n]["is_correct"] for n in rq if n not in WRITTEN}))
    check(ctx, "review releases the key after submit", all(marker(ctx) in (rq[n]["solution_text"] or "") for n in rq)
          and rq[1]["correct_answer"] == {"correct_key": "B"} and rq[1]["solution_steps"] == ["add", "check"], str(rq[1]))
    check(ctx, "review: written answers were graded by the LLM", all(rq[n]["is_correct"] in (True, False) for n in WRITTEN), str([rq[n]["is_correct"] for n in WRITTEN]))
    if fx["codes"]:
        src = (rq[1]["inspiration_sources"] or [{}])[0]
        check(ctx, "review: inspiration source resolved against the corpus", src.get("canonical_code") == fx["codes"][0] and src.get("competition")
              and src.get("year") and "source_url" in src, str(rq[1]["inspiration_sources"]))
    svc(ctx, "submit twice", "POST", f"{path}/submit", 409, code="ALREADY_SUBMITTED", params={"student_id": sid})
    respond(ctx, sid, qid, q[2], {"selected_key": "A"}, "respond after submit (answered question)", 409, code="ALREADY_ANSWERED")
    svc(ctx, "progress after submit", "PUT", f"{path}/progress", 409, code="EXAM_NOT_EDITABLE", json={"student_id": sid, "current_question_ordinal": 3})
    svc(ctx, "generation event after submit", "POST", f"{path}/generation-events", 409, code="EXAM_NOT_EDITABLE",
        json={"ordinal": 50, "phase": "DONE", "status": "DONE"})
    rv = svc(ctx, "review (service)", "GET", f"{path}/review", 200, params={"student_id": sid})
    lrv = call(ctx, "review (learner)", "GET", f"/v1/quiz/{qid}/review", 200, token=token)
    check(ctx, "service and learner reviews agree and equal the submit body", good(rv) and good(lrv) and js(rv) == js(lrv) == review, "reviews differ")
    final = get_paper(ctx, sid, qid, "get paper after submit")
    check(ctx, "paper is GRADED after submit", good(final) and js(final)["status"] == "GRADED", str(js(final)))
    scan(ctx, "get paper after submit", final)

    # ---- diagnosis: versioned history, latest wins
    di = svc(ctx, "diagnosis-input after submit", "GET", f"{path}/diagnosis-input", 200, params={"student_id": sid})
    if good(di):
        d = js(di)
        dq = {x["ordinal"]: x for x in d["questions"]}
        check(ctx, "diagnosis-input: per-question correctness and timing", all(dq[n]["is_correct"] is bool(n % 3) and dq[n]["time_spent_seconds"] == 10 + n
                                                                              for n in range(1, 21) if n not in WRITTEN), "mismatch")
        check(ctx, "diagnosis-input: submitted_at set, mastery maps present", d["submitted_at"] and isinstance(d["concept_mastery_pre_exam"], dict)
              and isinstance(d["technique_mastery_pre_exam"], dict), str({k: d.get(k) for k in ("submitted_at",)}))
        if fx["concepts"]:
            check(ctx, "diagnosis-input: concept tag round-trips as a slug", dq[1]["concept_slugs"] == fx["concepts"][:1], str(dq[1]["concept_slugs"]))
        if fx["techniques"]:
            check(ctx, "diagnosis-input: technique tag round-trips as a slug", dq[5]["technique_slugs"] == fx["techniques"][:1], str(dq[5]["technique_slugs"]))
    svc(ctx, "diagnosis: empty verdict", "POST", f"{path}/diagnosis", 422,
        json={"student_id": sid, "time_management_verdict": "", "generated_by": "apitest"})
    call(ctx, "learner diagnosis before any", "GET", f"/v1/quiz/{qid}/diagnosis", 404, token=token, code="NOT_FOUND")
    for version in (1, 2):
        w = svc(ctx, f"write diagnosis v{version}", "POST", f"{path}/diagnosis", 200, json={
            "student_id": sid, "time_management_verdict": f"verdict v{version}", "generated_by": "apitest-agent",
            "pacing_notes": [{"question_ordinal": 1, "note": f"fast v{version}"}], "reasoning_guidance": [{"question_ordinal": 2, "guidance": "g"}],
            "improvement_areas": [{"concept": "x", "why": "y"}]})
        if good(w):
            check(ctx, f"diagnosis v{version} answer is the latest", js(w).get("time_management_verdict") == f"verdict v{version}"
                  and js(w).get("pacing_notes") == [{"question_ordinal": 1, "note": f"fast v{version}"}], str(js(w)))
        g = svc(ctx, f"read diagnosis after v{version}", "GET", f"{path}/diagnosis", 200, params={"student_id": sid})
        check(ctx, f"diagnosis read returns v{version}", good(g) and js(g)["time_management_verdict"] == f"verdict v{version}", str(js(g)))
    lg = call(ctx, "learner reads the diagnosis", "GET", f"/v1/quiz/{qid}/diagnosis", 200, token=token)
    check(ctx, "learner diagnosis is the latest version", good(lg) and js(lg)["time_management_verdict"] == "verdict v2", str(js(lg)))

    # ---- lists and learner state
    score = review["score"]
    poll(ctx, "mine shows GRADED with the score", "GET", f"{BASE}/papers/mine",
         lambda rows: (_mine_row(rows, qid) or {}).get("status") == "GRADED" and (_mine_row(rows, qid) or {}).get("correct_count") == score
         and (_mine_row(rows, qid) or {}).get("question_count") == 20, admin=True, params={"student_id": sid})
    lim = svc(ctx, "papers/mine limit=1", "GET", "/papers/mine", 200, params={"student_id": sid, "limit": 1})
    check(ctx, "limit is honoured", good(lim) and len(js(lim)) == 1, str(js(lim)))
    ms = svc(ctx, "mastery-summary after the exam", "GET", f"/students/{sid}/mastery-summary", 200)
    if good(ms) and fx["concepts"]:
        slugs = {c.get("slug") for c in js(ms)["concepts"]}
        check(ctx, "inline mastery recompute recorded the tagged concept", fx["concepts"][0] in slugs, f"concepts in summary: {sorted(slugs)}")
