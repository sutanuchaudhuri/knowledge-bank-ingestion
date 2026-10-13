from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 8010

    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5433
    postgres_db: str = "mathbank"
    postgres_user: str = "mathbank_ml_readonly"
    postgres_password: str = "change-me"
    postgres_sslmode: str = ""

    ml_model_artifact_bucket: str = ""


# requirements/56 §4 — latency budgets, recorded but not yet enforced (no timeout/
# circuit-breaker wired in main.py yet — TODO).
LATENCY_BUDGET_MS: dict[str, int | None] = {
    "recommendation": 2000,
    "tutor_action_scoring": 200,
    "dynamic_exam_assembly": 5000,
    "batch_analytics": None,  # None == asynchronous/job-based, not a live-request budget
}


def get_settings() -> Settings:
    return Settings()
