"""requirements/53 QZ-8: the quiz_generator_agent specialist — a genuine, delegated ADK
sub-agent (not just more tools on the root agent), following the exact AgentTool
state-propagation pattern already established in artifact_agents.py.

Critical detail replicated from that file (confirmed by reading its own code comment):
"AgentTool creates a new Runner; session creation does not retain temp: state" — so this
agent's tools would see no signed-in student at all unless the parent's temp:student_token
is explicitly re-injected into the child session via a before_agent_callback. The same
ContextVar-handoff mechanism used for the artifact specialists is replicated here, scoped
to just the one state key quiz tools actually need.
"""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
from typing import Any

from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.tool_context import ToolContext

from .tools.quiz_tools import QUIZ_TOOLS, _token

_QUIZ_DELEGATED_STATE: ContextVar[dict | None] = ContextVar("quiz_delegated_state", default=None)

INSTRUCTION = """\
You generate and grade personalized AIME-style, HMMT-style, proof-based, topic-based, or
skill-based practice quizzes for the signed-in learner.

- Call generate_quiz_paper to create a brand-new paper. Only pass target_skill_slugs or
  target_concept_slugs if the learner explicitly named a topic/skill; otherwise leave both
  empty so the server personalizes to the learner's own current weak areas automatically.
  Keep question_count modest (3-5) unless asked for more.
- Present the returned questions one at a time or all at once as the learner prefers. Never
  reveal or guess a correct answer yourself — the server withholds every answer/solution
  until the learner's own response is recorded via submit_quiz_answer.
- Only call submit_quiz_answer with an answer the learner themselves actually gave in this
  conversation — never invent, guess, or auto-fill a response on their behalf.
- After grading, relay the returned feedback and solution verbatim (do not add your own
  alternative solution). Say explicitly that generated solutions are PENDING-tier content,
  not an expert-reviewed answer key, if the learner asks how authoritative it is.
- Use get_quiz_review once several/all questions are answered to summarize overall
  performance, or get_quiz_paper/list_my_quizzes to resume an earlier paper.
- Diagrams are generated automatically where relevant; never claim to have drawn one
  yourself if has_diagram is false.
"""


def _restore_quiz_invocation_state(callback_context):
    state = _QUIZ_DELEGATED_STATE.get()
    if state is None:
        raise RuntimeError("The quiz specialist must be invoked through authenticated tutor delegation.")
    callback_context.state.update(state)


class QuizAgentTool(AgentTool):
    """Authenticated, bounded delegation — mirrors artifact_agents.ArtifactAgentTool's
    state-propagation mechanics exactly, scoped to the one key quiz tools need."""

    async def run_async(self, *, args: dict[str, Any], tool_context: ToolContext) -> Any:
        if not _token(tool_context):
            return {
                "error": "SIGN_IN_REQUIRED",
                "message": "Sign in to generate or answer a quiz.",
            }
        context_token = _QUIZ_DELEGATED_STATE.set(
            {"temp:student_token": tool_context.state.get("temp:student_token")}
        )
        try:
            return await asyncio.wait_for(
                super().run_async(args=args, tool_context=tool_context), timeout=90
            )
        except TimeoutError:
            return {
                "error": "QUIZ_AGENT_TIMEOUT",
                "message": "Quiz generation/grading took too long; try fewer questions.",
            }
        finally:
            _QUIZ_DELEGATED_STATE.reset(context_token)


def build_quiz_agent(model: str | LiteLlm) -> Agent:
    return Agent(
        name="quiz_generator_agent",
        model=LiteLlm(model=model) if isinstance(model, str) else model,
        description="Generates and grades personalized AIME/HMMT/proof/topic/skill-based "
                    "practice quizzes (MCQ, free-text, proof) for the signed-in learner.",
        instruction=INSTRUCTION,
        tools=QUIZ_TOOLS,
        before_agent_callback=_restore_quiz_invocation_state,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )


def quiz_agent_tool(model: str | LiteLlm) -> QuizAgentTool:
    return QuizAgentTool(agent=build_quiz_agent(model))
