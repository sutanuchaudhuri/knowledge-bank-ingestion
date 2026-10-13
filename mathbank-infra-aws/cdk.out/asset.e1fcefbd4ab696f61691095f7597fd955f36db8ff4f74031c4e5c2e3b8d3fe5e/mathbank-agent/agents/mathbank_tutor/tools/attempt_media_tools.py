"""Owner-authorized multimodal context; approval remains a student UI action."""

from urllib.parse import quote

from google.adk.tools.tool_context import ToolContext

from .step_runtime_tools import _call


def get_multimodal_attempt(submission_id: str, tool_context: ToolContext) -> dict:
    """Read the signed-in student's original evidence, candidate/approved steps and assessments.

    Never treat machine candidates as approved student work or silently correct them.
    Unassessed steps are pending, not incorrect. Ask the student to review and explicitly
    approve candidates in the attempt workspace before discussing reasoning assessments.
    """
    return _call(
        tool_context,
        "GET",
        f"/v1/attempt-media/submissions/{quote(submission_id, safe='')}",
    )


def get_multimodal_step_assessment(
    learner_attempt_id: str,
    step_id: str,
    tool_context: ToolContext,
) -> dict:
    """Read an approved step's assessment and exact evidence citations without running a model."""
    return _call(
        tool_context,
        "GET",
        f"/v1/attempt-media/attempts/{quote(learner_attempt_id, safe='')}/steps/"
        f"{quote(step_id, safe='')}/assessment",
    )


ATTEMPT_MEDIA_TOOLS = [get_multimodal_attempt, get_multimodal_step_assessment]
