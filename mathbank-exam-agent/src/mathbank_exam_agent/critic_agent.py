"""Reviews one drafted question against a fixed rubric (requirements/64 §4) — no
tools, pure judgment over the already-drafted text plus the difficulty signals already
gathered by the caller. Returns APPROVE or REVISE with specific, structured feedback;
the caller (exam_service.py) owns the bounded revision loop, not this module.
"""
from __future__ import annotations

from strands import Agent

from mathbank_exam_agent.llm_models import critic_model
from mathbank_exam_agent.schemas import CriticVerdict, GeneratedQuestionDraft

_SYSTEM_PROMPT = """You are a strict reviewer of a drafted competition-mathematics \
question. Check, in order:

1. Mathematical correctness — is the stated correct_key/expected_answer actually \
correct given the question as written? Re-derive it yourself, don't trust the draft.
2. Difficulty match — judge the reasoning required by the COMPLETE question, not the \
number of written solution steps and not the difficulty of a source problem from which \
one easy sub-step was extracted. HARD requires non-obvious synthesis of at least two \
concepts, constraints, or techniques. Direct formula substitution, a standard \
definition recall, routine arithmetic, answer-choice enumeration, or a single familiar \
technique is not hard even when it appeared inside a hard source problem. VERY_HARD \
needs an additional layer or a genuinely difficult structural insight. Use the corpus \
difficulty signal as calibration, but never inherit a source label automatically. Set \
synthesis_ok=false when hard/very_hard was requested but the problem does not meet this \
synthesis standard; difficulty_match_ok must also be false in that case. Treat \
synthesis_rationale only as a claim to verify against the actual stem and solution, not \
as proof that the question is hard.
3. Clarity — is the question unambiguous? Could a careful student reasonably read it \
two different correct ways?
4. Math formatting and UI compatibility — inspect prompt_text, every option, the \
expected answer/rubric, option explanations, and solution_steps. Ensure math is \
properly delimited with \\( ... \\) inline or \\[ ... \\] for a standalone display \
equation, braces and commands are well-formed, and the notation is compatible with \
KaTeX. Reject raw/unbalanced delimiters or notation likely to show as source text or \
render incorrectly. You review the serialized content, not a browser screenshot; the \
exam UI renders accepted delimiters with KaTeX on a contained, contrasting math surface.
5. For MCQ only — are all 4 options plausible, distinct from each other, and is \
exactly one correct? Flag "all/none of the above" options and near-duplicate \
distractors. Independently solve the problem and verify that correct_key names the \
option matching your result and that the solution reaches that same result. Reject \
decimal approximation being called an exact integer and any contradiction between \
correct_key, option explanations, and solution_steps.
6. For MCQ only — does option_explanations have a real, specific entry for every \
single option (not just the correct one)? Each incorrect option's explanation must \
name an actual, specific mistake, not a generic "this is wrong" — REVISE if any entry \
is missing, vague, or mathematically wrong itself (re-derive it, don't trust the draft).

Set verdict to REVISE if ANY check fails, with feedback specific enough that the \
generator can fix it on the next attempt (name the exact issue, not a vague "improve \
this"). Only set verdict to APPROVE if every check genuinely passes."""


def _review_prompt(draft: GeneratedQuestionDraft, *, requested_difficulty: str | None,
                   corpus_difficulty_signal: str) -> str:
    return (
        f"DRAFT QUESTION:\n{draft.model_dump_json(indent=2)}\n\n"
        f"REQUESTED DIFFICULTY: {requested_difficulty or 'not specified — use judgment'}\n"
        f"CORPUS DIFFICULTY SIGNAL (real data, for calibration): {corpus_difficulty_signal}"
    )


def review_question(
    draft: GeneratedQuestionDraft, *, requested_difficulty: str | None,
    corpus_difficulty_signal: str,
) -> CriticVerdict:
    agent = Agent(model=critic_model(), system_prompt=_SYSTEM_PROMPT)
    prompt = _review_prompt(draft, requested_difficulty=requested_difficulty,
                            corpus_difficulty_signal=corpus_difficulty_signal)
    result = agent(prompt, structured_output_model=CriticVerdict)
    return result.structured_output


async def review_question_async(
    draft: GeneratedQuestionDraft, *, requested_difficulty: str | None,
    corpus_difficulty_signal: str,
) -> CriticVerdict:
    agent = Agent(model=critic_model(), system_prompt=_SYSTEM_PROMPT)
    prompt = _review_prompt(draft, requested_difficulty=requested_difficulty,
                            corpus_difficulty_signal=corpus_difficulty_signal)
    result = await agent.invoke_async(prompt, structured_output_model=CriticVerdict)
    return result.structured_output
