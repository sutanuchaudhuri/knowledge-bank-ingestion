"""WP5 diagnosis / recovery areas against the REAL ``test`` data-plane environment: concurrent duplicates and racing writers.

Skipped unless MB_DDB_ENV=test (``make test-ddb-integration``). Needs ``make -C ../mathbank-db aws-provision AWS_ENV=test``.
The attempt is seeded directly (SOLVE, OWNER, STEPSTATE, one DIAG with its GAP, learning items are not needed: the plan is seeded too), so no
content table is needed; everything is removed afterwards. Never point this at ``dev``: that environment holds the migrated copy of real data.
"""
from __future__ import annotations

import datetime as dt
import threading
import uuid

import pytest

from mathbank_rest.models.manual.learner_diagnosis import (
    LearnerGap,
    LearnerPlan,
    LearnerPlanOwner,
    PlanItem,
    gap_keys,
    gap_sk,
    plan_keys,
    plan_owner_pk,
    plan_sk,
)
from mathbank_rest.models.manual.learner_solve import (
    LearnerSolve,
    LearnerSolveOwner,
    LearnerStepstate,
    open_solve_keys,
    owner_pk,
    skill_keys,
    solve_sk,
    solves_keys,
    step_sk,
)
from mathbank_rest.step_logic import StateVersionConflict
from mathbank_rest.stores import ddb as t
from mathbank_rest.stores import typed
from mathbank_rest.stores.learner.recovery import RecoveryDynamoDB
from mathbank_rest.stores.learner.uow import LearnerUnitOfWork

pytestmark = pytest.mark.ddb_integration
CTX = "learner"
THREADS = 8
PROBLEM = str(uuid.uuid4())
THEORY_GRADE = {"result": "SUCCESS", "verdict": "ACKNOWLEDGED", "feedback": "", "grader": "none"}


def _delete(client, pk: str, sk: str) -> None:
    client.delete_item(TableName=t.table_name(CTX), Key={"PK": {"S": pk}, "SK": {"S": sk}})


@pytest.fixture()
def detour(real_env):
    """An IN_PROGRESS attempt in RECOVERY with one ACTIVE plan (worked example presented, one practice item pending) and its gap."""
    sid, aid, pid, gid, did = (str(uuid.uuid4()) for _ in range(5))
    now = dt.datetime.now(dt.UTC)
    stamp = t.encode(now)
    typed.put(LearnerSolve(
        PK=t.student_pk(sid), SK=solve_sk(aid), student_id=sid, solve_attempt_id=aid, problem_id=PROBLEM, attempt_number=1, status="IN_PROGRESS",
        current_mode="RECOVERY", current_solution_part_id="p1", current_solution_step_id="st1", current_recovery_plan_id=pid, recovery_plan_id=pid,
        hint_requested_count=0, plan_ids=[pid], started_at=now, last_activity_at=now, updated_at=now, version=3, **open_solve_keys(aid, stamp),
        **solves_keys(sid, aid, stamp)))
    typed.put(LearnerSolveOwner(PK=owner_pk(aid), SK="OWNER", student_id=sid, problem_id=PROBLEM))
    typed.put(LearnerStepstate(
        PK=t.student_pk(sid), SK=step_sk(aid, "st1"), student_id=sid, solve_attempt_id=aid, problem_id=PROBLEM, solution_step_id="st1",
        state="DETOURED", first_seen_at=now, last_updated_at=now, attempt_count=1, help_level_used=0, returned_to_step_count=0,
        returned_to_problem_count=0, skill_node_id="SK1", subconcept_node_id="SC1", version=2, **skill_keys(sid, "SK1", stamp, aid, "st1")))
    typed.put(LearnerGap(
        PK=t.student_pk(sid), SK=gap_sk(gid), student_id=sid, knowledge_gap_id=gid, gap_diagnosis_id=did, solve_attempt_id=aid, solution_step_id="st1",
        rank=1, failure_location="SKILL", failure_mode="CANNOT_EXECUTE", target_skill_id="SK1", target_subconcept_id="SC1", target_concept_id="C1",
        target_label="skill1", confidence=0.7, status="UNRESOLVED", created_at=now, version=1, latest_plan_id=pid, latest_plan_status="ACTIVE",
        **gap_keys("UNRESOLVED", stamp, gid)))
    items = [PlanItem(recovery_plan_item_id=uuid.uuid4(), ordinal=1, stage="FOUNDATION", item_kind="THEORY", worked_step_id="ex1",
                      is_transfer=False, required=False, status="PRESENTED", tries=0, presented_at=now),
             PlanItem(recovery_plan_item_id=uuid.uuid4(), ordinal=2, stage="RETURN_TO_STEP", item_kind="RETURN", is_transfer=False, required=True,
                      status="PENDING", tries=0)]
    typed.put(LearnerPlan(
        PK=t.student_pk(sid), SK=plan_sk(pid), student_id=sid, recovery_plan_id=pid, solve_attempt_id=aid, origin_problem_id=PROBLEM,
        origin_step_id="st1", gap_diagnosis_id=did, knowledge_gap_id=gid, trigger="DIAGNOSIS", target_skill_id="SK1", target_subconcept_id="SC1",
        target_label="skill1", status="ACTIVE", current_item_ordinal=1, planner_version="recovery-rules-v1", created_at=now, updated_at=now,
        items=items, version=1, mastery_policy={"independent_successes_required": 2, "transfer_success_required": True,
                                                "max_help_level_on_final": 1}, **plan_keys("ACTIVE", stamp, pid)))
    typed.put(LearnerPlanOwner(PK=plan_owner_pk(pid), SK="OWNER", student_id=sid))
    yield sid, aid, pid, str(items[0].recovery_plan_item_id)
    client, token = t.client(), None
    while True:
        page = t.query_page(CTX, t.student_pk(sid), limit=100, next_token=token)
        for item in page["items"]:
            _delete(client, item["PK"], item["SK"])
        token = page["next_token"]
        if not token:
            break
    _delete(client, owner_pk(aid), "OWNER")
    _delete(client, plan_owner_pk(pid), "OWNER")


def race(fn, n: int = THREADS) -> list:
    """Run ``fn(i)`` on ``n`` threads released together; returns each result or the exception it raised."""
    barrier, out = threading.Barrier(n), [None] * n

    def work(i: int) -> None:
        barrier.wait()
        try:
            out[i] = fn(i)
        except Exception as exc:  # noqa: BLE001
            out[i] = exc

    threads = [threading.Thread(target=work, args=(i,)) for i in range(n)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(60)
    return out


@pytest.fixture()
def no_content(monkeypatch):
    """The seeded plan has no learning items: the response path never needs content except for the view, which is stubbed."""
    from mathbank_rest.stores.learner import recovery

    monkeypatch.setattr(recovery, "_view", lambda plan_d, items, parent_label: {"recovery_plan_id": plan_d["recovery_plan_id"],
                                                                                "status": plan_d["status"]})


def test_concurrent_duplicate_responses_with_one_key_apply_once_and_all_get_the_same_answer(detour, no_content):
    sid, aid, pid, item = detour
    store = RecoveryDynamoDB()
    results = race(lambda i: store.apply_item_response(sid, pid, item, {"acknowledged": True}, THEORY_GRADE, 3, "same-key"))
    assert not [r for r in results if isinstance(r, Exception)], results
    assert {r["state_version"] for r in results} == {4} and sorted(r["replayed"] for r in results).count(False) == 1
    plan = typed.require(LearnerPlan, t.student_pk(sid), plan_sk(pid))
    assert plan.items[0].tries == 1 and plan.items[0].status == "PASSED"
    assert typed.require(LearnerSolve, t.student_pk(sid), solve_sk(aid)).state_version == 4
    events = typed.query(CTX, t.student_pk(sid), sk_begins="EVT#", limit=50).items
    assert [e.event_type for e in events].count("RECOVERY_ITEM_SUBMITTED") == 1


def test_racing_responses_with_distinct_keys_and_one_version_let_exactly_one_win(detour, no_content):
    sid, aid, pid, item = detour
    store = RecoveryDynamoDB()
    results = race(lambda i: store.apply_item_response(sid, pid, item, {"acknowledged": True}, THEORY_GRADE, 3, f"key-{i}"))
    winners = [r for r in results if isinstance(r, dict)]
    losers = [r for r in results if isinstance(r, Exception)]
    assert len(winners) == 1 and len(losers) == THREADS - 1 and all(isinstance(e, StateVersionConflict) or "NotFound" not in repr(e) for e in losers), results
    assert typed.require(LearnerSolve, t.student_pk(sid), solve_sk(aid)).state_version == 4
    assert typed.require(LearnerPlan, t.student_pk(sid), plan_sk(pid)).items[0].tries == 1


def test_concurrent_aborts_end_the_detour_once(detour, no_content):
    sid, aid, pid, _ = detour
    store = RecoveryDynamoDB()
    results = race(lambda i: store.leave_recovery(sid, pid, 3, abort=True, idempotency_key="abort-key"))
    assert not [r for r in results if isinstance(r, Exception)], results
    assert sorted(r["replayed"] for r in results).count(False) == 1 and {r["state_version"] for r in results} == {4}
    solve = typed.require(LearnerSolve, t.student_pk(sid), solve_sk(aid))
    assert (solve.current_mode, solve.state_version) == ("SOLVING", 4)
    step = typed.require(LearnerStepstate, t.student_pk(sid), step_sk(aid, "st1"))
    assert step.returned_to_step_count == 1 and step.state == "RETRY_PRESENTED"
    types = [e.event_type for e in typed.query(CTX, t.student_pk(sid), sk_begins="EVT#", limit=50).items]
    assert types.count("RECOVERY_PLAN_ABORTED") == 1 and types.count("RETURNED_TO_ORIGINAL_STEP") == 1


def test_the_abort_seam_races_with_a_learner_abort_and_exactly_one_commits(detour, no_content):
    sid, aid, pid, _ = detour
    store = RecoveryDynamoDB()

    def work(i: int):
        if i % 2:
            return store.leave_recovery(sid, pid, 3, abort=True)
        uow = LearnerUnitOfWork(sid)
        store.build_abort_plan_ops(uow, sid, aid, [pid], "SYSTEM", "ATTEMPT_ABANDONED")
        uow.commit()
        return "seam"

    results = race(work, n=4)
    assert sum(not isinstance(r, Exception) for r in results) >= 1
    assert typed.require(LearnerPlan, t.student_pk(sid), plan_sk(pid)).status == "ABORTED"
    types = [e.event_type for e in typed.query(CTX, t.student_pk(sid), sk_begins="EVT#", limit=50).items]
    assert types.count("RECOVERY_PLAN_ABORTED") == 1


def test_gap_status_moves_once_under_concurrent_outcomes(detour):
    from mathbank_rest.stores.learner import diagnosis

    sid, aid, _, _ = detour

    def move(i: int):
        uow = LearnerUnitOfWork(sid)
        changed = diagnosis.stage_gap_changes(uow, sid, aid, "st1", "FAILED", False, "TUTOR", skill_id="SK1", subconcept_id="SC1")
        uow.commit()
        return changed

    results = race(move, n=4)
    assert sum(1 for r in results if isinstance(r, list) and r) == 1, results
    gap = typed.query(LearnerGap, t.student_pk(sid), sk_begins="GAP#", limit=5).items[0]
    assert (gap.status, gap.GSI1PK, gap.version) == ("CONFIRMED", "GAPSTATUS#CONFIRMED", 2)