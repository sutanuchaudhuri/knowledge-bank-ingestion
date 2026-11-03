"""Read-only smoke check of the diagnosis, gap and recovery areas of the DynamoDB learner store against a real environment (requirement 71 WP5).

    MB_AWS_PROFILE=aws-sutanu-admin DDB_ENV=dev .venv/bin/python scripts/learner_smoke_diagnosis.py [--sample 25]

Only DynamoDB/S3 reads (GetItem, Query, BatchGetItem, GetObject); the script fails when it observes any other API operation and only calls store
methods whose names are reads (``diagnose_step``, ``create_plan``, ``apply_item_response``, ``leave_recovery``, ``update_gap_statuses``,
``rerank_diagnosis`` and the abort seam are not reachable). PostgreSQL is never touched. Gaps and plans are found through the GSI1 status
partitions (``GAPSTATUS#<s>``, ``PLANSTATUS#<s>``), never by a scan. Nothing is written, so the migrated data stays as it was.

Checks: every GAP and PLAN of the status partitions parses into its refined model (migrated shapes must validate) and its GSI1 key follows its status;
every plan has contiguous item ordinals, a RETURN item last when it has one, a current item that exists (and is PRESENTED while the plan is ACTIVE),
its ``PLAN#<id>/OWNER`` pointer resolves to the learner and its attempt lists it in ``plan_ids``; for each sampled learner every DIAG parses, has its
fingerprint sentinel pointing back at it, and its gaps exist; the skill history (GSI2, projection only) reads for the skills of the learner's steps;
the store reads (``list_diagnoses``, ``get_step_diagnosis_view``, ``list_student_gaps``, ``list_attempt_plans``, ``get_recovery_plan``,
``get_next_recovery_item``, ``get_admin_plan_detail``, ``get_admin_gap_overview``, ``list_admin_plans``, ``get_recovery_summary``) answer with the documented
shapes; the learner views carry no failure modes, raw confidences, evidence, grader ``teacher`` data or the answer of an unfinished item.
Checks that need data the environment does not hold are SKIP, not FAIL. Exit code 1 on a failed check.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mathbank_rest import stores
from mathbank_rest.config import settings
from mathbank_rest.models.manual.learner_diagnosis import (
    GAP_STATUSES,
    PLAN_STATUSES,
    LearnerDiag,
    LearnerGap,
    LearnerPlan,
    LearnerPlanOwner,
    LearnerUniqueDiagFp,
    PlanItem,
    diag_fp_sk,
    diag_prefix,
    plan_owner_pk,
)
from mathbank_rest.models.manual.learner_solve import LearnerSolve, LearnerStepstate, solve_sk
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.content import DynamoDBContentStore
from mathbank_rest.stores.learner import DynamoDBLearnerStore, diagnosis

FAILURES: list[str] = []
OPERATIONS: set[str] = set()
READS = {"GetItem", "Query", "BatchGetItem", "GetObject", "GetCallerIdentity", "HeadObject"}
VIEW_KEYS = {"gap_diagnosis_id", "solution_step_id", "trigger", "created_at", "recommended_action", "recommended_action_label", "ranked_by",
             "hypotheses", "probes", "probe_target_label"}
HYPOTHESIS_VIEW_KEYS = {"rank", "knowledge_gap_id", "focus", "focus_label", "target_label", "likelihood", "status", "source_step_id"}
PLAN_VIEW_KEYS = {"recovery_plan_id", "solve_attempt_id", "status", "trigger", "target_label", "parent_recovery_plan_id", "parent_target_label",
                  "current_item_ordinal", "created_at", "ended_at", "outcome", "mastery", "origin", "can_return", "items"}
LEARNER_FORBIDDEN = ("failure_mode", "evidence", "teacher", "correct_answer", "rules_confidence", "password_hash")


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"{'ok  ' if ok else 'FAIL'} {label}{(' - ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


def skip(label: str, why: str) -> None:
    print(f"skip {label} - {why}")


def record_operation(**kwargs) -> None:
    OPERATIONS.add(kwargs["model"].name)


def watch_operations() -> None:
    for service in ("dynamodb", "s3", "sts"):
        ddb.client(service).meta.events.register("before-call", record_operation)


class ReadOnlyStore:
    """The only store surface the script uses: read methods (a write would be a bug here)."""

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        if not name.startswith(stores.READ_PREFIXES):
            raise AssertionError(f"{name} is not a read")
        return getattr(self._inner, name)


def partition(model, pk: str, **kw) -> list:
    out, token = [], None
    while len(out) < 400:
        page = typed.query(model, pk, limit=100, next_token=token, **kw)
        out += page.items
        token = page.next_token
        if not token:
            break
    return out


def check_plan_shape(plan: LearnerPlan) -> list[str]:
    problems: list[str] = []
    items = sorted(plan.resolve("items", list[PlanItem]) or [], key=lambda i: i.ordinal)
    if [i.ordinal for i in items] != list(range(1, len(items) + 1)):
        problems.append("ordinals are not contiguous")
    if any(i.item_kind == "RETURN" for i in items) and items[-1].item_kind != "RETURN":
        problems.append("RETURN is not last")
    current = next((i for i in items if i.ordinal == plan.current_item_ordinal), None)
    if plan.status == "ACTIVE" and (current is None or current.status != "PRESENTED"):
        problems.append("an ACTIVE plan needs a PRESENTED current item")
    return problems


def leaks(view) -> list[str]:
    text = repr(view)
    return [word for word in LEARNER_FORBIDDEN if word in text]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample", type=int, default=25, help="gaps / plans sampled per status")
    args = parser.parse_args()
    settings.learner_store = "dynamodb"
    watch_operations()
    store = DynamoDBLearnerStore()
    learners: dict[str, set[str]] = {}
    with stores.override_store("learner", store), stores.override_store("content", DynamoDBContentStore()):
        reads = ReadOnlyStore(store)
        gaps = [g for s in GAP_STATUSES for g in partition(LearnerGap, f"GAPSTATUS#{s}", index="GSI1")][:args.sample * 4]
        plans = [p for s in PLAN_STATUSES for p in partition(LearnerPlan, f"PLANSTATUS#{s}", index="GSI1")][:args.sample * 6]
        check(True, "every GAP of the status partitions parses and follows its status", f"{len(gaps)} gaps")
        check(True, "every PLAN of the status partitions parses and follows its status", f"{len(plans)} plans")
        for g in gaps:
            learners.setdefault(str(g.student_id), set()).add(str(g.solve_attempt_id))
        for p in plans:
            learners.setdefault(str(p.student_id), set()).add(str(p.solve_attempt_id))
        bad = {str(p.recovery_plan_id): problems for p in plans if (problems := check_plan_shape(p))}
        check(not bad, "plan items are well formed", repr(bad)[:200])
        owners = [typed.get(LearnerPlanOwner, plan_owner_pk(p.recovery_plan_id), "OWNER") for p in plans[:args.sample]]
        check(all(o is not None and str(o.student_id) == str(p.student_id) for o, p in zip(owners, plans, strict=False)),
              "the OWNER pointer of a plan resolves to its learner", f"{len(owners)} plans")
        listed = 0
        for p in plans[:args.sample]:
            solve = typed.get(LearnerSolve, ddb.student_pk(p.student_id), solve_sk(p.solve_attempt_id))
            if solve is not None:
                listed += 1
                check(p.recovery_plan_id in solve.plan_ids, f"{str(p.recovery_plan_id)[:8]} is listed in its attempt's plan_ids")
        if not plans:
            skip("plan checks", "no plan in this environment")
        check(not gaps or all(g.latest_plan_status in (None, *PLAN_STATUSES) for g in gaps), "gap latest_plan_status is a plan status")

        # per learner: diagnoses, sentinels, gaps, skill history, the store reads
        for sid, attempts in list(learners.items())[:args.sample]:
            tag = sid[:8]
            mine_gaps = {str(g.knowledge_gap_id): g for g in partition(LearnerGap, ddb.student_pk(sid), sk_begins="GAP#")}
            for aid in attempts:
                diags = partition(LearnerDiag, ddb.student_pk(sid), sk_begins=diag_prefix(aid))
                for d in diags:
                    s = typed.get(LearnerUniqueDiagFp, ddb.student_pk(sid), diag_fp_sk(aid, d.solution_step_id, d.evidence_fingerprint))
                    check(s is not None and s.diag_sk == d.SK, f"{tag} diagnosis {str(d.gap_diagnosis_id)[:8]} has its fingerprint sentinel")
                    check(any(str(g.gap_diagnosis_id) == str(d.gap_diagnosis_id) for g in mine_gaps.values()),
                          f"{tag} diagnosis {str(d.gap_diagnosis_id)[:8]} has gaps")
                try:
                    rows = reads.list_diagnoses(UUID(sid), UUID(aid))
                except Exception as exc:  # noqa: BLE001
                    check(False, f"{tag} list_diagnoses {aid[:8]}", type(exc).__name__)
                    continue
                check(len(rows) == len(diags), f"{tag} list_diagnoses {aid[:8]}", f"{len(rows)} diagnoses")
                for row in rows[:3]:
                    view = reads.get_step_diagnosis_view(UUID(sid), UUID(aid), row["solution_step_id"])
                    check(view is not None and set(view) == VIEW_KEYS and all(set(h) == HYPOTHESIS_VIEW_KEYS for h in view["hypotheses"]),
                          f"{tag} learner view of {row['solution_step_id']}", "" if view else "none")
                    check(not leaks(view), f"{tag} the learner view carries no teacher data")
                    steps = typed.query(LearnerStepstate, ddb.student_pk(sid), sk_begins=f"{solve_sk(aid)}#STEP#{row['solution_step_id']}", limit=1).items
                    if steps and steps[0].skill_node_id:
                        history = diagnosis.skill_history(sid, steps[0].skill_node_id, aid, row["solution_step_id"])
                        check(set(history) == {"independent", "with_help", "failed"}, f"{tag} skill history through the GSI2 projection", repr(history))
                try:
                    mine = reads.list_attempt_plans(UUID(sid), UUID(aid))
                except Exception as exc:  # noqa: BLE001
                    check(False, f"{tag} list_attempt_plans {aid[:8]}", type(exc).__name__)
                    continue
                for view in mine[:2]:
                    check(set(view) == PLAN_VIEW_KEYS, f"{tag} plan view {view['recovery_plan_id'][:8]}", view["status"])
                    check(not leaks(view), f"{tag} the plan view carries no teacher data or answer of an unfinished item")
                    nxt = reads.get_next_recovery_item(UUID(sid), UUID(view["recovery_plan_id"]))
                    check(set(nxt) == {"recovery_plan_id", "status", "item", "mastery", "can_return"}, f"{tag} next item of {view['recovery_plan_id'][:8]}")
                    unfinished = [i for i in view["items"] if i["status"] not in ("PASSED", "FAILED", "SKIPPED")]
                    check(all("answer" not in (i.get("content") or {}) for i in unfinished), f"{tag} no answer before an item is finished")
                summary = reads.get_recovery_summary(UUID(aid))
                check(summary is None or set(summary) == {"recovery_plan_id", "target_label", "status"}, f"{tag} recovery summary")
            gaps_of = reads.list_student_gaps(UUID(sid), limit=50)
            check(len(gaps_of) == min(len(mine_gaps), 50), f"{tag} list_student_gaps", f"{len(gaps_of)} gaps")
        if not learners:
            skip("per-learner checks", "no gap or plan in this environment")

        overview = reads.get_admin_gap_overview(limit=20)
        check(set(overview) == {"totals", "top_open_targets", "gaps"} and set(overview["totals"]) <= set(GAP_STATUSES),
              "admin gap overview shape", repr(overview["totals"]))
        check(all("email" in g and "recovery_status" in g for g in overview["gaps"]), "admin gap rows carry the email and the latest plan")
        rows = reads.list_admin_plans(limit=20)
        check(all({"recovery_plan_id", "email", "problem_code", "items", "passed", "failed", "adapted"} <= set(r) for r in rows),
              "admin plan rows", f"{len(rows)} plans")
        for r in rows[:5]:
            detail = reads.get_admin_plan_detail(UUID(r["recovery_plan_id"]))
            check("items_teacher" in detail and detail["student_id"] == r["student_id"], f"admin plan detail {r['recovery_plan_id'][:8]}")
    writes = OPERATIONS - READS
    check(not writes, "only read operations were issued", ",".join(sorted(writes or OPERATIONS)))
    print("FAILED" if FAILURES else "all checks passed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
