"""Settings for mathbank-manim-studio (requirements/60). Reads the same shared Postgres
(POSTGRES_*) and OPENAI_API_KEY conventions used across mathbank-* projects, from this
project's own .env (never the sibling projects' .env files).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_db: str = "mathbank"
    postgres_user: str = "mathbank_app"
    postgres_password: str = ""
    postgres_sslmode: str = ""

    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"

    # The research agent spawns mathbank-mcp-competitions as a real MCP subprocess over
    # stdio for corpus grounding (requirements/49) rather than re-implementing REST calls.
    mcp_competitions_script: str = str(
        REPOSITORY_ROOT / "mathbank-mcp-competitions" / "src" / "mathbank_mcp_competitions"
        / "__main__.py"
    )
    mcp_competitions_python: str = str(
        REPOSITORY_ROOT / "mathbank-mcp-competitions" / ".venv" / "bin" / "python3"
    )

    studio_object_root: str = str(Path(__file__).resolve().parents[2] / "data" / "studio_objects")
    job_ttl_days: int = 1
    worker_poll_seconds: float = 2.0

    # S3 object storage (Lambda deployment opt-in, requirements/63 — local dev keeps the
    # filesystem backend above unchanged). Reuses mathbank-rest's already-provisioned
    # Neon S3-compatible bucket under a `manim-studio/` key prefix, and the same
    # MATHBANK_S3_* alias names object_store.py's Lambda deployment checks first (never
    # the bare AWS_* names, which Lambda reserves for its own execution-role credentials
    # — see GOTCHAS.md #40-class issues / mathbank-rest's object_store.py).
    mathbank_object_backend: str = "filesystem"  # "filesystem" or "s3"
    mathbank_object_bucket: str = ""
    mathbank_object_key_prefix: str = "manim-studio/"
    mathbank_s3_endpoint_url: str = ""
    mathbank_s3_region: str = ""
    mathbank_s3_access_key_id: str = ""
    mathbank_s3_secret_access_key: str = ""
    mathbank_s3_session_token: str = ""

    # Shared with mathbank-rest's ADMIN_API_KEY (same value, same header convention,
    # requirements/60 §7) — guards the one write endpoint a peer service calls
    # (mark-promoted), not the research/render job endpoints themselves.
    admin_api_key: str = ""

    @property
    def database_url(self) -> str:
        suffix = f"?sslmode={self.postgres_sslmode}" if self.postgres_sslmode else ""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}{suffix}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
