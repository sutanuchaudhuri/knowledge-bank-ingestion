"""Scaffolded problem-solving — decompose a hard problem into subproblems and
grade free-form answers to them. Implements the planned capability sketched in
presentation/tutor-interaction.html's Turn 3 and
requirements/10_AGENTIC_TUTOR_AND_STUDENT_MASTERY_REQUIREMENTS.md (AGT-11).

Same OpenAI-from-mathbank-rest pattern as db/vector_search.py (embeddings) —
this is the chat-completions equivalent, not a new architectural boundary.
"""
from __future__ import annotations

import json

from openai import OpenAI

from mathbank_rest.db import queries
from mathbank_rest.project_credentials import configure_openai

MODEL_NAME = "gpt-4o-mini"

_client = OpenAI(api_key=configure_openai())

_DECOMPOSE_SYSTEM = """You are a competition math tutor helping a student who is stuck on a \
problem. Break the problem into 2-4 small, ordered subproblems that build up to the full \
solution, each one answerable on its own. Do not reveal the final numeric answer in any \
subproblem. Respond ONLY as JSON matching this shape:
{"subproblems": [{"step": 1, "prompt": "...", "targets_skill": "short label, e.g. casework, \
recursion, modular arithmetic"}]}"""

_CHECK_SYSTEM = """You are grading a student's answer to one subproblem of a larger \
competition math problem. Judge whether their answer/reasoning is substantively correct for \
THIS subproblem only (minor wording differences are fine). Respond ONLY as JSON:
{"correct": true/false, "feedback": "one encouraging sentence, max 25 words"}"""


def decompose_problem(problem_code: str, max_steps: int = 3) -> dict:
    """Returns {"problem_code", "subproblems": [{"step", "prompt", "targets_skill"}]}."""
    problem = queries.get_problem_by_code(problem_code)
    if problem is None:
        raise ValueError(f"no problem with code {problem_code!r}")

    user_prompt = (
        f"Problem ({problem.get('competition', '')} {problem.get('year', '')}, "
        f"difficulty: {problem.get('difficulty_band') or 'unknown'}):\n"
        f"{problem['statement_text']}\n\n"
        f"Break this into at most {max_steps} subproblems."
    )
    response = _client.chat.completions.create(
        model=MODEL_NAME,
        response_format={"type": "json_object"},
        temperature=0.2,
        messages=[
            {"role": "system", "content": _DECOMPOSE_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
    )
    data = json.loads(response.choices[0].message.content or "{}")
    subproblems = data.get("subproblems", [])[:max_steps]
    return {"problem_code": problem_code, "subproblems": subproblems}


def check_subproblem_answer(subproblem_prompt: str, student_answer: str) -> dict:
    """Returns {"correct": bool, "feedback": str}."""
    user_prompt = f"Subproblem: {subproblem_prompt}\n\nStudent's answer: {student_answer}"
    response = _client.chat.completions.create(
        model=MODEL_NAME,
        response_format={"type": "json_object"},
        temperature=0.0,
        messages=[
            {"role": "system", "content": _CHECK_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
    )
    data = json.loads(response.choices[0].message.content or "{}")
    return {
        "correct": bool(data.get("correct", False)),
        "feedback": str(data.get("feedback", "")),
    }
