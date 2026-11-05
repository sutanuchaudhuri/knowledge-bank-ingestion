"""HTTP client for the API under test: records every exchange (method, path, status, latency) for the report."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class Exchange:
    suite: str
    case: str
    method: str
    path: str
    status: int | None
    ms: int
    ok: bool
    note: str = ""
    body: str = ""            # truncated response body, kept for failures only


@dataclass
class Recorder:
    exchanges: list[Exchange] = field(default_factory=list)
    suite: str = ""

    def add(self, **kw) -> Exchange:
        e = Exchange(suite=kw.pop("suite", self.suite), **kw)
        self.exchanges.append(e)
        return e

    @property
    def failures(self) -> list[Exchange]:
        return [e for e in self.exchanges if not e.ok]


class Api:
    """Thin wrapper over httpx. `call()` never raises on HTTP errors; `expect()` records pass/fail against allowed statuses."""

    def __init__(self, base: str, rec: Recorder, *, admin_key: str = "", timeout: float = 120.0):
        self.base, self.rec, self.admin_key = base.rstrip("/"), rec, admin_key
        self.http = httpx.Client(base_url=self.base, timeout=timeout)

    def headers(self, token: str | None = None, *, admin: bool = False, extra: dict[str, str] | None = None) -> dict[str, str]:
        h: dict[str, str] = {}
        if token:
            h["Authorization"] = f"Bearer {token}"
        if admin and self.admin_key:
            h["X-Admin-Api-Key"] = self.admin_key
        h.update(extra or {})
        return h

    def call(self, method: str, path: str, *, token: str | None = None, admin: bool = False, json: Any = None,
             params: dict | None = None, idem: bool = False, headers: dict[str, str] | None = None) -> tuple[httpx.Response | None, int, str]:
        h = self.headers(token, admin=admin, extra=headers)
        if idem and "Idempotency-Key" not in h:
            h["Idempotency-Key"] = str(uuid.uuid4())
        t0 = time.perf_counter()
        try:
            r = self.http.request(method, path, headers=h, json=json, params=params)
            return r, int((time.perf_counter() - t0) * 1000), ""
        except httpx.HTTPError as exc:
            return None, int((time.perf_counter() - t0) * 1000), f"{type(exc).__name__}: {exc}"

    def expect(self, case: str, method: str, path: str, ok: set[int] | int | range, *, suite: str = "", note: str = "",
               **kw) -> httpx.Response | None:
        """Call and record; ok statuses may be an int, a set or a range. Returns the response (None on transport failure)."""
        allowed = {ok} if isinstance(ok, int) else set(ok)
        r, ms, err = self.call(method, path, **kw)
        status = r.status_code if r is not None else None
        good = status in allowed
        detail = err or note
        if r is not None and not good:
            detail = (detail + " " if detail else "") + f"expected {sorted(allowed)}"
        self.rec.add(suite=suite or self.rec.suite, case=case, method=method, path=path, status=status, ms=ms, ok=good,
                     note=detail, body="" if good or r is None else r.text[:600])
        return r
