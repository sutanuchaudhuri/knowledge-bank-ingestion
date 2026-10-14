"""Natural-language request -> structured generation parameters (requirements/64 §3,
EXM-3). One Strands `Agent` call, no tools — pure parsing/intent-extraction, grounded
only in requirements/53's own fixed style/question-type vocabulary (never invented).
"""
from __future__ import annotations

from strands import Agent

from mathbank_exam_agent.llm_models import generator_model
from mathbank_exam_agent.schemas import GenerationIntake

_SYSTEM_PROMPT = """You turn a student's natural-language mock-exam request into \
structured generation parameters.

Valid `style` values: AIME, HMMT, PROOF_BASED, TOPIC_BASED, SKILL_BASED, MIXED.
Valid `question_types` values: MCQ, FREE_TEXT, PROOF. A request implying "exam-style, \
no partial credit" usually means MCQ; "show your work"/"prove" implies FREE_TEXT or PROOF.
If the request names a competition style (AIME, HMMT) but doesn't specify question \
types, default to MCQ for AIME and a MIXED set of FREE_TEXT/PROOF for HMMT/PROOF_BASED, \
matching how those real competitions are actually formatted.
If the request gives a topic by name (e.g. "combinatorics", "number theory") but no \
explicit concept/skill slug, leave target_concept_slugs/target_skill_slugs empty and \
put the topic name in topic_hint instead — slug resolution happens later, against the \
real corpus, not here.
If the request gives a time limit in minutes, convert it to seconds for \
time_limit_seconds. If no time limit is mentioned, leave it null — never invent one.
Always produce a short, human-readable title."""


def parse_intake(nl_request: str) -> GenerationIntake:
    agent = Agent(model=generator_model(), system_prompt=_SYSTEM_PROMPT)
    result = agent(nl_request, structured_output_model=GenerationIntake)
    return result.structured_output


async def parse_intake_async(nl_request: str) -> GenerationIntake:
    agent = Agent(model=generator_model(), system_prompt=_SYSTEM_PROMPT)
    result = await agent.invoke_async(nl_request, structured_output_model=GenerationIntake)
    return result.structured_output
