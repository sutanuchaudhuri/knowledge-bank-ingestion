"""Domain errors raised by the store layer and their HTTP mapping (requirement 71 §2.2).

Stores raise these instead of HTTPException or driver errors (guide §2: services raise domain errors, the
router maps them). `install_error_handlers(app)` registers the mapping once per app, so every router gets the
same 404/409/422/503 behaviour whichever backend served the request.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class StoreError(Exception):
    """Base class; `status_code` and `body()` define the HTTP mapping."""

    status_code = 500
    code = "store_error"

    def __init__(self, message: str = "", **detail):
        super().__init__(message or self.code)
        self.message = message or self.code
        self.detail = detail

    def body(self) -> dict:
        return {"detail": self.code, **self.detail}

    def headers(self) -> dict[str, str]:
        return {}


class NotFound(StoreError):
    status_code = 404
    code = "not_found"


class RevisionConflict(StoreError):
    """Optimistic concurrency failed: the item changed since `expected_revision` was read."""

    status_code = 409
    code = "revision_conflict"

    def __init__(self, current_revision: int | None = None, message: str = ""):
        super().__init__(message, current_revision=current_revision)
        self.current_revision = current_revision


class UniqueViolation(StoreError):
    """A uniqueness sentinel already exists (replaces PostgreSQL UNIQUE)."""

    status_code = 409
    code = "unique_violation"

    def __init__(self, field: str, value: str | None = None, message: str = ""):
        super().__init__(message, field=field)
        self.field, self.value = field, value


class ConditionFailed(StoreError):
    """A transaction condition other than a version check failed (state precondition)."""

    status_code = 409
    code = "condition_failed"


class IdempotencyKeyReused(StoreError):
    """Same Idempotency-Key with a different request body."""

    status_code = 422
    code = "idempotency_key_reused"


class ValidationFailed(StoreError):
    status_code = 422
    code = "validation_failed"


class InvalidToken(StoreError):
    """Tampered, expired or foreign pagination token."""

    status_code = 400
    code = "invalid_next_token"


class StoreFrozen(StoreError):
    """The context is in its cutover freeze window: writes are rejected, reads continue."""

    status_code = 503
    code = "store_frozen"

    def __init__(self, context: str, retry_after: int = 30):
        super().__init__(f"{context} is frozen", context=context)
        self.retry_after = retry_after

    def headers(self) -> dict[str, str]:
        return {"Retry-After": str(self.retry_after)}


class StoreUnavailable(StoreError):
    status_code = 503
    code = "store_unavailable"


class StoreNotImplemented(StoreError):
    """The selected backend has no implementation for this context yet (work package not landed)."""

    status_code = 501
    code = "store_not_implemented"


def install_error_handlers(app: FastAPI) -> None:
    async def _handler(_: Request, exc: StoreError) -> JSONResponse:
        return JSONResponse(exc.body(), status_code=exc.status_code, headers=exc.headers())

    app.add_exception_handler(StoreError, _handler)
