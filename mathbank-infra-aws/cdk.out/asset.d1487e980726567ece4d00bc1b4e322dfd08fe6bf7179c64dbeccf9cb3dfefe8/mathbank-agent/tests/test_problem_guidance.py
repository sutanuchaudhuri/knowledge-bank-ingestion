import asyncio
from types import SimpleNamespace

import httpx
import pytest
from agents.mathbank_tutor import pedagogy_agent as pedagogy
from agents.mathbank_tutor import problem_guidance as guidance
from agents.mathbank_tutor.formatter_agent import guard_tutor_output
from google.adk import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from test_artifact_agents import ScriptedModel

CODE = "AIME_1985_Q01"
CONTEXT = {"problem": {"canonical_code": CODE, "statement_text": "The canonical question."},
           "skills": [], "prerequisites": [], "warnings": [], "metadata_status": "automatic"}
PLAN = {
    "problem_code": CODE, "status": "ready", "selected_solution_id": "pair",
    "rationale": "Neighboring terms avoid unnecessary fraction computations.",
    "stages": ["Read the recurrence.", "Explore neighboring terms.", "Group and check."],
    "first_checkpoint": "What do you get by multiplying neighboring terms?",
    "solution_evidence": {"status": "available", "references_considered": 2, "total_records": 2,
                         "sources": [{"solution_id": "pair", "verification_status": "UNVERIFIED"}]},
    "provenance": {"review_status": "PENDING"},
    "warnings": ["Stored references are unverified."],
}


def mock_tools(monkeypatch, status=200):
    calls = []
    monkeypatch.setattr(guidance.rest_tools, "get_problem_learning_context", lambda code: CONTEXT)
    monkeypatch.setattr(guidance.rest_tools, "get_problem_diagrams", lambda code: [])
    monkeypatch.setattr(guidance.rest_tools, "get_problem_by_code",
                        lambda code: pytest.fail("Guided tools must not expose full problem detail"))

    def handler(request):
        calls.append(request)
        assert request.url.path == "/v1/tutor/guidance-plan" and request.method == "POST"
        return httpx.Response(status, json={**PLAN, "body_markdown": "PRIVATE_SOLUTION", "official_answer": "384"}
                              if status == 200 else {"detail": "Planning unavailable."})

    monkeypatch.setattr(guidance.rest_tools, "_client", lambda: httpx.Client(
        base_url="http://rest", transport=httpx.MockTransport(handler),
    ))
    return calls


def test_public_tool_projects_safe_plan_and_never_returns_raw_references(monkeypatch):
    calls = mock_tools(monkeypatch)
    result = guidance.prepare_problem_guidance(CODE)
    assert len(calls) == 1 and result["diagram_count"] == 0
    assert "PRIVATE" not in str(result) and "384" not in str(result)
    assert "first checkpoint" in result["markdown_block"]
    assert "stored solution records" not in result["markdown_block"]
    assert "/learn?problem=" not in result["markdown_block"]
    assert "No question-specific source diagram" not in result["markdown_block"]
    assert "Stored references are unverified." not in result["markdown_block"]
    assert result["warnings"] == PLAN["warnings"]
    assert result["solution_evidence"] == PLAN["solution_evidence"]


def test_exact_browser_problem_prompt_forces_plan_before_any_root_model_and_pins_safe_reply(monkeypatch):
    calls = mock_tools(monkeypatch)

    async def run():
        root = Agent(
            name="test_problem_tutor", model=ScriptedModel(script=[]),
            tools=[guidance.prepare_problem_guidance],
            before_model_callback=pedagogy.route_topic_before_model,
            after_tool_callback=pedagogy.after_pedagogy_tool,
            after_model_callback=guard_tutor_output,
        )
        sessions = InMemorySessionService()
        session = await sessions.create_session(app_name="test", user_id="u")
        runner = Runner(agent=root, app_name="test", session_service=sessions)
        events = [event async for event in runner.run_async(
            user_id="u", session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=(
                f"Help me think through {CODE}. Load the canonical problem and its diagrams first, "
                "then guide me without revealing the full solution."
            ))]),
        )]
        assert any(part.function_call and part.function_call.name == "prepare_problem_guidance"
                   for event in events for part in event.content.parts or [])
        assert "neighboring" in events[-1].content.parts[0].text
        reply = events[-1].content.parts[0].text
        assert "unverified" not in reply
        assert "Source figures" not in reply and "Problem and source details" not in reply
        stored = await sessions.get_session(app_name="test", user_id="u", session_id=session.id)
        assert stored.state["pedagogy:problem_guidance"]["selected_solution_id"] == "pair"
        assert stored.state["tutor:response_window"]["question"] == PLAN["first_checkpoint"]
        assert any(event.actions.state_delta.get("tutor:response_window") for event in events)
        public_parts = [
            part.function_response.response if part.function_response else part.text
            for event in events for part in event.content.parts or []
            if part.function_response or part.text
        ]
        serialized = str(public_parts) + str(stored.state)
        assert "PRIVATE" not in serialized and "384" not in serialized

    asyncio.run(run())
    assert len(calls) == 1


def test_planning_failure_does_not_become_a_successful_roadmap(monkeypatch):
    mock_tools(monkeypatch, 503)
    result = guidance.prepare_problem_guidance(CODE)
    assert result["error"] == "HTTP_503" and "markdown_block" not in result
    state = {}
    pedagogy.after_pedagogy_tool(SimpleNamespace(name="prepare_problem_guidance"), {},
                               SimpleNamespace(state=state), result)
    assert "Planning unavailable." in state["temp:pedagogy_reply"]
    assert "pedagogy:problem_guidance" not in state


def test_learning_context_tool_requests_read_only_metadata(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=CONTEXT)
    monkeypatch.setattr(guidance.rest_tools, "_client", lambda: httpx.Client(
        base_url="http://rest", transport=httpx.MockTransport(handler)))
    assert guidance.rest_tools.get_problem_learning_context(CODE) == CONTEXT
    assert requests[0].url.params["enrich"] == "false"


@pytest.mark.parametrize("failed_stage", ["context", "diagrams", "plan"])
def test_transport_failures_are_explicit_and_clear_old_guidance(monkeypatch, failed_stage):
    mock_tools(monkeypatch)
    def fail(*args, **kwargs):
        raise httpx.ReadTimeout("sensitive transport detail")
    if failed_stage == "context":
        monkeypatch.setattr(guidance.rest_tools, "get_problem_learning_context", fail)
    elif failed_stage == "diagrams":
        monkeypatch.setattr(guidance.rest_tools, "get_problem_diagrams", fail)
    else:
        monkeypatch.setattr(guidance.rest_tools, "_client", fail)
    result = guidance.prepare_problem_guidance(CODE)
    assert result["error"] == "GUIDANCE_TRANSPORT_ERROR"
    assert "sensitive" not in str(result)
    state = {"pedagogy:problem_guidance": {"problem_code": "OLD"}}
    pedagogy.after_pedagogy_tool(SimpleNamespace(name="prepare_problem_guidance"), {},
                               SimpleNamespace(state=state), result)
    assert "please retry" in state["temp:pedagogy_reply"]
    assert "pedagogy:problem_guidance" not in state


def test_source_diagrams_are_checked_before_paid_plan_and_preserved(monkeypatch):
    order = []
    monkeypatch.setattr(guidance.rest_tools, "get_problem_learning_context", lambda code: CONTEXT)
    def diagrams(code):
        order.append("diagrams")
        return [{"markdown": "![Source figure](/api/rest/problem-images/image/content)"}]
    def handler(request):
        assert order == ["diagrams"]
        order.append("plan")
        return httpx.Response(200, json=PLAN)
    monkeypatch.setattr(guidance.rest_tools, "get_problem_diagrams", diagrams)
    monkeypatch.setattr(guidance.rest_tools, "_client", lambda: httpx.Client(
        base_url="http://rest", transport=httpx.MockTransport(handler)))
    result = guidance.prepare_problem_guidance(CODE)
    assert result["diagram_count"] == 1
    assert "![Source figure]" in result["markdown_block"]
    assert "No question-specific" not in result["markdown_block"]
