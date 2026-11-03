"""WP5 diagnosis / gap / recovery routes: parity between the PostgreSQL contract and the DynamoDB backend.

The same scripted scenario runs through the real router (``TestClient``) twice. The "postgres" side is ``GapOracle``: an in-memory learner store that
implements today's PostgreSQL state machine (``step_diagnosis`` / ``step_recovery``: context, fingerprint, hypotheses, plan building, adaptation,
branches, resume / abort, the admin views) independently of ``DiagnosisDynamoDB`` / ``RecoveryDynamoDB``, on top of ``Oracle`` (the solve contract of
``test_wp5_solve_parity``). Both sides share only the pure logic modules and the content reads (``content_reads``), which both backends use by design.
The "dynamodb" side is the composed ``DynamoDBLearnerStore`` on moto. Generated ids and timestamps are normalised; every other difference fails the
test unless it is listed.
"""
from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "parity"))

from parity_harness import diff
from test_wp5_diagnosis import SK_UUID, seed_learning  # noqa: F401
from test_wp5_solve import CODE, seed_content
from test_wp5_solve_parity import BackendClient, Oracle, Run

from mathbank_rest import security, stores
from mathbank_rest import step_diagnosis_logic as dlogic
from mathbank_rest import step_recovery_logic as rlogic
from mathbank_rest.main import app
from mathbank_rest.routers import step_runtime as routes
from mathbank_rest.step_logic import InvalidTransition, NotFound, check_version
from mathbank_rest.stores.content import DynamoDBContentStore
from mathbank_rest.stores.learner import DynamoDBLearnerStore, content_reads, hooks
from mathbank_rest.stores.learner import diagnosis as diagnosis_module
from mathbank_rest.stores.learner import recovery as recovery_module

OPEN = ("UNRESOLVED", "CONFIRMED")


class GapOracle(Oracle):
    """PostgreSQL semantics in memory for diagnoses, gaps and recovery plans (the contract the routers and clients were built against)."""

    backend = "oracle"

    def __init__(self) -> None:
        super().__init__(with_mastery=False)
        self.diags: list[dict] = []
        self.gaps: dict[str, dict] = {}
        self.fps: dict[tuple, str] = {}
        self.plans: dict[str, dict] = {}

    # ------------------------------------------------------------------------------------------ runtime pointers
    def get_attempt_runtime(self, attempt_id, student_id=None):
        out = super().get_attempt_runtime(attempt_id, student_id)
        a = self.attempts[str(attempt_id)]
        out["attempt"]["recovery_plan_id"] = UUID(a["root_plan"]) if a.get("root_plan") else None
        out["attempt"]["current_recovery_plan_id"] = UUID(a["plan"]) if a.get("plan") else None
        if out["current_step"]:
            out["current_step"]["diagnosis"] = dlogic.student_view(self._latest(a["id"], out["current_step"]["solution_step_id"]))
        out["recovery"] = self.get_recovery_summary(attempt_id)
        return out

    # ------------------------------------------------------------------------------------------ diagnosis
    def _skills(self, a, sid):
        by_id = {s["solution_step_id"]: s for s in self._dag(a)["steps"]}
        return {(aid, step): by_id[step]["skill_node_id"] for (aid, step) in self.steps
                if self.attempts[aid]["student_id"] == sid and step in by_id}

    def _history(self, a, sid, skill, step_id):
        out = {"independent": 0, "with_help": 0, "failed": 0}
        for (aid, step), sk in self._skills(a, sid).items():
            if sk != skill or (aid, step) == (a["id"], step_id):
                continue
            state = self.steps[(aid, step)]["state"]
            key = {"SUCCESS_INDEPENDENT": "independent", "SUCCESS_WITH_HELP": "with_help", "FAILED": "failed", "RETRY_PRESENTED": "failed"}.get(state)
            if key:
                out[key] += 1
        return out

    def _context(self, a, sid, step_id):
        dag = self._dag(a)
        by_id = {s["solution_step_id"]: s for s in dag["steps"]}
        row = by_id.get(step_id)
        if row is None:
            raise NotFound("step is not part of this attempt")
        st = self.steps.get((a["id"], step_id))
        if st is None:
            raise InvalidTransition("step has not been presented yet")
        techs = sorted((t for t in dag["step_techniques"] if t["solution_step_id"] == step_id), key=lambda t: (-t["confidence"], t["technique_node_id"]))
        preds = sorted((by_id[d["from_step_id"]] for d in dag["dependencies"] if d["to_step_id"] == step_id and d["relationship_type"] == "DEPENDS_ON"),
                       key=lambda s: -s["global_step_index"])
        nodes = content_reads.taxonomy([row["skill_node_id"], row["subconcept_node_id"], row["concept_node_id"], *[p["skill_node_id"] for p in preds],
                                        *[t["technique_node_id"] for t in techs]])

        def lab(r):
            n = nodes.get(r["skill_node_id"])
            return {"skill_id": r["skill_node_id"], "skill_label": r["skill_name"] or (n.name if n else None),
                    "skill_uuid": str(n.skill_id) if n is not None and n.skill_id else None, "subconcept_id": r["subconcept_node_id"],
                    "concept_id": r["concept_node_id"]}

        ev = st["evaluation"] or {}
        step = {"solution_step_id": step_id, "problem_id": a["problem_id"], "step_type": row["step_type"], **lab(row),
                "subconcept_label": nodes[row["subconcept_node_id"]].name if row["subconcept_node_id"] in nodes else None,
                "concept_label": nodes[row["concept_node_id"]].name if row["concept_node_id"] in nodes else None}
        failing = {by_id[s]["skill_node_id"] for (aid, s), r in self.steps.items() if aid == a["id"] and s != step_id and s in by_id
                   and r["state"] in ("FAILED", "RETRY_PRESENTED") and by_id[s]["subconcept_node_id"] == row["subconcept_node_id"]
                   and by_id[s]["skill_node_id"] != row["skill_node_id"]}
        return {"step": step, "current": {"state": st["state"], "attempt_count": st["count"], "help_level": st["help"],
                                          "failure_mode": ev.get("failure_mode"), "failure_location": ev.get("failure_location"),
                                          "verdict": ev.get("verdict")},
                "predecessors": [{"step_id": p["solution_step_id"], **lab(p), "state": (self.steps.get((a["id"], p["solution_step_id"])) or {}).get("state"),
                                  "help_level": (self.steps.get((a["id"], p["solution_step_id"])) or {}).get("help", 0),
                                  "independent": bool((self.steps.get((a["id"], p["solution_step_id"])) or {}).get("independent")),
                                  "history": self._history(a, sid, p["skill_node_id"], p["solution_step_id"]) if p["skill_node_id"] else {}}
                                 for p in preds],
                "subconcept_failures": len(failing) if row["subconcept_node_id"] else 0, "concept_prereqs": [],
                "step_techniques": [{"technique_node_id": t["technique_node_id"], "confidence": t["confidence"],
                                     "name": nodes[t["technique_node_id"]].name if t["technique_node_id"] in nodes else None} for t in techs],
                "skill_history": self._history(a, sid, row["skill_node_id"], step_id) if row["skill_node_id"] else {}}

    def _hyps(self, diag_id):
        return [dict(g) for g in sorted((g for g in self.gaps.values() if g["gap_diagnosis_id"] == diag_id), key=lambda g: g["rank"])]

    def _row(self, d):
        keys = ("gap_diagnosis_id", "student_id", "solve_attempt_id", "solution_step_id", "trigger", "recommended_action", "evidence", "probes",
                "diagnoser_version", "ai_rerank", "created_at")
        return {**{k: d[k] for k in keys}, "hypotheses": [{k: v for k, v in g.items() if k not in ("gap_diagnosis_id", "student_id", "solve_attempt_id",
                                                                                                 "solution_step_id", "_skill_unused")}
                                                           for g in self._hyps(d["gap_diagnosis_id"])]}

    def _latest(self, aid, step_id):
        found = [d for d in self.diags if d["solve_attempt_id"] == aid and d["solution_step_id"] == step_id]
        return self._row(found[-1]) if found else None

    def diagnose_step(self, student_id, attempt_id, step_id, trigger="STUDENT_REQUEST"):
        a = self._lock(attempt_id, student_id)
        sid = a["student_id"]
        ctx = self._context(a, sid, step_id)
        fp = dlogic.evidence_fingerprint(ctx)
        if (a["id"], step_id, fp) in self.fps:
            return {**self._row(next(d for d in self.diags if d["gap_diagnosis_id"] == self.fps[(a["id"], step_id, fp)])), "reused": True}
        hyps = dlogic.score_hypotheses(ctx)
        action = dlogic.recommend_action(hyps, ctx)
        probes = []
        if action != "RETRY_WITH_HINT" and hyps:
            skill = hyps[0]["target_skill_id"]
            seen = {s for (aid, s), sk in self._skills(a, sid).items() if sk == skill}
            probes = content_reads.learning_item_probes(sid, a["problem_id"], skill, seen) if skill else []
        did, now = str(uuid.uuid4()), self._now()
        self.diags.append({"gap_diagnosis_id": did, "student_id": sid, "solve_attempt_id": a["id"], "solution_step_id": step_id, "trigger": trigger,
                           "recommended_action": action, "evidence": dlogic.evidence_of(ctx), "probes": probes,
                           "diagnoser_version": dlogic.DIAGNOSER_VERSION, "ai_rerank": None, "created_at": now})
        self.fps[(a["id"], step_id, fp)] = did
        actor = "STUDENT" if trigger == "STUDENT_REQUEST" else "TUTOR"
        for h in hyps:
            gid = str(uuid.uuid4())
            self.gaps[gid] = {"knowledge_gap_id": gid, "gap_diagnosis_id": did, "student_id": sid, "solve_attempt_id": a["id"],
                              "solution_step_id": step_id, "rank": h["rank"], "failure_location": h["failure_location"],
                              "failure_mode": h["failure_mode"], "target_concept_id": h["target_concept_id"],
                              "target_subconcept_id": h["target_subconcept_id"], "target_skill_id": h["target_skill_id"],
                              "target_skill_node_id": h["target_skill_node_id"], "target_label": h["target_label"],
                              "source_step_id": h["source_step_id"], "confidence": h["confidence"], "evidence": h["evidence"],
                              "status": "UNRESOLVED", "status_reason": None, "created_at": now, "status_changed_at": None, "resolved_at": None}
            self._event(sid, a["id"], "GAP_HYPOTHESIS_CREATED", actor, step_id, {"knowledge_gap_id": gid})
        self._event(sid, a["id"], "GAP_DIAGNOSED", actor, step_id, {"gap_diagnosis_id": did})
        return {**self._row(self.diags[-1]), "reused": False}

    def list_diagnoses(self, student_id, attempt_id):
        a = self.attempts.get(str(attempt_id))
        if a is None or (student_id is not None and a["student_id"] != str(student_id)):
            raise NotFound("attempt not found")
        return [self._row(d) for d in reversed(self.diags) if d["solve_attempt_id"] == a["id"]]

    def list_student_gaps(self, student_id, status=None, limit=100):
        keys = ("knowledge_gap_id", "gap_diagnosis_id", "solve_attempt_id", "solution_step_id", "rank", "failure_location", "failure_mode",
                "target_concept_id", "target_subconcept_id", "target_skill_id", "target_label", "source_step_id", "confidence", "evidence", "status",
                "status_reason", "created_at", "status_changed_at", "resolved_at")
        rows = [g for g in self.gaps.values() if g["student_id"] == str(student_id) and status in (None, g["status"])]
        rows.sort(key=lambda g: (-g["created_at"].timestamp(), g["rank"]))
        return [{k: g[k] for k in keys} for g in rows[:min(max(limit, 1), 500)]]

    def get_admin_gap_overview(self, *, status=None, student=None, limit=100):
        who = (student or "").strip().lower() or None
        scoped = [g for g in self.gaps.values() if who is None or who == g["student_id"]]
        totals: dict[str, int] = {}
        groups: dict[str, list] = {}
        for g in scoped:
            totals[g["status"]] = totals.get(g["status"], 0) + 1
            if g["status"] in OPEN:
                groups.setdefault(g["target_skill_id"] or g["target_subconcept_id"], []).append(g)
        top = sorted(({"target_id": k, "target_label": max(g["target_label"] or "" for g in v), "open_gaps": len(v),
                       "students": len({g["student_id"] for g in v})} for k, v in groups.items()),
                     key=lambda r: (-r["open_gaps"], -r["students"], str(r["target_id"])))[:10]
        rows = []
        for g in sorted((g for g in scoped if status in (None, g["status"])), key=lambda g: (-g["created_at"].timestamp(), g["rank"]))[:limit]:
            a, d = self.attempts[g["solve_attempt_id"]], next(d for d in self.diags if d["gap_diagnosis_id"] == g["gap_diagnosis_id"])
            plan = next((p for p in sorted(self.plans.values(), key=lambda p: p["d"]["created_at"], reverse=True)
                         if p["d"]["knowledge_gap_id"] == g["knowledge_gap_id"]), None)
            rows.append({"knowledge_gap_id": g["knowledge_gap_id"], "gap_diagnosis_id": g["gap_diagnosis_id"], "student_id": g["student_id"],
                         "email": None, "solve_attempt_id": g["solve_attempt_id"], "problem_code": self._dag(a)["problem_code"],
                         "solution_step_id": g["solution_step_id"], "rank": g["rank"], "failure_location": g["failure_location"],
                         "failure_mode": g["failure_mode"], "target_skill_id": g["target_skill_id"], "target_label": g["target_label"],
                         "source_step_id": g["source_step_id"], "confidence": g["confidence"], "status": g["status"],
                         "status_reason": g["status_reason"], "created_at": g["created_at"], "status_changed_at": g["status_changed_at"],
                         "trigger": d["trigger"], "recommended_action": d["recommended_action"], "ai_reranked": False,
                         "recovery_plan_id": plan["d"]["recovery_plan_id"] if plan else None, "recovery_status": plan["d"]["status"] if plan else None})
        return {"totals": totals, "top_open_targets": top, "gaps": rows}

    # ------------------------------------------------------------------------------------------ recovery plans
    def _target(self, a, step_id, gap_diagnosis_id):
        if gap_diagnosis_id:
            d = next((d for d in self.diags if d["gap_diagnosis_id"] == str(gap_diagnosis_id) and d["solve_attempt_id"] == a["id"]
                      and d["solution_step_id"] == step_id), None)
            if d is None:
                raise NotFound("diagnosis not found for this step")
        else:
            found = [d for d in self.diags if d["solve_attempt_id"] == a["id"] and d["solution_step_id"] == step_id]
            d = found[-1] if found else None
        hyps = self._hyps(d["gap_diagnosis_id"]) if d else []
        if hyps:
            h = next((h for h in hyps if h["target_skill_id"]), hyps[0])
            return {"gap_diagnosis_id": d["gap_diagnosis_id"], "knowledge_gap_id": h["knowledge_gap_id"], "skill_id": h["target_skill_id"],
                    "subconcept_id": h["target_subconcept_id"], "label": h["target_label"]}
        s = stores.get_store("content").get_step_recovery_target(step_id)
        return {"gap_diagnosis_id": d["gap_diagnosis_id"] if d else None, "knowledge_gap_id": None, "skill_id": s["skill_node_id"],
                "subconcept_id": s["subconcept_node_id"], "label": s["label"]}

    def _used(self, sid):
        return {i["learning_item_id"] for p in self.plans.values() if p["d"]["student_id"] == sid for i in p["items"]
                if i["learning_item_id"] and i["status"] != "SKIPPED"}

    def _cands(self, a, sid, step_id, skill, sub):
        row = next(s for s in self._dag(a)["steps"] if s["solution_step_id"] == step_id)
        return content_reads.learning_item_candidates(sid, a["problem_id"], skill, sub, exclude_ids=self._used(sid),
                                                      origin_subconcept=row["subconcept_node_id"], origin_concept=row["concept_node_id"])

    def _item(self, spec, ordinal, reason, meta):
        li = spec["learning_item_id"]
        return {"recovery_plan_item_id": str(uuid.uuid4()), "ordinal": ordinal, "stage": spec["stage"], "item_kind": spec["item_kind"],
                "learning_item_id": li, "worked_step_id": spec["worked_step_id"], "is_transfer": spec["is_transfer"], "required": spec["required"],
                "status": "PENDING", "tries": 0, "independent_success": None, "last_response": None, "last_result": None, "added_reason": reason,
                "presented_at": None, "completed_at": None, "transformation_type": meta.get(li, {}).get("transformation_type") if li else None,
                "transformed_form": meta.get(li, {}).get("transformed_form") if li else None,
                "source_problem_id": spec.get("source_problem_id") or (meta.get(li, {}).get("source_problem_id") if li else None)}

    def _present_item(self, p, ordinal, actor="SYSTEM"):
        item = next(i for i in p["items"] if i["ordinal"] == ordinal)
        item["status"], item["presented_at"] = "PRESENTED", item["presented_at"] or "x"
        p["d"]["current_item_ordinal"] = ordinal
        self._event(p["d"]["student_id"], p["d"]["solve_attempt_id"], "RECOVERY_ITEM_PRESENTED", actor, p["d"]["origin_step_id"], {"ordinal": ordinal})

    def _make_plan(self, a, step_id, target, trigger, parent, include_return):
        sid = a["student_id"]
        meta = {}
        cands = self._cands(a, sid, step_id, target["skill_id"], target["subconcept_id"])
        for c in cands:
            meta[c["learning_item_id"]] = c
        row = next(s for s in self._dag(a)["steps"] if s["solution_step_id"] == step_id)
        attempted = {x["problem_id"] for x in self.attempts.values() if x["student_id"] == sid}
        worked = content_reads.worked_example_step(sid, a["problem_id"], target["skill_id"], attempted, origin_subconcept=row["subconcept_node_id"],
                                                   origin_concept=row["concept_node_id"])
        specs = rlogic.build_plan(cands, worked, include_return=include_return)
        if not any(s["item_kind"] == "LEARNING_ITEM" for s in specs) and not worked:
            raise rlogic.NoRecoveryMaterial(f"no approved practice is available for “{target['label'] or 'this skill'}” yet")
        pid = str(uuid.uuid4())
        now = self._now()
        d = {"recovery_plan_id": pid, "student_id": sid, "solve_attempt_id": a["id"], "origin_problem_id": a["problem_id"], "origin_step_id": step_id,
             "gap_diagnosis_id": target.get("gap_diagnosis_id"), "knowledge_gap_id": target.get("knowledge_gap_id"),
             "parent_recovery_plan_id": parent, "trigger": trigger, "target_skill_id": target["skill_id"], "target_subconcept_id": target["subconcept_id"],
             "target_label": target["label"], "status": "ACTIVE", "current_item_ordinal": None, "mastery_policy": dict(rlogic.DEFAULT_POLICY),
             "outcome": {}, "planner_version": rlogic.PLANNER_VERSION, "created_at": now, "updated_at": now, "ended_at": None}
        p = self.plans[pid] = {"d": d, "items": [self._item(s, s["ordinal"], "PLANNED", meta) for s in specs], "meta": meta}
        a.setdefault("plans", []).append(pid)
        self._event(sid, a["id"], "RECOVERY_PLAN_CREATED", "SYSTEM", step_id, {"recovery_plan_id": pid})
        self._present_item(p, 1)
        return p

    def _view(self, p):
        d = p["d"]
        origin = stores.get_store("content").get_step_origin(d["origin_step_id"])
        parent = self.plans[d["parent_recovery_plan_id"]]["d"]["target_label"] if d["parent_recovery_plan_id"] else None
        return rlogic.plan_view_of(d, sorted(p["items"], key=lambda i: i["ordinal"]), origin=origin, parent_label=parent,
                                   content_for=recovery_module._content_for)

    def create_plan(self, student_id, attempt_id, state_version, *, trigger="STUDENT_REQUEST", gap_diagnosis_id=None, idempotency_key=None):
        sid, a = str(student_id), self._lock(attempt_id, student_id)
        body = {"attempt_id": str(attempt_id), "state_version": state_version, "trigger": trigger, "gap_diagnosis_id": gap_diagnosis_id}
        if not idempotency_key and a["mode"] == "RECOVERY" and a.get("plan"):
            return {"recovery_plan": self._view(self.plans[a["plan"]]), "resumed": True, "state_version": a["version"]}

        def run():
            check_version(a["version"], state_version)
            if a["status"] != "IN_PROGRESS" or not a["step"]:
                raise InvalidTransition(f"attempt is {a['status']}")
            step_id = a["step"]
            if trigger == "DIAGNOSIS" and gap_diagnosis_id is None:
                raise InvalidTransition("a diagnosis-triggered detour needs gap_diagnosis_id")
            p = self._make_plan(a, step_id, self._target(a, step_id, gap_diagnosis_id), trigger, None, True)
            self.steps[(a["id"], step_id)]["state"] = "DETOURED"
            a["plan"], a["root_plan"] = p["d"]["recovery_plan_id"], p["d"]["recovery_plan_id"]
            a["mode"] = "RECOVERY"
            a["version"] += 1
            self._gap_plan(p, "ACTIVE")
            return {"recovery_plan": self._view(p), "resumed": False, "state_version": a["version"]}

        return self._idem(sid, idempotency_key, "recovery_create", body, run)

    def _gap_plan(self, p, status):
        pass

    def _owned(self, plan_id, student_id):
        p = self.plans.get(str(plan_id))
        if p is None or (student_id is not None and p["d"]["student_id"] != str(student_id)):
            raise NotFound("recovery plan not found")
        return p

    def get_recovery_plan(self, student_id, plan_id):
        return self._view(self._owned(plan_id, student_id))

    def get_next_recovery_item(self, student_id, plan_id):
        view = self.get_recovery_plan(student_id, plan_id)
        cur = next((i for i in view["items"] if i["ordinal"] == view["current_item_ordinal"]), None)
        return {"recovery_plan_id": view["recovery_plan_id"], "status": view["status"], "item": cur, "mastery": view["mastery"],
                "can_return": view["can_return"]}

    def list_attempt_plans(self, student_id, attempt_id):
        a = self.attempts.get(str(attempt_id))
        if a is None or (student_id is not None and a["student_id"] != str(student_id)):
            raise NotFound("attempt not found")
        return [self._view(self.plans[i]) for i in sorted(a.get("plans", []), key=lambda i: self.plans[i]["d"]["created_at"], reverse=True)]

    def load_item_response_context(self, student_id, plan_id, item_id, response, state_version, idempotency_key):
        p = self._owned(plan_id, student_id)
        body = {"plan_id": str(plan_id), "item_id": item_id, "response": response, "state_version": state_version}
        key = (str(student_id), idempotency_key)
        if idempotency_key and key in self.idem:
            op, h, stored = self.idem[key]
            from mathbank_rest.step_logic import IdempotencyKeyReused, request_hash

            if op != "recovery_item_response" or h != request_hash(op, body):
                raise IdempotencyKeyReused("Idempotency-Key was already used for a different request")
            return {"replay": {**stored, "replayed": True}}
        item = next((i for i in p["items"] if i["recovery_plan_item_id"] == item_id), None)
        if item is None:
            raise NotFound("recovery item not found")
        if p["d"]["status"] != "ACTIVE" or item["ordinal"] != p["d"]["current_item_ordinal"] or item["status"] != "PRESENTED":
            raise InvalidTransition("only the current item of an active plan accepts a response")
        if item["item_kind"] == "RETURN":
            raise InvalidTransition("use /resume to return to the original problem")
        ctx = {"item": dict(item), "plan": dict(p["d"])}
        if item["item_kind"] == "LEARNING_ITEM":
            ctx["learning_item"] = content_reads.learning_item_row(item["learning_item_id"], with_key=True)
        return ctx

    def _set_status(self, p, status):
        p["d"]["status"] = status

    def _end(self, p, status, mastery, actor):
        p["d"]["outcome"], p["d"]["ended_at"] = {"mastery": mastery}, self._now()
        self._set_status(p, status)
        self._event(p["d"]["student_id"], p["d"]["solve_attempt_id"], {"COMPLETED": "RECOVERY_PLAN_COMPLETED", "EXHAUSTED": "RECOVERY_PLAN_EXHAUSTED",
                                                                       "ABORTED": "RECOVERY_PLAN_ABORTED"}[status], actor, p["d"]["origin_step_id"], {})
        gid = p["d"]["knowledge_gap_id"]
        if gid and status in ("COMPLETED", "EXHAUSTED"):
            new = "RESOLVED" if status == "COMPLETED" else "CONFIRMED"
            g = self.gaps[gid]
            if g["status"] in (("UNRESOLVED", "CONFIRMED") if new == "RESOLVED" else ("UNRESOLVED",)):
                g.update({"status": new, "status_reason": f"recovery plan {p['d']['recovery_plan_id']} {status}", "status_changed_at": self._now(),
                          "resolved_at": self._now() if new == "RESOLVED" else None})
                self._event(g["student_id"], g["solve_attempt_id"], f"GAP_HYPOTHESIS_{new}", actor, g["solution_step_id"], {})

    def _alt(self, a, p, stage, transfer=False):
        used = {i["learning_item_id"] for i in p["items"] if i["learning_item_id"]}
        d = p["d"]
        cands = self._cands(a, d["student_id"], d["origin_step_id"], d["target_skill_id"], d["target_subconcept_id"])
        for c in cands:
            p["meta"][c["learning_item_id"]] = c
        avoid = {i["source_problem_id"] for i in p["items"] if i.get("source_problem_id")} if transfer else None
        c = rlogic._pick(cands, rlogic.STAGE_TYPES.get(stage, rlogic.STAGE_TYPES["ISOLATED_EXECUTION"]), used, avoid_sources=avoid) \
            or (None if transfer else rlogic._pick(cands, sum(rlogic.STAGE_TYPES.values(), ()), used))
        if c is None:
            return None
        return {"stage": stage, "item_kind": "LEARNING_ITEM", "learning_item_id": c["learning_item_id"], "worked_step_id": None,
                "is_transfer": transfer, "required": True, "source_problem_id": c.get("source_problem_id")}

    def _insert(self, p, spec, reason):
        cur = p["d"]["current_item_ordinal"]
        for i in p["items"]:
            if i["ordinal"] > cur:
                i["ordinal"] += 1
        p["items"].append(self._item(spec, cur + 1, reason, p["meta"]))
        return cur + 1

    def _added(self, p):
        return sum(1 for i in p["items"] if i["added_reason"] != "PLANNED")

    def _advance(self, a, p, actor):
        items = sorted(p["items"], key=lambda i: i["ordinal"])
        nxt = next((i for i in items if i["status"] == "PENDING" and i["ordinal"] > p["d"]["current_item_ordinal"]), None)
        if nxt is not None and nxt["item_kind"] != "RETURN":
            self._present_item(p, nxt["ordinal"], actor)
            return {"transition": "NEXT_ITEM"}
        mastery = rlogic.mastery_status(items, p["d"]["mastery_policy"])
        if not mastery["met"] and self._added(p) < rlogic.MAX_ADDED_ITEMS:
            spec = (self._alt(a, p, "TRANSFER", True) if not mastery["transfer_passed"] else None) or self._alt(a, p, "ISOLATED_EXECUTION")
            if spec:
                self._present_item(p, self._insert(p, spec, "MASTERY_NOT_YET_MET"), actor)
                return {"transition": "EXTRA_ITEM"}
        self._end(p, "COMPLETED" if mastery["met"] else "EXHAUSTED", mastery, actor)
        if p["d"]["parent_recovery_plan_id"]:
            parent = self.plans[p["d"]["parent_recovery_plan_id"]]
            self._set_status(parent, "ACTIVE")
            a["plan"] = parent["d"]["recovery_plan_id"]
            self._advance(a, parent, actor)
            return {"transition": "BRANCH_FINISHED", "active_recovery_plan_id": parent["d"]["recovery_plan_id"]}
        if nxt is not None:
            nxt["status"], nxt["presented_at"] = "PRESENTED", "x"
            p["d"]["current_item_ordinal"] = nxt["ordinal"]
        return {"transition": "PLAN_" + p["d"]["status"]}

    def _branch_target(self, p):
        d = p["d"]
        if not d["gap_diagnosis_id"]:
            return None
        depth, cur = 0, d
        while cur["parent_recovery_plan_id"]:
            depth, cur = depth + 1, self.plans[cur["parent_recovery_plan_id"]]["d"]
        if depth >= rlogic.MAX_BRANCH_DEPTH:
            return None
        rows = [g for g in self._hyps(d["gap_diagnosis_id"]) if g["target_skill_id"] and g["target_skill_id"] != d["target_skill_id"]
                and g["failure_location"] == "PREREQUISITE"]
        if not rows:
            return None
        g = max(rows, key=lambda g: (g["confidence"], -g["rank"]))
        return {"gap_diagnosis_id": d["gap_diagnosis_id"], "knowledge_gap_id": g["knowledge_gap_id"], "skill_id": g["target_skill_id"],
                "subconcept_id": g["target_subconcept_id"], "label": g["target_label"]}

    def apply_item_response(self, student_id, plan_id, item_id, response, grade, state_version, idempotency_key=None, actor="TUTOR"):
        p0 = self._owned(plan_id, student_id)
        a = self._lock(p0["d"]["solve_attempt_id"], student_id)
        body = {"plan_id": str(plan_id), "item_id": item_id, "response": response, "state_version": state_version}

        def run():
            check_version(a["version"], state_version)
            p = p0
            item = next((i for i in p["items"] if i["recovery_plan_item_id"] == item_id), None)
            if item is None or p["d"]["status"] != "ACTIVE" or item["ordinal"] != p["d"]["current_item_ordinal"] or item["status"] != "PRESENTED" \
                    or item["item_kind"] == "RETURN":
                raise InvalidTransition("only the current item of an active plan accepts a response")
            tries = item["tries"] + 1
            decision = rlogic.adapt(item["stage"], grade["result"], tries)
            final = decision != "RETRY"
            item["tries"] = tries
            item["status"] = ("PASSED" if grade["result"] == "SUCCESS" else "FAILED") if final else "PRESENTED"
            item["independent_success"] = (grade["result"] == "SUCCESS" and tries == 1) if final else None
            item["last_response"], item["last_result"] = response, rlogic.teacher_result(grade)
            item["completed_at"] = "x" if final else None
            student_result = {k: grade[k] for k in ("result", "verdict", "feedback") if k in grade}
            sid, aid, step = p["d"]["student_id"], p["d"]["solve_attempt_id"], p["d"]["origin_step_id"]
            self._event(sid, aid, "RECOVERY_ITEM_SUBMITTED", "STUDENT", step, {})
            self._event(sid, aid, "RECOVERY_ITEM_EVALUATED", actor, step, {})
            transition = {"transition": "RETRY"}
            if decision == "CONFIRM" and self._added(p) < rlogic.MAX_ADDED_ITEMS:
                spec = self._alt(a, p, item["stage"], item["is_transfer"])
                if spec:
                    self._insert(p, spec, "CONFIRMATION_AFTER_HELP")
            elif decision in ("ALTERNATE", "BRANCH"):
                target = self._branch_target(p) if decision == "BRANCH" else None
                if target:
                    try:
                        child = self._make_plan(a, step, target, "BRANCH", p["d"]["recovery_plan_id"], False)
                    except rlogic.NoRecoveryMaterial:
                        target = None
                    else:
                        self._set_status(p, "SUSPENDED")
                        self._event(sid, aid, "RECOVERY_PLAN_BRANCHED", actor, step, {})
                        a["plan"] = child["d"]["recovery_plan_id"]
                        transition = {"transition": "BRANCHED", "active_recovery_plan_id": child["d"]["recovery_plan_id"]}
                if not target and self._added(p) < rlogic.MAX_ADDED_ITEMS:
                    spec = self._alt(a, p, item["stage"], item["is_transfer"])
                    if spec:
                        self._insert(p, spec, "ALTERNATE_AFTER_FAILURE")
            if final and transition["transition"] != "BRANCHED":
                transition = self._advance(a, p, actor)
            a["version"] += 1
            return {"result": student_result, "decision": decision, **transition, "state_version": a["version"],
                    "recovery_plan": self._view(self.plans[a["plan"] or p["d"]["recovery_plan_id"]])}

        return self._idem(a["student_id"], idempotency_key, "recovery_item_response", body, run)

    def leave_recovery(self, student_id, plan_id, state_version, *, abort=False, idempotency_key=None, actor="STUDENT"):
        p0 = self._owned(plan_id, student_id)
        a = self._lock(p0["d"]["solve_attempt_id"], student_id)
        body = {"plan_id": str(plan_id), "state_version": state_version}

        def run():
            check_version(a["version"], state_version)
            if a["mode"] != "RECOVERY":
                raise InvalidTransition("the attempt is not in a recovery detour")
            root = p0
            while root["d"]["parent_recovery_plan_id"]:
                root = self.plans[root["d"]["parent_recovery_plan_id"]]
            family, queue = [], [root["d"]["recovery_plan_id"]]
            while queue:
                cur = queue.pop(0)
                family.append(self.plans[cur])
                queue += [i for i, x in self.plans.items() if x["d"]["parent_recovery_plan_id"] == cur]
            open_plans = [x for x in family if x["d"]["status"] in ("ACTIVE", "SUSPENDED")]
            if open_plans and not abort:
                raise InvalidTransition("finish the detour first, or leave it early with /abort")
            for x in open_plans:
                self._end(x, "ABORTED", rlogic.mastery_status(x["items"], x["d"]["mastery_policy"]), actor)
            for x in family:
                for i in x["items"]:
                    if i["status"] in ("PENDING", "PRESENTED"):
                        i["status"] = "PASSED" if i["item_kind"] == "RETURN" else "SKIPPED"
            step = root["d"]["origin_step_id"]
            row = self.steps[(a["id"], step)]
            if row["state"] == "DETOURED":
                row["state"] = "RETRY_PRESENTED" if row["count"] > 0 else "PRESENTED"
            a["plan"], a["mode"] = None, "SOLVING"
            a["version"] += 1
            self._event(a["student_id"], a["id"], "RETURNED_TO_ORIGINAL_STEP", actor, step, {})
            self._event(a["student_id"], a["id"], "STEP_PRESENTED", "SYSTEM", step, {})
            return {"returned_to_step_id": step, "recovery_plan_id": root["d"]["recovery_plan_id"], "plan_status": root["d"]["status"],
                    "state_version": a["version"]}

        return self._idem(a["student_id"], idempotency_key, "recovery_abort" if abort else "recovery_resume", body, run)

    def list_admin_plans(self, *, student_id=None, status=None, limit=100):
        rows = []
        for p in sorted(self.plans.values(), key=lambda p: p["d"]["created_at"], reverse=True):
            d = p["d"]
            if (student_id is not None and d["student_id"] != str(student_id)) or (status and d["status"] != status):
                continue
            a = self.attempts[d["solve_attempt_id"]]
            rows.append({"recovery_plan_id": d["recovery_plan_id"], "student_id": d["student_id"], "email": None, "solve_attempt_id": d["solve_attempt_id"],
                         "problem_code": self._dag(a)["problem_code"], "origin_step_id": d["origin_step_id"], "trigger": d["trigger"],
                         "target_skill_id": d["target_skill_id"], "target_label": d["target_label"], "status": d["status"],
                         "parent_recovery_plan_id": d["parent_recovery_plan_id"], "outcome": d["outcome"], "created_at": d["created_at"],
                         "ended_at": d["ended_at"], "items": len(p["items"]),
                         "passed": sum(1 for i in p["items"] if i["status"] == "PASSED" and i["item_kind"] == "LEARNING_ITEM"),
                         "failed": sum(1 for i in p["items"] if i["status"] == "FAILED"),
                         "adapted": sum(1 for i in p["items"] if i["added_reason"] != "PLANNED")})
        return rows[:min(max(limit, 1), 500)]

    def get_admin_plan_detail(self, plan_id):
        p = self._owned(plan_id, None)
        view = self._view(p)
        view["items_teacher"] = [{k: i[k] for k in rlogic.TEACHER_ITEM_KEYS} for i in sorted(p["items"], key=lambda i: i["ordinal"])]
        view["student_id"], view["knowledge_gap_id"], view["gap_diagnosis_id"] = (p["d"]["student_id"], p["d"]["knowledge_gap_id"],
                                                                                    p["d"]["gap_diagnosis_id"])
        return view

    def get_recovery_summary(self, attempt_id):
        a = self.attempts[str(attempt_id)]
        if not a.get("plan"):
            return None
        d = self.plans[a["plan"]]["d"]
        return {"recovery_plan_id": d["recovery_plan_id"], "target_label": d["target_label"], "status": d["status"]}


# ---------------------------------------------------------------------------------------------------------- the scenario

EXPECTED = {"start": 201, "stale create": 409, "unknown step": 404, "unknown attempt diagnoses": 404, "unknown plan": 404, "wrong item": 404,
            "stale respond": 409, "resume while active": 409, "unknown attempt plans": 404, "no longer recovering": 409,
            "diagnosis trigger without id": 409, "unknown diagnosis": 404, "key reuse": 422}


def scenario(run: Run) -> None:
    base = "/v1/attempts/{aid}"
    first = run.call("start", "POST", "/v1/students/{sid}/problems/" + CODE + "/attempts")
    run.aid = first["solve_attempt_id"]
    saved = run.call("response", "POST", base + "/steps/st1/responses", json={"response_text": "no idea", "state_version": 2, "evaluate": False})
    failed = run.call("outcome failed", "POST", base + "/steps/st1/outcome", json={
        "result": "FAILED", "state_version": saved["state_version"],
        "evaluation": {"verdict": "INCORRECT", "failure_mode": "CANNOT_EXECUTE", "failure_location": "SKILL", "feedback": "x"}})
    diag = run.call("diagnose", "POST", base + "/steps/st1/diagnose")
    run.call("diagnose again", "POST", base + "/steps/st1/diagnose")
    run.call("unknown step", "POST", base + "/steps/NOPE/diagnose")
    run.call("diagnose unpresented step", "POST", base + "/steps/st3/diagnose")
    run.call("diagnoses", "GET", base + "/diagnoses")
    run.call("unknown attempt diagnoses", "GET", f"/v1/attempts/{uuid.uuid4()}/diagnoses")
    run.call("admin diagnoses", "GET", "/v1/admin/attempts/{aid}/diagnoses")
    run.call("admin student gaps", "GET", "/v1/admin/students/{sid}/knowledge-gaps")
    run.call("admin student gaps filtered", "GET", "/v1/admin/students/{sid}/knowledge-gaps", params={"status": "RESOLVED"})
    run.call("admin gap overview", "GET", "/v1/admin/knowledge-gaps")
    run.call("runtime with diagnosis", "GET", base + "/runtime")
    run.call("diagnosis trigger without id", "POST", base + "/recovery-plans", json={"state_version": failed["state_version"], "trigger": "DIAGNOSIS"})
    run.call("unknown diagnosis", "POST", base + "/recovery-plans", json={"state_version": failed["state_version"], "trigger": "DIAGNOSIS",
                                                                          "gap_diagnosis_id": str(uuid.uuid4())})
    run.call("stale create", "POST", base + "/recovery-plans", json={"state_version": 1})
    created = run.call("create plan", "POST", base + "/recovery-plans", headers={"Idempotency-Key": "c1"}, json={
        "state_version": failed["state_version"], "trigger": "DIAGNOSIS", "gap_diagnosis_id": diag["gap_diagnosis_id"]})
    plan = created["recovery_plan"]["recovery_plan_id"]
    run.plan = plan
    run.call("create replay", "POST", base + "/recovery-plans", headers={"Idempotency-Key": "c1"}, json={
        "state_version": failed["state_version"], "trigger": "DIAGNOSIS", "gap_diagnosis_id": diag["gap_diagnosis_id"]})
    run.call("key reuse", "POST", base + "/recovery-plans", headers={"Idempotency-Key": "c1"}, json={"state_version": failed["state_version"]})
    run.call("create resumes", "POST", base + "/recovery-plans", json={"state_version": 2})
    run.call("plans of attempt", "GET", base + "/recovery-plans")
    run.call("unknown attempt plans", "GET", f"/v1/attempts/{uuid.uuid4()}/recovery-plans")
    run.call("plan", "GET", f"/v1/recovery-plans/{plan}")
    run.call("unknown plan", "GET", f"/v1/recovery-plans/{uuid.uuid4()}")
    nxt = run.call("next", "GET", f"/v1/recovery-plans/{plan}/next")
    run.call("runtime in recovery", "GET", base + "/runtime")
    run.call("resume while active", "POST", f"/v1/recovery-plans/{plan}/resume", json={"state_version": created["state_version"]})
    version = created["state_version"]

    def answer(label, *, wrong=False, key=None):
        nonlocal version
        view = run.call(label + " (view)", "GET", f"/v1/recovery-plans/{plan}/next")
        item = view["item"]
        form = (item.get("content") or {}).get("form")
        body = ({"acknowledged": True} if item["item_kind"] == "THEORY" else {"choice_index": 0 if wrong else 1} if form == "MCQ"
                else {"response_text": "a plausible idea"})
        out = run.call(label, "POST", f"/v1/recovery-plans/{plan}/items/{item['recovery_plan_item_id']}/responses",
                       headers={"Idempotency-Key": key} if key else None, json={"state_version": version, **body})
        version = out["state_version"]
        return out

    run.call("wrong item", "POST", f"/v1/recovery-plans/{plan}/items/{uuid.uuid4()}/responses", json={"state_version": version, "acknowledged": True})
    run.call("stale respond", "POST", f"/v1/recovery-plans/{plan}/items/{nxt['item']['recovery_plan_item_id']}/responses",
             json={"state_version": 1, "acknowledged": True})
    answer("acknowledge", key="r1")
    run.call("answer replay", "POST", f"/v1/recovery-plans/{plan}/items/{nxt['item']['recovery_plan_item_id']}/responses",
             headers={"Idempotency-Key": "r1"}, json={"state_version": version - 1, "acknowledged": True})
    answer("wrong 1", wrong=True)
    answer("wrong 2", wrong=True)                      # a failed recognition item with no prerequisite hypothesis: an alternate item
    answer("right after alternate")
    answer("isolated")
    answer("guided")
    done = answer("transfer")
    run.call("plan finished", "GET", f"/v1/recovery-plans/{plan}")
    run.call("admin plans", "GET", "/v1/admin/recovery-plans")
    run.call("admin plans by status", "GET", "/v1/admin/recovery-plans", params={"status": "COMPLETED"})
    run.call("admin plans by student", "GET", "/v1/admin/recovery-plans", params={"student_id": run.sid})
    run.call("admin plan detail", "GET", f"/v1/admin/recovery-plans/{plan}")
    run.call("unknown admin plan", "GET", f"/v1/admin/recovery-plans/{uuid.uuid4()}")
    run.call("gaps after plan", "GET", "/v1/admin/students/{sid}/knowledge-gaps")
    run.call("gap overview after plan", "GET", "/v1/admin/knowledge-gaps", params={"status": "RESOLVED"})
    left = run.call("resume", "POST", f"/v1/recovery-plans/{plan}/resume", headers={"Idempotency-Key": "u1"}, json={"state_version": done["state_version"]})
    run.call("resume replay", "POST", f"/v1/recovery-plans/{plan}/resume", headers={"Idempotency-Key": "u1"}, json={"state_version": done["state_version"]})
    run.call("no longer recovering", "POST", f"/v1/recovery-plans/{plan}/resume", json={"state_version": left["state_version"]})
    run.call("runtime after resume", "GET", base + "/runtime")
    second = run.call("create second plan", "POST", base + "/recovery-plans", json={"state_version": left["state_version"]})
    plan = run.plan = second["recovery_plan"]["recovery_plan_id"]
    version = second["state_version"]
    answer("second acknowledge")
    aborted = run.call("abort", "POST", f"/v1/recovery-plans/{plan}/abort", json={"state_version": version})
    run.call("plan aborted", "GET", f"/v1/recovery-plans/{plan}")
    run.call("plans of attempt after", "GET", base + "/recovery-plans")
    run.call("admin plans aborted", "GET", "/v1/admin/recovery-plans", params={"status": "ABORTED", "limit": 5})
    run.call("runtime after abort", "GET", base + "/runtime")
    assert aborted["plan_status"] == "ABORTED"


@pytest.fixture()
def clients(content_table, monkeypatch):
    """Both backends over one moto content store; the grader of sub-problem items is scripted."""
    seed_content()
    seed_learning()
    sid = str(uuid.uuid4())
    app.dependency_overrides[security.get_current_student_id] = lambda: UUID(sid)
    app.dependency_overrides[security.require_admin_api_key] = lambda: None
    monkeypatch.setattr(routes, "EVALUATOR", lambda ctx: {"verdict": "CORRECT", "confidence": 0.95, "feedback": "Well done.",
                                                          "failure_mode": "NONE", "failure_location": "NONE", "evidence": "secret"})
    previous = hooks._auto_diagnose
    hooks.register_auto_diagnose(diagnosis_module.auto_diagnose)
    composed = DynamoDBLearnerStore()
    with stores.override_store("content", DynamoDBContentStore()):
        yield sid, {"postgres": BackendClient(GapOracle()), "dynamodb": BackendClient(composed)}
    hooks.register_auto_diagnose(previous)
    app.dependency_overrides.clear()


def scrub(value, pattern):
    """Generated ids inside free text (a status reason names its plan) are not part of the contract."""
    if isinstance(value, dict):
        return {k: scrub(v, pattern) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, pattern) for v in value]
    return pattern.sub("<uuid>", value) if isinstance(value, str) else value


def test_every_diagnosis_gap_and_recovery_route_answers_identically_on_both_backends(clients):
    sid, backends = clients
    runs = {name: Run(client, sid) for name, client in backends.items()}
    for run in runs.values():
        run.sid, run.plan = sid, None
        scenario(run)
    pg, ddb = runs["postgres"].log, runs["dynamodb"].log
    assert [x[0] for x in pg] == [x[0] for x in ddb] and len(pg) > 60
    problems = []
    uuid_in_text = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    for (label, s0, b0), (_, s1, b1) in zip(pg, ddb, strict=True):
        if label in EXPECTED:
            assert (s0, s1) == (EXPECTED[label],) * 2, (label, s0, s1)
        found = [f"status {s0} vs {s1}"] if s0 != s1 else []
        found += diff(scrub(b0, uuid_in_text), scrub(b1, uuid_in_text))
        problems += [f"{label}: {d}" for d in found]
    assert not problems, "\n".join(problems[:40])
    assert [s for _, s, _ in pg if s >= 500] == [] and [s for _, s, _ in ddb if s >= 500] == []


def test_a_foreign_learner_gets_404_on_every_attempt_and_plan_route_on_both_backends(clients):
    sid, backends = clients
    runs = {name: Run(client, sid) for name, client in backends.items()}
    plans = {}
    for name, run in runs.items():
        run.sid = sid
        run.aid = run.call("start", "POST", "/v1/students/{sid}/problems/" + CODE + "/attempts")["solve_attempt_id"]
        saved = run.call("response", "POST", "/v1/attempts/{aid}/steps/st1/responses", json={"response_text": "x", "state_version": 2, "evaluate": False})
        run.call("outcome", "POST", "/v1/attempts/{aid}/steps/st1/outcome", json={"result": "FAILED", "state_version": saved["state_version"]})
        plans[name] = run.call("create", "POST", "/v1/attempts/{aid}/recovery-plans", json={"state_version": saved["state_version"] + 1})
    other = str(uuid.uuid4())
    app.dependency_overrides[security.get_current_student_id] = lambda: UUID(other)
    try:
        for name, run in runs.items():
            plan = plans[name]["recovery_plan"]["recovery_plan_id"]
            item = plans[name]["recovery_plan"]["items"][0]["recovery_plan_item_id"]
            for label, method, path, body in (
                    ("diagnose", "POST", "/v1/attempts/{aid}/steps/st1/diagnose", None),
                    ("diagnoses", "GET", "/v1/attempts/{aid}/diagnoses", None),
                    ("create", "POST", "/v1/attempts/{aid}/recovery-plans", {"state_version": 4}),
                    ("plans", "GET", "/v1/attempts/{aid}/recovery-plans", None),
                    ("plan", "GET", f"/v1/recovery-plans/{plan}", None),
                    ("next", "GET", f"/v1/recovery-plans/{plan}/next", None),
                    ("respond", "POST", f"/v1/recovery-plans/{plan}/items/{item}/responses", {"state_version": 4, "acknowledged": True}),
                    ("resume", "POST", f"/v1/recovery-plans/{plan}/resume", {"state_version": 4}),
                    ("abort", "POST", f"/v1/recovery-plans/{plan}/abort", {"state_version": 4})):
                run.call(label, method, path, json=body)
        for (label, s0, b0), (_, s1, b1) in zip(runs["postgres"].log[-9:], runs["dynamodb"].log[-9:], strict=True):
            assert (s0, s1) == (404, 404), (label, s0, s1, b0, b1)
            assert diff(b0, b1) == [], label
    finally:
        app.dependency_overrides[security.get_current_student_id] = lambda: UUID(sid)
    # the owner still sees an untouched plan on both sides
    for run in runs.values():
        assert run.call("owner plan", "GET", f"/v1/recovery-plans/{plans[next(n for n, r in runs.items() if r is run)]['recovery_plan']['recovery_plan_id']}"
                        )["status"] == "ACTIVE"


READS = {"list_diagnoses", "get_latest_diagnosis_for_step", "get_step_diagnosis_view", "list_student_gaps", "get_admin_gap_overview",
         "get_recovery_plan", "get_next_recovery_item", "load_item_response_context", "list_attempt_plans", "list_admin_plans",
         "get_admin_plan_detail", "get_recovery_summary"}
WRITES = {"diagnose_step", "update_gap_statuses", "rerank_diagnosis", "create_plan", "apply_item_response", "leave_recovery", "build_abort_plan_ops"}


@pytest.mark.parametrize("backend", ["Postgres", "DynamoDB"])
def test_method_names_follow_the_read_write_prefix_rule_so_a_frozen_store_serves_exactly_the_reads(backend):
    from mathbank_rest.stores import READ_PREFIXES

    cls = [getattr(__import__("mathbank_rest.stores.learner", fromlist=["x"]), f"{area}{backend}") for area in ("Diagnosis", "Recovery")]
    names = {n for c in cls for n in vars(c) if not n.startswith("_")}
    assert names == READS | WRITES
    assert {n for n in names if n.startswith(READ_PREFIXES)} == READS


@pytest.mark.parametrize("op,target,args", [
    ("diagnose_step", "step_diagnosis.diagnose_step", ("s", "a", "st1")),
    ("list_diagnoses", "step_diagnosis.list_diagnoses", ("s", "a")),
    ("list_student_gaps", "step_diagnosis.list_student_gaps", ("s", "OPEN", 5)),
    ("get_admin_gap_overview", "step_diagnosis.admin_gap_overview", ()),
    ("get_latest_diagnosis_for_step", "step_diagnosis.latest_for_step", ("s", "a", "st1")),
    ("create_plan", "step_recovery.create_plan", ("s", "a", 2)),
    ("get_recovery_plan", "step_recovery.get_plan", ("s", "p")),
    ("get_next_recovery_item", "step_recovery.next_item", ("s", "p")),
    ("load_item_response_context", "step_recovery.prepare_item_response", ("s", "p", "i", {}, 2, None)),
    ("apply_item_response", "step_recovery.apply_item_response", ("s", "p", "i", {}, {"result": "SUCCESS"}, 2)),
    ("leave_recovery", "step_recovery.leave_recovery", ("s", "p", 2)),
    ("list_attempt_plans", "step_recovery.list_attempt_plans", ("s", "a")),
    ("list_admin_plans", "step_recovery.admin_plans", ()),
    ("get_admin_plan_detail", "step_recovery.admin_plan_detail", ("p",)),
    ("get_recovery_summary", "step_recovery.recovery_summary", ("a",)),
])
def test_the_postgres_store_delegates_to_the_sql_layer_at_call_time(monkeypatch, op, target, args):
    """Behaviour unchanged by default: the Postgres store runs the SQL functions in one transaction, looked up at call time."""
    from mathbank_rest import step_diagnosis, step_recovery
    from mathbank_rest.db import postgres
    from mathbank_rest.stores.learner import PostgresLearnerStore

    conn, seen = object(), []

    class Tx:
        def __enter__(self):
            return conn

        def __exit__(self, *exc):
            return False

    class Engine:
        begin = connect = staticmethod(lambda: Tx())

    monkeypatch.setattr(postgres, "engine", Engine())
    module, name = target.split(".")
    monkeypatch.setattr({"step_diagnosis": step_diagnosis, "step_recovery": step_recovery}[module], name,
                        lambda c, *a, **k: seen.append((c, a, k)) or {"ok": op})
    getattr(PostgresLearnerStore(), op)(*args)
    assert seen and seen[0][0] is conn


def test_the_postgres_seams_are_harmless_no_ops():
    from mathbank_rest.stores.learner import PostgresLearnerStore

    assert PostgresLearnerStore().build_abort_plan_ops(object(), "s", "a", ["p"], "SYSTEM", "x") == 0
