"""WP6 papers over HTTP (requirement 71 §5, requirement 70 C2 section 9): answer-key non-disclosure on every learner-reachable body,
the learner routes added by the design (diagnosis, progress) and contract parity between the two exam backends.

The DynamoDB side is the real store on moto; the PostgreSQL side is the real ``PostgresExamStore`` with ``quiz_runtime``'s SQL layer
replaced by an in-memory oracle (``wp6_papers_oracle``). Both sit behind the same routers, ids are deterministic per backend so one
scripted scenario can address both, and LLMs are stubbed.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from wp6_papers_oracle import QuizSqlOracle
from wp6_papers_support import FakeLLM, NoPostgres, free_text, mcq, profile, seed_content

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "parity"))

from parity_harness import ParityCase, assert_parity

from mathbank_rest import quiz_logic as ql
from mathbank_rest import stores
from mathbank_rest.config import settings
from mathbank_rest.routers import exam_integration, quiz_runtime
from mathbank_rest.security import get_current_student_id, require_admin_api_key
from mathbank_rest.stores import typed
from mathbank_rest.stores.content import DynamoDBContentStore
from mathbank_rest.stores.errors import install_error_handlers
from mathbank_rest.stores.exam import DynamoDBExamStore, PostgresExamStore

NS = uuid.UUID("6b0f3c2e-5e55-4c1a-9a31-0d2f4c1b7a11")
MARKERS = ("SOLUTION-MARKER", "EXPLAIN-MARKER", "ANSWER-MARKER", "REVISION-MARKER", "SOURCE-MARKER", "INSIGHT-MARKER", "RUBRIC-MARKER")
SECRET_KEYS = {"correct_answer", "option_explanations", "revision_log", "inspiration_sources", "solution", "solution_text", "solution_latex",
               "solution_steps", "key_insight", "is_correct", "feedback", "grading_feedback", "grading_rubric", "expected_answer", "correct_key"}


class Ids:
    """Deterministic per-backend uuid sequences: the n-th id of the PostgreSQL run equals the n-th id of the DynamoDB run."""

    def __init__(self) -> None:
        self.active, self.n = "postgres", {"postgres": 0, "dynamodb": 0}

    def __call__(self) -> UUID:
        self.n[self.active] += 1
        return uuid.uuid5(NS, str(self.n[self.active]))


class Backend:
    """A TestClient that routes every request to its own exam store (and id sequence)."""

    def __init__(self, name: str, app: FastAPI, store, ids: Ids) -> None:
        self.name, self.client, self.store, self.ids = name, TestClient(app), store, ids

    def request(self, *args, **kwargs):
        self.ids.active = self.name
        with stores.override_store("exam", self.store):
            return self.client.request(*args, **kwargs)


def build_app(sid: str) -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(quiz_runtime.router)
    app.include_router(exam_integration.router)
    app.dependency_overrides[get_current_student_id] = lambda: UUID(sid)
    app.dependency_overrides[require_admin_api_key] = lambda: None
    return app


@pytest.fixture()
def http(content_table, monkeypatch, sid):
    from mathbank_rest import quiz_runtime as quiz_module
    from mathbank_rest.db import postgres
    from mathbank_rest.stores.exam import papers

    seed_content()
    typed.put(profile(sid))
    monkeypatch.setattr(postgres, "engine", NoPostgres())
    monkeypatch.setattr(settings, "quiz_mastery_inline", False)
    monkeypatch.setattr(settings, "quiz_strict_exam_policy", True)
    monkeypatch.setattr("mathbank_rest.db.hybrid_search.search_problems", lambda *a, **k: {"results": []})
    monkeypatch.setattr(ql, "_targets_from_state", lambda student_id, max_targets: [])
    llm = FakeLLM()
    monkeypatch.setattr(ql, "_client", lambda: llm.client)
    ids = Ids()

    monkeypatch.setattr(papers, "uuid4", ids)
    oracle = QuizSqlOracle(ids, lambda: (True, 0.9, "Well reasoned."))
    oracle.install(monkeypatch)

    class Learner:
        """The learner store both backends read the mastery of the tagged concepts from."""

        def get_mastery_summary(self, student_id):
            return {"concepts": [{"slug": s, "mastery_score": v} for s, v in oracle.mastery["concepts"].items()], "techniques": []}

    app = build_app(sid)
    with stores.override_store("content", DynamoDBContentStore()), stores.override_store("learner", Learner()):
        yield SimpleNamespace(
            sid=sid, app=app, llm=llm, oracle=oracle, quiz_module=quiz_module,
            ddb=Backend("dynamodb", app, DynamoDBExamStore(), ids), pg=Backend("postgres", app, PostgresExamStore(), ids),
            clients=None)


def pair(w) -> dict:
    return {"postgres": w.pg, "dynamodb": w.ddb}


def secret_questions() -> list[dict]:
    return [
        mcq(1, concepts=("counting",), solution_text="SOLUTION-MARKER one", key_insight="INSIGHT-MARKER",
            option_explanations={"A": "EXPLAIN-MARKER a", "B": "EXPLAIN-MARKER b", "C": "EXPLAIN-MARKER c"},
            revision_log=[{"round": 1, "verdict": "APPROVE", "feedback": "REVISION-MARKER"}],
            inspiration_sources=[{"canonical_code": "AMC10_2005B_Q18", "note": "SOURCE-MARKER"}]),
        free_text(2, correct_answer={"expected_answer": "ANSWER-MARKER", "grading_rubric": "RUBRIC-MARKER"}, solution_text="SOLUTION-MARKER two"),
    ]


def keys_of(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in keys_of(v)}
    if isinstance(value, list):
        return {k for v in value for k in keys_of(v)}
    return set()


def assert_safe(response, *, allow: frozenset = frozenset()) -> None:
    """A learner-reachable body: no answer-key attribute and no secret text anywhere in it."""
    assert response.status_code < 300, response.text
    assert not ((keys_of(response.json()) & SECRET_KEYS) - allow), (response.request.url, keys_of(response.json()) & SECRET_KEYS)
    assert not [m for m in MARKERS if m in response.text], response.request.url


# --------------------------------------------------------------------------------------------------------- disclosure


def test_no_learner_reachable_body_carries_an_answer_key(http):
    w, ddb = http, http.ddb
    exam = {"student_id": w.sid, "style": "MIXED", "title": "Mock", "requested_question_count": 2, "requested_question_types": ["MCQ", "FREE_TEXT"],
            "generated_by": "agent", "time_limit_seconds": 3600}
    qid = ddb.request("POST", "/v1/quiz-integration/papers/start", json=exam).json()["quiz_id"]
    finalize = ddb.request("POST", f"/v1/quiz-integration/papers/{qid}/finalize", json={"student_id": w.sid, "questions": secret_questions()})
    assert_safe(finalize)                                                                      # finalize
    q1, q2 = (q["question_id"] for q in finalize.json()["questions"])
    for call in (("GET", f"/v1/quiz/{qid}"), ("GET", "/v1/quiz/mine"),                                  # get, mine
                 ("GET", f"/v1/quiz-integration/papers/{qid}", {"student_id": w.sid}),
                 ("GET", "/v1/quiz-integration/papers/mine", {"student_id": w.sid})):
        assert_safe(ddb.request(call[0], call[1], params=call[2] if len(call) > 2 else None))
    assert_safe(ddb.request("PUT", f"/v1/quiz/{qid}/progress", json={"current_question_ordinal": 1, "question_id": q1, "selected_key": "B"}))
    assert_safe(ddb.request("PUT", f"/v1/quiz-integration/papers/{qid}/progress",
                            json={"student_id": w.sid, "current_question_ordinal": 2, "response_text": "x"}))              # progress
    assert_safe(ddb.request("GET", f"/v1/quiz/{qid}"))                                                  # now with draft and position
    for question, body in ((q1, {"selected_key": "A"}), (q2, {"response_text": "4"})):                    # exam-mode respond, both routes
        r = ddb.request("POST", f"/v1/quiz/{qid}/questions/{question}/respond", json=body) if question == q1 else \
            ddb.request("POST", f"/v1/quiz-integration/papers/{qid}/questions/{question}/respond", json={"student_id": w.sid, **body})
        assert_safe(r)
        assert set(r.json()) == {"saved", "question_id", "answered_count"}
    assert_safe(ddb.request("GET", f"/v1/quiz-integration/papers/{qid}/events", params={"student_id": w.sid}))
    for url, kwargs in ((f"/v1/quiz/{qid}/review", {}), (f"/v1/quiz-integration/papers/{qid}/review", {"params": {"student_id": w.sid}})):
        early = ddb.request("GET", url, **kwargs)                                                           # review -> 409 before submit
        assert early.status_code == 409 and early.json()["detail"]["code"] == "EXAM_IN_PROGRESS"
        assert not [m for m in MARKERS if m in early.text]
    failed = ddb.request("POST", "/v1/quiz-integration/papers/start", json=exam).json()["quiz_id"]          # fail
    r = ddb.request("POST", f"/v1/quiz-integration/papers/{failed}/fail", json={"student_id": w.sid, "error_message": "critic said no"})
    assert_safe(r)
    assert r.json()["status"] == "FAILED"
    practice = ddb.request("POST", "/v1/quiz/generate", json={"style": "AIME", "question_count": 2, "question_types": ["MCQ", "FREE_TEXT"]})
    assert_safe(practice)                                                                                    # generate
    submitted = ddb.request("POST", f"/v1/quiz-integration/papers/{qid}/submit", params={"student_id": w.sid})
    assert submitted.status_code == 200 and "SOLUTION-MARKER one" in submitted.text                        # after submit the key is the point


def test_a_practice_respond_discloses_by_design_and_nothing_else(http):
    w = http
    practice = w.ddb.request("POST", "/v1/quiz/generate", json={"style": "AIME", "question_count": 1, "question_types": ["MCQ"]}).json()
    body = w.ddb.request("POST", f"/v1/quiz/{practice['quiz_id']}/questions/{practice['questions'][0]['question_id']}/respond",
                         json={"selected_key": "B"}).json()
    assert set(body) == {"is_correct", "grading_method", "confidence", "feedback", "solution"} and set(body["solution"]) == {"solution_text", "key_insight"}
    assert not keys_of(body) & {"correct_answer", "option_explanations", "revision_log", "inspiration_sources"}


def test_a_foreign_quiz_id_is_a_plain_404_on_every_learner_route(http):
    w = http
    other = str(uuid.uuid4())
    typed.put(profile(other))
    qid = w.ddb.request("POST", "/v1/quiz-integration/papers/start", json={
        "student_id": other, "style": "AIME", "title": "t", "requested_question_count": 1, "requested_question_types": ["MCQ"],
        "generated_by": "x"}).json()["quiz_id"]
    for method, url, body in (("GET", f"/v1/quiz/{qid}", None), ("GET", f"/v1/quiz/{qid}/review", None), ("GET", f"/v1/quiz/{qid}/diagnosis", None),
                              ("PUT", f"/v1/quiz/{qid}/progress", {"current_question_ordinal": 1}),
                              ("POST", f"/v1/quiz/{qid}/questions/{uuid.uuid4()}/respond", {"selected_key": "A"})):
        r = w.ddb.request(method, url, json=body)
        assert r.status_code == 404 and r.json()["detail"]["code"] == "NOT_FOUND", (url, r.text)


def test_the_new_learner_routes_diagnosis_and_progress(http):
    w, ddb = http, http.ddb
    qid = ddb.request("POST", "/v1/quiz-integration/papers", json={
        "student_id": w.sid, "style": "AIME", "title": "t", "requested_question_count": 1, "requested_question_types": ["MCQ"], "generated_by": "x",
        "questions": [mcq(1)]}).json()["quiz_id"]
    assert ddb.request("GET", f"/v1/quiz/{qid}/diagnosis").status_code == 404
    assert ddb.request("PUT", f"/v1/quiz/{qid}/progress", json={"current_question_ordinal": 1, "bogus": 1}).status_code == 422
    assert ddb.request("PUT", f"/v1/quiz/{qid}/progress", json={"current_question_ordinal": 1}).json() == {"saved": True, "current_question_ordinal": 1}
    assert ddb.request("POST", f"/v1/quiz-integration/papers/{qid}/submit", params={"student_id": w.sid}).status_code == 200
    assert ddb.request("POST", f"/v1/quiz-integration/papers/{qid}/diagnosis", json={
        "student_id": w.sid, "time_management_verdict": "ok", "generated_by": "agent"}).status_code == 200
    got = ddb.request("GET", f"/v1/quiz/{qid}/diagnosis")
    assert got.status_code == 200 and got.json()["time_management_verdict"] == "ok"


def test_exam_integration_errors_keep_the_agent_contract(http):
    w, ddb = http, http.ddb
    qid = ddb.request("POST", "/v1/quiz-integration/papers/start", json={
        "student_id": w.sid, "style": "AIME", "title": "t", "requested_question_count": 1, "requested_question_types": ["MCQ"],
        "generated_by": "x"}).json()["quiz_id"]
    bad = ddb.request("POST", f"/v1/quiz-integration/papers/{qid}/generation-events", json={"ordinal": 1, "phase": "NOPE", "status": "DONE"})
    assert (bad.status_code, bad.json()["detail"]["code"]) == (422, "INVALID_PHASE")
    unknown = ddb.request("POST", f"/v1/quiz-integration/papers/{uuid.uuid4()}/generation-events",
                          json={"ordinal": 1, "phase": "INTAKE", "status": "STARTED"})
    assert (unknown.status_code, unknown.json()["detail"]["code"]) == (404, "NOT_FOUND")
    ok = ddb.request("POST", f"/v1/quiz-integration/papers/{qid}/generation-events", json={"ordinal": 1, "phase": "INTAKE", "status": "STARTED"})
    assert ok.json() == {"ok": True}
    assert ddb.request("GET", "/v1/quiz-integration/difficulty-distribution").status_code == 422
    assert ddb.request("GET", "/v1/quiz-integration/difficulty-distribution", params={"concept_slug": "counting"}).json() == {
        "distribution": {"hard": 1, "very_hard": 1}}
    missing_profile = ddb.request("POST", "/v1/quiz-integration/papers/start", json={
        "student_id": str(uuid.uuid4()), "style": "AIME", "title": "t", "requested_question_count": 1, "requested_question_types": ["MCQ"],
        "generated_by": "x"})
    assert missing_profile.status_code == 404 and missing_profile.json()["detail"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------------------------------------- parity


def run(w, name: str, method: str, path: str, *, json=None, params=None, status: int | None = None, allowed=()) -> None:
    assert_parity(pair(w), ParityCase(name, method, path, json=json, params=params, expect_status=status), allowed=allowed)


def test_the_exam_flow_is_the_same_on_both_backends(http):
    w = http
    sid = w.sid
    base = "/v1/quiz-integration"
    when = ["$.started_at", "$.submitted_at", "$[*].created_at"]
    exam = {"student_id": sid, "style": "MIXED", "title": "Mock exam", "instructions": "be quick", "requested_question_count": 2,
            "requested_question_types": ["MCQ", "FREE_TEXT"], "difficulty_band": "hard", "generated_by": "agent", "time_limit_seconds": 5400}
    run(w, "start", "POST", f"{base}/papers/start", json=exam, status=200)
    qid = str(uuid.uuid5(NS, "1"))
    for ordinal in range(1, 31):                                                                         # 30 progress events while generating
        run(w, f"event {ordinal}", "POST", f"{base}/papers/{qid}/generation-events", status=200,
            json={"ordinal": ordinal, "phase": "DRAFT_QUESTION", "status": "STARTED" if ordinal % 2 else "DONE", "question_ordinal": 1 + ordinal % 2,
                  "detail": f"step {ordinal}"})
    run(w, "events again (idempotent)", "POST", f"{base}/papers/{qid}/generation-events", status=200,
        json={"ordinal": 5, "phase": "PERSIST", "status": "DONE"})
    run(w, "list events", "GET", f"{base}/papers/{qid}/generation-events", params={"student_id": sid, "since_ordinal": 25}, status=200)
    run(w, "review of a shell", "GET", f"{base}/papers/{qid}/review", params={"student_id": sid}, status=409)
    run(w, "submit from generating", "POST", f"{base}/papers/{qid}/submit", params={"student_id": sid}, status=409)
    run(w, "respond before finalize", "POST", f"{base}/papers/{qid}/questions/{uuid.uuid4()}/respond",
        json={"student_id": sid, "selected_key": "A"}, status=409)
    fin = assert_parity(pair(w), ParityCase("finalize", "POST", f"{base}/papers/{qid}/finalize", expect_status=200,
                                            json={"student_id": sid, "generated_by": "agent", "questions": secret_questions()}))
    run(w, "finalize again", "POST", f"{base}/papers/{qid}/finalize", status=404, json={"student_id": sid, "questions": secret_questions()})
    q1, q2 = (q["question_id"] for q in fin["dynamodb"][1]["questions"])
    run(w, "get", "GET", f"{base}/papers/{qid}", params={"student_id": sid}, status=200)
    run(w, "mine", "GET", f"{base}/papers/mine", params={"student_id": sid}, status=200, allowed=when)
    run(w, "learner get", "GET", f"/v1/quiz/{qid}", status=200)
    run(w, "learner mine", "GET", "/v1/quiz/mine", status=200, allowed=when)
    run(w, "bad draft", "PUT", f"{base}/papers/{qid}/progress", status=422, json={"student_id": sid, "current_question_ordinal": 1, "selected_key": "Z"})
    run(w, "progress", "PUT", f"{base}/papers/{qid}/progress", status=200,
        json={"student_id": sid, "current_question_ordinal": 1, "question_id": q1, "selected_key": "B"})
    run(w, "learner progress", "PUT", f"/v1/quiz/{qid}/progress", status=200, json={"current_question_ordinal": 2, "response_text": "four"})
    run(w, "get with drafts", "GET", f"{base}/papers/{qid}", params={"student_id": sid}, status=200, allowed=when)
    for ordinal, kind in ((1, "SELECT_OPTION"), (1, "VIEW"), (2, "TEXT_CHANGE")):
        run(w, f"log {kind}", "POST", f"{base}/papers/{qid}/questions/{q1 if ordinal == 1 else q2}/events", status=200,
            json={"student_id": sid, "event_type": kind, "option_key": "B" if kind == "SELECT_OPTION" else None, "client_timestamp_ms": None})
    run(w, "bad event", "POST", f"{base}/papers/{qid}/questions/{q1}/events", status=422, json={"student_id": sid, "event_type": "NOPE"})
    run(w, "event for an unknown question", "POST", f"{base}/papers/{qid}/questions/{uuid.uuid4()}/events", status=404,
        json={"student_id": sid, "event_type": "VIEW"})
    run(w, "events", "GET", f"{base}/papers/{qid}/events", params={"student_id": sid}, status=200, allowed=when)
    run(w, "respond", "POST", f"{base}/papers/{qid}/questions/{q1}/respond", status=200, json={"student_id": sid, "selected_key": "B", "time_spent_seconds": 30})
    run(w, "respond again", "POST", f"{base}/papers/{qid}/questions/{q1}/respond", status=409, json={"student_id": sid, "selected_key": "A"})
    run(w, "learner respond", "POST", f"/v1/quiz/{qid}/questions/{q2}/respond", status=200, json={"response_text": "four", "time_spent_seconds": 55})
    run(w, "empty respond", "POST", f"/v1/quiz/{qid}/questions/{q2}/respond", status=422, json={})
    run(w, "review before submit", "GET", f"/v1/quiz/{qid}/review", status=409)
    run(w, "diagnosis before grading", "POST", f"{base}/papers/{qid}/diagnosis", status=409,
        json={"student_id": sid, "time_management_verdict": "x", "generated_by": "a"})
    run(w, "submit", "POST", f"{base}/papers/{qid}/submit", params={"student_id": sid}, status=200)
    run(w, "submit again", "POST", f"{base}/papers/{qid}/submit", params={"student_id": sid}, status=409)
    run(w, "respond after submit", "POST", f"{base}/papers/{qid}/questions/{q1}/respond", status=409, json={"student_id": sid, "selected_key": "A"})
    run(w, "progress after submit", "PUT", f"{base}/papers/{qid}/progress", status=409, json={"student_id": sid, "current_question_ordinal": 1})
    run(w, "review", "GET", f"{base}/papers/{qid}/review", params={"student_id": sid}, status=200)
    run(w, "learner review", "GET", f"/v1/quiz/{qid}/review", status=200)
    run(w, "diagnosis input", "GET", f"{base}/papers/{qid}/diagnosis-input", params={"student_id": sid}, status=200,
        allowed=[*when, "$.questions[*].skill_slugs"])     # QUZ-F04: the DynamoDB store reads the skill tags back
    run(w, "no diagnosis yet", "GET", f"{base}/papers/{qid}/diagnosis", params={"student_id": sid}, status=404)
    run(w, "write diagnosis", "POST", f"{base}/papers/{qid}/diagnosis", status=200, json={
        "student_id": sid, "time_management_verdict": "well paced", "pacing_notes": [{"question_ordinal": 1, "note": "fast"}],
        "reasoning_guidance": [{"question_ordinal": 2, "guidance": "show steps"}], "improvement_areas": [], "generated_by": "agent"})
    run(w, "read diagnosis", "GET", f"{base}/papers/{qid}/diagnosis", params={"student_id": sid}, status=200)
    run(w, "learner diagnosis", "GET", f"/v1/quiz/{qid}/diagnosis", status=200)
    run(w, "unknown paper", "GET", f"{base}/papers/{uuid.uuid4()}", params={"student_id": sid}, status=404)
    run(w, "foreign student", "GET", f"{base}/papers/{qid}", params={"student_id": str(uuid.uuid4())}, status=404)


def test_the_practice_flow_is_the_same_on_both_backends(http):
    w = http
    run(w, "bad style", "POST", "/v1/quiz/generate", json={"style": "NOPE"}, status=422)
    run(w, "bad types", "POST", "/v1/quiz/generate", json={"style": "AIME", "question_types": ["ESSAY"]}, status=422)
    res = {}
    for name, backend in pair(w).items():              # the drafted prompts differ by construction (LLM vs oracle): compare the contract
        res[name] = backend.request("POST", "/v1/quiz/generate", json={"style": "AIME", "question_count": 2, "question_types": ["MCQ", "FREE_TEXT"]})
        assert res[name].status_code == 200
    a, b = res["postgres"].json(), res["dynamodb"].json()
    assert set(a) == set(b) and [q["question_type"] for q in a["questions"]] == [q["question_type"] for q in b["questions"]]
    assert [set(q) for q in a["questions"]] == [set(q) for q in b["questions"]] and (a["title"], a["status"]) == (b["title"], b["status"])
    ids = {n: (r.json()["quiz_id"], [q["question_id"] for q in r.json()["questions"]]) for n, r in res.items()}
    for name, backend in pair(w).items():
        qid, (m, t) = ids[name][0], ids[name][1]
        first = backend.request("POST", f"/v1/quiz/{qid}/questions/{m}/respond", json={"selected_key": "B"}).json()
        second = backend.request("POST", f"/v1/quiz/{qid}/questions/{t}/respond", json={"response_text": "x"}).json()
        assert {k: first[k] for k in ("is_correct", "grading_method", "confidence", "feedback")} == {
            "is_correct": True, "grading_method": "EXACT_MATCH", "confidence": 1.0, "feedback": "Correct."}
        assert (second["grading_method"], second["confidence"], second["is_correct"]) == ("LLM_GRADED", 0.9, True)
        assert set(first["solution"]) == set(second["solution"]) == {"solution_text", "key_insight"}
        dup = backend.request("POST", f"/v1/quiz/{qid}/questions/{m}/respond", json={"selected_key": "A"})
        assert (dup.status_code, dup.json()["detail"]["code"]) == (409, "ALREADY_ANSWERED")
        review = backend.request("GET", f"/v1/quiz/{qid}/review").json()
        assert (review["score"], review["total"], review["answered_count"]) == (2, 2, 2)
        assert set(review["questions"][0]) == set(a_review_keys())


def a_review_keys() -> tuple:
    return ("question_id", "ordinal", "question_type", "prompt_text", "points", "student_response", "is_correct", "feedback", "solution_text",
            "key_insight", "options", "correct_answer", "option_explanations", "inspiration_sources", "difficulty_band", "complexity_signals",
            "solution_steps")
