"""Classification loads the ingestion env without overriding shell credentials."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mathbank.classify import concept_classifier as classifier


@pytest.mark.parametrize("shell_key", [None, "sk-shell-test-not-real"])
def test_local_environment_is_loaded_before_client_creation(monkeypatch, shell_key):
    import dotenv
    import openai

    if shell_key:
        monkeypatch.setenv("OPENAI_API_KEY", shell_key)
    else:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def fake_load(path):
        assert path == classifier.Path(classifier.__file__).resolve().parents[3] / ".env"
        if not classifier.os.environ.get("OPENAI_API_KEY"):
            monkeypatch.setenv("OPENAI_API_KEY", "sk-file-test-not-real")

    monkeypatch.setattr(dotenv, "load_dotenv", fake_load)
    client = MagicMock()
    client.return_value.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))]
    )
    monkeypatch.setattr(openai, "OpenAI", client)
    assert classifier._call_openai("system", "problem", "test-model") == "{}"
    client.assert_called_once_with(api_key=shell_key or "sk-file-test-not-real")
