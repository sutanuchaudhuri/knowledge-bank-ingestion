from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mathbank_rest import project_credentials, runtime_ai


def test_openai_client_uses_shared_loader_and_agent_endpoint(monkeypatch):
    monkeypatch.setenv("OPENAI_API_BASE", "https://example.test/v1")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://unused.test/v1")
    monkeypatch.setattr(project_credentials, "configure_openai", lambda: "synthetic-key")
    factory = MagicMock()
    monkeypatch.setattr(runtime_ai, "OpenAI", factory)
    runtime_ai.speech_client()
    factory.assert_called_once_with(
        api_key="synthetic-key",
        base_url="https://example.test/v1",
        max_retries=0,
        timeout=90,
    )


@pytest.mark.parametrize(
    "configured,expected",
    [
        ("openai/gpt-4o-mini", "gpt-4o-mini"),
        ("gpt-4.1-mini", "gpt-4.1-mini"),
    ],
)
def test_runtime_reuses_agent_model_configuration(monkeypatch, configured, expected):
    monkeypatch.setattr(runtime_ai, "provider_name", lambda: "openai")
    monkeypatch.setattr(
        runtime_ai,
        "dotenv_values",
        lambda path, **kwargs: (
            {"MATHBANK_AGENT_MODEL": configured}
            if Path(path).parent.name == "mathbank-agent"
            else {}
        ),
    )
    assert runtime_ai.model_name() == expected


def test_runtime_openai_never_falls_back_to_gateway(monkeypatch):
    monkeypatch.setattr(runtime_ai, "provider_name", lambda: "openai")
    monkeypatch.setattr(
        runtime_ai, "speech_client", lambda: (_ for _ in ()).throw(RuntimeError("quota"))
    )
    gateway = MagicMock()
    monkeypatch.setattr(runtime_ai, "gateway_client", gateway)
    with pytest.raises(RuntimeError, match="quota"):
        runtime_ai.client()
    gateway.assert_not_called()
