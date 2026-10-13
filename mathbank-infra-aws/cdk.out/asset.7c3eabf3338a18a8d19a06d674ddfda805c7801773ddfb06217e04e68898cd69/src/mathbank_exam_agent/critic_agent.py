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
2. Difficulty match — does the question's actual difficulty (not just its labeled \
difficulty_band) genuinely match what was requested? Use the corpus difficulty signal \
you are given as a real, grounded reference point, not a guess.
3. Clarity — is the question unambiguous? Could a careful student reasonably read it \
two different correct ways?
4. For MCQ only — are all 4 options plausible, distinct from each other, and is \
exactly one correct? Flag "all/none of the above" options and near-duplicate \
distractors.
5. For MCQ only — does option_explanations have a real, specific entry for every \
single option (not just the correct one)? Each incorrect option's explanation must \
name an actual, specific mistake, not a generic "this is wrong" — REVISE if any entry \
is missing, vague, or mathematically wrong itself (re-derive it, don't trust the draft).

Set verdict to REVISE if ANY check fails, with feedback specific enough that the \
generator can fix it on the next attempt (name the exact issue, not a vague "improve \
this"). Only set verdict to APPROVE if every check genuinely passes."""


def review_question(
    draft: GeneratedQuestionDraft, *, requested_difficulty: str | None,
    corpus_difficulty_signal: str,
) -> CriticVerdict:
    agent = Agent(model=critic_model(), system_prompt=_SYSTEM_PROMPT)
    prompt = (
        f"DRAFT QUESTION:\n{draft.model_dump_json(indent=2)}\n\n"
        f"REQUESTED DIFFICULTY: {requested_difficulty or 'not specified — use judgment'}\n"
        f"CORPUS DIFFICULTY SIGNAL (real data, for calibration): {corpus_difficulty_signal}"
    )
    result = agent(prompt, structured_output_model=CriticVerdict)
    return result.structured_output
