"""Real ADK Runner/AgentTool delegation with scripted models; no paid provider or DB."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from agents.mathbank_tutor.artifact_agents import (
    SUBJECTS,
    ArtifactAgentTool,
    _model_limit,
    artifact_agent_tools,
    build_artifact_agents,
)
from agents.mathbank_tutor.tools import step_runtime_tools
from google.adk import Agent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.agent_tool import AgentTool
from google.genai import types
from pydantic import Field

PLAN = {
    "subject": "GEOMETRY",
    "topic": "Triangle",
    "title": "Generated triangle",
    "elements": [
        {"kind": "POINT", "id": "A", "label": "A", "x": 100, "y": 100},
        {"kind": "POINT", "id": "B", "label": "B", "x": 600, "y": 100},
        {"kind": "POINT", "id": "C", "label": "C", "x": 350, "y": 450},
    ],
}
BLOCK = "```geometry-artifact\n" + json.dumps(PLAN) + "\n```"


class ScriptedModel(BaseLlm):
    model: str = "synthetic-adk-model"
    script: list[tuple[str, dict] | str] = Field(default_factory=list)
    position: int = 0

    async def generate_content_async(self, llm_request, stream=False):
        serialized = json.dumps(
            [content.model_dump(mode="json") for content in llm_request.contents]
        )
        assert "synthetic-token" not in serialized
        assert "synthetic-student-one" not in serialized
        assert "synthetic-student-two" not in serialized
        assert self.position < len(self.script), "Unexpected extra model call"
        item = self.script[self.position]
        self.position += 1
        if isinstance(item, str):
            part = types.Part.from_text(text=item)
        else:
            name, args = item
            part = types.Part(function_call=types.FunctionCall(name=name, args=args))
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


def network():
    agents = build_artifact_agents(ScriptedModel())
    agents["svg_artifact_agent"].model = ScriptedModel(script=[json.dumps(PLAN)])
    agents["overlay_frame_agent"].model = ScriptedModel(script=[json.dumps(PLAN)])
    agents["annotation_agent"].model = ScriptedModel(script=[json.dumps(PLAN)])
    agents["validation_agent"].model = ScriptedModel(
        script=[
            ("validate_artifact_plan", {"plan_json": json.dumps(PLAN)}),
            json.dumps({"valid": True, "errors": [], "warnings": []}),
        ]
    )
    agents["geometry_artifact_agent"].model = ScriptedModel(
        script=[
            ("svg_artifact_agent", {"request": json.dumps(PLAN)}),
            ("overlay_frame_agent", {"request": json.dumps(PLAN)}),
            ("annotation_agent", {"request": json.dumps(PLAN)}),
            ("validation_agent", {"request": json.dumps(PLAN)}),
            ("draw_geometry_diagram", {"plan_json": json.dumps(PLAN)}),
            BLOCK,
        ]
    )
    agents["subject_planning_agent"].model = ScriptedModel(
        script=[
            (
                "geometry_artifact_agent",
                {"request": "Draw the supplied triangle, no proof."},
            ),
            BLOCK,
        ]
    )
    return agents


def test_all_ten_agents_are_real_adk_agents_and_network_is_acyclic():
    agents = build_artifact_agents(ScriptedModel())
    assert len(agents) == 10
    assert all(isinstance(agent, Agent) for agent in agents.values())
    assert set(SUBJECTS).issubset(agents)
    assert all(isinstance(tool, AgentTool) for tool in artifact_agent_tools(agents))
    visited = set()

    def visit(name, ancestors):
        assert name not in ancestors
        visited.add(name)
        for tool in agents[name].tools:
            if isinstance(tool, AgentTool):
                visit(tool.agent.name, ancestors | {name})

    visit("subject_planning_agent", set())
    assert visited == set(agents)
    assert agents["validation_agent"].tools[0].__name__ == "validate_artifact_plan"


@pytest.mark.asyncio
async def test_real_nested_runner_delegation_preserves_auth_and_returns_diagram(
    monkeypatch,
):
    calls = []

    def handle(request):
        calls.append(request)
        if request.url.path.endswith("/validate"):
            return httpx.Response(
                200, json={"valid": True, "errors": [], "warnings": []}
            )
        return httpx.Response(
            200, json={"validation": {"valid": True}, "markdown_block": BLOCK}
        )

    monkeypatch.setattr(
        step_runtime_tools,
        "_client",
        lambda: httpx.Client(
            base_url="http://rest", transport=httpx.MockTransport(handle)
        ),
    )
    agents = network()
    root = Agent(
        name="synthetic_tutor",
        model=ScriptedModel(
            script=[
                (
                    "subject_planning_agent",
                    {"request": "Create a triangle illustration."},
                ),
                BLOCK,
            ]
        ),
        tools=artifact_agent_tools(agents),
    )
    sessions = InMemorySessionService()
    await sessions.create_session(
        app_name="artifact_test",
        user_id="synthetic-student",
        session_id="test",
        state={"temp:student_token": "synthetic-token"},
    )
    runner = Runner(app_name="artifact_test", agent=root, session_service=sessions)
    try:
        events = [
            event
            async for event in runner.run_async(
                user_id="synthetic-student",
                session_id="test",
                state_delta={"temp:student_token": "synthetic-token"},
                new_message=types.Content(
                    role="user", parts=[types.Part.from_text(text="Draw a diagram")]
                ),
            )
        ]
        final = [event for event in events if event.content and event.content.parts][-1]
        assert final.content.parts[0].text == BLOCK
        assert [request.url.path for request in calls] == [
            "/v1/artifacts/validate",
            "/v1/artifacts/geometry-preview",
        ]
        assert all(
            request.headers["authorization"] == "Bearer synthetic-token"
            for request in calls
        )
        assert all(
            "synthetic-token" not in request.content.decode() for request in calls
        )
        persisted = await sessions.get_session(
            app_name="artifact_test",
            user_id="synthetic-student",
            session_id="test",
        )
        assert not any(
            "synthetic-token" in event.model_dump_json() for event in persisted.events
        )
        assert agents["svg_artifact_agent"].model.position == 1
        assert agents["annotation_agent"].model.position == 1
        assert agents["validation_agent"].model.position == 2
    finally:
        await runner.close()


@pytest.mark.asyncio
async def test_anonymous_and_delegation_limit_stop_before_child_model():
    tool = ArtifactAgentTool(
        agent=build_artifact_agents(ScriptedModel())["geometry_artifact_agent"]
    )
    anonymous = SimpleNamespace(state={})
    assert (await tool.run_async(args={"request": "draw"}, tool_context=anonymous))[
        "error"
    ] == "SIGN_IN_REQUIRED"
    exhausted = SimpleNamespace(
        state={
            "temp:student_token": "synthetic",
            "temp:artifact_delegations": 16,
        }
    )
    assert (await tool.run_async(args={"request": "draw"}, tool_context=exhausted))[
        "error"
    ] == "ARTIFACT_DELEGATION_LIMIT"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,subject",
    [
        ("algebra_artifact_agent", "ALGEBRA"),
        ("combinatorics_artifact_agent", "COMBINATORICS"),
        ("number_theory_artifact_agent", "NUMBER_THEORY"),
    ],
)
async def test_subject_agents_return_rendered_artifacts(name, subject, monkeypatch):
    plan = {**PLAN, "subject": subject}
    block = "```artifact-preview\n" + json.dumps(plan) + "\n```"
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            200, json={"validation": {"valid": True}, "markdown_block": block}
        )

    monkeypatch.setattr(
        step_runtime_tools,
        "_client",
        lambda: httpx.Client(
            base_url="http://rest", transport=httpx.MockTransport(handle)
        ),
    )
    agents = build_artifact_agents(ScriptedModel())
    helper = "latex_artifact_agent" if subject == "ALGEBRA" else "svg_artifact_agent"
    agents[helper].model = ScriptedModel(script=[json.dumps(plan)])
    agents[name].model = ScriptedModel(
        script=[
            (helper, {"request": json.dumps(plan)}),
            ("preview_artifact", {"plan_json": json.dumps(plan)}),
            block,
        ]
    )
    root = Agent(
        name="synthetic_tutor",
        model=ScriptedModel(
            script=[
                (name, {"request": "Create a learner-safe illustration."}),
                block,
            ]
        ),
        tools=artifact_agent_tools(agents),
    )
    sessions = InMemorySessionService()
    await sessions.create_session(
        app_name="subject_test", user_id="synthetic", session_id="test"
    )
    runner = Runner(app_name="subject_test", agent=root, session_service=sessions)
    try:
        events = [
            event
            async for event in runner.run_async(
                user_id="synthetic",
                session_id="test",
                state_delta={"temp:student_token": "synthetic-token"},
                new_message=types.Content(
                    role="user", parts=[types.Part.from_text(text="Draw")]
                ),
            )
        ]
        assert any(
            event.content and any(part.text == block for part in event.content.parts)
            for event in events
        )
        assert len(calls) == 1 and calls[0].url.path == "/v1/artifacts/preview"
        assert json.loads(calls[0].content)["subject"] == subject
        assert agents[helper].model.position == 1
    finally:
        await runner.close()


def test_specialist_model_limit_is_enforced_before_inference():
    callback = SimpleNamespace(state={"temp:artifact_model_calls": 24})
    with pytest.raises(RuntimeError, match="model-call limit"):
        _model_limit(callback, None)


@pytest.mark.asyncio
async def test_concurrent_student_delegations_keep_tokens_isolated(monkeypatch):
    calls = []

    def handle(request):
        calls.append(
            (json.loads(request.content)["title"], request.headers["authorization"])
        )
        return httpx.Response(200, json={"markdown_block": BLOCK})

    monkeypatch.setattr(
        step_runtime_tools,
        "_client",
        lambda: httpx.Client(
            base_url="http://rest", transport=httpx.MockTransport(handle)
        ),
    )

    async def invoke(student):
        plan = {**PLAN, "title": student}
        agents = build_artifact_agents(ScriptedModel())
        agents["geometry_artifact_agent"].model = ScriptedModel(
            script=[
                ("draw_geometry_diagram", {"plan_json": json.dumps(plan)}),
                BLOCK,
            ]
        )
        root = Agent(
            name="synthetic_tutor",
            model=ScriptedModel(
                script=[
                    ("geometry_artifact_agent", {"request": student}),
                    BLOCK,
                ]
            ),
            tools=artifact_agent_tools(agents),
        )
        sessions = InMemorySessionService()
        await sessions.create_session(
            app_name="isolated", user_id=student, session_id="test"
        )
        runner = Runner(app_name="isolated", agent=root, session_service=sessions)
        try:
            async for _ in runner.run_async(
                user_id=student,
                session_id="test",
                state_delta={"temp:student_token": f"synthetic-{student}"},
                new_message=types.Content(
                    role="user", parts=[types.Part.from_text(text="Draw")]
                ),
            ):
                pass
        finally:
            await runner.close()

    await asyncio.gather(invoke("student-one"), invoke("student-two"))
    assert set(calls) == {
        ("student-one", "Bearer synthetic-student-one"),
        ("student-two", "Bearer synthetic-student-two"),
    }
