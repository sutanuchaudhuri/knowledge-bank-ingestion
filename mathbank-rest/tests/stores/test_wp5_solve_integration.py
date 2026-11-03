"""WP5 solve area against the REAL ``test`` data-plane environment: concurrent duplicates and racing writers.

Skipped unless MB_DDB_ENV=test (``make test-ddb-integration``). Needs ``make -C ../mathbank-db aws-provision AWS_ENV=test``.
The attempt is seeded directly (SOLVE, OWNER, STEPSTATE) so no content table is needed; everything is removed afterwards.
Never point this at ``dev``: that environment holds the migrated copy of real data.
"""
from __future__ import annotations

import datetime as dt
import threading
import uuid

import pytest

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
from mathbank_rest.stores.learner.solve import SolveDynamoDB

pytestmark = pytest.mark.ddb_integration
CTX = "learner"
THREADS = 8
PROBLEM = str(uuid.uuid4())


def _delete(client, pk: str, sk: str) -> None:
    client.delete_item(TableName=t.table_name(CTX), Key={"PK": {"S": pk}, "SK": {"S": sk}})


@pytest.fixture()
def attempt(real_env):
    sid, aid, now = str(uuid.uuid4()), str(uuid.uuid4()), dt.datetime.now(dt.UTC)
    stamp = t.encode(now)
    typed.put(LearnerSolve(
        PK=t.student_pk(sid), SK=solve_sk(aid), student_id=sid, solve_attempt_id=aid, problem_id=PROBLEM, attempt_number=1,
        status="IN_PROGRESS", current_mode="SOLVING", current_solution_part_id="p1", current_solution_step_id="st1",
        hint_requested_count=0, plan_ids=[], started_at=now, last_activity_at=now, updated_at=now, version=2,
        **open_solve_keys(aid, stamp), **solves_keys(sid, aid, stamp)))
    typed.put(LearnerSolveOwner(PK=owner_pk(aid), SK="OWNER", student_id=sid, problem_id=PROBLEM))
    typed.put(LearnerStepstate(
        PK=t.student_pk(sid), SK=step_sk(aid, "st1"), student_id=sid, solve_attempt_id=aid, problem_id=PROBLEM, solution_step_id="st1",
        state="PRESENTED", first_seen_at=now, last_updated_at=now, attempt_count=0, help_level_used=0, returned_to_step_count=0,
        returned_to_problem_count=0, skill_node_id="SK1", subconcept_node_id="SC1", version=1,
        **skill_keys(sid, "SK1", stamp, aid, "st1")))
    yield sid, aid
    client, token = t.client(), None
    while True:
        page = t.query_page(CTX, t.student_pk(sid), limit=100, next_token=token)
        for item in page["items"]:
            _delete(client, item["PK"], item["SK"])
        token = page["next_token"]
        if not token:
            break
    _delete(client, owner_pk(aid), "OWNER")


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


def test_concurrent_duplicates_with_one_key_write_once_and_all_get_the_same_answer(attempt):
    sid, aid = attempt
    store = SolveDynamoDB()
    results = race(lambda i: store.request_hint(sid, aid, "st1", 2, "same-key"))
    assert not [r for r in results if isinstance(r, Exception)], results
    assert {r["help_level"] for r in results} == {1} and {r["state_version"] for r in results} == {3}
    assert sorted(r["replayed"] for r in results).count(False) == 1                 # exactly one request did the work
    step = typed.require(LearnerStepstate, t.student_pk(sid), step_sk(aid, "st1"))
    solve = typed.require(LearnerSolve, t.student_pk(sid), solve_sk(aid))
    assert step.help_level_used == 1 and solve.hint_requested_count == 1 and solve.state_version == 3
    events = typed.query("learner", t.student_pk(sid), sk_begins="EVT#", limit=50).items
    assert [e.event_type for e in events] == ["HINT_REQUESTED"]


def test_racing_requests_with_distinct_keys_and_one_version_let_exactly_one_win(attempt):
    sid, aid = attempt
    store = SolveDynamoDB()
    results = race(lambda i: store.submit_step_response(sid, aid, "st1", f"answer {i}", 2, f"key-{i}"))
    winners = [r for r in results if isinstance(r, dict)]
    losers = [r for r in results if isinstance(r, Exception)]
    assert len(winners) == 1 and len(losers) == THREADS - 1 and all(isinstance(e, StateVersionConflict) for e in losers), results
    step = typed.require(LearnerStepstate, t.student_pk(sid), step_sk(aid, "st1"))
    assert step.attempt_count == 1 and typed.require(LearnerSolve, t.student_pk(sid), solve_sk(aid)).state_version == 3
    assert [e.event_type for e in typed.query("learner", t.student_pk(sid), sk_begins="EVT#", limit=50).items] == [
        "STEP_RESPONSE_SUBMITTED"]


def test_concurrent_early_submits_close_the_attempt_once(attempt):
    sid, aid = attempt
    store = SolveDynamoDB()
    results = race(lambda i: store.submit_attempt(sid, aid, 2, "hand-in"))
    assert not [r for r in results if isinstance(r, Exception)], results
    assert sorted(r["replayed"] for r in results).count(False) == 1 and {r["state_version"] for r in results} == {3}
    assert typed.require(LearnerSolve, t.student_pk(sid), solve_sk(aid)).status == "SUBMITTED"
    types = [e.event_type for e in typed.query("learner", t.student_pk(sid), sk_begins="EVT#", limit=50).items]
    assert types == ["ATTEMPT_SUBMITTED"]


def test_a_stale_attempt_is_abandoned_once_even_with_competing_workers(attempt):
    sid, aid = attempt
    store = SolveDynamoDB()
    old = dt.datetime.now(dt.UTC) - dt.timedelta(days=60)
    solve = typed.require(LearnerSolve, t.student_pk(sid), solve_sk(aid))
    typed.update(LearnerSolve, solve.PK, solve.SK, solve.version, {"last_activity_at": old, "GSI1SK": f"{t.encode(old)}#{aid}"})
    results = race(lambda i: store.abandon_stale_attempts(30), n=4)
    assert not [r for r in results if isinstance(r, Exception)], results
    assert sum(aid in r for r in results) == 1
    assert typed.require(LearnerSolve, t.student_pk(sid), solve_sk(aid)).status == "ABANDONED"
