"""Reviews the WHOLE drafted paper together, after every individual question has
already passed its own per-question critic review (requirements/64 continued) — checks
only what a single-question critic structurally cannot: cross-question near-duplication
(the same core setup reused across questions, not just surface wording) and MCQ option
text (correct or distractor) repeated verbatim across DIFFERENT questions. No tools,
pure judgment over the already-drafted/approved set; the caller (exam_service.py) owns
the bounded fix-up loop, not this module — same split of responsibility as critic_agent.py.
"""
from __future__ import annotations

from strands import Agent

from mathbank_exam_agent.llm_models import critic_model
from mathbank_exam_agent.schemas import DiversityVerdict, GeneratedQuestionDraft

_SYSTEM_PROMPT = """You review a full set of already-individually-approved mock-exam \
questions TOGETHER, as one paper. Your job is cross-question diversity, not re-checking \
anything a single-question reviewer already checked (correctness, clarity, distractor \
quality within one question — assume those already passed).

Check, across the whole set:
1. Near-duplication — do two or more questions share the same core setup/idea, just \
with surface wording or numbers changed? (Two genuinely different questions on the same \
topic/technique are fine and expected; the same combinatorial/algebraic SETUP reused \
twice is not.)
2. Repeated MCQ option text — does any option's text (correct or incorrect) appear \
verbatim or near-verbatim in a DIFFERENT question's options? A distractor repeating \
across questions is a real tell that makes the paper feel templated.
3. Overall topic/style spread — if the request implied variety (e.g. a MIXED-style \
paper), does the set actually cover distinct sub-topics, or did generation collapse onto \
one narrow idea repeatedly?

Set verdict to REVISE if ANY of the above genuinely fails, listing every offending \
question's 1-based ordinal in `flagged`, each with a specific `issue` (name the OTHER \
question ordinal it duplicates/repeats with) and `feedback` specific enough that a \
fresh regeneration of just that question can fix it (e.g. "pick a different setup than \
question 3's coin-flip counting — try a card-drawing or dice scenario instead"). Only \
set verdict to APPROVE if the whole set is genuinely diverse."""


def _paper_prompt(drafts: dict[int, GeneratedQuestionDraft]) -> str:
    paper_json = {
        str(ordinal): {
            "question_type": d.question_type, "prompt_text": d.prompt_text,
            "options": [o.model_dump() for o in d.options] if d.options else None,
            "synthesis_rationale": d.synthesis_rationale,
        }
        for ordinal, d in sorted(drafts.items())
    }
    return f"FULL PAPER (ordinal -> question):\n{paper_json}"


def review_paper(drafts: dict[int, GeneratedQuestionDraft]) -> DiversityVerdict:
    """`drafts` is 1-based ordinal -> draft, for every question currently in the paper
    (already individually critic-approved, served from the question pool, or exhausted
    its own revision budget)."""
    agent = Agent(model=critic_model(), system_prompt=_SYSTEM_PROMPT)
    result = agent(_paper_prompt(drafts), structured_output_model=DiversityVerdict)
    return result.structured_output


async def review_paper_async(drafts: dict[int, GeneratedQuestionDraft]) -> DiversityVerdict:
    agent = Agent(model=critic_model(), system_prompt=_SYSTEM_PROMPT)
    result = await agent.invoke_async(_paper_prompt(drafts), structured_output_model=DiversityVerdict)
    return result.structured_output
