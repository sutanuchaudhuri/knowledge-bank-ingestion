"""Orchestrates one full mock-exam paper generation (requirements/64 §3, §4, continued):
parse the natural-language request, resolve the topic, consult the cached question pool
first, retrieve real corpus candidates (the hybrid semantic + lexical + graph
`search_problems` RAG step), draft+critique only the slots the pool couldn't fill —
CONCURRENTLY on one asyncio event loop — run a whole-paper aggregate diversity/dedup pass
whose flagged slots are also regenerated concurrently, then persist via mathbank-rest's
split start_paper/finalize_paper calls, writing every newly approved question back into
the pool so it keeps growing. A durable, pollable progress-event log is posted at every
phase (from a background, order-preserving queue, so posting never blocks generation).

Question pool (quiz.question_pool, migration 052): critic-approved questions with full
solutions, keyed by the request inputs (style, requested difficulty band, normalized
topic, resolved concept). An "almost the same" request (same style/type/difficulty plus
a similar topic or the same resolved concept) is served from the pool first, skipping
questions this student has already been served.

Concurrency is safe: every model call constructs a fresh Strands `Agent` (one instance
is not re-entrant) and awaits `Agent.invoke_async`; MCP calls dispatch onto the
MCPClient's own background loop; blocking httpx REST calls run in `asyncio.to_thread`.
"""
from __future__ import annotations

import asyncio
import itertools
import json
import logging
from collections import Counter
from contextlib import asynccontextmanager

from strands.tools.mcp.mcp_client import MCPClient

from mathbank_exam_agent import rest_client
from mathbank_exam_agent.aggregate_critic_agent import review_paper_async
from mathbank_exam_agent.config import get_settings
from mathbank_exam_agent.critic_agent import review_question_async
from mathbank_exam_agent.diagnosis_agent import diagnose
from mathbank_exam_agent.generator_agent import draft_question_async
from mathbank_exam_agent.intake import parse_intake, parse_intake_async
from mathbank_exam_agent.math_format import math_format_issues, mcq_structure_issues
from mathbank_exam_agent.schemas import GeneratedQuestionDraft, GenerationIntake

logger = logging.getLogger(__name__)

_MAX_PARALLEL_QUESTIONS = 8  # a sane cap on concurrent LLM calls, independent of question_count
_MAX_AGGREGATE_FIX_ROUNDS = 2
_CANDIDATE_POOL_LIMIT = 12
_NO_DIFFICULTY_SIGNAL = "no corpus difficulty signal available for this topic — use judgment"


class GenerationQualityError(RuntimeError):
    pass


class _ProgressLog:
    """Monotonically-increasing ordinal counter + poster for one quiz_id's
    generation-event log (requirements/64 continued). `post` only enqueues — a single
    background task delivers events in ordinal order, so the web UI's `since_ordinal`
    polling never skips an event and generation never waits on a progress round trip.
    Call `aclose()` before returning to flush the queue."""

    def __init__(self, quiz_id: str):
        self._quiz_id = quiz_id
        self._ordinal = itertools.count(1)
        self._queue: asyncio.Queue[dict | None] = asyncio.Queue()
        self._worker = asyncio.create_task(self._drain())

    def post(self, *, phase: str, status: str, question_ordinal: int | None = None, detail: str = "") -> None:
        self._queue.put_nowait({
            "ordinal": next(self._ordinal), "phase": phase, "status": status,
            "question_ordinal": question_ordinal, "detail": detail,
        })

    async def _drain(self) -> None:
        while (event := await self._queue.get()) is not None:
            await asyncio.to_thread(rest_client.post_generation_event, self._quiz_id, **event)

    async def aclose(self) -> None:
        self._queue.put_nowait(None)
        await self._worker


@asynccontextmanager
async def _competitions_session():
    """Async counterpart of mcp_tools.competitions_session: MCPClient start/stop block,
    so they run off the event loop."""
    client = MCPClient(url=get_settings().mcp_competitions_url)
    await asyncio.to_thread(client.start)
    try:
        yield client
    finally:
        await asyncio.to_thread(client.stop, None, None, None)


def _concept_slug_from_problems(problems: list[dict]) -> str | None:
    slugs = Counter(
        evidence["slug"]
        for problem in problems
        for evidence in problem.get("graph_evidence", [])
        if evidence.get("kind") == "TESTS"
    )
    return slugs.most_common(1)[0][0] if slugs else None


def _search_problems(client: MCPClient, tool_use_id: str, query: str, limit: int) -> list[dict]:
    result = client.call_tool_sync(tool_use_id, "search_problems", {"query": query, "limit": limit})
    if result.get("status") != "success":
        return []
    return json.loads(result["content"][0]["text"])


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
    return _concept_slug_from_problems(_search_problems(client, "topic-resolve", intake.topic_hint, 5))


def _resolve_difficulty_signal(concept_slug: str | None) -> str:
    """Real core.problem.difficulty_band distribution for the resolved topic
    (requirements/64 §5 point 1) — falls back to a plain "no corpus signal available"
    string (never a fabricated one) if the topic didn't resolve to a real slug, or no
    corpus rows exist for it yet."""
    if not concept_slug:
        return _NO_DIFFICULTY_SIGNAL
    try:
        dist = rest_client.get_difficulty_distribution(concept_slug=concept_slug)
    except Exception:  # noqa: BLE001 -- a missing signal is not fatal to generation
        logger.exception("difficulty-distribution lookup failed for concept %s", concept_slug)
        return _NO_DIFFICULTY_SIGNAL
    if not dist:
        return _NO_DIFFICULTY_SIGNAL
    return f"corpus difficulty distribution for concept '{concept_slug}': {dist}"


def _candidate_window(pool: list[dict], *, question_index: int, size: int = 4) -> list[dict]:
    """Rotates through the shared candidate pool so different questions in the same
    paper see a different slice of real corpus problems (requirements/64 continued —
    "the actual question might be generated on the basis of N retrievals", not every
    question citing the identical set)."""
    if not pool:
        return []
    offset = (question_index * size) % len(pool)
    window = pool[offset:offset + size]
    if len(window) < size:
        window += pool[: size - len(window)]
    return window


async def _generate_one_question(
    tools: list, *, intake: GenerationIntake, question_type: str, difficulty_signal: str,
    candidate_sources: list[dict], progress: _ProgressLog, question_ordinal: int,
    initial_feedback: str | None = None,
) -> tuple[GeneratedQuestionDraft, list[dict], bool]:
    """Runs the bounded generator<->critic loop for one question. Returns the final
    (possibly revised) draft, the full round-by-round revision log (requirements/64 §4's
    "audit, don't just store the final state" decision), and whether the loop exhausted
    without ever reaching APPROVE (requirements/64 §4's "kept with a NEEDS_HUMAN_REVIEW
    flag rather than looping forever" — a bounded, observable failure mode, not a
    silently-accepted question the critic's own last review still flagged as wrong)."""
    revision_log: list[dict] = []
    revision_feedback = initial_feedback
    draft: GeneratedQuestionDraft | None = None
    needs_human_review = True
    max_rounds = get_settings().max_critic_revision_rounds
    for round_number in range(1, max_rounds + 2):
        progress.post(
            phase="DRAFT_QUESTION", status="STARTED", question_ordinal=question_ordinal,
            detail=f"drafting (round {round_number})",
        )
        draft = await draft_question_async(
            tools=tools, style=intake.style, question_type=question_type,
            topic_hint=intake.topic_hint or "general competition mathematics",
            difficulty_band=intake.difficulty_band, candidate_sources=candidate_sources,
            revision_feedback=revision_feedback,
        )
        progress.post(
            phase="DRAFT_QUESTION", status="DONE", question_ordinal=question_ordinal,
            detail=f"drafted (round {round_number})",
        )
        progress.post(
            phase="CRITIC_REVIEW", status="STARTED", question_ordinal=question_ordinal,
            detail=f"critic reviewing (round {round_number})",
        )
        verdict = await review_question_async(
            draft, requested_difficulty=intake.difficulty_band, corpus_difficulty_signal=difficulty_signal,
        )
        deterministic_issues = math_format_issues(draft) + mcq_structure_issues(draft)
        requested_difficulty = (intake.difficulty_band or "").lower()
        if requested_difficulty in {"hard", "very_hard"}:
            reasoning_tags = set(draft.concept_slugs) | set(draft.technique_slugs)
            if len(reasoning_tags) < 2:
                deterministic_issues.append(
                    "Hard questions must identify at least two concepts/techniques whose interaction is required"
                )
            if not draft.synthesis_rationale.strip():
                deterministic_issues.append(
                    "Hard questions must explain the required interaction in synthesis_rationale"
                )
            available_source_codes = {
                source.get("canonical_code") for source in candidate_sources
                if source.get("canonical_code")
            }
            used_source_codes = {source.canonical_code for source in draft.inspiration_sources}
            if len(available_source_codes) >= 2 and len(used_source_codes) < 2:
                deterministic_issues.append(
                    "Hard questions must synthesize distinct contributions from at least two supplied sources"
                )
            if not verdict.synthesis_ok:
                deterministic_issues.append(
                    "The critic found no non-trivial synthesis of multiple ideas or constraints"
                )
        if not verdict.math_format_ok:
            deterministic_issues.append(
                "Correct the mathematical delimiters and notation for the exam UI's KaTeX renderer"
            )
        if deterministic_issues:
            verdict.verdict = "REVISE"
            issue_feedback = "; ".join(dict.fromkeys(deterministic_issues))
            verdict.feedback = " ".join(
                part for part in (verdict.feedback.strip(), issue_feedback) if part
            )
        progress.post(
            phase="CRITIC_REVIEW", status="DONE", question_ordinal=question_ordinal,
            detail=f"critic: {verdict.verdict} (round {round_number})",
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
        if round_number >= 2:
            revision_feedback = (
                "Discard the previous setup entirely and compose a fundamentally different "
                "problem rather than patching or renumbering it. " + revision_feedback
            )
    return draft, revision_log, needs_human_review


def _slot_question_type(intake: GenerationIntake, i: int) -> str:
    return intake.question_types[i % len(intake.question_types)] if intake.question_types else "MCQ"


def _assign_pool_questions(
    intake: GenerationIntake, matches: list[dict],
) -> dict[int, tuple[dict, GeneratedQuestionDraft]]:
    """Fills paper slots (0-based) from pool matches, honouring each slot's question type
    and the server's ranking (best topic match, least served first). Unfilled slots — and
    any pooled row that no longer validates — are left for fresh generation."""
    by_type: dict[str, list[tuple[dict, GeneratedQuestionDraft]]] = {}
    for match in matches:
        try:
            draft = _draft_from_pool_question(match["question"])
        except Exception:  # noqa: BLE001 -- a stale/malformed pool row is skipped, not fatal
            logger.warning("skipping unusable pool question %s", match.get("pool_question_id"))
            continue
        by_type.setdefault(match["question_type"], []).append((match, draft))
    assigned: dict[int, tuple[dict, GeneratedQuestionDraft]] = {}
    for i in range(intake.question_count):
        bucket = by_type.get(_slot_question_type(intake, i))
        if bucket:
            assigned[i] = bucket.pop(0)
    return assigned


def _draft_from_pool_question(question: dict) -> GeneratedQuestionDraft:
    """A reviewable draft view of a pooled question (only for the aggregate diversity
    pass — the persisted payload is the pooled question itself)."""
    correct = question.get("correct_answer") or {}
    return GeneratedQuestionDraft(
        question_type=question["question_type"], prompt_text=question["prompt_text"],
        prompt_latex=question.get("prompt_latex"), options=question.get("options"),
        correct_key=correct.get("correct_key"), expected_answer=correct.get("expected_answer"),
        grading_rubric=correct.get("grading_rubric"),
        option_explanations=question.get("option_explanations") or {},
        solution_steps=question.get("solution_steps") or [question.get("solution_text", "")],
        key_insight=question.get("key_insight", ""),
        synthesis_rationale=question.get("synthesis_rationale", ""),
        difficulty_band=question.get("difficulty_band") or "medium",
        concept_slugs=question.get("concept_slugs") or [],
        technique_slugs=question.get("technique_slugs") or [],
    )


def _payload_from_pool_match(match: dict) -> dict:
    payload = {k: v for k, v in match["question"].items() if k not in ("revision_log", "add_to_pool")}
    payload["pool_question_id"] = match["pool_question_id"]
    payload["revision_log"] = [{
        "served_from_pool": match["pool_question_id"],
        "topic_similarity": match.get("topic_similarity"),
    }]
    return payload


def _payload_from_draft(draft: GeneratedQuestionDraft, *, revision_log: list[dict],
                        resolved_slug: str | None, add_to_pool: bool) -> dict:
    options = [o.model_dump() for o in draft.options] if draft.options else None
    correct_answer = (
        {"correct_key": draft.correct_key} if draft.question_type == "MCQ"
        else {"expected_answer": draft.expected_answer, "grading_rubric": draft.grading_rubric}
    )
    return {
        "question_type": draft.question_type, "prompt_text": draft.prompt_text,
        "prompt_latex": draft.prompt_latex, "options": options, "correct_answer": correct_answer,
        "solution_text": _solution_text_from_steps(draft.solution_steps), "key_insight": draft.key_insight,
        "solution_steps": draft.solution_steps,
        "difficulty_band": draft.difficulty_band, "revision_log": revision_log,
        "concept_slugs": draft.concept_slugs or ([resolved_slug] if resolved_slug else []),
        "technique_slugs": draft.technique_slugs, "skill_slugs": [],
        "option_explanations": draft.option_explanations,
        "inspiration_sources": [s.model_dump() for s in draft.inspiration_sources],
        "add_to_pool": add_to_pool,
    }


async def _match_pool(student_id: str, intake: GenerationIntake, resolved_slug: str | None) -> list[dict]:
    try:
        return await asyncio.to_thread(
            rest_client.match_pool_questions, student_id=student_id, style=intake.style,
            question_types=intake.question_types or ["MCQ"], difficulty_band=intake.difficulty_band,
            topic=intake.topic_hint, concept_slugs=[resolved_slug] if resolved_slug else [],
            limit=min(50, intake.question_count * 3),
        )
    except Exception:  # noqa: BLE001 -- the pool is an accelerator, never a hard dependency
        logger.exception("question-pool lookup failed; generating every question fresh")
        return []


def _solution_text_from_steps(steps: list[str]) -> str:
    """Derives the human-readable, numbered solution text from the generator's
    authoritative structured solution_steps — never the other way around, so
    solution_text can never drift out of sync with the real, computed step_count."""
    return "\n".join(f"{i}. {step}" for i, step in enumerate(steps, start=1))


def start_generation(student_id: str, nl_request: str, *, exam_mode: bool = True) -> str:
    """Phase 1 of 2 (requirements/64 continued — live-progress design): parses the
    natural-language request and mints a quiz_id immediately, status GENERATING. Fast —
    one intake-parsing LLM call, no question drafting yet. The caller gets this quiz_id
    back right away so it can start polling generation-progress and kick off
    `run_generation` (phase 2) separately, without blocking on the actual, much slower
    generation work."""
    intake = parse_intake(nl_request)
    return rest_client.start_paper({
        "student_id": student_id, "style": intake.style, "title": intake.title,
        "requested_question_count": intake.question_count,
        "requested_question_types": intake.question_types,
        "target_skill_slugs": intake.target_skill_slugs,
        "target_concept_slugs": intake.target_concept_slugs,
        "difficulty_band": intake.difficulty_band,
        "generated_by": f"openai:{get_settings().generator_model_id}",
        "exam_mode": exam_mode, "time_limit_seconds": intake.time_limit_seconds,
    })


async def run_generation_async(quiz_id: str, student_id: str, nl_request: str) -> dict:
    """Phase 2 of 2: pool lookup first, then concurrent generate+critique for the
    remaining slots (grounded in retrieved corpus candidates), a whole-paper aggregate
    diversity pass whose flagged slots are regenerated concurrently, then persisted via
    finalize_paper — which also writes every newly approved question into the pool.
    Re-parses the same nl_request `start_generation` already parsed (this service is
    stateless across the two HTTP calls) — concurrently with MCP session start-up, so it
    costs no wall-clock time. Returns the same shape quiz_runtime.get_quiz() returns."""
    progress = _ProgressLog(quiz_id)
    try:
        async with _competitions_session() as client:
            intake, tools = await asyncio.gather(
                parse_intake_async(nl_request), asyncio.to_thread(client.list_tools_sync),
            )
            progress.post(
                phase="INTAKE", status="DONE",
                detail=f"parsed: {intake.question_count} questions, {intake.style} style",
            )

            # One search serves both topic resolution and the candidate pool.
            progress.post(phase="TOPIC_RESOLVE", status="STARTED")
            candidate_pool: list[dict] = []
            if intake.topic_hint:
                candidate_pool = await asyncio.to_thread(
                    _search_problems, client, "candidate-pool", intake.topic_hint, _CANDIDATE_POOL_LIMIT,
                )
            resolved_slug = (
                intake.target_concept_slugs[0] if intake.target_concept_slugs
                else _concept_slug_from_problems(candidate_pool)
            )
            progress.post(phase="TOPIC_RESOLVE", status="DONE", detail=f"resolved concept: {resolved_slug or 'none'}")

            progress.post(phase="DIFFICULTY_SIGNAL", status="STARTED")
            progress.post(phase="POOL_LOOKUP", status="STARTED")
            difficulty_signal, pool_matches = await asyncio.gather(
                asyncio.to_thread(_resolve_difficulty_signal, resolved_slug),
                _match_pool(student_id, intake, resolved_slug),
            )
            progress.post(phase="DIFFICULTY_SIGNAL", status="DONE")
            pooled = _assign_pool_questions(intake, pool_matches)
            progress.post(
                phase="POOL_LOOKUP", status="DONE",
                detail=f"{len(pooled)} of {intake.question_count} questions served from the question pool",
            )

            payloads: dict[int, dict] = {i: _payload_from_pool_match(m) for i, (m, _) in pooled.items()}
            drafts: dict[int, GeneratedQuestionDraft] = {i: d for i, (_, d) in pooled.items()}
            revision_logs: dict[int, list[dict]] = {i: payloads[i]["revision_log"] for i in pooled}
            needs_review: dict[int, bool] = {i: False for i in pooled}
            semaphore = asyncio.Semaphore(_MAX_PARALLEL_QUESTIONS)

            async def generate_slot(i: int, feedback: str | None = None):
                async with semaphore:
                    return i, *await _generate_one_question(
                        tools, intake=intake, question_type=_slot_question_type(intake, i),
                        difficulty_signal=difficulty_signal,
                        candidate_sources=_candidate_window(candidate_pool, question_index=i),
                        progress=progress, question_ordinal=i + 1, initial_feedback=feedback,
                    )

            for i, draft, log, flagged in await asyncio.gather(
                *(generate_slot(i) for i in range(intake.question_count) if i not in pooled)
            ):
                drafts[i], revision_logs[i], needs_review[i] = draft, log, flagged
                payloads.pop(i, None)

            rejected_ordinals = [i + 1 for i, rejected in needs_review.items() if rejected]
            if rejected_ordinals:
                message = (
                    "Generation stopped because the correctness/difficulty critic did not approve "
                    f"question(s) {rejected_ordinals} after all revision attempts."
                )
                progress.post(phase="FAILED", status="FAILED", detail=message)
                await asyncio.to_thread(rest_client.fail_paper, quiz_id, student_id, message)
                raise GenerationQualityError(message)

            # --------------------------------------------------------------- aggregate pass
            diversity = None
            for fix_round in range(1, _MAX_AGGREGATE_FIX_ROUNDS + 1):
                progress.post(phase="AGGREGATE_DIVERSITY_CHECK", status="STARTED", detail=f"pass {fix_round}")
                diversity = await review_paper_async({i + 1: d for i, d in drafts.items()})
                progress.post(
                    phase="AGGREGATE_DIVERSITY_CHECK", status="DONE",
                    detail=f"pass {fix_round}: {diversity.verdict}, {len(diversity.flagged)} flagged",
                )
                flags = {f.ordinal - 1: f for f in diversity.flagged if f.ordinal - 1 in drafts}
                if diversity.verdict == "APPROVE" or not flags:
                    diversity = None
                    break
                for i, flag in flags.items():
                    progress.post(phase="AGGREGATE_FIX", status="STARTED", question_ordinal=i + 1, detail=flag.issue)
                # A flagged pooled question is replaced by a fresh generation.
                for i, draft, log, flagged in await asyncio.gather(
                    *(generate_slot(i, flag.feedback) for i, flag in flags.items())
                ):
                    issue = flags[i].issue
                    drafts[i], needs_review[i] = draft, flagged
                    revision_logs[i] = revision_logs[i] + [{"aggregate_fix_round": fix_round, "issue": issue}] + log
                    payloads.pop(i, None)
                    progress.post(phase="AGGREGATE_FIX", status="DONE", question_ordinal=i + 1)
            if diversity is not None:
                # Exhausted every fix-up round and the last pass still flagged something —
                # a bounded, observable failure mode, not silently accepted or looped forever.
                for flag in diversity.flagged:
                    i = flag.ordinal - 1
                    if i in needs_review:
                        needs_review[i] = True
                        revision_logs[i] = revision_logs[i] + [{"needs_human_review": True, "unresolved_issue": flag.issue}]

            rejected_ordinals = [i + 1 for i, rejected in needs_review.items() if rejected]
            if rejected_ordinals:
                message = (
                    "Generation stopped because whole-paper review did not approve "
                    f"question(s) {rejected_ordinals} after all fix attempts."
                )
                progress.post(phase="FAILED", status="FAILED", detail=message)
                await asyncio.to_thread(rest_client.fail_paper, quiz_id, student_id, message)
                raise GenerationQualityError(message)

        questions_payload: list[dict] = []
        for i in sorted(drafts):
            if i in payloads:  # still the pooled question, untouched
                payloads[i]["revision_log"] = revision_logs[i]
                questions_payload.append(payloads[i])
                continue
            if needs_review[i]:
                logger.warning(
                    "question %d exhausted revision rounds without a clean APPROVE "
                    "(topic=%r) — flagged NEEDS_HUMAN_REVIEW, not silently accepted",
                    i + 1, intake.topic_hint,
                )
                revision_logs[i].append({"needs_human_review": True})
            questions_payload.append(_payload_from_draft(
                drafts[i], revision_log=revision_logs[i], resolved_slug=resolved_slug,
                add_to_pool=not needs_review[i],
            ))

        progress.post(phase="PERSIST", status="STARTED")
        result = await asyncio.to_thread(rest_client.finalize_paper, quiz_id, {
            "student_id": student_id, "generated_by": f"openai:{get_settings().generator_model_id}",
            "questions": questions_payload,
            "pool_topic": intake.topic_hint or None,
            "pool_concept_slugs": [resolved_slug] if resolved_slug else [],
        })
        progress.post(phase="PERSIST", status="DONE")
        progress.post(phase="DONE", status="DONE", detail="paper ready")
        return result
    finally:
        await progress.aclose()


def run_generation(quiz_id: str, student_id: str, nl_request: str) -> dict:
    """Synchronous wrapper around run_generation_async for non-async callers."""
    return asyncio.run(run_generation_async(quiz_id, student_id, nl_request))


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
