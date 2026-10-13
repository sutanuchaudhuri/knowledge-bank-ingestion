import asyncio
from types import SimpleNamespace

from google.adk import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from test_artifact_agents import ScriptedModel

from agents.mathbank_tutor import topic_lessons
from agents.mathbank_tutor.formatter_agent import guard_tutor_output
from agents.mathbank_tutor.pedagogy_agent import route_topic_before_model
from agents.mathbank_tutor.timed_questions import (
    WINDOW_KEY,
    choose_response_window,
    continue_idle_question,
    guard_idle_tool,
    record_reply_window,
    response_seconds,
    set_response_window,
)


def test_question_window_uses_complexity_and_bounded_model_choice():
    assert response_seconds("Which side?") < response_seconds("Compute " * 80)
    assert 30 <= response_seconds("x") <= 180
    state = {}
    context = SimpleNamespace(state=state)
    assert choose_response_window("What is x?", 12, context)["error"]
    assert choose_response_window("What is x?", True, context)["error"]
    choose_response_window("What is x?", 90, context)
    record_reply_window("Consider the equality. What is x?", state)
    assert state[WINDOW_KEY]["seconds"] == 90
    assert state[WINDOW_KEY]["action"] == "hint"
    record_reply_window("This route is finished. [Source](/learn?problem=X)", state)
    assert state[WINDOW_KEY] is None
    choose_response_window("Write the equation.", 60, context)
    record_reply_window("Write the equation.", state)
    assert state[WINDOW_KEY]["seconds"] == 60
    record_reply_window("**Your first checkpoint:** Write the angle-sum equation.", state)
    assert state[WINDOW_KEY]["question"] == "Write the angle-sum equation."


def test_idle_is_hint_then_explanation_and_stale_events_do_not_advance():
    state = {}
    first = set_response_window("What is x?", 30, state)
    context = SimpleNamespace(state=state)
    wrong = continue_idle_question(first["id"], "explain", context)
    assert wrong["error"] == "STALE_RESPONSE_WINDOW"
    assert state[WINDOW_KEY] == first
    hint = continue_idle_question(first["id"], "hint", context)
    assert "SAME step" in hint["instruction"]
    assert continue_idle_question(first["id"], "hint", context)["error"]
    record_reply_window("Try the inverse operation. Which operation undoes addition?", state)
    second = state[WINDOW_KEY]
    assert second["id"] == first["id"] and second["action"] == "explain"
    assert second["step_question"] == "What is x?"
    reveal = continue_idle_question(second["id"], "explain", context)
    assert "ONLY this current step" in reveal["instruction"]
    assert "invented student answer" in reveal["instruction"]
    record_reply_window("Subtract 2. Now what is the corresponding area?", state)
    assert state[WINDOW_KEY]["id"] != first["id"]
    assert state[WINDOW_KEY]["action"] == "hint"


def test_idle_cannot_submit_work_or_trigger_mastery_changes():
    context = SimpleNamespace(state={"temp:idle_invocation": True})
    for name in ["submit_step_response", "advance_topic_lesson", "answer_recovery_item",
                 "check_subproblem_answer", "get_problem_by_code"]:
        assert guard_idle_tool(SimpleNamespace(name=name), {}, context)["error"] == "IDLE_IS_NOT_STUDENT_WORK"
    assert guard_idle_tool(SimpleNamespace(name="choose_response_window"), {}, context) is None
    context.state["temp:idle_invocation"] = False
    assert guard_idle_tool(SimpleNamespace(name="submit_step_response"), {}, context) is None


def test_published_route_idle_reads_stored_assets_and_updates_pinned_attempt(monkeypatch):
    from agents.mathbank_tutor.tools import step_runtime_tools

    calls = []

    def call(context, method, path, json):
        calls.append(json)
        return {"route_attempt_id": "attempt", "route_release_id": "release",
                "version": len(calls) + 1, "current_step": 2 if json["advance"] else 1,
                "hint": "Stored current explanation." if json["advance"] else "Stored first insight.",
                "student_prompt": "Next checkpoint?" if json["advance"] else "Current checkpoint?",
                "mastery_recorded": False}

    monkeypatch.setattr(step_runtime_tools, "_call", call)
    state = {"tutor:compiled_route_attempt": {"route_attempt_id": "attempt", "version": 1}}
    context = SimpleNamespace(state=state)
    first = set_response_window("Current checkpoint?", 30, state)
    hinted = continue_idle_question(first["id"], "hint", context)
    assert hinted["hint"] == "Stored first insight."
    record_reply_window(hinted["markdown_block"], state)
    second = state[WINDOW_KEY]
    explained = continue_idle_question(second["id"], "explain", context)
    assert explained["current_step"] == 2 and not explained["mastery_recorded"]
    assert calls == [{"expected_version": 1, "hint_level": 1, "advance": False},
                     {"expected_version": 2, "hint_level": 5, "advance": True}]
    assert state["tutor:compiled_route_attempt"]["route_release_id"] == "release"


def test_authored_topic_idle_reveals_then_skips_without_credit(monkeypatch):
    from agents.mathbank_tutor import pedagogy_agent

    monkeypatch.setattr(pedagogy_agent, "draw_geometry_diagram", lambda *args: {"markdown_block": ""})
    plan = topic_lessons.new_plan({"taxonomy_node_id": topic_lessons.POWER, "name": "Power"})
    state = {"pedagogy:topic_plan": plan}
    record_reply_window(topic_lessons.lesson_markdown(plan), state)
    first = state[WINDOW_KEY]
    context = SimpleNamespace(state=state)
    hinted = continue_idle_question(first["id"], "hint", context)
    assert "endpoints" in hinted["markdown_block"]
    record_reply_window(hinted["markdown_block"], state)
    second = state[WINDOW_KEY]
    result = continue_idle_question(second["id"], "explain", context)
    assert "A chord is the segment" in result["markdown_block"]
    updated = state["pedagogy:topic_plan"]
    assert updated["current_unit"] == 1
    assert updated["completed_checkpoints"] == []
    assert updated["quiz_results"] == []
    assert updated["stage_status"]["0"] == "skipped"
    assert result["progress"]["completed"] == 0
    assert result["progress"]["skipped"] == 1


def test_real_adk_turns_emit_window_deltas_and_idle_does_not_submit_an_answer():
    async def run():
        model = ScriptedModel(script=[
            ("choose_response_window", {"question": "What is $2+3$?", "seconds": 45}),
            "What is $2+3$?",
            "Start at 2 and count three more. What number do you reach?",
            "The sum is 5. Next, what is $5+1$?",
            "Your answer was submitted; let's check it.",
        ])
        agent = Agent(
            name="test_timed_tutor", model=model,
            tools=[choose_response_window, continue_idle_question],
            before_model_callback=route_topic_before_model,
            after_model_callback=guard_tutor_output,
        )
        sessions = InMemorySessionService()
        session = await sessions.create_session(app_name="timed", user_id="u")
        runner = Runner(agent=agent, app_name="timed", session_service=sessions)

        async def turn(text):
            return [event async for event in runner.run_async(
                user_id="u", session_id=session.id,
                new_message=types.Content(role="user", parts=[types.Part(text=text)]),
            )]

        events = await turn("Please give me a small arithmetic checkpoint and guide me")
        window = (await sessions.get_session(app_name="timed", user_id="u", session_id=session.id)).state[WINDOW_KEY]
        assert window["seconds"] == 45
        assert any(event.actions.state_delta.get(WINDOW_KEY) == window for event in events)
        await turn(f"[Tutor idle:{window['id']}:hint]")
        second = (await sessions.get_session(app_name="timed", user_id="u", session_id=session.id)).state[WINDOW_KEY]
        assert second["action"] == "explain"
        events = await turn(f"[Tutor idle:{second['id']}:explain]")
        assert any("The sum is 5" in (part.text or "") for event in events
                   for part in event.content.parts or [])
        next_window = (await sessions.get_session(app_name="timed", user_id="u", session_id=session.id)).state[WINDOW_KEY]
        assert next_window["id"] != window["id"]
        await turn("6")
        state = (await sessions.get_session(app_name="timed", user_id="u", session_id=session.id)).state
        assert state[WINDOW_KEY] is None
        assert "completed_checkpoints" not in state

    asyncio.run(run())
