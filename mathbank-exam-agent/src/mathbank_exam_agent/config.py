"""Settings for mathbank-exam-agent (requirements/64). This service never connects to
Postgres/Neo4j directly — every read/write of quiz.* data goes through mathbank-rest's
REST surface (the admin-key-gated /v1/quiz-integration/* endpoints for writes, the
existing /v1/quiz/* student-bearer-token endpoints for the exam-taking flow), keeping
mathbank-rest the one owner of that schema's writes (requirements/64 §3).
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""

    # Model backend (requirements/64 §1): OpenAI is used for now (OPENAI_API_KEY,
    # shared project-wide convention) pending Bedrock model-access being enabled on the
    # AWS account — see llm_models.py's module docstring for the one-line swap back to
    # BedrockModel once that's resolved. Deliberately 3 separate model-id settings (not
    # one): generation and critique need the stronger model because mathematical
    # correctness is a hard acceptance gate; diagnosis remains independently configurable.
    generator_model_id: str = "gpt-4o"
    critic_model_id: str = "gpt-4o"
    diagnosis_model_id: str = "gpt-4o-mini"
    # Set once Bedrock access is confirmed (requirements/64 §1's cost-driven default):
    bedrock_model_id: str = "anthropic.claude-haiku-4-5-20251001-v1:0"
    aws_region: str = "us-east-2"

    mathbank_rest_base_url: str = "http://localhost:8000"
    admin_api_key: str = ""

    # The research agent's own stdio-vs-HTTP choice (requirements/60/63) — this project
    # always uses the already-deployed HTTP instance, never a stdio subprocess, since
    # this service has no local sibling-package access to mathbank-mcp-competitions at
    # all (it is a genuinely separate project, requirements/64 §0's scope boundary).
    mcp_competitions_url: str = "http://localhost:9000/mcp"

    max_critic_revision_rounds: int = 4

    # AWS Cognito (requirements/64 continued — onboarding/login/forgot-password).
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_client_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
