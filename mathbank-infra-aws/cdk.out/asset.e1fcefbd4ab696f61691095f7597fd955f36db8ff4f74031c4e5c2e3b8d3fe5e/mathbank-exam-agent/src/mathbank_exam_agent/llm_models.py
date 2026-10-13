"""Model-backend factory (requirements/64 §1). **OpenAI is the current, live-verified
backend** — confirmed live this session that Bedrock model invocation is blocked
account-wide (`ValidationException: Error 002: Access to Bedrock models is not allowed
for this account`, reproduced with both an Anthropic and an Amazon model), so the
Strands `Agent`/`MCPClient` architecture is unchanged, but `BedrockModel` is swapped for
`OpenAIModel` until that account-level restriction is resolved. Swapping back is a
one-line change in each factory function below — nothing else in this project imports
`OpenAIModel`/`BedrockModel` directly.
"""
from __future__ import annotations

from strands.models.model import Model
from strands.models.openai import OpenAIModel

from mathbank_exam_agent.config import get_settings


def _openai_model(model_id: str) -> Model:
    settings = get_settings()
    return OpenAIModel(client_args={"api_key": settings.openai_api_key}, model_id=model_id)


def generator_model() -> Model:
    return _openai_model(get_settings().generator_model_id)


def critic_model() -> Model:
    return _openai_model(get_settings().critic_model_id)


def diagnosis_model() -> Model:
    return _openai_model(get_settings().diagnosis_model_id)
