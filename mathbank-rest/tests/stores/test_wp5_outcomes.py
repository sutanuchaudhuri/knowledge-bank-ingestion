"""WP5 outcomes area of the learner store on moto (requirement 70 C1 access patterns A6-A9, A41, A42, write path T7).

Gate: the MASTERY items written by the DynamoDB store equal what the unchanged ``mastery`` module computes through the PostgreSQL
path on the same replayed attempts (the PostgreSQL side is ``OutcomesPostgres`` with ``db.learner`` replaced by an in-memory oracle
that mirrors the SQL: tag fan-out without REJECTED tags, quiz evidence blended in, ordered by attempted_at). Content comes from the
WP4 corpus seeded into ``mb-content-ut``.
"""
from __future__ import annotations

import datetime as dt
import threading
import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
import test_wp4_catalog as wp4
from pydantic import ValidationError

from mathbank_rest import mastery, stores
from mathbank_rest.db import learner as learner_db
from mathbank_rest.models.ddb.learner import LearnerProblem
from mathbank_rest.models.manual.learner_outcomes import (
    CohortItem,
    DailyItem,
    MasteryItem,
    MevidItem,
    OutcomeItem,
)
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import typed
from mathbank_rest.stores.content import DynamoDBContentStore, catalog
from mathbank_rest.stores.errors import (
    ConditionFailed,
    IdempotencyKeyReused,
    NotFound,
    StoreFrozen,
    ValidationFailed,
)
from mathbank_rest.stores.learner.outcomes import FOLLOWUP_TAGS, OutcomesDynamoDB, OutcomesPostgres
from mathbank_rest.stores.learner.uow import LearnerUnitOfWork

NOW = datetime.now(UTC)
PID = wp4.pid
Q1 = "AIME_2005_I_Q01"        # concept count-subset, technique power-point
Q2 = "AIME_2005_I_Q02"        # concepts count-perm + count-subset
REJ = "AMC10_2005B_Q01"       # concept geometry-basic, technique power-point; a REJECTED `count` tag is stored but never served


@pytest.fixture()
def corpus(content_table):
    catalog._CATALOGUES.clear()
    OutcomesDynamoDB._themes.clear()
    wp4.seed()
    with stores.override_store("content", DynamoDBContentStore()):
        yield
    catalog._CATALOGUES.clear()
    OutcomesDynamoDB._themes.clear()


@pytest.fixture()
def store(corpus):
    return OutcomesDynamoDB()


def tags_of(code: str) -> dict:
    p = next(p for p in wp4.PROBLEMS if p.code == code)
    return {"concept_ids": [UUID(wp4.uid(f"concept:{s}")) for s, _, _ in p.concepts],
            "technique_ids": [UUID(wp4.uid(f"technique:{s}")) for s, _, _ in p.techniques]}


def cid(slug: str) -> UUID:
    return UUID(wp4.uid(f"concept:{slug}"))


def tid(slug: str) -> UUID:
    return UUID(wp4.uid(f"technique:{slug}"))


def mastery_items(sid) -> dict[tuple[str, str], MasteryItem]:
    page = typed.query(MasteryItem, toolkit.student_pk(sid), sk_begins="MASTERY#", limit=200)
    return {(i.tag_kind, str(i.tag_id)): i for i in page.items}


def commit(store, sid, code, correct, hints=0, when=None, source="web", answer=None):
    """Stage and commit one outcome with an explicit time (the replay primitive of the gate)."""
    problem = stores.get_store("content").get_problem_by_id(PID(code))
    uow = LearnerUnitOfWork(sid)
    staged = store.stage_outcome(uow, problem_id=UUID(PID(code)), attempt_id=uuid.uuid4(), attempted_at=when or datetime.now(UTC),
                                 is_correct=correct, submitted_answer=answer, time_spent_seconds=30, hint_count=hints, source=source,
                                 difficulty_band=problem["difficulty_band"], tags=stores.get_store("content").get_problem_tags(
                                     problem_id=PID(code)))
    uow.commit()
    return staged


def keys_of(ddb_client) -> set[tuple[str, str]]:
    return {(i["PK"]["S"], i["SK"]["S"]) for i in ddb_client.scan(TableName="mb-learner-ut")["Items"]}


# ------------------------------------------------------------------------------------------------ T7

def test_record_outcome_writes_outcome_cursor_evidence_and_mastery_in_one_transaction(ddb, store, sid):
    result = store.record_outcome(student_id=UUID(sid), problem_id=UUID(PID(Q1)), is_correct=True, submitted_answer="123",
                                  time_spent_seconds=41, hint_count=1, source="web")
    assert set(result) == {"attempt", "updated_mastery"} and set(result["attempt"]) == {"attempt_id", "attempted_at"}
    assert set(result["updated_mastery"]) == {"concepts", "techniques"}
    keys = keys_of(ddb)
    kinds = sorted(sk.split("#")[0] for pk, sk in keys if pk == toolkit.student_pk(sid))
    assert kinds == ["MASTERY", "MASTERY", "MEVID", "MEVID", "OUTCOME", "PROBLEM"]
    outcome = typed.query(OutcomeItem, toolkit.student_pk(sid), sk_begins="OUTCOME#").items[0]
    assert (outcome.problem_id, outcome.is_correct, outcome.hint_count, outcome.source, outcome.submitted_answer) == (
        UUID(PID(Q1)), True, 1, "web", "123")
    assert str(outcome.attempt_id) == result["attempt"]["attempt_id"] and outcome.mastery_pending is None
    cursor = typed.require(LearnerProblem, toolkit.student_pk(sid), f"PROBLEM#{PID(Q1)}")
    assert cursor.outcome_count == 1 and cursor.first_attempted_at == outcome.attempted_at
    expected = mastery.compute_mastery_score([{"is_correct": True, "attempted_at": outcome.attempted_at, "hint_count": 1,
                                               "difficulty_band": "EASY"}])
    assert result["updated_mastery"]["concepts"] == {str(cid("count-subset")): pytest.approx(expected)}
    assert result["updated_mastery"]["techniques"] == {str(tid("power-point")): pytest.approx(expected)}
    item = mastery_items(sid)[("C", str(cid("count-subset")))]
    assert (item.mastery_score, item.attempts_count, item.correct_count, item.version, item.formula_version) == (
        pytest.approx(expected), 1, 1, 1, 1)
    assert item.concept_id == cid("count-subset") and item.technique_id is None
    evidence = typed.query(MevidItem, toolkit.student_pk(sid), sk_begins="MEVID#C#").items[0]
    assert evidence.src_kind == "OUT" and evidence.src_id == outcome.attempt_id and evidence.difficulty_weight == pytest.approx(1.1)
    second = store.record_outcome(student_id=UUID(sid), problem_id=UUID(PID(Q1)), is_correct=False)
    assert typed.require(LearnerProblem, toolkit.student_pk(sid), f"PROBLEM#{PID(Q1)}").outcome_count == 2
    assert mastery_items(sid)[("C", str(cid("count-subset")))].attempts_count == 2
    assert second["updated_mastery"]["concepts"][str(cid("count-subset"))] < expected


def test_rejected_tags_and_unknown_problems_and_bad_input(store, sid):
    result = store.record_outcome(student_id=UUID(sid), problem_id=UUID(PID(REJ)), is_correct=True)
    assert set(result["updated_mastery"]["concepts"]) == {str(cid("geometry-basic"))}            # no mastery for the REJECTED `count`
    assert ("C", str(cid("count"))) not in mastery_items(sid)
    with pytest.raises(NotFound):
        store.record_outcome(student_id=UUID(sid), problem_id=uuid.uuid4(), is_correct=True)
    with pytest.raises(ValidationFailed):
        store.record_outcome(student_id=UUID(sid), problem_id=UUID(PID(Q1)), is_correct=True, hint_count=-1)


def test_free_text_source_is_normalised_and_ungraded_work_has_no_evidence(store, sid):
    store.record_outcome(student_id=UUID(sid), problem_id=UUID(PID(Q1)), is_correct=True, source="my-own-app")
    commit(store, sid, Q1, None)
    outcomes = typed.query(OutcomeItem, toolkit.student_pk(sid), sk_begins="OUTCOME#").items
    assert sorted((o.source, o.legacy_source, o.is_correct) for o in outcomes) == [("import", "my-own-app", True), ("web", None, None)]
    evidence = typed.query(MevidItem, toolkit.student_pk(sid), sk_begins="MEVID#C#").items
    assert len(evidence) == 1                                         # only the graded row is evidence
    assert mastery_items(sid)[("C", str(cid("count-subset")))].attempts_count == 1


def test_idempotent_redelivery_replays_and_reuse_with_another_body_is_422(ddb, store, sid):
    kwargs = {"student_id": UUID(sid), "problem_id": UUID(PID(Q1)), "is_correct": True, "hint_count": 0}
    first = store.record_outcome(**kwargs, idempotency_key="k-1")
    again = store.record_outcome(**kwargs, idempotency_key="k-1")
    assert again == first
    assert len(typed.query(OutcomeItem, toolkit.student_pk(sid), sk_begins="OUTCOME#").items) == 1
    assert typed.require(LearnerProblem, toolkit.student_pk(sid), f"PROBLEM#{PID(Q1)}").outcome_count == 1
    assert mastery_items(sid)[("C", str(cid("count-subset")))].version == 1
    with pytest.raises(IdempotencyKeyReused):
        store.record_outcome(**{**kwargs, "is_correct": False}, idempotency_key="k-1")
    store.record_outcome(**kwargs)                                    # without a key every call is a new outcome
    assert len(typed.query(OutcomeItem, toolkit.student_pk(sid), sk_begins="OUTCOME#").items) == 2


def test_two_concurrent_completions_on_one_concept_converge(store, sid):
    commit(store, sid, Q1, True, when=NOW - timedelta(days=3))
    competitor, fired = OutcomesDynamoDB(), []
    real = store._tag_state

    def racing(student_id, kind, tag, new):
        state = real(student_id, kind, tag, new)
        if not fired:                                                 # a second completion commits after our read, before our write
            fired.append(1)
            competitor.record_outcome(student_id=UUID(sid), problem_id=UUID(PID(Q1)), is_correct=False, hint_count=2)
        return state

    store._tag_state = racing
    store.record_outcome(student_id=UUID(sid), problem_id=UUID(PID(Q1)), is_correct=True)
    item = mastery_items(sid)[("C", str(cid("count-subset")))]
    assert fired and item.attempts_count == 3 and item.correct_count == 2 and item.version == 3
    assert len(typed.query(MevidItem, toolkit.student_pk(sid), sk_begins="MEVID#C#").items) == 3
    rebuilt = store.recompute_concept_mastery(UUID(sid), cid("count-subset"))
    assert rebuilt == pytest.approx(item.mastery_score)


def test_stale_mastery_write_is_refused_by_its_version_condition(store, sid):
    first = LearnerUnitOfWork(sid)
    second = LearnerUnitOfWork(sid)
    for uow in (first, second):                                       # both read the same (empty) state
        store.stage_outcome(uow, problem_id=UUID(PID(Q1)), attempt_id=uuid.uuid4(), attempted_at=datetime.now(UTC), is_correct=True,
                            submitted_answer=None, time_spent_seconds=None, hint_count=0, source="web", difficulty_band="EASY",
                            tags=tags_of(Q1))
    first.commit()
    with pytest.raises(ConditionFailed):
        second.commit()
    assert len(typed.query(OutcomeItem, toolkit.student_pk(sid), sk_begins="OUTCOME#").items) == 1     # the loser wrote nothing


# ------------------------------------------------------------------------------------------------ > 100 items

def test_outcome_with_too_many_tags_defers_mastery_and_flags_the_outcome(store, sid):
    many = [uuid.uuid4() for _ in range(FOLLOWUP_TAGS + 11)]               # 2 + 2 * 60 items do not fit in one transaction
    uow = LearnerUnitOfWork(sid)
    staged = store.stage_outcome(uow, problem_id=UUID(PID(Q1)), attempt_id=uuid.uuid4(), attempted_at=datetime.now(UTC), is_correct=True,
                                 submitted_answer=None, time_spent_seconds=None, hint_count=0, source="step_runtime",
                                 difficulty_band="EASY", tags={"concept_ids": many, "technique_ids": []})
    uow.commit()
    assert len(staged.deferred) == 60 and len(staged.updated_mastery["concepts"]) == 60
    outcome = typed.query(OutcomeItem, toolkit.student_pk(sid), sk_begins="OUTCOME#").items[0]
    assert outcome.mastery_pending is True
    assert mastery_items(sid) == {} and typed.query(MevidItem, toolkit.student_pk(sid), sk_begins="MEVID#").items == []
    store.finish_deferred_mastery(sid, staged)
    items = mastery_items(sid)
    assert set(items) == {("C", str(t)) for t in many} and all(i.attempts_count == 1 for i in items.values())
    assert len(typed.query(MevidItem, toolkit.student_pk(sid), sk_begins="MEVID#C#", limit=200).items) == 60


def test_the_largest_outcome_that_fits_stays_in_one_transaction(store, sid):
    fits = [uuid.uuid4() for _ in range(48)]                               # 2 + 96 items, plus the idempotency slot
    uow = LearnerUnitOfWork(sid)
    staged = store.stage_outcome(uow, problem_id=UUID(PID(Q1)), attempt_id=uuid.uuid4(), attempted_at=datetime.now(UTC), is_correct=False,
                                 submitted_answer=None, time_spent_seconds=None, hint_count=0, source="web", difficulty_band=None,
                                 tags={"concept_ids": fits, "technique_ids": []})
    assert staged.deferred == [] and len(uow) == 98
    uow.commit()
    assert typed.query(OutcomeItem, toolkit.student_pk(sid), sk_begins="OUTCOME#").items[0].mastery_pending is None
    assert len(mastery_items(sid)) == 48


# ------------------------------------------------------------------------------------------------ gate: mastery equals PostgreSQL

class PgOracle:
    """``db.learner`` as SQL computes it: attempts per student, tag fan-out without REJECTED tags, quiz rows blended in."""

    def __init__(self):
        self.attempts: list[dict] = []
        self.quiz: list[dict] = []
        self.scores: dict[tuple[str, str, str], dict] = {}
        self.when = NOW

    def insert_attempt(self, *, student_id, problem_id, is_correct, submitted_answer, time_spent_seconds, hint_count, source):
        row = {"attempt_id": uuid.uuid4(), "attempted_at": self.when, "student_id": str(student_id), "problem_id": str(problem_id),
               "is_correct": is_correct, "hint_count": hint_count}
        self.attempts.append(row)
        return {"attempt_id": row["attempt_id"], "attempted_at": row["attempted_at"]}

    def get_concepts_and_techniques_for_problem(self, problem_id):
        code = next(p.code for p in wp4.PROBLEMS if PID(p.code) == str(problem_id))
        return tags_of(code)

    def _rows(self, student_id, kind, tag):
        key = "concept_ids" if kind == "C" else "technique_ids"
        rows = [{"is_correct": a["is_correct"], "attempted_at": a["attempted_at"], "hint_count": a["hint_count"], "difficulty_band": "EASY"}
                for a in self.attempts if a["student_id"] == str(student_id) and a["is_correct"] is not None
                and tag in self.get_concepts_and_techniques_for_problem(a["problem_id"])[key]]
        rows += [{"is_correct": q["is_correct"], "attempted_at": q["attempted_at"], "hint_count": 0, "difficulty_band": "medium"}
                 for q in self.quiz if q["student_id"] == str(student_id) and q["kind"] == kind and q["tag"] == tag]
        return sorted(rows, key=lambda r: r["attempted_at"])

    def get_attempts_for_concept(self, student_id, concept_id):
        return self._rows(student_id, "C", concept_id)

    def get_attempts_for_technique(self, student_id, technique_id):
        return self._rows(student_id, "T", technique_id)

    def upsert_concept_mastery(self, *, student_id, concept_id, **row):
        self.scores[("C", str(student_id), str(concept_id))] = row

    def upsert_technique_mastery(self, *, student_id, technique_id, **row):
        self.scores[("T", str(student_id), str(technique_id))] = row


@pytest.fixture()
def oracle(monkeypatch):
    pg = PgOracle()
    for name in ("insert_attempt", "get_concepts_and_techniques_for_problem", "get_attempts_for_concept", "get_attempts_for_technique",
                 "upsert_concept_mastery", "upsert_technique_mastery"):
        monkeypatch.setattr(learner_db, name, getattr(pg, name))
    return pg


# (problem, is_correct, hints, days ago): old and recent, graded and ungraded, hinted, repeated, shared and distinct tags
REPLAY = [
    (Q1, True, 0, 120), (Q1, False, 2, 95), (Q2, True, 1, 70), (Q2, True, 0, 61), (Q1, True, 3, 44), (REJ, False, 0, 40),
    (Q1, None, 0, 30), (Q2, False, 5, 21), (REJ, True, 0, 14), (Q1, True, 0, 7), (Q2, True, 2, 2), (Q1, False, 0, 0.5),
    ("AMC10_2005A_Q01", True, 1, 33), ("AMC10_2005A_Q02", False, 0, 9),
]


def test_gate_mastery_equals_the_postgresql_computation_on_replayed_attempts(oracle, store, sid):
    quiz_at = NOW - timedelta(days=18)
    for code, correct, hints, days in REPLAY:
        when = NOW - timedelta(days=days)
        commit(store, sid, code, correct, hints, when)
        oracle.when = when
        with stores.override_store("learner", OutcomesPostgres()):
            OutcomesPostgres().record_outcome(student_id=UUID(sid), problem_id=UUID(PID(code)), is_correct=correct, hint_count=hints)
    # a quiz response on count-subset: PostgreSQL blends quiz.response, DynamoDB reads the QZ evidence row
    qz = {"student_id": sid, "kind": "C", "tag": cid("count-subset"), "is_correct": True, "attempted_at": quiz_at}
    oracle.quiz.append(qz)
    typed.put(MevidItem(PK=toolkit.student_pk(sid), SK=f"MEVID#C#{cid('count-subset')}#{toolkit.encode(quiz_at)}#QZ#{uuid.uuid4()}",
                        student_id=UUID(sid), tag_kind="C", tag_id=cid("count-subset"), is_correct=True, hint_count=0,
                        difficulty_band="medium", difficulty_weight=1.25, attempted_at=quiz_at, src_kind="QZ", src_id=uuid.uuid4(),
                        quiz_id=uuid.uuid4(), question_id=uuid.uuid4()))
    with stores.override_store("learner", OutcomesPostgres()):
        mastery.recompute_concept_mastery(UUID(sid), cid("count-subset"))
    store.recompute_concept_mastery(UUID(sid), cid("count-subset"))

    items = mastery_items(sid)
    expected = {(kind, tag): row for (kind, student, tag), row in oracle.scores.items() if student == sid}
    assert set(items) == set(expected) and len(items) == 6
    for key, row in expected.items():
        got = items[key]
        assert got.mastery_score == pytest.approx(row["mastery_score"], abs=1e-6), key
        assert (got.attempts_count, got.correct_count) == (row["attempts_count"], row["correct_count"]), key
        assert got.last_attempt_at == row["last_attempt_at"], key
    assert ("C", str(cid("count"))) not in items                      # REJECTED never feeds mastery
    # the blended quiz row really moved the concept score (guards against a vacuous comparison)
    plain = mastery.compute_mastery_score([r for r in oracle._rows(sid, "C", cid("count-subset")) if r["difficulty_band"] == "EASY"])
    assert items[("C", str(cid("count-subset")))].mastery_score != pytest.approx(plain, abs=1e-6)


def test_the_same_replay_is_deterministic_through_record_outcome_and_upsert_paths(store, sid):
    for code, correct, hints, days in REPLAY[:6]:
        commit(store, sid, code, correct, hints, NOW - timedelta(days=days))
    versions = {k: v.version for k, v in mastery_items(sid).items()}
    before = {k: (v.mastery_score, v.attempts_count) for k, v in mastery_items(sid).items()}
    for kind, tag in list(before):
        (store.recompute_concept_mastery if kind == "C" else store.recompute_technique_mastery)(UUID(sid), UUID(tag))
    after = mastery_items(sid)
    assert {k: v.version for k, v in after.items()} == {k: n + 1 for k, n in versions.items()}
    assert {k: (v.mastery_score, v.attempts_count) for k, v in after.items()} == {
        k: (pytest.approx(s, abs=1e-6), n) for k, (s, n) in before.items()}
    store.upsert_concept_mastery(student_id=UUID(sid), concept_id=cid("count"), mastery_score=0.5, attempts_count=4, correct_count=2,
                                 last_attempt_at=NOW)
    store.upsert_technique_mastery(student_id=UUID(sid), technique_id=tid("inversion"), mastery_score=0.25, attempts_count=4,
                                   correct_count=1, last_attempt_at=NOW)
    assert mastery_items(sid)[("C", str(cid("count")))].mastery_score == 0.5
    store.upsert_concept_mastery(student_id=UUID(sid), concept_id=cid("count"), mastery_score=0.75, attempts_count=5, correct_count=3,
                                 last_attempt_at=NOW)
    assert mastery_items(sid)[("C", str(cid("count")))].version == 2


# ------------------------------------------------------------------------------------------------ reads

def test_list_attempts_is_newest_first_paged_owner_scoped_and_keeps_the_sql_shape(store, sid):
    other = str(uuid.uuid4())
    for i, code in enumerate((Q1, Q2, REJ)):
        commit(store, sid, code, i % 2 == 0, i, NOW - timedelta(hours=10 - i), answer=f"answer {i}")
    commit(store, other, Q1, True)
    rows = store.list_attempts(UUID(sid))
    assert [r["canonical_code"] for r in rows] == [REJ, Q2, Q1]
    assert set(rows[0]) == {"attempt_id", "is_correct", "submitted_answer", "time_spent_seconds", "hint_count", "attempted_at", "source",
                            "canonical_code", "problem_number", "difficulty_band", "competition", "year"}
    assert (rows[0]["submitted_answer"], rows[0]["hint_count"], rows[0]["competition"], rows[0]["year"], rows[0]["difficulty_band"]) == (
        "answer 2", 2, "AMC 10", 2005, "EASY")
    assert [r["canonical_code"] for r in store.list_attempts(UUID(sid), limit=1, offset=1)] == [Q2]
    assert store.list_attempts(UUID(sid), limit=5, offset=3) == []
    assert len(store.list_attempts(UUID(other))) == 1 and store.list_attempts(UUID(str(uuid.uuid4()))) == []


def test_large_answers_are_offloaded_and_read_back(ddb, store, sid):
    answer = "x" * 40_000
    commit(store, sid, Q1, True, answer=answer)
    raw = typed.query(OutcomeItem, toolkit.student_pk(sid), sk_begins="OUTCOME#").items[0]
    assert raw.submitted_answer is None and raw.submitted_answer_ref is not None
    assert store.list_attempts(UUID(sid))[0]["submitted_answer"] == answer


def test_list_attempts_hides_problems_that_left_the_content_model(store, sid):
    commit(store, sid, Q1, True)
    ghost = LearnerUnitOfWork(sid)
    store.stage_outcome(ghost, problem_id=uuid.uuid4(), attempt_id=uuid.uuid4(), attempted_at=datetime.now(UTC), is_correct=True,
                        submitted_answer=None, time_spent_seconds=None, hint_count=0, source="web", difficulty_band=None,
                        tags={"concept_ids": [], "technique_ids": []})
    ghost.commit()
    assert [r["canonical_code"] for r in store.list_attempts(UUID(sid))] == [Q1]


def test_evidence_reads_are_ordered_and_scoped(store, sid):
    commit(store, sid, Q2, True, 1, NOW - timedelta(days=5))
    commit(store, sid, Q1, False, 0, NOW - timedelta(days=9))
    commit(store, str(uuid.uuid4()), Q1, True)
    rows = store.get_attempts_for_concept(UUID(sid), cid("count-subset"))
    assert [(r["is_correct"], r["hint_count"]) for r in rows] == [(False, 0), (True, 1)] and rows[0]["attempted_at"] < rows[1]["attempted_at"]
    assert set(rows[0]) == {"is_correct", "attempted_at", "hint_count", "difficulty_band"}
    assert len(store.get_attempts_for_technique(UUID(sid), tid("power-point"))) == 1
    assert store.get_attempts_for_concept(UUID(sid), cid("loop-a")) == []


def test_mastery_summary_is_weakest_first_named_and_skips_unknown_tags(store, sid):
    commit(store, sid, Q1, True, 0)
    commit(store, sid, Q2, False, 0)
    store.upsert_concept_mastery(student_id=UUID(sid), concept_id=uuid.uuid4(), mastery_score=0.1, attempts_count=1, correct_count=0,
                                 last_attempt_at=NOW)                 # a tag that is not in the content model
    summary = store.get_mastery_summary(UUID(sid))
    assert set(summary) == {"concepts", "techniques"}
    assert [c["slug"] for c in summary["concepts"]] == ["count-perm", "count-subset"]
    scores = [c["mastery_score"] for c in summary["concepts"]]
    assert scores == sorted(scores)
    assert set(summary["concepts"][0]) == {"slug", "name", "mastery_score", "attempts_count", "correct_count", "last_attempt_at"}
    assert [t["slug"] for t in summary["techniques"]] == ["power-point"] and summary["techniques"][0]["name"] == "Power of a point"
    assert store.get_mastery_summary(UUID(str(uuid.uuid4()))) == {"concepts": [], "techniques": []}


def test_improvement_plan_runs_on_the_store_and_the_content_store(store, sid):
    commit(store, sid, Q1, False, 0)
    with stores.override_store("learner", store):
        plan = mastery.build_improvement_plan(UUID(sid), max_focus_areas=5)
    assert plan["student_id"] == sid and plan["total_struggling_areas"] == 2
    kinds = {(a["kind"], a["slug"]): a for a in plan["focus_areas"]}
    assert kinds[("concept", "count-subset")]["tier"] == "critical" and kinds[("concept", "count-subset")]["attempts_count"] == 1
    assert kinds[("concept", "count-subset")]["recommended_problems"]            # served by the content store


def test_practice_progress_counts_distinct_problems_per_theme(store, sid, monkeypatch):
    commit(store, sid, Q1, True)
    commit(store, sid, Q1, False)                                    # repeated attempts count once
    commit(store, sid, Q2, None)                                     # ungraded work counts as attempted
    commit(store, str(uuid.uuid4()), REJ, True)                      # another student's work never counts
    progress = store.get_practice_progress(UUID(sid))
    rows = {(r["kind"], r["slug"]): r for r in progress["items"]}

    def expect(kind, slug, codes):
        live = {p.code for p in wp4.LIVE if p.code in codes}
        done = len(live & {Q1, Q2})
        assert rows[(kind, slug)] == {"kind": kind, "slug": slug, "name": rows[(kind, slug)]["name"], "available": len(live),
                                      "attempted": done, "remaining": len(live) - done}

    for slug in wp4.CONCEPTS:
        expect("concept", slug, {p.code for p in wp4.PROBLEMS if any(s == slug for s, _, _ in p.concepts)})
    for slug in wp4.TECHNIQUES:
        expect("technique", slug, {p.code for p in wp4.PROBLEMS if any(s == slug for s, _, _ in p.techniques)})
    assert rows[("concept", "count-subset")]["attempted"] == 2 and rows[("technique", "inversion")]["available"] == 0
    order = [(r["kind"], r["name"].lower(), r["slug"]) for r in progress["items"]]
    assert order == sorted(order) and len(order) == len(wp4.CONCEPTS) + len(wp4.TECHNIQUES)
    from mathbank_rest.stores.learner import outcomes

    calls = []
    real = outcomes._paged
    monkeypatch.setattr(outcomes, "_paged", lambda model, pk, **kw: (calls.append(pk), real(model, pk, **kw))[1])
    store.get_practice_progress(UUID(sid))
    assert not any(pk.startswith(("CONCEPT#", "TECHNIQUE#")) for pk in calls)       # the theme sets come from the cache


def test_daily_activity_range_is_inclusive_ordered_and_owner_scoped(store, sid):
    def day(student, d, **over):
        base = dict.fromkeys(("attempts_started", "attempts_completed", "attempts_abandoned", "steps_evaluated", "steps_succeeded",
                              "gaps_diagnosed", "knowledge_gaps_created", "recovery_plans_created", "recovery_plans_completed"), 0)
        typed.put(DailyItem(PK=toolkit.student_pk(student), SK=f"DAILY#{d}", student_id=UUID(student), activity_date=dt.date.fromisoformat(d),
                            updated_at=NOW, **{**base, **over}))

    for d in ("2026-10-01", "2026-10-03", "2026-10-05", "2026-10-07"):
        day(sid, d, attempts_started=1, steps_evaluated=4, steps_succeeded=3)
    day(str(uuid.uuid4()), "2026-10-03", attempts_started=9)
    rows = store.list_daily_activity(UUID(sid), dt.date(2026, 10, 3), dt.date(2026, 10, 6))
    assert [r["activity_date"] for r in rows] == [dt.date(2026, 10, 3), dt.date(2026, 10, 5)]
    assert rows[0] == {"activity_date": dt.date(2026, 10, 3), "attempts_started": 1, "attempts_completed": 0, "attempts_abandoned": 0,
                       "steps_evaluated": 4, "steps_succeeded": 3, "gaps_diagnosed": 0, "knowledge_gaps_created": 0,
                       "recovery_plans_created": 0, "recovery_plans_completed": 0}
    assert store.list_daily_activity(UUID(sid), dt.date(2026, 11, 1), dt.date(2026, 11, 30)) == []
    with pytest.raises(ValidationError):
        day(sid, "2026-10-09", steps_evaluated=1, steps_succeeded=2)


def test_cohort_weak_concepts_apply_the_minimum_cohort_floor(store, monkeypatch):
    from mathbank_rest.config import settings

    def cohort(slug, n, total, attempts=None):
        typed.put(CohortItem(PK="COHORT#CONCEPT", SK=str(cid(slug)), concept_id=cid(slug), n_students=n, sum_score=total, updated_at=NOW,
                             **({"sum_attempts": attempts} if attempts is not None else {})))

    cohort("count", 12, 2.4, 40)
    cohort("count-subset", 30, 15.0)
    cohort("count-perm", 9, 0.0)                                      # below the floor: never reported
    cohort("loop-a", 10, 3.0)
    assert settings.cohort_min_students == 10
    rows = store.get_cohort_weak_concepts(min_students=1, limit=20)
    assert [r["slug"] for r in rows] == ["count", "loop-a", "count-subset"]
    assert rows[0] == {"slug": "count", "name": "Counting", "student_count": 12, "avg_mastery_score": pytest.approx(0.2),
                       "total_attempts": 40}
    assert rows[2]["total_attempts"] is None
    assert [r["slug"] for r in store.get_cohort_weak_concepts(min_students=11, limit=1)] == ["count"]
    assert store.get_cohort_weak_concepts(min_students=31) == []
    monkeypatch.setattr(settings, "cohort_min_students", 30)
    assert [r["slug"] for r in store.get_cohort_weak_concepts(min_students=1)] == ["count-subset"]


# ------------------------------------------------------------------------------------------------ guards

def test_get_problem_id_by_code_resolves_visible_problems_only(store):
    assert store.get_problem_id_by_code(Q1) == UUID(PID(Q1))
    assert store.get_problem_id_by_code("AMC10_2006A_Q03") is None      # withdrawn
    assert store.get_problem_id_by_code("NOPE_0000_Q01") is None
    assert store.get_concepts_and_techniques_for_problem(UUID(PID(Q2)))["concept_ids"]


def test_dynamodb_outcome_paths_never_touch_the_postgres_engine(store, sid, monkeypatch):
    from mathbank_rest.db import postgres

    class Boom:
        def __getattr__(self, name):
            raise AssertionError("PostgreSQL used by a DynamoDB outcome path")

    monkeypatch.setattr(postgres, "engine", Boom())
    store.record_outcome(student_id=UUID(sid), problem_id=UUID(PID(Q1)), is_correct=True)
    store.list_attempts(UUID(sid))
    store.get_mastery_summary(UUID(sid))
    store.get_practice_progress(UUID(sid))
    store.list_daily_activity(UUID(sid), dt.date(2026, 1, 1), dt.date(2026, 1, 2))
    store.get_cohort_weak_concepts()
    store.recompute_technique_mastery(UUID(sid), tid("power-point"))


def test_frozen_outcome_store_serves_reads_and_rejects_writes(store, sid):
    frozen = stores.FrozenProxy("learner", store)
    assert frozen.list_attempts(UUID(sid)) == [] and frozen.get_mastery_summary(UUID(sid))["concepts"] == []
    with pytest.raises(StoreFrozen):
        frozen.record_outcome(student_id=UUID(sid), problem_id=UUID(PID(Q1)), is_correct=True)
    with pytest.raises(StoreFrozen):
        frozen.recompute_concept_mastery(UUID(sid), cid("count"))


def test_append_only_outcome_items_cannot_be_updated_or_deleted(store, sid):
    commit(store, sid, Q1, True)
    outcome = typed.query(OutcomeItem, toolkit.student_pk(sid), sk_begins="OUTCOME#").items[0]
    uow = LearnerUnitOfWork(sid)
    with pytest.raises(ValidationFailed):
        uow.update(OutcomeItem, outcome.PK, outcome.SK, {"is_correct": False})
    with pytest.raises(ValidationFailed):
        uow.delete(MevidItem, outcome.PK, outcome.SK)


@pytest.mark.ddb_integration
def test_threaded_completions_real_aws(real_env):
    """Eight completions on one concept at once: every OUTCOME/MEVID survives and the score equals the full recompute."""
    store, sid = OutcomesDynamoDB(), str(uuid.uuid4())
    problem, tags = uuid.uuid4(), {"concept_ids": [uuid.uuid4()], "technique_ids": []}
    barrier = threading.Barrier(8)

    def worker(i):
        barrier.wait()
        from mathbank_rest.stores.learner.uow import with_retries

        def attempt():
            uow = LearnerUnitOfWork(sid)
            store.stage_outcome(uow, problem_id=problem, attempt_id=uuid.uuid4(), attempted_at=datetime.now(UTC), is_correct=i % 2 == 0,
                                submitted_answer=None, time_spent_seconds=None, hint_count=i, source="web", difficulty_band="EASY", tags=tags)
            uow.commit()

        with_retries(attempt, attempts=8)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    tag = tags["concept_ids"][0]
    item = mastery_items(sid)[("C", str(tag))]
    assert item.attempts_count == 8 and item.version == 8
    assert store.recompute_concept_mastery(UUID(sid), tag) == pytest.approx(item.mastery_score, abs=1e-9)


# ------------------------------------------------------------------------------------------------ models

def test_refined_models_enforce_the_checks_the_schema_never_had():
    base = {"PK": toolkit.student_pk(uuid.uuid4()), "student_id": uuid.uuid4(), "tag_id": uuid.uuid4(), "formula_version": 1,
            "last_attempt_at": NOW, "updated_at": NOW}

    def item(**over):
        fields = {**base, "tag_kind": "C", "mastery_score": 0.5, "attempts_count": 2, "correct_count": 1}
        fields.update(over)
        fields.setdefault("SK", f"MASTERY#{fields['tag_kind']}#{fields['tag_id']}")
        return MasteryItem(**fields)

    assert item().mastery_score == 0.5
    for bad in ({"mastery_score": 1.01}, {"mastery_score": -0.1}, {"correct_count": 3}, {"attempts_count": -1}, {"tag_kind": "X"},
                {"SK": "MASTERY#C#" + str(uuid.uuid4())}):
        with pytest.raises(ValidationError):
            item(**bad)
    with pytest.raises(ValidationError):
        OutcomeItem(PK=base["PK"], SK=f"OUTCOME#x#{uuid.uuid4()}", student_id=base["student_id"], attempt_id=uuid.uuid4(), attempted_at=NOW,
                    hint_count=0, source="telepathy", problem_id=uuid.uuid4())
    with pytest.raises(ValidationError):
        MevidItem(PK=base["PK"], SK=f"MEVID#C#{uuid.uuid4()}#x#OUT#{uuid.uuid4()}", student_id=base["student_id"], tag_kind="C",
                  tag_id=uuid.uuid4(), is_correct=True, hint_count=0, difficulty_weight=2.0, attempted_at=NOW, src_kind="OUT",
                  src_id=uuid.uuid4())


def test_refinements_still_accept_the_migrated_item_shapes():
    sid, aid, pid_ = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    outcome = {"PK": f"STUDENT#{sid}", "SK": f"OUTCOME#2026-10-01T00:00:00.000000Z#{aid}", "type": "OUTCOME", "student_id": sid,
               "attempt_id": aid, "problem_id": pid_, "is_correct": True, "submitted_answer": "5", "time_spent_seconds": 3, "hint_count": 0,
               "attempted_at": "2026-10-01T00:00:00.000000Z", "source": "import", "legacy_source": "api"}
    assert OutcomeItem.from_item(outcome).to_item() == outcome
    tag = str(uuid.uuid4())
    mastery_row = {"PK": f"STUDENT#{sid}", "SK": f"MASTERY#T#{tag}", "type": "MASTERY", "student_id": sid, "tag_kind": "T", "tag_id": tag,
                   "technique_id": tag, "mastery_score": 1, "attempts_count": 3, "correct_count": 3,
                   "last_attempt_at": "2026-10-01T00:00:00.000000Z", "updated_at": "2026-10-01T00:00:00.000000Z", "formula_version": 1,
                   "version": 1}
    assert MasteryItem.from_item(mastery_row).mastery_score == 1.0
    daily = {"PK": f"STUDENT#{sid}", "SK": "DAILY#2026-10-01", "type": "DAILY", "student_id": sid, "activity_date": "2026-10-01",
             "updated_at": "2026-10-01T00:00:00.000000Z", **dict.fromkeys(
                 ("attempts_started", "attempts_completed", "attempts_abandoned", "steps_evaluated", "steps_succeeded", "gaps_diagnosed",
                  "knowledge_gaps_created", "recovery_plans_created", "recovery_plans_completed"), 0)}
    assert DailyItem.from_item(daily).to_item() == daily
