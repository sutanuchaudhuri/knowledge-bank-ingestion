"""Solution-grounded problem planning without exposing reference solutions."""

from __future__ import annotations

from urllib.parse import quote

from .tools import rest_tools
from .tools.step_runtime_tools import _error


def prepare_problem_guidance(problem_code: str) -> dict:
    """Load question/graph/figures and a solution-grounded plan; never return raw solutions."""
    context = rest_tools.get_problem_learning_context(problem_code)
    if context.get("error"):
        return context
    with rest_tools._client() as client:
        response = client.post("/v1/tutor/guidance-plan", json={"problem_code": problem_code}, timeout=60.0)
        if not response.is_success:
            return _error(response)
        plan = response.json()
    figures = rest_tools.get_problem_diagrams(problem_code)
    if isinstance(figures, dict) and figures.get("error"):
        return figures
    code = quote(problem_code, safe="")
    evidence = plan["solution_evidence"]
    if plan.get("status") != "ready":
        markdown = (
            f"No stored solution reference is available for **{problem_code}**. "
            "I cannot claim a solution-grounded teaching plan. "
            "We can discuss the statement provisionally; what have you tried?"
        )
    else:
        steps = "\n".join(f"{index}. {stage}" for index, stage in enumerate(plan["stages"], 1))
        markdown = (
            f"## Learning plan · {problem_code}\n\n"
            f"**Why this route:** {plan['rationale']}\n\n{steps}\n\n"
            f"**Your first checkpoint:** {plan['first_checkpoint']}\n\n"
            f"**Evidence:** {evidence['references_considered']} stored solution records "
            "were supplied to the planner. Their source status is not a correctness certification."
        )
    if plan.get("warnings"):
        markdown += "\n\n" + "\n".join(plan["warnings"])
    for figure in figures:
        if figure.get("markdown"):
            markdown += "\n\n" + figure["markdown"]
    markdown += f"\n\n[Problem and source details](/learn?problem={code})"
    safe_plan = {key: plan[key] for key in (
        "problem_code", "status", "selected_solution_id", "rationale", "stages",
        "first_checkpoint", "solution_evidence", "provenance", "warnings",
    ) if key in plan}
    return {**safe_plan, "context": context, "diagram_count": len(figures), "markdown_block": markdown}
