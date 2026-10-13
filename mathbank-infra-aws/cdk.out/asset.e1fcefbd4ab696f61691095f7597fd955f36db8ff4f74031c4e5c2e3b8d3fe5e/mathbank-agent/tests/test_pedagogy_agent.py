"""Real ADK topic routing and feedback contracts, without provider inference."""

import asyncio
from types import SimpleNamespace

import httpx
from agents.mathbank_tutor import formatter_agent as formatter
from agents.mathbank_tutor import pedagogy_agent as p
from agents.mathbank_tutor.formatter_agent import guard_tutor_output
from google.adk import Agent
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from test_artifact_agents import ScriptedModel

PLAN = {
    "matched": True,
    "node": {"name": "Power of a point", "taxonomy_node_id": "TECH.GEO.POWER_OF_A_POINT", "example_problem_codes": ["BROKEN", "RIGHT"]},
    "plan_steps": [
        "Identify the circle.",
        "Check segment products.",
        "Try one checkpoint.",
    ],
    "first_checkpoint": "Which segments are collinear?",
    "warnings": ["Machine-generated annotations."],
}


def test_formatter_cannot_replace_grounded_pedagogy_source():
    tool = formatter.formatter_agent_tool(ScriptedModel(script=[]))
    result = asyncio.run(tool.run_async(
        args={"request": '{"text":"Wrong polygon","instructions":"bold"}'},
        tool_context=SimpleNamespace(state={"temp:pedagogy_reply": "Grounded plan"}),
    ))
    assert result["error"] == "FORMAT_TEXT_CHANGED"


def test_root_only_accepts_formatting_bound_to_current_plan():
    state = {"temp:pedagogy_reply": "Grounded plan", "temp:formatted_reply": "Wrong polygon"}
    response = LlmResponse(content=types.Content(role="model", parts=[types.Part(text="Wrong rewrite")]))
    guard_tutor_output(SimpleNamespace(state=state), response)
    assert response.content.parts[0].text == "Grounded plan"
    state.update({"temp:formatted_reply": "**Grounded** plan", "temp:formatted_pedagogy_source": "Grounded plan"})
    guard_tutor_output(SimpleNamespace(state=state), response)
    assert response.content.parts[0].text == "**Grounded** plan"
    state["temp:formatted_reply"] = "Formatting failed: invalid span."
    guard_tutor_output(SimpleNamespace(state=state), response)
    assert response.content.parts[0].text.endswith("Grounded plan")
    assert "Formatting failed" in response.content.parts[0].text


def test_grounded_plan_does_not_stream_an_unverified_model_rewrite():
    response = LlmResponse(partial=True, content=types.Content(role="model", parts=[types.Part(text="Wrong draft")]))
    guard_tutor_output(SimpleNamespace(state={"temp:pedagogy_reply": "Grounded plan"}), response)
    assert not response.content.parts[0].text


def test_feedback_save_status_survives_failed_replan():
    context = SimpleNamespace(state={})
    p.after_pedagogy_tool(
        SimpleNamespace(name="report_pedagogy_feedback"), {"topic": "Power of point"},
        context, {"feedback_id": "id", "status": "PENDING"},
    )
    p.after_pedagogy_tool(
        SimpleNamespace(name="pedagogy_agent"), {}, context,
        {"error": "PEDAGOGY_TIMEOUT"},
    )
    assert "recorded for review" in context.state["temp:pedagogy_reply"]
    assert "could not be delivered" in context.state["temp:pedagogy_reply"]
    assert context.state["temp:feedback_notice"] is None


def test_duplicate_reviewed_feedback_does_not_claim_pending_queue():
    context = SimpleNamespace(state={})
    p.after_pedagogy_tool(
        SimpleNamespace(name="report_pedagogy_feedback"), {"topic": "Power of point"},
        context, {"feedback_id": "id", "status": "RESOLVED"},
    )
    assert "not reopened" in context.state["temp:feedback_notice"]


def test_plan_checks_step_supported_candidates_and_excludes_reported_problem(
    monkeypatch,
):
    monkeypatch.setattr(p, "get_topic_plan", lambda topic: PLAN)
    monkeypatch.setattr(
        p.rest_tools,
        "get_practice_problem",
        lambda code: {
            "eligible": code == "RIGHT",
            "canonical_code": code,
            "markdown_block": "Verified problem",
        },
    )
    result = p.prepare_topic_practice("Power of point")
    assert [item["canonical_code"] for item in result["practice"]] == ["RIGHT"]
    assert "Learning plan" in result["markdown_block"]
    assert "no related problems" not in result["markdown_block"]
    result = p.prepare_topic_practice("Power of point", ["RIGHT"])
    assert result["practice"] == []
    assert "bounded check" in result["markdown_block"]


def test_topic_prompt_forces_real_specialist_and_pins_plan_not_model_rewrite(
    monkeypatch,
):
    async def run():
        monkeypatch.setattr(p, "get_topic_plan", lambda topic: PLAN)
        monkeypatch.setattr(p, "draw_geometry_diagram", lambda *args: {"markdown_block": "Generated chord diagram"})
        monkeypatch.setattr(p, "prepare_topic_practice", lambda *args: (_ for _ in ()).throw(AssertionError("Bare topic must not select practice")))
        root_model = ScriptedModel(script=["Wrong polygon recommendation"])
        root = Agent(
            name="test_tutor",
            model=root_model,
            tools=[p.pedagogy_tool(ScriptedModel(script=["Provisional rationale"]))],
            before_model_callback=p.route_topic_before_model,
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
                    role="user", parts=[types.Part(text="Power of point")]
                ),
            )
        ]
        assert any(
            part.function_call and part.function_call.name == "pedagogy_agent"
            for event in events
            for part in event.content.parts or []
        )
        assert "Step 1 of 7" in events[-1].content.parts[0].text
        assert "Both on the circle" in events[-1].content.parts[0].text
        assert "Wrong polygon" not in events[-1].content.parts[0].text
        stored = await sessions.get_session(
            app_name="test", user_id="u", session_id=session.id
        )
        assert stored.state["pedagogy:last_codes"] == []
        assert stored.state["pedagogy:topic_plan"]["current_unit"] == 0
        assert "answer" not in stored.state["pedagogy:topic_plan"]
        assert "units" not in stored.state["pedagogy:topic_plan"]
        assert "synthetic-token" not in str([event.model_dump() for event in events])

    asyncio.run(run())


def test_feedback_auth_failure_is_explicit_but_session_excludes_candidate():
    context = SimpleNamespace(state={})
    result = p.report_pedagogy_feedback(
        "WRONG", "Power of point", "This problem is unrelated.", context
    )
    assert result["error"] == "SIGN_IN_REQUIRED"
    assert context.state["pedagogy:excluded_codes"] == ["WRONG"]


def test_feedback_is_saved_with_runtime_token_not_model_argument(monkeypatch):
    def handler(request):
        assert request.url.path == "/v1/tutor/feedback"
        assert request.headers["authorization"] == "Bearer synthetic-token"
        return httpx.Response(201, json={"feedback_id": "id", "status": "PENDING"})

    monkeypatch.setattr(
        p.rest_tools,
        "_client",
        lambda: httpx.Client(
            base_url="http://rest", transport=httpx.MockTransport(handler)
        ),
    )
    result = p.report_pedagogy_feedback(
        "WRONG",
        "Power of point",
        "This problem is unrelated.",
        SimpleNamespace(state={"temp:student_token": "synthetic-token"}),
    )
    assert result["status"] == "PENDING"
    assert "synthetic-token" not in str(result)


def test_complaint_forces_pending_report_and_replan_without_global_approval():
    state = {"pedagogy:last_codes": ["WRONG"], "pedagogy:last_topic": "Power of point"}
    context = SimpleNamespace(
        state=state,
        invocation_id="new",
        user_content=types.Content(
            parts=[types.Part(text="This is not related to power of point")]
        ),
    )
    result = p.route_topic_before_model(context, None)
    call = result.content.parts[0].function_call
    assert call.name == "report_pedagogy_feedback"
    assert call.args["problem_code"] == "WRONG"
    p.after_pedagogy_tool(
        SimpleNamespace(name=call.name),
        call.args,
        context,
        {"feedback_id": "id", "status": "PENDING"},
    )
    result = p.route_topic_before_model(context, None)
    assert result.content.parts[0].function_call.name == "pedagogy_agent"
    assert "review" in state["temp:feedback_notice"]


def test_real_tutor_has_pedagogy_routing_and_feedback_tool():
    from agents.mathbank_tutor.agent import root_agent

    assert root_agent.before_model_callback == p.route_topic_before_model
    assert p.report_pedagogy_feedback in root_agent.tools
    assert any(
        getattr(tool, "name", "") == "pedagogy_agent" for tool in root_agent.tools
    )


def test_unmatched_explicit_practice_does_not_fall_through_to_vector_recommendation(monkeypatch):
    monkeypatch.setattr(p, "get_topic_plan", lambda query: {"matched": False, "candidates": []})
    context = SimpleNamespace(state={}, invocation_id="unknown-topic",
        user_content=types.Content(parts=[types.Part(text="Give me a hard spherical geometry problem")]))
    response = p.route_topic_before_model(context, None)
    assert response is not None
    assert response.content.parts[0].function_call is None
    assert "No practice problem was selected" in response.content.parts[0].text
