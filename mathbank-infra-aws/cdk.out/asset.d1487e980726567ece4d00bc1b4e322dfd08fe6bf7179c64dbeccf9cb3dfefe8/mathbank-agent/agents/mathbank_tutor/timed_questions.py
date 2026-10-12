"""Session-local response windows; idle events are never learner answers."""

from __future__ import annotations

import re
from uuid import uuid4

import httpx
from google.adk.tools.tool_context import ToolContext

WINDOW_KEY = "tutor:response_window"
IDLE_PATTERN = re.compile(r"\[Tutor idle:([0-9a-f-]{36}):(hint|explain)\]")


def response_seconds(question: str) -> int:
    """Give longer symbolic or multi-part questions more working time."""
    return min(180, max(30, 30 + len(question.split()) * 2 + question.count("$") * 3))


def set_response_window(question: str, seconds: int, state) -> dict:
    window = {
        "id": str(uuid4()),
        "question": question,
        "step_question": question,
        "seconds": seconds,
        "action": "hint",
    }
    state[WINDOW_KEY] = window
    return window


def choose_response_window(question: str, seconds: int, tool_context: ToolContext) -> dict:
    """Choose 15-300 active seconds for the ONE checkpoint in your forthcoming reply.

    Call before posing a learner question. This does not grade or advance a lesson.
    Do not include a solution in question. Use longer windows for calculations.
    """
    if not isinstance(question, str) or not question.strip() or len(question) > 2000:
        return {"error": "INVALID_TIMED_QUESTION", "message": "Supply one short checkpoint."}
    if type(seconds) is not int or not 15 <= seconds <= 300:
        return {"error": "INVALID_RESPONSE_WINDOW", "message": "Choose 15-300 active seconds."}
    tool_context.state["temp:chosen_response_window"] = {
        "question": question.strip(), "seconds": seconds,
    }
    return {"question": question.strip(), "seconds": seconds}


def continue_idle_question(checkpoint_id: str, action: str, tool_context: ToolContext) -> dict:
    """Handle a client-reported active-time expiry, never as an answer or mastery."""
    window = tool_context.state.get(WINDOW_KEY)
    if not window or window["id"] != checkpoint_id or window["action"] != action:
        return {"error": "STALE_RESPONSE_WINDOW", "message": "That question has already changed."}
    tool_context.state[WINDOW_KEY] = None
    tool_context.state["temp:idle_question"] = window
    compiled = tool_context.state.get("tutor:compiled_route_attempt")
    guidance = tool_context.state.get("pedagogy:problem_guidance") or {}
    if compiled or guidance.get("route_release_id"):
        return request_compiled_route_help(1 if action == "hint" else 5, action == "explain", tool_context)
    topic_plan = tool_context.state.get("pedagogy:topic_plan")
    if topic_plan:
        from . import topic_lessons
        from .pedagogy_agent import control_topic_lesson

        unit = topic_lessons.units_for(topic_plan)[topic_plan["current_unit"]]
        if unit.get("hint") and unit.get("explanation") and unit["question"] in window.get("step_question", window["question"]):
            result = control_topic_lesson(
                "hint" if action == "hint" else "skip",
                topic_plan["revision"], tool_context,
            )
            if result.get("error"):
                return result
            if action == "explain":
                result["markdown_block"] = (
                    "**Let's work through this step:** " + unit["explanation"]
                    + "\n\n" + result["markdown_block"]
                )
            tool_context.state["temp:pedagogy_reply"] = result["markdown_block"]
            tool_context.state["temp:problem_guidance_ready"] = True
            return result
    if action == "hint":
        instruction = (
            "No student answer was submitted. Offer one concrete simpler insight for this "
            "checkpoint and ask a smaller version of the SAME step. Do not solve the whole "
            "problem or claim the learner answered. This is the first idle window."
        )
    else:
        instruction = (
            "No student answer was submitted after the extra insight. Explain the answer "
            "to ALL requested parts of step_question, but ONLY this current step, then "
            "move to the next small checkpoint in the "
            "existing teaching route. Do not give the full problem solution in one turn. "
            "Explicitly treat this as tutor-explained, not learner completion or mastery. "
            "Do not call answer-grading tools with an invented student answer. If the route "
            "is finished, summarize and stop asking; never loop back to the same checkpoint."
            " Ask the next concrete math question directly, not whether the learner "
            "would like to continue. Do not leave the old checkpoint for them to finish."
        )
    guidance = tool_context.state.get("pedagogy:problem_guidance") or {}
    return {
        "question": window["question"],
        "step_question": window.get("step_question", window["question"]),
        "action": action,
        "instruction": instruction,
        "teaching_context": {
            key: guidance[key] for key in ("problem_code", "stages") if key in guidance
        },
    }


def request_compiled_route_help(hint_level: int, advance: bool, tool_context: ToolContext) -> dict:
    """Fetch H1-H4 or H5 from the pinned published route, never invent a new step.

    Use when the learner asks for a hint/explanation on a compiled route.
    Only H5 may advance, after explaining the current checkpoint. It records tutor
    explanation, NOT a correct student answer or mastery. Paste markdown_block unchanged.
    """
    from .tools.step_runtime_tools import _call

    compiled = tool_context.state.get("tutor:compiled_route_attempt")
    if not compiled:
        return {"error": "SIGN_IN_REQUIRED", "message": "Sign in to continue this saved teaching route."}
    if type(hint_level) is not int or not 1 <= hint_level <= 5 or (advance and hint_level != 5):
        return {"error": "INVALID_ROUTE_HELP", "message": "Choose H1-H5; only a current-step explanation may advance."}
    try:
        result = _call(
            tool_context, "POST",
            f"/v1/tutor/route-attempts/{compiled['route_attempt_id']}/assist",
            json={"expected_version": compiled["version"], "hint_level": hint_level, "advance": advance},
        )
    except httpx.HTTPError:
        return {"error": "ROUTE_TRANSPORT_ERROR",
                "message": "Could not load the saved checkpoint; please retry."}
    if result.get("error"):
        return result
    tool_context.state["tutor:compiled_route_attempt"] = result
    prompt = result.get("student_prompt")
    markdown = result["hint"] + (
        "\n\n**Checkpoint:** " + prompt if prompt else
        "\n\nThis route is finished. We worked through these steps together; no mastery was recorded."
    )
    tool_context.state["temp:pedagogy_reply"] = markdown
    tool_context.state["temp:problem_guidance_ready"] = True
    return {**result, "markdown_block": markdown}


def guard_idle_tool(tool, args, tool_context):
    """No model may turn an inactivity event into submitted work or assessment."""
    if tool_context.state.get("temp:idle_invocation") and tool.name in {
        "advance_topic_lesson", "submit_step_response", "answer_recovery_item",
        "check_subproblem_answer", "diagnose_step_gap", "start_recovery_plan",
        "get_problem_by_code", "prepare_problem_guidance",
    }:
        return {
            "error": "IDLE_IS_NOT_STUDENT_WORK",
            "message": "No student answer was submitted. Explain this step without grading or restarting.",
        }
    return None


def record_reply_window(text: str, state) -> None:
    """Attach pacing to final learner questions, including deterministic authored replies."""
    selected = state.get("temp:chosen_response_window")
    idle = state.get("temp:idle_question")
    state["temp:chosen_response_window"] = None
    state["temp:idle_question"] = None
    # Strip source links before finding the last question, not URL query strings.
    prose = re.sub(r"!?\[[^\]]*\]\([^)]*\)", "", text)
    checkpoint = re.search(
        r"\*\*(?:Your first checkpoint|First checkpoint|Checkpoint):\*\*\s*([^\n]+)",
        prose, re.IGNORECASE,
    )
    questions = re.findall(r"[^?\n]+[?]", prose)
    if not selected and not checkpoint and not questions:
        state[WINDOW_KEY] = None
        return
    question = (
        selected["question"] if selected else checkpoint.group(1).strip()
        if checkpoint else questions[-1].strip().lstrip("* ")
    )
    seconds = selected["seconds"] if selected else response_seconds(question)
    window = set_response_window(question, seconds, state)
    if idle and idle["action"] == "hint":
        window = {
            **window, "id": idle["id"], "action": "explain",
            "step_question": idle.get("step_question", idle["question"]),
        }
        state[WINDOW_KEY] = window
