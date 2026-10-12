import pytest
from project_env import PROVIDER_KEYS, load_project_openai


@pytest.fixture
def files(tmp_path, monkeypatch):
    for name in PROVIDER_KEYS:
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name, raising=False)
    service = tmp_path / "mathbank-agent/.env"
    service.parent.mkdir()
    service.write_text("OPENAI_API_KEY=sk-service-fixture\nPOSTGRES_HOST=service-db\n")
    return tmp_path / ".env", service


def test_root_key_wins_over_shell_and_service_from_any_directory(files, monkeypatch, tmp_path):
    import os

    root, service = files
    root.write_text('export OPENAI_API_KEY="sk-root-fixture" # comment\n')
    monkeypatch.setenv("OPENAI_API_KEY", "sk-wrong-shell-fixture")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://incorrect.example")
    monkeypatch.setenv("OPENAI_ORGANIZATION", "wrong-shell-org")
    monkeypatch.setenv("POSTGRES_HOST", "worker-db")
    monkeypatch.chdir(tmp_path.parent)
    assert load_project_openai(service) == "sk-root-fixture"
    assert os.environ["OPENAI_API_KEY"] == "sk-root-fixture"
    assert "OPENAI_BASE_URL" not in os.environ
    assert "OPENAI_ORGANIZATION" not in os.environ
    assert os.environ["POSTGRES_HOST"] == "worker-db"


def test_service_only_checkout_ignores_shell_key(files, monkeypatch):
    _, service = files
    monkeypatch.setenv("OPENAI_API_KEY", "sk-wrong-shell-fixture")
    assert load_project_openai(service) == "sk-service-fixture"


@pytest.mark.parametrize("text", ["", "OPENAI_API_KEY=\n", "OPENAI_API_KEY=change-me\n",
                                 'OPENAI_API_KEY="secret with spaces"\n',
                                 "OPENAI_API_KEY=${OPENAI_API_KEY}\n"])
def test_invalid_root_never_falls_back_or_discloses_value(files, monkeypatch, text):
    root, service = files
    root.write_text(text)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-shell-fixture")
    with pytest.raises(RuntimeError, match="shell credentials are ignored") as error:
        load_project_openai(service)
    assert "sk-shell-fixture" not in str(error.value)
    assert "secret with spaces" not in str(error.value)


def test_missing_all_files_rejects_shell(files, monkeypatch):
    _, service = files
    service.unlink()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-shell-fixture")
    with pytest.raises(RuntimeError, match="shell credentials are ignored"):
        load_project_openai(service)


def test_provider_settings_from_files_only(files, monkeypatch):
    import os

    root, service = files
    root.write_text("OPENAI_API_KEY=sk-root-fixture\nOPENAI_PROJECT=file-project\n")
    service.write_text("OPENAI_API_KEY=sk-service-fixture\nOPENAI_BASE_URL=https://file.example/v1\n")
    monkeypatch.setenv("OPENAI_PROJECT", "shell-project")
    load_project_openai(service)
    assert os.environ["OPENAI_PROJECT"] == "file-project"
    assert os.environ["OPENAI_BASE_URL"] == "https://file.example/v1"
