"""WP5 identity area of the learner store on moto (requirement 70 C1 access patterns A1-A4, write paths T1-T6).

Sequential races (two requests built from the same stale read) cover the conditional paths; the threaded variant that needs real
DynamoDB transactions is marked ``ddb_integration`` and runs only against the ``test`` environment (``make test-ddb-integration``).
"""
from __future__ import annotations

import threading
import time
import uuid

import pytest
from fastapi import HTTPException

from mathbank_rest import security, stores
from mathbank_rest.models.ddb.learner import LearnerUniqueCognitoSub, LearnerUniqueEmail
from mathbank_rest.models.manual.learner_identity import IdentityProfile, LearnerRatePw
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import typed
from mathbank_rest.stores.errors import ItemSchemaError, NotFound, UniqueViolation, ValidationFailed
from mathbank_rest.stores.learner.identity import (
    CurrentPasswordIncorrect,
    EmailAlreadyRegistered,
    IdentityDynamoDB,
    IdentityPostgres,
    PasswordNotSet,
    RateLimited,
    is_password_hash,
    normalize_email,
    search_blob,
)

PASSWORD = "correct horse battery"


@pytest.fixture()
def store(ddb):
    return IdentityDynamoDB()


def register(store, email="Ada.Lovelace@Example.org", first="Ada", last="Lovelace", password=PASSWORD) -> dict:
    return store.create_student(email=email, password_hash=security.hash_password(password), first_name=first, last_name=last)


def profile_item(sid) -> IdentityProfile:
    return typed.require(IdentityProfile, toolkit.student_pk(sid), "PROFILE")


def keys(ddb_client, table="mb-learner-ut") -> set[tuple[str, str]]:
    items = ddb_client.scan(TableName=table)["Items"]          # test-only inspection of a moto table
    return {(i["PK"]["S"], i["SK"]["S"]) for i in items}


# ------------------------------------------------------------------------------------------------ T1 / A2 / A3

def test_register_writes_profile_and_email_sentinel_and_reads_back(store):
    created = register(store)
    sid = created["student_id"]
    assert created["display_name"] == "Ada Lovelace" and created["status"] == "ACTIVE"
    item = profile_item(sid)
    assert (item.email, item.email_lc, item.token_version, item.version) == ("Ada.Lovelace@Example.org", "ada.lovelace@example.org", 0, 1)
    assert item.GSI2PK == "STUDENT_DIR" and item.GSI2SK == f"ada.lovelace@example.org#{sid}"
    assert item.search_blob == search_blob("ada.lovelace@example.org", "Ada", "Lovelace", "Ada Lovelace")
    assert is_password_hash(item.password_hash)
    pk, sk = toolkit.unique_key("email", "ada.lovelace@example.org")
    assert typed.require(LearnerUniqueEmail, pk, sk).student_id == sid

    by_email = store.get_student_by_email("  ADA.LOVELACE@example.ORG ")
    assert by_email["student_id"] == sid and by_email["status"] == "ACTIVE" and by_email["token_version"] == 0
    assert security.verify_password(PASSWORD, by_email["password_hash"])
    profile = store.get_student_profile(sid)
    assert set(profile) == {"student_id", "email", "first_name", "last_name", "display_name", "status", "created_at", "last_login_at",
                            "grade", "phone"}
    assert profile["last_login_at"] is None
    assert store.get_student_by_email("nobody@example.org") is None
    assert store.get_student_profile(uuid.uuid4()) is None


def test_duplicate_email_is_a_clean_unique_violation_and_leaves_no_orphan_profile(ddb, store):
    register(store)
    before = keys(ddb)
    with pytest.raises(UniqueViolation) as excinfo:
        register(store, email="ada.lovelace@EXAMPLE.org", first="Other")
    assert excinfo.value.field == "email" and excinfo.value.status_code == 409
    assert keys(ddb) == before                                      # the failed transaction wrote nothing


def test_status_and_token_version_reads(store):
    sid = register(store)["student_id"]
    assert store.get_student_status(sid) == "ACTIVE" and store.get_student_token_version(sid) == 0
    assert store.get_student_status(uuid.uuid4()) is None and store.get_student_token_version(uuid.uuid4()) == 0


def test_postgres_store_maps_a_unique_race_to_unique_violation(monkeypatch):
    from sqlalchemy.exc import IntegrityError

    from mathbank_rest.db import learner as learner_db

    def boom(**_):
        raise IntegrityError("insert", {}, Exception("duplicate key"))

    monkeypatch.setattr(learner_db, "create_student", boom)
    with pytest.raises(UniqueViolation):
        IdentityPostgres().create_student(email="a@x.org", password_hash="h", first_name="A", last_name="B")


# ------------------------------------------------------------------------------------------------ T2 / A4

SUB = "5d8e4b5e-0f2c-4d3a-9a57-0d1f0c1b2a3c"
OTHER_SUB = "9f0a1b2c-3d4e-4f50-8a61-72839405a6b7"


def onboard(store, **kw) -> dict:
    return store.create_student_for_cognito(**{"cognito_sub": SUB, "first_name": "Grace", "last_name": "Hopper",
                                               "email": "grace@example.org", **kw})


def test_cognito_onboarding_creates_profile_with_both_sentinels_and_is_idempotent(ddb, store):
    created = onboard(store, grade="10", phone="555-0100")
    assert created["display_name"] == "Grace Hopper" and created["grade"] == "10" and created["phone"] == "555-0100"
    item = profile_item(created["student_id"])
    assert item.password_hash == "!COGNITO" and item.cognito_sub == uuid.UUID(SUB) and item.is_anonymous is False
    pk, sk = toolkit.unique_key("cognito_sub", SUB)
    assert typed.require(LearnerUniqueCognitoSub, pk, sk).student_id == created["student_id"]
    assert store.get_student_by_cognito_sub(SUB.upper())["student_id"] == created["student_id"]
    before = keys(ddb)
    again = onboard(store)
    assert again["student_id"] == created["student_id"] and keys(ddb) == before


def test_anonymous_onboarding_gets_a_placeholder_address_each_time(store):
    one = store.create_student_for_cognito(cognito_sub=None, first_name="", last_name="", is_anonymous=True)
    two = store.create_student_for_cognito(cognito_sub=None, first_name="", last_name="", is_anonymous=True)
    assert one["student_id"] != two["student_id"] and one["display_name"] == "Student"
    assert one["email"].endswith("@mathbank.anonymous.invalid") and profile_item(one["student_id"]).is_anonymous is True


def test_existing_password_account_is_linked_only_when_verified_and_unbound(store):
    victim = register(store, email="victim@example.org")
    with pytest.raises(EmailAlreadyRegistered):                      # not verified: refused, profile untouched
        onboard(store, email="victim@example.org")
    assert profile_item(victim["student_id"]).cognito_sub is None
    linked = onboard(store, email="victim@example.org", email_verified=True)
    assert linked["student_id"] == victim["student_id"]
    item = profile_item(victim["student_id"])
    assert item.cognito_sub == uuid.UUID(SUB) and item.version == 2 and item.password_hash != "!COGNITO"
    assert store.get_student_by_cognito_sub(SUB)["student_id"] == victim["student_id"]
    with pytest.raises(EmailAlreadyRegistered):                      # bound to another identity: never taken over
        onboard(store, cognito_sub=OTHER_SUB, email="victim@example.org", email_verified=True)
    with pytest.raises(EmailAlreadyRegistered):                      # anonymous callers cannot claim a real address
        store.create_student_for_cognito(cognito_sub=None, first_name="X", last_name="Y", email="victim@example.org",
                                         email_verified=True)


def test_link_race_loses_cleanly_and_the_winner_stays(store, monkeypatch):
    victim = register(store, email="victim@example.org")
    stale = profile_item(victim["student_id"])
    real_by_email = store._by_email_lc
    calls = []

    def stale_first(lc):                                             # the loser reads the profile before the winner links it
        calls.append(lc)
        return stale if len(calls) == 1 else real_by_email(lc)

    onboard(store, cognito_sub=OTHER_SUB, email="victim@example.org", email_verified=True)    # the winner
    monkeypatch.setattr(store, "_by_email_lc", stale_first)
    with pytest.raises(EmailAlreadyRegistered):                      # stale link fails its condition, the retry sees the winner
        onboard(store, email="victim@example.org", email_verified=True)
    assert profile_item(victim["student_id"]).cognito_sub == uuid.UUID(OTHER_SUB)


def test_a_sub_already_onboarded_under_another_address_returns_that_profile(store):
    first = onboard(store)
    same_identity = onboard(store, email="grace.new@example.org")
    assert same_identity["student_id"] == first["student_id"]


def test_non_uuid_sub_is_a_422(store):
    with pytest.raises(ValidationFailed):
        onboard(store, cognito_sub="not-a-uuid")


def test_email_already_registered_has_the_postgres_body():
    exc = EmailAlreadyRegistered()
    assert isinstance(exc, HTTPException) and exc.status_code == 409
    assert exc.detail["code"] == "EMAIL_ALREADY_REGISTERED"


# ------------------------------------------------------------------------------------------------ T3

def test_touch_last_login_stamps_without_bumping_the_version_and_skips_inactive(store):
    sid = register(store)["student_id"]
    store.touch_last_login(sid)
    item = profile_item(sid)
    assert item.last_login_at is not None and item.version == 1
    store.set_student_status(sid, "DISABLED", "service:admin-key")
    stamped = profile_item(sid).last_login_at
    time.sleep(0.01)
    store.touch_last_login(sid)                                      # DISABLED: condition fails, silently ignored
    assert profile_item(sid).last_login_at == stamped
    store.touch_last_login(uuid.uuid4())                             # unknown student: still silent


# ------------------------------------------------------------------------------------------------ T4

def test_disable_and_enable_cycle_bumps_token_version_once_and_audits(store, monkeypatch):
    audited = []
    monkeypatch.setattr(store, "_audit_ops", lambda *a: audited.append(a) or [])
    sid = register(store)["student_id"]
    disabled = store.set_student_status(sid, "DISABLED", "staff:7")
    item = profile_item(sid)
    assert disabled["status"] == "DISABLED" and disabled["disabled_at"] is not None
    assert (item.status, item.token_version, item.version) == ("DISABLED", 1, 2) and item.disabled_at is not None
    assert store.set_student_status(sid, "DISABLED", "staff:7")["status"] == "DISABLED"       # idempotent: no second bump
    assert profile_item(sid).token_version == 1
    enabled = store.set_student_status(sid, "ACTIVE", "staff:7")
    item = profile_item(sid)
    assert enabled == {"student_id": sid, "status": "ACTIVE", "disabled_at": None}
    assert (item.status, item.token_version, item.version) == ("ACTIVE", 1, 3) and item.disabled_at is None
    assert [a[1] for a in audited] == ["STUDENT_DISABLED", "STUDENT_ENABLED"]


def test_status_change_edge_cases(store):
    sid = register(store)["student_id"]
    assert store.set_student_status(uuid.uuid4(), "DISABLED", "x") is None
    with pytest.raises(ValueError):
        store.set_student_status(sid, "DELETED", "x")
    typed.update(IdentityProfile, toolkit.student_pk(sid), "PROFILE", 1, {"status": "ERASING"})
    with pytest.raises(ValueError, match="deleted"):
        store.set_student_status(sid, "ACTIVE", "x")


def test_status_change_retries_when_the_profile_moved_under_it(store, monkeypatch):
    sid = register(store)["student_id"]
    stale = profile_item(sid)
    store.update_profile(sid, {"grade": "9"})                        # version 1 -> 2 after the stale read
    reads = []
    real = IdentityDynamoDB._load

    def stale_first(student_id):
        reads.append(1)
        return stale if len(reads) == 1 else real(student_id)

    monkeypatch.setattr(IdentityDynamoDB, "_load", staticmethod(stale_first))
    assert store.set_student_status(sid, "DISABLED", "x")["status"] == "DISABLED"
    assert len(reads) == 2 and profile_item(sid).grade == "9"


# ------------------------------------------------------------------------------------------------ T5

def test_update_profile_recomputes_display_name_and_search_blob_and_bumps_version(store):
    sid = register(store)["student_id"]
    updated = store.update_profile(sid, {"first_name": "Augusta", "grade": "11", "phone": "555-0111"})
    item = profile_item(sid)
    assert updated["display_name"] == "Augusta Lovelace" == item.display_name
    assert updated["grade"] == "11" and updated["phone"] == "555-0111" and updated["email"] == "Ada.Lovelace@Example.org"
    assert item.search_blob == search_blob("ada.lovelace@example.org", "Augusta", "Lovelace", "Augusta Lovelace") and item.version == 2
    cleared = store.update_profile(sid, {"grade": None, "display_name": "Countess"})
    item = profile_item(sid)
    assert cleared["grade"] is None and item.grade is None and item.display_name == "Countess" and item.version == 3
    assert store.update_profile(sid, {})["display_name"] == "Countess" and profile_item(sid).version == 3
    assert store.update_profile(uuid.uuid4(), {"grade": "1"}) is None
    with pytest.raises(ValidationFailed):
        store.update_profile(sid, {"email": "evil@example.org"})
    with pytest.raises(ItemSchemaError):                             # an over-long value never reaches the table
        store.update_profile(sid, {"grade": "x" * 51})
    assert profile_item(sid).version == 3


def test_concurrent_profile_edits_both_apply(store, monkeypatch):
    sid = register(store)["student_id"]
    stale = profile_item(sid)
    store.update_profile(sid, {"phone": "555"})
    reads = []
    real = IdentityDynamoDB._load
    monkeypatch.setattr(IdentityDynamoDB, "_load", staticmethod(lambda s: (reads.append(1), stale if len(reads) == 1 else real(s))[1]))
    store.update_profile(sid, {"grade": "8"})
    item = profile_item(sid)
    assert (item.phone, item.grade, item.version) == ("555", "8", 3)


# ------------------------------------------------------------------------------------------------ T6

def test_change_password_verifies_old_bumps_token_version_and_replaces_the_hash(store):
    sid = register(store)["student_id"]
    result = store.change_password(sid, current_password=PASSWORD, new_password="a brand new password")
    item = profile_item(sid)
    assert result == {"token_version": 1} and item.token_version == 1 and item.version == 2
    assert security.verify_password("a brand new password", item.password_hash)
    assert not security.verify_password(PASSWORD, item.password_hash)


def test_change_password_refusals(store):
    sid = register(store)["student_id"]
    with pytest.raises(CurrentPasswordIncorrect) as wrong:
        store.change_password(sid, current_password="nope", new_password="a brand new password")
    assert wrong.value.status_code == 403
    assert profile_item(sid).token_version == 0
    cognito = onboard(store)["student_id"]
    with pytest.raises(PasswordNotSet) as no_password:
        store.change_password(cognito, current_password="x", new_password="a brand new password")
    assert no_password.value.status_code == 409
    with pytest.raises(NotFound):
        store.change_password(uuid.uuid4(), current_password="x", new_password="a brand new password")


def test_password_attempts_are_rate_limited_per_student_then_the_window_reopens(store, monkeypatch):
    sid = register(store)["student_id"]
    other = register(store, email="other@example.org")["student_id"]
    for _ in range(5):
        with pytest.raises(CurrentPasswordIncorrect):
            store.change_password(sid, current_password="bad", new_password="a brand new password")
    with pytest.raises(RateLimited) as limited:
        store.change_password(sid, current_password=PASSWORD, new_password="a brand new password")
    assert limited.value.status_code == 429 and 0 < limited.value.retry_after <= 900
    assert limited.value.headers() == {"Retry-After": str(limited.value.retry_after)}
    assert profile_item(sid).token_version == 0                      # the correct password was refused while limited
    assert store.change_password(other, current_password=PASSWORD, new_password="a brand new password")["token_version"] == 1
    counter = typed.require(LearnerRatePw, toolkit.student_pk(sid), "RATE#pw")
    assert counter.count == 5 and counter.ttl == counter.window_start + 900
    later = time.time() + 901
    monkeypatch.setattr(time, "time", lambda: later)
    assert store.change_password(sid, current_password=PASSWORD, new_password="a brand new password")["token_version"] == 1
    assert typed.require(LearnerRatePw, toolkit.student_pk(sid), "RATE#pw").count == 1


# ------------------------------------------------------------------------------------------------ security: status and token version

@pytest.fixture()
def auth(store, monkeypatch):
    """The learner JWT dependency reading through the DynamoDB identity store (the suite-wide offline status stub is replaced)."""
    security._status_cache.clear()
    monkeypatch.setattr(security, "_load_student_status", lambda sid: security._learner_store().get_student_status(sid))
    with stores.override_store("learner", store):
        yield store
    security._status_cache.clear()


def bearer(sid, version=None):
    from fastapi.security import HTTPAuthorizationCredentials

    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=security.create_access_token(sid, token_version=version))


def test_password_change_invalidates_older_tokens(auth):
    sid = register(auth)["student_id"]
    old = bearer(sid, 0)
    assert security.get_current_student_id(old) == sid
    assert security.get_current_student_id(bearer(sid)) == sid          # no tv claim: accepted only while the version is 0
    new_version = auth.change_password(sid, current_password=PASSWORD, new_password="a brand new password")["token_version"]
    security.invalidate_student_status(sid)
    for stale in (old, bearer(sid)):
        with pytest.raises(HTTPException) as rejected:
            security.get_current_student_id(stale)
        assert rejected.value.status_code == 401
    assert security.get_current_student_id(bearer(sid, new_version)) == sid


def test_disable_rejects_tokens_even_after_reactivation(auth):
    sid = register(auth)["student_id"]
    token = bearer(sid, 0)
    assert security.get_current_student_id(token) == sid
    auth.set_student_status(sid, "DISABLED", "x")
    security.invalidate_student_status(sid)
    with pytest.raises(HTTPException) as rejected:
        security.get_current_student_id(token)
    assert rejected.value.status_code == 401
    auth.set_student_status(sid, "ACTIVE", "x")
    security.invalidate_student_status(sid)
    with pytest.raises(HTTPException):                                # token_version moved on at the disable
        security.get_current_student_id(token)
    assert security.get_current_student_id(bearer(sid, 1)) == sid


def test_unknown_student_is_401_and_a_store_outage_is_503(auth, monkeypatch):
    with pytest.raises(HTTPException) as unknown:
        security.get_current_student_id(bearer(uuid.uuid4(), 0))
    assert unknown.value.status_code == 401
    from botocore.exceptions import EndpointConnectionError

    def down(_sid):
        raise EndpointConnectionError(endpoint_url="https://dynamodb.invalid")

    monkeypatch.setattr(security, "_load_student_status", down)
    with pytest.raises(HTTPException) as unavailable:
        security.get_current_student_id(bearer(uuid.uuid4(), 0))
    assert unavailable.value.status_code == 503


def test_status_is_cached_per_process_for_the_configured_seconds(auth, monkeypatch):
    sid = register(auth)["student_id"]
    reads = []
    real = auth.get_student_status
    monkeypatch.setattr(auth, "get_student_status", lambda s: (reads.append(s), real(s))[1])
    token = bearer(sid, 0)
    for _ in range(3):
        security.get_current_student_id(token)
    assert len(reads) == 1


def test_dynamodb_identity_paths_never_touch_the_postgres_engine(auth, monkeypatch):
    from mathbank_rest.db import postgres

    class Boom:
        def __getattr__(self, name):
            raise AssertionError("PostgreSQL used by a DynamoDB identity path")

    monkeypatch.setattr(postgres, "engine", Boom())
    sid = register(auth)["student_id"]
    auth.get_student_by_email("ada.lovelace@example.org")
    auth.touch_last_login(sid)
    auth.update_profile(sid, {"grade": "9"})
    auth.change_password(sid, current_password=PASSWORD, new_password="a brand new password")
    auth.set_student_status(sid, "DISABLED", "x")
    assert auth.get_student_profile(sid)["status"] == "DISABLED"


def test_frozen_identity_store_serves_reads_and_rejects_writes(store):
    from mathbank_rest.stores.errors import StoreFrozen

    frozen = stores.FrozenProxy("learner", store)
    sid = register(store)["student_id"]
    assert frozen.get_student_profile(sid)["student_id"] == sid and frozen.get_student_status(sid) == "ACTIVE"
    for write in (lambda: frozen.touch_last_login(sid), lambda: frozen.update_profile(sid, {"grade": "9"}),
                  lambda: frozen.change_password(sid, current_password="x", new_password="y" * 8),
                  lambda: frozen.set_student_status(sid, "DISABLED", "x"), lambda: register(frozen)):
        with pytest.raises(StoreFrozen):
            write()


def test_normalisation_helpers():
    assert normalize_email("  A@B.Org ") == "a@b.org"
    assert not is_password_hash("!COGNITO") and not is_password_hash(None) and is_password_hash(security.hash_password("x"))


# ------------------------------------------------------------------------------------------------ real DynamoDB (test env only)

@pytest.mark.ddb_integration
def test_concurrent_registrations_of_one_email_create_exactly_one_account(real_env):
    email = f"race-{uuid.uuid4().hex[:10]}@example.org"
    store, results, barrier = IdentityDynamoDB(), [], threading.Barrier(6)

    def worker():
        barrier.wait()
        try:
            results.append(("ok", store.create_student(email=email, password_hash="$2b$12$x", first_name="R", last_name="S")))
        except UniqueViolation:
            results.append(("taken", None))

    threads = [threading.Thread(target=worker) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(r[0] for r in results) == ["ok"] + ["taken"] * 5
    winner = next(r[1] for r in results if r[0] == "ok")
    assert store.get_student_by_email(email)["student_id"] == winner["student_id"]


@pytest.mark.ddb_integration
def test_concurrent_cognito_links_of_one_account_pick_one_winner(real_env):
    store = IdentityDynamoDB()
    email = f"link-{uuid.uuid4().hex[:10]}@example.org"
    victim = store.create_student(email=email, password_hash="$2b$12$x", first_name="V", last_name="V")
    subs = [str(uuid.uuid4()) for _ in range(4)]
    barrier, results = threading.Barrier(4), []

    def worker(sub):
        barrier.wait()
        try:
            store.create_student_for_cognito(cognito_sub=sub, first_name="C", last_name="C", email=email, email_verified=True)
            results.append(sub)
        except EmailAlreadyRegistered:
            pass

    threads = [threading.Thread(target=worker, args=(s,)) for s in subs]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(results) == 1
    assert store.get_student_by_cognito_sub(results[0])["student_id"] == victim["student_id"]
