"""Synthesizes the post-exam holistic report (requirements/64 §7) — one call per
completed exam, not per question, so the slightly-stronger model configured as
`diagnosis_model_id` is an acceptable per-call cost. No tools: every input the model
needs is already assembled as structured data by the caller (exam_service.py), not
fetched by the agent itself.
"""
from __future__ import annotations

from strands import Agent

from mathbank_exam_agent.llm_models import diagnosis_model
from mathbank_exam_agent.schemas import DiagnosisReport

_SYSTEM_PROMPT = """You write a holistic, post-exam diagnosis report for a student who \
just completed a mock exam. You are given, per question: whether it was answered \
correctly, time spent, difficulty_band, tagged concepts/techniques, and (for incorrect \
answers) the student's actual response alongside the correct solution. You are also \
given the student's PRE-exam mastery tier for each tagged concept/technique (one of \
"critical", "developing", "solid" — use these exact words, never invent a different \
tier vocabulary).

time_management_verdict: a short, specific judgment grounded in the real per-question \
time distribution (e.g. "rushed the last two questions, spending under 2 minutes each \
after averaging 8 minutes on the first three") — never generic advice like "manage \
your time better."

pacing_notes: one entry per question whose time_spent_seconds is unusually high or low \
relative to its difficulty_band — skip questions with ordinary pacing, don't pad this \
list with a note for every single question.

reasoning_guidance: for each INCORRECT question only, describe the kind of thinking \
that reaches the correct approach (e.g. "look for an invariant before casework") — \
never restate the solution itself, that's already shown separately.

improvement_areas: rank concepts/techniques by how much this exam's evidence should \
change the student's priorities — a "critical" pre-exam tier confirmed by another miss \
here is a *confirmed* gap, worth distinguishing from a "solid" pre-exam tier that this \
exam just revealed a new gap in (a more surprising, arguably more urgent finding). Cite \
the real evidence (e.g. "missed 2 of 2 questions tagged here") for each entry."""


def diagnose(diagnosis_input: dict) -> DiagnosisReport:
    agent = Agent(model=diagnosis_model(), system_prompt=_SYSTEM_PROMPT)
    result = agent(
        f"EXAM DATA:\n{diagnosis_input}", structured_output_model=DiagnosisReport,
    )
    return result.structured_output
