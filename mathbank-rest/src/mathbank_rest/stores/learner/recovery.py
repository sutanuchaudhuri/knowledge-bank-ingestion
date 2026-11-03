"""Learner store, recovery area (requirement 71 WP5; requirement 70 C1 access patterns A23-A25, write paths T14-T19).

``RecoveryPostgres`` delegates to ``step_recovery`` (the SQL layer) at call time, so behaviour is unchanged and monkeypatching tests keep working.
``RecoveryDynamoDB`` is the ``mb-learner`` implementation. A recovery plan is one ``PLAN`` item with its ``items[]`` embedded, so every plan change is
one CAS update (the two-phase ordinal shift of the SQL layer disappears); ``PLAN#<id>/OWNER`` resolves the owner for admin routes. Every operation
is ONE ``LearnerUnitOfWork`` transaction (<= 100 items, the idempotency receipt included): the plan(s), the gaps they resolve, the SOLVE item
(``state_version`` guard, mode, ``current_recovery_plan_id``, ``plan_ids``), the origin STEPSTATE and the events. The pure logic (planning, mastery
policy, adaptation, grading, the learner view) is ``step_recovery_logic``, shared with PostgreSQL. Nothing here imports ``db.postgres``.

Operations (a method is a read exactly when its name starts with a ``stores.READ_PREFIXES`` entry):

* writes  ``create_plan`` (T16), ``apply_item_response`` (T17), ``leave_recovery`` (resume / abort, T18, T19: ``student_id=None`` is the admin abort),
          ``build_abort_plan_ops`` (seam, T15)
* reads   ``get_recovery_plan`` / ``get_next_recovery_item`` (A23), ``load_item_response_context`` (replay check + grading context, read-only),
          ``list_attempt_plans`` (A24), ``list_admin_plans`` / ``get_admin_plan_detail`` (A25), ``get_recovery_summary``

Seam provided to the solve area (stale-session job, T15): ``build_abort_plan_ops(uow, student_id, attempt_id, plan_ids, actor, reason) -> int``
appends to the given unit of work the PLAN updates (ACTIVE / SUSPENDED -> ABORTED, ``ended_at``, unfinished items SKIPPED, ``version`` guard), the
GAP ``latest_plan_status`` update and one RECOVERY_PLAN_ABORTED event per plan, and returns the number of operations added. It never touches the
SOLVE item, a STEPSTATE or the PROBLEM cursor (the caller owns them). It stops adding plans when the transaction would exceed the item limit.

Seam consumed from the solve area: ``returned_to_step_count`` of the origin STEPSTATE is incremented on every return to the step (resume or abort);
the solve area emits RETURNED_TO_ORIGINAL_PROBLEM when it exceeds ``returned_to_problem_count``.

Differences from PostgreSQL that callers can observe (all listed in the WP5 report): the plan carries denormalised ``transformation_type`` /
``transformed_form`` / ``source_problem_id`` per item, an admin abort has no client ``state_version``, candidates come from the ``FACET#`` partitions
(see ``content_reads``) and responses carry datetimes as ISO text, also on replay.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import uuid
from collections.abc import Callable
from typing import Any

from mathbank_rest import step_recovery_logic as logic
from mathbank_rest.models import base
from mathbank_rest.models.manual.learner_diagnosis import (
    LearnerGap,
    LearnerPlan,
    LearnerPlanOwner,
    PlanItem,
    plan_keys,
    plan_owner_pk,
    plan_sk,
)
from mathbank_rest.models.manual.learner_idem import LearnerIdem
from mathbank_rest.models.manual.learner_solve import (
    LearnerProblem,
    LearnerSolve,
    LearnerStepstate,
)
from mathbank_rest.step_logic import (
    IdempotencyKeyReused,
    InvalidTransition,
    NotFound,
    StateVersionConflict,
    check_version,
)
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores import errors as store_errors
from mathbank_rest.stores.errors import ConditionFailed
from mathbank_rest.stores.learner import content_reads
from mathbank_rest.stores.learner.diagnosis import (
    GapPatches,
    diags_of_attempt,
    event_item,
    iso,
    latest_diag,
    load_gaps,
    load_solve,
    load_steps,
    owner_of,
    pk_of,
    plain,
    stamp,
)
from mathbank_rest.stores.learner.solve import _assert_distinct
from mathbank_rest.stores.learner.uow import LearnerUnitOfWork, run_idempotent, with_retries

CTX = "learner"
LOG = logging.getLogger("mathbank_rest.stores.learner.recovery")
MAX_ROWS = 2000
MAX_ITEMS_BYTES = 300_000
RESPONSE_TEXT_KEEP = 2000
OPEN = logic.OPEN_PLAN_STATUSES


# ---------------------------------------------------------------------------------------------- postgres

def _engine():
    from mathbank_rest.db.postgres import engine

    return engine


def _sr():
    from mathbank_rest import step_recovery

    return step_recovery


class RecoveryPostgres:
    """Postgres backend: calls ``step_recovery`` at call time (monkeypatched tests keep working, behaviour unchanged)."""

    def create_plan(self, student_id, attempt_id, state_version: int, *, trigger: str = "STUDENT_REQUEST",
                    gap_diagnosis_id: str | None = None, idempotency_key: str | None = None) -> dict:
        with _engine().begin() as conn:
            return _sr().create_plan(conn, student_id, attempt_id, state_version, trigger=trigger,
                                     gap_diagnosis_id=gap_diagnosis_id, idempotency_key=idempotency_key)

    def get_recovery_plan(self, student_id, plan_id) -> dict:
        with _engine().begin() as conn:
            return _sr().get_plan(conn, student_id, plan_id)

    def get_next_recovery_item(self, student_id, plan_id) -> dict:
        with _engine().begin() as conn:
            return _sr().next_item(conn, student_id, plan_id)

    def load_item_response_context(self, student_id, plan_id, item_id: str, response: dict, state_version: int,
                                   idempotency_key: str | None) -> dict:
        with _engine().begin() as conn:
            return _sr().prepare_item_response(conn, student_id, plan_id, item_id, response, state_version, idempotency_key)

    def apply_item_response(self, student_id, plan_id, item_id: str, response: dict, grade: dict, state_version: int,
                            idempotency_key: str | None = None, actor: str = "TUTOR") -> dict:
        with _engine().begin() as conn:
            return _sr().apply_item_response(conn, student_id, plan_id, item_id, response, grade, state_version, idempotency_key, actor)

    def leave_recovery(self, student_id, plan_id, state_version: int | None, *, abort: bool = False,
                       idempotency_key: str | None = None, actor: str = "STUDENT") -> dict:
        with _engine().begin() as conn:
            return _sr().leave_recovery(conn, student_id, plan_id, state_version, abort=abort, idempotency_key=idempotency_key, actor=actor)

    def list_attempt_plans(self, student_id, attempt_id) -> list[dict]:
        with _engine().begin() as conn:
            return _sr().list_attempt_plans(conn, student_id, attempt_id)

    def list_admin_plans(self, *, student_id=None, status: str | None = None, limit: int = 100) -> list[dict]:
        with _engine().begin() as conn:
            return _sr().admin_plans(conn, student_id=student_id, status=status, limit=limit)

    def get_admin_plan_detail(self, plan_id) -> dict:
        with _engine().begin() as conn:
            return _sr().admin_plan_detail(conn, plan_id)

    def get_recovery_summary(self, attempt_id) -> dict | None:
        with _engine().begin() as conn:
            return _sr().recovery_summary(conn, str(attempt_id))

    def build_abort_plan_ops(self, uow, student_id, attempt_id, plan_ids, actor: str, reason: str) -> int:
        """PostgreSQL aborts an abandoned attempt's plans inside ``step_runtime.abandon_stale_attempts``; nothing to stage here."""
        return 0


# ---------------------------------------------------------------------------------------------- helpers

_UNSET = object()


class _Resume(Exception):
    """A detour is already running: the response is the running plan (``resumed``); no receipt is written."""

    def __init__(self, response: dict) -> None:
        self.response = response


def _default(o: Any) -> Any:
    return iso(o) if isinstance(o, dt.datetime) else str(o)


def _norm(value: Any) -> Any:
    """JSON-safe copy with datetimes as ISO text, so a replayed receipt equals the live response."""
    return json.loads(json.dumps(value, default=_default))


def _receipt(sid: str, key: str | None, operation: str, body: dict, build: Callable[[LearnerUnitOfWork], dict]) -> tuple[dict, bool]:
    """One transaction with the idempotency receipt in it (A18). A concurrent duplicate of the same request fails its own guards first
    (the state moved): the winner's receipt is then the answer. The receipt keeps the response as JSON text (DynamoDB drops ``null`` members)."""
    def checked(uow: LearnerUnitOfWork) -> dict:
        out = _norm(build(uow))
        _assert_distinct(uow.ops())
        return {"json": json.dumps(out)}

    try:
        stored, replayed = run_idempotent(sid, key=key, operation=operation, body=body, build=checked)
    except store_errors.IdempotencyKeyReused:
        raise IdempotencyKeyReused("Idempotency-Key was already used for a different request") from None
    except (StateVersionConflict, ConditionFailed):
        winner = _receipt_of(sid, key)
        if winner is None:
            raise
        if winner.request_hash != ddb.request_hash({"operation": operation, "body": body}):
            raise IdempotencyKeyReused("Idempotency-Key was already used for a different request") from None
        stored, replayed = winner.resolve("response"), True
    return json.loads(stored["json"]), replayed


def _receipt_of(sid: str, key: str | None) -> LearnerIdem | None:
    if not key:
        return None
    item = typed.get(LearnerIdem, pk_of(sid), f"IDEM#{key}")
    return None if item is None or (item.ttl or 1 << 62) <= dt.datetime.now(dt.UTC).timestamp() else item


def _replay(sid: str, key: str | None, operation: str, body: dict) -> dict | None:
    winner = _receipt_of(sid, key)
    if winner is None:
        return None
    if winner.request_hash != ddb.request_hash({"operation": operation, "body": body}):
        raise IdempotencyKeyReused("Idempotency-Key was already used for a different request")
    return {**json.loads(winner.resolve("response")["json"]), "replayed": True}


def _items_of(m: LearnerPlan) -> list[dict]:
    items = [i.model_dump(mode="json") for i in (m.resolve("items", list[PlanItem]) or [])]
    items.sort(key=lambda i: i["ordinal"])
    for i in items:  # a response document holds only what the learner sent (jsonb in SQL); DynamoDB drops nulls inside the grader evidence
        if i.get("last_response") is not None:
            i["last_response"] = {k: v for k, v in i["last_response"].items() if v is not None}
        if i.get("last_result") is not None:
            i["last_result"]["teacher"] = {**dict.fromkeys(("evidence", "failure_mode", "confidence", "grader")), **(i["last_result"].get("teacher") or {})}
    missing = [i["learning_item_id"] for i in items if i["item_kind"] == "LEARNING_ITEM" and not i.get("transformation_type")]
    if missing:
        meta = content_reads.learning_item_meta(missing)
        for i in items:
            if i["item_kind"] == "LEARNING_ITEM" and not i.get("transformation_type") and i["learning_item_id"] in meta:
                i.update(meta[i["learning_item_id"]])
    return items


def _plan_d(m: LearnerPlan) -> dict:
    """The plan as ``step_recovery._plan_row`` returned it."""
    opt = lambda v: None if v is None else str(v)
    return {"recovery_plan_id": str(m.recovery_plan_id), "student_id": str(m.student_id), "solve_attempt_id": str(m.solve_attempt_id),
            "origin_problem_id": str(m.origin_problem_id), "origin_step_id": m.origin_step_id, "gap_diagnosis_id": opt(m.gap_diagnosis_id),
            "knowledge_gap_id": opt(m.knowledge_gap_id), "parent_recovery_plan_id": opt(m.parent_recovery_plan_id), "trigger": m.trigger,
            "target_skill_id": m.target_skill_id, "target_subconcept_id": m.target_subconcept_id, "target_label": m.target_label,
            "status": m.status, "current_item_ordinal": m.current_item_ordinal,
            "mastery_policy": plain(m.resolve("mastery_policy")) or None, "outcome": plain(m.resolve("outcome")) or {},
            "planner_version": m.planner_version, "created_at": m.created_at, "updated_at": m.updated_at, "ended_at": m.ended_at}


class _Plan:
    """A plan being changed in memory (``d``: the row, ``items``: its ordered items); ``model`` is None for a plan created in this transaction."""

    def __init__(self, model: LearnerPlan | None, d: dict, items: list[dict]) -> None:
        self.model, self.d, self.items = model, d, items
        self.changed = model is None

    @property
    def id(self) -> str:
        return self.d["recovery_plan_id"]


class _Tx:
    """The in-memory transaction of one recovery operation: the plans it touches, the events, the gap changes, the SOLVE pointer."""

    def __init__(self, sid: str, solve: LearnerSolve) -> None:
        self.sid, self.solve, self.aid = sid, solve, str(solve.solve_attempt_id)
        self.plans: dict[str, _Plan] = {}
        self.events: list = []
        self.patches = GapPatches(sid)
        self.current_plan: Any = _UNSET
        self.new_plan_ids: list[str] = []
        self.li_meta: dict[str, dict] = {}
        self.now = stamp()
        self._dag: dict | None = None
        self._student_plans: list[LearnerPlan] | None = None
        self._attempted: set[str] | None = None

    # -- loading
    def adopt(self, model: LearnerPlan) -> _Plan:
        p = self.plans.get(str(model.recovery_plan_id))
        if p is None:
            p = self.plans[str(model.recovery_plan_id)] = _Plan(model, _plan_d(model), _items_of(model))
        return p

    def plan(self, plan_id: str) -> _Plan:
        if plan_id in self.plans:
            return self.plans[plan_id]
        return self.adopt(_load_plan(self.sid, plan_id))

    def dag(self) -> dict:
        if self._dag is None:
            self._dag = content_reads.content().get_solution_dag(problem_id=str(self.solve.problem_id))
        return self._dag

    def step_row(self, step_id: str) -> dict:
        return next((s for s in self.dag()["steps"] if s["solution_step_id"] == step_id), {})

    def student_plans(self) -> list[LearnerPlan]:
        if self._student_plans is None:
            self._student_plans = _all_plans(self.sid)
        return self._student_plans

    def used_learning_items(self) -> set[str]:
        """Learning items already in one of the learner's plans (any status but SKIPPED): never offered again."""
        used: set[str] = set()
        for m in self.student_plans():
            if str(m.recovery_plan_id) not in self.plans:
                used |= {i["learning_item_id"] for i in _items_of(m) if i["learning_item_id"] and i["status"] != "SKIPPED"}
        for p in self.plans.values():
            used |= {i["learning_item_id"] for i in p.items if i["learning_item_id"] and i["status"] != "SKIPPED"}
        return used

    def attempted_problems(self) -> set[str]:
        if self._attempted is None:
            page = typed.query(LearnerProblem, pk_of(self.sid), sk_begins="PROBLEM#", limit=200)
            self._attempted = {str(p.problem_id) for p in page.items}
        return self._attempted

    # -- changes
    def event(self, event_type: str, actor: str, step_id: str | None, payload: dict, key: str | None = None) -> None:
        self.events.append(event_item(self.sid, self.aid, event_type, actor, step_id=step_id, payload=payload, key=key))


def _load_plan(sid: str, plan_id: str) -> LearnerPlan:
    m = typed.get(LearnerPlan, pk_of(sid), plan_sk(plan_id))
    if m is None:
        raise NotFound("recovery plan not found")
    return m


def _owned(student_id, plan_id) -> tuple[str, LearnerPlan]:
    """The plan of a learner (a foreign id is 404); ``student_id=None`` is the admin read (owner through the ``PLAN#<id>/OWNER`` pointer)."""
    pid = str(plan_id)
    if student_id is None:
        owner = typed.get(LearnerPlanOwner, plan_owner_pk(pid), "OWNER")
        if owner is None:
            raise NotFound("recovery plan not found")
        sid = str(owner.student_id)
    else:
        sid = str(student_id)
    return sid, _load_plan(sid, pid)


def _all_plans(sid: str) -> list[LearnerPlan]:
    out: list[LearnerPlan] = []
    token = None
    while len(out) < MAX_ROWS:
        page = typed.query(LearnerPlan, pk_of(sid), sk_begins="PLAN#", limit=200, next_token=token)
        out += page.items
        token = page.next_token
        if not token:
            break
    return out


# ---------------------------------------------------------------------------------------------- presentation

def _content_for(item: dict, reveal: bool) -> dict:
    if item["item_kind"] == "THEORY":
        return logic.theory_content(content_reads.content().get_step_worked_example(item["worked_step_id"]))
    if item["item_kind"] == "RETURN":
        return logic.return_content()
    row = content_reads.learning_item_row(item["learning_item_id"], with_key=reveal)
    if row is None:
        raise NotFound("learning item not found")
    return logic.learning_item_content(row, reveal)


def _view(plan_d: dict, items: list[dict], parent_label: Callable[[str], str | None]) -> dict:
    origin = content_reads.content().get_step_origin(plan_d["origin_step_id"])
    parent = plan_d["parent_recovery_plan_id"]
    return logic.plan_view_of(plan_d, items, origin=origin, parent_label=parent_label(parent) if parent else None, content_for=_content_for)


def _stored_view(sid: str, m: LearnerPlan) -> dict:
    def label(parent_id: str) -> str | None:
        parent = typed.get(LearnerPlan, pk_of(sid), plan_sk(parent_id))
        return parent.target_label if parent else None

    return _view(_plan_d(m), _items_of(m), label)


def _tx_view(tx: _Tx, p: _Plan) -> dict:
    return _view(p.d, p.items, lambda parent_id: tx.plan(parent_id).d["target_label"])


# ---------------------------------------------------------------------------------------------- the plan state machine (in memory, mirrors step_recovery)

def _set_status(tx: _Tx, p: _Plan, status: str) -> None:
    p.d["status"], p.d["updated_at"], p.changed = status, tx.now, True
    if p.d["knowledge_gap_id"]:
        gap = tx.patches.load(p.d["knowledge_gap_id"])
        latest = tx.patches.gaps[str(gap.knowledge_gap_id)][1].get("latest_plan_id", gap.latest_plan_id) if gap else None
        if gap is not None and (latest is None or str(latest) == p.id):
            tx.patches.set_plan(gap, p.id, status)


def _present_item(tx: _Tx, p: _Plan, ordinal: int, actor: str = "SYSTEM") -> None:
    item = next(i for i in p.items if i["ordinal"] == ordinal)
    item["status"] = "PRESENTED"
    item["presented_at"] = item["presented_at"] or iso(tx.now)
    p.d["current_item_ordinal"], p.d["updated_at"], p.changed = ordinal, tx.now, True
    tx.event("RECOVERY_ITEM_PRESENTED", actor, p.d["origin_step_id"], {
        "recovery_plan_id": p.id, "recovery_plan_item_id": item["recovery_plan_item_id"], "ordinal": ordinal, "stage": item["stage"],
        "learning_item_id": item["learning_item_id"]})


def _new_item(spec: dict, ordinal: int, reason: str, meta: dict) -> dict:
    li = spec["learning_item_id"]
    return {"recovery_plan_item_id": str(uuid.uuid4()), "ordinal": ordinal, "stage": spec["stage"], "item_kind": spec["item_kind"],
            "learning_item_id": li, "worked_step_id": spec["worked_step_id"], "is_transfer": spec["is_transfer"],
            "required": spec["required"], "status": "PENDING", "tries": 0, "independent_success": None, "last_response": None,
            "last_result": None, "added_reason": reason, "presented_at": None, "completed_at": None,
            "transformation_type": (meta.get(li) or {}).get("transformation_type") if li else None,
            "transformed_form": (meta.get(li) or {}).get("transformed_form") if li else None,
            "source_problem_id": spec.get("source_problem_id") or ((meta.get(li) or {}).get("source_problem_id") if li else None)}


def _add_item_before_return(tx: _Tx, p: _Plan, spec: dict, reason: str) -> int:
    """Insert an adaptive item right after the current one; later items (RETURN included) move down by one."""
    cur = p.d["current_item_ordinal"]
    for i in p.items:
        if i["ordinal"] > cur:
            i["ordinal"] += 1
    p.items.append(_new_item(spec, cur + 1, reason, tx.li_meta))
    p.items.sort(key=lambda i: i["ordinal"])
    p.changed = True
    return cur + 1


def _added_count(p: _Plan) -> int:
    return sum(1 for i in p.items if i["added_reason"] != "PLANNED")


def _candidates(tx: _Tx, origin_problem_id: str, origin_step_id: str, skill_id: str | None, subconcept_id: str | None) -> list[dict]:
    row = tx.step_row(origin_step_id)
    found = content_reads.learning_item_candidates(
        tx.sid, origin_problem_id, skill_id, subconcept_id, exclude_ids=tx.used_learning_items(),
        origin_subconcept=row.get("subconcept_node_id"), origin_concept=row.get("concept_node_id"))
    for c in found:
        tx.li_meta[c["learning_item_id"]] = {k: c[k] for k in ("transformation_type", "transformed_form", "source_problem_id")}
    return found


def _alternate_spec(tx: _Tx, p: _Plan, stage: str, *, transfer: bool = False) -> dict | None:
    used = {i["learning_item_id"] for i in p.items if i["learning_item_id"]}
    cands = _candidates(tx, p.d["origin_problem_id"], p.d["origin_step_id"], p.d["target_skill_id"], p.d["target_subconcept_id"])
    avoid = {i["source_problem_id"] for i in p.items if i.get("source_problem_id")} if transfer else None
    c = logic._pick(cands, logic.STAGE_TYPES.get(stage, logic.STAGE_TYPES["ISOLATED_EXECUTION"]), used, avoid_sources=avoid) \
        or (None if transfer else logic._pick(cands, sum(logic.STAGE_TYPES.values(), ()), used))
    if c is None:
        return None
    return {"stage": stage, "item_kind": "LEARNING_ITEM", "learning_item_id": c["learning_item_id"], "worked_step_id": None,
            "is_transfer": transfer, "required": True, "source_problem_id": c.get("source_problem_id")}


def _branch_target(tx: _Tx, p: _Plan) -> dict | None:
    """Strongest prerequisite hypothesis (a different skill) of the plan's diagnosis, for a child plan."""
    if not p.d["gap_diagnosis_id"]:
        return None
    depth, cur = 0, p
    while cur.d["parent_recovery_plan_id"]:
        depth += 1
        cur = tx.plan(cur.d["parent_recovery_plan_id"])
    if depth >= logic.MAX_BRANCH_DEPTH:
        return None
    rows = [g for g in load_gaps(tx.sid) if str(g.gap_diagnosis_id) == p.d["gap_diagnosis_id"] and g.target_skill_id
            and g.target_skill_id != p.d["target_skill_id"] and g.failure_location == "PREREQUISITE"]
    if not rows:
        return None
    g = min(rows, key=lambda g: (-float(g.confidence), g.rank))
    return {"gap_diagnosis_id": p.d["gap_diagnosis_id"], "knowledge_gap_id": str(g.knowledge_gap_id), "skill_id": g.target_skill_id,
            "subconcept_id": g.target_subconcept_id, "label": g.target_label}


def _create_plan_row(tx: _Tx, step_id: str, target: dict, trigger: str, parent_id: str | None, include_return: bool) -> _Plan:
    """Build (and stage) a plan whose first item is presented. Raises ``NoRecoveryMaterial`` BEFORE changing anything."""
    origin_problem = str(tx.solve.problem_id)
    candidates = _candidates(tx, origin_problem, step_id, target["skill_id"], target["subconcept_id"])
    row = tx.step_row(step_id)
    worked = content_reads.worked_example_step(
        tx.sid, origin_problem, target["skill_id"], tx.attempted_problems(), origin_subconcept=row.get("subconcept_node_id"),
        origin_concept=row.get("concept_node_id"))
    specs = logic.build_plan(candidates, worked, include_return=include_return)
    if not any(s["item_kind"] == "LEARNING_ITEM" for s in specs) and not worked:
        raise logic.NoRecoveryMaterial(f"no approved practice is available for “{target['label'] or 'this skill'}” yet")
    plan_id = str(uuid.uuid4())
    d = {"recovery_plan_id": plan_id, "student_id": tx.sid, "solve_attempt_id": tx.aid, "origin_problem_id": origin_problem,
         "origin_step_id": step_id, "gap_diagnosis_id": target.get("gap_diagnosis_id"), "knowledge_gap_id": target.get("knowledge_gap_id"),
         "parent_recovery_plan_id": parent_id, "trigger": trigger, "target_skill_id": target["skill_id"],
         "target_subconcept_id": target["subconcept_id"], "target_label": target["label"], "status": "ACTIVE",
         "current_item_ordinal": None, "mastery_policy": dict(logic.DEFAULT_POLICY), "outcome": {},
         "planner_version": logic.PLANNER_VERSION, "created_at": tx.now, "updated_at": tx.now, "ended_at": None}
    p = _Plan(None, d, [_new_item(s, s["ordinal"], "PLANNED", tx.li_meta) for s in specs])
    tx.plans[plan_id] = p
    tx.new_plan_ids.append(plan_id)
    tx.event("RECOVERY_PLAN_CREATED", "SYSTEM", step_id, {
        "recovery_plan_id": plan_id, "trigger": trigger, "target_skill_id": target["skill_id"], "target_label": target["label"],
        "items": len(specs), "parent_recovery_plan_id": parent_id, "gap_diagnosis_id": target.get("gap_diagnosis_id")})
    if d["knowledge_gap_id"]:
        gap = tx.patches.load(d["knowledge_gap_id"])
        if gap is not None:
            tx.patches.set_plan(gap, plan_id, "ACTIVE")
    _present_item(tx, p, 1)
    return p


def _end_plan(tx: _Tx, p: _Plan, status: str, mastery: dict, actor: str, reason: str | None = None) -> None:
    p.d["outcome"], p.d["ended_at"] = {"mastery": mastery}, tx.now
    _set_status(tx, p, status)
    event = {"COMPLETED": "RECOVERY_PLAN_COMPLETED", "EXHAUSTED": "RECOVERY_PLAN_EXHAUSTED", "ABORTED": "RECOVERY_PLAN_ABORTED"}[status]
    tx.event(event, actor, p.d["origin_step_id"], {"recovery_plan_id": p.id, "mastery": mastery, **({"reason": reason} if reason else {})})
    if p.d["knowledge_gap_id"] and status in ("COMPLETED", "EXHAUSTED"):
        _update_gap(tx, p, "RESOLVED" if status == "COMPLETED" else "CONFIRMED", actor)


def _update_gap(tx: _Tx, p: _Plan, new: str, actor: str) -> None:
    gap = tx.patches.load(p.d["knowledge_gap_id"])
    if gap is None:
        return
    current = tx.patches.gaps[str(gap.knowledge_gap_id)][1].get("status", gap.status)
    if current not in (("UNRESOLVED", "CONFIRMED") if new == "RESOLVED" else ("UNRESOLVED",)):
        return
    tx.patches.set_status(gap, new, f"recovery plan {p.id} {p.d['status']}", tx.now)
    tx.event(f"GAP_HYPOTHESIS_{new}", actor, gap.solution_step_id, {
        "knowledge_gap_id": str(gap.knowledge_gap_id), "to": new, "recovery_plan_id": p.id, "rank": gap.rank,
        "target_label": gap.target_label, "likelihood_label": _likelihood(gap)})


def _likelihood(gap: LearnerGap) -> str:
    from mathbank_rest import step_diagnosis_logic

    return step_diagnosis_logic.likelihood_label(float(gap.confidence))


def _advance(tx: _Tx, p: _Plan, actor: str) -> dict:
    """Present the next pending item; at RETURN (or the end of a branch) apply the mastery policy."""
    nxt = next((i for i in p.items if i["status"] == "PENDING" and i["ordinal"] > p.d["current_item_ordinal"]), None)
    if nxt is not None and nxt["item_kind"] != "RETURN":
        _present_item(tx, p, nxt["ordinal"], actor)
        return {"transition": "NEXT_ITEM"}
    mastery = logic.mastery_status(p.items, p.d["mastery_policy"] or logic.DEFAULT_POLICY)
    if not mastery["met"] and _added_count(p) < logic.MAX_ADDED_ITEMS:
        spec = (_alternate_spec(tx, p, "TRANSFER", transfer=True) if not mastery["transfer_passed"] else None) \
            or _alternate_spec(tx, p, "ISOLATED_EXECUTION")
        if spec:
            _present_item(tx, p, _add_item_before_return(tx, p, spec, "MASTERY_NOT_YET_MET"), actor)
            return {"transition": "EXTRA_ITEM"}
    _end_plan(tx, p, "COMPLETED" if mastery["met"] else "EXHAUSTED", mastery, actor)
    if p.d["parent_recovery_plan_id"]:  # a branch finished: wake the parent plan
        parent = tx.plan(p.d["parent_recovery_plan_id"])
        _set_status(tx, parent, "ACTIVE")
        tx.current_plan = parent.id
        _advance(tx, parent, actor)
        return {"transition": "BRANCH_FINISHED", "active_recovery_plan_id": parent.id}
    if nxt is not None:  # the RETURN item
        nxt["status"], nxt["presented_at"] = "PRESENTED", iso(tx.now)
        p.d["current_item_ordinal"], p.changed = nxt["ordinal"], True
    return {"transition": "PLAN_" + p.d["status"]}


# ---------------------------------------------------------------------------------------------- writing the transaction

def _fit_items(items: list[dict]) -> list[dict]:
    """The engine's 350 KB item limit: shorten the stored text of long learner answers on the oldest items when the plan grows too big."""
    if len(json.dumps(items, default=str)) <= MAX_ITEMS_BYTES:
        return items
    out = [dict(i) for i in items]
    for i in out:
        resp = i.get("last_response")
        if resp and len(resp.get("response_text") or "") > RESPONSE_TEXT_KEEP:
            i["last_response"] = {**resp, "response_text": resp["response_text"][:RESPONSE_TEXT_KEEP]}
    return out


def _new_model(tx: _Tx, p: _Plan) -> LearnerPlan:
    d = p.d
    return LearnerPlan(
        PK=pk_of(tx.sid), SK=plan_sk(p.id), student_id=tx.sid, recovery_plan_id=p.id, solve_attempt_id=tx.aid,
        origin_problem_id=d["origin_problem_id"], origin_step_id=d["origin_step_id"], gap_diagnosis_id=d["gap_diagnosis_id"],
        knowledge_gap_id=d["knowledge_gap_id"], parent_recovery_plan_id=d["parent_recovery_plan_id"], trigger=d["trigger"],
        target_skill_id=d["target_skill_id"], target_subconcept_id=d["target_subconcept_id"], target_label=d["target_label"],
        status=d["status"], current_item_ordinal=d["current_item_ordinal"], mastery_policy=d["mastery_policy"],
        planner_version=d["planner_version"], created_at=d["created_at"], updated_at=d["updated_at"],
        items=[PlanItem(**i) for i in p.items], version=1, **plan_keys(d["status"], iso(d["created_at"]), p.id))


def _flush_plans(tx: _Tx, uow: LearnerUnitOfWork) -> None:
    for p in tx.plans.values():
        if p.model is None:
            uow.put_new(_new_model(tx, p))
            uow.put_new(LearnerPlanOwner(PK=plan_owner_pk(p.id), SK="OWNER", student_id=tx.sid))
        elif p.changed:
            changes: dict[str, Any] = {"items": _fit_items(p.items), "status": p.d["status"], "current_item_ordinal": p.d["current_item_ordinal"],
                                       "GSI1PK": f"PLANSTATUS#{p.d['status']}"}
            if p.d["outcome"]:
                changes["outcome"] = p.d["outcome"]
            if p.d["ended_at"]:
                changes["ended_at"] = p.d["ended_at"]
            uow.update(LearnerPlan, p.model.PK, p.model.SK, changes, expected={"version": p.model.version},
                       conflict=ConditionFailed("the recovery plan changed; retry"))


def _flush_solve(tx: _Tx, uow: LearnerUnitOfWork, *, mode: str | None = None, step: dict | None = None, remove: tuple[str, ...] = ()) -> None:
    """The one update of the SOLVE item: ``state_version`` guard (+1), activity stamp (the stale-session index), pointer and mode changes."""
    solve = tx.solve
    changes: dict[str, Any] = {"last_activity_at": tx.now, "GSI1SK": f"{iso(tx.now)}#{tx.aid}"}
    if tx.current_plan is not _UNSET and tx.current_plan is not None:
        changes["current_recovery_plan_id"] = tx.current_plan
    if tx.new_plan_ids:
        changes["plan_ids"] = [*(str(p) for p in solve.plan_ids), *tx.new_plan_ids]
    if mode:
        changes["current_mode"] = mode
    changes |= step or {}
    uow.update(LearnerSolve, solve.PK, solve.SK, changes, expected={"version": solve.version, "status": "IN_PROGRESS"}, remove=remove,
               conflict=StateVersionConflict(f"state_version {solve.state_version} is stale. Refetch the runtime."))


def _flush_step(tx: _Tx, uow: LearnerUnitOfWork, step: LearnerStepstate, state: str, *, returned: bool = False) -> None:
    changes: dict[str, Any] = {"state": state, "last_updated_at": tx.now}
    if step.skill_node_id:
        changes["GSI2SK"] = f"{iso(tx.now)}#{tx.aid}#{step.solution_step_id}"
    uow.update(LearnerStepstate, step.PK, step.SK, changes, expected={"version": step.version} if step.version is not None else None,
               increment={"returned_to_step_count": 1} if returned else None,
               conflict=StateVersionConflict("the step changed; refetch the runtime"))


def _flush_rest(tx: _Tx, uow: LearnerUnitOfWork) -> None:
    tx.patches.flush(uow)
    for e in tx.events:
        uow.put_new(e)


# ---------------------------------------------------------------------------------------------- DynamoDB

class RecoveryDynamoDB:
    """DynamoDB backend over mb-learner."""

    # ------------------------------------------------------------------------------------------ T16 create

    def create_plan(self, student_id, attempt_id, state_version: int, *, trigger: str = "STUDENT_REQUEST",
                    gap_diagnosis_id: str | None = None, idempotency_key: str | None = None) -> dict:
        """Start a detour from the attempt's current step (persisted before the first item is shown). If a detour is already running it is
        returned instead (``resumed``)."""
        if trigger not in ("DIAGNOSIS", "STUDENT_REQUEST", "TUTOR"):
            raise ValueError(trigger)
        sid, aid = str(student_id), str(attempt_id)
        body = {"attempt_id": aid, "state_version": state_version, "trigger": trigger, "gap_diagnosis_id": gap_diagnosis_id}

        def build(uow: LearnerUnitOfWork) -> dict:
            solve = load_solve(sid, aid)
            if solve.current_mode == "RECOVERY" and solve.current_recovery_plan_id:
                tx = _Tx(sid, solve)
                plan = tx.plan(str(solve.current_recovery_plan_id))
                raise _Resume(_norm({"recovery_plan": _tx_view(tx, plan), "resumed": True, "state_version": solve.state_version}))
            check_version(solve.state_version, state_version)
            if solve.status != "IN_PROGRESS" or not solve.current_solution_step_id:
                raise InvalidTransition(f"attempt is {solve.status}")
            step_id = solve.current_solution_step_id
            if trigger == "DIAGNOSIS" and gap_diagnosis_id is None:
                raise InvalidTransition("a diagnosis-triggered detour needs gap_diagnosis_id")
            tx = _Tx(sid, solve)
            plan = _create_plan_row(tx, step_id, _target_for(tx, step_id, gap_diagnosis_id), trigger, None, include_return=True)
            step = load_steps(sid, aid).get(step_id)
            _flush_plans(tx, uow)
            _flush_rest(tx, uow)
            if step is not None:
                _flush_step(tx, uow, step, "DETOURED")
            tx.current_plan = plan.id
            _flush_solve(tx, uow, mode="RECOVERY", step={"recovery_plan_id": plan.id})
            return {"recovery_plan": _tx_view(tx, plan), "resumed": False, "state_version": solve.state_version + 1}

        def attempt() -> tuple[dict, bool]:
            return _receipt(sid, idempotency_key, "recovery_create", body, build)

        try:
            response, replayed = with_retries(attempt)
        except _Resume as r:
            return r.response
        return {**response, "replayed": replayed}

    # ------------------------------------------------------------------------------------------ reads (A23, A24, A25)

    def get_recovery_plan(self, student_id, plan_id) -> dict:
        sid, m = _owned(student_id, plan_id)
        return _stored_view(sid, m)

    def get_next_recovery_item(self, student_id, plan_id) -> dict:
        view = self.get_recovery_plan(student_id, plan_id)
        current = next((i for i in view["items"] if i["ordinal"] == view["current_item_ordinal"]), None)
        return {"recovery_plan_id": view["recovery_plan_id"], "status": view["status"], "item": current, "mastery": view["mastery"],
                "can_return": view["can_return"]}

    def list_attempt_plans(self, student_id, attempt_id) -> list[dict]:
        """A24: the attempt's detours, newest first (``SOLVE.plan_ids`` -> BatchGet)."""
        aid = str(attempt_id)
        sid = str(student_id) if student_id is not None else owner_of(aid)
        solve = load_solve(sid, aid)
        models = typed.batch_get(LearnerPlan, [(pk_of(sid), plan_sk(p)) for p in solve.plan_ids])
        models.sort(key=lambda m: m.created_at, reverse=True)
        return [_stored_view(sid, m) for m in models]

    def list_admin_plans(self, *, student_id=None, status: str | None = None, limit: int = 100) -> list[dict]:
        """A25: plans with item outcome counts (a learner's partition, or GSI1 ``PLANSTATUS#<s>``), newest first."""
        if student_id is not None:
            models = [m for m in _all_plans(str(student_id)) if status is None or m.status == status]
        else:
            models = []
            for s in ([status] if status else logic.ENDED + logic.OPEN_PLAN_STATUSES):
                token = None
                while len(models) < MAX_ROWS:
                    page = typed.query(LearnerPlan, f"PLANSTATUS#{s}", index="GSI1", forward=False, limit=200, next_token=token)
                    models += page.items
                    token = page.next_token
                    if not token:
                        break
        models = sorted({str(m.recovery_plan_id): m for m in models}.values(), key=lambda m: m.created_at, reverse=True)
        models = models[:min(max(limit, 1), 500)]
        profile_model = base.model_for(CTX, "PROFILE")
        profiles = {str(p.student_id): p for p in typed.batch_get(
            profile_model, [(pk_of(sid), "PROFILE") for sid in {str(m.student_id) for m in models}])}
        problems: dict[str, str | None] = {}
        rows = []
        for m in models:
            pid = str(m.origin_problem_id)
            if pid not in problems:
                found = content_reads.content().get_problem_by_id(pid)
                problems[pid] = found["canonical_code"] if found else None
            items = _items_of(m)
            rows.append({
                "recovery_plan_id": str(m.recovery_plan_id), "student_id": str(m.student_id),
                "email": getattr(profiles.get(str(m.student_id)), "email", None), "solve_attempt_id": str(m.solve_attempt_id),
                "problem_code": problems[pid], "origin_step_id": m.origin_step_id, "trigger": m.trigger,
                "target_skill_id": m.target_skill_id, "target_label": m.target_label, "status": m.status,
                "parent_recovery_plan_id": str(m.parent_recovery_plan_id) if m.parent_recovery_plan_id else None,
                "outcome": plain(m.resolve("outcome")) or {}, "created_at": m.created_at, "ended_at": m.ended_at, "items": len(items),
                "passed": sum(1 for i in items if i["status"] == "PASSED" and i["item_kind"] == "LEARNING_ITEM"),
                "failed": sum(1 for i in items if i["status"] == "FAILED"),
                "adapted": sum(1 for i in items if i["added_reason"] != "PLANNED")})
        return rows

    def get_admin_plan_detail(self, plan_id) -> dict:
        """A25: one plan with the grader evidence of every item (the learner view plus ``items_teacher``)."""
        sid, m = _owned(None, plan_id)
        view = _stored_view(sid, m)
        view["items_teacher"] = [{k: i[k] for k in logic.TEACHER_ITEM_KEYS} for i in _items_of(m)]
        view["student_id"] = str(m.student_id)
        view["knowledge_gap_id"] = str(m.knowledge_gap_id) if m.knowledge_gap_id else None
        view["gap_diagnosis_id"] = str(m.gap_diagnosis_id) if m.gap_diagnosis_id else None
        return view

    def get_recovery_summary(self, attempt_id) -> dict | None:
        """The pointer of the runtime read model: the attempt's current recovery plan."""
        aid = str(attempt_id)
        solve = load_solve(owner_of(aid), aid)
        if not solve.current_recovery_plan_id:
            return None
        m = typed.get(LearnerPlan, solve.PK, plan_sk(solve.current_recovery_plan_id))
        return {"recovery_plan_id": str(solve.current_recovery_plan_id), "target_label": m.target_label if m else None,
                "status": m.status if m else None}

    # ------------------------------------------------------------------------------------------ T17 item response

    def load_item_response_context(self, student_id, plan_id, item_id: str, response: dict, state_version: int,
                                   idempotency_key: str | None) -> dict:
        """Read-only validation before grading (so a replay or a stale request never triggers a model call): ``{"replay": ...}`` or the
        grading context ``{"item", "plan", "learning_item"}``."""
        sid, m = _owned(student_id, plan_id)
        body = {"plan_id": str(plan_id), "item_id": item_id, "response": response, "state_version": state_version}
        replay = _replay(sid, idempotency_key, "recovery_item_response", body)
        if replay:
            return {"replay": replay}
        plan, items = _plan_d(m), _items_of(m)
        item = next((i for i in items if i["recovery_plan_item_id"] == item_id), None)
        if item is None:
            raise NotFound("recovery item not found")
        if plan["status"] != "ACTIVE" or item["ordinal"] != plan["current_item_ordinal"] or item["status"] != "PRESENTED":
            raise InvalidTransition("only the current item of an active plan accepts a response")
        if item["item_kind"] == "RETURN":
            raise InvalidTransition("use /resume to return to the original problem")
        ctx: dict[str, Any] = {"item": item, "plan": plan}
        if item["item_kind"] == "LEARNING_ITEM":
            row = content_reads.learning_item_row(item["learning_item_id"], with_key=True)
            if row is None:
                raise NotFound("learning item not found")
            ctx["learning_item"] = row
        return ctx

    def apply_item_response(self, student_id, plan_id, item_id: str, response: dict, grade: dict, state_version: int,
                            idempotency_key: str | None = None, actor: str = "TUTOR") -> dict:
        """Record a graded response for the current item and adapt the plan (one transaction, ``state_version`` guarded)."""
        sid, _ = _owned(student_id, plan_id)
        body = {"plan_id": str(plan_id), "item_id": item_id, "response": response, "state_version": state_version}

        def build(uow: LearnerUnitOfWork) -> dict:
            m = _load_plan(sid, str(plan_id))
            solve = load_solve(sid, str(m.solve_attempt_id))
            check_version(solve.state_version, state_version)
            tx = _Tx(sid, solve)
            p = tx.adopt(m)
            item = next((i for i in p.items if i["recovery_plan_item_id"] == item_id), None)
            if item is None or p.d["status"] != "ACTIVE" or item["ordinal"] != p.d["current_item_ordinal"] \
                    or item["status"] != "PRESENTED" or item["item_kind"] == "RETURN":
                raise InvalidTransition("only the current item of an active plan accepts a response")
            tries = item["tries"] + 1
            decision = logic.adapt(item["stage"], grade["result"], tries)
            final = decision != "RETRY"
            item["tries"] = tries
            item["status"] = ("PASSED" if grade["result"] == "SUCCESS" else "FAILED") if final else "PRESENTED"
            item["independent_success"] = (grade["result"] == "SUCCESS" and tries == 1) if final else None
            item["last_response"] = response
            item["last_result"] = logic.teacher_result(grade)
            item["completed_at"] = iso(tx.now) if final else None
            p.changed = True
            student_result = {k: grade[k] for k in ("result", "verdict", "feedback") if k in grade}
            payload = {"recovery_plan_id": p.id, "recovery_plan_item_id": item_id, "ordinal": item["ordinal"], "stage": item["stage"],
                       "learning_item_id": item["learning_item_id"]}
            tx.event("RECOVERY_ITEM_SUBMITTED", "STUDENT", p.d["origin_step_id"], {**payload, "response": response}, idempotency_key)
            tx.event("RECOVERY_ITEM_EVALUATED", actor, p.d["origin_step_id"],
                     {**payload, "result": grade["result"], "tries": tries, "decision": decision, "grader": grade.get("grader")})
            transition: dict[str, Any] = {"transition": "RETRY"}
            if decision == "CONFIRM" and _added_count(p) < logic.MAX_ADDED_ITEMS:
                spec = _alternate_spec(tx, p, item["stage"], transfer=item["is_transfer"])
                if spec:
                    _add_item_before_return(tx, p, spec, "CONFIRMATION_AFTER_HELP")
            elif decision in ("ALTERNATE", "BRANCH"):
                target = _branch_target(tx, p) if decision == "BRANCH" else None
                if target:
                    try:
                        child = _create_plan_row(tx, p.d["origin_step_id"], target, "BRANCH", p.id, include_return=False)
                    except logic.NoRecoveryMaterial:
                        target = None
                    else:
                        _set_status(tx, p, "SUSPENDED")
                        tx.event("RECOVERY_PLAN_BRANCHED", actor, p.d["origin_step_id"], {
                            "recovery_plan_id": p.id, "child_recovery_plan_id": child.id, "target_label": target["label"]})
                        tx.current_plan = child.id
                        transition = {"transition": "BRANCHED", "active_recovery_plan_id": child.id}
                if not target and _added_count(p) < logic.MAX_ADDED_ITEMS:
                    spec = _alternate_spec(tx, p, item["stage"], transfer=item["is_transfer"])
                    if spec:
                        _add_item_before_return(tx, p, spec, "ALTERNATE_AFTER_FAILURE")
            if final and transition["transition"] != "BRANCHED":
                transition = _advance(tx, p, actor)
            _flush_plans(tx, uow)
            _flush_rest(tx, uow)
            _flush_solve(tx, uow)
            active = tx.current_plan if tx.current_plan is not _UNSET else str(solve.current_recovery_plan_id or p.id)
            return {"result": student_result, "decision": decision, **transition, "state_version": solve.state_version + 1,
                    "recovery_plan": _tx_view(tx, tx.plan(active))}

        def attempt() -> tuple[dict, bool]:
            return _receipt(sid, idempotency_key, "recovery_item_response", body, build)

        response_doc, replayed = with_retries(attempt)
        return {**response_doc, "replayed": replayed}

    # ------------------------------------------------------------------------------------------ T18 / T19 resume, abort

    def leave_recovery(self, student_id, plan_id, state_version: int | None, *, abort: bool = False,
                       idempotency_key: str | None = None, actor: str = "STUDENT") -> dict:
        """Return to the exact origin step. ``abort`` ends unfinished plans (and their branches) as ABORTED; otherwise the plan must already
        be COMPLETED or EXHAUSTED. ``student_id=None`` (admin abort, T19) has no client ``state_version``: the loaded one is used."""
        sid, _ = _owned(student_id, plan_id)
        operation = "recovery_abort" if abort else "recovery_resume"
        body = {"plan_id": str(plan_id), "state_version": state_version}

        def build(uow: LearnerUnitOfWork) -> dict:
            m = _load_plan(sid, str(plan_id))
            solve = load_solve(sid, str(m.solve_attempt_id))
            if state_version is not None:
                check_version(solve.state_version, state_version)
            if solve.current_mode != "RECOVERY":
                raise InvalidTransition("the attempt is not in a recovery detour")
            tx = _Tx(sid, solve)
            tx.adopt(m)
            root = tx.plan(str(plan_id))
            while root.d["parent_recovery_plan_id"]:
                root = tx.plan(root.d["parent_recovery_plan_id"])
            family = _family(tx, root.id)
            open_plans = [p for p in family if p.d["status"] in OPEN]
            if open_plans and not abort:
                raise InvalidTransition("finish the detour first, or leave it early with /abort")
            for p in open_plans:
                _end_plan(tx, p, "ABORTED", logic.mastery_status(p.items, p.d["mastery_policy"] or logic.DEFAULT_POLICY), actor)
            for p in family:
                for i in p.items:
                    if i["status"] in ("PENDING", "PRESENTED"):
                        i["status"] = "PASSED" if i["item_kind"] == "RETURN" else "SKIPPED"
                        i["completed_at"] = iso(tx.now)
                        p.changed = True
            step_id = root.d["origin_step_id"]
            step = load_steps(sid, tx.aid).get(step_id)
            tx.event("RETURNED_TO_ORIGINAL_STEP", actor, step_id, {"recovery_plan_id": root.id, "aborted": bool(open_plans)}, idempotency_key)
            tx.event("STEP_PRESENTED", "SYSTEM", step_id, {})
            _flush_plans(tx, uow)
            _flush_rest(tx, uow)
            if step is not None:
                _flush_step(tx, uow, step, "RETRY_PRESENTED" if step.attempt_count > 0 else "PRESENTED", returned=True)
            tx.current_plan = None
            # the SOLVE position never moved during the detour: it is still the origin step
            _flush_solve(tx, uow, mode="SOLVING", remove=("current_recovery_plan_id",))
            return {"returned_to_step_id": step_id, "recovery_plan_id": root.id, "plan_status": root.d["status"],
                    "state_version": solve.state_version + 1}

        def attempt() -> tuple[dict, bool]:
            return _receipt(sid, idempotency_key, operation, body, build)

        response_doc, replayed = with_retries(attempt)
        return {**response_doc, "replayed": replayed}

    # ------------------------------------------------------------------------------------------ T15 seam

    def build_abort_plan_ops(self, uow: LearnerUnitOfWork, student_id, attempt_id, plan_ids, actor: str, reason: str) -> int:
        """Stage the abort of an abandoned attempt's open plans on ``uow`` (see the module docstring); returns the operations added."""
        sid, aid = str(student_id), str(attempt_id)
        before = len(uow)
        models = [m for m in typed.batch_get(LearnerPlan, [(pk_of(sid), plan_sk(p)) for p in plan_ids]) if m.status in OPEN]
        patches = GapPatches(sid)
        for m in sorted(models, key=lambda m: m.created_at):
            if uow.remaining() < 4:
                LOG.warning("attempt %s: plan %s left open, the transaction is full", aid, m.recovery_plan_id)
                continue
            now = stamp()
            items = _items_of(m)
            for i in items:
                if i["status"] in ("PENDING", "PRESENTED"):
                    i["status"], i["completed_at"] = "SKIPPED", iso(now)
            mastery = logic.mastery_status(items, plan_policy(m))
            uow.update(LearnerPlan, m.PK, m.SK, {"items": _fit_items(items), "status": "ABORTED", "outcome": {"mastery": mastery},
                                                 "ended_at": now, "GSI1PK": "PLANSTATUS#ABORTED"},
                       expected={"version": m.version}, conflict=ConditionFailed("the recovery plan changed; retry"))
            if m.knowledge_gap_id:
                gap = patches.load(m.knowledge_gap_id)
                if gap is not None and (gap.latest_plan_id is None or str(gap.latest_plan_id) == str(m.recovery_plan_id)):
                    patches.set_plan(gap, m.recovery_plan_id, "ABORTED")
            uow.put_new(event_item(sid, aid, "RECOVERY_PLAN_ABORTED", actor, step_id=m.origin_step_id,
                                   payload={"recovery_plan_id": str(m.recovery_plan_id), "mastery": mastery, "reason": reason}))
        patches.flush(uow)
        return len(uow) - before


def plan_policy(m: LearnerPlan) -> dict:
    return plain(m.resolve("mastery_policy")) or logic.DEFAULT_POLICY


def _family(tx: _Tx, root_id: str) -> list[_Plan]:
    """The root plan and its descendants (branches), loaded from the attempt's ``plan_ids``."""
    by_parent: dict[str, list[str]] = {}
    for m in typed.batch_get(LearnerPlan, [(pk_of(tx.sid), plan_sk(p)) for p in tx.solve.plan_ids]):
        tx.adopt(m)
        if m.parent_recovery_plan_id:
            by_parent.setdefault(str(m.parent_recovery_plan_id), []).append(str(m.recovery_plan_id))
    out, queue = [], [root_id]
    while queue:
        cur = queue.pop(0)
        out.append(tx.plan(cur))
        queue += by_parent.get(cur, [])
    return out


def _target_for(tx: _Tx, step_id: str, gap_diagnosis_id: str | None) -> dict:
    """Recovery target: the top skill-level hypothesis of the given (or latest) diagnosis for the step; the step's own skill when there is none."""
    sid, aid = tx.sid, tx.aid
    if gap_diagnosis_id:
        diag = next((d for d in diags_of_attempt(sid, aid) if str(d.gap_diagnosis_id) == str(gap_diagnosis_id) and d.solution_step_id == step_id),
                    None)
        if diag is None:
            raise NotFound("diagnosis not found for this step")
    else:
        diag = latest_diag(sid, aid, step_id)
    hyps = sorted((g for g in load_gaps(sid) if diag is not None and str(g.gap_diagnosis_id) == str(diag.gap_diagnosis_id)),
                  key=lambda g: g.rank)
    if hyps:
        h = next((g for g in hyps if g.target_skill_id), hyps[0])
        return {"gap_diagnosis_id": str(diag.gap_diagnosis_id), "knowledge_gap_id": str(h.knowledge_gap_id), "skill_id": h.target_skill_id,
                "subconcept_id": h.target_subconcept_id, "label": h.target_label}
    s = content_reads.content().get_step_recovery_target(step_id)
    return {"gap_diagnosis_id": str(diag.gap_diagnosis_id) if diag else None, "knowledge_gap_id": None, "skill_id": s["skill_node_id"],
            "subconcept_id": s["subconcept_node_id"], "label": s["label"]}
