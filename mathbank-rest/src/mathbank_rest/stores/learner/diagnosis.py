"""Learner store, diagnosis area (requirement 71 WP5; requirement 70 C1 access patterns A14, A19-A22, write paths T12/T13).

``DiagnosisPostgres`` delegates to ``step_diagnosis`` (the SQL layer) at call time, so behaviour is unchanged and monkeypatching tests keep
working. ``DiagnosisDynamoDB`` is the ``mb-learner`` implementation: DIAG (append-only), the fingerprint sentinel, GAP (a versioned status machine)
and the GAP_* events, written with ``LearnerUnitOfWork``; the pure scoring and views are ``step_diagnosis_logic`` (shared with PostgreSQL). Nothing
here imports ``db.postgres``.

Operations (a method is a read exactly when its name starts with a ``stores.READ_PREFIXES`` entry):

* writes  ``diagnose_step`` (T13, idempotent through the fingerprint sentinel), ``update_gap_statuses`` (T12 gap part), ``rerank_diagnosis``
          (sets ``ai_rerank`` once, conditionally)
* reads   ``list_diagnoses`` (A19), ``get_latest_diagnosis_for_step`` (A19), ``get_step_diagnosis_view``, ``list_student_gaps`` (A21),
          ``get_admin_gap_overview`` (A22)

Seam implemented (``stores/learner/hooks.py``): at import this module registers ``auto_diagnose(uow, ctx)``. The solve area calls it LAST in the
step-outcome transaction. It stages, atomically (all or nothing), (1) the status moves of the learner's open gaps about the evaluated skill
(Update GAP with ``version = :seen`` + GAP_HYPOTHESIS_* event each) when they fit the remaining budget, and (2) when the step failed often enough, a
diagnosis (fingerprint sentinel + DIAG + GAPs + events) when that fits what is left; otherwise it is skipped exactly like the PostgreSQL savepoint
failure. It never touches the SOLVE item or a STEPSTATE. It fills ``ctx["out"]``: ``gap_status_changes`` (``[{knowledge_gap_id, from, to}]``) and
``diagnosis`` (the learner view; for a repeated fingerprint the existing diagnosis, as PostgreSQL returns it).

Differences from PostgreSQL that callers can observe (all listed in the WP5 report): a manual diagnosis needs an IN_PROGRESS attempt (T13), the
skill history is eventually consistent (GSI2), a diagnosis has no CONCEPT-level hypotheses (concept prerequisites are not in mb-content), probes and
recovery candidates come from the ``FACET#`` partitions (see ``content_reads``), and the GAP_HYPOTHESIS_* event payloads also carry ``target_label``
and ``likelihood_label`` (the learner feed allow-list).
"""
from __future__ import annotations

import datetime as dt
import logging
import threading
import uuid
from collections.abc import Callable
from typing import Any, ClassVar

from pydantic import BaseModel

from mathbank_rest import step_diagnosis_logic as logic
from mathbank_rest.models import base
from mathbank_rest.models.base import DdbItem
from mathbank_rest.models.manual.learner_diagnosis import (
    GAP_STATUSES,
    LearnerDiag,
    LearnerGap,
    LearnerUniqueDiagFp,
    diag_fp_sk,
    diag_prefix,
    diag_sk,
    gap_keys,
    gap_sk,
)
from mathbank_rest.models.manual.learner_solve import (
    LearnerEvent,
    LearnerSolve,
    LearnerSolveOwner,
    LearnerStepstate,
    event_sk,
    owner_pk,
    solve_sk,
)
from mathbank_rest.step_logic import InvalidTransition, NotFound, public
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.errors import ConditionFailed
from mathbank_rest.stores.learner import content_reads, hooks
from mathbank_rest.stores.learner.uow import LearnerUnitOfWork, with_retries

CTX = "learner"
LOG = logging.getLogger("mathbank_rest.stores.learner.diagnosis")
MAX_ROWS = 5000
HISTORY_PAGE = 200


# ---------------------------------------------------------------------------------------------- postgres

def _engine():
    from mathbank_rest.db.postgres import engine

    return engine


def _sd():
    from mathbank_rest import step_diagnosis

    return step_diagnosis


class DiagnosisPostgres:
    """Postgres backend: calls ``step_diagnosis`` at call time (monkeypatched tests keep working, behaviour unchanged)."""

    def diagnose_step(self, student_id, attempt_id, step_id: str, trigger: str = "STUDENT_REQUEST") -> dict:
        with _engine().begin() as conn:
            return _sd().diagnose_step(conn, student_id, attempt_id, step_id, trigger)

    def update_gap_statuses(self, student_id, attempt_id, step_id: str, result: str, independent: bool, actor: str) -> list[dict]:
        from mathbank_rest import step_runtime

        with _engine().begin() as conn:
            attempt = step_runtime._lock_attempt(conn, attempt_id, student_id)
            return _sd().update_gap_statuses(conn, attempt, step_id, result, independent, actor)

    def rerank_diagnosis(self, student_id, attempt_id, diagnosis_id, reranker: Callable[[dict], dict] | None = None,
                         force: bool = False) -> dict | None:
        """Sets the cached re-rank (best effort); returns the diagnosis with it, or None when nothing was stored."""
        sd = _sd()
        if sd.rerank_diagnosis(_engine(), str(diagnosis_id), reranker, force) is None:
            return None
        with _engine().connect() as conn:
            return sd._diagnosis_row(conn, str(diagnosis_id))

    def list_diagnoses(self, student_id, attempt_id) -> list[dict]:
        with _engine().begin() as conn:
            return _sd().list_diagnoses(conn, student_id, attempt_id)

    def get_latest_diagnosis_for_step(self, student_id, attempt_id, step_id: str) -> dict | None:
        with _engine().connect() as conn:
            return _sd().latest_for_step(conn, str(attempt_id), step_id)

    def get_step_diagnosis_view(self, student_id, attempt_id, step_id: str) -> dict | None:
        return _sd().student_view(self.get_latest_diagnosis_for_step(student_id, attempt_id, step_id))

    def list_student_gaps(self, student_id, status: str | None = None, limit: int = 100) -> list[dict]:
        with _engine().begin() as conn:
            return _sd().list_student_gaps(conn, student_id, status, limit)

    def get_admin_gap_overview(self, *, status: str | None = None, student: str | None = None, limit: int = 100) -> dict:
        with _engine().begin() as conn:
            return _sd().admin_gap_overview(conn, status=status, student=student, limit=limit)


# ---------------------------------------------------------------------------------------------- helpers

_clock_lock = threading.Lock()
_last = dt.datetime.min.replace(tzinfo=dt.UTC)


def stamp() -> dt.datetime:
    """Strictly increasing microsecond instants within this process, so the events of one operation keep their causal order."""
    global _last
    with _clock_lock:
        now = dt.datetime.now(dt.UTC)
        if now <= _last:
            now = _last + dt.timedelta(microseconds=1)
        _last = now
        return now


def iso(t: dt.datetime) -> str:
    return ddb.encode(t)


def pk_of(student_id: Any) -> str:
    return ddb.student_pk(student_id)


class _SkillRow(DdbItem):
    """A GSI2 skill-history entry: the production GSI2 projects only keys, ``type``, ``state``, ``help_level_used``, ``attempt_count``,
    ``independent_success``, ``solve_attempt_id`` and ``solution_step_id`` of a STEPSTATE, so a full ``LearnerStepstate`` cannot be parsed from it."""

    CTX: ClassVar[str] = CTX
    TYPE: ClassVar[str] = "STEPSTATE"
    state: str
    solve_attempt_id: uuid.UUID
    solution_step_id: str


def plain(value: Any) -> Any:
    """JSON-safe plain data (models, UUIDs, datetimes) of an item attribute, as the SQL layer returned it (jsonb -> dict/list)."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_unset=True)
    if isinstance(value, list):
        return [plain(v) for v in value]
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    return value


def load_solve(sid: str, aid: str) -> LearnerSolve:
    solve = typed.get(LearnerSolve, pk_of(sid), solve_sk(aid))
    if solve is None:
        raise NotFound("attempt not found")
    return solve


def owner_of(aid: str) -> str:
    owner = typed.get(LearnerSolveOwner, owner_pk(aid), "OWNER")
    if owner is None:
        raise NotFound("attempt not found")
    return str(owner.student_id)


def load_steps(sid: str, aid: str) -> dict[str, LearnerStepstate]:
    out: dict[str, LearnerStepstate] = {}
    token = None
    while True:
        page = typed.query(LearnerStepstate, pk_of(sid), sk_begins=f"{solve_sk(aid)}#STEP#", limit=200, next_token=token)
        out |= {s.solution_step_id: s for s in page.items}
        token = page.next_token
        if not token:
            return out


def load_gaps(sid: str) -> list[LearnerGap]:
    out: list[LearnerGap] = []
    token = None
    while len(out) < MAX_ROWS:
        page = typed.query(LearnerGap, pk_of(sid), sk_begins="GAP#", limit=200, next_token=token)
        out += page.items
        token = page.next_token
        if not token:
            break
    return out


def event_item(sid: str, aid: str, event_type: str, actor: str, *, step_id: str | None = None, payload: dict | None = None,
               key: str | None = None) -> LearnerEvent:
    event_id = ddb.uuid7()
    when = iso(stamp())
    sk = event_sk(when, event_id)
    return LearnerEvent(PK=pk_of(sid), SK=sk, student_id=sid, event_id=event_id, event_time=when, event_type=event_type, actor_type=actor,
                        payload=public(payload or {}), solve_attempt_id=aid, solution_step_id=step_id, idempotency_key=key,
                        GSI1PK=f"SOLVE#{aid}", GSI1SK=sk)


# ---------------------------------------------------------------------------------------------- views of stored items

def gap_dict(g: LearnerGap, *, admin: bool = False) -> dict:
    """A hypothesis as the SQL rows had it (``_diagnosis_row`` hypotheses; with ``admin`` the ``list_student_gaps`` row)."""
    row = {"knowledge_gap_id": str(g.knowledge_gap_id), "rank": g.rank, "failure_location": g.failure_location,
           "failure_mode": g.failure_mode, "target_concept_id": g.target_concept_id, "target_subconcept_id": g.target_subconcept_id,
           "target_skill_id": g.target_skill_id, "target_label": g.target_label, "source_step_id": g.source_step_id,
           "confidence": float(g.confidence), "evidence": plain(g.resolve("evidence")) or {}, "status": g.status,
           "status_reason": g.status_reason, "created_at": g.created_at, "status_changed_at": g.status_changed_at,
           "resolved_at": g.resolved_at}
    if admin:
        row = {"knowledge_gap_id": row.pop("knowledge_gap_id"), "gap_diagnosis_id": str(g.gap_diagnosis_id),
               "solve_attempt_id": str(g.solve_attempt_id), "solution_step_id": g.solution_step_id, **row}
    else:
        row["target_skill_node_id"] = str(g.target_skill_node_id) if g.target_skill_node_id else None
    return row


def diag_dict(d: LearnerDiag, gaps: list[LearnerGap]) -> dict:
    """A diagnosis as ``step_diagnosis._diagnosis_row`` returned it, with its hypotheses by rank."""
    mine = sorted((g for g in gaps if str(g.gap_diagnosis_id) == str(d.gap_diagnosis_id)), key=lambda g: g.rank)
    return {"gap_diagnosis_id": str(d.gap_diagnosis_id), "student_id": str(d.student_id), "solve_attempt_id": str(d.solve_attempt_id),
            "solution_step_id": d.solution_step_id, "trigger": d.trigger, "recommended_action": d.recommended_action,
            "evidence": plain(d.resolve("evidence")) or {}, "probes": plain(d.resolve("probes")) or [],
            "diagnoser_version": d.diagnoser_version, "ai_rerank": plain(d.resolve("ai_rerank")), "created_at": d.created_at,
            "hypotheses": [gap_dict(g) for g in mine]}


def diags_of_attempt(sid: str, aid: str, *, newest_first: bool = True) -> list[LearnerDiag]:
    out: list[LearnerDiag] = []
    token = None
    while True:
        page = typed.query(LearnerDiag, pk_of(sid), sk_begins=diag_prefix(aid), forward=not newest_first, limit=200, next_token=token)
        out += page.items
        token = page.next_token
        if not token or len(out) >= MAX_ROWS:
            return out


def latest_diag(sid: str, aid: str, step_id: str) -> LearnerDiag | None:
    token = None
    while True:
        page = typed.query(LearnerDiag, pk_of(sid), sk_begins=diag_prefix(aid), forward=False, limit=50, next_token=token)
        for d in page.items:
            if d.solution_step_id == step_id:
                return d
        token = page.next_token
        if not token:
            return None


# ---------------------------------------------------------------------------------------------- skill history (A14)

def skill_rows(sid: str, skill_id: str) -> list[_SkillRow]:
    out: list[_SkillRow] = []
    token = None
    while len(out) < MAX_ROWS:
        page = typed.query(_SkillRow, f"STUDENT#{sid}#SKILL#{skill_id}", index="GSI2", limit=HISTORY_PAGE, next_token=token)
        out += page.items
        token = page.next_token
        if not token:
            break
    return out


def skill_history(sid: str, skill_id: str, aid: str, step_id: str) -> dict:
    """``{independent, with_help, failed}`` over every step of the learner exercising ``skill_id`` (GSI2 skill history), the given step excluded."""
    counts = {"independent": 0, "with_help": 0, "failed": 0}
    for row in skill_rows(sid, skill_id):
        if str(row.solve_attempt_id) == str(aid) and row.solution_step_id == step_id:
            continue
        if row.state == "SUCCESS_INDEPENDENT":
            counts["independent"] += 1
        elif row.state == "SUCCESS_WITH_HELP":
            counts["with_help"] += 1
        elif row.state in ("FAILED", "RETRY_PRESENTED"):
            counts["failed"] += 1
    return counts


def seen_steps(sid: str, skill_id: str) -> set[str]:
    return {r.solution_step_id for r in skill_rows(sid, skill_id)}


# ---------------------------------------------------------------------------------------------- diagnosis context

def build_context(sid: str, solve: LearnerSolve, step_id: str, states: dict[str, LearnerStepstate], dag: dict, *,
                  current: LearnerStepstate | None = None, force_state: str | None = None) -> dict:
    """The diagnoser's input (see ``step_diagnosis.load_context``) from the published DAG, the learner's step states and A14.
    ``current`` is the step's state after an outcome that is not committed yet (``force_state`` its state at diagnosis time)."""
    aid = str(solve.solve_attempt_id)
    by_id = {s["solution_step_id"]: s for s in dag["steps"]}
    row = by_id.get(step_id)
    if row is None:
        raise NotFound("step is not part of this attempt")
    st = current or states.get(step_id)
    if st is None:
        raise InvalidTransition("step has not been presented yet")
    techniques = sorted((t for t in dag["step_techniques"] if t["solution_step_id"] == step_id),
                        key=lambda t: (-(t.get("confidence") or 0), t["technique_node_id"]))
    preds = sorted((by_id[d["from_step_id"]] for d in dag["dependencies"]
                    if d["to_step_id"] == step_id and d["relationship_type"] == "DEPENDS_ON" and d["from_step_id"] in by_id),
                   key=lambda s: -s["global_step_index"])
    nodes = content_reads.taxonomy([row["skill_node_id"], row["subconcept_node_id"], row["concept_node_id"],
                                    *[t["technique_node_id"] for t in techniques],
                                    *[p["skill_node_id"] for p in preds]])

    def labelled(r: dict) -> dict:
        skill = nodes.get(r["skill_node_id"]) if r["skill_node_id"] else None
        return {"skill_id": r["skill_node_id"], "skill_label": r["skill_name"] or (skill.name if skill else None),
                "skill_uuid": str(skill.skill_id) if skill is not None and skill.skill_id else None,
                "subconcept_id": r["subconcept_node_id"], "concept_id": r["concept_node_id"]}

    step = {"solution_step_id": step_id, "problem_id": str(solve.problem_id), "step_type": row["step_type"], **labelled(row)}
    sub, concept = nodes.get(row["subconcept_node_id"]), nodes.get(row["concept_node_id"])
    step |= {"subconcept_label": sub.name if sub else None, "concept_label": concept.name if concept else None,
             "concept_uuid": str(concept.concept_id) if concept is not None and concept.concept_id else None}
    ev = plain(st.resolve("last_evaluation")) or {}
    cur = {"state": force_state or st.state, "attempt_count": st.attempt_count, "help_level": st.help_level_used,
           "failure_mode": ev.get("failure_mode"), "failure_location": ev.get("failure_location"), "verdict": ev.get("verdict")}
    preds_out = []
    for p in preds:
        ps = states.get(p["solution_step_id"])
        preds_out.append({"step_id": p["solution_step_id"], **labelled(p), "state": ps.state if ps else None,
                          "help_level": ps.help_level_used if ps else 0, "independent": bool(ps.independent_success) if ps else False,
                          "history": skill_history(sid, p["skill_node_id"], aid, p["solution_step_id"]) if p["skill_node_id"] else {}})
    sub_fail = 0
    if row["subconcept_node_id"]:
        sub_fail = len({by_id[k]["skill_node_id"] for k, s in states.items()
                        if k != step_id and k in by_id and s.state in ("FAILED", "RETRY_PRESENTED")
                        and by_id[k]["subconcept_node_id"] == row["subconcept_node_id"]
                        and by_id[k]["skill_node_id"] != row["skill_node_id"]})
    return {"step": step, "current": cur, "predecessors": preds_out, "subconcept_failures": sub_fail, "concept_prereqs": [],
            "step_techniques": [{"technique_node_id": t["technique_node_id"], "confidence": float(t.get("confidence") or 0),
                                 "name": nodes[t["technique_node_id"]].name if t["technique_node_id"] in nodes else None}
                                for t in techniques],
            "skill_history": skill_history(sid, row["skill_node_id"], aid, step_id) if row["skill_node_id"] else {}}


# ---------------------------------------------------------------------------------------------- staging (shared by the hook, diagnose_step, recovery)

class GapPatches:
    """Merges every change to one GAP into a single guarded update (DynamoDB allows one operation per item per transaction)."""

    def __init__(self, sid: str) -> None:
        self.sid = sid
        self.gaps: dict[str, tuple[LearnerGap, dict]] = {}

    def load(self, gap_id: Any) -> LearnerGap | None:
        key = str(gap_id)
        if key in self.gaps:
            return self.gaps[key][0]
        gap = typed.get(LearnerGap, pk_of(self.sid), gap_sk(key))
        if gap is not None:
            self.gaps[key] = (gap, {})
        return gap

    def add(self, gap: LearnerGap) -> LearnerGap:
        self.gaps.setdefault(str(gap.knowledge_gap_id), (gap, {}))
        return gap

    def set_status(self, gap: LearnerGap, new: str, reason: str, now: dt.datetime) -> None:
        changes = self.gaps[str(gap.knowledge_gap_id)][1]
        changes |= {"status": new, "status_reason": reason, "status_changed_at": now, "GSI1PK": f"GAPSTATUS#{new}"}
        if new in ("REJECTED", "RESOLVED"):
            changes["resolved_at"] = now

    def set_plan(self, gap: LearnerGap, plan_id: Any, plan_status: str) -> None:
        self.gaps[str(gap.knowledge_gap_id)][1].update({"latest_plan_id": str(plan_id), "latest_plan_status": plan_status})

    def flush(self, uow: LearnerUnitOfWork) -> int:
        n = 0
        for gap, changes in self.gaps.values():
            if changes:
                uow.update(LearnerGap, gap.PK, gap.SK, changes, expected={"version": gap.version},
                           conflict=ConditionFailed("the knowledge gap changed; retry"))
                n += 1
        return n


def stage_gap_changes(uow: LearnerUnitOfWork, sid: str, aid: str, step_id: str, result: str, independent: bool, actor: str, *,
                      skill_id: str | None, subconcept_id: str | None, gaps: list[LearnerGap] | None = None) -> list[dict]:
    """Status moves of the learner's open hypotheses about the evaluated step's skill (or, for subconcept hypotheses, its subconcept)."""
    patches = GapPatches(sid)
    changed: list[dict] = []
    now = stamp()
    for gap in gaps if gaps is not None else load_gaps(sid):
        if gap.status not in logic.OPEN_STATUSES:
            continue
        if not logic.gap_matches_step({"target_skill_id": gap.target_skill_id, "failure_location": gap.failure_location,
                                       "target_subconcept_id": gap.target_subconcept_id}, skill_id, subconcept_id):
            continue
        new = logic.gap_transition(gap.status, result, independent)
        if new is None:
            continue
        reason = f"{result}{'_INDEPENDENT' if independent else ''} on {step_id}"
        patches.add(gap)
        patches.set_status(gap, new, reason, now)
        changed.append({"knowledge_gap_id": str(gap.knowledge_gap_id), "from": gap.status, "to": new})
        uow.put_new(event_item(sid, aid, f"GAP_HYPOTHESIS_{new}", actor, step_id=step_id, payload={
            "knowledge_gap_id": str(gap.knowledge_gap_id), "from": gap.status, "to": new, "reason": reason, "rank": gap.rank,
            "target_label": gap.target_label, "likelihood_label": logic.likelihood_label(float(gap.confidence))}))
    patches.flush(uow)
    return changed


def new_diagnosis_items(sid: str, aid: str, step_id: str, trigger: str, actor: str, ctx: dict) -> tuple[list, dict]:
    """The items of a new diagnosis (DIAG, sentinel, GAPs, events) and the diagnosis document, without writing anything."""
    fp = logic.evidence_fingerprint(ctx)
    hyps = logic.score_hypotheses(ctx)
    action = logic.recommend_action(hyps, ctx)
    probes: list[dict] = []
    if action != "RETRY_WITH_HINT" and hyps and hyps[0]["target_skill_id"]:
        skill = hyps[0]["target_skill_id"]
        probes = content_reads.learning_item_probes(sid, ctx["step"]["problem_id"], skill, seen_steps(sid, skill))
    diag_id, created = str(uuid.uuid4()), stamp()
    stamp_text = iso(created)
    sk = diag_sk(aid, stamp_text, diag_id)
    diag = LearnerDiag(PK=pk_of(sid), SK=sk, student_id=sid, solve_attempt_id=aid, gap_diagnosis_id=diag_id, solution_step_id=step_id,
                       trigger=trigger, recommended_action=action, evidence_fingerprint=fp, evidence=logic.evidence_of(ctx), probes=probes,
                       diagnoser_version=logic.DIAGNOSER_VERSION, created_at=created)
    sentinel = LearnerUniqueDiagFp(PK=pk_of(sid), SK=diag_fp_sk(aid, step_id, fp), student_id=sid, gap_diagnosis_id=diag_id, diag_sk=sk)
    gaps = []
    for h in hyps:
        gap_id = str(uuid.uuid4())
        gaps.append(LearnerGap(
            PK=pk_of(sid), SK=gap_sk(gap_id), student_id=sid, knowledge_gap_id=gap_id, gap_diagnosis_id=diag_id, solve_attempt_id=aid,
            solution_step_id=step_id, rank=h["rank"], failure_location=h["failure_location"], failure_mode=h["failure_mode"],
            target_concept_id=h["target_concept_id"], target_subconcept_id=h["target_subconcept_id"], target_skill_id=h["target_skill_id"],
            target_skill_node_id=h["target_skill_node_id"], target_label=h["target_label"], source_step_id=h["source_step_id"],
            confidence=h["confidence"], evidence=h["evidence"], status="UNRESOLVED", created_at=created, version=1,
            **gap_keys("UNRESOLVED", stamp_text, gap_id)))
    events = [event_item(sid, aid, "GAP_HYPOTHESIS_CREATED", actor, step_id=step_id, payload={
        "knowledge_gap_id": str(g.knowledge_gap_id), "gap_diagnosis_id": diag_id, "rank": g.rank, "failure_location": g.failure_location,
        "target_skill_id": g.target_skill_id, "confidence": g.confidence, "target_label": g.target_label,
        "likelihood_label": logic.likelihood_label(float(g.confidence))}) for g in gaps]
    events.append(event_item(sid, aid, "GAP_DIAGNOSED", actor, step_id=step_id, payload={
        "gap_diagnosis_id": diag_id, "trigger": trigger, "recommended_action": action, "hypotheses": len(hyps)}))
    return [diag, sentinel, *gaps, *events], diag_dict(diag, gaps)


def stage_new_diagnosis(uow: LearnerUnitOfWork, items: list) -> None:
    diag, sentinel, *rest = items
    uow.put_new(diag)
    uow.put_new(sentinel, conflict=ConditionFailed("a diagnosis with this evidence exists; retry"))
    for item in rest:
        uow.put_new(item)


def existing_diagnosis(sid: str, aid: str, step_id: str, fp: str) -> dict | None:
    """The diagnosis a fingerprint sentinel points at (identical evidence returns it instead of a new one)."""
    sentinel = typed.get(LearnerUniqueDiagFp, pk_of(sid), diag_fp_sk(aid, step_id, fp))
    if sentinel is None:
        return None
    diag = typed.get(LearnerDiag, pk_of(sid), sentinel.diag_sk)
    if diag is None:
        return None
    return diag_dict(diag, [g for g in load_gaps(sid) if str(g.gap_diagnosis_id) == str(diag.gap_diagnosis_id)])


# ---------------------------------------------------------------------------------------------- the hook (T12 + T13)

def auto_diagnose(uow: LearnerUnitOfWork, ctx: dict[str, Any]) -> bool:
    """See the module docstring. Returns True when it added items to ``uow``."""
    sid, aid, step_id = str(ctx["student_id"]), str(ctx["attempt_id"]), ctx["solution_step_id"]
    solve, step, result, actor = ctx["solve"], ctx["step_state"], ctx["outcome"], ctx.get("actor") or "SYSTEM"
    out = ctx["out"]
    budget = int(ctx.get("budget", uow.remaining()))
    scratch = LearnerUnitOfWork(sid)
    out["gap_status_changes"] = []
    changes = stage_gap_changes(scratch, sid, aid, step_id, result, bool(step.independent_success), actor,
                                skill_id=step.skill_node_id, subconcept_id=step.subconcept_node_id)
    if len(scratch) > budget:
        LOG.warning("gap status changes of %s do not fit the transaction (%s > %s); skipped", step_id, len(scratch), budget)
        scratch, changes = LearnerUnitOfWork(sid), []
    out["gap_status_changes"] = changes
    if logic.should_auto_diagnose(result, step.attempt_count, step.help_level_used):
        dag = content_reads.content().get_solution_dag(problem_id=str(solve.problem_id))
        context = build_context(sid, solve, step_id, load_steps(sid, aid), dag, current=step, force_state="FAILED")
        found = existing_diagnosis(sid, aid, step_id, logic.evidence_fingerprint(context))
        if found is not None:
            out["diagnosis"] = logic.student_view(found)
        else:
            items, view = new_diagnosis_items(sid, aid, step_id, "AUTO", "SYSTEM", context)
            if len(scratch) + len(items) <= budget:
                stage_new_diagnosis(scratch, items)
                out["diagnosis"] = logic.student_view(view)
            else:
                LOG.warning("diagnosis of %s does not fit the transaction (%s > %s); skipped", step_id, len(scratch) + len(items), budget)
    for op in scratch.ops():
        uow.add(op)
    return len(scratch) > 0


hooks.register_auto_diagnose(auto_diagnose)


# ---------------------------------------------------------------------------------------------- DynamoDB

class DiagnosisDynamoDB:
    """DynamoDB backend over mb-learner."""

    # ------------------------------------------------------------------------------------------ writes

    def diagnose_step(self, student_id, attempt_id, step_id: str, trigger: str = "STUDENT_REQUEST") -> dict:
        """Score and persist a diagnosis for a presented step of the learner's attempt; identical evidence returns the existing one
        (``reused``). Does not change the runtime mode or ``state_version``."""
        if trigger not in logic.TRIGGERS:
            raise ValueError(trigger)
        sid, aid = str(student_id), str(attempt_id)
        actor = "STUDENT" if trigger == "STUDENT_REQUEST" else "TUTOR"

        def attempt() -> dict:
            solve = load_solve(sid, aid)
            dag = content_reads.content().get_solution_dag(problem_id=str(solve.problem_id))
            context = build_context(sid, solve, step_id, load_steps(sid, aid), dag)
            found = existing_diagnosis(sid, aid, step_id, logic.evidence_fingerprint(context))
            if found is not None:
                return {**found, "reused": True}
            if solve.status != "IN_PROGRESS":
                raise InvalidTransition(f"attempt is {solve.status}")
            items, view = new_diagnosis_items(sid, aid, step_id, trigger, actor, context)
            uow = LearnerUnitOfWork(sid)
            uow.add(ddb.Check(CTX, solve.PK, solve.SK, ddb.Cond("#v = :v AND #s = :s", {"#v": "version", "#s": "status"},
                                                                {":v": solve.version, ":s": "IN_PROGRESS"}),
                              ConditionFailed("the attempt changed; retry"), label="solve guard"))
            stage_new_diagnosis(uow, items)
            uow.commit()
            return {**view, "reused": False}

        return with_retries(attempt)

    def update_gap_statuses(self, student_id, attempt_id, step_id: str, result: str, independent: bool, actor: str) -> list[dict]:
        """Move the learner's open hypotheses about the step's skill for an outcome (its own transaction; the step-outcome transaction
        stages the same changes through the auto-diagnose hook)."""
        sid, aid = str(student_id), str(attempt_id)

        def attempt() -> list[dict]:
            solve = load_solve(sid, aid)
            dag = content_reads.content().get_solution_dag(problem_id=str(solve.problem_id))
            row = next((s for s in dag["steps"] if s["solution_step_id"] == step_id), None)
            if row is None:
                return []
            uow = LearnerUnitOfWork(sid)
            changed = stage_gap_changes(uow, sid, aid, step_id, result, independent, actor, skill_id=row["skill_node_id"],
                                        subconcept_id=row["subconcept_node_id"])
            uow.commit()
            return changed

        return with_retries(attempt)

    def rerank_diagnosis(self, student_id, attempt_id, diagnosis_id, reranker: Callable[[dict], dict] | None = None,
                         force: bool = False) -> dict | None:
        """Optional LLM re-rank, best effort, outside any transaction: the model only reorders the persisted hypotheses. The result is set
        once (a conditional update); returns the diagnosis with it, or None when nothing was stored."""
        if not (force or logic.rerank_enabled()):
            return None
        sid, aid = str(student_id), str(attempt_id)
        diag = next((d for d in diags_of_attempt(sid, aid) if str(d.gap_diagnosis_id) == str(diagnosis_id)), None)
        if diag is None:
            return None
        found = diag_dict(diag, load_gaps(sid))
        if found.get("ai_rerank"):
            return found
        if len(found["hypotheses"]) < 2:
            return None
        step = content_reads.content().get_step_details([diag.solution_step_id]).get(diag.solution_step_id)
        try:
            answer = (reranker or logic.openai_reranker)(logic.rerank_context_of(found, step))
        except Exception:  # noqa: BLE001 - the rules order stands
            return None
        order = logic.validate_rerank(answer, found["hypotheses"])
        if order is None:
            return None
        stored = logic.stored_rerank(answer, order, found["hypotheses"])
        race = ConditionFailed("the diagnosis already has a re-rank")
        cond = ddb.Cond("attribute_exists(PK) AND attribute_not_exists(#r) AND attribute_not_exists(#rr)")
        try:
            ddb.transact([ddb.Update(CTX, diag.PK, diag.SK, "SET #r = :r", names={"#r": "ai_rerank", "#rr": "ai_rerank_ref"},
                                     values={":r": stored}, cond=cond, conflict=race, label="ai_rerank")])
        except ConditionFailed as exc:
            if exc is not race:
                raise
        fresh = typed.get(LearnerDiag, diag.PK, diag.SK)
        return diag_dict(fresh, load_gaps(sid)) if fresh is not None else None

    # ------------------------------------------------------------------------------------------ reads

    def list_diagnoses(self, student_id, attempt_id) -> list[dict]:
        """A19: the attempt's diagnoses, newest first, with their hypotheses. ``student_id=None`` is the admin read (owner through the pointer)."""
        aid = str(attempt_id)
        sid = str(student_id) if student_id is not None else owner_of(aid)
        load_solve(sid, aid)
        diags = diags_of_attempt(sid, aid)
        gaps = load_gaps(sid) if diags else []
        return [diag_dict(d, gaps) for d in diags]

    def get_latest_diagnosis_for_step(self, student_id, attempt_id, step_id: str) -> dict | None:
        sid, aid = str(student_id), str(attempt_id)
        diag = latest_diag(sid, aid, step_id)
        return None if diag is None else diag_dict(diag, load_gaps(sid))

    def get_step_diagnosis_view(self, student_id, attempt_id, step_id: str) -> dict | None:
        """The learner view of the latest diagnosis of a step (the runtime read model calls this)."""
        return logic.student_view(self.get_latest_diagnosis_for_step(student_id, attempt_id, step_id))

    def list_student_gaps(self, student_id, status: str | None = None, limit: int = 100) -> list[dict]:
        """A21: a learner's hypotheses across attempts (admin rows with failure mode, confidence and evidence), newest first."""
        rows = [g for g in load_gaps(str(student_id)) if status is None or g.status == status]
        rows.sort(key=lambda g: (-g.created_at.timestamp(), g.rank))
        return [gap_dict(g, admin=True) for g in rows[:min(max(limit, 1), 500)]]

    def get_admin_gap_overview(self, *, status: str | None = None, student: str | None = None, limit: int = 100) -> dict:
        """A22: status totals, the most common open targets and recent hypotheses across learners (GSI1 ``GAPSTATUS#<s>``)."""
        every = [g for s in GAP_STATUSES for g in _by_status(s)]
        profile_model = base.model_for(CTX, "PROFILE")
        profiles = {str(p.student_id): p for p in typed.batch_get(
            profile_model, [(pk_of(sid), "PROFILE") for sid in {str(g.student_id) for g in every}])}
        who = (student or "").strip().lower() or None

        def visible(g: LearnerGap) -> bool:
            if who is None:
                return True
            email = (getattr(profiles.get(str(g.student_id)), "email", None) or "").lower()
            return who in email or str(g.student_id) == who

        scoped = [g for g in every if visible(g)]
        totals: dict[str, int] = {}
        groups: dict[str, dict] = {}
        for g in scoped:
            totals[g.status] = totals.get(g.status, 0) + 1
            if g.status in logic.OPEN_STATUSES:
                key = g.target_skill_id or g.target_subconcept_id
                grp = groups.setdefault(key, {"target_id": key, "labels": [], "open_gaps": 0, "students": set()})
                grp["labels"].append(g.target_label or "")
                grp["open_gaps"] += 1
                grp["students"].add(str(g.student_id))
        top = sorted(({"target_id": v["target_id"], "target_label": max(v["labels"]), "open_gaps": v["open_gaps"], "students": len(v["students"])}
                      for v in groups.values()), key=lambda r: (-r["open_gaps"], -r["students"], str(r["target_id"])))[:10]
        picked = sorted((g for g in scoped if status is None or g.status == status), key=lambda g: (-g.created_at.timestamp(), g.rank))
        return {"totals": totals, "top_open_targets": top,
                "gaps": [_overview_row(g, profiles) for g in picked[:min(max(limit, 1), 500)]]}


def _by_status(status: str) -> list[LearnerGap]:
    out: list[LearnerGap] = []
    token = None
    while len(out) < MAX_ROWS:
        page = typed.query(LearnerGap, f"GAPSTATUS#{status}", index="GSI1", forward=False, limit=200, next_token=token)
        out += page.items
        token = page.next_token
        if not token:
            break
    return out


def _overview_row(g: LearnerGap, profiles: dict) -> dict:
    sid, aid = str(g.student_id), str(g.solve_attempt_id)
    solve = typed.get(LearnerSolve, pk_of(sid), solve_sk(aid))
    problem = content_reads.content().get_problem_by_id(str(solve.problem_id)) if solve is not None else None
    diag = next((d for d in diags_of_attempt(sid, aid) if str(d.gap_diagnosis_id) == str(g.gap_diagnosis_id)), None)
    return {"knowledge_gap_id": str(g.knowledge_gap_id), "gap_diagnosis_id": str(g.gap_diagnosis_id), "student_id": sid,
            "email": getattr(profiles.get(sid), "email", None), "solve_attempt_id": aid,
            "problem_code": problem["canonical_code"] if problem else None, "solution_step_id": g.solution_step_id, "rank": g.rank,
            "failure_location": g.failure_location, "failure_mode": g.failure_mode, "target_skill_id": g.target_skill_id,
            "target_label": g.target_label, "source_step_id": g.source_step_id, "confidence": float(g.confidence), "status": g.status,
            "status_reason": g.status_reason, "created_at": g.created_at, "status_changed_at": g.status_changed_at,
            "trigger": diag.trigger if diag else None, "recommended_action": diag.recommended_action if diag else None,
            "ai_reranked": bool(diag is not None and (diag.ai_rerank is not None or diag.ref("ai_rerank") is not None)),
            "recovery_plan_id": str(g.latest_plan_id) if g.latest_plan_id else None, "recovery_status": g.latest_plan_status}
