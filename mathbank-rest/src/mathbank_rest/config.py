"""Typed settings loaded from the environment / .env file."""
from __future__ import annotations

import warnings
from typing import Literal

from pydantic import Field, SecretStr
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
    # Socratic Studio has a separate staff boundary; legacy routes retain this key (see
    # requirements/11_SYSTEM_DIAGRAMS_TESTING_AND_METRICS.md).
    admin_api_key: str = INSECURE_DEFAULT_ADMIN_API_KEY

    cognito_region: str = "us-east-2"
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_client_secret: SecretStr = SecretStr("")
    cognito_admin_group: str = "Admins"
    # Optional second Studio role ("view as student"); only honoured for members of the admin group.
    cognito_student_group: str = "Students"
    socratic_math_reviewer_group: str = ""
    socratic_pedagogy_reviewer_group: str = ""
    socratic_publisher_group: str = ""
    socratic_csrf_secret: SecretStr = SecretStr("")
    socratic_allowed_origins: list[str] = Field(default_factory=list)
    socratic_cookie_secure: bool = True
    socratic_session_seconds: int = Field(default=900, ge=60, le=3600)
    socratic_auth_mode: Literal["cognito", "local"] = "cognito"
    socratic_aws_profile: str = ""
    socratic_local_username: str = ""
    socratic_local_password_hash: SecretStr = SecretStr("")
    socratic_local_capabilities: list[
        Literal["author", "review_mathematics", "review_pedagogy", "publish", "manage_users", "preview"]
    ] = Field(default_factory=lambda: ["author"])
    # Best-effort Studio access audit into audit.action_log (sign-ins, role switches, admin user
    # actions). Off by default so offline tests never write; the hosted stack and DRAFTS=1 enable it.
    socratic_access_audit: bool = False

    # requirements/60 §7 — the Manim Video Studio is a peer service, not a sibling
    # Python package; promotion calls its REST API (list candidates, fetch the
    # rendered video, mark-promoted) rather than reading its tables directly.
    manim_studio_base_url: str = "http://localhost:8020"

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
