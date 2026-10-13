"""MathBank Competitions — a standalone FastMCP server (requirements/49, implementing a
scoped slice of the fastmcp-intellitutor pack: a *parallel* MCP surface any MCP-capable
agent can use to fetch competition/problem/concept/technique data, independent of
`mathbank-agent`'s own Google ADK tutoring stack — doc 49 §2's recommended "coexist as
distinct products" shape).

Two kinds of tools, per the pack's own architecture (01_FASTMCP_DECISION_ARCHITECTURE.md
§2):

1. Plain model-visible `@mcp.tool()` functions — for any MCP client/agent that just wants
   structured competition data (the literal "parallel MCP server ... to fetch competition
   specific data" ask). These never render UI; they return JSON.
2. A `FastMCPApp("mathbank-competitions-explorer")` with one Prefab `.ui()` entry point —
   the "prefab client rendered in HTML" ask — plus one app-only backend tool it calls for
   its one interactive action (switching competitions), per the pack's rule that
   authoritative/data-changing actions go through `FastMCPApp` backend tools, not
   client-only state (01 §6/§7).

Every tool/handler below calls `rest_client.py`, which itself only calls mathbank-rest's
existing, already-tested `/v1/*` endpoints — no SQL, no duplicated retrieval logic here
(the pack's "Domain service boundary" rule, 01 §4).
"""
from __future__ import annotations

from fastmcp import FastMCP, FastMCPApp
from prefab_ui.actions import SetState, ShowToast
from prefab_ui.actions.mcp import CallTool
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge,
    Column,
    DataTable,
    DataTableColumn,
    Heading,
    Row,
    Select,
    SelectOption,
    Text,
)
from prefab_ui.rx import EVENT, RESULT, Rx, STATE

from mathbank_mcp_competitions.rest_client import get_rest_client

# ---------------------------------------------------------------------------
# 2. Prefab UI — "prefab client rendered in HTML." Defined before `mcp` itself since
#    FastMCP mounts a FastMCPApp via its constructor's `providers=[...]` argument, so the
#    app and everything registered on it must exist first.
# ---------------------------------------------------------------------------

competitions_app = FastMCPApp("mathbank-competitions-explorer")


@competitions_app.tool()
async def load_competition_problems(competition: str) -> dict:
    """App-only backend tool: re-fetches the problem list for a newly-selected
    competition. Called by the Select's `on_change` handler below, never invoked
    directly by the model (it has no `@mcp.tool()` of its own — only the FastMCPApp
    registration, which is app-visible per 01_FASTMCP_DECISION_ARCHITECTURE.md §5)."""
    problems = await get_rest_client().list_problems(competition=competition, limit=25)
    return {"competition": competition, "problems": problems}


def _problem_columns() -> list[DataTableColumn]:
    return [
        DataTableColumn(key="canonical_code", header="Code", sortable=True),
        DataTableColumn(key="problem_number", header="#", align="right"),
        DataTableColumn(key="year", header="Year", sortable=True),
        DataTableColumn(key="official_answer", header="Answer"),
    ]


@competitions_app.ui()
async def open_competition_explorer(competition: str = "AMC10") -> PrefabApp:
    """Model-visible Prefab entry point: renders a competition picker plus a searchable,
    paginated table of problems for the selected competition. Initial data is fetched
    server-side (once, here) exactly like the pack's own `open_course` example in
    03_STUDENT_INTELLITUTOR_PREFAB_UI.md §5; subsequent competition changes round-trip
    through `load_competition_problems` above rather than being client-only, since
    fetching a *different* competition's data is a real data operation, not local
    presentation state (01 §6/§7's client-vs-server-state rule).
    """
    client = get_rest_client()
    competitions = await client.list_competitions()
    problems = await client.list_problems(competition=competition, limit=25)

    with Column(gap=4, css_class="p-6") as view:
        with Row(gap=2, align="center"):
            Heading("MathBank Competition Explorer")
            Badge(Rx("problems.length"))
        with Row(gap=2, align="center"):
            Text("Competition")
            with Select(
                name="competition",
                on_change=CallTool(
                    load_competition_problems,
                    arguments={"competition": EVENT.target.value},
                    on_success=[
                        SetState("problems", RESULT.problems),
                        SetState("competition", RESULT.competition),
                    ],
                    on_error=ShowToast("Could not load that competition", variant="error"),
                ),
            ):
                for item in competitions:
                    SelectOption(
                        value=item["external_code"], label=item["name"],
                        selected=(item["external_code"] == competition),
                    )
        DataTable(
            columns=_problem_columns(),
            rows=STATE.problems,
            search=True,
            paginated=True,
            page_size=10,
        )

    return PrefabApp(
        title="MathBank Competition Explorer",
        view=view,
        state={"competition": competition, "problems": problems},
    )


# ---------------------------------------------------------------------------
# Server + 1. Plain data-fetch tools — "other agents" (any MCP client) use these
# directly. Defined after `mcp` so they can use the `@mcp.tool()` decorator.
# ---------------------------------------------------------------------------

mcp = FastMCP("MathBank Competitions", providers=[competitions_app])


@mcp.tool()
async def list_competitions() -> list[dict]:
    """Lists every competition in the corpus (AMC10/AMC12/AIME/HMMT/etc.) with its
    external code, display name, and level. Call this first to discover valid
    `competition` codes for the other tools."""
    return await get_rest_client().list_competitions()


@mcp.tool()
async def list_problems(
    competition: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    concept: str | None = None,
    technique: str | None = None,
    limit: int = 25,
) -> list[dict]:
    """Lists problems, optionally filtered by competition code (e.g. "AMC10"), year
    range, a concept slug, or a technique slug. Does not include the full problem
    statement — call `get_problem` with a `canonical_code` from this list for that."""
    return await get_rest_client().list_problems(
        competition=competition, year_min=year_min, year_max=year_max,
        concept=concept, technique=technique, limit=min(limit, 200),
    )


@mcp.tool()
async def get_problem(canonical_code: str) -> dict:
    """Fetches one problem's full detail by its canonical code (e.g.
    "AMC10_2000_Q01") — statement text, official answer, source URL, and its mapped
    concepts/techniques."""
    problem = await get_rest_client().get_problem(canonical_code)
    if problem is None:
        raise ValueError(f"No problem found with canonical_code={canonical_code!r}")
    return problem


@mcp.tool()
async def search_problems(
    query: str, competition: str | None = None,
    year_min: int | None = None, year_max: int | None = None, limit: int = 10,
) -> list[dict]:
    """Hybrid (semantic + lexical + graph) search over problem statements. Use this
    instead of `list_problems` when the caller describes a topic/idea rather than
    giving exact filter values (e.g. "a geometry problem about an inscribed circle")."""
    return await get_rest_client().search_problems(
        query=query, competition=competition, year_min=year_min, year_max=year_max,
        limit=min(limit, 50),
    )


@mcp.tool()
async def list_concepts(domain: str | None = None, limit: int = 50) -> list[dict]:
    """Lists canonical concept taxonomy entries, optionally filtered by domain."""
    return await get_rest_client().list_concepts(domain=domain, limit=min(limit, 200))


@mcp.tool()
async def list_techniques(q: str | None = None, limit: int = 50) -> list[dict]:
    """Lists canonical solution techniques, optionally filtered by a free-text query."""
    return await get_rest_client().list_techniques(q=q, limit=min(limit, 200))


# ---------------------------------------------------------------------------
# 2. Admin-scoped scene-catalog-promotion tools (requirements/60 §7). These wrap
# mathbank-rest's auth-gated /v1/admin/interaction-templates/scenes/* endpoints — the
# caller must supply a real admin_api_key argument (the same shared secret
# mathbank-web's admin UI sends as an X-Admin-Api-Key header); the key is validated by
# mathbank-rest itself, never by this server. This is the pattern this project's own
# README documents for FastMCP's "visibility is not security" principle (requirements/
# 49 §1): the tool is visible to any agent, but does nothing useful without the secret.
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_promotable_scenes(admin_api_key: str) -> list[dict]:
    """Lists finished, not-yet-promoted Manim Video Studio (requirements/60) render
    jobs — candidates an admin agent can promote into the canonical scene catalog with
    `promote_scene_to_catalog`. Requires a valid admin_api_key."""
    return await get_rest_client().list_promotable_scenes(admin_api_key=admin_api_key)


@mcp.tool()
async def promote_scene_to_catalog(
    render_job_id: str, canonical_code: str, admin_api_key: str,
) -> dict:
    """Promotes one finished Manim Video Studio render job into a new DRAFT row in the
    canonical `visual.scene_spec` catalog (requirements/41 ITL-4), storing its rendered
    video. Returns {"scene_spec_id", "status": "DRAFT"}. The new row still needs
    `validate_scene_in_catalog` + `approve_scene_in_catalog` before it is APPROVED.
    Requires a valid admin_api_key."""
    return await get_rest_client().promote_scene(
        render_job_id=render_job_id, canonical_code=canonical_code,
        admin_api_key=admin_api_key,
    )


@mcp.tool()
async def validate_scene_in_catalog(scene_spec_id: str, admin_api_key: str) -> dict:
    """Runs mathbank-rest's structural validator (duplicate/unknown object ids) against
    a DRAFT catalog scene, without changing its status. Requires a valid admin_api_key."""
    return await get_rest_client().validate_scene(
        scene_spec_id=scene_spec_id, admin_api_key=admin_api_key,
    )


@mcp.tool()
async def approve_scene_in_catalog(scene_spec_id: str, admin_api_key: str) -> dict:
    """Validates and, if clean, approves a DRAFT catalog scene — APPROVED scenes are
    then immutable (requirements/41 ITL-1's guard trigger). Requires a valid
    admin_api_key."""
    return await get_rest_client().approve_scene(
        scene_spec_id=scene_spec_id, admin_api_key=admin_api_key,
    )

