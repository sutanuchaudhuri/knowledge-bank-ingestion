"""Settings. Non-secret values only; the OpenAI key is read from the repository root .env (never the shell)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PROJECT_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GENAI_POC_", env_file=PROJECT_ROOT / ".env", extra="ignore")

    # Local workstation profile; leave blank to use the default credential chain (e.g. an execution role).
    aws_profile: str = "aws-sutanu-admin"

    # Nova Sonic speech-to-speech model. Not offered in us-east-2, where the data plane lives.
    sonic_region: str = "us-east-1"
    sonic_model_id: str = "amazon.nova-2-5-sonic"
    voice: str = "tiffany"
    input_sample_rate: int = 16000
    output_sample_rate: int = 24000

    # Read-only MathBank data plane (requirements 70/71): S3 Vectors indexes + mb-content items.
    data_region: str = "us-east-2"
    vector_bucket: str = "mathbank-vectors-dev"
    content_table: str = "mb-content-dev"
    min_similarity: float = Field(default=0.45, ge=0.0, le=1.0)
    # Keep only hits within this distance of the best accepted hit of the same family (drops weak tail matches).
    relative_window: float = Field(default=0.10, ge=0.0, le=1.0)

    # Paid-usage guardrails: per-session wall clock and the cumulative audio budget for this POC.
    max_session_seconds: int = Field(default=120, ge=10, le=480)
    audio_budget_seconds: int = Field(default=300, ge=0)
    budget_ledger: Path = PROJECT_ROOT / ".runtime" / "usage.json"

    host: str = "127.0.0.1"
    port: int = 8040


@lru_cache
def get_settings() -> Settings:
    return Settings()
