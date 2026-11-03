"""Pure recovery-plan logic shared by the PostgreSQL (``step_recovery``) and DynamoDB (``stores.learner.recovery``) backends.

No SQL and no database access: planning (``build_plan``), the mastery policy, adaptation, grading (MCQ deterministic, sub-problems by the
step evaluator), the safe-question filter, and the learner-safe presentation of a plan (``plan_view_of`` / ``student_item``), which takes the
plan, its items and a content callback instead of a connection. ``step_recovery`` re-exports every name.

A recovery plan is a short, persisted detour from the exact step where a student is stuck:

    FOUNDATION (worked example) -> RECOGNITION -> ISOLATED_EXECUTION -> GUIDED_APPLICATION -> TRANSFER (a different source problem)
    -> RETURN_TO_STEP

Adaptation (spec 11 section 6): independent success -> advance; success after a retry -> one same-stage confirmation item; a final failure -> an
alternate same-stage item, or, for a failed recognition (conceptual) item, a child plan on the strongest prerequisite hypothesis. A plan is
COMPLETED only when the mastery policy is met; when items run out first it ends EXHAUSTED. Either way the student returns to the exact origin
step (RETURNED_TO_ORIGINAL_STEP); a plan never sets mastery directly.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable

from mathbank_rest import step_tutor
from mathbank_rest.step_logic import InvalidTransition, RuntimeError_

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
OPEN_PLAN_STATUSES = ("ACTIVE", "SUSPENDED")


class NoRecoveryMaterial(RuntimeError_):
    status_code = 409
    code = "NO_RECOVERY_MATERIAL"


# ---------------------------------------------------------------- planning

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


def variety(student_id: str, item_id: str) -> str:
    return hashlib.md5(f"{student_id}:{item_id}".encode()).hexdigest()


def safe_recovery_question(candidate: dict) -> bool:
    """A practice question must not copy unpublished solution reasoning into its prompt."""
    question = candidate.get("question_text") or ""
    seed = candidate.get("answer_or_solution_seed") or candidate.get("correct_answer") or ""
    return not step_tutor.leaks_solution(question, seed, known=(candidate.get("statement_text") or "",))


def teacher_result(grade: dict) -> dict:
    """The ``last_result`` document of an answered item: the learner's part plus the teacher-only grader evidence."""
    student = {k: grade[k] for k in ("result", "verdict", "feedback") if k in grade}
    return {**student, "teacher": {k: grade.get(k) for k in ("evidence", "failure_mode", "confidence", "grader")}}


# ---------------------------------------------------------------- student-safe presentation

# Import-provenance notes stored as taxonomy descriptions (e.g. "Skill inferred from ordered
# solution steps.") describe how a node was derived, not the skill; never show them to students.
_PROVENANCE_DESCRIPTION_RE = re.compile(r"^\s*(skill|concept|technique|node)?\s*(inferred|derived|mapped|generated)\b", re.IGNORECASE)


def _student_description(description: str | None) -> str | None:
    if not description or _PROVENANCE_DESCRIPTION_RE.search(description):
        return None
    return description


def theory_content(r: dict) -> dict:
    return {"title": f"Worked example: {r['skill_name'] or 'this skill'}", "skill_description": _student_description(r["description"]),
            "example_problem_code": r["canonical_code"], "example_problem_statement": r["statement_text"],
            "example_step_text": r["step_text"]}


def return_content() -> dict:
    return {"title": "Now return to the original problem",
            "message": "Use what you just practised on the step where you were stuck."}


def learning_item_content(r: dict, reveal: bool) -> dict:
    """``r``: question_text, choices, correct_answer, answer_or_solution_seed, transformed_form, transformation_type,
    solution_part_label, canonical_code, statement_text of the learning item (and its source problem)."""
    content = {"title": TYPE_LABELS.get(r["transformation_type"], "Practice"), "form": r["transformed_form"],
               "question_text": r["question_text"], "choices": r["choices"] if r["transformed_form"] == "MCQ" else None,
               "source_problem_code": r["canonical_code"], "source_part_label": r["solution_part_label"],
               "source_problem_statement": r["statement_text"]}  # items refer to "source Problem X"
    if reveal:  # only after the item is finished
        content["answer"] = r["correct_answer"] if r["transformed_form"] == "MCQ" else r["answer_or_solution_seed"]
    return content


def student_item(content_for: Callable[[dict, bool], dict], item: dict, *, current: bool) -> dict:
    """The learner's view of one plan item; ``content_for(item, reveal)`` loads its content (only for the current or a finished item)."""
    finished = item["status"] in ("PASSED", "FAILED", "SKIPPED")
    out = {k: item[k] for k in ("recovery_plan_item_id", "ordinal", "stage", "item_kind", "is_transfer", "status",
                                "tries", "independent_success", "added_reason")}
    out["stage_label"] = STAGE_LABELS[item["stage"]]
    out["type_label"] = TYPE_LABELS.get(item.get("transformation_type") or "", None)
    result = item.get("last_result") or {}
    out["last_result"] = {k: result[k] for k in ("result", "verdict", "feedback") if k in result} or None
    out["last_response"] = item.get("last_response")
    if current or finished:
        out["content"] = content_for(item, finished and item["item_kind"] == "LEARNING_ITEM")
    return out


def plan_view_of(plan: dict, items: list[dict], *, origin: dict, parent_label: str | None,
                 content_for: Callable[[dict, bool], dict]) -> dict:
    """The learner view of a plan from its row, its items (ordered), the origin step's location and the parent's label."""
    progress = mastery_status(items, plan["mastery_policy"] or DEFAULT_POLICY)
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
        "items": [student_item(content_for, i, current=i["ordinal"] == plan["current_item_ordinal"]) for i in items],
    }


TEACHER_ITEM_KEYS = ("ordinal", "stage", "item_kind", "learning_item_id", "worked_step_id", "transformation_type", "status",
                     "tries", "independent_success", "last_response", "last_result", "added_reason")
