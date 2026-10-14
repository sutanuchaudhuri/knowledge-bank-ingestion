"""Drafts one question at a time (requirements/64 §4, continued), grounded in a
deterministic retrieval step the caller (exam_service.py) performs up front via the
corpus's hybrid (semantic + lexical + graph) `search_problems` — the same "RAG + graph"
grounding the orchestrator consults before dispatching each question (requirements/64
continued). That retrieval is NOT left to the agent's own tool-calling judgment: the
caller passes the retrieved candidate pool directly into the prompt, and the generator
is required to cite `inspiration_sources` only from that pool — never a hallucinated
canonical_code — which `exam_service.py` validates/filters server-side before accepting
the draft. `list_concepts`/`list_techniques` remain real agent tool calls (slug
resolution is a judgment call worth an agent turn); sourcing is not.
"""
from __future__ import annotations

from strands import Agent

from mathbank_exam_agent.llm_models import generator_model
from mathbank_exam_agent.math_format import normalize_draft_math
from mathbank_exam_agent.schemas import GeneratedQuestionDraft, InspirationSource

_SYSTEM_PROMPT = """You draft ONE competition-mathematics question for a mock exam \
paper, in the given style/type/topic/difficulty.

Workflow, in order:
1. Call list_concepts and/or list_techniques to resolve the requested topic to real \
concept_slugs/technique_slugs in this corpus — never invent a slug, only use ones these \
tools actually return.
2. You are given a CANDIDATE POOL of real corpus problems already retrieved for this \
topic (below). Pick 1-3 of them as genuine inspiration — draw on their underlying setup, \
style, or technique, but your drafted question must be an original question, never a \
copy or trivial rewording. For every source you use, fill inspiration_sources with its \
exact canonical_code (copied verbatim from the candidate pool — never invent one) and a \
specific note on what you actually borrowed or changed (e.g. "same combinatorial \
counting setup, changed the group sizes and added a parity constraint" — never a vague \
"general inspiration"). If the candidate pool is empty, inspiration_sources may be empty.
For HARD or VERY_HARD requests, when at least two candidates are available, use at least \
two sources that contribute DISTINCT core ideas and make both ideas necessary in the \
new problem. Do not merely borrow wording from one and a technique from another.
3. Draft the question. prompt_text contains the question stem ONLY; never repeat MCQ \
choices inside prompt_text because the UI renders options separately. For MCQ: exactly \
4 options, exactly one correct, and the three \
incorrect options must each be a distinct, plausible mistake (not near-duplicates of \
each other or of the correct answer, and never an "all/none of the above" option).
4. Calibrate difficulty by the reasoning demanded by the WHOLE source problem, never \
by extracting one recognizable step or named formula from it. A source mentioning \
Euler's totient inside a longer solution does NOT justify a one-step "compute phi(n)" \
question. EASY may be one routine application. MEDIUM needs linked reasoning rather \
than direct substitution. HARD must require a non-obvious synthesis of at least two \
concepts, constraints, or techniques; it must not be solvable by direct formula lookup, \
inspection, checking four choices numerically, or one routine computation. VERY_HARD \
must add another layer or a genuinely difficult structural insight. Set difficulty_band \
to your honest estimate, not merely the requested label.
Fill synthesis_rationale for hard/very_hard drafts: name the distinct ideas and explain \
how they interact so that neither alone solves the problem. The critic will verify this \
against the actual question and reject unsupported claims.
5. Write the complete, correct solution as solution_steps — a list of discrete, \
ORDERED steps, one list entry per actual step of the derivation (not one entry per \
sentence of prose, and never the whole solution collapsed into a single entry) — plus a \
one-sentence key_insight. Step count is presentation metadata, NOT evidence of \
difficulty: never inflate a routine computation into many steps to make it look hard.
6. For MCQ questions ONLY: fill option_explanations with one entry per option key. \
The correct key's explanation says why it's correct (briefly — the full derivation \
already belongs in solution_steps, this is just the one-line "why this one"). Every \
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
prompt_text into it. In structured output, TeX backslashes must survive JSON escaping: \
emit valid escaped strings so commands such as \\frac and \\text never become control \
characters. Do not put Markdown bold markers or TeX answer labels in prompt_text."""


def _format_candidate_pool(candidate_sources: list[dict]) -> str:
    if not candidate_sources:
        return "CANDIDATE POOL: empty — no close corpus match was retrieved for this topic. " \
               "inspiration_sources must be empty; draft purely from your own knowledge."
    lines = ["CANDIDATE POOL (choose inspiration_sources only from these exact canonical_codes):"]
    for c in candidate_sources:
        lines.append(
            f"- canonical_code={c['canonical_code']!r} "
            f"({c.get('competition', '?')} {c.get('year', '?')}): "
            f"{(c.get('statement_text') or '')[:2000]}"
        )
    return "\n".join(lines)


def _valid_canonical_codes(candidate_sources: list[dict]) -> set[str]:
    return {c["canonical_code"] for c in candidate_sources}


def _ensure_inspiration_source(draft: GeneratedQuestionDraft, candidate_sources: list[dict]) -> None:
    """Keep attribution visible when retrieval found a real corpus candidate.

    Structured model output may omit the field or cite a code outside the supplied
    pool. In either case, retain the closed-pool guarantee while recording the
    retrieved source rather than silently losing all provenance.
    """
    valid_codes = _valid_canonical_codes(candidate_sources)
    draft.inspiration_sources = [
        source for source in draft.inspiration_sources if source.canonical_code in valid_codes
    ]
    if draft.inspiration_sources or not candidate_sources:
        return
    source = candidate_sources[0]
    draft.inspiration_sources = [
        InspirationSource(
            canonical_code=source["canonical_code"],
            note=(
                "Topic-matched corpus example retrieved for inspiration; "
                "the question was newly composed rather than copied."
            ),
        )
    ]


def _draft_prompt(
    *, style: str, question_type: str, topic_hint: str, difficulty_band: str | None,
    candidate_sources: list[dict], revision_feedback: str | None,
) -> str:
    prompt = (
        f"Draft a {question_type} question in {style} style, on the topic: {topic_hint!r}. "
        f"Requested difficulty: {difficulty_band or 'use your judgment based on the style'}.\n\n"
        f"{_format_candidate_pool(candidate_sources)}"
    )
    if revision_feedback:
        prompt += (
            f"\n\nThis is a REVISION of a previous draft the critic rejected. Specific "
            f"feedback to address: {revision_feedback}"
        )
    if (difficulty_band or "").lower() in {"hard", "very_hard"}:
        prompt += (
            "\n\nHARD DESIGN CONTRACT: start from the complexity of complete source problems, "
            "not an isolated named step. Build a new problem whose solution requires at least "
            "two ideas or constraints to interact non-trivially. If two or more candidates are "
            "available, combine distinct core contributions from at least two of them. State "
            "that interaction precisely in synthesis_rationale."
        )
    return prompt


def _finish_draft(draft: GeneratedQuestionDraft, candidate_sources: list[dict]) -> GeneratedQuestionDraft:
    # Never trust the model's own citation at face value — drop any canonical_code that
    # isn't actually in the candidate pool it was given (requirements/64 continued: a
    # hallucinated source is worse than no source, since a student may click through it).
    _ensure_inspiration_source(draft, candidate_sources)
    return normalize_draft_math(draft)


def draft_question(
    *, tools: list, style: str, question_type: str, topic_hint: str,
    difficulty_band: str | None, candidate_sources: list[dict],
    revision_feedback: str | None = None,
) -> GeneratedQuestionDraft:
    agent = Agent(model=generator_model(), tools=tools, system_prompt=_SYSTEM_PROMPT)
    prompt = _draft_prompt(
        style=style, question_type=question_type, topic_hint=topic_hint, difficulty_band=difficulty_band,
        candidate_sources=candidate_sources, revision_feedback=revision_feedback,
    )
    result = agent(prompt, structured_output_model=GeneratedQuestionDraft)
    return _finish_draft(result.structured_output, candidate_sources)


async def draft_question_async(
    *, tools: list, style: str, question_type: str, topic_hint: str,
    difficulty_band: str | None, candidate_sources: list[dict],
    revision_feedback: str | None = None,
) -> GeneratedQuestionDraft:
    """Same as draft_question, but awaits the model so many slots draft concurrently on
    one event loop. A fresh Agent per call keeps concurrent use safe."""
    agent = Agent(model=generator_model(), tools=tools, system_prompt=_SYSTEM_PROMPT)
    prompt = _draft_prompt(
        style=style, question_type=question_type, topic_hint=topic_hint, difficulty_band=difficulty_band,
        candidate_sources=candidate_sources, revision_feedback=revision_feedback,
    )
    result = await agent.invoke_async(prompt, structured_output_model=GeneratedQuestionDraft)
    return _finish_draft(result.structured_output, candidate_sources)
