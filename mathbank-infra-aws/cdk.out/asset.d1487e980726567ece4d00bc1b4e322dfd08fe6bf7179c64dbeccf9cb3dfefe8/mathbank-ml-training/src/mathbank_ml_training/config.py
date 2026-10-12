"""Settings for mathbank-ml-training, loaded from environment variables (.env).

Mirrors the `pydantic-settings` pattern already used by mathbank-rest/mathbank-agent
(see mathbank-rest/src/mathbank_rest/config.py for the sibling convention) rather than
inventing a new settings mechanism.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5433
    postgres_db: str = "mathbank"
    postgres_user: str = "mathbank_ml_readonly"
    postgres_password: str = "change-me"
    postgres_sslmode: str = ""

    neo4j_uri: str = "neo4j://127.0.0.1:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "change-me"
    neo4j_database: str = "neo4j"

    ml_training_artifact_bucket: str = ""
    aws_region: str = ""

    sagemaker_role_arn: str = ""
    sagemaker_execution_image_uri: str = ""

    # TODO (requirements/55 §2): once extract/postgres_extract.py is implemented, confirm
    # whether a single read-only role is sufficient or whether row-level security /
    # column masking is needed for any learner-sensitive fields before this package is
    # ever pointed at a non-dev database.


def get_settings() -> Settings:
    """Returns a fresh Settings instance. Not cached yet — TODO: add `functools.lru_cache`
    once this module is used by more than notebooks (repeated .env parsing is harmless for
    now but wasteful once jobs/*.py run frequently)."""
    return Settings()
