"""Recovery plans (v2 Phase 10) — runtime_extension/11 (plan runtime), 03 (schema), 13 (REST), 14 §7–9.

A recovery plan is a short, persisted detour from the exact step where a student is stuck:

    FOUNDATION (worked example) → RECOGNITION → ISOLATED_EXECUTION → GUIDED_APPLICATION
    → TRANSFER (a different source problem) → RETURN_TO_STEP

Items are approved, non-proof learning items for the gap's skill (falling back to its subconcept),
never items generated from the problem being solved. The plan is written before the first item is
shown; the runtime (not an agent's memory) owns it. MCQs are graded deterministically; subproblems
by the step evaluator *outside* the attempt row lock. Correct answers and seeds are only revealed
after an item is finished.

Adaptation (spec 11 §6): independent success → advance; success after a retry → one same-stage
confirmation item; a final failure → an alternate same-stage item, or — for a failed recognition
(conceptual) item — a child plan on the strongest prerequisite hypothesis. A plan is COMPLETED only
when the mastery policy is met; when items run out first it ends EXHAUSTED. Either way the student
returns to the exact origin step (RETURNED_TO_ORIGINAL_STEP); a plan never sets mastery directly.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Callable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from mathbank_rest import step_tutor
from mathbank_rest.step_runtime import (
    CROSS_REFERENCE_STUB_RE,
    InvalidTransition, NotFound, RuntimeError_, _bump_version, _check_version, _event, _lock_attempt, _outbox,
    _remember, _replay,
)

PLANNER_VERSION = "recovery-rules-v1"
MAX_TRIES_PER_ITEM = 2
MAX_ADDED_ITEMS = 3
MAX_BRANCH_DEPTH = 1
CANDIDATE_LIMIT = 80
DEFAULT_POLICY = {"independent_successes_required": 2, "transfer_success_required": True,
                  "max_help_level_on_final": 1}

STAGES = ("FOUNDATION", "RECOGNITION", "ISOLATED_EXECUTION", "GUIDED_APPLICATION", "TRANSFER", "RETURN_TO_STEP")
STAGE_TYPES = {
    "RECOGNITION": ("MCQ_METHOD_RECOGNITION", "MCQ_LOCAL_GOAL", "MCQ_FIRST_MOVE"),
    "ISOLATED_EXECUTION": ("MCQ_INTERMEDIATE_SKILL", "SUBPROBLEM_FIRST_MOVE", "MCQ_FIRST_MOVE"),
    "GUIDED_APPLICATION": ("SUBPROBLEM_NEXT_INTERMEDIATE", "MCQ_STEP_SEQUENCE", "SUBPROBLEM_FIRST_MOVE"),
    "TRANSFER": ("SUBPROBLEM_FIRST_MOVE", "SUBPROBLEM_NEXT_INTERMEDIATE", "MCQ_INTERMEDIATE_SKILL",
                 "MCQ_FIRST_MOVE"),
}
STAGE_LABELS = {
    "FOUNDATION": "Worked example", "RECOGNITION": "Recognise the idea", "ISOLATED_EXECUTION": "Use it once",
    "GUIDED_APPLICATION": "Use it in context", "TRANSFER": "Try it somewhere new",
    "RETURN_TO_STEP": "Back to your problem",
}
TYPE_LABELS = {
    "MCQ_METHOD_RECOGNITION": "Which method fits?", "MCQ_LOCAL_GOAL": "What is the local goal?",
    "MCQ_FIRST_MOVE": "Pick the first move", "MCQ_INTERMEDIATE_SKILL": "Pick the intermediate result",
    "MCQ_STEP_SEQUENCE": "Order the reasoning", "SUBPROBLEM_FIRST_MOVE": "Make the first move",
    "SUBPROBLEM_NEXT_INTERMEDIATE": "Reach the next result",
}
ENDED = ("COMPLETED", "EXHAUSTED", "ABORTED", "SUPERSEDED")


class NoRecoveryMaterial(RuntimeError_):
    status_code = 409
    code = "NO_RECOVERY_MATERIAL"


# ---------------------------------------------------------------- pure planning logic (unit-tested)

def _pick(candidates: list[dict], types: tuple[str, ...], used: set[str], *, avoid_sources: set | None = None,
          skill_only: bool = False) -> dict | None:
    """First unused candidate of the stage's types, by type preference, skill-level matches first."""
    for require_skill in ((True,) if skill_only else (True, False)):
        for t in types:
            for c in candidates:
                if c["learning_item_id"] in used or c["transformation_type"] != t:
                    continue
                if require_skill and not c.get("skill_match"):
                    continue
                if avoid_sources and c.get("source_problem_id") in avoid_sources:
                    continue
                return c
    return None


def build_plan(candidates: list[dict], worked_step_id: str | None = None, *, include_return: bool = True) -> list[dict]:
    """Ordered item specs for a plan. ``candidates`` are pre-ordered learning items with
    ``learning_item_id, transformation_type, transformed_form, source_problem_id, skill_match``."""
    items: list[dict] = []
    used: set[str] = set()
    if worked_step_id:
        items.append({"stage": "FOUNDATION", "item_kind": "THEORY", "worked_step_id": worked_step_id,
                      "learning_item_id": None, "is_transfer": False, "required": False})
    for stage in ("RECOGNITION", "ISOLATED_EXECUTION", "GUIDED_APPLICATION"):
        c = _pick(candidates, STAGE_TYPES[stage], used)
        if c:
            used.add(c["learning_item_id"])
            items.append({"stage": stage, "item_kind": "LEARNING_ITEM", "learning_item_id": c["learning_item_id"],
                          "worked_step_id": None, "is_transfer": False, "required": True,
                          "source_problem_id": c.get("source_problem_id")})
    sources = {i.get("source_problem_id") for i in items if i.get("source_problem_id")}
    c = (_pick(candidates, STAGE_TYPES["TRANSFER"], used, avoid_sources=sources, skill_only=True)
         or _pick(candidates, STAGE_TYPES["TRANSFER"], used, avoid_sources=sources))
    if c:
        used.add(c["learning_item_id"])
        items.append({"stage": "TRANSFER", "item_kind": "LEARNING_ITEM", "learning_item_id": c["learning_item_id"],
                      "worked_step_id": None, "is_transfer": True, "required": True,
                      "source_problem_id": c.get("source_problem_id")})
    if include_return:
        items.append({"stage": "RETURN_TO_STEP", "item_kind": "RETURN", "learning_item_id": None,
                      "worked_step_id": None, "is_transfer": False, "required": True})
    for i, item in enumerate(items, start=1):
        item["ordinal"] = i
    return items


def mastery_status(items: list[dict], policy: dict) -> dict:
    """Progress against the mastery policy from item rows (``item_kind, status, tries,
    independent_success, is_transfer``)."""
    practice = [i for i in items if i["item_kind"] == "LEARNING_ITEM"]
    independent = sum(1 for i in practice if i["status"] == "PASSED" and i.get("independent_success"))
    max_extra_tries = int(policy.get("max_help_level_on_final", 1))
    transfer_ok = any(i["is_transfer"] and i["status"] == "PASSED" and (i.get("tries") or 1) - 1 <= max_extra_tries
                      for i in practice)
    need = int(policy.get("independent_successes_required", 2))
    met = independent >= need and (transfer_ok or not policy.get("transfer_success_required", True))
    return {"independent_successes": independent, "independent_successes_required": need,
            "transfer_passed": transfer_ok, "transfer_required": bool(policy.get("transfer_success_required", True)),
            "met": met}


def adapt(stage: str, result: str, tries: int) -> str:
    """Next move after grading an item: ADVANCE, CONFIRM, RETRY, ALTERNATE or BRANCH."""
    if stage == "FOUNDATION":
        return "ADVANCE"
    if result == "SUCCESS":
        return "ADVANCE" if tries == 1 else "CONFIRM"
    if tries < MAX_TRIES_PER_ITEM:
        return "RETRY"
    return "BRANCH" if stage == "RECOGNITION" else "ALTERNATE"


def grade_mcq(choices: list, correct_answer: str, choice_index: int | None) -> dict:
    ok = choice_index is not None and 0 <= choice_index < len(choices) and choices[choice_index] == correct_answer
    return {"result": "SUCCESS" if ok else "FAILED", "verdict": "CORRECT" if ok else "INCORRECT",
            "feedback": "Correct." if ok else "Not this one. Look again at what the problem needs at this point.",
            "grader": "deterministic"}


def _variety(student_id: str, item_id: str) -> str:
    return hashlib.md5(f"{student_id}:{item_id}".encode()).hexdigest()


# ---------------------------------------------------------------- loading

def _target_for(conn: Connection, attempt: dict, step_id: str, gap_diagnosis_id: str | None) -> dict:
    """Recovery target: the top skill-level hypothesis of the given (or latest) diagnosis for the step;
    the step's own skill when there is no diagnosis."""
    from mathbank_rest import step_diagnosis

    if gap_diagnosis_id:
        d = conn.execute(text(
            "SELECT gap_diagnosis_id::text FROM pedagogy.gap_diagnosis WHERE gap_diagnosis_id = CAST(:d AS uuid) "
            "AND solve_attempt_id = CAST(:a AS uuid) AND solution_step_id = :s"),
            {"d": gap_diagnosis_id, "a": str(attempt["solve_attempt_id"]), "s": step_id}).scalar()
        if d is None:
            raise NotFound("diagnosis not found for this step")
        diag = step_diagnosis._diagnosis_row(conn, d)
    else:
        diag = step_diagnosis.latest_for_step(conn, str(attempt["solve_attempt_id"]), step_id)
    if diag and diag["hypotheses"]:
        h = next((h for h in diag["hypotheses"] if h["target_skill_id"]), diag["hypotheses"][0])
        return {"gap_diagnosis_id": diag["gap_diagnosis_id"], "knowledge_gap_id": h["knowledge_gap_id"],
                "skill_id": h["target_skill_id"], "subconcept_id": h["target_subconcept_id"],
                "label": h["target_label"]}
    s = conn.execute(text(
        "SELECT s.skill_node_id, s.subconcept_node_id, coalesce(s.skill_name, t.name) AS label "
        "  FROM pedagogy.solution_step s LEFT JOIN pedagogy.taxonomy_node t ON t.taxonomy_node_id = s.skill_node_id "
        " WHERE s.solution_step_id = :s"), {"s": step_id}).mappings().one()
    return {"gap_diagnosis_id": diag["gap_diagnosis_id"] if diag else None, "knowledge_gap_id": None,
            "skill_id": s["skill_node_id"], "subconcept_id": s["subconcept_node_id"], "label": s["label"]}


def _candidates(conn: Connection, student_id: str, origin_problem_id: str, skill_id: str | None,
                subconcept_id: str | None) -> list[dict]:
    """Approved, visible, non-proof items for the skill (or its subconcept), never from the origin problem
    and not already passed by this student in an earlier plan."""
    if not skill_id and not subconcept_id:
        return []
    if not subconcept_id and skill_id:
        subconcept_id = conn.execute(text(
            "SELECT subconcept_node_id FROM pedagogy.solution_step WHERE skill_node_id = :sk "
            "AND subconcept_node_id IS NOT NULL LIMIT 1"), {"sk": skill_id}).scalar()
    rows = conn.execute(text(
        "SELECT li.learning_item_id::text, li.transformation_type, li.transformed_form, li.source_problem_id::text, "
        "       (li.target_skill_node_id IS NOT DISTINCT FROM :sk AND :sk IS NOT NULL) AS skill_match, "
        "       CASE WHEN ce.subconcept_node_id IS NOT NULL AND ce.subconcept_node_id = oe.subconcept_node_id THEN 2 "
        "            WHEN ce.concept_node_id IS NOT NULL AND ce.concept_node_id = oe.concept_node_id THEN 1 "
        "            ELSE 0 END AS topic_closeness "
        "  FROM pedagogy.learning_item li "
        "  LEFT JOIN pedagogy.problem_enrichment ce ON ce.problem_id = li.source_problem_id "
        "  LEFT JOIN pedagogy.problem_enrichment oe ON oe.problem_id = CAST(:p AS uuid) "
        " WHERE li.review_status = 'APPROVED' AND li.student_visible AND li.no_proof "
        "   AND li.source_problem_id IS DISTINCT FROM CAST(:p AS uuid) "
        "   AND length(coalesce(li.answer_or_solution_seed, li.correct_answer, '')) >= 25 "
        "   AND coalesce(li.answer_or_solution_seed, '') !~* :stub AND coalesce(li.correct_answer, '') !~* :stub "
        "   AND (li.target_skill_node_id = :sk "
        "        OR (li.target_subconcept_node_id = :sc AND li.target_skill_node_id IS NULL)) "
        "   AND NOT EXISTS (SELECT 1 FROM pedagogy.recovery_plan_item ri "
        "                     JOIN pedagogy.recovery_plan rp USING (recovery_plan_id) "
        "                    WHERE rp.student_id = CAST(:stu AS uuid) AND ri.learning_item_id = li.learning_item_id "
        "                      AND ri.status IN ('PASSED', 'PRESENTED', 'PENDING', 'FAILED'))"),
        {"sk": skill_id, "sc": subconcept_id, "p": origin_problem_id, "stu": student_id,
         "stub": CROSS_REFERENCE_STUB_RE}).mappings()
    out = [dict(r) for r in rows]
    out.sort(key=lambda c: (not c["skill_match"], -(c.get("topic_closeness") or 0),
                            _variety(student_id, c["learning_item_id"])))
    return out[:CANDIDATE_LIMIT]


def _worked_example(conn: Connection, student_id: str, origin_problem_id: str, skill_id: str | None) -> str | None:
    """A same-skill step from another problem the student has not attempted (shown with its text)."""
    if not skill_id:
        return None
    return conn.execute(text(
        "SELECT s.solution_step_id FROM pedagogy.solution_step s "
        "  LEFT JOIN pedagogy.problem_enrichment ce ON ce.problem_id = s.problem_id "
        "  LEFT JOIN pedagogy.problem_enrichment oe ON oe.problem_id = CAST(:p AS uuid) "
        " WHERE s.skill_node_id = :sk AND s.problem_id <> CAST(:p AS uuid) AND s.publication_status = 'PUBLISHED' "
        "   AND length(coalesce(s.step_text, '')) BETWEEN 30 AND 600 "
        "   AND s.step_text !~* :stub "
        "   AND NOT EXISTS (SELECT 1 FROM learner.solve_attempt a WHERE a.student_id = CAST(:stu AS uuid) "
        "                    AND a.problem_id = s.problem_id) "
        # Prefer topically close examples so a chapter-3 learner isn't shown a chapter-28 inversion step.
        " ORDER BY (ce.subconcept_node_id IS NOT NULL AND ce.subconcept_node_id = oe.subconcept_node_id) DESC, "
        "          (ce.concept_node_id IS NOT NULL AND ce.concept_node_id = oe.concept_node_id) DESC, "
        "          s.is_checkpoint DESC, md5(:stu || s.solution_step_id) LIMIT 1"),
        {"sk": skill_id, "p": origin_problem_id, "stu": student_id, "stub": CROSS_REFERENCE_STUB_RE}).scalar()


def _plan_row(conn: Connection, plan_id: str, *, lock: bool = False) -> dict:
    row = conn.execute(text(
        "SELECT recovery_plan_id::text, student_id::text, solve_attempt_id::text, origin_problem_id::text, "
        "       origin_step_id, gap_diagnosis_id::text, knowledge_gap_id::text, parent_recovery_plan_id::text, "
        "       trigger, target_skill_id, target_subconcept_id, target_label, status, current_item_ordinal, "
        "       mastery_policy, outcome, planner_version, created_at, updated_at, ended_at "
        "  FROM pedagogy.recovery_plan WHERE recovery_plan_id = CAST(:r AS uuid)" + (" FOR UPDATE" if lock else "")),
        {"r": plan_id}).mappings().first()
    if row is None:
        raise NotFound("recovery plan not found")
    return dict(row)


def _items(conn: Connection, plan_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(text(
        "SELECT ri.recovery_plan_item_id::text, ri.ordinal, ri.stage, ri.item_kind, ri.learning_item_id::text, "
        "       ri.worked_step_id, ri.is_transfer, ri.required, ri.status, ri.tries, ri.independent_success, "
        "       ri.last_response, ri.last_result, ri.added_reason, ri.presented_at, ri.completed_at, "
        "       li.transformation_type, li.transformed_form, li.source_problem_id::text AS source_problem_id "
        "  FROM pedagogy.recovery_plan_item ri LEFT JOIN pedagogy.learning_item li USING (learning_item_id) "
        " WHERE ri.recovery_plan_id = CAST(:r AS uuid) ORDER BY ri.ordinal"), {"r": plan_id}).mappings()]


# ---------------------------------------------------------------- student-safe presentation

# Import-provenance notes stored as taxonomy descriptions (e.g. "Skill inferred from ordered
# solution steps.") describe how a node was derived, not the skill; never show them to students.
_PROVENANCE_DESCRIPTION_RE = re.compile(r"^\s*(skill|concept|technique|node)?\s*(inferred|derived|mapped|generated)\b", re.I)


def _student_description(description: str | None) -> str | None:
    if not description or _PROVENANCE_DESCRIPTION_RE.search(description):
        return None
    return description


def _present_content(conn: Connection, item: dict, reveal: bool) -> dict:
    if item["item_kind"] == "THEORY":
        r = conn.execute(text(
            "SELECT s.step_text, s.skill_name, t.description, p.canonical_code, p.statement_text "
            "  FROM pedagogy.solution_step s JOIN core.problem p ON p.problem_id = s.problem_id "
            "  LEFT JOIN pedagogy.taxonomy_node t ON t.taxonomy_node_id = s.skill_node_id "
            " WHERE s.solution_step_id = :s"), {"s": item["worked_step_id"]}).mappings().one()
        return {"title": f"Worked example: {r['skill_name'] or 'this skill'}", "skill_description": _student_description(r["description"]),
                "example_problem_code": r["canonical_code"], "example_problem_statement": r["statement_text"],
                "example_step_text": r["step_text"]}
    if item["item_kind"] == "RETURN":
        return {"title": "Now return to the original problem",
                "message": "Use what you just practised on the step where you were stuck."}
    r = conn.execute(text(
        "SELECT li.question_text, li.choices, li.correct_answer, li.answer_or_solution_seed, li.transformed_form, "
        "       li.transformation_type, li.requires_source_problem, li.solution_part_label, "
        "       p.canonical_code, p.statement_text "
        "  FROM pedagogy.learning_item li LEFT JOIN core.problem p ON p.problem_id = li.source_problem_id "
        " WHERE li.learning_item_id = :i"), {"i": item["learning_item_id"]}).mappings().one()
    content = {"title": TYPE_LABELS.get(r["transformation_type"], "Practice"), "form": r["transformed_form"],
               "question_text": r["question_text"], "choices": r["choices"] if r["transformed_form"] == "MCQ" else None,
               "source_problem_code": r["canonical_code"], "source_part_label": r["solution_part_label"],
               "source_problem_statement": r["statement_text"]}  # items refer to "source Problem X"
    if reveal:  # only after the item is finished
        content["answer"] = r["correct_answer"] if r["transformed_form"] == "MCQ" else r["answer_or_solution_seed"]
    return content


def student_item(conn: Connection, item: dict, *, current: bool) -> dict:
    finished = item["status"] in ("PASSED", "FAILED", "SKIPPED")
    out = {k: item[k] for k in ("recovery_plan_item_id", "ordinal", "stage", "item_kind", "is_transfer", "status",
                                "tries", "independent_success", "added_reason")}
    out["stage_label"] = STAGE_LABELS[item["stage"]]
    out["type_label"] = TYPE_LABELS.get(item.get("transformation_type") or "", None)
    result = item.get("last_result") or {}
    out["last_result"] = {k: result[k] for k in ("result", "verdict", "feedback") if k in result} or None
    out["last_response"] = item.get("last_response")
    if current or finished:
        out["content"] = _present_content(conn, item, reveal=finished and item["item_kind"] == "LEARNING_ITEM")
    return out


def plan_view(conn: Connection, plan: dict) -> dict:
    items = _items(conn, plan["recovery_plan_id"])
    progress = mastery_status(items, plan["mastery_policy"] or DEFAULT_POLICY)
    origin = conn.execute(text(
        "SELECT p.canonical_code, sp.part_label, s.step_index_in_part, s.global_step_index "
        "  FROM pedagogy.solution_step s JOIN pedagogy.solution_part sp USING (solution_part_id) "
        "  JOIN core.problem p ON p.problem_id = s.problem_id WHERE s.solution_step_id = :s"),
        {"s": plan["origin_step_id"]}).mappings().one()
    parent_label = None
    if plan["parent_recovery_plan_id"]:
        parent_label = conn.execute(text(
            "SELECT target_label FROM pedagogy.recovery_plan WHERE recovery_plan_id = CAST(:p AS uuid)"),
            {"p": plan["parent_recovery_plan_id"]}).scalar()
    return {
        "recovery_plan_id": plan["recovery_plan_id"], "solve_attempt_id": plan["solve_attempt_id"],
        "status": plan["status"], "trigger": plan["trigger"], "target_label": plan["target_label"],
        "parent_recovery_plan_id": plan["parent_recovery_plan_id"], "parent_target_label": parent_label,
        "current_item_ordinal": plan["current_item_ordinal"], "created_at": plan["created_at"],
        "ended_at": plan["ended_at"], "outcome": plan["outcome"], "mastery": progress,
        "origin": {"problem_code": origin["canonical_code"], "solution_step_id": plan["origin_step_id"],
                   "part_label": origin["part_label"], "step_index_in_part": origin["step_index_in_part"],
                   "global_step_index": origin["global_step_index"]},
        "can_return": plan["status"] in ("COMPLETED", "EXHAUSTED"),
        "items": [student_item(conn, i, current=i["ordinal"] == plan["current_item_ordinal"]) for i in items],
    }


# ---------------------------------------------------------------- persistence helpers

def _insert_items(conn: Connection, plan_id: str, specs: list[dict], reason: str = "PLANNED") -> None:
    for s in specs:
        conn.execute(text(
            "INSERT INTO pedagogy.recovery_plan_item (recovery_plan_id, ordinal, stage, item_kind, learning_item_id, "
            "  worked_step_id, is_transfer, required, added_reason) "
            "VALUES (CAST(:r AS uuid), :o, :st, :k, :li, :ws, :tr, :req, :why)"),
            {"r": plan_id, "o": s["ordinal"], "st": s["stage"], "k": s["item_kind"], "li": s["learning_item_id"],
             "ws": s["worked_step_id"], "tr": s["is_transfer"], "req": s["required"], "why": reason})


def _present_item(conn: Connection, plan: dict, ordinal: int, actor: str = "SYSTEM") -> None:
    item = conn.execute(text(
        "UPDATE pedagogy.recovery_plan_item SET status = 'PRESENTED', presented_at = coalesce(presented_at, now()) "
        "WHERE recovery_plan_id = CAST(:r AS uuid) AND ordinal = :o "
        "RETURNING recovery_plan_item_id::text, stage, item_kind, learning_item_id::text"),
        {"r": plan["recovery_plan_id"], "o": ordinal}).mappings().one()
    conn.execute(text(
        "UPDATE pedagogy.recovery_plan SET current_item_ordinal = :o, updated_at = now() "
        "WHERE recovery_plan_id = CAST(:r AS uuid)"), {"r": plan["recovery_plan_id"], "o": ordinal})
    plan["current_item_ordinal"] = ordinal
    _event(conn, plan["student_id"], plan["solve_attempt_id"], "RECOVERY_ITEM_PRESENTED", actor,
           step_id=plan["origin_step_id"],
           payload={"recovery_plan_id": plan["recovery_plan_id"], "recovery_plan_item_id": item["recovery_plan_item_id"],
                    "ordinal": ordinal, "stage": item["stage"], "learning_item_id": item["learning_item_id"]})


def _add_item_before_return(conn: Connection, plan: dict, spec: dict, reason: str) -> int:
    """Insert an adaptive item right after the current one, shifting later items (including RETURN)."""
    cur = plan["current_item_ordinal"]
    # two-phase shift through a high offset keeps (plan, ordinal) unique and ordinal >= 1
    conn.execute(text(
        "UPDATE pedagogy.recovery_plan_item SET ordinal = ordinal + 100001 "
        "WHERE recovery_plan_id = CAST(:r AS uuid) AND ordinal > :c"), {"r": plan["recovery_plan_id"], "c": cur})
    conn.execute(text(
        "UPDATE pedagogy.recovery_plan_item SET ordinal = ordinal - 100000 "
        "WHERE recovery_plan_id = CAST(:r AS uuid) AND ordinal > 100000"), {"r": plan["recovery_plan_id"]})
    _insert_items(conn, plan["recovery_plan_id"], [{**spec, "ordinal": cur + 1}], reason)
    return cur + 1


def _added_count(conn: Connection, plan_id: str) -> int:
    return conn.execute(text(
        "SELECT count(*) FROM pedagogy.recovery_plan_item WHERE recovery_plan_id = CAST(:r AS uuid) "
        "AND added_reason <> 'PLANNED'"), {"r": plan_id}).scalar_one()


def _create_plan_row(conn: Connection, attempt: dict, step_id: str, target: dict, trigger: str,
                     parent_id: str | None, include_return: bool) -> dict:
    student_id = str(attempt["student_id"])
    candidates = _candidates(conn, student_id, str(attempt["problem_id"]), target["skill_id"], target["subconcept_id"])
    worked = _worked_example(conn, student_id, str(attempt["problem_id"]), target["skill_id"])
    specs = build_plan(candidates, worked, include_return=include_return)
    if not any(s["item_kind"] == "LEARNING_ITEM" for s in specs) and not worked:
        raise NoRecoveryMaterial(f"no approved practice is available for “{target['label'] or 'this skill'}” yet")
    plan_id = conn.execute(text(
        "INSERT INTO pedagogy.recovery_plan (student_id, solve_attempt_id, origin_problem_id, origin_step_id, "
        "  gap_diagnosis_id, knowledge_gap_id, parent_recovery_plan_id, trigger, target_skill_id, "
        "  target_subconcept_id, target_label, mastery_policy, planner_version) "
        "VALUES (:stu, :a, :p, :s, CAST(:d AS uuid), CAST(:g AS uuid), CAST(:par AS uuid), :t, :sk, :sc, :lbl, "
        "  CAST(:pol AS jsonb), :v) RETURNING recovery_plan_id::text"),
        {"stu": student_id, "a": str(attempt["solve_attempt_id"]), "p": str(attempt["problem_id"]), "s": step_id,
         "d": target.get("gap_diagnosis_id"), "g": target.get("knowledge_gap_id"), "par": parent_id, "t": trigger,
         "sk": target["skill_id"], "sc": target["subconcept_id"], "lbl": target["label"],
         "pol": json.dumps(DEFAULT_POLICY), "v": PLANNER_VERSION}).scalar_one()
    _insert_items(conn, plan_id, specs)
    plan = _plan_row(conn, plan_id)
    _event(conn, student_id, attempt["solve_attempt_id"], "RECOVERY_PLAN_CREATED", "SYSTEM", step_id=step_id,
           payload={"recovery_plan_id": plan_id, "trigger": trigger, "target_skill_id": target["skill_id"],
                    "target_label": target["label"], "items": len(specs), "parent_recovery_plan_id": parent_id,
                    "gap_diagnosis_id": target.get("gap_diagnosis_id")})
    _outbox(conn, "RECOVERY_PLAN_CREATED", "recovery_plan", plan_id,
            {"student_id": student_id, "solve_attempt_id": str(attempt["solve_attempt_id"]), "origin_step_id": step_id})
    _present_item(conn, plan, 1)
    return plan


def _set_runtime_plan(conn: Connection, attempt_id: str, plan_id: str | None, mode: str) -> int:
    if plan_id:
        conn.execute(text("UPDATE learner.solve_attempt SET recovery_plan_id = CAST(:r AS uuid) "
                          "WHERE solve_attempt_id = CAST(:a AS uuid)"), {"r": plan_id, "a": attempt_id})
    return conn.execute(text(
        "UPDATE tutor.runtime_state SET current_recovery_plan_id = CAST(:r AS uuid), current_mode = :m, "
        "  state_version = state_version + 1, updated_at = now() WHERE solve_attempt_id = CAST(:a AS uuid) "
        "RETURNING state_version"), {"r": plan_id, "m": mode, "a": attempt_id}).scalar_one()


# ---------------------------------------------------------------- operations

def create_plan(conn: Connection, student_id: UUID | str, attempt_id: UUID | str, state_version: int, *,
                trigger: str = "STUDENT_REQUEST", gap_diagnosis_id: str | None = None,
                idempotency_key: str | None = None) -> dict:
    """Start a detour from the attempt's current step (persisted before the first item is shown).
    If a detour is already running for the attempt, it is returned instead (``resumed``)."""
    if trigger not in ("DIAGNOSIS", "STUDENT_REQUEST", "TUTOR"):
        raise ValueError(trigger)
    body = {"attempt_id": str(attempt_id), "state_version": state_version, "trigger": trigger,
            "gap_diagnosis_id": gap_diagnosis_id}
    attempt = _lock_attempt(conn, attempt_id, student_id)
    replay = _replay(conn, attempt["student_id"], idempotency_key, "recovery_create", body)
    if replay:
        return replay
    if attempt["current_mode"] == "RECOVERY":
        current = conn.execute(text(
            "SELECT current_recovery_plan_id::text FROM tutor.runtime_state WHERE solve_attempt_id = CAST(:a AS uuid)"),
            {"a": str(attempt_id)}).scalar()
        if current:
            return {"recovery_plan": plan_view(conn, _plan_row(conn, current)), "resumed": True,
                    "state_version": attempt["state_version"]}
    _check_version(attempt, state_version)
    if attempt["status"] != "IN_PROGRESS" or not attempt["current_solution_step_id"]:
        raise InvalidTransition(f"attempt is {attempt['status']}")
    step_id = attempt["current_solution_step_id"]
    if trigger == "DIAGNOSIS" and gap_diagnosis_id is None:
        raise InvalidTransition("a diagnosis-triggered detour needs gap_diagnosis_id")
    target = _target_for(conn, attempt, step_id, gap_diagnosis_id)
    plan = _create_plan_row(conn, attempt, step_id, target, trigger, None, include_return=True)
    conn.execute(text(
        "UPDATE learner.attempt_step_state SET state = 'DETOURED', last_updated_at = now() "
        "WHERE solve_attempt_id = CAST(:a AS uuid) AND solution_step_id = :s"), {"a": str(attempt_id), "s": step_id})
    version = _set_runtime_plan(conn, str(attempt_id), plan["recovery_plan_id"], "RECOVERY")
    response = {"recovery_plan": plan_view(conn, _plan_row(conn, plan["recovery_plan_id"])), "resumed": False,
                "state_version": version}
    return _remember(conn, attempt["student_id"], idempotency_key, "recovery_create", body, response)


def _owned_plan(conn: Connection, plan_id: UUID | str, student_id: UUID | str | None) -> dict:
    plan = _plan_row(conn, str(plan_id))
    if student_id is not None and plan["student_id"] != str(student_id):
        raise NotFound("recovery plan not found")
    return plan


def get_plan(conn: Connection, student_id: UUID | str | None, plan_id: UUID | str) -> dict:
    return plan_view(conn, _owned_plan(conn, plan_id, student_id))


def next_item(conn: Connection, student_id: UUID | str | None, plan_id: UUID | str) -> dict:
    view = get_plan(conn, student_id, plan_id)
    current = next((i for i in view["items"] if i["ordinal"] == view["current_item_ordinal"]), None)
    return {"recovery_plan_id": view["recovery_plan_id"], "status": view["status"], "item": current,
            "mastery": view["mastery"], "can_return": view["can_return"]}


def prepare_item_response(conn: Connection, student_id: UUID | str, plan_id: UUID | str, item_id: str,
                          response: dict, state_version: int, idempotency_key: str | None) -> dict:
    """Read-only validation before grading (so a replay or stale request never triggers a model call).
    Returns ``{"replay": ...}`` or the grading context."""
    plan = _owned_plan(conn, plan_id, student_id)
    body = {"plan_id": str(plan_id), "item_id": item_id, "response": response, "state_version": state_version}
    replay = _replay(conn, plan["student_id"], idempotency_key, "recovery_item_response", body)
    if replay:
        return {"replay": replay}
    item = next((i for i in _items(conn, plan["recovery_plan_id"]) if i["recovery_plan_item_id"] == item_id), None)
    if item is None:
        raise NotFound("recovery item not found")
    if plan["status"] != "ACTIVE" or item["ordinal"] != plan["current_item_ordinal"] or item["status"] != "PRESENTED":
        raise InvalidTransition("only the current item of an active plan accepts a response")
    if item["item_kind"] == "RETURN":
        raise InvalidTransition("use /resume to return to the original problem")
    ctx = {"item": item, "plan": plan}
    if item["item_kind"] == "LEARNING_ITEM":
        ctx["learning_item"] = dict(conn.execute(text(
            "SELECT li.question_text, li.choices, li.correct_answer, li.answer_or_solution_seed, li.transformed_form, "
            "       li.solution_part_label, p.statement_text "
            "  FROM pedagogy.learning_item li LEFT JOIN core.problem p ON p.problem_id = li.source_problem_id "
            " WHERE li.learning_item_id = :i"), {"i": item["learning_item_id"]}).mappings().one())
    return ctx


def grade_item(ctx: dict, response: dict,
               evaluator: Callable[[step_tutor.StepContext], dict] = step_tutor.openai_evaluator) -> dict:
    """Grade outside any lock: THEORY acknowledges, MCQ is deterministic, SUBPROBLEM uses the step evaluator."""
    item = ctx["item"]
    if item["item_kind"] == "THEORY":
        return {"result": "SUCCESS", "verdict": "ACKNOWLEDGED", "feedback": "", "grader": "none"}
    li = ctx["learning_item"]
    if li["transformed_form"] == "MCQ":
        idx = response.get("choice_index")
        return grade_mcq(li["choices"] or [], li["correct_answer"], idx if isinstance(idx, int) else None)
    answer = (response.get("response_text") or "").strip()
    if not answer:
        raise InvalidTransition("response_text is required for this item")
    sctx = step_tutor.StepContext(
        problem_statement=li["statement_text"] or "", part_label=li["solution_part_label"] or "",
        step_type=None, tutor_role="RECOVERY_PRACTICE", skill_name=ctx["plan"]["target_label"],
        previous_steps=[li["question_text"]], canonical_step=li["answer_or_solution_seed"] or "",
        student_response=answer)
    verdict = step_tutor.sanitize_feedback(evaluator(sctx), sctx)
    verdict["result"] = step_tutor.outcome_from_verdict(verdict)
    verdict["grader"] = verdict.get("model", "model")
    return verdict


def _alternate_spec(conn: Connection, plan: dict, stage: str, *, transfer: bool = False) -> dict | None:
    items = _items(conn, plan["recovery_plan_id"])
    used = {i["learning_item_id"] for i in items if i["learning_item_id"]}
    cands = _candidates(conn, plan["student_id"], plan["origin_problem_id"], plan["target_skill_id"],
                        plan["target_subconcept_id"])
    avoid = {i["source_problem_id"] for i in items if i.get("source_problem_id")} if transfer else None
    c = _pick(cands, STAGE_TYPES.get(stage, STAGE_TYPES["ISOLATED_EXECUTION"]), used, avoid_sources=avoid) \
        or (None if transfer else _pick(cands, sum(STAGE_TYPES.values(), ()), used))
    if c is None:
        return None
    return {"stage": stage, "item_kind": "LEARNING_ITEM", "learning_item_id": c["learning_item_id"],
            "worked_step_id": None, "is_transfer": transfer, "required": True}


def _branch_target(conn: Connection, plan: dict) -> dict | None:
    """Strongest prerequisite hypothesis (different skill) of the plan's diagnosis, for a child plan."""
    if not plan["gap_diagnosis_id"]:
        return None
    depth = conn.execute(text(
        "WITH RECURSIVE up AS (SELECT recovery_plan_id, parent_recovery_plan_id, 0 AS d FROM pedagogy.recovery_plan "
        "  WHERE recovery_plan_id = CAST(:r AS uuid) UNION ALL SELECT p.recovery_plan_id, p.parent_recovery_plan_id, "
        "  up.d + 1 FROM pedagogy.recovery_plan p JOIN up ON p.recovery_plan_id = up.parent_recovery_plan_id) "
        "SELECT max(d) FROM up"), {"r": plan["recovery_plan_id"]}).scalar_one()
    if depth >= MAX_BRANCH_DEPTH:
        return None
    row = conn.execute(text(
        "SELECT knowledge_gap_id::text, target_skill_id, target_subconcept_id, target_label "
        "  FROM pedagogy.knowledge_gap WHERE gap_diagnosis_id = CAST(:d AS uuid) AND target_skill_id IS NOT NULL "
        "   AND target_skill_id IS DISTINCT FROM :sk AND failure_location = 'PREREQUISITE' "
        " ORDER BY confidence DESC, rank LIMIT 1"),
        {"d": plan["gap_diagnosis_id"], "sk": plan["target_skill_id"]}).mappings().first()
    if row is None:
        return None
    return {"gap_diagnosis_id": plan["gap_diagnosis_id"], "knowledge_gap_id": row["knowledge_gap_id"],
            "skill_id": row["target_skill_id"], "subconcept_id": row["target_subconcept_id"],
            "label": row["target_label"]}


def _end_plan(conn: Connection, plan: dict, status: str, mastery: dict, actor: str) -> None:
    conn.execute(text(
        "UPDATE pedagogy.recovery_plan SET status = :st, outcome = CAST(:o AS jsonb), ended_at = now(), "
        "  updated_at = now() WHERE recovery_plan_id = CAST(:r AS uuid)"),
        {"st": status, "o": json.dumps({"mastery": mastery}), "r": plan["recovery_plan_id"]})
    plan["status"] = status
    event = {"COMPLETED": "RECOVERY_PLAN_COMPLETED", "EXHAUSTED": "RECOVERY_PLAN_EXHAUSTED",
             "ABORTED": "RECOVERY_PLAN_ABORTED"}[status]
    _event(conn, plan["student_id"], plan["solve_attempt_id"], event, actor, step_id=plan["origin_step_id"],
           payload={"recovery_plan_id": plan["recovery_plan_id"], "mastery": mastery})
    _outbox(conn, event, "recovery_plan", plan["recovery_plan_id"],
            {"student_id": plan["student_id"], "status": status, "target_skill_id": plan["target_skill_id"]})
    if plan["knowledge_gap_id"] and status in ("COMPLETED", "EXHAUSTED"):
        _update_gap(conn, plan, "RESOLVED" if status == "COMPLETED" else "CONFIRMED", actor)


def _update_gap(conn: Connection, plan: dict, new: str, actor: str) -> None:
    allowed = ("UNRESOLVED", "CONFIRMED") if new == "RESOLVED" else ("UNRESOLVED",)
    row = conn.execute(text(
        "UPDATE pedagogy.knowledge_gap SET status = :st, status_reason = :why, status_changed_at = now(), "
        "  resolved_at = CASE WHEN :st = 'RESOLVED' THEN now() END "
        "WHERE knowledge_gap_id = CAST(:g AS uuid) AND status = ANY(:allowed) "
        "RETURNING knowledge_gap_id::text, solution_step_id"),
        {"st": new, "why": f"recovery plan {plan['recovery_plan_id']} {plan['status']}",
         "g": plan["knowledge_gap_id"], "allowed": list(allowed)}).mappings().first()
    if row:
        _event(conn, plan["student_id"], plan["solve_attempt_id"], f"GAP_HYPOTHESIS_{new}", actor,
               step_id=row["solution_step_id"],
               payload={"knowledge_gap_id": row["knowledge_gap_id"], "to": new,
                        "recovery_plan_id": plan["recovery_plan_id"]})


def _advance(conn: Connection, plan: dict, actor: str) -> dict:
    """Present the next pending item; at RETURN (or the end of a branch) apply the mastery policy."""
    items = _items(conn, plan["recovery_plan_id"])
    nxt = next((i for i in items if i["status"] == "PENDING" and i["ordinal"] > plan["current_item_ordinal"]), None)
    if nxt is not None and nxt["item_kind"] != "RETURN":
        _present_item(conn, plan, nxt["ordinal"], actor)
        return {"transition": "NEXT_ITEM"}
    mastery = mastery_status(items, plan["mastery_policy"] or DEFAULT_POLICY)
    if not mastery["met"] and _added_count(conn, plan["recovery_plan_id"]) < MAX_ADDED_ITEMS:
        spec = (_alternate_spec(conn, plan, "TRANSFER", transfer=True) if not mastery["transfer_passed"] else None) \
            or _alternate_spec(conn, plan, "ISOLATED_EXECUTION")
        if spec:
            ordinal = _add_item_before_return(conn, plan, spec, "MASTERY_NOT_YET_MET")
            _present_item(conn, plan, ordinal, actor)
            return {"transition": "EXTRA_ITEM"}
    _end_plan(conn, plan, "COMPLETED" if mastery["met"] else "EXHAUSTED", mastery, actor)
    if plan["parent_recovery_plan_id"]:  # branch finished: wake the parent plan
        parent = _plan_row(conn, plan["parent_recovery_plan_id"], lock=True)
        conn.execute(text("UPDATE pedagogy.recovery_plan SET status = 'ACTIVE', updated_at = now() "
                          "WHERE recovery_plan_id = CAST(:r AS uuid)"), {"r": parent["recovery_plan_id"]})
        parent["status"] = "ACTIVE"
        conn.execute(text("UPDATE tutor.runtime_state SET current_recovery_plan_id = CAST(:r AS uuid) "
                          "WHERE solve_attempt_id = CAST(:a AS uuid)"),
                     {"r": parent["recovery_plan_id"], "a": plan["solve_attempt_id"]})
        _advance(conn, parent, actor)
        return {"transition": "BRANCH_FINISHED", "active_recovery_plan_id": parent["recovery_plan_id"]}
    if nxt is not None:  # the RETURN item
        conn.execute(text(
            "UPDATE pedagogy.recovery_plan_item SET status = 'PRESENTED', presented_at = now() "
            "WHERE recovery_plan_id = CAST(:r AS uuid) AND ordinal = :o"),
            {"r": plan["recovery_plan_id"], "o": nxt["ordinal"]})
        conn.execute(text("UPDATE pedagogy.recovery_plan SET current_item_ordinal = :o "
                          "WHERE recovery_plan_id = CAST(:r AS uuid)"),
                     {"r": plan["recovery_plan_id"], "o": nxt["ordinal"]})
    return {"transition": "PLAN_" + plan["status"]}


def apply_item_response(conn: Connection, student_id: UUID | str, plan_id: UUID | str, item_id: str,
                        response: dict, grade: dict, state_version: int, idempotency_key: str | None = None,
                        actor: str = "TUTOR") -> dict:
    """Record a graded response for the current item and adapt the plan (one transaction, attempt locked)."""
    plan0 = _owned_plan(conn, plan_id, student_id)
    attempt = _lock_attempt(conn, plan0["solve_attempt_id"], student_id)
    body = {"plan_id": str(plan_id), "item_id": item_id, "response": response, "state_version": state_version}
    replay = _replay(conn, attempt["student_id"], idempotency_key, "recovery_item_response", body)
    if replay:
        return replay
    _check_version(attempt, state_version)
    plan = _plan_row(conn, str(plan_id), lock=True)
    item = next((i for i in _items(conn, plan["recovery_plan_id"]) if i["recovery_plan_item_id"] == item_id), None)
    if item is None or plan["status"] != "ACTIVE" or item["ordinal"] != plan["current_item_ordinal"] \
            or item["status"] != "PRESENTED" or item["item_kind"] == "RETURN":
        raise InvalidTransition("only the current item of an active plan accepts a response")
    tries = item["tries"] + 1
    decision = adapt(item["stage"], grade["result"], tries)
    final = decision != "RETRY"
    status = ("PASSED" if grade["result"] == "SUCCESS" else "FAILED") if final else "PRESENTED"
    independent = (grade["result"] == "SUCCESS" and tries == 1) if final else None
    student_result = {k: grade[k] for k in ("result", "verdict", "feedback") if k in grade}
    conn.execute(text(
        "UPDATE pedagogy.recovery_plan_item SET tries = :t, status = :st, independent_success = :ind, "
        "  last_response = CAST(:resp AS jsonb), last_result = CAST(:res AS jsonb), "
        "  completed_at = CASE WHEN :final THEN now() END WHERE recovery_plan_item_id = CAST(:i AS uuid)"),
        {"t": tries, "st": status, "ind": independent, "resp": json.dumps(response),
         "res": json.dumps({**student_result, "teacher": {k: grade.get(k) for k in
                                                          ("evidence", "failure_mode", "confidence", "grader")}}),
         "final": final, "i": item_id})
    payload = {"recovery_plan_id": plan["recovery_plan_id"], "recovery_plan_item_id": item_id,
               "ordinal": item["ordinal"], "stage": item["stage"], "learning_item_id": item["learning_item_id"]}
    _event(conn, plan["student_id"], plan["solve_attempt_id"], "RECOVERY_ITEM_SUBMITTED", "STUDENT",
           step_id=plan["origin_step_id"], payload={**payload, "response": response}, key=idempotency_key)
    _event(conn, plan["student_id"], plan["solve_attempt_id"], "RECOVERY_ITEM_EVALUATED", actor,
           step_id=plan["origin_step_id"],
           payload={**payload, "result": grade["result"], "tries": tries, "decision": decision,
                    "grader": grade.get("grader")})
    transition = {"transition": "RETRY"}
    if decision == "CONFIRM" and _added_count(conn, plan["recovery_plan_id"]) < MAX_ADDED_ITEMS:
        spec = _alternate_spec(conn, plan, item["stage"], transfer=item["is_transfer"])
        if spec:
            _add_item_before_return(conn, plan, spec, "CONFIRMATION_AFTER_HELP")
    elif decision in ("ALTERNATE", "BRANCH"):
        target = _branch_target(conn, plan) if decision == "BRANCH" else None
        if target:
            try:
                with conn.begin_nested():
                    conn.execute(text("UPDATE pedagogy.recovery_plan SET status = 'SUSPENDED', updated_at = now() "
                                      "WHERE recovery_plan_id = CAST(:r AS uuid)"), {"r": plan["recovery_plan_id"]})
                    origin = {"solve_attempt_id": plan["solve_attempt_id"], "student_id": plan["student_id"],
                              "problem_id": plan["origin_problem_id"]}
                    child = _create_plan_row(conn, origin, plan["origin_step_id"], target, "BRANCH",
                                             plan["recovery_plan_id"], include_return=False)
            except NoRecoveryMaterial:
                target = None
            else:
                _event(conn, plan["student_id"], plan["solve_attempt_id"], "RECOVERY_PLAN_BRANCHED", actor,
                       step_id=plan["origin_step_id"],
                       payload={"recovery_plan_id": plan["recovery_plan_id"],
                                "child_recovery_plan_id": child["recovery_plan_id"], "target_label": target["label"]})
                conn.execute(text("UPDATE tutor.runtime_state SET current_recovery_plan_id = CAST(:r AS uuid) "
                                  "WHERE solve_attempt_id = CAST(:a AS uuid)"),
                             {"r": child["recovery_plan_id"], "a": plan["solve_attempt_id"]})
                transition = {"transition": "BRANCHED", "active_recovery_plan_id": child["recovery_plan_id"]}
        if not target and _added_count(conn, plan["recovery_plan_id"]) < MAX_ADDED_ITEMS:
            spec = _alternate_spec(conn, plan, item["stage"], transfer=item["is_transfer"])
            if spec:
                _add_item_before_return(conn, plan, spec, "ALTERNATE_AFTER_FAILURE")
    if final and transition["transition"] != "BRANCHED":
        transition = _advance(conn, plan, actor)
    version = _bump_version(conn, plan["solve_attempt_id"])
    active_id = conn.execute(text(
        "SELECT current_recovery_plan_id::text FROM tutor.runtime_state WHERE solve_attempt_id = CAST(:a AS uuid)"),
        {"a": plan["solve_attempt_id"]}).scalar() or plan["recovery_plan_id"]
    result = {"result": student_result, "decision": decision, **transition, "state_version": version,
              "recovery_plan": plan_view(conn, _plan_row(conn, active_id))}
    return _remember(conn, attempt["student_id"], idempotency_key, "recovery_item_response", body, result)


def leave_recovery(conn: Connection, student_id: UUID | str | None, plan_id: UUID | str, state_version: int, *,
                   abort: bool = False, idempotency_key: str | None = None, actor: str = "STUDENT") -> dict:
    """Return to the exact origin step. ``abort`` ends unfinished plans (and their branches) as ABORTED;
    otherwise the plan must already be COMPLETED or EXHAUSTED."""
    plan = _owned_plan(conn, plan_id, student_id)
    attempt = _lock_attempt(conn, plan["solve_attempt_id"], student_id)
    op = "recovery_abort" if abort else "recovery_resume"
    body = {"plan_id": str(plan_id), "state_version": state_version}
    replay = _replay(conn, attempt["student_id"], idempotency_key, op, body)
    if replay:
        return replay
    _check_version(attempt, state_version)
    if attempt["current_mode"] != "RECOVERY":
        raise InvalidTransition("the attempt is not in a recovery detour")
    root = plan
    while root["parent_recovery_plan_id"]:
        root = _plan_row(conn, root["parent_recovery_plan_id"])
    family = [r[0] for r in conn.execute(text(
        "WITH RECURSIVE f AS (SELECT recovery_plan_id FROM pedagogy.recovery_plan WHERE recovery_plan_id = CAST(:r AS uuid) "
        "  UNION ALL SELECT p.recovery_plan_id FROM pedagogy.recovery_plan p JOIN f "
        "  ON p.parent_recovery_plan_id = f.recovery_plan_id) SELECT recovery_plan_id::text FROM f"),
        {"r": root["recovery_plan_id"]})]
    open_plans = [p for p in (_plan_row(conn, pid, lock=True) for pid in family) if p["status"] in ("ACTIVE", "SUSPENDED")]
    if open_plans and not abort:
        raise InvalidTransition("finish the detour first, or leave it early with /abort")
    for p in open_plans:
        _end_plan(conn, p, "ABORTED", mastery_status(_items(conn, p["recovery_plan_id"]),
                                                     p["mastery_policy"] or DEFAULT_POLICY), actor)
    conn.execute(text(
        "UPDATE pedagogy.recovery_plan_item SET status = CASE WHEN item_kind = 'RETURN' THEN 'PASSED' ELSE 'SKIPPED' END, "
        "  completed_at = now() WHERE recovery_plan_id = ANY(CAST(:f AS uuid[])) AND status IN ('PENDING', 'PRESENTED')"),
        {"f": family})
    step_id = root["origin_step_id"]
    conn.execute(text(
        "UPDATE learner.attempt_step_state SET state = CASE WHEN attempt_count > 0 THEN 'RETRY_PRESENTED' "
        "  ELSE 'PRESENTED' END, last_updated_at = now() "
        "WHERE solve_attempt_id = CAST(:a AS uuid) AND solution_step_id = :s AND state = 'DETOURED'"),
        {"a": root["solve_attempt_id"], "s": step_id})
    conn.execute(text(
        "UPDATE learner.solve_attempt SET current_solution_step_id = :s, "
        "  current_solution_part_id = (SELECT solution_part_id FROM pedagogy.solution_step WHERE solution_step_id = :s) "
        "WHERE solve_attempt_id = CAST(:a AS uuid)"), {"a": root["solve_attempt_id"], "s": step_id})
    conn.execute(text("UPDATE tutor.runtime_state SET current_step_id = :s WHERE solve_attempt_id = CAST(:a AS uuid)"),
                 {"a": root["solve_attempt_id"], "s": step_id})
    version = _set_runtime_plan(conn, root["solve_attempt_id"], None, "SOLVING")
    _event(conn, root["student_id"], root["solve_attempt_id"], "RETURNED_TO_ORIGINAL_STEP", actor, step_id=step_id,
           payload={"recovery_plan_id": root["recovery_plan_id"], "aborted": bool(open_plans)}, key=idempotency_key)
    _event(conn, root["student_id"], root["solve_attempt_id"], "STEP_PRESENTED", "SYSTEM", step_id=step_id)
    response = {"returned_to_step_id": step_id, "recovery_plan_id": root["recovery_plan_id"],
                "plan_status": _plan_row(conn, root["recovery_plan_id"])["status"], "state_version": version}
    return _remember(conn, attempt["student_id"], idempotency_key, op, body, response)


# ---------------------------------------------------------------- listings

def list_attempt_plans(conn: Connection, student_id: UUID | str | None, attempt_id: UUID | str) -> list[dict]:
    if student_id is not None:
        owner = conn.execute(text("SELECT student_id::text FROM learner.solve_attempt WHERE solve_attempt_id = CAST(:a AS uuid)"),
                             {"a": str(attempt_id)}).scalar()
        if owner is None or owner != str(student_id):
            raise NotFound("attempt not found")
    ids = conn.execute(text(
        "SELECT recovery_plan_id::text FROM pedagogy.recovery_plan WHERE solve_attempt_id = CAST(:a AS uuid) "
        "ORDER BY created_at DESC"), {"a": str(attempt_id)}).scalars()
    return [plan_view(conn, _plan_row(conn, i)) for i in ids]


def admin_plans(conn: Connection, *, student_id: UUID | str | None = None, status: str | None = None,
                limit: int = 100) -> list[dict]:
    """Teacher view of recovery plans with item outcomes and grader evidence."""
    rows = conn.execute(text(
        "SELECT rp.recovery_plan_id::text, rp.student_id::text, sp.email, rp.solve_attempt_id::text, "
        "       p.canonical_code AS problem_code, rp.origin_step_id, rp.trigger, rp.target_skill_id, rp.target_label, "
        "       rp.status, rp.parent_recovery_plan_id::text, rp.outcome, rp.created_at, rp.ended_at, "
        "       count(ri.*) AS items, count(ri.*) FILTER (WHERE ri.status = 'PASSED' AND ri.item_kind = 'LEARNING_ITEM') AS passed, "
        "       count(ri.*) FILTER (WHERE ri.status = 'FAILED') AS failed, "
        "       count(ri.*) FILTER (WHERE ri.added_reason <> 'PLANNED') AS adapted "
        "  FROM pedagogy.recovery_plan rp JOIN learner.student_profile sp USING (student_id) "
        "  JOIN core.problem p ON p.problem_id = rp.origin_problem_id "
        "  LEFT JOIN pedagogy.recovery_plan_item ri USING (recovery_plan_id) "
        " WHERE (CAST(:s AS uuid) IS NULL OR rp.student_id = CAST(:s AS uuid)) AND (CAST(:st AS text) IS NULL OR rp.status = :st) "
        " GROUP BY rp.recovery_plan_id, sp.email, p.canonical_code ORDER BY rp.created_at DESC LIMIT :n"),
        {"s": str(student_id) if student_id else None, "st": status, "n": min(max(limit, 1), 500)}).mappings()
    return [dict(r) for r in rows]


def admin_plan_detail(conn: Connection, plan_id: UUID | str) -> dict:
    plan = _plan_row(conn, str(plan_id))
    view = plan_view(conn, plan)
    view["items_teacher"] = [{k: i[k] for k in ("ordinal", "stage", "item_kind", "learning_item_id", "worked_step_id",
                                                "transformation_type", "status", "tries", "independent_success",
                                                "last_response", "last_result", "added_reason")}
                             for i in _items(conn, plan["recovery_plan_id"])]
    view["student_id"] = plan["student_id"]
    view["knowledge_gap_id"] = plan["knowledge_gap_id"]
    view["gap_diagnosis_id"] = plan["gap_diagnosis_id"]
    return view


def recovery_summary(conn: Connection, attempt_id: str) -> dict | None:
    """Small pointer for the runtime read model."""
    row = conn.execute(text(
        "SELECT r.current_recovery_plan_id::text AS plan_id, rp.target_label, rp.status "
        "  FROM tutor.runtime_state r LEFT JOIN pedagogy.recovery_plan rp ON rp.recovery_plan_id = r.current_recovery_plan_id "
        " WHERE r.solve_attempt_id = CAST(:a AS uuid)"), {"a": attempt_id}).mappings().first()
    if not row or not row["plan_id"]:
        return None
    return {"recovery_plan_id": row["plan_id"], "target_label": row["target_label"], "status": row["status"]}


