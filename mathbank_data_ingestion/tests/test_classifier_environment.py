"""Classifier and reviewer use file credentials, not inherited shell keys."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mathbank.classify import concept_classifier as classifier
from mathbank.classify import reviewer


@pytest.mark.parametrize("shell_key", [None, "sk-shell-test-not-real"])
@pytest.mark.parametrize("caller", [classifier, reviewer])
def test_local_environment_is_loaded_before_client_creation(
    monkeypatch, tmp_path, shell_key, caller
):
    import openai

    from mathbank import project_credentials

    service = tmp_path / "mathbank_data_ingestion"
    service.mkdir()
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-file-test-not-real\n")
    (service / ".env").write_text("OPENAI_API_KEY=sk-stale-service-fixture\n")
    monkeypatch.setattr(project_credentials, "SERVICE_ROOT", service)

    if shell_key:
        monkeypatch.setenv("OPENAI_API_KEY", shell_key)
    else:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    client = MagicMock()
    client.return_value.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))]
    )
    monkeypatch.setattr(openai, "OpenAI", client)
    if caller is classifier:
        assert caller._call_openai("system", "problem", "test-model") == "{}"
    else:
        assert caller._call_openai([], "test-model") == "{}"
    client.assert_called_once_with(api_key="sk-file-test-not-real")
