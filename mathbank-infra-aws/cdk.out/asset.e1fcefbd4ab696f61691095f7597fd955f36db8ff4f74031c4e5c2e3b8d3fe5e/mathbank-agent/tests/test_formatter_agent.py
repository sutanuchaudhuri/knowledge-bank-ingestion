"""Offline formatter contracts and real scripted ADK delegation; no inference."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from agents.mathbank_tutor.formatter_agent import (
    format_tutor_text,
    formatter_agent_tool,
    guard_tutor_output,
    normalize_math,
)
from google.adk import Agent
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from test_artifact_agents import ScriptedModel


def test_delimiters_normalize_in_prose_not_code():
    code = r"```js" + "\n" + r'const text = "\\(x\\)";' + "\n```"
    text = r"Let \\( OT = 25 \\) and \( AM = MB = 30 \). Find \( MD \)."
    assert (
        normalize_math(text + "\n" + code)
        == "Let $OT = 25$ and $AM = MB = 30$. Find $MD$.\n" + code
    )
    assert normalize_math(r"\[x=2\]") == "\n\n$$\nx=2\n$$\n\n"
    assert (
        normalize_math(r"[asy]label('\(x\)');[/asy]") == r"[asy]label('\(x\)');[/asy]"
    )
    assert normalize_math(r"Receiving \(x") == r"Receiving \(x"
    link = r"[Find \(MD\)](https://example.test/\(original\))"
    assert normalize_math(link) == r"[Find $MD$](https://example.test/\(original\))"


def test_formatting_uses_exact_spans_and_preserves_source():
    text = (
        r"Given \(x_1=2\). Find \(MD\)."
        + "\n[Original](https://example.test/source.pdf)"
    )
    selected = r"\(x_1=2\)"
    start = text.index(selected)
    result = format_tutor_text(
        text,
        json.dumps([{"start": start, "end": start + len(selected), "style": "given"}]),
    )
    assert result["valid"]
    assert (
        result["markdown_block"]
        == "Given [$x_1=2$](#mb-tone-given). Find $MD$.\n[Original](https://example.test/source.pdf)"
    )

    result = format_tutor_text(r"\(x_1+x_2\)", '[{"start":0,"end":11,"style":"bold"}]')
    assert result["valid"]


@pytest.mark.parametrize(
    "text,annotations",
    [
        ("text", "{}"),
        ("text", '[{"start":0,"end":4,"style":"red"}]'),
        ("text", '[{"start":true,"end":4,"style":"bold"}]'),
        ("text", '[{"start":0,"end":9,"style":"bold"}]'),
        (
            "text",
            '[{"start":0,"end":3,"style":"bold"},{"start":2,"end":4,"style":"goal"}]',
        ),
        ("`code`", '[{"start":1,"end":5,"style":"bold"}]'),
        ("[source](https://example.test)", '[{"start":1,"end":7,"style":"bold"}]'),
        (r"\(x=2\)", '[{"start":2,"end":3,"style":"bold"}]'),
        ("line\nline", '[{"start":0,"end":9,"style":"bold"}]'),
        ("**text**", '[{"start":0,"end":8,"style":"bold"}]'),
        ("**text**", '[{"start":2,"end":6,"style":"bold"}]'),
        (r"\(x=2", '[{"start":0,"end":5,"style":"bold"}]'),
    ],
)
def test_invalid_annotations_are_explicit_failures(text, annotations):
    result = format_tutor_text(text, annotations)
    assert result["error"] == "FORMAT_INVALID"
    assert "markdown_block" not in result


def test_all_styles_are_bounded_and_meaning_preserving():
    for style in ("given", "goal", "insight", "warning", "bold", "italic"):
        result = format_tutor_text(
            "Key term", json.dumps([{"start": 0, "end": 8, "style": style}])
        )
        assert result["valid"] and "Key term" in result["markdown_block"]


def test_final_guard_preserves_thoughts_tools_and_partial_chunks():
    response = LlmResponse(
        content=types.Content(
            parts=[
                types.Part(text=r"\(private\)", thought=True),
                types.Part(text=r"Find \\( MD \\)."),
                types.Part(
                    function_call=types.FunctionCall(
                        name="tool", args={"text": r"\(x\)"}
                    )
                ),
            ]
        )
    )
    guard_tutor_output(None, response)
    assert response.content.parts[0].text == r"\(private\)"
    assert response.content.parts[1].text == "Find $MD$."
    assert response.content.parts[2].function_call.args["text"] == r"\(x\)"
    partial = LlmResponse(
        partial=True, content=types.Content(parts=[types.Part(text=r"\(x\)")])
    )
    guard_tutor_output(None, partial)
    assert partial.content.parts[0].text == r"\(x\)"


@pytest.mark.parametrize("changed_input", [False, True])
def test_real_formatter_delegation_enforces_tool_output_not_model_rewrite(
    changed_input,
):
    async def run():
        model = ScriptedModel(
            script=[
                (
                    "format_tutor_text",
                    {
                        "text": "Invented answer 999."
                        if changed_input
                        else r"Find \(MD\).",
                        "annotations_json": "[]",
                    },
                ),
                "The answer is 999; invented rewrite.",
            ]
        )
        delegate = formatter_agent_tool(model)
        root = Agent(
            name="formatter_test",
            model=ScriptedModel(
                script=[
                    (
                        "formatter_agent",
                        {
                            "request": json.dumps(
                                {
                                    "text": r"Find \(MD\).",
                                    "instructions": "Format only, no answer.",
                                }
                            )
                        },
                    ),
                    "Done",
                ]
            ),
            tools=[delegate],
            after_model_callback=guard_tutor_output,
        )
        sessions = InMemorySessionService()
        session = await sessions.create_session(app_name="test", user_id="u")
        runner = Runner(agent=root, app_name="test", session_service=sessions)
        events = [
            event
            async for event in runner.run_async(
                user_id="u",
                session_id=session.id,
                state_delta={"temp:student_token": "synthetic-token"},
                new_message=types.Content(
                    role="user", parts=[types.Part(text="Format")]
                ),
            )
        ]
        response = next(
            part.function_response.response
            for event in events
            for part in event.content.parts or []
            if part.function_response
            and part.function_response.name == "formatter_agent"
        )
        expected = (
            "Formatting failed: Formatter must use the exact original request text."
            if changed_input
            else "Find $MD$."
        )
        assert expected in str(response)
        assert "999" not in str(response)
        assert events[-1].content.parts[0].text == expected
        assert "synthetic-token" not in json.dumps(
            [event.model_dump(mode="json") for event in events]
        )

    asyncio.run(run())


def test_formatter_is_registered_and_authentication_is_required():
    from agents.mathbank_tutor.agent import root_agent

    assert root_agent.after_model_callback == guard_tutor_output
    assert any(
        getattr(tool, "name", "") == "formatter_agent" for tool in root_agent.tools
    )
    tool = formatter_agent_tool(ScriptedModel())
    result = asyncio.run(
        tool.run_async(
            args={"request": '{"text":"Format","instructions":"No changes"}'},
            tool_context=SimpleNamespace(state={}),
        )
    )
    assert result["error"] == "SIGN_IN_REQUIRED"
    invalid = asyncio.run(
        tool.run_async(
            args={"request": '{"instructions":"no original"}'},
            tool_context=SimpleNamespace(state={}),
        )
    )
    assert invalid["error"] == "FORMAT_INVALID"


def test_automatic_guard_is_applied_to_emitted_and_persisted_final_events():
    async def run():
        root = Agent(
            name="format_guard_test",
            model=ScriptedModel(
                script=[
                    r"Problem: Let \\( OT = 25 \\) and \( AM = MB = 30 \). Find \( MD \).",
                ]
            ),
            after_model_callback=guard_tutor_output,
        )
        sessions = InMemorySessionService()
        session = await sessions.create_session(app_name="test", user_id="u")
        runner = Runner(agent=root, app_name="test", session_service=sessions)
        events = [
            event
            async for event in runner.run_async(
                user_id="u",
                session_id=session.id,
                new_message=types.Content(
                    role="user", parts=[types.Part(text=r"Explain \(MD\)")]
                ),
            )
        ]
        assert (
            events[-1].content.parts[0].text
            == "Problem: Let $OT = 25$ and $AM = MB = 30$. Find $MD$."
        )
        stored = await sessions.get_session(
            app_name="test", user_id="u", session_id=session.id
        )
        assert (
            stored.events[-1].content.parts[0].text == events[-1].content.parts[0].text
        )
        assert stored.events[0].content.parts[0].text == r"Explain \(MD\)"

    asyncio.run(run())
