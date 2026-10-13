"""Explicit provider selection; failed Gateway requests never trigger a silent fallback."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values
from openai import OpenAI


def gateway_client() -> OpenAI:
    values = dotenv_values(Path(__file__).resolve().parents[3] / ".env", interpolate=False)
    base = values.get("NEON_AI_GATEWAY_BASE_URL")
    token = values.get("NEON_AI_GATEWAY_TOKEN")
    if not base or not token or token.strip() in ("...", "change-me"):
        raise RuntimeError(
            "Configure NEON_AI_GATEWAY_BASE_URL and NEON_AI_GATEWAY_TOKEN in root .env"
        )
    parsed = urlsplit(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise RuntimeError("AI Gateway requires a credential-free HTTPS base URL")
    return OpenAI(base_url=base.rstrip("/") + "/v1", api_key=token, max_retries=0, timeout=90)


def provider_name() -> str:
    root = Path(__file__).resolve().parents[3]
    root_values = dotenv_values(root / ".env", interpolate=False)
    service_values = dotenv_values(root / "mathbank-rest/.env", interpolate=False)
    provider = (
        root_values.get("MATHBANK_RUNTIME_AI_PROVIDER")
        or service_values.get("MATHBANK_RUNTIME_AI_PROVIDER")
        or "openai"
    )
    if provider not in ("openai", "neon"):
        raise RuntimeError("MATHBANK_RUNTIME_AI_PROVIDER must be openai or neon")
    return provider


def model_name() -> str:
    if provider_name() == "neon":
        return "gpt-5-4-mini"
    root = Path(__file__).resolve().parents[3]
    root_values = dotenv_values(root / ".env", interpolate=False)
    rest_values = dotenv_values(root / "mathbank-rest/.env", interpolate=False)
    agent_values = dotenv_values(root / "mathbank-agent/.env", interpolate=False)
    model = (
        root_values.get("MATHBANK_RUNTIME_AI_MODEL")
        or rest_values.get("MATHBANK_RUNTIME_AI_MODEL")
        or agent_values.get("MATHBANK_AGENT_MODEL")
        or "openai/gpt-4o-mini"
    )
    if "/" in model and not model.startswith("openai/"):
        raise RuntimeError("The OpenAI runtime requires an OpenAI model")
    return model.removeprefix("openai/")


def client() -> OpenAI:
    return speech_client() if provider_name() == "openai" else gateway_client()


def speech_client() -> OpenAI:
    """Use the same file-only OpenAI credentials and endpoint settings as the tutor agent."""
    from mathbank_rest.project_credentials import configure_openai

    key = configure_openai()
    base = os.environ.get("OPENAI_API_BASE") or os.environ.get("OPENAI_BASE_URL")
    return OpenAI(api_key=key, base_url=base, max_retries=0, timeout=90)
