"""requirements/53 QZ-8: real ADK Runner/AgentTool delegation test for the quiz sub-agent.

Follows the exact rigor level established in test_artifact_agents.py — a real ADK Runner
with a scripted model and a mocked REST transport, not mocked ADK internals — to prove the
signed-in student's token actually reaches the REST call through the AgentTool delegation
boundary (the one gap the sub-agent pattern is confirmed NOT to handle for free, per
artifact_agents.py's own code comment) and never leaks into the LLM-visible conversation or
the persisted session.
"""
import json

import httpx
import pytest
from agents.mathbank_tutor.quiz_agent import build_quiz_agent, quiz_agent_tool
from agents.mathbank_tutor.tools import quiz_tools
from google.adk import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from test_artifact_agents import ScriptedModel

GENERATED_PAPER = {
    "quiz_id": "11111111-1111-1111-1111-111111111111",
    "style": "AIME", "title": "Aime Practice Set", "status": "READY", "instructions": "",
    "questions": [
        {"question_id": "22222222-2222-2222-2222-222222222222", "ordinal": 1,
         "question_type": "MCQ", "prompt_text": "What is 2+2?", "prompt_latex": None,
         "options": [{"key": "A", "text": "3"}, {"key": "B", "text": "4"}],
         "points": 1.0, "has_diagram": False, "answered": False},
    ],
}


def test_quiz_agent_is_a_real_adk_agent_with_all_five_tools():
    agent = build_quiz_agent(ScriptedModel())
    assert isinstance(agent, Agent)
    assert agent.disallow_transfer_to_parent and agent.disallow_transfer_to_peers
    tool_names = {t.__name__ for t in agent.tools}
    assert tool_names == {
        "generate_quiz_paper", "get_quiz_paper", "submit_quiz_answer",
        "get_quiz_review", "list_my_quizzes",
    }


@pytest.mark.asyncio
async def test_real_nested_runner_delegation_preserves_auth_and_hides_token():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json=GENERATED_PAPER)

    quiz_tools_client = httpx.Client(base_url="http://rest", transport=httpx.MockTransport(handle))
    import unittest.mock
    with unittest.mock.patch.object(quiz_tools, "_client", return_value=quiz_tools_client):
        agent = build_quiz_agent(
            ScriptedModel(script=[
                ("generate_quiz_paper", {"style": "AIME", "question_count": 1}),
                json.dumps(GENERATED_PAPER),
            ])
        )
        root = Agent(
            name="synthetic_tutor",
            model=ScriptedModel(script=[
                ("quiz_generator_agent", {"request": "Give me an AIME practice question."}),
                json.dumps(GENERATED_PAPER),
            ]),
            tools=[quiz_agent_tool(ScriptedModel())],
        )
        # Swap in our scripted quiz agent instance (same mechanics as
        # test_artifact_agents.py's `network()` helper for its sub-agents).
        root.tools[0].agent = agent

        sessions = InMemorySessionService()
        await sessions.create_session(
            app_name="quiz_test", user_id="synthetic-student", session_id="test",
            state={"temp:student_token": "synthetic-quiz-token"},
        )
        runner = Runner(app_name="quiz_test", agent=root, session_service=sessions)
        try:
            events = [
                event async for event in runner.run_async(
                    user_id="synthetic-student", session_id="test",
                    state_delta={"temp:student_token": "synthetic-quiz-token"},
                    new_message=types.Content(
                        role="user", parts=[types.Part.from_text(text="Give me an AIME question")]
                    ),
                )
            ]
            final = [e for e in events if e.content and e.content.parts][-1]
            assert GENERATED_PAPER["questions"][0]["prompt_text"] in final.content.parts[0].text
            assert len(calls) == 1
            assert calls[0].url.path == "/v1/quiz/generate"
            assert calls[0].headers["authorization"] == "Bearer synthetic-quiz-token"
            assert "synthetic-quiz-token" not in calls[0].content.decode()

            persisted = await sessions.get_session(
                app_name="quiz_test", user_id="synthetic-student", session_id="test",
            )
            assert not any(
                "synthetic-quiz-token" in event.model_dump_json() for event in persisted.events
            )
        finally:
            await runner.close()


@pytest.mark.asyncio
async def test_quiz_tools_require_sign_in_without_a_token():
    agent = build_quiz_agent(
        ScriptedModel(script=[
            ("generate_quiz_paper", {"style": "AIME", "question_count": 1}),
            "done",
        ])
    )
    root = Agent(
        name="synthetic_tutor",
        model=ScriptedModel(script=[
            ("quiz_generator_agent", {"request": "Give me an AIME practice question."}),
            "done",
        ]),
        tools=[quiz_agent_tool(ScriptedModel())],
    )
    root.tools[0].agent = agent
    sessions = InMemorySessionService()
    await sessions.create_session(
        app_name="quiz_test2", user_id="anon-student", session_id="test", state={},
    )
    runner = Runner(app_name="quiz_test2", agent=root, session_service=sessions)
    try:
        events = [
            event async for event in runner.run_async(
                user_id="anon-student", session_id="test",
                new_message=types.Content(
                    role="user", parts=[types.Part.from_text(text="Give me an AIME question")]
                ),
            )
        ]
        assert any(
            "SIGN_IN_REQUIRED" in part.function_response.response.get("error", "")
            for event in events if event.content and event.content.parts
            for part in event.content.parts if part.function_response
        )
    finally:
        await runner.close()
