"""Shared helper that converts a stubbed service function's `NotImplementedError` into a
structured `501` response body (`contracts.MLUnavailable`) instead of a bare FastAPI 500.

Kept in its own module (not in `main.py`) so router modules can import it without a
circular import on `main` (which itself imports the routers to register them).
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from fastapi.responses import JSONResponse

from mathbank_ml_inference.contracts import MLUnavailable

T = TypeVar("T")


def call_stubbed(fn: Callable[[], T], *, todo_ref: str, design_doc_ref: str):
    """Calls `fn()`. If it raises NotImplementedError (every service function in this
    package does, until requirements/56's real logic is implemented), returns a 501 with
    a structured body instead of propagating a bare 500. Once a given service function is
    actually implemented, this wrapper becomes a no-op pass-through — no router code needs
    to change when that happens.
    """
    try:
        return fn()
    except NotImplementedError:
        return JSONResponse(
            status_code=501,
            content=MLUnavailable(todo_ref=todo_ref, design_doc_ref=design_doc_ref).model_dump(),
        )
