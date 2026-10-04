"""Typed settings loaded from the environment / .env file."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


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
