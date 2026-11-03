"""Learner store, identity area (requirement 71 WP5; requirement 70 C1 access patterns A1-A5, write paths T1-T6).

``IdentityPostgres`` delegates to ``db/learner.py`` at call time (behaviour unchanged, monkeypatched tests keep working).
``IdentityDynamoDB`` is the ``mb-learner`` implementation on ``LearnerUnitOfWork`` and the typed profile model: every path is a
GetItem or one ``TransactWriteItems``, never a scan, never PostgreSQL.

Operations (a method is a read exactly when its name starts with a ``stores.READ_PREFIXES`` entry):

* reads   ``get_student_status`` (A1), ``get_student_token_version`` (A1), ``get_student_by_email`` (A2), ``get_student_profile`` (A3),
          ``get_student_by_cognito_sub`` (A4)
* writes  ``create_student`` (T1), ``create_student_for_cognito`` (T2), ``touch_last_login`` (T3), ``set_student_status`` (T4),
          ``update_profile`` (T5), ``change_password`` (T6)

Differences from PostgreSQL that callers can observe (all listed in the WP5 report):

* e-mail addresses are normalised (trim + lower case) for the uniqueness sentinel and the lookups;
* ``token_version`` exists only in DynamoDB: a password change or a disable bumps it and every token minted earlier stops working. The
  PostgreSQL table has no such column, so there a password change cannot revoke older tokens;
* ``touch_last_login`` does not bump the profile ``version`` (a login must not fail a concurrent profile edit);
* the ``mb-audit`` row of T4 is added through ``IdentityDynamoDB._audit_ops`` (empty until the audit store of WP9 lands).
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from mathbank_rest import security
from mathbank_rest.models.ddb.learner import LearnerUniqueCognitoSub, LearnerUniqueEmail
from mathbank_rest.models.manual.learner_identity import (
    COGNITO_PASSWORD,
    IdentityProfile,
    LearnerRatePw,
)
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.errors import (
    ConditionFailed,
    NotFound,
    StoreError,
    UniqueViolation,
    ValidationFailed,
)
from mathbank_rest.stores.learner.uow import CTX, LearnerUnitOfWork, with_retries

LOG = logging.getLogger(__name__)

PASSWORD_WINDOW_SECONDS = 15 * 60
PASSWORD_MAX_ATTEMPTS = 5
ANONYMOUS_DOMAIN = "mathbank.anonymous.invalid"
TERMINAL_STATUSES = ("DELETED", "ERASING")


class EmailAlreadyRegistered(HTTPException):
    """Onboarding found an account with this e-mail that this Cognito identity may not take over (same body as ``db.learner``)."""

    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            detail={
                "code": "EMAIL_ALREADY_REGISTERED",
                "message": "an account with this email already exists; sign in with its password",
            },
        )


class CurrentPasswordIncorrect(StoreError):
    status_code = 403
    code = "current_password_incorrect"


class PasswordNotSet(StoreError):
    """Password change on an account that signs in through Cognito (no local password)."""

    status_code = 409
    code = "password_not_set"


class RateLimited(StoreError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, retry_after: float, message: str = ""):
        super().__init__(message, retry_after=max(1, int(retry_after)))
        self.retry_after = max(1, int(retry_after))

    def headers(self) -> dict[str, str]:
        return {"Retry-After": str(self.retry_after)}


# ------------------------------------------------------------------------------------------------ shared helpers

def normalize_email(email: str) -> str:
    return email.strip().lower()


def display_name_of(first_name: str, last_name: str) -> str:
    return f"{first_name} {last_name}".strip() or "Student"


def search_blob(email_lc: str, first_name: str, last_name: str, display_name: str) -> str:
    """Same recipe as the migration (mathbank-db/aws/dynamo/specs/learner.py): lower-cased non-empty parts joined by a space."""
    return " ".join(x.strip().lower() for x in (email_lc, first_name, last_name, display_name) if x and x.strip())


def is_password_hash(password_hash: str | None) -> bool:
    """A real bcrypt hash; Cognito rows carry ``!COGNITO`` (DynamoDB) or random hex (PostgreSQL)."""
    return bool(password_hash) and password_hash.startswith("$2")


def _db():
    from mathbank_rest.db import learner

    return learner


# ------------------------------------------------------------------------------------------------ postgres

_pw_lock = threading.Lock()
_pw_attempts: dict[str, deque[float]] = defaultdict(deque)


def _pw_rate_limit(student_id: UUID | str) -> None:
    """Per-process window (the PostgreSQL deployment is a single service); the DynamoDB store uses a ``RATE#pw`` item instead."""
    now = time.time()
    with _pw_lock:
        window = _pw_attempts[str(student_id)]
        while window and window[0] <= now - PASSWORD_WINDOW_SECONDS:
            window.popleft()
        if len(window) >= PASSWORD_MAX_ATTEMPTS:
            raise RateLimited(window[0] + PASSWORD_WINDOW_SECONDS - now)
        window.append(now)


class IdentityPostgres:
    """Postgres backend: calls today's functions at call time (monkeypatched tests keep working)."""

    def get_student_status(self, student_id: UUID) -> str | None:
        return _db().get_student_status(student_id)

    def get_student_token_version(self, student_id: UUID) -> int:
        return 0                                    # the PostgreSQL profile has no token_version column

    def get_student_by_email(self, email: str) -> dict | None:
        return _db().get_student_by_email(email)

    def get_student_profile(self, student_id: UUID) -> dict | None:
        return _db().get_student_profile(student_id)

    def get_student_by_cognito_sub(self, cognito_sub: str) -> dict | None:
        return _db().get_student_by_cognito_sub(cognito_sub)

    def create_student(self, *, email: str, password_hash: str, first_name: str, last_name: str) -> dict:
        try:
            return _db().create_student(email=email, password_hash=password_hash, first_name=first_name, last_name=last_name)
        except IntegrityError:
            raise UniqueViolation("email", email) from None

    def create_student_for_cognito(self, **kwargs: Any) -> dict:
        return _db().create_student_for_cognito(**kwargs)

    def touch_last_login(self, student_id: UUID) -> None:
        _db().touch_last_login(student_id)

    def set_student_status(self, student_id: UUID, new_status: str, actor_id: str) -> dict | None:
        return _db().set_student_status(student_id, new_status, actor_id)

    def update_profile(self, student_id: UUID, changes: dict) -> dict | None:
        return _db().update_student_profile(student_id, changes)

    def change_password(self, student_id: UUID, *, current_password: str, new_password: str) -> dict:
        _pw_rate_limit(student_id)
        current = _db().get_student_password_hash(student_id)
        if current is None:
            raise NotFound("student")
        if not is_password_hash(current):
            raise PasswordNotSet("this account signs in through its identity provider")
        if not security.verify_password(current_password, current):
            raise CurrentPasswordIncorrect("current password is incorrect")
        _db().set_student_password_hash(student_id, security.hash_password(new_password))
        return {"token_version": 0}


# ------------------------------------------------------------------------------------------------ dynamodb

def _profile_dict(p: IdentityProfile) -> dict:
    """The ``GET /v1/learner/me`` shape of ``db.learner.get_student_profile``."""
    return {"student_id": p.student_id, "email": p.email, "first_name": p.first_name, "last_name": p.last_name,
            "display_name": p.display_name, "status": p.status, "created_at": p.created_at, "last_login_at": p.last_login_at,
            "grade": p.grade, "phone": p.phone}


def _cognito_dict(p: IdentityProfile) -> dict:
    return {"student_id": p.student_id, "email": p.email, "first_name": p.first_name, "last_name": p.last_name,
            "display_name": p.display_name, "grade": p.grade, "phone": p.phone, "status": p.status}


def _login_dict(p: IdentityProfile) -> dict:
    return {"student_id": p.student_id, "email": p.email, "password_hash": p.password_hash, "first_name": p.first_name,
            "last_name": p.last_name, "display_name": p.display_name, "status": p.status, "token_version": p.token_version}


def _expected(profile: IdentityProfile) -> dict | None:
    return {"version": profile.version} if profile.version is not None else None


class IdentityDynamoDB:
    """DynamoDB backend over mb-learner."""

    # -- reads (A1-A4) -----------------------------------------------------------------------------------------------

    @staticmethod
    def _load(student_id: UUID | str) -> IdentityProfile | None:
        return typed.get(IdentityProfile, ddb.student_pk(student_id), "PROFILE")

    def _by_email_lc(self, email_lc: str) -> IdentityProfile | None:
        pk, sk = ddb.unique_key("email", email_lc)
        sentinel = typed.get(LearnerUniqueEmail, pk, sk)
        return None if sentinel is None else self._load(sentinel.student_id)

    def _by_cognito_sub(self, cognito_sub: str) -> IdentityProfile | None:
        pk, sk = ddb.unique_key("cognito_sub", cognito_sub)
        sentinel = typed.get(LearnerUniqueCognitoSub, pk, sk)
        return None if sentinel is None else self._load(sentinel.student_id)

    def get_student_status(self, student_id: UUID) -> str | None:
        profile = self._load(student_id)
        return None if profile is None else profile.status

    def get_student_token_version(self, student_id: UUID) -> int:
        profile = self._load(student_id)
        return 0 if profile is None else profile.token_version

    def get_student_by_email(self, email: str) -> dict | None:
        profile = self._by_email_lc(normalize_email(email))
        return None if profile is None else _login_dict(profile)

    def get_student_profile(self, student_id: UUID) -> dict | None:
        profile = self._load(student_id)
        return None if profile is None else _profile_dict(profile)

    def get_student_by_cognito_sub(self, cognito_sub: str) -> dict | None:
        profile = self._by_cognito_sub(str(cognito_sub).lower())
        return None if profile is None else _cognito_dict(profile)

    # -- T1 ----------------------------------------------------------------------------------------------------------

    @staticmethod
    def _new_profile(*, student_id: UUID, email: str, password_hash: str, first_name: str, last_name: str, display_name: str,
                     grade: str | None = None, phone: str | None = None, is_anonymous: bool = False,
                     cognito_sub: UUID | None = None) -> IdentityProfile:
        lc = normalize_email(email)
        return IdentityProfile(
            PK=ddb.student_pk(student_id), SK="PROFILE", student_id=student_id, email=email.strip(), email_lc=lc,
            password_hash=password_hash, first_name=first_name, last_name=last_name, display_name=display_name, status="ACTIVE",
            token_version=0, is_anonymous=is_anonymous, created_at=datetime.now(UTC),
            search_blob=search_blob(lc, first_name, last_name, display_name), version=1, grade=grade, phone=phone,
            cognito_sub=cognito_sub, GSI2PK="STUDENT_DIR", GSI2SK=f"{lc}#{student_id}")

    def create_student(self, *, email: str, password_hash: str, first_name: str, last_name: str) -> dict:
        """PROFILE + e-mail sentinel in one transaction; a taken address is a clean ``UniqueViolation('email')`` (409), also under a race."""
        sid = uuid4()
        profile = self._new_profile(student_id=sid, email=email, password_hash=password_hash, first_name=first_name,
                                    last_name=last_name, display_name=display_name_of(first_name, last_name))
        uow = LearnerUnitOfWork(sid)
        uow.put_new(profile)
        uow.sentinel("email", profile.email_lc, {"student_id": str(sid)})
        uow.commit()
        return {"student_id": sid, "email": profile.email, "first_name": first_name, "last_name": last_name,
                "display_name": profile.display_name, "status": profile.status, "created_at": profile.created_at}

    # -- T2 ----------------------------------------------------------------------------------------------------------

    def create_student_for_cognito(
        self, *, cognito_sub: str | None, first_name: str, last_name: str, grade: str | None = None, email: str | None = None,
        phone: str | None = None, is_anonymous: bool = False, email_verified: bool = False,
    ) -> dict:
        """Onboarding (new profile, or link of an existing password account). The WP1 rules hold: an existing address is returned only
        when it is already bound to this ``cognito_sub``, linked only when the caller vouches ``email_verified`` and the account has no
        Cognito identity yet, and otherwise refused with 409 ``EMAIL_ALREADY_REGISTERED`` with the profile untouched."""
        try:
            sub = None if cognito_sub is None else UUID(str(cognito_sub))
        except ValueError:
            raise ValidationFailed("cognito_sub must be a UUID") from None
        display_name = display_name_of(first_name, last_name)
        email = email or f"anon-{sub or uuid4()}@{ANONYMOUS_DOMAIN}"
        email_lc = normalize_email(email)

        def attempt() -> dict:
            existing = self._by_email_lc(email_lc)
            if existing is None:
                bound = None if sub is None else self._by_cognito_sub(str(sub))
                if bound is not None:                               # the same identity onboarded earlier (under another address)
                    return _cognito_dict(bound)
                sid = uuid4()
                profile = self._new_profile(student_id=sid, email=email, password_hash=COGNITO_PASSWORD, first_name=first_name,
                                            last_name=last_name, display_name=display_name, grade=grade, phone=phone,
                                            is_anonymous=is_anonymous, cognito_sub=sub)
                uow = LearnerUnitOfWork(sid)
                uow.put_new(profile)
                uow.sentinel("email", email_lc, {"student_id": str(sid)})
                if sub is not None:
                    uow.sentinel("cognito_sub", str(sub), {"student_id": str(sid)})
                uow.commit()
                return _cognito_dict(profile)
            if sub is not None and existing.cognito_sub == sub:
                return _cognito_dict(existing)
            if sub is None or existing.cognito_sub is not None or not email_verified:
                raise EmailAlreadyRegistered()
            uow = LearnerUnitOfWork(existing.student_id)
            uow.update(IdentityProfile, existing.PK, "PROFILE", {"cognito_sub": sub}, expected=_expected(existing),
                       cond=ddb.Cond("attribute_not_exists(cognito_sub)"))
            uow.sentinel("cognito_sub", str(sub), {"student_id": str(existing.student_id)})
            uow.commit()
            return _cognito_dict(existing)

        return with_retries(attempt, on=(ConditionFailed, UniqueViolation))

    # -- T3 ----------------------------------------------------------------------------------------------------------

    def touch_last_login(self, student_id: UUID) -> None:
        stamp = typed.validate_changes(IdentityProfile, {"last_login_at": datetime.now(UTC)})["last_login_at"]
        op = ddb.Update(CTX, ddb.student_pk(student_id), "PROFILE", "SET #ll = :t",
                        names={"#ll": "last_login_at", "#st": "status"}, values={":t": stamp, ":active": "ACTIVE"},
                        cond=ddb.Cond("attribute_exists(PK) AND #st = :active"), label="touch_last_login")
        try:
            ddb.transact([op])
        except ConditionFailed:
            LOG.info("last_login_at not stamped: student %s is missing or not ACTIVE", student_id)

    # -- T4 ----------------------------------------------------------------------------------------------------------

    def _audit_ops(self, actor_id: str, action: str, student_id: UUID, before: dict, after: dict) -> list[ddb.TxOp]:
        """Extra ops for the same transaction (the ``mb-audit`` row of requirement 70 T4). Empty until the audit store lands (WP9)."""
        LOG.info("audit %s by %s on student %s: %s -> %s", action, actor_id, student_id, before, after)
        return []

    def set_student_status(self, student_id: UUID, new_status: str, actor_id: str) -> dict | None:
        """Disable or re-enable an account (None = no such student; ``ValueError`` for a deleted or erasing one). Disabling bumps
        ``token_version`` so every token issued before stops working even after a re-enable."""
        if new_status not in ("ACTIVE", "DISABLED"):
            raise ValueError(f"unsupported status {new_status!r}")

        def attempt() -> dict | None:
            profile = self._load(student_id)
            if profile is None:
                return None
            if profile.status in TERMINAL_STATUSES:
                raise ValueError("account is deleted")
            if profile.status == new_status:
                return {"student_id": profile.student_id, "status": profile.status, "disabled_at": profile.disabled_at}
            disabling = new_status == "DISABLED"
            disabled_at = datetime.now(UTC) if disabling else None
            changes: dict[str, Any] = {"status": new_status}
            if disabling:
                changes["disabled_at"] = disabled_at
            uow = LearnerUnitOfWork(student_id)
            uow.update(IdentityProfile, profile.PK, "PROFILE", changes, expected=_expected(profile),
                       cond=ddb.Cond("#st = :from", {"#st": "status"}, {":from": profile.status}),
                       increment={"token_version": 1} if disabling else None, remove=() if disabling else ("disabled_at",))
            for op in self._audit_ops(actor_id, "STUDENT_DISABLED" if disabling else "STUDENT_ENABLED", student_id,
                                      {"status": profile.status}, {"status": new_status}):
                uow.add(op)
            uow.commit()
            return {"student_id": profile.student_id, "status": new_status, "disabled_at": disabled_at}

        return with_retries(attempt)

    # -- T5 ----------------------------------------------------------------------------------------------------------

    def update_profile(self, student_id: UUID, changes: dict) -> dict | None:
        """PATCH /v1/learner/me: names, grade, phone and (optionally) display name; ``display_name`` and ``search_blob`` are recomputed.
        A ``None`` value clears an optional attribute. Returns the new profile (the ``/me`` shape) or None for an unknown student."""
        editable = {"first_name", "last_name", "display_name", "grade", "phone"}
        if set(changes) - editable:
            raise ValidationFailed(f"not editable: {sorted(set(changes) - editable)}")

        def attempt() -> dict | None:
            profile = self._load(student_id)
            if profile is None:
                return None
            values = dict(changes)
            if not values:
                return _profile_dict(profile)
            first = values.get("first_name", profile.first_name)
            last = values.get("last_name", profile.last_name)
            if "display_name" not in values and ("first_name" in values or "last_name" in values):
                values["display_name"] = display_name_of(first, last)
            display_name = values.get("display_name", profile.display_name)
            sets = {k: v for k, v in values.items() if v is not None}
            sets["search_blob"] = search_blob(profile.email_lc, first, last, display_name)
            uow = LearnerUnitOfWork(student_id)
            uow.update(IdentityProfile, profile.PK, "PROFILE", sets, expected=_expected(profile),
                       remove=tuple(k for k, v in values.items() if v is None))
            uow.commit()
            return {**_profile_dict(profile), **values}

        return with_retries(attempt)

    # -- T6 ----------------------------------------------------------------------------------------------------------

    def _count_password_attempt(self, student_id: UUID) -> None:
        """Fixed window of 5 attempts per 15 minutes in ``STUDENT#sid / RATE#pw`` (expires through ``ttl``)."""
        pk = ddb.student_pk(student_id)
        for _ in range(3):
            now = int(time.time())
            cutoff = now - PASSWORD_WINDOW_SECONDS
            bump = ddb.Update(CTX, pk, "RATE#pw", "SET #c = #c + :one", names={"#c": "count", "#w": "window_start"},
                              values={":one": 1, ":max": PASSWORD_MAX_ATTEMPTS, ":cut": cutoff},
                              cond=ddb.Cond("attribute_exists(PK) AND #w > :cut AND #c < :max"), label="rate:pw")
            try:
                ddb.transact([bump])
                return
            except ConditionFailed:
                pass
            current = typed.get(LearnerRatePw, pk, "RATE#pw")
            if current is not None and current.window_start > cutoff:
                raise RateLimited(current.window_start + PASSWORD_WINDOW_SECONDS - now)
            try:
                typed.put(LearnerRatePw(PK=pk, SK="RATE#pw", count=1, window_start=now, ttl=now + PASSWORD_WINDOW_SECONDS),
                          cond=ddb.Cond("attribute_not_exists(PK) OR #w <= :cut", {"#w": "window_start"}, {":cut": cutoff}))
                return
            except ConditionFailed:
                continue
        raise RateLimited(PASSWORD_WINDOW_SECONDS)

    def change_password(self, student_id: UUID, *, current_password: str, new_password: str) -> dict:
        """Verify the current password in code, then replace the hash and bump ``token_version`` (all older tokens stop working) in one
        conditional update. Cognito accounts (``!COGNITO``) have no password: 409. Wrong current password: 403. Rate limited: 429."""
        self._count_password_attempt(student_id)
        profile = self._load(student_id)
        if profile is None:
            raise NotFound("student")
        if not is_password_hash(profile.password_hash):
            raise PasswordNotSet("this account signs in through its identity provider")
        if not security.verify_password(current_password, profile.password_hash):
            raise CurrentPasswordIncorrect("current password is incorrect")
        uow = LearnerUnitOfWork(student_id)
        uow.update(IdentityProfile, profile.PK, "PROFILE", {"password_hash": security.hash_password(new_password)},
                   expected=_expected(profile) or {"password_hash": profile.password_hash},
                   cond=ddb.Cond("#ph <> :cog", {"#ph": "password_hash"}, {":cog": COGNITO_PASSWORD}),
                   increment={"token_version": 1})
        uow.commit()
        return {"token_version": profile.token_version + 1}
