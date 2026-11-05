"""Isolation and authentication: learner B against learner A's paper (learner bearer routes AND service routes with B's student id), and
every exam-integration / quiz route without credentials, with a wrong service key, with a learner bearer in place of the key, and
(quiz routes) with a garbage / tampered bearer or with the service key. Nothing may leak and nothing of A's may change."""
from __future__ import annotations

from apitest.context import Ctx
from apitest.journeys import journey
from apitest.journeys.exam_common import BASE, call, check, get_paper, good, import_paper, js, mcq, poll, qids, register, scan, start_paper, svc


@journey("exam_isolation")
def exam_isolation(ctx: Ctx) -> None:
    a, b = register(ctx, "isoa"), register(ctx, "isob")
    if not (a and b):
        return
    imp = import_paper(ctx, a.sid, [mcq(ctx, n) for n in range(1, 4)], case="A: import a paper", title="apitest isolation")
    shell = start_paper(ctx, a.sid, count=2, case="A: start a second paper")
    if not good(imp) or shell is None:
        return
    qid, ids = js(imp)["quiz_id"], qids(imp)
    answered = call(ctx, "A: answers q1", "POST", f"/v1/quiz/{qid}/questions/{ids[0]}/respond", 200, token=a.token, json={"selected_key": "B"})
    scan(ctx, "A: own respond", answered)
    snapshot = js(get_paper(ctx, a.sid, qid, "A: snapshot before the attacks"))

    # ---- learner B, bearer routes: someone else's quiz id is a plain 404 (or 403), on every route, and changes nothing
    deny = {403, 404}
    call(ctx, "B: get A's quiz", "GET", f"/v1/quiz/{qid}", deny, token=b.token)
    call(ctx, "B: review A's quiz", "GET", f"/v1/quiz/{qid}/review", deny, token=b.token)
    call(ctx, "B: diagnosis of A's quiz", "GET", f"/v1/quiz/{qid}/diagnosis", deny, token=b.token)
    call(ctx, "B: progress on A's quiz", "PUT", f"/v1/quiz/{qid}/progress", deny, token=b.token,
         json={"current_question_ordinal": 2, "question_id": ids[1], "selected_key": "A"})
    call(ctx, "B: respond to A's question", "POST", f"/v1/quiz/{qid}/questions/{ids[1]}/respond", deny, token=b.token, json={"selected_key": "B"})
    call(ctx, "B: respond to A's already answered question", "POST", f"/v1/quiz/{qid}/questions/{ids[0]}/respond", deny, token=b.token,
         json={"selected_key": "A"})
    mine_b = call(ctx, "B: mine", "GET", "/v1/quiz/mine", 200, token=b.token)
    check(ctx, "B's list does not contain A's papers", good(mine_b) and js(mine_b) == [], str(js(mine_b)))

    # ---- the service credential acting with B's student id on A's paper: 404 everywhere, A's paper untouched
    p, q, bs = f"/papers/{qid}", ids[1], b.sid
    for case, method, path, kw in (
            ("get paper", "GET", p, {"params": {"student_id": bs}}),
            ("review", "GET", f"{p}/review", {"params": {"student_id": bs}}),
            ("submit", "POST", f"{p}/submit", {"params": {"student_id": bs}}),
            ("diagnosis-input", "GET", f"{p}/diagnosis-input", {"params": {"student_id": bs}}),
            ("diagnosis read", "GET", f"{p}/diagnosis", {"params": {"student_id": bs}}),
            ("diagnosis write", "POST", f"{p}/diagnosis", {"json": {"student_id": bs, "time_management_verdict": "x", "generated_by": "apitest"}}),
            ("events read", "GET", f"{p}/events", {"params": {"student_id": bs}}),
            ("generation events read", "GET", f"{p}/generation-events", {"params": {"student_id": bs}}),
            ("event write", "POST", f"{p}/questions/{q}/events", {"json": {"student_id": bs, "event_type": "VIEW"}}),
            ("progress", "PUT", f"{p}/progress", {"json": {"student_id": bs, "current_question_ordinal": 2, "question_id": q, "selected_key": "A"}}),
            ("respond", "POST", f"{p}/questions/{q}/respond", {"json": {"student_id": bs, "selected_key": "B"}}),
            ("finalize", "POST", f"{p}/finalize", {"json": {"student_id": bs, "questions": [mcq(ctx, 9)]}}),
            ("fail a GENERATING shell", "POST", f"/papers/{shell}/fail", {"json": {"student_id": bs, "error_message": "hostile"}}),
            ("finalize a GENERATING shell", "POST", f"/papers/{shell}/finalize", {"json": {"student_id": bs, "questions": [mcq(ctx, 9)]}}),
    ):
        svc(ctx, f"service as B: {case} on A's paper", method, path, 404, **kw)
    after = get_paper(ctx, a.sid, qid, "A: paper after the attacks")
    check(ctx, "A's paper is exactly as before the attacks", good(after) and js(after) == snapshot, "paper changed")
    shell_after = get_paper(ctx, a.sid, shell, "A: shell after the attacks")
    check(ctx, "A's second paper is still GENERATING", good(shell_after) and js(shell_after)["status"] == "GENERATING", "shell changed")
    ok = call(ctx, "A: submit still possible", "POST", f"{BASE}/papers/{qid}/submit", 200, admin=True, params={"student_id": a.sid})
    check(ctx, "nothing B sent was recorded (only A's q1 answer is in the review)", good(ok) and js(ok)["answered_count"] == 1 and js(ok)["score"] == 1,
          str(js(ok) and {k: js(ok)[k] for k in ("answered_count", "score")}))

    # ---- credentials of every exam-integration route (A's real ids, so a missing check would really mutate A's data)
    sub = "5f6f1d6c-2f1f-4b7d-9d55-" + ctx.run_id.ljust(12, "0")[:12]
    ev = ids[2]
    routes = [
        ("POST", "/students/onboard", {"json": {"cognito_sub": sub, "first_name": "No", "last_name": "Auth", "email": f"noauth.{ctx.run_id}@example.com"}}),
        ("GET", f"/students/by-cognito-sub/{sub}", {}),
        ("GET", f"/students/{a.sid}", {}),
        ("POST", f"/students/{a.sid}/mint-session-token", {}),
        ("GET", f"/students/{a.sid}/mastery-summary", {}),
        ("GET", "/difficulty-distribution", {"params": {"concept_slug": "x"}}),
        ("POST", "/papers", {"json": {"student_id": a.sid, "style": "AIME", "title": "noauth", "requested_question_count": 1,
                                      "requested_question_types": ["MCQ"], "generated_by": "x", "questions": [mcq(ctx, 1)]}}),
        ("POST", "/papers/start", {"json": {"student_id": a.sid, "style": "AIME", "title": "noauth", "requested_question_count": 1,
                                            "requested_question_types": ["MCQ"], "generated_by": "x"}}),
        ("GET", "/papers/mine", {"params": {"student_id": a.sid}}),
        ("GET", f"/papers/{qid}", {"params": {"student_id": a.sid}}),
        ("POST", f"/papers/{shell}/finalize", {"json": {"student_id": a.sid, "questions": [mcq(ctx, 1)]}}),
        ("POST", f"/papers/{shell}/fail", {"json": {"student_id": a.sid, "error_message": "noauth"}}),
        ("POST", "/question-pool/match", {"json": {"student_id": a.sid, "style": "AIME", "concept_slugs": ["x"]}}),
        ("POST", f"/papers/{shell}/generation-events", {"json": {"ordinal": 77, "phase": "DONE", "status": "DONE"}}),
        ("GET", f"/papers/{shell}/generation-events", {"params": {"student_id": a.sid}}),
        ("PUT", f"/papers/{qid}/progress", {"json": {"student_id": a.sid, "current_question_ordinal": 1}}),
        ("POST", f"/papers/{qid}/questions/{ev}/respond", {"json": {"student_id": a.sid, "selected_key": "A"}}),
        ("POST", f"/papers/{qid}/questions/{ev}/events", {"json": {"student_id": a.sid, "event_type": "VIEW"}}),
        ("GET", f"/papers/{qid}/events", {"params": {"student_id": a.sid}}),
        ("GET", f"/papers/{qid}/review", {"params": {"student_id": a.sid}}),
        ("POST", f"/papers/{qid}/submit", {"params": {"student_id": a.sid}}),
        ("GET", f"/papers/{qid}/diagnosis-input", {"params": {"student_id": a.sid}}),
        ("POST", f"/papers/{qid}/diagnosis", {"json": {"student_id": a.sid, "time_management_verdict": "noauth", "generated_by": "x"}}),
        ("GET", f"/papers/{qid}/diagnosis", {"params": {"student_id": a.sid}}),
    ]
    for method, path, kw in routes:
        full, label = f"{BASE}{path}", f"{method} {path[:56]}"
        call(ctx, f"no credentials: {label}", method, full, 401, **kw)
        call(ctx, f"wrong service key: {label}", method, full, 401, headers={"X-Admin-Api-Key": "definitely-not-the-key"}, **kw)
        call(ctx, f"learner bearer instead of the key: {label}", method, full, {401, 403}, token=a.token, **kw)

    # nothing above may have taken effect
    svc(ctx, "unauthenticated onboard created no student", "GET", f"/students/by-cognito-sub/{sub}", 404)
    rows = poll(ctx, "A: papers after the credential probes (exactly 2: nothing was created)", "GET", f"{BASE}/papers/mine", lambda r: len(r) == 2,
                admin=True, params={"student_id": a.sid}) or []
    check(ctx, "unauthenticated import/start created no paper (A still has exactly 2)", len(rows) == 2, f"{len(rows)} papers: {[(r['title'], r['status']) for r in rows]}")
    shell_end = get_paper(ctx, a.sid, shell, "A: shell after the credential probes")
    check(ctx, "unauthenticated generation event / finalize / fail did not land", good(shell_end) and js(shell_end)["status"] == "GENERATING", "")

    # ---- credentials of the learner quiz routes
    quiz_routes = [("GET", "/v1/quiz/mine", {}), ("GET", f"/v1/quiz/{qid}", {}), ("GET", f"/v1/quiz/{qid}/review", {}),
                   ("GET", f"/v1/quiz/{qid}/diagnosis", {}), ("PUT", f"/v1/quiz/{qid}/progress", {"json": {"current_question_ordinal": 1}}),
                   ("POST", f"/v1/quiz/{qid}/questions/{ev}/respond", {"json": {"selected_key": "A"}}),
                   ("POST", "/v1/quiz/generate", {"json": {"style": "AIME", "question_count": 1}})]
    tampered = a.token[:-3] + ("AAA" if not a.token.endswith("AAA") else "BBB")
    for method, path, kw in quiz_routes:
        label = f"{method} {path[:48]}"
        call(ctx, f"quiz, no bearer: {label}", method, path, {401, 403}, **kw)
        call(ctx, f"quiz, garbage bearer: {label}", method, path, 401, token="not.a.jwt", **kw)
        call(ctx, f"quiz, tampered signature: {label}", method, path, 401, token=tampered, **kw)
        call(ctx, f"quiz, service key instead of a bearer: {label}", method, path, {401, 403}, admin=True, **kw)
