"""Solution-grounded problem planning without exposing reference solutions."""

from __future__ import annotations

import logging

import httpx

from .tools import rest_tools
from .tools.step_runtime_tools import _error

logger = logging.getLogger(__name__)


def _load_guidance_inputs(problem_code: str) -> tuple[dict, list, dict] | dict:
    stage = "canonical learning context"
    try:
        context = rest_tools.get_problem_learning_context(problem_code)
        if context.get("error"):
            return context
        stage = "source diagrams"
        figures = rest_tools.get_problem_diagrams(problem_code)
        if isinstance(figures, dict) and figures.get("error"):
            return figures
        stage = "solution-grounded teaching plan"
        with rest_tools._client() as client:
            response = client.post(
                "/v1/tutor/guidance-plan", json={"problem_code": problem_code}, timeout=60.0
            )
            if not response.is_success:
                return _error(response)
            plan = response.json()
        return context, figures, plan
    except httpx.HTTPError as exc:
        logger.warning("Problem guidance %s failed: %s", stage, type(exc).__name__)
        return {
            "error": "GUIDANCE_TRANSPORT_ERROR",
            "stage": stage,
            "message": f"Could not load {stage}; please retry. No teaching plan was accepted.",
        }


def prepare_problem_guidance(problem_code: str) -> dict:
    """Load question/graph/figures and a solution-grounded plan; never return raw solutions."""
    inputs = _load_guidance_inputs(problem_code)
    if isinstance(inputs, dict):
        return inputs
    context, figures, plan = inputs
    if plan.get("status") != "ready":
        markdown = (
            f"No published teaching route is available for **{problem_code}**. "
            "I cannot start an approved step-by-step route yet. "
            "We can discuss the statement provisionally; what have you tried?"
        )
    else:
        steps = "\n".join(f"{index}. {stage}" for index, stage in enumerate(plan["stages"], 1))
        markdown = (
            f"## Learning plan · {problem_code}\n\n"
            f"**Why this route:** {plan['rationale']}\n\n{steps}\n\n"
            f"**Your first checkpoint:** {plan['first_checkpoint']}"
        )
    for figure in figures:
        if figure.get("markdown"):
            markdown += "\n\n" + figure["markdown"]
    safe_plan = {key: plan[key] for key in (
        "problem_code", "status", "selected_solution_id", "rationale", "stages",
        "first_checkpoint", "solution_evidence", "provenance", "warnings",
        "route_release_id",
    ) if key in plan}
    return {**safe_plan, "context": context, "diagram_count": len(figures), "markdown_block": markdown}
