"""Races on real DynamoDB (threads, one barrier per wave): duplicate respond, parallel respond on different questions, parallel finalize,
parallel progress (+ respond), duplicate generation-event ordinals, parallel submit / diagnosis, respond-vs-submit.

A 5xx anywhere is a failure by construction (the expected sets below never contain one); every other outcome is judged afterwards on the
final stored state, so a lost write or a double count shows up even when every individual status looked plausible."""
from __future__ import annotations

import collections
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from apitest.context import Ctx
from apitest.journeys import journey
from apitest.journeys.exam_common import BASE, check, code_of, get_paper, good, import_paper, js, mcq, onboard, qids, scan, start_paper, svc


def fan(n: int, fn: Callable[[int], object]) -> list:
    """Run fn(0..n-1) on n threads released together."""
    barrier = threading.Barrier(n)

    def run(i: int):
        barrier.wait()
        return fn(i)

    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(run, range(n)))


def codes(rs) -> collections.Counter:
    return collections.Counter((r.status_code if r is not None else None, code_of(r) if r is not None else None) for r in rs)


def _respond_as(ctx: Ctx, me, qid: str, question_id: str, key: str, case: str, i: int = 0, ok=frozenset({200, 409})):
    """Even workers use the service route, odd ones the learner bearer route."""
    if i % 2:
        return ctx.api.expect(case, "POST", f"/v1/quiz/{qid}/questions/{question_id}/respond", set(ok), token=me.token, json={"selected_key": key})
    return ctx.api.expect(case, "POST", f"{BASE}/papers/{qid}/questions/{question_id}/respond", set(ok), admin=True,
                          json={"student_id": me.sid, "selected_key": key})


def _mine(ctx: Ctx, me, qid: str) -> dict:
    rows = js(ctx.api.call("GET", f"{BASE}/papers/mine", admin=True, params={"student_id": me.sid})[0]) or []
    return next((r for r in rows if r["quiz_id"] == qid), {})


@journey("exam_race_respond")
def exam_race_respond(ctx: Ctx) -> None:
    me = onboard(ctx, "race1")
    if me is None:
        return
    imp = import_paper(ctx, me.sid, [mcq(ctx, n) for n in range(1, 15)], case="import 14-question paper", title="apitest race respond")
    if not good(imp):
        return
    qid, ids = js(imp)["quiz_id"], qids(imp)

    # ---- 8 identical respond calls for ONE question
    rs = fan(8, lambda i: _respond_as(ctx, me, qid, ids[0], "B", "duplicate respond (8 parallel)", i))
    c = codes(rs)
    wins = [r for r in rs if r is not None and r.status_code == 200]
    check(ctx, "8 parallel duplicate responds: exactly one is saved", len(wins) == 1, str(dict(c)))
    check(ctx, "the 7 losers say ALREADY_ANSWERED (not a generic CONFLICT)", all(k == (409, "ALREADY_ANSWERED") for k in c if k[0] != 200), str(dict(c)))
    check(ctx, "the winner counted exactly one answer", len(wins) == 1 and js(wins[0]).get("answered_count") == 1, str(js(wins[0]) if wins else None))
    nxt = _respond_as(ctx, me, qid, ids[1], "B", "respond to the next question after the race", 0, ok={200})
    check(ctx, "no phantom increments from the losers (answered_count is 2)", good(nxt) and js(nxt)["answered_count"] == 2, str(js(nxt)))

    # ---- 3 then 8 parallel responds to DIFFERENT questions (all correct): every answer must be saved and counted once
    total = 2
    for wave, (lo, hi) in enumerate(((2, 5), (5, 13)), start=1):
        batch = ids[lo:hi]
        rs = fan(len(batch), lambda i, batch=batch, wave=wave: _respond_as(ctx, me, qid, batch[i], "B", f"respond to {len(batch)} different questions in parallel", i))
        saved = [js(r) for r in rs if r is not None and r.status_code == 200]
        c = codes(rs)
        check(ctx, f"{len(batch)}-way parallel answers: all saved (a legitimate answer must not be refused as a conflict)",
              len(saved) == len(batch), f"{len(saved)}/{len(batch)} saved: {dict(c)}")
        counts = sorted(s["answered_count"] for s in saved)
        check(ctx, f"{len(batch)}-way parallel answers: answered_count values are unique and consecutive (no lost or double count)",
              counts == list(range(total + 1, total + len(saved) + 1)), f"{counts} after {total} answered")
        total += len(saved)
        row = None
        for _ in range(8):
            row = _mine(ctx, me, qid)
            if row.get("correct_count") == total:
                break
            time.sleep(0.6)                                     # a beat for the eventually consistent GSI
        check(ctx, f"stored correct_count equals the answers saved so far ({total})", row.get("correct_count") == total, str(row))
    last = _respond_as(ctx, me, qid, ids[13], "B", "respond to the last question", 1, ok={200})
    check(ctx, "final counter is total + 1", good(last) and js(last)["answered_count"] == total + 1, f"{js(last)} total={total}")
    sub = svc(ctx, "submit after the races", "POST", f"/papers/{qid}/submit", 200, params={"student_id": me.sid})
    if good(sub):
        rv = js(sub)
        check(ctx, "review agrees with the counters", rv["answered_count"] == total + 1 and rv["score"] == total + 1,
              f"answered {rv['answered_count']} score {rv['score']} expected {total + 1}")


@journey("exam_race_finalize")
def exam_race_finalize(ctx: Ctx) -> None:
    me = onboard(ctx, "race2")
    if me is None:
        return
    for width in (2, 4):
        qid = start_paper(ctx, me.sid, count=6, case=f"start (finalize x{width})")
        if qid is None:
            return
        sets = [[mcq(ctx, n, prompt_text=f"[{ctx.run_id}] writer {w} question {n}") for n in range(1, 7)] for w in range(width)]
        rs = fan(width, lambda i, qid=qid, sets=sets: ctx.api.expect(
            f"parallel finalize x{width}", "POST", f"{BASE}/papers/{qid}/finalize", {200, 404, 409}, admin=True,
            json={"student_id": me.sid, "generated_by": f"writer-{i}", "questions": sets[i]}))
        c = codes(rs)
        check(ctx, f"{width} parallel finalizes: exactly one wins", sum(1 for r in rs if r is not None and r.status_code == 200) == 1, str(dict(c)))
        check(ctx, f"{width} parallel finalizes: losers get 404/409, never a 5xx", all(k[0] in (200, 404, 409) for k in c), str(dict(c)))
        paper = get_paper(ctx, me.sid, qid, f"paper after {width} parallel finalizes")
        if good(paper):
            p = js(paper)
            scan(ctx, "paper after parallel finalize", paper)
            writers = {q["prompt_text"].split(" question ")[0] for q in p["questions"]}
            check(ctx, "READY with exactly 6 questions, ordinals 1..6", p["status"] == "READY" and [q["ordinal"] for q in p["questions"]] == list(range(1, 7)),
                  f"{p['status']} {[q['ordinal'] for q in p['questions']]}")
            check(ctx, "all questions come from ONE writer (no interleaving of two finalizes)", len(writers) == 1, str(writers))


@journey("exam_race_progress")
def exam_race_progress(ctx: Ctx) -> None:
    me = onboard(ctx, "race3")
    if me is None:
        return
    imp = import_paper(ctx, me.sid, [mcq(ctx, n) for n in range(1, 9)], case="import 8-question paper", title="apitest race progress")
    if not good(imp):
        return
    qid, ids = js(imp)["quiz_id"], qids(imp)
    path = f"{BASE}/papers/{qid}/progress"

    def put(i: int, ordinal: int, key: str, ok=frozenset({200, 409})):
        body = {"current_question_ordinal": ordinal, "question_id": ids[ordinal - 1], "selected_key": key}
        if i % 2:
            return ctx.api.expect("parallel progress (learner)", "PUT", f"/v1/quiz/{qid}/progress", set(ok), token=me.token, json=body)
        return ctx.api.expect("parallel progress (service)", "PUT", path, set(ok), admin=True, json={"student_id": me.sid, **body})

    # ---- 8 drafts for 8 different questions at once: none may be lost
    rs = fan(8, lambda i: put(i, i + 1, "ABC"[i % 3], ok={200}))
    check(ctx, "8 parallel progress saves all succeed", all(r is not None and r.status_code == 200 for r in rs), str(dict(codes(rs))))
    g = get_paper(ctx, me.sid, qid, "paper after 8 parallel drafts")
    scan(ctx, "paper after parallel drafts", g)
    if good(g):
        p = js(g)
        drafts = {q["ordinal"]: q["draft_response"] for q in p["questions"]}
        lost = [o for o in range(1, 9) if drafts.get(o) != {"selected_key": "ABC"[(o - 1) % 3]}]
        check(ctx, "no draft was lost", not lost, f"missing/wrong drafts for ordinals {lost}: {drafts}")
        check(ctx, "paper IN_PROGRESS, started_at set once, resume ordinal is one of the saved ones",
              p["status"] == "IN_PROGRESS" and p["started_at"] and p["resume_question_ordinal"] in range(1, 9), str((p["status"], p["started_at"], p["resume_question_ordinal"])))

    # ---- six writers of the SAME draft: one of the six values must win, intact
    fan(6, lambda i: put(i, 1, "ABC"[i % 3], ok={200}))
    g = get_paper(ctx, me.sid, qid, "paper after 6 drafts of one question")
    if good(g):
        check(ctx, "the stored draft is one of the written values", js(g)["questions"][0]["draft_response"] in ({"selected_key": k} for k in "ABC"),
              str(js(g)["questions"][0]["draft_response"]))

    # ---- respond racing a draft of the same question: an answered question must never keep a draft that could resurrect it
    def mix(i: int):
        n = i // 2 + 1
        if i % 2 == 0:
            return _respond_as(ctx, me, qid, ids[n - 1], "B", "respond racing a draft", 0)
        return put(0, n, "A")

    rs = fan(8, mix)
    c = codes(rs)
    check(ctx, "respond/draft race: only 200 / ALREADY_ANSWERED outcomes", all(k in {(200, None), (409, "ALREADY_ANSWERED")} for k in c), str(dict(c)))
    g = get_paper(ctx, me.sid, qid, "paper after respond/draft races")
    scan(ctx, "paper after respond/draft races", g)
    if good(g):
        rows = js(g)["questions"][:4]
        check(ctx, "all four questions got their answer", all(q["answered"] and q["student_response"] == {"selected_key": "B"} for q in rows),
              str([(q["ordinal"], q["answered"], q["student_response"]) for q in rows]))
        check(ctx, "no answered question keeps a draft", all(q["draft_response"] is None for q in rows), str([(q["ordinal"], q["draft_response"]) for q in rows]))

    # ---- generation events: one ordinal written 8 times, then 8 distinct ordinals
    qid2 = start_paper(ctx, me.sid, count=1, case="start (generation event races)")
    if qid2 is None:
        return
    gp = f"{BASE}/papers/{qid2}/generation-events"
    fan(8, lambda i: ctx.api.expect("same ordinal x8", "POST", gp, {200}, admin=True,
                                    json={"ordinal": 1, "phase": "INTAKE", "status": "STARTED", "detail": f"writer {i}"}))
    fan(8, lambda i: ctx.api.expect("8 distinct ordinals", "POST", gp, {200}, admin=True,
                                    json={"ordinal": 2 + i, "phase": "DRAFT_QUESTION", "status": "DONE", "detail": f"d{i}"}))
    ev = svc(ctx, "events after the races", "GET", f"/papers/{qid2}/generation-events", 200, params={"student_id": me.sid})
    if good(ev):
        check(ctx, "one row per ordinal, 1..9, in order", [e["ordinal"] for e in js(ev)] == list(range(1, 10)), str([e["ordinal"] for e in js(ev)]))
        first = next(e for e in js(ev) if e["ordinal"] == 1)
        check(ctx, "the single row of ordinal 1 is one writer's, intact", first["detail"].startswith("writer ") and first["phase"] == "INTAKE", str(first))


@journey("exam_race_submit")
def exam_race_submit(ctx: Ctx) -> None:
    me = onboard(ctx, "race4")
    if me is None:
        return
    imp = import_paper(ctx, me.sid, [mcq(ctx, n) for n in range(1, 4)], case="import 3-question paper", title="apitest race submit")
    if not good(imp):
        return
    qid = js(imp)["quiz_id"]
    rs = fan(4, lambda i: ctx.api.expect("parallel submit", "POST", f"{BASE}/papers/{qid}/submit", {200, 409}, admin=True, params={"student_id": me.sid}))
    c = codes(rs)
    check(ctx, "4 parallel submits: exactly one 200", sum(1 for r in rs if r is not None and r.status_code == 200) == 1, str(dict(c)))
    check(ctx, "the others say ALREADY_SUBMITTED", all(k in {(200, None), (409, "ALREADY_SUBMITTED")} for k in c), str(dict(c)))

    # ---- parallel diagnosis writes on the graded paper
    rs = fan(4, lambda i: ctx.api.expect("parallel diagnosis", "POST", f"{BASE}/papers/{qid}/diagnosis", {200, 409}, admin=True,
                                         json={"student_id": me.sid, "time_management_verdict": f"writer {i}", "generated_by": f"w{i}"}))
    c = codes(rs)
    check(ctx, "parallel diagnosis writes: at least one lands", any(r is not None and r.status_code == 200 for r in rs), str(dict(c)))
    check(ctx, "a diagnosis writer is never refused as a conflict while the paper is idle", all(k[0] == 200 for k in c), str(dict(c)))
    final = svc(ctx, "diagnosis after the race", "POST", f"/papers/{qid}/diagnosis", 200,
                json={"student_id": me.sid, "time_management_verdict": "final", "generated_by": "final"})
    got = svc(ctx, "latest diagnosis after the race", "GET", f"/papers/{qid}/diagnosis", 200, params={"student_id": me.sid})
    check(ctx, "a later write is the latest (version counter was not corrupted by the race)",
          good(final) and good(got) and js(got)["time_management_verdict"] == "final", str(js(got)))

    # ---- respond racing submit, three times: the answer is either saved before the submit (and then reviewed) or refused
    for round_ in range(1, 4):
        imp = import_paper(ctx, me.sid, [mcq(ctx, n) for n in range(1, 4)], case=f"import for respond-vs-submit #{round_}", title="apitest race submit 2")
        if not good(imp):
            return
        q2, ids = js(imp)["quiz_id"], qids(imp)
        first = _respond_as(ctx, me, q2, ids[0], "B", "pre-answer q1", 0, ok={200})
        if not good(first):
            return

        def act(i: int, q2=q2, ids=ids):
            if i == 0:
                return ctx.api.expect("respond racing submit", "POST", f"{BASE}/papers/{q2}/questions/{ids[1]}/respond", {200, 409}, admin=True,
                                      json={"student_id": me.sid, "selected_key": "B"})
            return ctx.api.expect("submit racing respond", "POST", f"{BASE}/papers/{q2}/submit", {200, 409}, admin=True, params={"student_id": me.sid})

        r_resp, r_sub = fan(2, act)
        review = svc(ctx, f"review after respond-vs-submit #{round_}", "GET", f"/papers/{q2}/review", 200, params={"student_id": me.sid})
        if good(review) and r_resp is not None:
            saved = r_resp.status_code == 200
            row = next(q for q in js(review)["questions"] if q["ordinal"] == 2)
            check(ctx, f"respond-vs-submit #{round_}: a saved answer is in the review, a refused one is not (outcome {codes([r_resp, r_sub])})",
                  (row["student_response"] is not None) == saved and js(review)["answered_count"] == (2 if saved else 1),
                  f"respond={r_resp.status_code} submit={r_sub.status_code if r_sub is not None else None} answered_count={js(review)['answered_count']} q2={row['student_response']}")
            check(ctx, f"respond-vs-submit #{round_}: a refused answer carries EXAM_NOT_EDITABLE", saved or code_of(r_resp) in ("EXAM_NOT_EDITABLE", "ALREADY_ANSWERED"),
                  str(code_of(r_resp)))
