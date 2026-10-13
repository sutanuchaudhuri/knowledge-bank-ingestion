"""Drafts one question at a time (requirements/64 §4), grounded via the generator
agent's own MCP tool calls (search_problems for "inspired by" examples, list_concepts/
list_techniques for slug resolution) — the same "inspired by, never copied" rule
requirements/53 already follows, now surfaced as real agent-visible tool calls instead
of an inline Python function call.
"""
from __future__ import annotations

from strands import Agent

from mathbank_exam_agent.llm_models import generator_model
from mathbank_exam_agent.schemas import GeneratedQuestionDraft

_SYSTEM_PROMPT = """You draft ONE competition-mathematics question for a mock exam \
paper, in the given style/type/topic/difficulty.

Workflow, in order:
1. Call list_concepts and/or list_techniques to resolve the requested topic to real \
concept_slugs/technique_slugs in this corpus — never invent a slug, only use ones these \
tools actually return.
2. Call search_problems with the resolved topic name to find 2-3 real, similar \
problems from the corpus. Use these only as *inspiration* for style and difficulty \
calibration — your drafted question must be an original question, never a copy or \
trivial rewording of a real corpus problem.
3. Draft the question. For MCQ: exactly 4 options, exactly one correct, and the three \
incorrect options must each be a distinct, plausible mistake (not near-duplicates of \
each other or of the correct answer, and never an "all/none of the above" option).
4. Set difficulty_band to your own honest estimate (easy, medium, hard, very_hard) — \
this is checked by a separate critic step against the requested difficulty, so do not \
just echo the request back without actually calibrating.
5. Write a complete, correct solution_text and a one-sentence key_insight.
6. For MCQ questions ONLY: fill option_explanations with one entry per option key. \
The correct key's explanation says why it's correct (briefly — the full derivation \
already belongs in solution_text, this is just the one-line "why this one"). Every \
INCORRECT key's explanation must name the SPECIFIC mistake that choice represents \
(e.g. "forgot to divide by 2 in the final step", "used the wrong sign when moving the \
term across the equals sign", "computed the perimeter instead of the area") — never a \
generic "this is incorrect" with no reason.

Style conventions (same vocabulary requirements/53 already uses): AIME/HMMT-style \
questions are terse and numeric/MCQ-flavored; PROOF_BASED questions require full \
written justification, never just a final answer; TOPIC_BASED/SKILL_BASED/MIXED follow \
whatever question_type was actually requested.

Math notation: write all math inline in prompt_text itself using \\( ... \\) (or \\[ \
... \\] for a standalone display equation) — never $ ... $ or $$ ... $$. Leave \
prompt_latex null; it is not a second copy of the question, so never duplicate \
prompt_text into it."""


def draft_question(
    *, tools: list, style: str, question_type: str, topic_hint: str,
    difficulty_band: str | None, revision_feedback: str | None = None,
) -> GeneratedQuestionDraft:
    agent = Agent(model=generator_model(), tools=tools, system_prompt=_SYSTEM_PROMPT)
    prompt = (
        f"Draft a {question_type} question in {style} style, on the topic: {topic_hint!r}. "
        f"Requested difficulty: {difficulty_band or 'use your judgment based on the style'}."
    )
    if revision_feedback:
        prompt += (
            f"\n\nThis is a REVISION of a previous draft the critic rejected. Specific "
            f"feedback to address: {revision_feedback}"
        )
    result = agent(prompt, structured_output_model=GeneratedQuestionDraft)
    return result.structured_output
