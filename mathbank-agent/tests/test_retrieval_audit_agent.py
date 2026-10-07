import asyncio
import json
from types import SimpleNamespace

import httpx
from agents.mathbank_tutor import pedagogy_agent as p
from agents.mathbank_tutor.formatter_agent import guard_tutor_output
from agents.mathbank_tutor.retrieval_audit_agent import retrieval_audit_tool
from google.adk import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from test_artifact_agents import ScriptedModel

AUDIT = {"version": "topic-audit-v1", "published_step_count": 9, "supporting_step_ids": [],
         "suggested_error_kind": "METADATA", "review_status": "PENDING", "structural_validation": {"status": "REVIEW_REQUIRED"}}


def test_auditor_cannot_substitute_server_snapshot():
    tool = retrieval_audit_tool(ScriptedModel(script=[]))
    result = asyncio.run(tool.run_async(args={"request": "{}"},
        tool_context=SimpleNamespace(state={"temp:retrieval_audit_evidence": AUDIT})))
    assert result["error"] == "AUDIT_EVIDENCE_REQUIRED"


def test_complaint_runs_real_pending_audit_then_teaching_not_canonical_mutation(monkeypatch):
    async def run():
        def handler(request):
            assert request.url.path == "/v1/tutor/feedback"
            return httpx.Response(201, json={"feedback_id": "id", "status": "PENDING", "audit": AUDIT})
        monkeypatch.setattr(p.rest_tools, "_client", lambda: httpx.Client(base_url="http://rest",
            transport=httpx.MockTransport(handler)))
        monkeypatch.setattr(p, "get_topic_plan", lambda topic: {
            "matched": True, "node": {"name": "Power of point", "taxonomy_node_id": "TECH.GEO.POWER_OF_A_POINT"},
            "plan_steps": ["Recognise", "Apply", "Transfer"], "first_checkpoint": "Which circle?",
            "warnings": ["Machine evidence"],
        })
        monkeypatch.setattr(p, "draw_geometry_diagram", lambda *args: {"markdown_block": "Illustrative chord diagram"})
        root = Agent(name="test", model=ScriptedModel(script=["Canonical tags automatically fixed"]),
            tools=[p.report_pedagogy_feedback,
                   retrieval_audit_tool(ScriptedModel(script=["Review evidence only"])),
                   p.pedagogy_tool(ScriptedModel(script=["Teach recognition first"]))],
            before_model_callback=p.route_topic_before_model,
            after_tool_callback=p.after_pedagogy_tool, after_model_callback=guard_tutor_output)
        sessions = InMemorySessionService()
        session = await sessions.create_session(app_name="test", user_id="u",
            state={"pedagogy:last_topic": "Power of point", "pedagogy:last_codes": ["WRONG"]})
        runner = Runner(agent=root, app_name="test", session_service=sessions)
        events = [event async for event in runner.run_async(user_id="u", session_id=session.id,
            state_delta={"temp:student_token": "synthetic-token"},
            new_message=types.Content(role="user", parts=[types.Part(text="This is not related")]))]
        calls = [part.function_call.name for event in events for part in event.content.parts or [] if part.function_call]
        assert calls == ["report_pedagogy_feedback", "retrieval_audit_agent", "pedagogy_agent"]
        reply = events[-1].content.parts[0].text
        assert "recorded for review" in reply and "annotations remain unchanged" in reply
        assert "Step 1 of 7" in reply and "automatically fixed" not in reply
        stored = await sessions.get_session(app_name="test", user_id="u", session_id=session.id)
        assert stored.state["pedagogy:excluded_codes"] == ["WRONG"]
        assert "synthetic-token" not in json.dumps([event.model_dump(mode="json") for event in events])
    asyncio.run(run())


def test_explicit_practice_uses_ranked_complete_candidates_and_preserves_exposure_on_review(monkeypatch):
    async def run():
        node = {"name": "Power of point", "taxonomy_node_id": "TECH.GEO.POWER_OF_A_POINT",
                "example_problem_codes": ["UNRELATED"]}
        topic = {"matched": True, "node": node, "plan_steps": ["Recognise", "Apply", "Transfer"],
                 "first_checkpoint": "Which circle?", "warnings": ["Machine evidence"]}
        checked = []
        def handler(request):
            assert request.url.path == "/v1/tutor/topic-practice"
            body = json.loads(request.content)
            assert body["exposed_codes"] == ["SEEN"]
            assert body["exclude_codes"] == ["WRONG"]
            assert body["target_difficulty"] == 5
            return httpx.Response(200, json={"profile_version": "topic-fit-v1",
                "candidates": [{"canonical_code": "INCOMPLETE"}, {"canonical_code": "GOOD"}]})
        def problem(code):
            checked.append(code)
            return {"eligible": code == "GOOD", "canonical_code": code,
                    "markdown_block": "**Problem:** Two chords intersect.\n\n**Source:** Identified textbook."}
        monkeypatch.setattr(p.rest_tools, "_client", lambda: httpx.Client(base_url="http://rest",
            transport=httpx.MockTransport(handler)))
        monkeypatch.setattr(p, "get_topic_plan", lambda query: topic)
        monkeypatch.setattr(p.rest_tools, "get_practice_problem", problem)
        monkeypatch.setattr(p, "draw_geometry_diagram", lambda *args: {"markdown_block": "Generated illustration"})
        root = Agent(name="practice_test", model=ScriptedModel(script=["Invented practice", "Invented lesson"]),
            tools=[p.pedagogy_tool(ScriptedModel(script=["Practice", "Review"]))],
            before_model_callback=p.route_topic_before_model,
            after_tool_callback=p.after_pedagogy_tool, after_model_callback=guard_tutor_output)
        sessions = InMemorySessionService()
        initial = p.topic_lessons.new_plan(node)
        initial["exposed_codes"] = ["SEEN"]
        session = await sessions.create_session(app_name="practice_test", user_id="u", state={
            "pedagogy:topic_plan": initial, "pedagogy:last_topic": "Power of point",
            "pedagogy:excluded_codes": ["WRONG"], "pedagogy:exposed_codes": ["SEEN"]})
        runner = Runner(agent=root, app_name="practice_test", session_service=sessions)
        events = [event async for event in runner.run_async(user_id="u", session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text="Give me a hard problem")]))]
        assert checked == ["INCOMPLETE", "GOOD"]
        reply = events[-1].content.parts[0].text
        assert "## Practice" in reply and "Two chords" in reply and "Invented" not in reply
        _ = [event async for event in runner.run_async(user_id="u", session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text="Review")]))]
        stored = await sessions.get_session(app_name="practice_test", user_id="u", session_id=session.id)
        assert stored.state["pedagogy:topic_plan"]["exposed_codes"] == ["SEEN", "GOOD"]
        assert stored.state["pedagogy:topic_plan"]["current_unit"] == 0
    asyncio.run(run())
