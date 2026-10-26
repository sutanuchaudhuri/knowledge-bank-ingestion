import importlib.util
import json
import stat
from pathlib import Path

import bcrypt
import pytest
from dotenv import dotenv_values

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/setup_socratic_auth.py"
spec = importlib.util.spec_from_file_location("socratic_setup", SCRIPT)
assert spec and spec.loader
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def test_local_setup_dry_run_and_apply_are_private_and_preserve_settings(tmp_path, monkeypatch):
    target = tmp_path / ".env"
    target.write_text("UNRELATED=keep\n")
    keys = setup.prepare(target, "local", "http://127.0.0.1:5186")
    assert "SOCRATIC_LOCAL_PASSWORD_HASH" in keys
    assert target.read_text() == "UNRELATED=keep\n"
    monkeypatch.setattr(setup.getpass, "getpass", lambda prompt: "a-local-test-password")
    setup.prepare(target, "local", "http://127.0.0.1:5186", apply=True)
    values = dotenv_values(target, interpolate=False)
    assert values["UNRELATED"] == "keep"
    assert json.loads(values["SOCRATIC_ALLOWED_ORIGINS"]) == ["http://127.0.0.1:5186"]
    assert values["SOCRATIC_COOKIE_SECURE"] == "false"
    assert bcrypt.checkpw(b"a-local-test-password", values["SOCRATIC_LOCAL_PASSWORD_HASH"].encode())
    assert "a-local-test-password" not in target.read_text()
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    before = target.read_text()
    setup.prepare(target, "local", "http://127.0.0.1:5186", apply=True)
    assert target.read_text() == before


def test_cognito_setup_copies_only_selected_identity_keys(tmp_path):
    source, target = tmp_path / "source.env", tmp_path / "target.env"
    source.write_text("COGNITO_USER_POOL_ID=us-east-2_fixture\nCOGNITO_CLIENT_ID=fixture-client\n"
                      "COGNITO_CLIENT_SECRET=synthetic-client-secret\nAWS_SECRET_ACCESS_KEY=do-not-copy\n")
    setup.prepare(target, "cognito", "https://studio.example.test", source=source,
                  aws_profile="aws-sutanu-admin", apply=True)
    values = dotenv_values(target, interpolate=False)
    assert values["COGNITO_REGION"] == "us-east-2"
    assert values["SOCRATIC_AWS_PROFILE"] == "aws-sutanu-admin"
    assert "AWS_SECRET_ACCESS_KEY" not in values
    assert len(values["SOCRATIC_CSRF_SECRET"]) >= 32
    assert values["SOCRATIC_COOKIE_SECURE"] == "true"


@pytest.mark.parametrize("mode,origin", [
    ("local", "https://remote.example.test"), ("cognito", "http://remote.example.test"),
    ("local", "http://localhost:5186/path"), ("local", "http://[broken"),
])
def test_invalid_setup_never_changes_target(tmp_path, mode, origin):
    target = tmp_path / ".env"
    target.write_text("UNRELATED=keep\n")
    with pytest.raises(ValueError):
        setup.prepare(target, mode, origin, apply=True)
    assert target.read_text() == "UNRELATED=keep\n"


def test_incomplete_cognito_source_does_not_write_anything(tmp_path):
    target, source = tmp_path / ".env", tmp_path / "source"
    source.write_text("COGNITO_CLIENT_ID=only-client\n")
    with pytest.raises(ValueError):
        setup.prepare(target, "cognito", "http://localhost:5186", source=source, apply=True)
    assert not target.exists()


def test_generated_password_is_saved_hashed_and_rotates_without_prompt(tmp_path, monkeypatch):
    target = tmp_path / ".env"
    target.write_text("UNRELATED=keep\n")
    monkeypatch.setattr(setup.getpass, "getpass", lambda prompt: pytest.fail("must not prompt"))
    keys = setup.prepare(target, "local", "http://127.0.0.1:5186", generate_password=True)
    assert "SOCRATIC_LOCAL_PASSWORD" in keys and target.read_text() == "UNRELATED=keep\n"
    setup.prepare(target, "local", "http://127.0.0.1:5186", generate_password=True, apply=True)
    first = dotenv_values(target, interpolate=False)
    password = first["SOCRATIC_LOCAL_PASSWORD"]
    assert 12 <= len(password.encode()) <= 72
    assert bcrypt.checkpw(password.encode(), first["SOCRATIC_LOCAL_PASSWORD_HASH"].encode())
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    setup.prepare(target, "local", "http://127.0.0.1:5186", generate_password=True, apply=True)
    second = dotenv_values(target, interpolate=False)
    assert second["SOCRATIC_LOCAL_PASSWORD"] != password
    assert not bcrypt.checkpw(password.encode(), second["SOCRATIC_LOCAL_PASSWORD_HASH"].encode())


def test_credentials_only_preserves_cognito_mode_and_origins(tmp_path):
    target = tmp_path / ".env"
    target.write_text('SOCRATIC_AUTH_MODE="cognito"\nSOCRATIC_ALLOWED_ORIGINS=\'["http://127.0.0.1:5186"]\'\n'
                      'SOCRATIC_COOKIE_SECURE="false"\nSOCRATIC_SESSION_SECONDS="600"\n')
    setup.prepare(target, "local", "http://127.0.0.1:5186", generate_password=True,
                  credentials_only=True, apply=True)
    values = dotenv_values(target, interpolate=False)
    assert values["SOCRATIC_AUTH_MODE"] == "cognito"
    assert values["SOCRATIC_SESSION_SECONDS"] == "600"
    assert values["SOCRATIC_LOCAL_USERNAME"] == "local-author"
    assert bcrypt.checkpw(values["SOCRATIC_LOCAL_PASSWORD"].encode(),
                          values["SOCRATIC_LOCAL_PASSWORD_HASH"].encode())


def test_generation_is_rejected_for_cognito_mode(tmp_path):
    with pytest.raises(ValueError):
        setup.prepare(tmp_path / ".env", "cognito", "https://studio.example.test", generate_password=True)
