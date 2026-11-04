"""WP6 papers area (requirement 71, requirement 70 C2 sections 4 and 9): the DynamoDB ``PapersDynamoDB`` on moto.

Content comes from the real DynamoDB content store (moto ``mb-content``: catalogue snapshots + two problems); the learner profile is
the cross-table ConditionCheck target. No test touches PostgreSQL or AWS: ``db.postgres.engine`` is replaced by a guard that raises.
"""
from __future__ import annotations

import datetime as dt
import uuid
from types import SimpleNamespace
from uuid import UUID

import pytest
from wp6_papers_support import (
    FakeLLM,
    NoPostgres,
    free_text,
    mcq,
    profile,
    seed_content,
    uid,
)

from mathbank_rest import quiz_logic as ql
from mathbank_rest import stores
from mathbank_rest.config import settings
from mathbank_rest.models.ddb.exam import ExamPaperOwner, ExamResponseOwner
from mathbank_rest.models.manual import exam_papers as ep
from mathbank_rest.quiz_logic import QuizError
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import typed
from mathbank_rest.stores.content import DynamoDBContentStore
from mathbank_rest.stores.exam.papers import PapersDynamoDB

CONCEPT = uid("concept:counting")
TECHNIQUE = uid("technique:pigeonhole")


@pytest.fixture()
def world(content_table, monkeypatch, sid):
    """moto content + learner + exam tables, the DynamoDB content store, PostgreSQL forbidden, the LLM stubbed."""
    from mathbank_rest.db import postgres

    seed_content()
    typed.put(profile(sid))
    monkeypatch.setattr(postgres, "engine", NoPostgres())
    monkeypatch.setattr(settings, "quiz_mastery_inline", False)
    monkeypatch.setattr(settings, "quiz_strict_exam_policy", True)
    llm = FakeLLM()
    monkeypatch.setattr(ql, "_client", lambda: llm.client)
    with stores.override_store("content", DynamoDBContentStore()):
        yield SimpleNamespace(store=PapersDynamoDB(), sid=sid, llm=llm, monkeypatch=monkeypatch)


def pk(sid: str) -> str:
    return toolkit.student_pk(sid)


def start(w, *, exam_mode: bool = True, count: int = 2, band: str | None = "hard", **over) -> UUID:
    return w.store.start_paper(
        UUID(w.sid), style="MIXED", title="Mock", instructions="be quick", requested_question_count=count,
        requested_question_types=["MCQ", "FREE_TEXT"], target_concept_slugs=["counting"], difficulty_band=band,
        generated_by="bedrock:x", exam_mode=exam_mode, time_limit_seconds=5400, **over)


def ready(w, questions: list[dict] | None = None, *, exam_mode: bool = True, **finalize) -> tuple[UUID, dict]:
    qid = start(w, exam_mode=exam_mode, count=len(questions or [0, 0]))
    view = w.store.finalize_paper(qid, UUID(w.sid), questions=questions or [mcq(1), free_text(2)], **finalize)
    return qid, view


def paper_of(w, qid) -> ep.ExamPaperItem:
    return typed.require(ep.ExamPaperItem, pk(w.sid), ep.paper_sk(qid))


def items_of(w, qid, prefix: str = "") -> list[dict]:
    page = toolkit.query_page("exam", pk(w.sid), sk_begins=f"QUIZ#{qid}{prefix}", limit=200)
    return page["items"]


def question_ids(view: dict) -> list[str]:
    return [q["question_id"] for q in view["questions"]]


@pytest.fixture()
def tx(monkeypatch):
    """Every committed transaction as a list of (kind, label) pairs."""
    seen: list[list[tuple[str, str]]] = []
    real = toolkit.transact

    def spy(ops, **kw):
        seen.append([(o.kind, o.label) for o in ops])
        return real(ops, **kw)

    monkeypatch.setattr(toolkit, "transact", spy)
    return seen


# ---------------------------------------------------------------------------------------------------------- start


def test_start_paper_writes_paper_and_owner_and_checks_the_profile(world):
    qid = start(world)
    paper = paper_of(world, qid)
    assert (paper.status, paper.answer_disclosure, paper.agent_framework, paper.version) == ("GENERATING", "AFTER_SUBMIT", "STRANDS_BEDROCK", 1)
    assert (paper.question_count, paper.answered_count, paper.correct_count, paper.diagnosis_version) == (0, 0, 0, 0)
    assert paper.GSI1PK == f"STUDENT#{world.sid}#PAPERS" and paper.GSI2PK == "PAPER_STATUS#GENERATING"
    owner = typed.require(ExamPaperOwner, f"QUIZ#{qid}", "OWNER")
    assert str(owner.student_id) == world.sid
    practice = world.store.start_paper(UUID(world.sid), style="AIME", title="t", requested_question_count=1, requested_question_types=["MCQ"],
                                       generated_by="x", exam_mode=False)
    assert paper_of(world, practice).answer_disclosure == "IMMEDIATE"


def test_a_missing_or_disabled_profile_writes_nothing(world, sid):
    stranger = str(uuid.uuid4())
    with pytest.raises(QuizError) as exc:
        world.store.start_paper(UUID(stranger), style="AIME", title="t", requested_question_count=1, requested_question_types=["MCQ"],
                                generated_by="x")
    assert exc.value.status_code == 404
    assert toolkit.query_page("exam", pk(stranger), limit=10)["items"] == []
    typed.put(profile(world.sid, status="DISABLED"))
    with pytest.raises(QuizError) as exc:
        start(world)
    assert exc.value.status_code == 404


@pytest.mark.parametrize("over,code", [
    ({"style": "NOPE"}, "INVALID_STYLE"),
    ({"requested_question_count": 0}, "INVALID_QUESTION_COUNT"),
    ({"requested_question_count": 21}, "INVALID_QUESTION_COUNT"),
    ({"requested_question_types": ["ESSAY"]}, "INVALID_QUESTION_TYPE"),
    ({"requested_question_types": []}, "INVALID_QUESTION_TYPE"),
    ({"difficulty_band": "impossible"}, "INVALID_DIFFICULTY_BAND"),
    ({"time_limit_seconds": 59}, "INVALID_TIME_LIMIT"),
    ({"time_limit_seconds": 36001}, "INVALID_TIME_LIMIT"),
])
def test_start_paper_enforces_the_check_constraints(world, over, code):
    kw = {"style": "MIXED", "title": "t", "requested_question_count": 1, "requested_question_types": ["MCQ"], "generated_by": "x", **over}
    with pytest.raises(QuizError) as exc:
        world.store.start_paper(UUID(world.sid), **kw)
    assert exc.value.code == code and exc.value.status_code == 422
    assert toolkit.query_page("exam", pk(world.sid), limit=10)["items"] == []


def test_the_difficulty_band_is_lower_cased(world):
    assert paper_of(world, start(world, band="Very_Hard")).difficulty_band == "very_hard"


# -------------------------------------------------------------------------------------------------------- finalize


def test_finalize_writes_paper_questions_and_keys_in_one_transaction(world, tx):
    qid, view = ready(world, [mcq(1, concepts=("counting",), techniques=("pigeonhole",), sources=("AMC10_2005B_Q18", "NOPE", "AMC10_2005B_Q18")),
                              free_text(2)])
    assert [len(t) for t in tx if any(label == "PAPER finalize" for _, label in t)] == [1 + 2 * 2]
    assert [q["ordinal"] for q in view["questions"]] == [1, 2] and view["status"] == "READY"
    paper = paper_of(world, qid)
    assert (paper.status, paper.question_count, paper.GSI2PK) == ("READY", 2, "PAPER_STATUS#READY")
    types = sorted(i["type"] for i in items_of(world, qid))
    assert types == ["PAPER", "QUESTION", "QUESTION", "QUESTION_SECRET", "QUESTION_SECRET"]
    q1 = typed.require(ep.ExamQuestionItem, pk(world.sid), ep.question_sk(qid, view["questions"][0]["question_id"]))
    assert [str(i) for i in q1.concept_ids] == [CONCEPT] and q1.concept_slugs == ["counting"]
    assert [str(i) for i in q1.technique_ids] == [TECHNIQUE]
    assert str(q1.inspired_by_problem_id) == uid("AMC10_2005B_Q18") and q1.difficulty_band == "easy"
    assert q1.complexity_signals.step_count == 1 and q1.complexity_signals.concept_count == 2
    secret = typed.require(ep.ExamQuestionSecretItem, pk(world.sid), ep.secret_sk(qid, view["questions"][0]["question_id"]))
    assert [(s.rank, s.canonical_code) for s in secret.inspiration_sources] == [(1, "AMC10_2005B_Q18")]    # unknown code skipped, dup merged
    assert secret.correct_answer.correct_key == "B" and secret.solution_text == "1+1=2"


def test_finalize_twice_fails_and_a_non_owner_gets_404(world):
    qid, _ = ready(world)
    with pytest.raises(QuizError) as exc:
        world.store.finalize_paper(qid, UUID(world.sid), questions=[mcq(1)])
    assert exc.value.status_code == 404
    other = str(uuid.uuid4())
    typed.put(profile(other))
    fresh = start(world)
    with pytest.raises(QuizError) as exc:
        world.store.finalize_paper(fresh, UUID(other), questions=[mcq(1)])
    assert exc.value.status_code == 404
    assert paper_of(world, fresh).status == "GENERATING"


def test_a_twenty_question_finalize_stays_within_the_transaction_limit(world, tx):
    qid = start(world, count=20)
    world.store.finalize_paper(qid, UUID(world.sid), questions=[mcq(i, concepts=("counting",), sources=("AMC10_2005B_Q18",)) for i in range(1, 21)])
    sizes = [len(t) for t in tx if any(label == "PAPER finalize" for _, label in t)]
    assert sizes == [41] and max(sizes) <= 100
    assert paper_of(world, qid).question_count == 20


def test_finalize_rejects_bad_input_without_touching_the_paper(world):
    qid = start(world)
    for questions, code in ((  [], "NO_QUESTIONS"), ([{**mcq(1), "question_type": "ESSAY"}], "INVALID_QUESTION_TYPE"),
                            ([mcq(i) for i in range(21)], "INVALID_QUESTION_COUNT")):
        with pytest.raises(QuizError) as exc:
            world.store.finalize_paper(qid, UUID(world.sid), questions=questions)
        assert exc.value.code == code
    assert paper_of(world, qid).status == "GENERATING"


def test_finalize_failure_marks_the_paper_failed(world, monkeypatch):
    qid = start(world)
    monkeypatch.setattr("mathbank_rest.stores.exam.papers._resolve_slugs", lambda *a: (_ for _ in ()).throw(RuntimeError("content down")))
    with pytest.raises(QuizError) as exc:
        world.store.finalize_paper(qid, UUID(world.sid), questions=[mcq(1, concepts=("counting",))])
    assert (exc.value.code, exc.value.status_code) == ("GENERATION_FAILED", 502)
    paper = paper_of(world, qid)
    assert paper.status == "FAILED" and "content down" in paper.error_message and paper.GSI2PK == "PAPER_STATUS#FAILED"


def test_the_pool_seam_is_called_before_the_transaction_and_its_ops_join_it(world, monkeypatch, tx):
    calls: list = []
    pool_id = str(uuid.uuid4())

    def link(student_id, quiz_id, doc):
        calls.append((str(student_id), str(quiz_id), doc["style"], doc["paper_difficulty_band"], doc["pool_topic"], doc["pool_concept_slugs"]))
        return pool_id

    def serve(student_id, pool_ids, *, quiz_id):
        calls.append(("serve", list(pool_ids)))
        return [toolkit.Check("exam", f"POOL#{p}", "POOL", toolkit.Cond("attribute_not_exists(PK)")) for p in pool_ids]

    store = PapersDynamoDB()
    monkeypatch.setattr(PapersDynamoDB, "link_or_insert_pool_question", lambda self, *a: link(*a), raising=False)
    monkeypatch.setattr(PapersDynamoDB, "build_pool_serve_ops", lambda self, *a, **k: serve(*a, **k), raising=False)
    qid = start(world)
    world.store = store
    view = store.finalize_paper(qid, UUID(world.sid), questions=[mcq(1, add_to_pool=True), mcq(2)], pool_topic="Counting", pool_concept_slugs=["counting"])
    assert calls[0] == (world.sid, str(qid), "MIXED", "hard", "Counting", ["counting"]) and calls[1] == ("serve", [pool_id])
    q1 = typed.require(ep.ExamQuestionItem, pk(world.sid), ep.question_sk(qid, view["questions"][0]["question_id"]))
    assert str(q1.pool_question_id) == pool_id
    assert any(kind == "check" for kind, _ in tx[-1]) and len(tx[-1]) == 1 + 4 + 1


def test_the_batched_pool_seam_gets_every_question_once_and_a_failure_links_nothing(world, monkeypatch, tx):
    served, written = str(uuid.uuid4()), str(uuid.uuid4())
    seen: list = []

    def batch(self, student_id, quiz_id, docs):
        seen.append([(d.get("pool_question_id"), d.get("add_to_pool"), d["style"]) for d in docs])
        return [served, written, None, None]

    monkeypatch.setattr(PapersDynamoDB, "link_or_insert_pool_questions", batch, raising=False)
    monkeypatch.setattr(PapersDynamoDB, "build_pool_serve_ops", lambda self, sid_, ids, *, quiz_id: [], raising=False)
    qid = start(world, count=4)
    served_doc = mcq(1, pool_question_id=uuid.UUID(served))
    view = PapersDynamoDB().finalize_paper(qid, UUID(world.sid), questions=[served_doc, mcq(2, add_to_pool=True), mcq(3, add_to_pool=True), mcq(4)])
    assert seen == [[(uuid.UUID(served), False, "MIXED"), (None, True, "MIXED"), (None, True, "MIXED"), (None, False, "MIXED")]]
    linked = [typed.require(ep.ExamQuestionItem, pk(world.sid), ep.question_sk(qid, q["question_id"])).pool_question_id for q in view["questions"]]
    assert [str(p) if p else None for p in linked] == [served, written, None, None]
    monkeypatch.setattr(PapersDynamoDB, "link_or_insert_pool_questions", lambda *a: (_ for _ in ()).throw(RuntimeError("vectors down")), raising=False)
    again = start(world, count=1)
    done = PapersDynamoDB().finalize_paper(again, UUID(world.sid), questions=[mcq(1, pool_question_id=uuid.UUID(served))])
    assert done["status"] == "READY"
    only = typed.require(ep.ExamQuestionItem, pk(world.sid), ep.question_sk(again, done["questions"][0]["question_id"]))
    assert only.pool_question_id is None


# ------------------------------------------------------------------------------------------------------ fail / view


def test_fail_acts_only_from_generating(world):
    qid = start(world)
    view = world.store.fail_paper(qid, UUID(world.sid), "critic rejected" * 100)
    assert view["status"] == "FAILED" and len(paper_of(world, qid).error_message) == 500
    ready_id, _ = ready(world)
    again = world.store.fail_paper(ready_id, UUID(world.sid), "late")
    assert again["status"] == "READY" and paper_of(world, ready_id).error_message is None
    with pytest.raises(QuizError) as exc:
        world.store.fail_paper(uuid.uuid4(), UUID(world.sid), "x")
    assert exc.value.status_code == 404


def test_get_quiz_is_the_allow_listed_view_and_a_foreign_paper_is_404(world):
    qid, view = ready(world)
    got = world.store.get_quiz(qid, UUID(world.sid))
    assert got == view
    assert set(got) == {"quiz_id", "style", "title", "status", "instructions", "exam_mode", "time_limit_seconds", "started_at",
                        "resume_question_ordinal", "questions"}
    assert set(got["questions"][0]) == {"question_id", "ordinal", "question_type", "prompt_text", "prompt_latex", "options", "points",
                                        "has_diagram", "student_response", "draft_response", "answered"}
    assert got["questions"][0]["options"][1] == {"key": "B", "text": "2"} and got["questions"][1]["options"] is None
    assert got["questions"][0]["points"] == 1.0
    other = str(uuid.uuid4())
    typed.put(profile(other))
    for call in (lambda: world.store.get_quiz(qid, UUID(other)), lambda: world.store.get_paper_header(qid, UUID(other)),
                 lambda: world.store.get_review(qid, UUID(other))):
        with pytest.raises(QuizError) as exc:
            call()
        assert exc.value.status_code == 404


def test_get_quiz_reads_only_the_learner_key_range(world, monkeypatch):
    qid, _ = ready(world)
    ranges = []
    real = toolkit.query_page

    def spy(ctx, pk_, **kw):
        ranges.append(kw.get("sk_between") or kw.get("sk_begins"))
        return real(ctx, pk_, **kw)

    monkeypatch.setattr(toolkit, "query_page", spy)
    world.store.get_quiz(qid, UUID(world.sid))
    assert ranges == [(f"QUIZ#{qid}#P#", f"QUIZ#{qid}#P#\uffff")]
    assert f"QUIZ#{qid}#S#KEY#" > ranges[0][1]


def test_list_my_quizzes_comes_from_the_gsi_newest_first(world):
    first, _ = ready(world)
    second = start(world)
    rows = world.store.list_my_quizzes(UUID(world.sid))
    assert [r["quiz_id"] for r in rows] == [str(second), str(first)]
    assert set(rows[0]) == {"quiz_id", "style", "title", "status", "created_at", "question_count", "correct_count"}
    assert rows[1]["question_count"] == 2 and isinstance(rows[0]["created_at"], dt.datetime)
    assert len(world.store.list_my_quizzes(UUID(world.sid), limit=1)) == 1
    assert world.store.list_my_quizzes(UUID(str(uuid.uuid4()))) == []


def test_get_paper_header_has_the_columns_of_the_paper(world):
    qid, _ = ready(world)
    head = world.store.get_paper_header(qid, UUID(world.sid))
    assert head["status"] == "READY" and head["exam_mode"] is True and head["time_limit_seconds"] == 5400
    assert head["requested_question_types"] == ["MCQ", "FREE_TEXT"] and head["resume_question_ordinal"] is None


# ----------------------------------------------------------------------------------------------------- progress


def test_save_progress_starts_the_clock_once_and_keeps_a_draft(world):
    qid, view = ready(world)
    q1, q2 = question_ids(view)
    assert world.store.save_exam_progress(qid, UUID(world.sid), current_question_ordinal=1, question_id=UUID(q1),
                                          raw_response={"selected_key": "A"}) == {"saved": True, "current_question_ordinal": 1}
    paper = paper_of(world, qid)
    assert (paper.status, paper.resume_question_ordinal, paper.GSI2PK) == ("IN_PROGRESS", 1, "PAPER_STATUS#IN_PROGRESS")
    started = paper.started_at
    assert started is not None
    draft = typed.require(ep.ExamDraft, pk(world.sid), ep.draft_sk(qid, q1))
    assert draft.raw_response == {"selected_key": "A"} and abs(draft.ttl - toolkit.epoch_after(90)) < 120
    world.store.save_exam_progress(qid, UUID(world.sid), current_question_ordinal=2)
    again = paper_of(world, qid)
    assert again.started_at == started and again.resume_question_ordinal == 2 and again.version == paper.version + 1
    got = world.store.get_quiz(qid, UUID(world.sid))
    assert got["questions"][0]["draft_response"] == {"selected_key": "A"} and got["resume_question_ordinal"] == 2
    assert q2 in question_ids(got)


def test_save_progress_validates_the_draft_and_the_position(world):
    qid, view = ready(world)
    q1 = view["questions"][0]["question_id"]
    for kwargs, code, status in (({"current_question_ordinal": 1, "raw_response": {"selected_key": "Z"}}, "INVALID_DRAFT", 422),
                                 ({"current_question_ordinal": 1, "raw_response": {"selected_key": "A", "x": 1}}, "INVALID_DRAFT", 422),
                                 ({"current_question_ordinal": 1, "question_id": uuid.uuid4()}, "INVALID_DRAFT", 422),
                                 ({"current_question_ordinal": 9}, "NOT_FOUND", 404)):
        with pytest.raises(QuizError) as exc:
            world.store.save_exam_progress(qid, UUID(world.sid), **kwargs)
        assert (exc.value.code, exc.value.status_code) == (code, status)
    assert paper_of(world, qid).status == "READY" and items_of(world, qid, f"#P#DRAFT#{q1}") == []


def test_a_draft_for_an_answered_question_is_409_and_nothing_is_written(world):
    qid, view = ready(world)
    q1 = view["questions"][0]["question_id"]
    world.store.submit_response(qid, UUID(q1), UUID(world.sid), raw_response={"selected_key": "B"})
    before = paper_of(world, qid)
    with pytest.raises(QuizError) as exc:
        world.store.save_exam_progress(qid, UUID(world.sid), current_question_ordinal=1, raw_response={"selected_key": "A"})
    assert (exc.value.code, exc.value.status_code) == ("ALREADY_ANSWERED", 409)
    assert paper_of(world, qid).version == before.version and items_of(world, qid, f"#P#DRAFT#{q1}") == []
    world.store.save_exam_progress(qid, UUID(world.sid), current_question_ordinal=2)          # a position alone is fine


@pytest.mark.parametrize("status", ["GENERATING", "FAILED", "GRADED"])
def test_progress_and_respond_need_a_ready_or_in_progress_paper(world, status):
    qid, view = ready(world)
    if status == "GENERATING":
        qid = start(world)
    elif status == "FAILED":
        qid = start(world)
        world.store.fail_paper(qid, UUID(world.sid), "x")
    else:
        world.store.submit_exam(qid, UUID(world.sid))
    for call in (lambda: world.store.save_exam_progress(qid, UUID(world.sid), current_question_ordinal=1),
                 lambda: world.store.submit_response(qid, UUID(view["questions"][0]["question_id"]), UUID(world.sid),
                                                     raw_response={"selected_key": "B"})):
        with pytest.raises(QuizError) as exc:
            call()
        assert (exc.value.code, exc.value.status_code) == ("EXAM_NOT_EDITABLE", 409)


# ------------------------------------------------------------------------------------------------------- respond


def test_respond_grades_writes_evidence_and_counts(world, tx):
    qid, view = ready(world, [mcq(1, concepts=("counting",), techniques=("pigeonhole",), band=None), free_text(2)])
    q1 = question_ids(view)[0]
    world.store.save_exam_progress(qid, UUID(world.sid), current_question_ordinal=1, raw_response={"selected_key": "A"})
    body = world.store.submit_response(qid, UUID(q1), UUID(world.sid), raw_response={"selected_key": "A"}, time_spent_seconds=40)
    assert body == {"saved": True, "question_id": q1, "answered_count": 1}                      # exam mode: nothing else
    resp = typed.require(ep.ExamResponseItem, pk(world.sid), ep.response_sk(qid, q1))
    assert (resp.is_correct, resp.grading_method, resp.grading_confidence, resp.time_spent_seconds, resp.version) == (False, "EXACT_MATCH", 1.0, 40, 1)
    assert resp.grading_feedback == "The correct answer was B."
    assert typed.require(ExamResponseOwner, f"RESPONSE#{resp.response_id}", "OWNER").question_id == UUID(q1)
    assert items_of(world, qid, f"#P#DRAFT#{q1}") == []                                        # the draft went with the answer
    evidence = [i for i in toolkit.query_page("exam", pk(world.sid), sk_begins="QEVID#", limit=50)["items"]]
    assert sorted((i["SK"].split("#")[1], i["is_correct"], i["difficulty_band"]) for i in evidence) == [("C", False, "hard"), ("T", False, "hard")]
    paper = paper_of(world, qid)
    assert (paper.status, paper.answered_count, paper.correct_count, paper.GSI2PK) == ("IN_PROGRESS", 1, 0, "PAPER_STATUS#IN_PROGRESS")
    assert [len(t) for t in tx if any(label == "PAPER respond" for _, label in t)] == [1 + 1 + 2 + 1 + 1]
    assert paper.started_at is not None and paper.graded_at is None


def test_the_question_band_wins_over_the_paper_band_in_the_evidence(world):
    qid, view = ready(world, [mcq(1, concepts=("counting",), band="medium")])
    world.store.submit_response(qid, UUID(view["questions"][0]["question_id"]), UUID(world.sid), raw_response={"selected_key": "B"})
    (item,) = toolkit.query_page("exam", pk(world.sid), sk_begins="QEVID#C#", limit=5)["items"]
    assert item["difficulty_band"] == "medium" and item["is_correct"] is True


def test_a_duplicate_respond_is_409_and_writes_no_second_evidence(world):
    qid, view = ready(world, [mcq(1, concepts=("counting",)), mcq(2)])
    q1 = UUID(view["questions"][0]["question_id"])
    world.store.submit_response(qid, q1, UUID(world.sid), raw_response={"selected_key": "B"})
    before = paper_of(world, qid)
    with pytest.raises(QuizError) as exc:
        world.store.submit_response(qid, q1, UUID(world.sid), raw_response={"selected_key": "A"})
    assert (exc.value.code, exc.value.status_code) == ("ALREADY_ANSWERED", 409)
    assert len(toolkit.query_page("exam", pk(world.sid), sk_begins="QEVID#", limit=50)["items"]) == 1
    after = paper_of(world, qid)
    assert (after.answered_count, after.version) == (before.answered_count, before.version)


def test_the_lost_race_of_a_duplicate_inside_the_transaction_is_still_already_answered(world, monkeypatch):
    qid, view = ready(world, [mcq(1, concepts=("counting",)), mcq(2)])
    q1 = UUID(view["questions"][0]["question_id"])
    real = world.store._pp_paper
    first = {"done": False}

    def racing_paper(quiz_id, student_id):
        paper = real(quiz_id, student_id)
        if not first["done"] and paper.answered_count == 0:        # the competing request commits between our read and our commit
            first["done"] = True
            PapersDynamoDB().submit_response(qid, q1, UUID(world.sid), raw_response={"selected_key": "B"})
        return paper

    monkeypatch.setattr(world.store, "_pp_paper", racing_paper)
    with pytest.raises(QuizError) as exc:
        world.store.submit_response(qid, q1, UUID(world.sid), raw_response={"selected_key": "A"})
    assert exc.value.code == "ALREADY_ANSWERED"
    assert len(toolkit.query_page("exam", pk(world.sid), sk_begins="QEVID#", limit=50)["items"]) == 1
    assert paper_of(world, qid).answered_count == 1


def test_a_version_race_retries_without_grading_again(world, monkeypatch):
    qid, view = ready(world, [free_text(1), free_text(2)])
    q1, q2 = (UUID(q) for q in question_ids(view))
    real = world.store._pp_paper
    raced = {"n": 0}

    def racing_paper(quiz_id, student_id):
        paper = real(quiz_id, student_id)
        if raced["n"] < 2 and paper.answered_count == raced["n"]:   # two other answers land after our first two reads
            raced["n"] += 1
            other = q2 if raced["n"] == 1 else None
            if other is not None:
                PapersDynamoDB().submit_response(qid, other, UUID(world.sid), raw_response={"response_text": "2"})
            else:
                PapersDynamoDB().save_exam_progress(qid, UUID(world.sid), current_question_ordinal=1)
        return paper

    monkeypatch.setattr(world.store, "_pp_paper", racing_paper)
    monkeypatch.setattr("time.sleep", lambda _s: None)
    calls_before = world.llm.calls.count("grading_result")
    body = world.store.submit_response(qid, q1, UUID(world.sid), raw_response={"response_text": "2"})
    graded = world.llm.calls.count("grading_result") - calls_before
    assert graded == 2 and body["answered_count"] == 2          # one grading for the competing request, ONE for ours: no regrade
    assert paper_of(world, qid).answered_count == 2


def test_free_text_is_graded_by_the_llm_once(world):
    qid, view = ready(world, [free_text(1)], exam_mode=False)
    body = world.store.submit_response(qid, UUID(view["questions"][0]["question_id"]), UUID(world.sid), raw_response={"response_text": "2"})
    assert world.llm.calls.count("grading_result") == 1
    assert (body["grading_method"], body["confidence"], body["is_correct"]) == ("LLM_GRADED", 0.9, True)
    assert body["solution"] == {"solution_text": "1+1=2", "key_insight": "addition"}


def test_practice_respond_returns_the_grading_and_the_last_answer_grades_the_paper(world):
    qid, view = ready(world, [mcq(1), mcq(2)], exam_mode=False)
    q1, q2 = (UUID(q) for q in question_ids(view))
    first = world.store.submit_response(qid, q1, UUID(world.sid), raw_response={"selected_key": "B"})
    assert set(first) == {"is_correct", "grading_method", "confidence", "feedback", "solution"} and first["feedback"] == "Correct."
    assert paper_of(world, qid).status == "IN_PROGRESS"
    world.store.submit_response(qid, q2, UUID(world.sid), raw_response={"selected_key": "A"})
    paper = paper_of(world, qid)
    assert (paper.status, paper.answered_count, paper.correct_count, paper.GSI2PK) == ("GRADED", 2, 1, "PAPER_STATUS#GRADED")
    assert paper.graded_at is not None and paper.submitted_at is not None
    with pytest.raises(QuizError) as exc:                       # a retry of an answer the closed paper already holds
        world.store.submit_response(qid, q1, UUID(world.sid), raw_response={"selected_key": "B"})
    assert exc.value.code == "ALREADY_ANSWERED"


def test_strict_policy_off_restores_the_full_exam_respond(world, monkeypatch):
    monkeypatch.setattr(settings, "quiz_strict_exam_policy", False)
    qid, view = ready(world, [mcq(1)])
    body = world.store.submit_response(qid, UUID(view["questions"][0]["question_id"]), UUID(world.sid), raw_response={"selected_key": "B"})
    assert body["is_correct"] is True and "saved" not in body


def test_unknown_question_and_unknown_paper_are_404(world):
    qid, _ = ready(world)
    for call in (lambda: world.store.submit_response(qid, uuid.uuid4(), UUID(world.sid), raw_response={"selected_key": "A"}),
                 lambda: world.store.submit_response(uuid.uuid4(), uuid.uuid4(), UUID(world.sid), raw_response={"selected_key": "A"}),
                 lambda: world.store.get_quiz(uuid.uuid4(), UUID(world.sid))):
        with pytest.raises(QuizError) as exc:
            call()
        assert exc.value.status_code == 404


def test_respond_absorbs_mastery_after_the_commit_and_never_fails_on_it(world, monkeypatch):
    monkeypatch.setattr(settings, "quiz_mastery_inline", True)
    seen = []
    monkeypatch.setattr("mathbank_rest.mastery.recompute_concept_mastery", lambda s, c: seen.append(("C", str(c))))
    monkeypatch.setattr("mathbank_rest.mastery.recompute_technique_mastery", lambda s, t: (_ for _ in ()).throw(RuntimeError("learner down")))
    qid, view = ready(world, [mcq(1, concepts=("counting",), techniques=("pigeonhole",))])
    body = world.store.submit_response(qid, UUID(view["questions"][0]["question_id"]), UUID(world.sid), raw_response={"selected_key": "B"})
    assert body["saved"] is True and seen == [("C", CONCEPT)]


# --------------------------------------------------------------------------------------------------------- events


def test_response_events_are_ordered_and_validated(world):
    qid, view = ready(world)
    q1 = UUID(view["questions"][0]["question_id"])
    now_ms = int(dt.datetime.now(dt.UTC).timestamp() * 1000)
    out = world.store.log_response_event(qid, q1, UUID(world.sid), event_type="SELECT_OPTION", option_key="A", client_timestamp_ms=now_ms)
    assert set(out) == {"event_id", "event_type", "option_key"} and out["option_key"] == "A"
    world.store.log_response_event(qid, q1, UUID(world.sid), event_type="SELECT_OPTION", option_key="B", client_timestamp_ms=now_ms - 90_000_000)
    world.store.log_response_event(qid, q1, UUID(world.sid), event_type="VIEW")
    events = world.store.get_response_events(qid, UUID(world.sid))
    assert [(e["event_type"], e["option_key"], e["ordinal"]) for e in events] == [("SELECT_OPTION", "A", 1), ("SELECT_OPTION", "B", 1), ("VIEW", None, 1)]
    assert [e["client_timestamp_ms"] for e in events] == [now_ms, None, None]        # more than a day away: not trusted
    assert [e["created_at"] for e in events] == sorted(e["created_at"] for e in events)
    assert set(events[0]) == {"question_id", "ordinal", "event_type", "option_key", "client_timestamp_ms", "created_at"}


@pytest.mark.parametrize("kwargs,code,status", [
    ({"event_type": "NOPE"}, "INVALID_EVENT_TYPE", 422),
    ({"event_type": "VIEW", "option_key": "x" * 11}, "INVALID_OPTION_KEY", 422),
])
def test_response_event_validation(world, kwargs, code, status):
    qid, view = ready(world)
    with pytest.raises(QuizError) as exc:
        world.store.log_response_event(qid, UUID(view["questions"][0]["question_id"]), UUID(world.sid), **kwargs)
    assert (exc.value.code, exc.value.status_code) == (code, status)
    assert world.store.get_response_events(qid, UUID(world.sid)) == []


def test_an_event_for_an_unknown_question_or_a_foreign_paper_is_404(world):
    qid, view = ready(world)
    q1 = UUID(view["questions"][0]["question_id"])
    other = str(uuid.uuid4())
    typed.put(profile(other))
    for call in (lambda: world.store.log_response_event(qid, uuid.uuid4(), UUID(world.sid), event_type="VIEW"),
                 lambda: world.store.log_response_event(qid, q1, UUID(other), event_type="VIEW"),
                 lambda: world.store.get_response_events(qid, UUID(other))):
        with pytest.raises(QuizError) as exc:
            call()
        assert exc.value.status_code == 404


def test_a_skip_event_deletes_the_draft(world):
    qid, view = ready(world)
    q1 = view["questions"][0]["question_id"]
    world.store.save_exam_progress(qid, UUID(world.sid), current_question_ordinal=1, raw_response={"selected_key": "A"})
    assert len(items_of(world, qid, f"#P#DRAFT#{q1}")) == 1
    world.store.log_response_event(qid, UUID(q1), UUID(world.sid), event_type="VIEW")
    assert len(items_of(world, qid, f"#P#DRAFT#{q1}")) == 1
    world.store.log_response_event(qid, UUID(q1), UUID(world.sid), event_type="SKIP")
    assert items_of(world, qid, f"#P#DRAFT#{q1}") == []


def test_events_are_append_only_by_construction(world):
    from mathbank_rest.stores.errors import ValidationFailed
    from mathbank_rest.stores.exam.uow import ExamUnitOfWork

    uow = ExamUnitOfWork(world.sid)
    with pytest.raises(ValidationFailed):
        uow.delete(ep.ExamResponseEventItem, pk(world.sid), "QUIZ#x#T#EVT#t#e")
    with pytest.raises(ValidationFailed):
        uow.update(ep.ExamGenerationEventItem, pk(world.sid), "QUIZ#x#T#GEN#000001", {"detail": "x"})


# ---------------------------------------------------------------------------------------------- generation events


def test_generation_events_resolve_the_owner_and_are_idempotent_on_the_ordinal(world):
    qid = start(world)
    world.store.post_generation_event(qid, ordinal=1, phase="INTAKE", status="STARTED", detail="go")
    world.store.post_generation_event(qid, ordinal=2, phase="DRAFT_QUESTION", status="DONE", question_ordinal=1, detail="q1")
    world.store.post_generation_event(qid, ordinal=2, phase="DRAFT_QUESTION", status="FAILED", question_ordinal=1, detail="again")
    events = world.store.list_generation_events(qid, UUID(world.sid))
    assert [(e["ordinal"], e["phase"], e["status"], e["question_ordinal"], e["detail"]) for e in events] == [
        (1, "INTAKE", "STARTED", None, "go"), (2, "DRAFT_QUESTION", "DONE", 1, "q1")]
    assert [e["ordinal"] for e in world.store.list_generation_events(qid, UUID(world.sid), since_ordinal=1)] == [2]
    assert world.store.list_generation_events(qid, UUID(world.sid), since_ordinal=2) == []
    gen = typed.require(ep.ExamGenerationEventItem, pk(world.sid), ep.generation_sk(qid, 1))
    assert abs(gen.ttl - toolkit.epoch_after(180)) < 120 and str(gen.student_id) == world.sid


def test_generation_event_errors(world):
    qid = start(world)
    for kwargs, code, status in (({"phase": "NOPE", "status": "DONE"}, "INVALID_PHASE", 422),
                                 ({"phase": "DONE", "status": "NOPE"}, "INVALID_STATUS", 422),
                                 ({"phase": "DONE", "status": "DONE", "ordinal": 0}, "INVALID_ORDINAL", 422)):
        with pytest.raises(QuizError) as exc:
            world.store.post_generation_event(qid, **{"ordinal": 1, **kwargs})
        assert (exc.value.code, exc.value.status_code) == (code, status)
    with pytest.raises(QuizError) as exc:
        world.store.post_generation_event(uuid.uuid4(), ordinal=1, phase="INTAKE", status="STARTED")
    assert exc.value.status_code == 404
    assert world.store.list_generation_events(qid, UUID(world.sid)) == []


def test_generation_events_follow_the_paper_state(world):
    qid, _ = ready(world)
    world.store.post_generation_event(qid, ordinal=1, phase="PERSIST", status="DONE")           # READY still takes the agent's last events
    world.store.save_exam_progress(qid, UUID(world.sid), current_question_ordinal=1)             # IN_PROGRESS
    with pytest.raises(QuizError) as exc:
        world.store.post_generation_event(qid, ordinal=2, phase="DONE", status="DONE")
    assert (exc.value.code, exc.value.status_code) == ("EXAM_NOT_EDITABLE", 409)
    assert [e["ordinal"] for e in world.store.list_generation_events(qid, UUID(world.sid))] == [1]
    failed = start(world)
    world.store.fail_paper(failed, UUID(world.sid), "x")
    world.store.post_generation_event(failed, ordinal=1, phase="FAILED", status="FAILED")


# ---------------------------------------------------------------------------------------------- submit and review


def test_submit_from_generating_is_409_and_submit_deletes_drafts_and_grades(world):
    gen = start(world)
    with pytest.raises(QuizError) as exc:
        world.store.submit_exam(gen, UUID(world.sid))
    assert (exc.value.code, exc.value.status_code) == ("EXAM_NOT_EDITABLE", 409)
    qid, view = ready(world)
    q1 = view["questions"][0]["question_id"]
    world.store.save_exam_progress(qid, UUID(world.sid), current_question_ordinal=1, raw_response={"selected_key": "A"})
    world.store.submit_response(qid, UUID(question_ids(view)[1]), UUID(world.sid), raw_response={"response_text": "4"})
    review = world.store.submit_exam(qid, UUID(world.sid))
    paper = paper_of(world, qid)
    assert (paper.status, paper.GSI2PK) == ("GRADED", "PAPER_STATUS#GRADED") and paper.submitted_at and paper.graded_at
    assert items_of(world, qid, f"#P#DRAFT#{q1}") == []
    assert (review["answered_count"], review["score"], review["total"]) == (1, 1, 2)
    with pytest.raises(QuizError) as exc:
        world.store.submit_exam(qid, UUID(world.sid))
    assert (exc.value.code, exc.value.status_code) == ("ALREADY_SUBMITTED", 409)


def test_review_is_409_until_the_exam_is_submitted_and_is_a_pure_read(world):
    qid, view = ready(world, [mcq(1, sources=("AMC10_2005B_Q18", "AIME_2010I_Q3")), mcq(2)])
    q1, q2 = question_ids(view)
    world.store.submit_response(qid, UUID(q1), UUID(world.sid), raw_response={"selected_key": "B"})
    world.store.submit_response(qid, UUID(q2), UUID(world.sid), raw_response={"selected_key": "A"})      # every question answered, still IN_PROGRESS
    for _ in range(2):
        with pytest.raises(QuizError) as exc:
            world.store.get_review(qid, UUID(world.sid))
        assert (exc.value.code, exc.value.status_code) == ("EXAM_IN_PROGRESS", 409)
    assert paper_of(world, qid).status == "IN_PROGRESS"
    world.store.submit_exam(qid, UUID(world.sid))
    version = paper_of(world, qid).version
    review = world.store.get_review(qid, UUID(world.sid))
    assert paper_of(world, qid).version == version                                                         # reading changed nothing
    first, second = review["questions"]
    assert set(first) == {"question_id", "ordinal", "question_type", "prompt_text", "points", "student_response", "is_correct", "feedback",
                          "solution_text", "key_insight", "options", "correct_answer", "option_explanations", "inspiration_sources",
                          "difficulty_band", "complexity_signals", "solution_steps"}
    assert (first["is_correct"], second["is_correct"], review["score"]) == (True, False, 1)
    assert first["correct_answer"] == {"correct_key": "B"} and first["solution_steps"] == ["add"] and first["difficulty_band"] == "easy"
    assert first["inspiration_sources"] == [
        {"canonical_code": "AMC10_2005B_Q18", "competition": "AMC 10", "year": 2005, "source_url": "https://example.org/AMC10_2005B_Q18",
         "note": "borrowed from AMC10_2005B_Q18"},
        {"canonical_code": "AIME_2010I_Q3", "competition": "AIME", "year": 2010, "source_url": "https://example.org/AIME_2010I_Q3",
         "note": "borrowed from AIME_2010I_Q3"}]
    assert second["inspiration_sources"] == [] and first["student_response"] == {"selected_key": "B"}


def test_a_practice_paper_can_be_reviewed_any_time(world):
    qid, _ = ready(world, [mcq(1)], exam_mode=False)
    assert world.store.get_review(qid, UUID(world.sid))["answered_count"] == 0


# ----------------------------------------------------------------------------------------------------- diagnosis


def test_diagnosis_needs_a_graded_paper_and_keeps_versions(world):
    qid, _ = ready(world)
    kwargs = {"time_management_verdict": "fine", "pacing_notes": [{"question_ordinal": 1}], "reasoning_guidance": [],
              "improvement_areas": [{"concept_or_technique": "x"}], "generated_by": "agent"}
    with pytest.raises(QuizError) as exc:
        world.store.write_diagnosis(qid, UUID(world.sid), **kwargs)
    assert (exc.value.code, exc.value.status_code) == ("NOT_GRADED", 409)
    with pytest.raises(QuizError) as exc:
        world.store.get_diagnosis(qid, UUID(world.sid))
    assert exc.value.status_code == 404
    world.store.submit_exam(qid, UUID(world.sid))
    first = world.store.write_diagnosis(qid, UUID(world.sid), **kwargs)
    assert set(first) == {"quiz_id", "time_management_verdict", "pacing_notes", "reasoning_guidance", "improvement_areas", "generated_by", "created_at"}
    second = world.store.write_diagnosis(qid, UUID(world.sid), **{**kwargs, "time_management_verdict": "better"})
    assert second["time_management_verdict"] == "better" and world.store.get_diagnosis(qid, UUID(world.sid)) == second
    assert paper_of(world, qid).diagnosis_version == 2
    assert sorted(i["SK"].rsplit("#", 1)[1] for i in items_of(world, qid, "#X#DIAG#")) == ["0001", "0002"]
    assert first["pacing_notes"] == [{"question_ordinal": 1}]


def test_diagnosis_input_joins_mastery_through_the_learner_store(world):
    qid, view = ready(world, [mcq(1, concepts=("counting",), techniques=("pigeonhole",), band="medium"), mcq(2)])
    q1 = question_ids(view)[0]
    world.store.submit_response(qid, UUID(q1), UUID(world.sid), raw_response={"selected_key": "B"}, time_spent_seconds=45)
    world.store.submit_exam(qid, UUID(world.sid))

    class Learner:
        def get_mastery_summary(self, student_id):
            return {"concepts": [{"slug": "counting", "mastery_score": 0.42}, {"slug": "other", "mastery_score": 0.9}],
                    "techniques": [{"slug": "pigeonhole", "mastery_score": 0.7}]}

    with stores.override_store("learner", Learner()):
        data = world.store.get_paper_for_diagnosis(qid, UUID(world.sid))
    assert set(data) == {"quiz_id", "style", "time_limit_seconds", "started_at", "submitted_at", "questions", "concept_mastery_pre_exam",
                         "technique_mastery_pre_exam"}
    assert data["concept_mastery_pre_exam"] == {"counting": 0.42} and data["technique_mastery_pre_exam"] == {"pigeonhole": 0.7}
    first, second = data["questions"]
    assert (first["is_correct"], first["time_spent_seconds"], first["difficulty_band"], first["concept_slugs"], first["technique_slugs"]) == (
        True, 45, "medium", ["counting"], ["pigeonhole"])
    assert (second["is_correct"], second["student_response"], second["concept_slugs"]) == (None, None, [])
    assert set(first) == {"question_id", "ordinal", "question_type", "prompt_text", "difficulty_band", "is_correct", "time_spent_seconds",
                          "student_response", "solution_text", "key_insight", "concept_slugs", "technique_slugs", "skill_slugs"}
    assert first["skill_slugs"] == [] and second["skill_slugs"] == []                                    # QUZ-F04: skills are read back too


# -------------------------------------------------------------------------------------------------- A18 and signals


def test_quiz_evidence_is_ordered_by_submission_time(world):
    qid, view = ready(world, [mcq(1, concepts=("counting",)), mcq(2, concepts=("counting",), techniques=("pigeonhole",), band=None)])
    q1, q2 = question_ids(view)
    world.store.submit_response(qid, UUID(q2), UUID(world.sid), raw_response={"selected_key": "A"})
    world.store.submit_response(qid, UUID(q1), UUID(world.sid), raw_response={"selected_key": "B"})
    rows = world.store.get_quiz_evidence(UUID(world.sid), "C", UUID(CONCEPT))
    assert [(r["is_correct"], r["hint_count"], r["difficulty_band"]) for r in rows] == [(False, 0, "hard"), (True, 0, "easy")]
    assert rows[0]["attempted_at"] < rows[1]["attempted_at"]
    assert [r["is_correct"] for r in world.store.get_quiz_evidence(UUID(world.sid), "T", UUID(TECHNIQUE))] == [False]
    assert world.store.get_quiz_evidence(UUID(world.sid), "C", uuid.uuid4()) == []
    assert world.store.get_quiz_evidence(UUID(str(uuid.uuid4())), "C", UUID(CONCEPT)) == []


def test_difficulty_distribution_counts_problems_by_band(world):
    assert world.store.get_difficulty_distribution(concept_slug="counting") == {"distribution": {"hard": 1, "very_hard": 1}}
    assert world.store.get_difficulty_distribution(concept_slug="unknown") == {"distribution": {}}
    assert world.store.get_difficulty_distribution(technique_slug="pigeonhole") == {"distribution": {}}


# --------------------------------------------------------------------------------------------- practice generation


def test_the_practice_flow_persists_the_paper_in_one_transaction(world, monkeypatch, tx):
    monkeypatch.setattr("mathbank_rest.db.hybrid_search.search_problems",
                        lambda *a, **k: {"results": [{"canonical_code": "AMC10_2005B_Q18", "statement_text": "s", "competition": "AMC 10", "year": 2005}]})
    view = world.store.generate_quiz(UUID(world.sid), style="PROOF_BASED", question_count=2, question_types=["MCQ", "FREE_TEXT"],
                                     target_concept_slugs=["counting"], target_skill_slugs=["case-analysis", "nope"])
    assert view["status"] == "READY" and [q["question_type"] for q in view["questions"]] == ["MCQ", "FREE_TEXT"]
    assert view["title"] == "Proof Based Practice Set" and view["exam_mode"] is False
    qid = UUID(view["quiz_id"])
    paper = paper_of(world, qid)
    assert (paper.agent_framework, paper.answer_disclosure, paper.generated_by, paper.question_count) == ("OPENAI_DIRECT", "IMMEDIATE", ql.MODEL_NAME, 2)
    assert paper.object_key == f"exam/papers/{qid}/paper.json"
    assert toolkit.client("s3").head_object(Bucket=toolkit.data_bucket(), Key=paper.object_key)["ContentLength"] > 10
    sizes = [len(t) for t in tx if any(label == "PAPER persist" for _, label in t)]
    assert sizes == [1 + 2 * 2] and max(sizes) <= 41
    q1 = typed.require(ep.ExamQuestionItem, pk(world.sid), ep.question_sk(qid, view["questions"][0]["question_id"]))
    assert [str(i) for i in q1.concept_ids] == [CONCEPT] and str(q1.inspired_by_problem_id) == uid("AMC10_2005B_Q18")
    q2 = typed.require(ep.ExamQuestionItem, pk(world.sid), ep.question_sk(qid, view["questions"][1]["question_id"]))
    assert [str(i) for i in q2.skill_ids] == [uid("skill:case-analysis")]
    secret = typed.require(ep.ExamQuestionSecretItem, pk(world.sid), ep.secret_sk(qid, view["questions"][0]["question_id"]))
    assert secret.correct_answer.correct_key == "B" and toolkit.client("s3").head_object(Bucket=toolkit.data_bucket(), Key=secret.solution_object_key)
    assert "diagram_plan" not in world.llm.calls                                                         # PROOF_BASED: no diagram call


def test_the_practice_flow_with_no_targets_uses_the_weakest_areas(world, monkeypatch):
    monkeypatch.setattr("mathbank_rest.db.hybrid_search.search_problems", lambda *a, **k: {"results": []})
    monkeypatch.setattr(ql, "_targets_from_state", lambda sid_, max_targets: [{"kind": "technique", "slug": "pigeonhole", "name": "Pigeonhole principle"}])
    view = world.store.generate_quiz(UUID(world.sid), style="MIXED", question_count=1, question_types=["MCQ"])
    q = typed.require(ep.ExamQuestionItem, pk(world.sid), ep.question_sk(view["quiz_id"], view["questions"][0]["question_id"]))
    assert [str(i) for i in q.technique_ids] == [TECHNIQUE]                                              # QUZ-F03: the technique tag is kept


def test_a_failed_generation_marks_the_paper_failed_with_502(world, monkeypatch):
    monkeypatch.setattr("mathbank_rest.db.hybrid_search.search_problems", lambda *a, **k: {"results": []})
    world.llm.fail_on = "quiz_question"
    with pytest.raises(QuizError) as exc:
        world.store.generate_quiz(UUID(world.sid), style="AIME", question_count=1, question_types=["MCQ"], target_concept_slugs=["counting"])
    assert (exc.value.code, exc.value.status_code) == ("GENERATION_FAILED", 502)
    (row,) = world.store.list_my_quizzes(UUID(world.sid))
    assert row["status"] == "FAILED" and "llm down" in typed.require(ep.ExamPaperItem, pk(world.sid), ep.paper_sk(row["quiz_id"])).error_message


@pytest.mark.parametrize("kwargs,code", [({"style": "X", "question_count": 1, "question_types": ["MCQ"]}, "INVALID_STYLE"),
                                         ({"style": "AIME", "question_count": 0, "question_types": ["MCQ"]}, "INVALID_QUESTION_COUNT"),
                                         ({"style": "AIME", "question_count": 1, "question_types": ["ESSAY"]}, "INVALID_QUESTION_TYPE")])
def test_generate_validates_before_writing(world, kwargs, code):
    with pytest.raises(QuizError) as exc:
        world.store.generate_quiz(UUID(world.sid), **kwargs)
    assert exc.value.code == code and toolkit.query_page("exam", pk(world.sid), limit=5)["items"] == []


# ------------------------------------------------------------------------------------------------- import_paper


def test_import_paper_is_start_plus_finalize_and_validates_first(world):
    view = world.store.import_paper(UUID(world.sid), style="AIME", title="t", requested_question_count=1, requested_question_types=["MCQ"],
                                    generated_by="x", questions=[mcq(1)])
    assert view["status"] == "READY"
    for kwargs, code in (({"style": "NOPE"}, "INVALID_STYLE"), ({"questions": []}, "NO_QUESTIONS")):
        before = len(world.store.list_my_quizzes(UUID(world.sid)))
        with pytest.raises(QuizError) as exc:
            world.store.import_paper(UUID(world.sid), **{"style": "AIME", "title": "t", "requested_question_count": 1,
                                                          "requested_question_types": ["MCQ"], "generated_by": "x", "questions": [mcq(1)], **kwargs})
        assert exc.value.code == code
        assert len(world.store.list_my_quizzes(UUID(world.sid))) == before                                  # no stray GENERATING shell


# --------------------------------------------------------------------------------------------------- the invariants


def test_every_paper_item_validates_against_its_refined_model(world):
    qid, view = ready(world, [mcq(1, concepts=("counting",)), free_text(2)])
    world.store.save_exam_progress(qid, UUID(world.sid), current_question_ordinal=1, raw_response={"selected_key": "A"})
    world.store.submit_response(qid, UUID(question_ids(view)[0]), UUID(world.sid), raw_response={"selected_key": "A"})
    world.store.log_response_event(qid, UUID(question_ids(view)[0]), UUID(world.sid), event_type="VIEW")
    world.store.submit_exam(qid, UUID(world.sid))
    world.store.write_diagnosis(qid, UUID(world.sid), time_management_verdict="v", pacing_notes=[], reasoning_guidance=[], improvement_areas=[],
                                generated_by="a")
    from mathbank_rest.models import base

    seen = set()
    for item in items_of(world, qid) + toolkit.query_page("exam", pk(world.sid), sk_begins="QEVID#", limit=20)["items"]:
        model = base.parse_item("exam", item)
        assert model.to_item() == item, item["SK"]
        seen.add(item["type"])
    assert seen == {"PAPER", "QUESTION", "QUESTION_SECRET", "RESPONSE", "RESPONSE_EVENT", "DIAGNOSIS", "QUIZ_EVIDENCE"}


def test_no_postgres_and_no_scan_on_any_path(world):
    qid, view = ready(world)
    for question in question_ids(view):
        world.store.log_response_event(qid, UUID(question), UUID(world.sid), event_type="VIEW")
    world.store.submit_exam(qid, UUID(world.sid))
    world.store.get_review(qid, UUID(world.sid))                      # NoPostgres would raise on any engine access
