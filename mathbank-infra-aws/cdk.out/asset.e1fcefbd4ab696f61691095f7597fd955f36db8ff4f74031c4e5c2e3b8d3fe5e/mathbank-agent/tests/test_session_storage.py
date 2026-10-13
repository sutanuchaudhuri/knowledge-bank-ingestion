import os
from uuid import uuid4

import pytest
from google.adk.events import Event, EventActions

import session_config


def test_url_uses_shell_and_escapes_password(monkeypatch):
    monkeypatch.setattr(session_config, "dotenv_values", lambda path: {})
    for key, value in {
        "POSTGRES_HOST": "localhost", "POSTGRES_PORT": "5433",
        "POSTGRES_DB": "mathbank", "POSTGRES_USER": "test",
        "POSTGRES_PASSWORD": "fake:@/?secret", "POSTGRES_SSLMODE": "disable",
    }.items():
        monkeypatch.setenv(key, value)
    url = session_config.session_database_url()
    assert url.drivername == "postgresql+psycopg"
    assert url.password == "fake:@/?secret"
    assert "fake:@" not in url.render_as_string(hide_password=False)
    assert url.query["sslmode"] == "disable"


def test_missing_settings_fail_without_local_fallback(monkeypatch):
    monkeypatch.setattr(session_config, "dotenv_values", lambda path: {})
    for key in ("POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError, match="Agent sessions require"):
        session_config.session_database_url()


def test_configuration_precedence(monkeypatch):
    def values(path):
        base = {"POSTGRES_HOST": "rest-host", "POSTGRES_DB": "test",
                "POSTGRES_USER": "test", "POSTGRES_PASSWORD": "fake"}
        if path == session_config.ROOT.parent / "mathbank-rest" / ".env":
            return base
        if path == session_config.ROOT.parent / ".env":
            return {"POSTGRES_HOST": "root-host"}
        return {"POSTGRES_HOST": "agent-host"}

    monkeypatch.setattr(session_config, "dotenv_values", values)
    for key in ("POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    assert session_config.session_database_url().host == "agent-host"
    monkeypatch.setenv("POSTGRES_HOST", "shell-host")
    assert session_config.session_database_url().host == "shell-host"


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("MATHBANK_TEST_POSTGRES") != "1", reason="live Postgres opt-in")
async def test_postgres_session_event_and_state_survive_new_service():
    url = session_config.session_database_url()
    session_config.prepare_session_schema(url)
    identity = dict(app_name="mathbank_tutor", user_id="storage-integration-test",
                    session_id=f"test-{uuid4()}")
    first = session_config.create_session_service(url)
    second = None
    try:
        session = await first.create_session(**identity, state={"probe": "created"})
        await first.append_event(session, Event(
            invocation_id="storage-probe", author="mathbank_tutor",
            actions=EventActions(state_delta={"probe": "persisted"}),
        ))
        await first.close()
        second = session_config.create_session_service(url)
        stored = await second.get_session(**identity)
        assert stored is not None
        assert stored.state["probe"] == "persisted"
        assert len(stored.events) == 1
        assert stored.events[0].invocation_id == "storage-probe"
        assert await second.get_session(**{**identity, "user_id": "different-user"}) is None
    finally:
        cleanup = second or first
        await cleanup.delete_session(**identity)
        await cleanup.close()
