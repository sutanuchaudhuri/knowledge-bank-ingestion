"""MathBank tutor agent — Google ADK agent, OpenAI model via LiteLLM.

Tools call mathbank-rest, which performs hybrid (semantic + lexical) RAG
retrieval over Postgres (search.embedding / search.chunk) joined back to the
canonical corpus tables (core.problem, knowledge.concept, ...). See
mathematics_tutor_db_plan/agent/ for the full design and flow docs.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm

from .tools.rest_tools import (
    get_corpus_coverage,
    get_problem_by_code,
    get_problems_for_concept,
    list_competitions,
    list_concepts,
    search_problems,
)

load_dotenv()

# Checks the shell environment (e.g. ~/.zshrc) first; load_dotenv() above only
# fills OPENAI_API_KEY from .env if it isn't already set, never overrides it.
if not os.environ.get("OPENAI_API_KEY"):
    raise RuntimeError(
        "OPENAI_API_KEY not found in the shell environment (~/.zshrc) or mathbank-agent/.env. "
        "Export it in your shell, or set OPENAI_API_KEY=... in .env (see .env.example)."
    )

MODEL = os.environ.get("MATHBANK_AGENT_MODEL", "openai/gpt-4o-mini")

INSTRUCTION = """\
You are the MathBank tutor assistant. You answer questions about a corpus of
competition mathematics problems (AMC, AIME, HMMT, SMT, PUMaC, CHMMC, CMM,
Math Prize for Girls) stored in PostgreSQL, retrieved via hybrid semantic +
lexical search tools — never invent a problem, competition, or solution that
your tools did not return.

Guidelines:
- For any question about what problems exist on a topic ("recent questions
  on combinatorics", "problems about cyclic quadrilaterals"), call
  search_problems. Set recent_first=true whenever the user says
  recent/latest/newest.
- To show a full solution or answer for a specific problem, call
  get_problem_by_code with its canonical_code (from a prior search_problems
  result).
- If asked about corpus completeness/size, call get_corpus_coverage.
- If a search returns no results, say so plainly — do not fabricate a problem.
- Every problem you mention must include its canonical_code and competition/year
  so the user (or a future student-profile feature) can look it up again.
- The current caller may be anonymous or an admin; you have no learner history
  or attempt data yet (student-profile-aware retrieval — mastery, exclusion of
  already-attempted problems — is a planned follow-up, not available today).
"""

root_agent = Agent(
    name="mathbank_tutor",
    model=LiteLlm(model=MODEL),
    description="Answers questions about the MathBank competition-math corpus using hybrid RAG over Postgres.",
    instruction=INSTRUCTION,
    tools=[
        search_problems,
        get_problem_by_code,
        list_competitions,
        get_corpus_coverage,
        list_concepts,
        get_problems_for_concept,
    ],
)
