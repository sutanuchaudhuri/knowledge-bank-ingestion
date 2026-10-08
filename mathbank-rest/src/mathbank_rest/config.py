"""Typed settings loaded from the environment / .env file."""
from __future__ import annotations

import warnings

from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_JWT_SECRET = "dev-only-insecure-secret-change-me"
INSECURE_DEFAULT_ADMIN_API_KEY = "dev-only-insecure-admin-key-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5433
    postgres_db: str = "mathbank"
    postgres_user: str = "mathbank_app"
    postgres_password: str = ""
    postgres_sslmode: str = ""  # "require" for Neon/managed Postgres; empty = libpq default (prefer)

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str | None = None

    # Student login (learner.* schema) — HS256 JWT bearer tokens.
    # Must be set to a long random value via env/JWT_SECRET in every real
    # deployment — the checked-in default only exists so local dev/tests work
    # without a .env; see the warning emitted below when it's left unchanged.
    jwt_secret: str = INSECURE_DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60 * 24 * 7  # 7 days

    # Admin endpoints (routers/admin.py) — register competitions/papers,
    # retry pipeline stages. Single shared key via X-Admin-Api-Key header;
    # no per-admin-user accounts yet (tracked as a follow-up, see
    # requirements/11_SYSTEM_DIAGRAMS_TESTING_AND_METRICS.md).
    admin_api_key: str = INSECURE_DEFAULT_ADMIN_API_KEY

    @property
    def postgres_dsn(self) -> str:
        dsn = (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        if self.postgres_sslmode:
            dsn += f"?sslmode={self.postgres_sslmode}"
        return dsn


settings = Settings()

if settings.jwt_secret == INSECURE_DEFAULT_JWT_SECRET:
    warnings.warn(
        "JWT_SECRET is using the insecure built-in default — set a long random "
        "value in .env before issuing tokens anyone relies on (student logins "
        "signed with this default are forgeable by anyone reading this source).",
        stacklevel=1,
    )

if settings.admin_api_key == INSECURE_DEFAULT_ADMIN_API_KEY:
    warnings.warn(
        "ADMIN_API_KEY is using the insecure built-in default — set a long "
        "random value in .env before exposing /v1/admin/* beyond localhost.",
        stacklevel=1,
    )
