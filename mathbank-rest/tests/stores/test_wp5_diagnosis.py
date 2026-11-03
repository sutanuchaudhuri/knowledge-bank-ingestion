"""WP5 diagnosis area (requirement 71, requirement 70 C1 T12/T13, A14, A19-A22): the DynamoDB ``DiagnosisStore`` on moto.

The learner store is the composed ``DynamoDBLearnerStore`` (solve + diagnosis + recovery) over the real DynamoDB content store (moto
``mb-content``). The seeded world: problem ``PRASOLOV_PGV1_1.1`` with steps st1 -> st2 (DEPENDS_ON) and st3, skills SK1..SK3 in subconcept SC1,
learning items and a worked-example step for SK1 / SK2 in the ``FACET#`` partitions. Nothing touches Postgres (``db.postgres.engine`` raises).
"""
from __future__ import annotations

import datetime as dt
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "parity"))

from test_wp5_solve import (
    CODE,
    PROBLEM_ID,
    NoPostgres,
    feed,
    pk,
    seed_content,
    solve_of,
    start,
    step_of,
    types,
)

from mathbank_rest import step_diagnosis_logic as logic
from mathbank_rest import stores
from mathbank_rest.models.ddb.content import (
    ContentFacet,
    ContentLi,
    ContentLiKey,
    ContentStep,
    ContentTaxnode,
)
from mathbank_rest.models.ddb.learner import LearnerProfile
from mathbank_rest.models.manual.learner_diagnosis import (
    LearnerDiag,
    LearnerGap,
    LearnerPlan,
    LearnerUniqueDiagFp,
    diag_prefix,
)
from mathbank_rest.models.manual.learner_solve import LearnerStepstate, skill_keys, step_sk
from mathbank_rest.step_logic import InvalidTransition, NotFound
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import typed
from mathbank_rest.stores.content import DynamoDBContentStore
from mathbank_rest.stores.errors import ConditionFailed, ItemSchemaError
from mathbank_rest.stores.learner import DynamoDBLearnerStore, diagnosis, hooks
from mathbank_rest.stores.learner import uow as uow_module

NOW = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
ANSWER = "Use the angle bisector theorem to compare the ratios"
SEED = "Apply the angle bisector theorem to get the ratio of the two segments."
SK_UUID = {f"SK{i}": str(uuid.UUID(int=i)) for i in (1, 2, 3)}
TYPES = ("MCQ_METHOD_RECOGNITION", "MCQ_INTERMEDIATE_SKILL", "SUBPROBLEM_NEXT_INTERMEDIATE", "SUBPROBLEM_FIRST_MOVE",
         "MCQ_METHOD_RECOGNITION", "MCQ_INTERMEDIATE_SKILL", "SUBPROBLEM_FIRST_MOVE", "MCQ_FIRST_MOVE")
EVALUATION = {"verdict": "INCORRECT", "failure_mode": "CANNOT_EXECUTE", "failure_location": "SKILL", "feedback": "look again"}


# ---------------------------------------------------------------------------------------------------------- content

def seed_taxonomy() -> None:
    for nid, ntype, extra in (("SK1", "SKILL", {"skill_id": SK_UUID["SK1"]}), ("SK2", "SKILL", {"skill_id": SK_UUID["SK2"]}),
                              ("SK3", "SKILL", {"skill_id": SK_UUID["SK3"]}), ("SC1", "SUBCONCEPT", {}),
                              ("C1", "CONCEPT", {"concept_id": str(uuid.UUID(int=99))})):
        typed.put(ContentTaxnode.model_validate({
            "PK": f"TAXNODE#{nid}", "SK": "META", "type": "TAXNODE", "content_sha256": "c" * 64, "eligible": True,
            "example_problem_codes": [CODE], "lifecycle": "ACTIVE", "name": f"name {nid}", "node_type": ntype, "problem_count": 3,
            "src_rev": 1, "taxonomy_node_id": nid, "updated_at": NOW,
            "vector_state": {"index": "i", "keys": [nid], "model": "m", "sha256": "s" * 64}, **extra}))


def add_li(lid: str, ttype: str, *, skill: str = "SK1", sub: str = "SC1", eligible: bool = True, seed: str = SEED) -> str:
    form = "MCQ" if ttype.startswith("MCQ") else "SUBPROBLEM"
    source = str(uuid.uuid4())
    typed.put(ContentLi.model_validate({
        "PK": f"LI#{lid}", "SK": "META", "type": "LI", "anchor_step_ids": ["st1"], "approval_method": "automatic", "approved_at": NOW,
        "book_code": "BK", "content_sha256": "c" * 64, "diagram_strategy": "NONE_REQUIRED_BY_SOURCE", "difficulty_direction": "LOWER",
        "eligible": eligible, "generation_mode": "RULE_SEEDED_V3", "learning_item_id": lid, "occurrence": 1, "requires_source_problem": False,
        "source_problem_code": "BK_P1", "source_problem_id": source, "source_transformation_id": "t", "src_rev": 1,
        "target_concept_node_id": "C1", "target_subconcept_node_id": sub, "transformation_type": ttype, "transformed_form": form,
        "updated_at": NOW, "question_text": f"Which idea fits task {lid}?", "target_skill_node_id": skill, "solution_part_label": "A",
        "choices": ["Compare areas of the triangles", ANSWER, "Apply the law of cosines directly"] if form == "MCQ" else None,
        "vector_state": {"index": "i", "keys": [str(uuid.uuid4())], "model": "m", "sha256": "s" * 64}}))
    typed.put(ContentLiKey(PK=f"LI#{lid}", SK="KEY", content_sha256="k" * 64, learning_item_id=lid, src_rev=1,
                           correct_answer=ANSWER if form == "MCQ" else None, answer_or_solution_seed=seed))
    typed.put(ContentFacet(PK=f"FACET#LI#TARGET_SUBCONCEPT#{sub}", SK=lid, content_sha256="c" * 64, dim="TARGET_SUBCONCEPT", entity_id=lid,
                           src_rev=1, unit="LI", value=sub, vector_keys=[uuid.uuid4()], target_skill_node_id=skill,
                           transformation_type=ttype, transformed_form=form, source_problem_id=source, target_subconcept_node_id=sub))
    return lid


def seed_learning(*, with_worked_example: bool = True) -> None:
    seed_taxonomy()
    for i, ttype in enumerate(TYPES):
        add_li(f"li-sk1-{i}", ttype, skill="SK1")
    for i, ttype in enumerate(TYPES[:5]):
        add_li(f"li-sk2-{i}", ttype, skill="SK2")
    if with_worked_example:
        typed.put(ContentStep(
            PK="STEP#ex1", SK="META", book_code="B", concept_node_id="C1", content_sha256="c", eligible=True, global_step_index=1,
            hint_level=1, is_checkpoint=False, problem_code="BK_P2", problem_id=str(uuid.uuid4()), skill_name="skill1", skill_node_id="SK1",
            solution_id=str(uuid.uuid4()), solution_part_id="x1", solution_step_id="ex1", src_rev=1, step_index_in_part=1,
            step_text="In the other triangle the bisector divides the opposite side in the ratio of the adjacent sides.",
            step_type="SETUP", subconcept_node_id="SC1", technique_node_ids=[], tutor_role="CORE_BRIDGE", updated_at=NOW,
            vector_state={"index": "i", "keys": [str(uuid.uuid4())], "model": "m", "sha256": "s"}))
        typed.put(ContentFacet(PK="FACET#STEP#SKILL#SK1", SK="ex1", content_sha256="c" * 64, dim="SKILL", entity_id="ex1", src_rev=1,
                               unit="STEP", value="SK1", vector_keys=[uuid.uuid4()], subconcept_node_id="SC1", skill_node_id="SK1"))


@pytest.fixture()
def world(content_table, monkeypatch):
    """moto content + learner tables, the DynamoDB content store, the auto-diagnose seam registered, PostgreSQL forbidden."""
    from mathbank_rest.db import postgres

    seed_content()
    seed_learning()
    monkeypatch.setattr(postgres, "engine", NoPostgres())
    previous = hooks._auto_diagnose
    hooks.register_auto_diagnose(diagnosis.auto_diagnose)
    with stores.override_store("content", DynamoDBContentStore()):
        yield DynamoDBLearnerStore()
    hooks.register_auto_diagnose(previous)


@pytest.fixture()
def student(sid, world):
    return sid


def attempt_of(store, sid) -> str:
    return start(store, sid)["solve_attempt_id"]


def fail(store, sid, aid, step_id="st1", *, times=1, evaluation=EVALUATION, key=None) -> dict:
    """``times`` x (the learner answers, the evaluator fails it); returns the last outcome."""
    out = {}
    for n in range(times):
        v = store.get_attempt_runtime(aid, sid)["attempt"]["state_version"]
        saved = store.submit_step_response(sid, aid, step_id, f"wrong {n}", v)
        out = store.record_step_outcome(aid, step_id, "FAILED", saved["state_version"], evaluation=evaluation,
                                        idempotency_key=f"{key}-{n}" if key else None)
    return out


def succeed(store, sid, aid, step_id="st1") -> dict:
    v = store.get_attempt_runtime(aid, sid)["attempt"]["state_version"]
    saved = store.submit_step_response(sid, aid, step_id, "right", v)
    return store.record_step_outcome(aid, step_id, "SUCCESS", saved["state_version"], evaluation={"verdict": "CORRECT"})


def diags(sid, aid) -> list[LearnerDiag]:
    return typed.query(LearnerDiag, pk(sid), sk_begins=diag_prefix(aid), limit=50).items


def gaps(sid) -> list[LearnerGap]:
    return typed.query(LearnerGap, pk(sid), sk_begins="GAP#", limit=50).items


# ---------------------------------------------------------------------------------------------------------- models

def test_models_accept_the_migrated_shapes_and_refuse_bad_enums(sid):
    aid, did, gid, plan = (str(uuid.uuid4()) for _ in range(4))
    gap = {"PK": f"STUDENT#{sid}", "SK": f"GAP#{gid}", "type": "GAP", "GSI1PK": "GAPSTATUS#UNRESOLVED", "GSI1SK": f"2026-01-01T00:00:00.000000Z#{gid}",
           "student_id": sid, "knowledge_gap_id": gid, "gap_diagnosis_id": did, "solve_attempt_id": aid, "solution_step_id": "s", "rank": 1,
           "failure_location": "SKILL", "failure_mode": "CANNOT_EXECUTE", "target_concept_id": "C", "target_subconcept_id": "S",
           "target_skill_id": "K", "target_skill_node_id": str(uuid.uuid4()), "target_label": "l", "confidence": 0.7,
           "evidence": {"signals": ["a"]}, "status": "UNRESOLVED", "created_at": "2026-01-01T00:00:00.000000Z", "version": 1}
    assert LearnerGap.from_item(gap).to_item() == gap
    for bad in ({"status": "OPEN"}, {"failure_mode": "WHATEVER"}, {"confidence": 1.5}, {"GSI1PK": "GAPSTATUS#RESOLVED"}):
        with pytest.raises(ItemSchemaError):
            LearnerGap.from_item({**gap, **bad})
    diag = {"PK": f"STUDENT#{sid}", "SK": f"SOLVE#{aid}#DIAG#2026-01-01T00:00:00.000000Z#{did}", "type": "DIAG", "student_id": sid,
            "gap_diagnosis_id": did, "solve_attempt_id": aid, "solution_step_id": "s", "trigger": "AUTO", "recommended_action": "RECOVERY_DETOUR",
            "evidence_fingerprint": "f" * 32, "evidence": {"current": {"attempt_count": 2, "help_level": 0, "state": "FAILED"},
                                                           "predecessor_steps": [], "skill_history": {}, "subconcept_failures": 0},
            "probes": [], "diagnoser_version": "rules-v1", "created_at": "2026-01-01T00:00:00.000000Z"}
    LearnerDiag.from_item(diag)
    with pytest.raises(ItemSchemaError):
        LearnerDiag.from_item({**diag, "trigger": "ROBOT"})
    with pytest.raises(ItemSchemaError):
        LearnerDiag.from_item({**diag, "recommended_action": "GIVE_UP"})
    item = {"recovery_plan_item_id": str(uuid.uuid4()), "ordinal": 1, "stage": "RECOGNITION", "item_kind": "LEARNING_ITEM",
            "learning_item_id": "li", "is_transfer": False, "required": True, "status": "PRESENTED", "tries": 0, "added_reason": "PLANNED"}
    base = {"PK": f"STUDENT#{sid}", "SK": f"PLAN#{plan}", "type": "PLAN", "GSI1PK": "PLANSTATUS#ACTIVE", "GSI1SK": f"x#{plan}",
            "student_id": sid, "recovery_plan_id": plan, "solve_attempt_id": aid, "origin_problem_id": str(uuid.uuid4()),
            "origin_step_id": "s", "trigger": "STUDENT_REQUEST", "status": "ACTIVE", "current_item_ordinal": 1, "planner_version": "v",
            "created_at": "2026-01-01T00:00:00.000000Z", "updated_at": "2026-01-01T00:00:00.000000Z", "items": [item], "version": 1,
            "target_label": "t", "target_skill_id": "K", "target_subconcept_id": "S"}
    assert LearnerPlan.from_item(base).to_item()["items"] == [item]
    for bad in ({"status": "DONE"}, {"trigger": "MAGIC"}, {"GSI1PK": "PLANSTATUS#ABORTED"},
                {"items": [{**item, "learning_item_id": None}]}, {"items": [{**item, "stage": "DANCE"}]},
                {"items": [item, {**item, "recovery_plan_item_id": str(uuid.uuid4())}]}):
        with pytest.raises(ItemSchemaError):
            LearnerPlan.from_item({**base, **bad})


# ---------------------------------------------------------------------------------------------------------- A14 skill history

def test_skill_history_reads_only_the_gsi2_projection_and_excludes_the_current_step(student, world):
    other = str(uuid.uuid4())
    for i, (state, help_, ok) in enumerate((("SUCCESS_INDEPENDENT", 0, True), ("SUCCESS_INDEPENDENT", 0, True),
                                            ("SUCCESS_WITH_HELP", 2, None), ("FAILED", 1, None), ("RETRY_PRESENTED", 0, None))):
        step = f"old{i}"
        stamp = f"2026-01-0{i + 1}T00:00:00.000000Z"
        typed.put(LearnerStepstate(
            PK=pk(student), SK=step_sk(other, step), student_id=student, solve_attempt_id=other, problem_id=PROBLEM_ID, solution_step_id=step,
            state=state, first_seen_at=NOW, last_updated_at=NOW, attempt_count=1, help_level_used=help_, returned_to_step_count=0,
            returned_to_problem_count=0, skill_node_id="SK1", subconcept_node_id="SC1", independent_success=ok, last_response_text="secret",
            version=1, **skill_keys(student, "SK1", stamp, other, step)))
    assert diagnosis.skill_history(student, "SK1", str(uuid.uuid4()), "none") == {"independent": 2, "with_help": 1, "failed": 2}
    assert diagnosis.skill_history(student, "SK1", other, "old0") == {"independent": 1, "with_help": 1, "failed": 2}   # current step excluded
    assert diagnosis.skill_history(student, "SK9", other, "old0") == {"independent": 0, "with_help": 0, "failed": 0}
    assert diagnosis.seen_steps(student, "SK1") == {f"old{i}" for i in range(5)}


# ---------------------------------------------------------------------------------------------------------- T13 manual diagnosis

def test_manual_diagnosis_writes_the_diagnosis_gaps_and_events_in_one_transaction(student, world):
    aid = attempt_of(world, student)
    out = world.diagnose_step(student, aid, "st1")
    assert out["reused"] is False and out["trigger"] == "STUDENT_REQUEST" and out["solution_step_id"] == "st1"
    assert [h["rank"] for h in out["hypotheses"]] == [1] and out["hypotheses"][0]["status"] == "UNRESOLVED"
    assert out["hypotheses"][0]["target_skill_node_id"] == SK_UUID["SK1"] and out["hypotheses"][0]["target_label"] == "skill1"
    assert out["recommended_action"] == "DIAGNOSTIC_PROBE"
    assert out["evidence"]["current"] == {"state": "PRESENTED", "attempt_count": 0, "help_level": 0, "failure_mode": None,
                                          "failure_location": None, "verdict": None}
    stored = diags(student, aid)
    assert len(stored) == 1 and stored[0].trigger == "STUDENT_REQUEST" and stored[0].diagnoser_version == "rules-v1"
    sentinel = typed.require(LearnerUniqueDiagFp, pk(student), f"UNIQUE#diag_fp#{aid}#st1#{stored[0].evidence_fingerprint}")
    assert sentinel.diag_sk == stored[0].SK and str(sentinel.gap_diagnosis_id) == out["gap_diagnosis_id"]
    [gap] = gaps(student)
    assert (gap.status, gap.rank, gap.GSI1PK, gap.version, gap.target_skill_id) == ("UNRESOLVED", 1, "GAPSTATUS#UNRESOLVED", 1, "SK1")
    assert types(student, aid)[-2:] == ["GAP_HYPOTHESIS_CREATED", "GAP_DIAGNOSED"]
    assert solve_of(student, aid).state_version == 2                                # the runtime mode and version are untouched
    assert {p["kind"] for p in out["probes"]} <= {"LEARNING_ITEM", "PRACTICE_STEP"} and out["probes"]
    assert all("question_text" not in p and "step_text" not in p for p in out["probes"])


def test_identical_evidence_returns_the_existing_diagnosis(student, world):
    aid = attempt_of(world, student)
    first = world.diagnose_step(student, aid, "st1")
    again = world.diagnose_step(student, aid, "st1")
    assert again["reused"] is True and again["gap_diagnosis_id"] == first["gap_diagnosis_id"]
    assert len(diags(student, aid)) == 1 and len(gaps(student)) == 1
    fail(world, student, aid)                                                       # new evidence: a new diagnosis
    assert world.diagnose_step(student, aid, "st1")["reused"] is False and len(diags(student, aid)) == 2


def test_manual_diagnosis_needs_an_owned_presented_step_of_an_open_attempt(student, world):
    aid = attempt_of(world, student)
    with pytest.raises(NotFound):
        world.diagnose_step(str(uuid.uuid4()), aid, "st1")                          # a foreign learner: 404
    with pytest.raises(NotFound):
        world.diagnose_step(student, str(uuid.uuid4()), "st1")
    with pytest.raises(NotFound):
        world.diagnose_step(student, aid, "no-such-step")
    with pytest.raises(InvalidTransition):
        world.diagnose_step(student, aid, "st3")                                    # not presented yet
    with pytest.raises(ValueError):
        world.diagnose_step(student, aid, "st1", "ROBOT")
    world.submit_attempt(student, aid, solve_of(student, aid).state_version)
    with pytest.raises(InvalidTransition):
        world.diagnose_step(student, aid, "st1")                                    # T13: IN_PROGRESS only
    assert diags(student, aid) == []


def test_concurrent_identical_diagnoses_leave_one_diagnosis(student, world, monkeypatch):
    aid = attempt_of(world, student)
    world.diagnose_step(student, aid, "st1")
    real, calls = diagnosis.existing_diagnosis, []

    def blind_once(*a, **kw):                                                       # the loser read before the winner committed
        calls.append(1)
        return None if len(calls) == 1 else real(*a, **kw)

    monkeypatch.setattr(diagnosis, "existing_diagnosis", blind_once)
    out = world.diagnose_step(student, aid, "st1")
    assert out["reused"] is True and len(calls) == 2 and len(diags(student, aid)) == 1 and len(gaps(student)) == 1


# ---------------------------------------------------------------------------------------------------------- T12 auto-diagnosis seam

def test_auto_diagnosis_joins_the_step_outcome_transaction(student, world):
    aid = attempt_of(world, student)
    first = fail(world, student, aid)
    assert first["diagnosis"] is None and first["gap_status_changes"] == [] and diags(student, aid) == []     # one failed try: no diagnosis
    out = fail(world, student, aid)
    view = out["diagnosis"]
    assert view["trigger"] == "AUTO" and view["ranked_by"] == "RULES" and view["recommended_action"] in logic.ACTIONS
    assert [h["rank"] for h in view["hypotheses"]] == [1] and view["hypotheses"][0]["focus"] == "SKILL"
    assert set(view["hypotheses"][0]) == {"rank", "knowledge_gap_id", "focus", "focus_label", "target_label", "likelihood", "status",
                                          "source_step_id"}
    [stored] = diags(student, aid)
    assert stored.trigger == "AUTO" and stored.evidence.current.attempt_count == 2 and stored.evidence.current.state == "FAILED"
    assert stored.evidence.current.failure_mode == "CANNOT_EXECUTE"
    assert step_of(student, aid, "st1").state == "RETRY_PRESENTED" and solve_of(student, aid).state_version == out["state_version"]
    assert types(student, aid)[-3:] == ["STEP_PRESENTED", "GAP_HYPOTHESIS_CREATED", "GAP_DIAGNOSED"]
    runtime = world.get_attempt_runtime(aid, student)
    assert runtime["current_step"]["diagnosis"]["gap_diagnosis_id"] == view["gap_diagnosis_id"]             # the runtime view calls the seam


def test_a_repeated_fingerprint_adds_no_diagnosis_but_the_outcome_still_returns_it(student, world):
    aid = attempt_of(world, student)
    first = fail(world, student, aid, times=2)["diagnosis"]
    v = world.get_attempt_runtime(aid, student)["attempt"]["state_version"]
    again = world.record_step_outcome(aid, "st1", "FAILED", v, evaluation=EVALUATION)       # no new response: identical evidence
    assert again["diagnosis"]["gap_diagnosis_id"] == first["gap_diagnosis_id"]
    assert len(diags(student, aid)) == 1 and len(gaps(student)) == 1
    assert [c["to"] for c in again["gap_status_changes"]] == ["CONFIRMED"]                  # but the open hypothesis moved


def test_gap_statuses_follow_later_outcomes_with_a_version_cas(student, world):
    aid = attempt_of(world, student)
    fail(world, student, aid, times=2)
    [gap] = gaps(student)
    v = world.get_attempt_runtime(aid, student)["attempt"]["state_version"]
    confirmed = world.record_step_outcome(aid, "st1", "FAILED", v, evaluation=EVALUATION)
    assert confirmed["gap_status_changes"] == [{"knowledge_gap_id": str(gap.knowledge_gap_id), "from": "UNRESOLVED", "to": "CONFIRMED"}]
    [now] = gaps(student)
    assert (now.status, now.GSI1PK, now.version, now.status_reason) == ("CONFIRMED", "GAPSTATUS#CONFIRMED", 2, "FAILED on st1")
    assert now.resolved_at is None and now.status_changed_at is not None
    assert "GAP_HYPOTHESIS_CONFIRMED" in types(student, aid)
    done = succeed(world, student, aid)                                                     # an independent success resolves it
    assert [c["to"] for c in done["gap_status_changes"]] == ["RESOLVED"]
    [resolved] = gaps(student)
    assert (resolved.status, resolved.GSI1PK, resolved.version) == ("RESOLVED", "GAPSTATUS#RESOLVED", 3) and resolved.resolved_at is not None
    assert types(student, aid).count("GAP_HYPOTHESIS_RESOLVED") == 1
    # a resolved gap is not moved again
    assert world.update_gap_statuses(student, aid, "st1", "FAILED", False, "TUTOR") == []


def test_update_gap_statuses_runs_in_its_own_transaction_with_the_same_rules(student, world):
    aid = attempt_of(world, student)
    world.diagnose_step(student, aid, "st1")
    assert world.update_gap_statuses(student, aid, "st1", "SUCCESS", False, "TUTOR") == []              # help: not enough evidence
    [moved] = world.update_gap_statuses(student, aid, "st1", "SUCCESS", True, "TUTOR")
    assert (moved["from"], moved["to"]) == ("UNRESOLVED", "REJECTED") and gaps(student)[0].resolved_at is not None
    assert world.update_gap_statuses(student, aid, "no-such-step", "FAILED", False, "TUTOR") == []


def test_a_gap_version_race_fails_the_whole_outcome_and_nothing_is_written(student, world, monkeypatch):
    aid = attempt_of(world, student)
    fail(world, student, aid, times=2)
    [gap] = gaps(student)
    stale = gap.model_copy(update={"version": 7})                                           # another writer moved the gap
    monkeypatch.setattr(diagnosis, "load_gaps", lambda sid: [stale])
    v = world.get_attempt_runtime(aid, student)["attempt"]["state_version"]
    before = (step_of(student, aid, "st1").version, len(feed(student)), solve_of(student, aid).state_version)
    with pytest.raises(ConditionFailed):
        world.record_step_outcome(aid, "st1", "FAILED", v, evaluation=EVALUATION)
    assert (step_of(student, aid, "st1").version, len(feed(student)), solve_of(student, aid).state_version) == before
    assert gaps(student)[0].status == "UNRESOLVED"


def test_the_outcome_is_idempotent_with_its_diagnosis(student, world):
    aid = attempt_of(world, student)
    v = world.get_attempt_runtime(aid, student)["attempt"]["state_version"]
    saved = world.submit_step_response(student, aid, "st1", "x", v)
    saved = world.submit_step_response(student, aid, "st1", "y", saved["state_version"])
    first = world.record_step_outcome(aid, "st1", "FAILED", saved["state_version"], evaluation=EVALUATION, idempotency_key="o-1")
    replay = world.record_step_outcome(aid, "st1", "FAILED", saved["state_version"], evaluation=EVALUATION, idempotency_key="o-1")
    assert first["diagnosis"] and replay["replayed"] is True and replay["diagnosis"] == first["diagnosis"]
    assert len(diags(student, aid)) == 1 and len(gaps(student)) == 1 and types(student, aid).count("GAP_DIAGNOSED") == 1


def test_a_prerequisite_step_adds_a_prerequisite_hypothesis(student, world):
    aid = attempt_of(world, student)
    succeed(world, student, aid, "st1")
    fail(world, student, aid, "st2", times=2)
    [stored] = diags(student, aid)
    view = world.get_step_diagnosis_view(student, aid, "st2")
    kinds = {h["focus"] for h in view["hypotheses"]}
    assert kinds == {"SKILL", "PREREQUISITE"} and view["hypotheses"][0]["focus"] == "SKILL"
    prereq = next(h for h in view["hypotheses"] if h["focus"] == "PREREQUISITE")
    assert prereq["source_step_id"] == "st1" and stored.evidence.predecessor_steps == ["st1"]
    assert world.get_step_diagnosis_view(student, aid, "st1") is None


# ---------------------------------------------------------------------------------------------------------- budget (<= 100 items)

class Recorder:
    """Wraps the real seam, recording the transaction size it saw (``len`` before the hook, ``remaining``)."""

    def __init__(self) -> None:
        self.seen: list[tuple[int, int]] = []

    def __call__(self, uow, ctx):
        self.seen.append((len(uow), uow.remaining()))
        return diagnosis.auto_diagnose(uow, ctx)


def test_the_diagnosis_fits_exactly_or_is_skipped_without_losing_the_outcome(student, world, monkeypatch):
    aid = attempt_of(world, student)
    probe = Recorder()
    hooks.register_auto_diagnose(probe)
    fail(world, student, aid)
    fail(world, student, aid)                                           # fires: 1 hypothesis = DIAG + sentinel + GAP + 2 events
    ops_before, remaining = probe.seen[-1]
    need = 2 + 1 + 1 + 1
    assert remaining >= need and len(diags(student, aid)) == 1
    # the same outcome with room for one item less than the diagnosis needs: skipped, committed without it
    other = str(uuid.uuid4())
    aid2 = attempt_of(world, other)
    monkeypatch.setattr(uow_module, "MAX_ITEMS", ops_before + 1 + (need - 1))
    fail(world, other, aid2)
    out = fail(world, other, aid2)
    assert out["diagnosis"] is None and out["state"] == "FAILED" and diags(other, aid2) == [] and gaps(other) == []
    assert step_of(other, aid2, "st1").state == "RETRY_PRESENTED"                                   # the outcome itself is intact
    assert types(other, aid2).count("STEP_EVALUATED") == 2
    # with exactly enough room it is included
    third = str(uuid.uuid4())
    aid3 = attempt_of(world, third)
    monkeypatch.setattr(uow_module, "MAX_ITEMS", ops_before + 1 + need)
    fail(world, third, aid3)
    assert fail(world, third, aid3)["diagnosis"] is not None and len(diags(third, aid3)) == 1


def test_gap_status_changes_are_dropped_before_the_outcome_when_they_do_not_fit(student, world):
    aid = attempt_of(world, student)
    fail(world, student, aid, times=2)
    scratch = uow_module.LearnerUnitOfWork(student)
    ctx = {"student_id": student, "attempt_id": aid, "solution_step_id": "st1", "solve": solve_of(student, aid),
           "step_state": step_of(student, aid, "st1"), "outcome": "FAILED", "actor": "TUTOR", "out": {}, "budget": 1}
    assert diagnosis.auto_diagnose(scratch, ctx) is False and len(scratch) == 0 and ctx["out"]["gap_status_changes"] == []
    assert gaps(student)[0].status == "UNRESOLVED"


def test_an_unexpected_failure_in_the_seam_never_loses_the_outcome(student, world, monkeypatch):
    aid = attempt_of(world, student)

    def boom(*a, **kw):
        raise RuntimeError("diagnoser down")

    monkeypatch.setattr(diagnosis, "build_context", boom)
    fail(world, student, aid)
    out = fail(world, student, aid)
    assert out["state"] == "FAILED" and out["diagnosis"] is None and diags(student, aid) == []
    assert step_of(student, aid, "st1").state == "RETRY_PRESENTED"


# ---------------------------------------------------------------------------------------------------------- reads (A19, A21, A22)

def test_list_diagnoses_newest_first_with_owner_scoping(student, world):
    aid = attempt_of(world, student)
    world.diagnose_step(student, aid, "st1")
    fail(world, student, aid)
    second = world.diagnose_step(student, aid, "st1")
    rows = world.list_diagnoses(student, aid)
    assert rows[0]["gap_diagnosis_id"] == second["gap_diagnosis_id"] and len(rows) == 2
    assert set(rows[0]) == {"gap_diagnosis_id", "student_id", "solve_attempt_id", "solution_step_id", "trigger", "recommended_action",
                            "evidence", "probes", "diagnoser_version", "ai_rerank", "created_at", "hypotheses"}
    assert set(rows[0]["hypotheses"][0]) == {"knowledge_gap_id", "rank", "failure_location", "failure_mode", "target_concept_id",
                                              "target_subconcept_id", "target_skill_id", "target_skill_node_id", "target_label",
                                              "source_step_id", "confidence", "evidence", "status", "status_reason", "created_at",
                                              "status_changed_at", "resolved_at"}
    assert world.list_diagnoses(None, aid) == rows                                          # the admin read resolves the owner
    with pytest.raises(NotFound):
        world.list_diagnoses(str(uuid.uuid4()), aid)
    with pytest.raises(NotFound):
        world.list_diagnoses(None, str(uuid.uuid4()))
    latest = world.get_latest_diagnosis_for_step(student, aid, "st1")
    assert latest["gap_diagnosis_id"] == second["gap_diagnosis_id"] and world.get_latest_diagnosis_for_step(student, aid, "st2") is None


def test_list_student_gaps_filters_by_status_and_limits(student, world):
    aid = attempt_of(world, student)
    succeed(world, student, aid, "st1")
    fail(world, student, aid, "st2", times=2)
    rows = world.list_student_gaps(student)
    assert len(rows) == 2 and rows[0]["rank"] == 1 and {r["status"] for r in rows} == {"UNRESOLVED"}
    assert set(rows[0]) == {"knowledge_gap_id", "gap_diagnosis_id", "solve_attempt_id", "solution_step_id", "rank", "failure_location",
                            "failure_mode", "target_concept_id", "target_subconcept_id", "target_skill_id", "target_label", "source_step_id",
                            "confidence", "evidence", "status", "status_reason", "created_at", "status_changed_at", "resolved_at"}
    assert world.list_student_gaps(student, "RESOLVED") == [] and len(world.list_student_gaps(student, limit=1)) == 1
    assert world.list_student_gaps(str(uuid.uuid4())) == []                                 # another learner's gaps are not visible


def profile(sid: str, email: str) -> LearnerProfile:
    return LearnerProfile(
        PK=toolkit.student_pk(sid), SK="PROFILE", student_id=sid, email=email, email_lc=email, first_name="A", last_name="B", display_name="A B",
        password_hash="h", search_blob=email, status="ACTIVE", is_anonymous=False, token_version=0, version=1, created_at=NOW, updated_at=NOW)


def test_admin_gap_overview_across_learners(student, world):
    other = str(uuid.uuid4())
    typed.put(profile(student, "ann@x.org"))
    typed.put(profile(other, "bob@y.org"))
    aid, aid2 = attempt_of(world, student), attempt_of(world, other)
    fail(world, student, aid, times=2)
    fail(world, other, aid2, times=2)
    v = world.get_attempt_runtime(aid2, other)["attempt"]["state_version"]
    world.record_step_outcome(aid2, "st1", "FAILED", v, evaluation=EVALUATION)                  # bob's gap: CONFIRMED
    out = world.get_admin_gap_overview()
    assert set(out) == {"totals", "top_open_targets", "gaps"} and out["totals"] == {"UNRESOLVED": 1, "CONFIRMED": 1}
    assert out["top_open_targets"] == [{"target_id": "SK1", "target_label": "skill1", "open_gaps": 2, "students": 2}]
    assert {g["email"] for g in out["gaps"]} == {"ann@x.org", "bob@y.org"}
    row = next(g for g in out["gaps"] if g["email"] == "ann@x.org")
    assert row["problem_code"] == CODE and row["trigger"] == "AUTO" and row["ai_reranked"] is False
    assert row["recovery_plan_id"] is None and row["recovery_status"] is None and row["status"] == "UNRESOLVED"
    assert set(row) == {"knowledge_gap_id", "gap_diagnosis_id", "student_id", "email", "solve_attempt_id", "problem_code", "solution_step_id",
                        "rank", "failure_location", "failure_mode", "target_skill_id", "target_label", "source_step_id", "confidence",
                        "status", "status_reason", "created_at", "status_changed_at", "trigger", "recommended_action", "ai_reranked",
                        "recovery_plan_id", "recovery_status"}
    only = world.get_admin_gap_overview(status="CONFIRMED")
    assert [g["email"] for g in only["gaps"]] == ["bob@y.org"] and only["totals"] == {"UNRESOLVED": 1, "CONFIRMED": 1}
    by_mail = world.get_admin_gap_overview(student="ANN@")
    assert by_mail["totals"] == {"UNRESOLVED": 1} and [g["email"] for g in by_mail["gaps"]] == ["ann@x.org"]
    assert [g["email"] for g in world.get_admin_gap_overview(student=other)["gaps"]] == ["bob@y.org"]
    assert len(world.get_admin_gap_overview(limit=1)["gaps"]) == 1


# ---------------------------------------------------------------------------------------------------------- optional re-rank

def test_rerank_is_stored_once_and_only_when_valid(student, world, monkeypatch):
    aid = attempt_of(world, student)
    succeed(world, student, aid, "st1")
    fail(world, student, aid, "st2", times=2)
    [stored] = diags(student, aid)
    did = str(stored.gap_diagnosis_id)
    assert world.rerank_diagnosis(student, aid, did, lambda c: {"order": []}) is None                   # disabled by default
    ids = [h["knowledge_gap_id"] for h in world.get_latest_diagnosis_for_step(student, aid, "st2")["hypotheses"]]
    assert world.rerank_diagnosis(student, aid, did, lambda c: {"order": ids[:1]}, force=True) is None            # not a permutation
    assert world.rerank_diagnosis(student, aid, did, lambda c: (_ for _ in ()).throw(RuntimeError("down")), force=True) is None
    seen = {}

    def model(context):
        seen["ctx"] = context
        return {"order": list(reversed(ids)), "rationale": "teacher note", "model": "fake"}

    done = world.rerank_diagnosis(student, aid, did, model, force=True)
    assert done["ai_rerank"]["order"] == list(reversed(ids)) and done["ai_rerank"]["changed"] is True
    assert seen["ctx"]["step_type"] == "SETUP" and "step_text" not in str(seen["ctx"])
    again = world.rerank_diagnosis(student, aid, did, lambda c: {"order": ids, "rationale": "x"}, force=True)
    assert again["ai_rerank"]["order"] == list(reversed(ids))                                          # set once
    view = logic.student_view(world.get_latest_diagnosis_for_step(student, aid, "st2"))
    assert view["ranked_by"] == "AI" and [h["knowledge_gap_id"] for h in view["hypotheses"]] == list(reversed(ids))
    assert "teacher note" not in str(view)
    assert world.get_admin_gap_overview()["gaps"][0]["ai_reranked"] is True
    assert world.rerank_diagnosis(student, aid, str(uuid.uuid4()), model, force=True) is None


def test_no_postgres_is_touched(student, world):
    aid = attempt_of(world, student)
    fail(world, student, aid, times=2)
    world.list_diagnoses(student, aid)
    world.get_admin_gap_overview()
    world.list_student_gaps(student)
