"""Thin async HTTP wrapper around mathbank-rest's existing public `/v1/*` read endpoints.

requirements/49 (citing the fastmcp-intellitutor pack's doc 01 §4, "Domain service
boundary"): FastMCP tools must call the *existing* MathBank service layer, never
reimplement grading/retrieval/query logic or talk to Postgres directly. This module is
that boundary — every function here is a single `httpx` call to an already-implemented,
already-tested `mathbank-rest` endpoint (see mathbank-rest/src/mathbank_rest/routers/v1.py),
nothing more.

All wrapped endpoints are public, read-only, and require no admin/student auth — this
server exposes the same corpus data anyone can already read from mathbank-web's `/db/*`
pages, just over MCP instead of HTTP+React, for consumption by any MCP-capable agent
(not only `mathbank-agent`).
"""
from __future__ import annotations

import httpx

from mathbank_mcp_competitions.config import get_settings


class RestClient:
    def __init__(self, base_url: str | None = None):
        self._base_url = (base_url or get_settings().mathbank_rest_base_url).rstrip("/")

    async def list_competitions(self) -> list[dict]:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=15.0) as client:
            response = await client.get("/v1/competitions")
            response.raise_for_status()
            return response.json()

    async def list_problems(
        self,
        *,
        competition: str | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        concept: str | None = None,
        technique: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> list[dict]:
        params = {
            "competition": competition,
            "year_min": year_min,
            "year_max": year_max,
            "concept": concept,
            "technique": technique,
            "limit": limit,
            "offset": offset,
        }
        params = {k: v for k, v in params.items() if v is not None}
        async with httpx.AsyncClient(base_url=self._base_url, timeout=15.0) as client:
            response = await client.get("/v1/problems", params=params)
            response.raise_for_status()
            return response.json()

    async def get_problem(self, canonical_code: str) -> dict | None:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=15.0) as client:
            response = await client.get(f"/v1/problems/by-code/{canonical_code}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()

    async def search_problems(
        self, *, query: str, competition: str | None = None,
        year_min: int | None = None, year_max: int | None = None, limit: int = 10,
    ) -> list[dict]:
        body = {
            "query": query,
            "filters": {
                "competition": competition,
                "year_min": year_min,
                "year_max": year_max,
            },
            "limit": limit,
        }
        async with httpx.AsyncClient(base_url=self._base_url, timeout=30.0) as client:
            response = await client.post("/v1/search/problems", json=body)
            response.raise_for_status()
            return response.json()["results"]

    async def list_concepts(self, *, domain: str | None = None, limit: int = 50) -> list[dict]:
        params = {"limit": limit}
        if domain:
            params["domain"] = domain
        async with httpx.AsyncClient(base_url=self._base_url, timeout=15.0) as client:
            response = await client.get("/v1/concepts", params=params)
            response.raise_for_status()
            return response.json()

    async def list_techniques(self, *, q: str | None = None, limit: int = 50) -> list[dict]:
        params = {"limit": limit}
        if q:
            params["q"] = q
        async with httpx.AsyncClient(base_url=self._base_url, timeout=15.0) as client:
            response = await client.get("/v1/techniques", params=params)
            response.raise_for_status()
            return response.json()

    # --- requirements/60 §7: admin-scoped scene-promotion operations -----------------
    # These wrap mathbank-rest's /v1/admin/interaction-templates/scenes/* endpoints,
    # which are auth-gated (X-Admin-Api-Key) at mathbank-rest itself — the tools that
    # call these methods are therefore "admin-scoped" only in the sense that the caller
    # must supply a valid key as an explicit argument; this server does not duplicate or
    # bypass that check (FastMCP's own "visibility is not security" principle, requirements/
    # 49 §1, applies here: the tool is visible to any agent, but inert without the key).

    async def list_promotable_scenes(self, *, admin_api_key: str) -> list[dict]:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=15.0) as client:
            response = await client.get(
                "/v1/admin/interaction-templates/scenes/promotable-candidates",
                headers={"X-Admin-Api-Key": admin_api_key},
            )
            response.raise_for_status()
            return response.json()

    async def promote_scene(
        self, *, render_job_id: str, canonical_code: str, admin_api_key: str,
        created_by: str = "mcp-agent",
    ) -> dict:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=30.0) as client:
            response = await client.post(
                "/v1/admin/interaction-templates/scenes/promote",
                json={"render_job_id": render_job_id, "canonical_code": canonical_code,
                      "created_by": created_by},
                headers={"X-Admin-Api-Key": admin_api_key},
            )
            response.raise_for_status()
            return response.json()

    async def validate_scene(self, *, scene_spec_id: str, admin_api_key: str) -> dict:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=15.0) as client:
            response = await client.post(
                f"/v1/admin/interaction-templates/scenes/{scene_spec_id}/validate",
                headers={"X-Admin-Api-Key": admin_api_key},
            )
            response.raise_for_status()
            return response.json()

    async def approve_scene(self, *, scene_spec_id: str, admin_api_key: str) -> dict:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=15.0) as client:
            response = await client.post(
                f"/v1/admin/interaction-templates/scenes/{scene_spec_id}/approve",
                headers={"X-Admin-Api-Key": admin_api_key},
            )
            response.raise_for_status()
            return response.json()


_client: RestClient | None = None


def get_rest_client() -> RestClient:
    global _client
    if _client is None:
        _client = RestClient()
    return _client
