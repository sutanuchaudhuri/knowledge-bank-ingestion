"""Store flags, selection, freeze proxy and HTTP error mapping (requirement 71 §2.2)."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mathbank_rest import stores
from mathbank_rest.config import settings
from mathbank_rest.stores import errors as E


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    stores.reset_for_tests()
    saved = {c: stores.IMPLEMENTATIONS[c].copy() for c in stores.CONTEXTS}
    monkeypatch.setattr(settings, "store_flags_ssm_prefix", "")
    yield
    stores.reset_for_tests()
    for c, v in saved.items():
        stores.IMPLEMENTATIONS[c] = v


class FakeStore:
    def __init__(self):
        self.calls = []

    def get_thing(self, i):
        self.calls.append(("get", i))
        return {"id": i}

    def list_things(self):
        return [1, 2]

    def create_thing(self, i):
        self.calls.append(("create", i))

    def update_thing(self, i):
        self.calls.append(("update", i))


@pytest.mark.parametrize("value,expected", [
    ("postgres", ("postgres", "postgres")), ("dynamodb", ("dynamodb", "dynamodb")), ("DynamoDB", ("dynamodb", "dynamodb")),
    ("frozen", ("frozen", "postgres")), ("frozen:dynamodb", ("frozen", "dynamodb")), ("", ("postgres", "postgres"))])
def test_parse_mode(value, expected):
    assert stores.parse_mode(value) == expected


@pytest.mark.parametrize("bad", ["mongo", "frozen:mongo", "fro"])
def test_parse_mode_rejects_unknown(bad):
    with pytest.raises(ValueError):
        stores.parse_mode(bad)


def test_defaults_keep_todays_behaviour_for_every_context():
    for ctx in stores.CONTEXTS:
        assert stores.store_mode(ctx) == ("postgres", "postgres")
    assert settings.vector_store == "pgvector"


def test_unknown_context_is_rejected():
    with pytest.raises(KeyError):
        stores.store_mode("nope")


def test_unimplemented_backend_is_a_clear_501_not_a_silent_fallback(monkeypatch):
    monkeypatch.setattr(settings, "live_store", "dynamodb")
    with pytest.raises(E.StoreNotImplemented) as e:
        stores.get_store("live")
    assert e.value.status_code == 501 and e.value.detail == {"context": "live", "backend": "dynamodb"}


def test_registered_implementation_is_selected_by_flag(monkeypatch):
    stores.register_implementation("live", "postgres", f"{__name__}:FakeStore")
    assert isinstance(stores.get_store("live"), FakeStore)
    monkeypatch.setattr(settings, "live_store", "dynamodb")
    with pytest.raises(E.StoreNotImplemented):
        stores.get_store("live")


def test_override_store_wins_and_restores():
    fake = FakeStore()
    with stores.override_store("live", fake):
        assert stores.get_store("live") is fake
    with pytest.raises(E.StoreNotImplemented):
        stores.get_store("live")


def test_frozen_serves_reads_and_blocks_writes(monkeypatch):
    stores.register_implementation("media", "postgres", f"{__name__}:FakeStore")
    monkeypatch.setattr(settings, "media_store", "frozen")
    s = stores.get_store("media")
    assert s.get_thing(7) == {"id": 7} and s.list_things() == [1, 2]
    for write in (lambda: s.create_thing(1), lambda: s.update_thing(1)):
        with pytest.raises(E.StoreFrozen) as e:
            write()
    assert e.value.status_code == 503 and e.value.headers() == {"Retry-After": "30"}
    assert s._inner.calls == [("get", 7)]  # the blocked writes never reached the store


def test_ssm_flag_overrides_settings_and_is_cached(monkeypatch):
    import boto3
    from moto import mock_aws

    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.setenv(k, "x")
    monkeypatch.setattr(settings, "ddb_region", "us-east-2")
    monkeypatch.setattr(settings, "store_flags_ssm_prefix", "/mathbank/ut/stores")
    monkeypatch.setattr(settings, "store_flags_refresh_seconds", 3600)
    monkeypatch.setattr(stores, "_ssm", None)
    with mock_aws():
        ssm = boto3.client("ssm", region_name="us-east-2")
        ssm.put_parameter(Name="/mathbank/ut/stores/exam", Value="frozen:dynamodb", Type="String")
        assert stores.store_mode("exam") == ("frozen", "dynamodb")
        ssm.put_parameter(Name="/mathbank/ut/stores/exam", Value="dynamodb", Type="String", Overwrite=True)
        assert stores.store_mode("exam") == ("frozen", "dynamodb")        # cached for the refresh window
        stores._cache.clear()
        assert stores.store_mode("exam") == ("dynamodb", "dynamodb")      # refreshed
        assert stores.store_mode("live") == ("postgres", "postgres")      # no parameter -> settings value


def test_unreadable_ssm_flag_never_takes_the_api_down(monkeypatch):
    monkeypatch.setattr(settings, "store_flags_ssm_prefix", "/mathbank/ut/stores")
    monkeypatch.setattr(settings, "exam_store", "dynamodb")

    class Boom:
        def get_parameter(self, **_):
            raise RuntimeError("ssm down")

    monkeypatch.setattr(stores, "_ssm", Boom())
    assert stores.store_mode("exam") == ("dynamodb", "dynamodb")


def test_describe_reports_every_context_and_vectors():
    d = stores.describe()
    assert set(d) == {*stores.CONTEXTS, "vectors"} and d["vectors"] == {"backend": "pgvector"}
    assert d["live"] == {"mode": "postgres", "backend": "postgres", "implemented": False}
    assert d["learner"]["implemented"] is True


# ---------------------------------------------------------------- HTTP mapping

def _app(exc):
    app = FastAPI()
    E.install_error_handlers(app)

    @app.get("/x")
    def x():
        raise exc

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("exc,status,body", [
    (E.NotFound("gone"), 404, {"detail": "not_found"}),
    (E.RevisionConflict(8), 409, {"detail": "revision_conflict", "current_revision": 8}),
    (E.UniqueViolation("email", "a@b"), 409, {"detail": "unique_violation", "field": "email"}),
    (E.ConditionFailed("no"), 409, {"detail": "condition_failed"}),
    (E.IdempotencyKeyReused("k"), 422, {"detail": "idempotency_key_reused"}),
    (E.ValidationFailed("bad", field="x"), 422, {"detail": "validation_failed", "field": "x"}),
    (E.InvalidToken("t"), 400, {"detail": "invalid_next_token"}),
    (E.StoreUnavailable("down"), 503, {"detail": "store_unavailable"}),
    (E.StoreNotImplemented("n", context="c"), 501, {"detail": "store_not_implemented", "context": "c"}),
])
def test_http_mapping(exc, status, body):
    r = _app(exc).get("/x")
    assert r.status_code == status and r.json() == body


def test_frozen_maps_to_503_with_retry_after():
    r = _app(E.StoreFrozen("learner", retry_after=45)).get("/x")
    assert r.status_code == 503 and r.headers["retry-after"] == "45" and r.json()["context"] == "learner"
