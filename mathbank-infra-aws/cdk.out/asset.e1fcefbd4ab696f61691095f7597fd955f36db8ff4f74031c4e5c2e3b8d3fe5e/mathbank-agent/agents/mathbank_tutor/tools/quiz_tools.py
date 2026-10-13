"""requirements/53 QZ-8: ADK tools backing the quiz_generator_agent sub-agent.

Follows the exact auth/call convention established in step_runtime_tools.py: the signed-in
student's REST bearer token arrives as ADK *temp* session state (never persisted), and every
tool is a thin, typed wrapper whose docstring is read by the LLM as its own tool description.
"""
from __future__ import annotations

import os
from typing import Any

import httpx
from google.adk.tools.tool_context import ToolContext

REST_BASE_URL = os.environ.get("MATHBANK_REST_BASE_URL", "http://127.0.0.1:8000")
TOKEN_STATE_KEY = "temp:student_token"

SIGN_IN_REQUIRED = {
    "error": "SIGN_IN_REQUIRED",
    "message": "Generating or answering a quiz needs a signed-in student; ask the learner "
               "to sign in first.",
}


def _client() -> httpx.Client:
    return httpx.Client(base_url=REST_BASE_URL, timeout=90.0)


def _token(tool_context: ToolContext | None) -> str | None:
    if tool_context is None:
        return None
    try:
        return tool_context.state.get(TOKEN_STATE_KEY) or None
    except Exception:  # noqa: BLE001 — no state in an unusual runner
        return None


def _error(response: httpx.Response) -> dict:
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, dict):
        return {"error": detail.get("code") or f"HTTP_{response.status_code}",
                "message": detail.get("message"), "status": response.status_code}
    return {"error": f"HTTP_{response.status_code}",
            "message": detail if isinstance(detail, str) else None, "status": response.status_code}


def _call(tool_context: ToolContext | None, method: str, path: str, *, json: dict | None = None) -> dict:
    token = _token(tool_context)
    if not token:
        return dict(SIGN_IN_REQUIRED)
    with _client() as client:
        response = client.request(method, path, json=json, headers={"Authorization": f"Bearer {token}"})
    if response.status_code >= 400:
        return _error(response)
    return response.json()


def generate_quiz_paper(
    style: str, tool_context: ToolContext, question_count: int = 5,
    question_types: list[str] | None = None, target_skill_slugs: list[str] | None = None,
    target_concept_slugs: list[str] | None = None, difficulty_band: str = "",
) -> dict[str, Any]:
    """Generate a brand-new, personalized question paper for the signed-in learner.

    style: AIME, HMMT, PROOF_BASED, TOPIC_BASED, SKILL_BASED, or MIXED.
    question_count: 1-20 (default 5; keep it small, e.g. 3-5, unless the learner asks for more
        — generation is sequential and each question takes real time).
    question_types: subset of MCQ, FREE_TEXT, PROOF (default MCQ+FREE_TEXT).
    target_skill_slugs / target_concept_slugs: supply ONLY if the learner names a specific
        topic/skill; otherwise leave both empty and the server personalizes to the learner's
        own weakest concepts/techniques automatically.
    Problems are freshly generated, inspired by real corpus problems but never copied from
    them. Diagrams are included automatically where a geometry question benefits from one.
    Returns the answer-free paper — never read or guess the correct answer yourself; the
    server withholds it until the learner actually responds to a question.
    """
    return _call(tool_context, "POST", "/v1/quiz/generate", json={
        "style": style, "question_count": question_count,
        "question_types": question_types or ["MCQ", "FREE_TEXT"],
        "target_skill_slugs": target_skill_slugs or [],
        "target_concept_slugs": target_concept_slugs or [],
        "difficulty_band": difficulty_band or None,
    })


def get_quiz_paper(quiz_id: str, tool_context: ToolContext) -> dict[str, Any]:
    """Re-fetch an existing quiz paper (answer-free) — use to resume showing an in-progress
    paper, never to peek at answers."""
    return _call(tool_context, "GET", f"/v1/quiz/{quiz_id}")


def submit_quiz_answer(
    quiz_id: str, question_id: str, tool_context: ToolContext,
    selected_key: str = "", response_text: str = "", time_spent_seconds: int = 0,
) -> dict[str, Any]:
    """Submit the learner's own answer to one quiz question and reveal its grading + solution.

    Use selected_key for an MCQ question (e.g. "B"); use response_text for FREE_TEXT/PROOF
    (the learner's own words/work, never yours). Only call this with an answer the learner
    themselves actually gave — never invent or guess a response on their behalf. The returned
    solution is PENDING-tier generated content (not an expert-reviewed answer key); say so if
    asked. Each question accepts exactly one submission.
    """
    body: dict = {}
    if selected_key:
        body["selected_key"] = selected_key
    if response_text:
        body["response_text"] = response_text
    if time_spent_seconds:
        body["time_spent_seconds"] = time_spent_seconds
    return _call(tool_context, "POST", f"/v1/quiz/{quiz_id}/questions/{question_id}/respond", json=body)


def get_quiz_review(quiz_id: str, tool_context: ToolContext) -> dict[str, Any]:
    """Full post-attempt review: every question, the learner's own response, correctness,
    feedback, and solution. Use once the learner has answered some or all questions and wants
    to review their results."""
    return _call(tool_context, "GET", f"/v1/quiz/{quiz_id}/review")


def list_my_quizzes(tool_context: ToolContext) -> dict[str, Any]:
    """List the learner's own past generated quiz papers with status/question count."""
    result = _call(tool_context, "GET", "/v1/quiz/mine")
    return {"quizzes": result} if isinstance(result, list) else result


QUIZ_TOOLS = [generate_quiz_paper, get_quiz_paper, submit_quiz_answer, get_quiz_review, list_my_quizzes]
