"""Step evaluation + progressive hints (v2 Phase 8).

Spec: pack 13 (attempt diagnosis taxonomy), runtime_extension/09 (help levels), 10 (diagnosis
inputs), 17 (hidden-solution security).

Server-side only: the canonical step text is sent to the model, never to the browser. Model output
shown to a student (feedback and hint levels 1–3) is checked for copied solution text and replaced
when it leaks. Level 5 is the deliberate full reveal of the step.

Model calls never run while the attempt row is locked: callers submit (commit), call the model,
then apply the outcome in a new transaction guarded by ``state_version``.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import text
from sqlalchemy.engine import Connection

STEP_TUTOR_MODEL = os.getenv("STEP_TUTOR_MODEL", "gpt-4.1-mini")
HINT_PROMPT_VERSION = "step-hint-v1"
SUCCESS_CONFIDENCE = 0.6
LEAK_NGRAM = 7

FAILURE_MODES = (
    "NONE", "NOT_RECOGNIZED", "MISUNDERSTOOD", "THEOREM_NOT_RECALLED", "WRONG_THEOREM_SELECTED",
    "CANNOT_EXECUTE", "PROOF_CONNECTION_MISSING", "DIAGRAM_MISREAD", "ALGEBRA_BREAKDOWN", "CASE_MISSED",
    "OVERCOMPLICATED", "CARELESS",
)
FAILURE_LOCATIONS = ("NONE", "CONCEPT", "SUBCONCEPT", "SKILL", "TECHNIQUE", "PREREQUISITE", "REPRESENTATION")
VERDICTS = ("CORRECT", "PARTIALLY_CORRECT", "INCORRECT", "OFF_TOPIC")

# Student-facing goal per step type: tells the student *what kind* of move is next, never the move.
STEP_GOALS = {
    "SETUP_OR_CONSTRUCTION": "Set up the configuration: introduce the point, line, notation or construction that makes the next part tractable.",
    "OBSERVATION": "Make a key observation about the figure or the given data.",
    "GEOMETRIC_RELATION": "Establish the geometric relation (angles, parallels, equal segments, …) needed next.",
    "SIMILARITY_RELATION": "Find the similarity (or congruence) that the argument relies on here.",
    "ALGEBRAIC_OR_RATIO_RELATION": "Write down and manipulate the ratio or algebraic relation that follows.",
    "INFERENCE": "Infer the next fact from what has been established so far.",
    "JUSTIFICATION": "Justify the claim this step depends on.",
    "CASE_OR_ASSUMPTION": "Set up the case or assumption this step considers.",
    "CONCLUSION": "Draw the conclusion for this part from what you have established.",
}

HINT_GUIDANCE = {
    1: "DIRECTIONAL PROMPT: ask one short guiding question that points the student's attention to what to look at. "
       "Do not name a theorem, construction, object to introduce, or any result.",
    2: "CONCEPT REMINDER: remind the student of the relevant concept or skill in general terms (you may name it) "
       "and how it is usually used. Do not apply it to the specific objects of this problem.",
    3: "STRATEGIC HINT: describe the strategy for this step, naming the relevant objects of the figure, but do not "
       "state the resulting relation, value or conclusion.",
    4: "NEAR-EXPLICIT STEP: describe almost exactly what to do in this step, leaving only the final computation or "
       "the final statement for the student to write.",
}
FALLBACK_HINTS = {
    1: "What do you already know at this point, and which part of the figure have you not used yet?",
    2: "Recall the main idea behind “{skill}”. How is it usually applied in problems like this?",
    3: "Think about how “{skill}” applies to the objects in this part of the problem. Which relation would it give you?",
}


@dataclass(frozen=True)
class StepContext:
    problem_statement: str
    part_label: str
    step_type: str | None
    tutor_role: str | None
    skill_name: str | None
    previous_steps: list[str]
    canonical_step: str
    student_response: str | None = None
    help_level_used: int = 0


# ---------------------------------------------------------------- pure helpers (unit-tested)

def _words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (value or "").lower())


def _ngrams(words: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def leaks_solution(candidate: str, canonical: str, *, known: tuple[str, ...] = (), n: int = LEAK_NGRAM) -> bool:
    """True when ``candidate`` copies an n-word run of ``canonical`` that the student hasn't already seen.

    Runs that also appear in ``known`` texts (problem statement, the student's own response,
    earlier steps) are not secret, so they don't count.
    """
    canonical_words = _words(canonical)
    if len(canonical_words) < n:
        normalized = " ".join(canonical_words)
        return len(normalized) >= 12 and normalized in " ".join(_words(candidate))
    secret = _ngrams(canonical_words, n)
    for item in known:
        secret -= _ngrams(_words(item), n)
    return bool(secret & _ngrams(_words(candidate), n))


def step_goal(step_type: str | None) -> str:
    return STEP_GOALS.get(step_type or "", "Work out the next step of the solution.")


def outcome_from_verdict(verdict: dict) -> str:
    ok = verdict.get("verdict") == "CORRECT" and float(verdict.get("confidence", 0)) >= SUCCESS_CONFIDENCE
    return "SUCCESS" if ok else "FAILED"


def sanitize_feedback(verdict: dict, ctx: StepContext) -> dict:
    """Feedback on a failed step must not hand over the step itself."""
    verdict = dict(verdict)
    if outcome_from_verdict(verdict) == "FAILED" and leaks_solution(
            verdict.get("feedback", ""), ctx.canonical_step,
            known=(ctx.problem_statement, ctx.student_response or "", *ctx.previous_steps)):
        verdict["feedback"] = ("Not quite yet. Re-read what this step needs to achieve and check your reasoning "
                               "against what you have already established. A hint can help.")
        verdict["feedback_redacted"] = True
    return verdict


def _context_block(ctx: StepContext) -> str:
    previous = "\n".join(f"- {s}" for s in ctx.previous_steps[-6:]) or "(none — this is the first step)"
    return (
        f"PROBLEM (text extracted from a PDF; fractions/subscripts may be flattened, e.g. 'a 2' = a/2):\n"
        f"{ctx.problem_statement}\n\nCURRENT PART: {ctx.part_label}\n"
        f"STEPS ALREADY ESTABLISHED IN THE REFERENCE SOLUTION:\n{previous}\n\n"
        f"CURRENT STEP — type {ctx.step_type}, role {ctx.tutor_role}, skill: {ctx.skill_name}\n"
        f"REFERENCE VERSION OF THIS STEP (secret, never quote it):\n{ctx.canonical_step}\n"
    )


# ---------------------------------------------------------------- model calls (injectable)

_EVAL_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["verdict", "confidence", "feedback", "failure_mode", "failure_location", "evidence"],
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "confidence": {"type": "number"},
        "feedback": {"type": "string"},
        "failure_mode": {"type": "string", "enum": list(FAILURE_MODES)},
        "failure_location": {"type": "string", "enum": list(FAILURE_LOCATIONS)},
        "evidence": {"type": "string"},
    },
}

_EVAL_SYSTEM = """You grade ONE step of a student's solution to a geometry problem, step by step, the way a \
careful tutor would. Compare the student's response with the reference version of the current step.
- CORRECT: the response makes this step's move (the same move or an equally valid one that achieves the same \
purpose for the rest of the solution). Notation and wording may differ.
- PARTIALLY_CORRECT: right direction but incomplete or with an error. INCORRECT: wrong move or wrong result. \
OFF_TOPIC: not an attempt at this step.
- confidence: 0..1 for your verdict.
- feedback: at most 40 words, addressed to the student, encouraging and specific about THEIR reasoning. Never \
state the missing construction, relation or result and never quote the reference step.
- failure_mode/failure_location: diagnose the most local failure (pack 13), NONE when CORRECT.
- evidence: one sentence for the teacher explaining the verdict (not shown to the student)."""


def _client():
    from mathbank_rest.tutor import _client as client  # loads the OpenAI key from the project .env

    return client


def openai_evaluator(ctx: StepContext) -> dict:
    response = _client().chat.completions.create(
        model=STEP_TUTOR_MODEL, temperature=0,
        response_format={"type": "json_schema",
                         "json_schema": {"name": "step_evaluation", "strict": True, "schema": _EVAL_SCHEMA}},
        messages=[{"role": "system", "content": _EVAL_SYSTEM},
                  {"role": "user", "content": _context_block(ctx) + f"\nSTUDENT RESPONSE:\n{ctx.student_response}"}],
    )
    verdict = json.loads(response.choices[0].message.content or "{}")
    verdict["confidence"] = max(0.0, min(1.0, float(verdict.get("confidence", 0))))
    verdict["model"] = STEP_TUTOR_MODEL
    return verdict


def openai_hint_writer(ctx: StepContext, level: int, lower_hints: list[str], stricter: bool = False) -> str:
    rules = HINT_GUIDANCE[level] + (" Use different wording from the reference step: paraphrase, do not copy any "
                                    "phrase of it." if stricter else "")
    previous = "\n".join(f"Level {i + 1}: {h}" for i, h in enumerate(lower_hints)) or "(none)"
    response = _client().chat.completions.create(
        model=STEP_TUTOR_MODEL, temperature=0.2,
        messages=[{"role": "system", "content":
                   "You write one hint (max 45 words) for the current step of a geometry solution. "
                   "Use $...$ for math. Escalate from the earlier hints; never repeat them. " + rules},
                  {"role": "user", "content": _context_block(ctx) + f"\nEARLIER HINTS:\n{previous}\n\nWrite the level {level} hint."}],
    )
    return (response.choices[0].message.content or "").strip()


# ---------------------------------------------------------------- DB-backed operations

def load_step_context(conn: Connection, attempt_id: str, step_id: str) -> StepContext:
    row = conn.execute(text(
        "SELECT p.statement_text, sp.part_label, s.step_type, s.tutor_role, s.skill_name, s.step_text, "
        "       s.solution_id, s.global_step_index, st.last_response_text, coalesce(st.help_level_used, 0) AS help "
        "  FROM pedagogy.solution_step s JOIN pedagogy.solution_part sp USING (solution_part_id) "
        "  JOIN core.problem p ON p.problem_id = s.problem_id "
        "  LEFT JOIN learner.attempt_step_state st ON st.solution_step_id = s.solution_step_id "
        "       AND st.solve_attempt_id = CAST(:a AS uuid) "
        " WHERE s.solution_step_id = :s"), {"a": str(attempt_id), "s": step_id}).mappings().one()
    previous = list(conn.execute(text(
        "SELECT step_text FROM pedagogy.solution_step WHERE solution_id = :sol AND global_step_index < :i "
        "AND publication_status = 'PUBLISHED' ORDER BY global_step_index"),
        {"sol": row["solution_id"], "i": row["global_step_index"]}).scalars())
    return StepContext(
        problem_statement=row["statement_text"] or "", part_label=row["part_label"], step_type=row["step_type"],
        tutor_role=row["tutor_role"], skill_name=row["skill_name"], previous_steps=previous,
        canonical_step=row["step_text"] or "", student_response=row["last_response_text"],
        help_level_used=row["help"])


def get_or_create_hint(conn: Connection, attempt_id: str, step_id: str, level: int,
                       writer: Callable[..., str] = openai_hint_writer) -> dict:
    """Hint text for a level. Levels 1–4 are cached per step for everyone; level 5 reveals the step."""
    ctx = load_step_context(conn, attempt_id, step_id)
    if level >= 5:
        return {"hint_text": ctx.canonical_step, "hint_source": "REFERENCE_STEP"}
    cached = conn.execute(text(
        "SELECT hint_text FROM pedagogy.step_hint WHERE solution_step_id = :s AND hint_level = :l "
        "AND prompt_version = :v"), {"s": step_id, "l": level, "v": HINT_PROMPT_VERSION}).scalar()
    if cached:
        return {"hint_text": cached, "hint_source": "CACHED"}
    lower = list(conn.execute(text(
        "SELECT hint_text FROM pedagogy.step_hint WHERE solution_step_id = :s AND hint_level < :l "
        "AND prompt_version = :v ORDER BY hint_level"), {"s": step_id, "l": level, "v": HINT_PROMPT_VERSION}).scalars())
    known = (ctx.problem_statement, *ctx.previous_steps)
    hint, source = writer(ctx, level, lower), "GENERATED"
    if level <= 3 and leaks_solution(hint, ctx.canonical_step, known=known):
        hint = writer(ctx, level, lower, stricter=True)
        if leaks_solution(hint, ctx.canonical_step, known=known):
            hint, source = FALLBACK_HINTS[level].format(skill=ctx.skill_name or "this step"), "FALLBACK"
    if not hint:
        hint, source = FALLBACK_HINTS[min(level, 3)].format(skill=ctx.skill_name or "this step"), "FALLBACK"
    conn.execute(text(
        "INSERT INTO pedagogy.step_hint (solution_step_id, hint_level, prompt_version, hint_text, model) "
        "VALUES (:s, :l, :v, :t, :m) ON CONFLICT DO NOTHING"),
        {"s": step_id, "l": level, "v": HINT_PROMPT_VERSION, "t": hint,
         "m": STEP_TUTOR_MODEL if source == "GENERATED" else "fallback-template"})
    return {"hint_text": hint, "hint_source": source}


def evaluate_step(conn: Connection, attempt_id: str, step_id: str,
                  evaluator: Callable[[StepContext], dict] = openai_evaluator) -> dict:
    """Grade the stored response for a step (read-only; the caller applies the outcome)."""
    ctx = load_step_context(conn, attempt_id, step_id)
    verdict = sanitize_feedback(evaluator(ctx), ctx)
    verdict["result"] = outcome_from_verdict(verdict)
    return verdict
