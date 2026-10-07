"""Topic-first teaching plans with explicit grounding and authenticated feedback."""

from __future__ import annotations

import asyncio
import json
import re
import time

import httpx
from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from . import topic_lessons
from .tools import rest_tools
from .tools.artifact_tools import draw_geometry_diagram
from .tools.step_runtime_tools import _error, _token


def get_topic_plan(topic: str) -> dict:
    """Read an exact canonical topic and published-step-supported examples; never a solution."""
    with rest_tools._client() as client:
        response = client.get("/v1/tutor/topic-plan", params={"q": topic})
        if not response.is_success:
            return _error(response)
        return response.json()


def prepare_topic_practice(topic: str, exclude_codes: list[str] | None = None,
                           candidate_codes: list[str] | None = None) -> dict:
    """Return a teaching roadmap and complete step-supported practice; skip reported mismatches."""
    plan = get_topic_plan(topic)
    if plan.get("error") or not plan.get("matched"):
        return plan
    excluded = set(exclude_codes or [])
    problems = []
    for code in (candidate_codes if candidate_codes is not None else plan["node"].get("example_problem_codes") or [])[:10]:
        if code in excluded:
            continue
        problem = rest_tools.get_practice_problem(code)
        if problem.get("eligible"):
            problems.append(problem)
            break
    steps = "\n".join(f"{i}. {step}" for i, step in enumerate(plan["plan_steps"], 1))
    markdown = f"## Learning plan · {plan['node']['name']}\n{steps}\n\n"
    markdown += "Evidence: published step annotations; these may be machine-generated, not human verified.\n\n"
    markdown += (
        problems[0]["markdown_block"]
        if problems
        else "No complete step-supported candidate was returned in this bounded check; this does not mean the corpus has no related problems."
    )
    markdown += f"\n\n**First checkpoint:** {plan['first_checkpoint']}"
    return {**plan, "practice": problems, "markdown_block": markdown}


def _lesson_view(plan: dict, tool_context: ToolContext, notice: str = "") -> dict:
    plan = topic_lessons.ensure_tracking(plan)
    markdown = topic_lessons.lesson_markdown(plan, notice)
    artifact = None
    if plan["node_id"] == topic_lessons.POWER and plan["current_unit"] <= 1:
        try:
            artifact = draw_geometry_diagram(
                json.dumps(topic_lessons.chord_diagram("AB" if plan["current_unit"] == 0 else "CD")),
                tool_context,
            )
        except httpx.HTTPError as exc:
            artifact = {"error": type(exc).__name__, "message": "Instructional diagram service unavailable."}
        if artifact.get("error"):
            markdown += "\n\n**Diagram unavailable:** " + (artifact.get("message") or str(artifact["error"]))
        else:
            markdown += "\n\n" + artifact["markdown_block"]
    units = topic_lessons.units_for(plan)
    current = units[plan["current_unit"]]
    progress = []
    for index, unit in enumerate(units):
        short, acronym, icon = topic_lessons.STAGE_META.get(unit["stage"], (unit["title"], unit["stage"][:3], "circle"))
        seconds = plan["stage_seconds"].get(str(index), 0)
        if index == plan["current_unit"] and isinstance(plan.get("stage_started_at"), (int, float)):
            seconds += max(0, int(time.time() - plan["stage_started_at"]))
        progress.append({
            "index": index, "title": unit["title"], "short_title": short,
            "acronym": acronym, "icon": icon,
            "status": plan["stage_status"].get(str(index), "pending"),
            "is_current": index == plan["current_unit"],
            "seconds": seconds,
        })
    checkpoint = None
    if current.get("question") and (current.get("choices") or current.get("input_type")):
        checkpoint = {
            "question": current["question"],
            "choices": current.get("choices", []),
            "input_type": current.get("input_type", "single-choice"),
            "hint_available": bool(current.get("hint")),
            "hint": current.get("hint") if plan.get("hint_revealed") else None,
        }
    return {"matched": True, "intent": "LEARN_TOPIC", "stage": current["stage"],
            "current_unit": plan["current_unit"], "unit_count": plan["unit_count"],
            "completed_checkpoints": len(plan["completed_checkpoints"]),
            "artifact_status": "unavailable" if artifact and artifact.get("error") else "rendered" if artifact else "not_requested",
            "revision": plan["revision"], "progress": {
                "topic": plan["topic"], "stages": progress,
                "current_unit": plan["current_unit"],
                "completed": sum(item["status"] == "completed" for item in progress),
                "skipped": sum(item["status"] == "skipped" for item in progress),
                "checkpoint": checkpoint, "feedback": notice,
                "feedback_tone": "success" if notice.startswith("Correct.") else "hint" if notice.startswith("Hint:") else "warning" if notice.startswith("Not quite.") else None,
            }, "practice": [], "markdown_block": markdown}


def advance_topic_lesson(answer: str, expected_revision: int, tool_context: ToolContext) -> dict:
    """Grade only the current authored A-D checkpoint; never infer free-text mastery."""
    plan = tool_context.state.get("pedagogy:topic_plan")
    if not plan:
        return {"error": "NO_TOPIC_PLAN", "message": "Start or resume a topic lesson first."}
    if expected_revision != plan["revision"]:
        return {"error": "STALE_TOPIC_PLAN", "message": "This checkpoint changed; resume the current lesson."}
    updated, notice = topic_lessons.advance(plan, answer)
    tool_context.state["pedagogy:topic_plan"] = updated
    result = _lesson_view(updated, tool_context, notice)
    result["progress"]["feedback_tone"] = "success" if notice.startswith("Correct.") else "warning"
    tool_context.state["temp:pedagogy_reply"] = result["markdown_block"]
    return result


def control_topic_lesson(action: str, expected_revision: int, tool_context: ToolContext,
                         target: int = -1) -> dict:
    """Skip, jump, or reveal a hint in the persisted topic lesson."""
    plan = tool_context.state.get("pedagogy:topic_plan") if tool_context else None
    if not plan:
        return {"error": "NO_TOPIC_PLAN", "message": "Start or resume a topic lesson first."}
    if expected_revision != plan["revision"]:
        return {"error": "STALE_TOPIC_PLAN", "message": "This lesson changed; resume the current stage."}
    plan = topic_lessons.ensure_tracking(plan)
    if action == "skip":
        updated, notice = topic_lessons.skip(plan)
    elif action == "jump":
        updated, notice = topic_lessons.jump(plan, target)
    elif action == "problem":
        units = topic_lessons.units_for(plan)
        updated = plan
        for index in range(plan["current_unit"], len(units) - 1):
            if updated["stage_status"].get(str(index)) not in {"completed", "skipped"}:
                updated["stage_status"][str(index)] = "skipped"
        updated, notice = topic_lessons.jump(updated, len(units) - 1)
        notice = "Moved to the problem stage. Earlier unfinished stages are marked skipped, not completed."
    elif action == "hint":
        unit = topic_lessons.units_for(plan)[plan["current_unit"]]
        if not unit.get("hint"):
            return {"error": "HINT_UNAVAILABLE", "message": "No authored hint is available for this stage."}
        updated = plan
        updated["hint_revealed"] = True
        updated["revision"] += 1
        notice = "Hint: " + unit["hint"]
    else:
        return {"error": "INVALID_LESSON_ACTION", "message": "That lesson action is not supported."}
    tool_context.state["pedagogy:topic_plan"] = updated
    result = _lesson_view(updated, tool_context, notice)
    result["progress"]["feedback_tone"] = "hint" if action == "hint" else "warning"
    tool_context.state["temp:pedagogy_reply"] = result["markdown_block"]
    return result


def get_topic_lesson(tool_context: ToolContext) -> dict:
    """Resume the session's current lesson; never return future checkpoint answer keys."""
    plan = tool_context.state.get("pedagogy:topic_plan")
    if not plan:
        return {"error": "NO_TOPIC_PLAN", "message": "Name a topic to start a lesson."}
    result = _lesson_view(plan, tool_context)
    result["revision"] = plan["revision"]
    result["misconceptions"] = plan["misconceptions"]
    return result


def report_pedagogy_feedback(
    problem_code: str, topic: str, reason: str, tool_context: ToolContext
) -> dict:
    """Record an explicit learner relevance/annotation complaint as PENDING, never approve or publish."""
    excluded = list(tool_context.state.get("pedagogy:excluded_codes", []))
    if problem_code not in excluded:
        excluded.append(problem_code)
    tool_context.state["pedagogy:excluded_codes"] = excluded[-50:]
    token = _token(tool_context)
    if not token:
        return {
            "error": "SIGN_IN_REQUIRED",
            "message": "Sign in to save a review report; no feedback was recorded.",
        }
    with rest_tools._client() as client:
        response = client.post(
            "/v1/tutor/feedback",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "problem_code": problem_code,
                "topic": topic.strip(),
                "reason": reason.strip(),
            },
        )
        if not response.is_success:
            return _error(response)
        result = response.json()
    return result


def after_pedagogy_tool(tool, args, tool_context, tool_response):
    if tool.name == "prepare_problem_guidance":
        tool_context.state["temp:pedagogy_reply"] = tool_response.get("markdown_block") or (
            "Solution-grounded planning could not be delivered; please retry. No solution-backed approach was verified."
        )
        tool_context.state["temp:problem_guidance_ready"] = True
        if tool_response.get("status") == "ready":
            tool_context.state["pedagogy:problem_guidance"] = {
                key: tool_response[key] for key in (
                    "problem_code", "stages", "first_checkpoint", "selected_solution_id", "solution_evidence",
                )
            }
    elif tool.name == "report_pedagogy_feedback":
        tool_context.state["temp:pedagogy_replan"] = args.get("topic")
        tool_context.state["temp:feedback_notice"] = (
            (
                "Your relevance report was recorded for review; annotations remain unchanged."
                if tool_response.get("status") == "PENDING"
                else "This matching report was already reviewed and was not reopened; annotations remain unchanged."
            )
            if tool_response.get("feedback_id")
            else "Your relevance report was not saved. Sign in or retry the feedback service; this candidate is excluded in this conversation."
        )
        tool_context.state["temp:pedagogy_reply"] = tool_context.state["temp:feedback_notice"]
        if tool_response.get("status") == "PENDING" and tool_response.get("audit", {}).get("version"):
            tool_context.state["temp:retrieval_audit_evidence"] = tool_response["audit"]
            tool_context.state["temp:retrieval_audit_request"] = tool_response["audit"]
    elif tool.name == "pedagogy_agent":
        notice = tool_context.state.get("temp:feedback_notice")
        if notice and (tool_response.get("error") or not tool_response.get("matched")):
            tool_context.state["temp:pedagogy_reply"] = (
                notice + "\n\nThe follow-up teaching plan could not be delivered; please retry."
            )
            tool_context.state["temp:feedback_notice"] = None


class PedagogyAgentTool(AgentTool):
    async def run_async(self, *, args, tool_context):
        request = args.get("request")
        if not isinstance(request, str) or not request.strip() or len(request) > 1000:
            return {
                "error": "INVALID_TOPIC",
                "message": "Supply a topic name or JSON {topic,intent,target_difficulty}.",
            }
        intent = "LEARN_TOPIC"
        target_difficulty = None
        if request.lstrip().startswith("{"):
            try:
                parsed = json.loads(request)
                if not isinstance(parsed, dict) or set(parsed) - {"topic", "intent", "target_difficulty"}:
                    raise ValueError("Unsupported topic request fields.")
                request = parsed["topic"]
                intent = parsed.get("intent", "LEARN_TOPIC")
                target_difficulty = parsed.get("target_difficulty")
            except (ValueError, KeyError) as exc:
                return {"error": "INVALID_TOPIC", "message": str(exc)}
        if (not isinstance(request, str) or not request.strip() or len(request) > 200
                or intent not in {"LEARN_TOPIC", "FIND_PRACTICE", "REVIEW_TOPIC", "QUIZ_ME"}
                or (target_difficulty is not None and (type(target_difficulty) is not int or not 1 <= target_difficulty <= 5))):
            return {"error": "INVALID_TOPIC", "message": "Invalid topic, intent or difficulty (1-5)."}
        count = tool_context.state.get("temp:pedagogy_calls", 0)
        if count >= 2:
            return {
                "error": "PEDAGOGY_LIMIT",
                "message": "Teaching-plan delegation limit reached.",
            }
        tool_context.state["temp:pedagogy_calls"] = count + 1
        try:
            plan = get_topic_plan(request)
        except httpx.HTTPError as exc:
            return {
                "error": "PEDAGOGY_UNAVAILABLE",
                "message": f"Teaching evidence unavailable: {type(exc).__name__}",
            }
        if plan.get("error") or not plan.get("matched"):
            return plan
        topic_state = tool_context.state.get("pedagogy:topic_plan")
        if (not topic_state or topic_state["node_id"] != plan["node"]["taxonomy_node_id"]
                or intent == "REVIEW_TOPIC"):
            topic_state = topic_lessons.new_plan(plan["node"])
            topic_state["exposed_codes"] = list(tool_context.state.get("pedagogy:exposed_codes", []))
        if intent == "FIND_PRACTICE":
            body = {"topic": request, "limit": 10, "target_difficulty": target_difficulty,
                    "exclude_codes": tool_context.state.get("pedagogy:excluded_codes", []),
                    "exposed_codes": topic_state["exposed_codes"], "known_skills": topic_state["known_skills"]}
            headers = {"Authorization": f"Bearer {_token(tool_context)}"} if _token(tool_context) else {}
            try:
                with rest_tools._client() as client:
                    response = client.post("/v1/tutor/topic-practice", json=body, headers=headers)
                    if not response.is_success:
                        return _error(response)
                    ranking = response.json()
                plan = prepare_topic_practice(request, body["exclude_codes"],
                    [c["canonical_code"] for c in ranking.get("candidates", [])])
            except httpx.HTTPError as exc:
                return {"error": "PRACTICE_UNAVAILABLE", "message": f"Practice evidence unavailable: {type(exc).__name__}"}
            plan.update({"intent": intent, "profile_version": ranking.get("profile_version"),
                         "ranking": ranking.get("candidates", [])})
            plan["markdown_block"] = plan["markdown_block"].replace("## Learning plan", "## Practice", 1)
        else:
            if intent == "QUIZ_ME" and topic_state["authored"] and topic_state["current_unit"] == 0:
                topic_state["current_unit"] = 1
                topic_state["revision"] += 1
            tool_context.state["pedagogy:topic_plan"] = topic_state
            plan = {**plan, **_lesson_view(topic_state, tool_context)}
        # The specialist receives learner-safe evidence only, never credentials or solutions.
        safe = {
            "topic": plan["node"]["name"],
            "plan_steps": plan["plan_steps"],
            "first_checkpoint": plan["first_checkpoint"],
            "warnings": plan["warnings"],
            "intent": intent,
            "current_stage": plan.get("stage"),
        }
        try:
            await asyncio.wait_for(
                super().run_async(
                    args={"request": json.dumps(safe)}, tool_context=tool_context
                ),
                timeout=60,
            )
        except TimeoutError:
            return {
                "error": "PEDAGOGY_TIMEOUT",
                "message": "Pedagogy specialist timed out; no plan was delivered.",
            }
        shown = [p["canonical_code"] for p in plan.get("practice", [])]
        exposure = list(dict.fromkeys([
            *tool_context.state.get("pedagogy:exposed_codes", []),
            *topic_state["exposed_codes"], *shown,
        ]))[-100:]
        topic_state["exposed_codes"] = exposure
        tool_context.state["pedagogy:exposed_codes"] = exposure
        tool_context.state["pedagogy:topic_plan"] = topic_state
        notice = tool_context.state.get("temp:feedback_notice")
        if notice:
            plan["markdown_block"] = notice + "\n\n" + plan["markdown_block"]
            tool_context.state["temp:feedback_notice"] = None
        tool_context.state["temp:pedagogy_reply"] = plan["markdown_block"]
        tool_context.state["pedagogy:last_topic"] = request
        tool_context.state["pedagogy:last_codes"] = [
            p["canonical_code"] for p in plan["practice"]
        ]
        topic_state["exposed_codes"] = list(dict.fromkeys(
            topic_state["exposed_codes"] + tool_context.state["pedagogy:last_codes"]
        ))[-100:]
        tool_context.state["pedagogy:topic_plan"] = topic_state
        return plan


def pedagogy_tool(model):
    return PedagogyAgentTool(
        agent=Agent(
            name="pedagogy_agent",
            model=LiteLlm(model=model) if isinstance(model, str) else model,
            description='Teach before practice. Request is a topic name (LEARN_TOPIC) or JSON {topic,intent,target_difficulty}; intent LEARN_TOPIC/FIND_PRACTICE/REVIEW_TOPIC/QUIZ_ME.',
            instruction="Review the supplied answer-free teaching roadmap and return a concise provisional rationale. "
            "Never solve a problem, invent source evidence, or disclose private reasoning. "
            "Machine-approved evidence is not human verification. The deterministic plan controls learner output.",
        )
    )


def route_topic_before_model(callback_context, llm_request):
    """Exact short topic prompts route to the pedagogy specialist without relying on model choice."""
    state = callback_context.state
    audit = state.get("temp:retrieval_audit_request")
    if audit:
        state["temp:retrieval_audit_request"] = None
        return LlmResponse(content=types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(
            name="retrieval_audit_agent", args={"request": json.dumps(audit)}))]))
    replan = state.get("temp:pedagogy_replan")
    if replan:
        state["temp:pedagogy_replan"] = None
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        function_call=types.FunctionCall(
                            name="pedagogy_agent", args={"request": replan}
                        )
                    )
                ],
            )
        )
    if state.get("temp:pedagogy_routed_invocation") == callback_context.invocation_id:
        if state.get("temp:problem_guidance_ready"):
            return LlmResponse(content=types.Content(role="model", parts=[
                types.Part(text=state["temp:pedagogy_reply"]),
            ]))
        return None
    state["temp:pedagogy_routed_invocation"] = callback_context.invocation_id
    state["temp:pedagogy_reply"] = None
    state["temp:formatted_reply"] = None
    state["temp:problem_guidance_ready"] = False
    content = callback_context.user_content
    query = (
        "".join(p.text or "" for p in content.parts or [] if not p.thought).strip()
        if content
        else ""
    )
    if not query or len(query) > 300 or "\n" in query:
        return None
    codes = re.findall(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b", query)
    runtime_request = "solve_attempt_id" in query or (
        codes and codes[0].startswith("PRASOLOV_")
        and re.search(r"\bstep[- ]by[- ]step\b", query, re.IGNORECASE)
    )
    if not runtime_request and len(set(codes)) == 1 and re.search(
        r"\b(help me think|guide me|walk me through|help me solve)\b", query, re.IGNORECASE
    ):
        return LlmResponse(content=types.Content(role="model", parts=[
            types.Part(function_call=types.FunctionCall(
                name="prepare_problem_guidance", args={"problem_code": codes[0]},
            )),
        ]))
    last_codes = state.get("pedagogy:last_codes", [])
    last_topic = state.get("pedagogy:last_topic")
    if (
        last_topic
        and len(last_codes) == 1
        and re.search(
            r"\b(not.*related|unrelated|wrong topic|not.*align)\b", query, re.IGNORECASE
        )
    ):
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        function_call=types.FunctionCall(
                            name="report_pedagogy_feedback",
                            args={
                                "problem_code": last_codes[0],
                                "topic": last_topic,
                                "reason": query,
                            },
                        )
                    )
                ],
            )
        )
    intent = topic_lessons.resolve_intent(query, last_topic)
    plan_state = state.get("pedagogy:topic_plan")
    if plan_state:
        action = None
        target = -1
        if re.fullmatch(r"(?:skip|skip this|skip step)", query, re.IGNORECASE):
            action = "skip"
        elif re.fullmatch(r"(?:hint|show hint|give me a hint)", query, re.IGNORECASE):
            action = "hint"
        elif re.fullmatch(r"(?:jump to|go to) problem", query, re.IGNORECASE):
            action = "problem"
        else:
            match = re.fullmatch(r"(?:jump to|go to) step ([1-9]\d*)", query, re.IGNORECASE)
            if match:
                action, target = "jump", int(match.group(1)) - 1
        if action:
            return LlmResponse(content=types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(
                name="control_topic_lesson",
                args={"action": action, "expected_revision": plan_state["revision"], "target": target},
            ))]))
        current_unit = topic_lessons.units_for(plan_state)[plan_state["current_unit"]]
        if (current_unit.get("input_type") == "numeric"
                and re.fullmatch(r"\d+(?:\.\d+)?", query)):
            return LlmResponse(content=types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(
                name="advance_topic_lesson", args={"answer": query, "expected_revision": plan_state["revision"]}))]))
    if intent["intent"] == "CONTINUE_ATTEMPT" and state.get("pedagogy:topic_plan"):
        plan_state = state["pedagogy:topic_plan"]
        if re.fullmatch(r"(?:option |choice )?[ABCD]", query, re.IGNORECASE):
            return LlmResponse(content=types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(
                name="advance_topic_lesson", args={"answer": query, "expected_revision": plan_state["revision"]}))]))
        view = _lesson_view(plan_state, callback_context)
        state["temp:pedagogy_reply"] = view["markdown_block"]
        return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=view["markdown_block"])]))
    if intent["intent"] not in {"LEARN_TOPIC", "FIND_PRACTICE", "QUIZ_ME", "REVIEW_TOPIC"} or not intent.get("topic"):
        state["pedagogy:intent"] = intent["intent"]
        return None
    try:
        plan = get_topic_plan(intent["topic"])
    except httpx.HTTPError as exc:
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        text=f"Topic grounding is unavailable ({type(exc).__name__}); please retry. No concept match was verified."
                    )
                ],
            )
        )
    if plan.get("error"):
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        text="Topic grounding is unavailable. No concept match was verified; please retry."
                    )
                ],
            )
        )
    if plan.get("matched"):
        state["pedagogy:intent"] = intent["intent"]
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        function_call=types.FunctionCall(
                            name="pedagogy_agent", args={"request": json.dumps({
                                "topic": intent["topic"], "intent": intent["intent"],
                                "target_difficulty": intent.get("target_difficulty")})}
                        )
                    )
                ],
            )
        )
    if (intent["intent"] in {"FIND_PRACTICE", "QUIZ_ME", "REVIEW_TOPIC"}
            or plan.get("candidates")
            or re.match(r"^(teach me|learn|explain|help me learn)\b", query, re.IGNORECASE)):
        options = [node["name"] for node in plan.get("candidates", [])[:8]]
        message = ("No unique canonical topic match was verified. No practice problem was selected. "
                   "Please name the concept or technique more precisely.")
        if options:
            message += "\n\nPossible topics: " + ", ".join(options) + "."
        state["pedagogy:intent"] = intent["intent"]
        state["temp:pedagogy_reply"] = message
        return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=message)]))
    # Greetings and other general requests remain with the root, not unrelated practice retrieval.
    return None
