"""Orchestrates one full mock-exam paper generation (requirements/64 §3, §4): parse the
natural-language request, resolve the topic to a real concept slug, fetch a real corpus
difficulty signal, run the generator<->critic loop for each requested question (bounded
to `max_critic_revision_rounds`), then persist the finished paper via mathbank-rest's
admin-gated import endpoint. mathbank-exam-agent never writes to Postgres directly —
every write below goes through rest_client.py (requirements/64 §3).
"""
from __future__ import annotations

import json
import logging
from collections import Counter

from strands.tools.mcp.mcp_client import MCPClient

from mathbank_exam_agent import rest_client
from mathbank_exam_agent.config import get_settings
from mathbank_exam_agent.critic_agent import review_question
from mathbank_exam_agent.diagnosis_agent import diagnose
from mathbank_exam_agent.generator_agent import draft_question
from mathbank_exam_agent.intake import parse_intake
from mathbank_exam_agent.mcp_tools import competitions_session
from mathbank_exam_agent.schemas import GeneratedQuestionDraft, GenerationIntake

logger = logging.getLogger(__name__)


def _resolve_topic_concept_slug(client: MCPClient, intake: GenerationIntake) -> str | None:
    """Resolves a free-text `topic_hint` (or an explicitly-given target_concept_slugs
    entry) to one real concept slug, via the same `search_problems` MCP tool the
    generator agent itself calls — its results already carry each matched problem's
    `graph_evidence` (concept/technique tags), confirmed live this session. A plain
    direct tool call, not an LLM reasoning step: this is fixed, deterministic lookup
    logic, not judgment, so it shouldn't burn a model call."""
    if intake.target_concept_slugs:
        return intake.target_concept_slugs[0]
    if not intake.topic_hint:
        return None
    result = client.call_tool_sync("topic-resolve", "search_problems", {"query": intake.topic_hint, "limit": 5})
    if result.get("status") != "success":
        return None
    problems = json.loads(result["content"][0]["text"])
    slugs = Counter(
        evidence["slug"]
        for problem in problems
        for evidence in problem.get("graph_evidence", [])
        if evidence.get("kind") == "TESTS"
    )
    return slugs.most_common(1)[0][0] if slugs else None


def _resolve_difficulty_signal(concept_slug: str | None) -> str:
    """Real core.problem.difficulty_band distribution for the resolved topic
    (requirements/64 §5 point 1) — falls back to a plain "no corpus signal available"
    string (never a fabricated one) if the topic didn't resolve to a real slug, or no
    corpus rows exist for it yet."""
    if not concept_slug:
        return "no corpus difficulty signal available for this topic — use judgment"
    try:
        dist = rest_client.get_difficulty_distribution(concept_slug=concept_slug)
    except Exception:  # noqa: BLE001 -- a missing signal is not fatal to generation
        logger.exception("difficulty-distribution lookup failed for concept %s", concept_slug)
        return "no corpus difficulty signal available for this topic — use judgment"
    if not dist:
        return "no corpus difficulty signal available for this topic — use judgment"
    return f"corpus difficulty distribution for concept '{concept_slug}': {dist}"


def _generate_one_question(
    tools: list, *, intake: GenerationIntake, question_type: str, difficulty_signal: str,
) -> tuple[GeneratedQuestionDraft, list[dict], bool]:
    """Runs the bounded generator<->critic loop for one question. Returns the final
    (possibly revised) draft, the full round-by-round revision log (requirements/64 §4's
    "audit, don't just store the final state" decision), and whether the loop exhausted
    without ever reaching APPROVE (requirements/64 §4's "kept with a NEEDS_HUMAN_REVIEW
    flag rather than looping forever" — a bounded, observable failure mode, not a
    silently-accepted question the critic's own last review still flagged as wrong)."""
    revision_log: list[dict] = []
    revision_feedback: str | None = None
    draft: GeneratedQuestionDraft | None = None
    needs_human_review = True
    max_rounds = get_settings().max_critic_revision_rounds
    for round_number in range(1, max_rounds + 2):
        draft = draft_question(
            tools=tools, style=intake.style, question_type=question_type,
            topic_hint=intake.topic_hint or "general competition mathematics",
            difficulty_band=intake.difficulty_band, revision_feedback=revision_feedback,
        )
        verdict = review_question(
            draft, requested_difficulty=intake.difficulty_band, corpus_difficulty_signal=difficulty_signal,
        )
        revision_log.append({
            "round": round_number, "verdict": verdict.verdict, "feedback": verdict.feedback,
            "prompt_text": draft.prompt_text,
        })
        if verdict.verdict == "APPROVE":
            needs_human_review = False
            break
        if round_number > max_rounds:
            break
        revision_feedback = verdict.feedback
    return draft, revision_log, needs_human_review


def generate_exam_paper(student_id: str, nl_request: str, *, exam_mode: bool = True) -> dict:
    """The full pipeline (requirements/64 §3, §4): NL request -> intake -> per-question
    generate+critique -> persisted paper. Returns the same shape quiz_runtime.get_quiz()
    already returns (via mathbank-rest's /v1/quiz-integration/papers import response)."""
    intake = parse_intake(nl_request)
    questions_payload: list[dict] = []
    with competitions_session() as client:
        tools = client.list_tools_sync()
        resolved_slug = _resolve_topic_concept_slug(client, intake)
        difficulty_signal = _resolve_difficulty_signal(resolved_slug)
        for i in range(intake.question_count):
            qtype = intake.question_types[i % len(intake.question_types)] if intake.question_types else "MCQ"
            draft, revision_log, needs_human_review = _generate_one_question(
                tools, intake=intake, question_type=qtype, difficulty_signal=difficulty_signal,
            )
            if needs_human_review:
                logger.warning(
                    "question exhausted %d revision rounds without critic APPROVE "
                    "(topic=%r, type=%s) — flagged NEEDS_HUMAN_REVIEW, not silently accepted",
                    get_settings().max_critic_revision_rounds, intake.topic_hint, qtype,
                )
                revision_log.append({"needs_human_review": True})
            options = [o.model_dump() for o in draft.options] if draft.options else None
            correct_answer = (
                {"correct_key": draft.correct_key} if draft.question_type == "MCQ"
                else {"expected_answer": draft.expected_answer, "grading_rubric": draft.grading_rubric}
            )
            questions_payload.append({
                "question_type": draft.question_type, "prompt_text": draft.prompt_text,
                "prompt_latex": draft.prompt_latex, "options": options, "correct_answer": correct_answer,
                "solution_text": draft.solution_text, "key_insight": draft.key_insight,
                "difficulty_band": draft.difficulty_band, "revision_log": revision_log,
                "concept_slugs": draft.concept_slugs or ([resolved_slug] if resolved_slug else []),
                "technique_slugs": draft.technique_slugs, "skill_slugs": [],
                "option_explanations": draft.option_explanations,
            })

    return rest_client.import_paper({
        "student_id": student_id, "style": intake.style, "title": intake.title,
        "requested_question_count": intake.question_count,
        "requested_question_types": intake.question_types,
        "target_skill_slugs": intake.target_skill_slugs,
        "target_concept_slugs": intake.target_concept_slugs or ([resolved_slug] if resolved_slug else []),
        "difficulty_band": intake.difficulty_band,
        "generated_by": f"openai:{get_settings().generator_model_id}",
        "exam_mode": exam_mode, "time_limit_seconds": intake.time_limit_seconds,
        "questions": questions_payload,
    })


def diagnose_exam(quiz_id: str, student_id: str) -> dict:
    """Post-exam diagnosis (requirements/64 §7) — requires the paper to already be
    GRADED (mathbank-rest's get_paper_for_diagnosis/write_diagnosis both enforce this,
    requirements/64's quiz_runtime.py additions); this function is pure orchestration,
    all the real synthesis happens in diagnosis_agent.diagnose()."""
    diagnosis_input = rest_client.get_diagnosis_input(quiz_id, student_id)
    report = diagnose(diagnosis_input)
    return rest_client.write_diagnosis(quiz_id, {
        "student_id": student_id,
        "time_management_verdict": report.time_management_verdict,
        "pacing_notes": [n.model_dump() for n in report.pacing_notes],
        "reasoning_guidance": [n.model_dump() for n in report.reasoning_guidance],
        "improvement_areas": [a.model_dump() for a in report.improvement_areas],
        "generated_by": f"openai:{get_settings().diagnosis_model_id}",
    })

