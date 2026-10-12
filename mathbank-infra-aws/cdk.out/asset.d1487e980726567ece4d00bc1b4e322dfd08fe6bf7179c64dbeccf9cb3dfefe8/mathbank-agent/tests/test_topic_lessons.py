import asyncio
import copy
import json
from types import SimpleNamespace

import pytest
from agents.mathbank_tutor import pedagogy_agent as p
from agents.mathbank_tutor import topic_lessons as lessons
from agents.mathbank_tutor.formatter_agent import guard_tutor_output
from google.adk import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from test_artifact_agents import ScriptedModel


@pytest.mark.parametrize("query,intent,topic", [
    ("Power of point", "LEARN_TOPIC", "Power of point"),
    ("teach me power of point", "LEARN_TOPIC", "power of point"),
    ("give me a power of point problem", "FIND_PRACTICE", "power of point"),
    ("give me a hard power of point problem", "FIND_PRACTICE", "power of point"),
    ("give me a problem on power of point", "FIND_PRACTICE", "power of point"),
    ("I know the theory; just give me a hard problem", "FIND_PRACTICE", "Power of point"),
    ("what went wrong in this solution?", "EXPLAIN_STEP", "Power of point"),
    ("quiz me", "QUIZ_ME", "Power of point"),
    ("review Power of point", "REVIEW_TOPIC", "Power of point"),
    ("B", "CONTINUE_ATTEMPT", "Power of point"),
])
def test_intents(query, intent, topic):
    result = lessons.resolve_intent(query, "Power of point")
    assert result["intent"] == intent
    assert result["topic"] == topic


def test_wrong_answer_stays_then_progresses_through_all_stages_without_mastery():
    plan = lessons.new_plan({"name": "Power of a point", "taxonomy_node_id": lessons.POWER})
    original = copy.deepcopy(plan)
    wrong, notice = lessons.advance(plan, "A")
    assert plan == original and wrong["current_unit"] == 0
    assert wrong["misconceptions"] == ["CHORD_ENDPOINTS"] and "Not quite" in notice
    assert lessons.advance(wrong, "continue")[0] == wrong
    for answer in ("B", "B", "9", "B", "A", "B"):
        wrong, _ = lessons.advance(wrong, answer)
    assert wrong["status"] == "READY_FOR_PRACTICE"
    assert wrong["completed_checkpoints"] == list(range(6))
    assert "mastery" not in wrong
    assert "answer_value" not in json.dumps(wrong) and "units" not in wrong


def test_skip_jump_and_hint_keep_distinct_progress_and_hide_unrevealed_hint(monkeypatch):
    monkeypatch.setattr(p, "draw_geometry_diagram", lambda *args: {"markdown_block": "Validated diagram"})
    clock = [100.0]
    monkeypatch.setattr(lessons.time, "time", lambda: clock[0])
    plan = lessons.new_plan({"name": "Power of point", "taxonomy_node_id": lessons.POWER})
    context = SimpleNamespace(state={"pedagogy:topic_plan": plan})

    first_view = p.get_topic_lesson(context)
    assert first_view["progress"]["stages"][0]["status"] == "active"
    assert first_view["progress"]["checkpoint"]["hint"] is None
    assert lessons.POWER_UNITS[0]["hint"] not in json.dumps(first_view["progress"])

    clock[0] = 112.0
    skipped = p.control_topic_lesson("skip", plan["revision"], context)
    stored = context.state["pedagogy:topic_plan"]
    assert stored["current_unit"] == 1
    assert stored["stage_status"]["0"] == "skipped"
    assert skipped["progress"]["skipped"] == 1
    assert skipped["progress"]["stages"][0]["seconds"] == 12

    jumped = p.control_topic_lesson("jump", stored["revision"], context, target=4)
    stored = context.state["pedagogy:topic_plan"]
    assert stored["current_unit"] == 4
    assert stored["stage_status"]["1"] == "pending"
    assert stored["stage_status"]["4"] == "active"
    assert jumped["progress"]["feedback_tone"] == "warning"
    assert jumped["progress"]["completed"] == 0

    hinted = p.control_topic_lesson("hint", stored["revision"], context)
    assert hinted["progress"]["checkpoint"]["hint"] == lessons.POWER_UNITS[4]["hint"]
    assert hinted["progress"]["feedback_tone"] == "hint"
    assert "answer" not in json.dumps(hinted["progress"])


def test_jump_to_problem_marks_remaining_stages_skipped_not_completed(monkeypatch):
    monkeypatch.setattr(p, "draw_geometry_diagram", lambda *args: {"markdown_block": "Validated diagram"})
    plan = lessons.new_plan({"name": "Power of point", "taxonomy_node_id": lessons.POWER})
    context = SimpleNamespace(state={"pedagogy:topic_plan": plan})
    result = p.control_topic_lesson("problem", plan["revision"], context)
    stored = context.state["pedagogy:topic_plan"]
    assert stored["current_unit"] == len(lessons.POWER_UNITS) - 1
    assert stored["stage_status"]["0"] == "skipped"
    assert stored["stage_status"]["5"] == "skipped"
    assert stored["stage_status"]["6"] == "active"
    assert stored["completed_checkpoints"] == []
    assert result["progress"]["completed"] == 0


def test_chord_diagram_has_exact_circle_incidence_and_product():
    diagram = lessons.chord_diagram("AB")
    points = {e["id"]: (e["x"], e["y"]) for e in diagram["elements"] if e["kind"] == "POINT"}
    for name in "ABCD":
        x, y = points[name]
        assert (x - 300) ** 2 + (y - 220) ** 2 == pytest.approx(140 ** 2)
    assert (points["P"][0] - points["A"][0]) * (points["B"][0] - points["P"][0]) == pytest.approx(
        (points["P"][1] - points["C"][1]) * (points["D"][1] - points["P"][1]))
    assert all(e["auxiliary"] for e in diagram["elements"] if e["id"] in {"PC", "PD"})


def test_stale_revision_does_not_advance():
    plan = lessons.new_plan({"name": "Power of point", "taxonomy_node_id": lessons.POWER})
    context = SimpleNamespace(state={"pedagogy:topic_plan": plan})
    assert p.advance_topic_lesson("B", 99, context)["error"] == "STALE_TOPIC_PLAN"
    assert context.state["pedagogy:topic_plan"] == plan


@pytest.mark.parametrize(
    "query,action,target",
    [("skip step", "skip", -1), ("show hint", "hint", -1), ("jump to step 4", "jump", 3), ("jump to problem", "problem", -1)],
)
def test_lesson_navigation_is_routed_deterministically(query, action, target):
    plan = lessons.new_plan({"name": "Power of point", "taxonomy_node_id": lessons.POWER})
    context = SimpleNamespace(
        state={"pedagogy:topic_plan": plan, "pedagogy:last_topic": "Power of point"},
        invocation_id=f"test-{query}",
        user_content=types.Content(role="user", parts=[types.Part(text=query)]),
    )
    result = p.route_topic_before_model(context, None)
    call = result.content.parts[0].function_call
    assert call.name == "control_topic_lesson"
    assert call.args == {"action": action, "expected_revision": plan["revision"], "target": target}


def test_numeric_checkpoint_answer_routes_to_deterministic_validator():
    plan = lessons.new_plan({"name": "Power of point", "taxonomy_node_id": lessons.POWER})
    for answer in ("B", "B"):
        plan, _ = lessons.advance(plan, answer)
    context = SimpleNamespace(
        state={"pedagogy:topic_plan": plan, "pedagogy:last_topic": "Power of point"},
        invocation_id="test-numeric-answer",
        user_content=types.Content(role="user", parts=[types.Part(text="9")]),
    )
    result = p.route_topic_before_model(context, None)
    call = result.content.parts[0].function_call
    assert call.name == "advance_topic_lesson"
    assert call.args == {"answer": "9", "expected_revision": plan["revision"]}


def test_real_runner_restores_lesson_and_advances_only_current_checkpoint(monkeypatch):
    async def run():
        monkeypatch.setattr(p, "draw_geometry_diagram", lambda *args: {"markdown_block": "Validated diagram"})
        sessions = InMemorySessionService()
        plan = lessons.new_plan({"name": "Power of point", "taxonomy_node_id": lessons.POWER})
        session = await sessions.create_session(app_name="test", user_id="u",
            state={"pedagogy:topic_plan": plan, "pedagogy:last_topic": "Power of point"})
        root = Agent(name="test", model=ScriptedModel(script=["Wrong rewrite", "Wrong again"]),
            tools=[p.advance_topic_lesson], before_model_callback=p.route_topic_before_model,
            after_model_callback=guard_tutor_output)
        runner = Runner(agent=root, app_name="test", session_service=sessions)
        for answer, index in (("A", 0), ("B", 1)):
            events = [event async for event in runner.run_async(user_id="u", session_id=session.id,
                new_message=types.Content(role="user", parts=[types.Part(text=answer)]))]
            stored = await sessions.get_session(app_name="test", user_id="u", session_id=session.id)
            assert stored.state["pedagogy:topic_plan"]["current_unit"] == index
            assert "Wrong" not in events[-1].content.parts[0].text
            runner = Runner(agent=root, app_name="test", session_service=sessions)
        assert stored.state["pedagogy:topic_plan"]["quiz_results"][0]["correct"] is False
        assert stored.state["pedagogy:topic_plan"]["quiz_results"][1]["correct"] is True
    asyncio.run(run())
