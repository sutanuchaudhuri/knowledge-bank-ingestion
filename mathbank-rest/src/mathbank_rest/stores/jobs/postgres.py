"""``jobs`` store, PostgreSQL-era backend: REST's view of the Studio queue as it is today.

The Studio tables (``studio.scene_research_job`` / ``studio.video_render_job``) and the ``FOR UPDATE SKIP LOCKED`` claims
belong to mathbank-manim-studio; REST has only ever used the Studio's HTTP API (see ``scene_spec_promotion``). This class is
that client behind the store interface, so callers do not care which backend is selected. Worker operations
(claim/heartbeat/complete/fail...) do not exist here: the Studio worker owns them while it polls Postgres.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

import httpx

from mathbank_rest.config import settings
from mathbank_rest.stores.errors import (
    ConditionFailed,
    NotFound,
    StoreNotImplemented,
    StoreUnavailable,
    ValidationFailed,
)

_TS = ("created_at", "updated_at", "expires_at")


def _ts(value: Any) -> Any:
    return dt.datetime.fromisoformat(value) if isinstance(value, str) else value


def _research_row(body: dict) -> dict:
    row = {"scene_research_job_id": body["id"], "context_json": body.get("context"),
           **{k: v for k, v in body.items() if k not in ("id", "context")}}
    return {**row, **{k: _ts(row[k]) for k in _TS if k in row}}


def _render_row(body: dict) -> dict:
    row = {"video_render_job_id": body["id"], **{k: v for k, v in body.items() if k != "id"}}
    return {**row, **{k: _ts(row[k]) for k in _TS if k in row}}


class PostgresJobsStore:
    backend = "postgres"

    def __init__(self, base_url: str | None = None, *, timeout: float = 10.0):
        self._base = (base_url or settings.manim_studio_base_url).rstrip("/")
        self._timeout = timeout

    # ------------------------------------------------------------------ HTTP

    def _request(self, method: str, path: str, *, ok_404: bool = False, **kw: Any) -> Any:
        try:
            r = httpx.request(method, f"{self._base}{path}", timeout=self._timeout, **kw)
        except httpx.HTTPError as exc:
            raise StoreUnavailable(f"manim studio unreachable: {exc.__class__.__name__}") from None
        if r.status_code == 404:
            if ok_404:
                return None
            raise NotFound(path)
        if r.status_code == 409:
            raise ConditionFailed(r.json().get("detail", "conflict") if r.content else "conflict")
        if r.status_code == 422:
            raise ValidationFailed("studio rejected the request")
        if r.status_code >= 400:
            raise StoreUnavailable(f"manim studio answered {r.status_code}")
        return r.json()

    # ------------------------------------------------------------------ writes

    def create_research_job(self, topic: str, context: dict | None = None, *, requested_by: str | None = None) -> dict:
        return _research_row(self._request("POST", "/v1/research-jobs", json={"topic": topic, "context": context or {}}))

    def create_render_job(self, scene_spec_json: dict | None = None, source_research_job_id: str | None = None, *,
                          requested_by: str | None = None) -> dict:
        body = {"research_job_id": source_research_job_id} if source_research_job_id else {"scene_spec_json": scene_spec_json}
        return _render_row(self._request("POST", "/v1/render-jobs", json=body))

    def mark_render_job_promoted(self, job_id: str, scene_spec_id: str) -> dict:
        return _render_row(self._request("POST", f"/v1/render-jobs/{job_id}/mark-promoted", json={"scene_spec_id": scene_spec_id},
                                         headers={"X-Admin-Api-Key": settings.admin_api_key}))

    # ------------------------------------------------------------------ reads

    def get_research_job(self, job_id: str) -> dict | None:
        body = self._request("GET", f"/v1/research-jobs/{job_id}", ok_404=True)
        return None if body is None else _research_row(body)

    def get_render_job(self, job_id: str) -> dict | None:
        body = self._request("GET", f"/v1/render-jobs/{job_id}", ok_404=True)
        return None if body is None else _render_row(body)

    def get_job(self, kind: str, job_id: str) -> dict | None:
        return self.get_research_job(job_id) if kind == "research" else self.get_render_job(job_id)

    def list_render_jobs(self, *, status: str | None = None, unpromoted_only: bool = False, limit: int = 50) -> list[dict]:
        params: dict[str, Any] = {"unpromoted_only": unpromoted_only}
        if status:
            params["status"] = status
        return [_render_row(b) for b in self._request("GET", "/v1/render-jobs", params=params)][:limit]

    def list_jobs(self, kind: str, *, status: str | None = None, unpromoted_only: bool = False,
                  requested_by: str | None = None, limit: int = 50, next_token: str | None = None) -> dict:
        if kind != "render":
            raise StoreNotImplemented("the Studio has no research-job listing endpoint", context="jobs", backend="postgres")
        return {"items": self.list_render_jobs(status=status, unpromoted_only=unpromoted_only, limit=limit), "next_token": None}

    # ------------------------------------------------------------------ worker operations (Studio-owned on Postgres)

    def _worker_only(self, *_a: Any, **_k: Any) -> Any:
        raise StoreNotImplemented("claim/complete/fail run inside the Studio worker (FOR UPDATE SKIP LOCKED) on the postgres "
                                  "backend", context="jobs", backend="postgres")

    claim = heartbeat = complete = fail = cancel = retry = enqueue = republish_pending = _worker_only
