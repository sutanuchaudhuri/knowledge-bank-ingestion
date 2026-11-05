"""Builds the live Nova Sonic tutor (Strands BidiAgent)."""
from __future__ import annotations

from typing import cast

from strands.bidi import BidiAgent

from mathbank_genai_poc.config import Settings
from mathbank_genai_poc.knowledge import KnowledgeBase
from mathbank_genai_poc.tools import make_tools

SYSTEM_PROMPT = """You are MathBank's live voice math tutor for a secondary-school or competition-math student.
This is a spoken conversation, so:
- Speak in short, warm sentences. Ask one question at a time and then stop and listen.
- Say mathematics the way a teacher reads it aloud ("x squared", "angle A B C"), never as code or LaTeX.

Grounding:
- When the student names a topic, technique, theorem or problem type, first call search_math_topic with a short
  topic phrase, then teach from what it returns. Search again when the student moves to a new topic.
- Never invent definitions, theorems, sources or problem statements. If the search is not grounded, say so plainly.

Teaching:
- Teach Socratically: find out what the student already knows, give the key idea briefly, then ask them to try a
  small next step. Give hints in increasing strength rather than full solutions.
- The teaching_moves in search results are private notes. Do not read them aloud or give away a full solution.
- When offering practice, read one problem clearly and let the student attempt it. Do not state its answer.
- Do not ask for or store personal information. If asked what you are, say you are a MathBank prototype tutor."""


def build_agent(settings: Settings, kb: KnowledgeBase) -> BidiAgent:
    import boto3
    from strands.bidi.models import BedrockNovaSonicAudioConfig, BedrockNovaSonicModel

    session = boto3.Session(profile_name=settings.aws_profile or None, region_name=settings.sonic_region)
    audio = cast(BedrockNovaSonicAudioConfig, {"input": {"sample_rate": settings.input_sample_rate},
                                               "output": {"sample_rate": settings.output_sample_rate}})
    model = BedrockNovaSonicModel(boto_session=session, model_id=settings.sonic_model_id, voice=settings.voice,
                                  audio=audio)
    return BidiAgent(model=model, tools=make_tools(kb), system_prompt=SYSTEM_PROMPT, name="mathbank-voice-tutor")
