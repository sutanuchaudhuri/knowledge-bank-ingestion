"""Real, live integration tests for the MathBank Competitions MCP server — run against
the actually-running `mathbank-rest` dev server (http://localhost:8000 by default), using
FastMCP's own in-memory `Client` to exercise the real MCP protocol path (tool discovery,
argument validation, structured content serialization), not just bare Python function
calls.

Run with: `pytest` (requires `mathbank-rest`'s dev server running — `make start` in that
project — since this is a live, non-mocked integration test, matching this repo's
established "live, non-mocked, real end-to-end" verification convention).
"""
from __future__ import annotations

import pytest
from fastmcp import Client

from mathbank_mcp_competitions.server import mcp


@pytest.fixture
async def client():
    async with Client(mcp) as c:
        yield c


async def test_lists_all_expected_tools(client):
    tools = await client.list_tools()
    names = {t.name for t in tools}
    for expected in (
        "list_competitions", "list_problems", "get_problem", "search_problems",
        "list_concepts", "list_techniques", "open_competition_explorer",
        "list_promotable_scenes", "promote_scene_to_catalog",
        "validate_scene_in_catalog", "approve_scene_in_catalog",
    ):
        assert expected in names


async def test_list_competitions_returns_real_amc_entries(client):
    result = await client.call_tool("list_competitions", {})
    codes = {row["external_code"] for row in result.data}
    assert "AMC10" in codes
    assert "AIME" in codes


async def test_list_problems_filters_by_competition(client):
    result = await client.call_tool("list_problems", {"competition": "AMC10", "limit": 5})
    assert len(result.data) == 5
    assert all(row["competition"] == "AMC 10" for row in result.data)


async def test_get_problem_returns_full_statement_text(client):
    result = await client.call_tool("get_problem", {"canonical_code": "AMC10_2000_Q01"})
    assert result.data["canonical_code"] == "AMC10_2000_Q01"
    assert "2001" in result.data["statement_text"]


async def test_get_problem_raises_a_clean_error_for_an_unknown_code(client):
    with pytest.raises(Exception, match="No problem found"):
        await client.call_tool("get_problem", {"canonical_code": "NOT_A_REAL_CODE"})


async def test_search_problems_finds_relevant_geometry_results(client):
    result = await client.call_tool(
        "search_problems",
        {"query": "geometry triangle area", "competition": "AMC10", "limit": 3},
    )
    assert len(result.data) > 0
    assert all("canonical_code" in row for row in result.data)


async def test_list_concepts_and_techniques_return_real_rows(client):
    concepts = await client.call_tool("list_concepts", {"limit": 5})
    techniques = await client.call_tool("list_techniques", {"limit": 5})
    assert len(concepts.data) > 0
    assert len(techniques.data) > 0


async def test_open_competition_explorer_renders_a_full_prefab_component_tree(client):
    """The core "prefab client rendered in HTML" assertion: calling the UI tool through
    the real MCP protocol returns structured Prefab content with the full nested
    component tree (a Row with a Heading+Badge, a Row with a Select+options, and a
    DataTable), not a flat/truncated shape."""
    result = await client.call_tool("open_competition_explorer", {"competition": "AMC10"})
    assert "$prefab" in result.structured_content
    assert result.structured_content["state"]["competition"] == "AMC10"
    assert len(result.structured_content["state"]["problems"]) > 0

    outer = result.structured_content["view"]
    inner = outer["children"][0]
    assert inner["type"] == "Column"
    assert len(inner["children"]) == 3
    row_types = [child["type"] for child in inner["children"]]
    assert row_types == ["Row", "Row", "DataTable"]

    select_row = inner["children"][1]
    select = select_row["children"][1]
    assert select["type"] == "Select"
    option_values = {opt["value"] for opt in select["children"]}
    assert "AMC10" in option_values
    selected_options = [opt for opt in select["children"] if opt["selected"]]
    assert len(selected_options) == 1
    assert selected_options[0]["value"] == "AMC10"


async def test_load_competition_problems_app_tool_switches_competition(client):
    """The app-only backend tool the Select's on_change calls — verifies it independently
    returns a fresh problem list for a different competition."""
    result = await client.call_tool("load_competition_problems", {"competition": "AIME"})
    assert result.data["competition"] == "AIME"
    assert len(result.data["problems"]) > 0
