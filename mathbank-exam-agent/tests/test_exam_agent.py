"""requirements/64 (continued): unit tests for mathbank-exam-agent's pure logic (no
network/LLM calls) — schema validation and the deterministic graph_evidence-slug-
resolution/candidate-pool-rotation/complexity-signal helpers. A real, opt-in live
end-to-end test (NL request -> parallel generator<->critic loop, grounded in retrieved
corpus candidates -> aggregate diversity pass -> persisted paper with inspiration
sources + complexity signals -> response -> diagnosis, against the real OpenAI API, the
real deployed MCP server, and the real Neon Postgres instance) was run manually this
session, confirmed genuine parallel execution via the generation-event log, and is not
re-encoded here as an automated pytest case — each real call costs real tokens and takes
60-150+ seconds, unlike every other live test in this repo's pytest suites (which hit
free local/Neon resources only). Tracked as a known gap in requirements/64 §11, not
silently skipped.
"""
from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import mathbank_exam_agent.exam_service as exam_service
from mathbank_exam_agent.exam_service import (
    _candidate_window,
    _resolve_topic_concept_slug,
    _solution_text_from_steps,
)
from mathbank_exam_agent.generator_agent import _ensure_inspiration_source, _valid_canonical_codes
from mathbank_exam_agent.math_format import (
    math_format_issues,
    mcq_structure_issues,
    normalize_draft_math,
    normalize_math_text,
)
from mathbank_exam_agent.schemas import (
    CriticVerdict,
    DiagnosisReport,
    DiversityVerdict,
    FlaggedQuestion,
    GeneratedQuestionDraft,
    GenerationIntake,
    InspirationSource,
)


def test_generation_intake_requires_question_count_in_range():
    import pydantic
    import pytest

    with pytest.raises(pydantic.ValidationError):
        GenerationIntake(style="AIME", question_count=0, question_types=["MCQ"], title="t")
    with pytest.raises(pydantic.ValidationError):
        GenerationIntake(style="AIME", question_count=21, question_types=["MCQ"], title="t")
    intake = GenerationIntake(style="AIME", question_count=5, question_types=["MCQ"], title="t")
    assert intake.question_count == 5
    assert intake.target_concept_slugs == []


def test_generated_question_draft_roundtrip():
    draft = GeneratedQuestionDraft(
        question_type="MCQ", prompt_text="2+2=?",
        options=[{"key": "A", "text": "3"}, {"key": "B", "text": "4"}],
        correct_key="B", solution_steps=["Add 2 and 2."], key_insight="Basic arithmetic.",
        difficulty_band="easy",
    )
    assert draft.model_dump()["options"][1]["key"] == "B"


def test_critic_verdict_defaults_distractor_quality_ok_true():
    verdict = CriticVerdict(
        verdict="APPROVE", correctness_ok=True, difficulty_match_ok=True, clarity_ok=True,
        math_format_ok=True, feedback="Looks good.",
    )
    assert verdict.distractor_quality_ok is True
    assert verdict.synthesis_ok is True
    assert verdict.math_format_ok is True


def test_normalize_math_text_repairs_json_escape_damage_and_double_delimiters():
    malformed = "Use \\\\( n^{\x0crac{1}{2}} \\\\) and \text{integer}."
    assert normalize_math_text(malformed) == r"Use \( n^{\frac{1}{2}} \) and \text{integer}."


def test_normalize_draft_math_repairs_every_student_visible_field():
    draft = GeneratedQuestionDraft(
        question_type="MCQ",
        prompt_text="Find \\\\( x^{\x0crac{1}{2}} \\\\).",
        options=[
            {"key": "A", "text": "\\\\(1\\\\)"},
            {"key": "B", "text": "\\\\(2\\\\)"},
            {"key": "C", "text": "\\\\(3\\\\)"},
            {"key": "D", "text": "\\\\(4\\\\)"},
        ],
        correct_key="A",
        option_explanations={"A": "Correct", "B": "Wrong", "C": "Wrong", "D": "Wrong"},
        solution_steps=["Use \text{the definition}."],
        key_insight="Apply \x0crac{1}{2}.",
        difficulty_band="easy",
    )
    normalize_draft_math(draft)
    assert draft.prompt_text == r"Find \( x^{\frac{1}{2}} \)."
    assert draft.options[0].text == r"\(1\)"
    assert draft.solution_steps == [r"Use \text{the definition}."]
    assert draft.key_insight == r"Apply \frac{1}{2}."
    assert math_format_issues(draft) == []


def test_mcq_structure_issues_rejects_wrong_count_and_missing_correct_key():
    draft = GeneratedQuestionDraft(
        question_type="MCQ",
        prompt_text=r"What is \(2+2\)?",
        options=[{"key": "A", "text": "3"}, {"key": "B", "text": "4"}],
        correct_key="D",
        option_explanations={"A": "Wrong", "B": "Correct"},
        solution_steps=["Add."],
        key_insight="Addition.",
        difficulty_band="easy",
    )
    assert mcq_structure_issues(draft) == [
        "MCQ must have exactly four options",
        "correct_key must identify one of the four options",
    ]


def test_critic_cannot_approve_invalid_math_format(monkeypatch):
    intake = GenerationIntake(style="AIME", question_count=1, question_types=["MCQ"], title="t")
    draft = GeneratedQuestionDraft(
        question_type="MCQ", prompt_text=r"What is \(2+2\)?",
        options=[{"key": "A", "text": "3"}, {"key": "B", "text": "4"}],
        correct_key="B", solution_steps=["Add 2 and 2."], key_insight="Basic arithmetic.",
        difficulty_band="easy",
    )
    verdict = CriticVerdict(
        verdict="APPROVE", correctness_ok=True, difficulty_match_ok=True, clarity_ok=True,
        math_format_ok=False, feedback="",
    )
    monkeypatch.setattr(
        exam_service, "get_settings", lambda: SimpleNamespace(max_critic_revision_rounds=0),
    )
    async def fake_draft(**_kwargs):
        return draft

    async def fake_review(*_args, **_kwargs):
        return verdict

    monkeypatch.setattr(exam_service, "draft_question_async", fake_draft)
    monkeypatch.setattr(exam_service, "review_question_async", fake_review)

    final_draft, revision_log, needs_human_review = asyncio.run(exam_service._generate_one_question(
        [], intake=intake, question_type="MCQ", difficulty_signal="", candidate_sources=[],
        progress=MagicMock(), question_ordinal=1,
    ))

    assert final_draft is draft
    assert revision_log[0]["verdict"] == "REVISE"
    assert "KaTeX" in revision_log[0]["feedback"]
    assert needs_human_review is True


def test_hard_question_cannot_pass_without_multiple_reasoning_tags(monkeypatch):
    intake = GenerationIntake(
        style="AIME", question_count=1, question_types=["MCQ"], title="t",
        difficulty_band="hard",
    )
    draft = GeneratedQuestionDraft(
        question_type="MCQ", prompt_text=r"What is \(2+2\)?",
        options=[
            {"key": "A", "text": "3"}, {"key": "B", "text": "4"},
            {"key": "C", "text": "5"}, {"key": "D", "text": "6"},
        ],
        correct_key="B",
        option_explanations={"A": "a", "B": "b", "C": "c", "D": "d"},
        solution_steps=["Add 2 and 2."], key_insight="Basic arithmetic.",
        difficulty_band="hard", concept_slugs=["arithmetic"],
    )
    verdict = CriticVerdict(
        verdict="APPROVE", correctness_ok=True, difficulty_match_ok=True,
        synthesis_ok=True, clarity_ok=True, math_format_ok=True, feedback="",
    )
    monkeypatch.setattr(
        exam_service, "get_settings", lambda: SimpleNamespace(max_critic_revision_rounds=0),
    )

    async def fake_draft(**_kwargs):
        return draft

    async def fake_review(*_args, **_kwargs):
        return verdict

    monkeypatch.setattr(exam_service, "draft_question_async", fake_draft)
    monkeypatch.setattr(exam_service, "review_question_async", fake_review)

    _, revision_log, needs_human_review = asyncio.run(exam_service._generate_one_question(
        [], intake=intake, question_type="MCQ", difficulty_signal="", candidate_sources=[],
        progress=MagicMock(), question_ordinal=1,
    ))

    assert revision_log[0]["verdict"] == "REVISE"
    assert "at least two concepts/techniques" in revision_log[0]["feedback"]
    assert needs_human_review is True


def test_diagnosis_report_empty_lists_are_valid():
    report = DiagnosisReport(
        time_management_verdict="Well-paced.", pacing_notes=[], reasoning_guidance=[],
        improvement_areas=[],
    )
    assert report.pacing_notes == []


# --------------------------------------------------------------------------- topic resolution

def _mcp_result(problems: list[dict]) -> dict:
    import json

    return {"status": "success", "content": [{"text": json.dumps(problems)}]}


def test_resolve_topic_concept_slug_prefers_explicit_slugs():
    intake = GenerationIntake(
        style="AIME", question_count=1, question_types=["MCQ"], title="t",
        target_concept_slugs=["count"],
    )
    # No MCP call should even be attempted when a slug was already given explicitly.
    client = MagicMock()
    assert _resolve_topic_concept_slug(client, intake) == "count"
    client.call_tool_sync.assert_not_called()


def test_resolve_topic_concept_slug_picks_most_common_tests_slug():
    intake = GenerationIntake(
        style="AIME", question_count=1, question_types=["MCQ"], title="t", topic_hint="combinatorics",
    )
    client = MagicMock()
    client.call_tool_sync.return_value = _mcp_result([
        {"graph_evidence": [
            {"kind": "TESTS", "slug": "count"}, {"kind": "USES_TECHNIQUE", "slug": "count-bijection"},
        ]},
        {"graph_evidence": [{"kind": "TESTS", "slug": "count"}]},
        {"graph_evidence": [{"kind": "TESTS", "slug": "alg"}]},
    ])
    assert _resolve_topic_concept_slug(client, intake) == "count"


def test_resolve_topic_concept_slug_returns_none_on_no_evidence():
    intake = GenerationIntake(
        style="AIME", question_count=1, question_types=["MCQ"], title="t", topic_hint="something obscure",
    )
    client = MagicMock()
    client.call_tool_sync.return_value = _mcp_result([{"graph_evidence": []}])
    assert _resolve_topic_concept_slug(client, intake) is None


def test_resolve_topic_concept_slug_returns_none_with_no_topic_hint():
    intake = GenerationIntake(style="AIME", question_count=1, question_types=["MCQ"], title="t")
    client = MagicMock()
    assert _resolve_topic_concept_slug(client, intake) is None
    client.call_tool_sync.assert_not_called()


# --------------------------------------------------------------------------- candidate pool rotation / complexity signals

def test_candidate_window_rotates_so_different_questions_see_different_sources():
    pool = [{"c": i} for i in range(10)]
    window_0 = _candidate_window(pool, question_index=0, size=4)
    window_1 = _candidate_window(pool, question_index=1, size=4)
    assert window_0 == [{"c": 0}, {"c": 1}, {"c": 2}, {"c": 3}]
    assert window_1 == [{"c": 4}, {"c": 5}, {"c": 6}, {"c": 7}]
    assert window_0 != window_1


def test_candidate_window_wraps_around_when_offset_exceeds_pool_size():
    pool = [{"c": i} for i in range(5)]
    window = _candidate_window(pool, question_index=3, size=4)  # offset 12 % 5 = 2
    assert len(window) == 4
    assert window[0] == {"c": 2}


def test_candidate_window_empty_pool_returns_empty():
    assert _candidate_window([], question_index=0) == []


def test_solution_text_from_steps_numbers_each_step():
    text = _solution_text_from_steps(["Add the numbers.", "State the result."])
    assert text == "1. Add the numbers.\n2. State the result."


def test_valid_canonical_codes_extracts_set():
    sources = [{"canonical_code": "AMC10_2003A_Q24"}, {"canonical_code": "AIME_2023_I_Q11"}]
    assert _valid_canonical_codes(sources) == {"AMC10_2003A_Q24", "AIME_2023_I_Q11"}


def test_ensure_inspiration_source_falls_back_to_retrieved_candidate():
    draft = GeneratedQuestionDraft(
        question_type="MCQ", prompt_text="2+2=?",
        options=[{"key": "A", "text": "3"}, {"key": "B", "text": "4"}],
        correct_key="B", solution_steps=["Add 2 and 2."], key_insight="Basic arithmetic.",
        difficulty_band="easy",
    )

    _ensure_inspiration_source(
        draft,
        [{"canonical_code": "AMC10_2003A_Q24", "statement_text": "A counting problem"}],
    )

    assert [source.canonical_code for source in draft.inspiration_sources] == ["AMC10_2003A_Q24"]
    assert "newly composed" in draft.inspiration_sources[0].note


def test_ensure_inspiration_source_keeps_empty_pool_empty():
    draft = GeneratedQuestionDraft(
        question_type="MCQ", prompt_text="2+2=?",
        options=[{"key": "A", "text": "3"}, {"key": "B", "text": "4"}],
        correct_key="B", solution_steps=["Add 2 and 2."], key_insight="Basic arithmetic.",
        difficulty_band="easy",
    )

    _ensure_inspiration_source(draft, [])

    assert draft.inspiration_sources == []


def test_inspiration_source_requires_canonical_code_and_note():
    source = InspirationSource(canonical_code="AMC10_2003A_Q24", note="changed the group sizes")
    assert source.canonical_code == "AMC10_2003A_Q24"


def test_diversity_verdict_defaults_flagged_empty():
    verdict = DiversityVerdict(verdict="APPROVE")
    assert verdict.flagged == []


def test_flagged_question_carries_ordinal_issue_and_feedback():
    flag = FlaggedQuestion(ordinal=2, issue="near-duplicate of question 1", feedback="pick a different setup")
    assert flag.ordinal == 2


def test_generated_question_draft_defaults_inspiration_sources_empty():
    draft = GeneratedQuestionDraft(
        question_type="MCQ", prompt_text="2+2=?",
        options=[{"key": "A", "text": "3"}, {"key": "B", "text": "4"}],
        correct_key="B", solution_steps=["Add 2 and 2."], key_insight="Basic arithmetic.",
        difficulty_band="easy",
    )
    assert draft.inspiration_sources == []


# --------------------------------------------------------------------------- question pool + asyncio orchestration

def _pool_question(prompt: str, qtype: str = "MCQ") -> dict:
    return {
        "question_type": qtype, "prompt_text": prompt, "prompt_latex": None,
        "options": [
            {"key": "A", "text": "1"}, {"key": "B", "text": "2"},
            {"key": "C", "text": "3"}, {"key": "D", "text": "4"},
        ] if qtype == "MCQ" else None,
        "correct_answer": {"correct_key": "B"} if qtype == "MCQ" else {"expected_answer": "2", "grading_rubric": "r"},
        "solution_text": "1. step", "solution_steps": ["step"], "key_insight": "k",
        "difficulty_band": "hard", "concept_slugs": ["count"], "technique_slugs": ["invariant"],
        "skill_slugs": [],
        "option_explanations": {"A": "a", "B": "b", "C": "c", "D": "d"},
        "inspiration_sources": [],
    }


def _match(pid: str, prompt: str, qtype: str = "MCQ") -> dict:
    return {"pool_question_id": pid, "question_type": qtype, "question": _pool_question(prompt, qtype),
            "topic_similarity": 0.9}


def test_assign_pool_questions_respects_slot_types_and_skips_bad_rows():
    intake = GenerationIntake(style="AIME", question_count=4, question_types=["MCQ", "FREE_TEXT"], title="t")
    bad = {"pool_question_id": "bad", "question_type": "MCQ", "question": {"question_type": "MCQ"}}
    matches = [bad, _match("p1", "q1"), _match("p2", "q2"), _match("p3", "q3", "FREE_TEXT")]
    assigned = exam_service._assign_pool_questions(intake, matches)
    # slots 0,2 want MCQ, 1,3 want FREE_TEXT; only one FREE_TEXT is available
    assert {i: m["pool_question_id"] for i, (m, _) in assigned.items()} == {0: "p1", 1: "p3", 2: "p2"}


def test_payload_from_pool_match_links_pool_id_and_never_re_adds():
    payload = exam_service._payload_from_pool_match(_match("p1", "q1"))
    assert payload["pool_question_id"] == "p1"
    assert "add_to_pool" not in payload
    assert payload["revision_log"][0]["served_from_pool"] == "p1"


def _install_run_fakes(monkeypatch, *, pool_matches: list[dict], question_count: int, delay: float = 0.0):
    intake = GenerationIntake(
        style="AIME", question_count=question_count, question_types=["MCQ"], title="t",
        topic_hint="combinatorics", difficulty_band="hard",
    )
    calls = {"draft": 0, "finalize": None, "failed": None, "events": []}
    client = MagicMock()
    client.list_tools_sync.return_value = []

    @asynccontextmanager
    async def fake_session():
        yield client

    async def fake_intake(_nl):
        return intake

    async def fake_draft(**_kwargs):
        calls["draft"] += 1
        await asyncio.sleep(delay)
        n = calls["draft"]
        return GeneratedQuestionDraft(
            question_type="MCQ", prompt_text=f"fresh {n}",
            options=[
                {"key": "A", "text": "1"}, {"key": "B", "text": "2"},
                {"key": "C", "text": "3"}, {"key": "D", "text": "4"},
            ],
            correct_key="B",
            option_explanations={"A": "a", "B": "b", "C": "c", "D": "d"},
            solution_steps=["s"], key_insight="k", difficulty_band="hard",
            synthesis_rationale="Counting constraints and an invariant must be used together.",
            concept_slugs=["count"], technique_slugs=["invariant"],
        )

    async def fake_review(*_a, **_k):
        await asyncio.sleep(delay)
        return CriticVerdict(verdict="APPROVE", correctness_ok=True, difficulty_match_ok=True,
                             clarity_ok=True, math_format_ok=True, feedback="")

    async def fake_paper(_drafts):
        return DiversityVerdict(verdict="APPROVE")

    def fake_finalize(_quiz_id, payload):
        calls["finalize"] = payload
        return {"quiz_id": "q"}

    monkeypatch.setattr(exam_service, "_competitions_session", fake_session)
    monkeypatch.setattr(exam_service, "parse_intake_async", fake_intake)
    monkeypatch.setattr(exam_service, "draft_question_async", fake_draft)
    monkeypatch.setattr(exam_service, "review_question_async", fake_review)
    monkeypatch.setattr(exam_service, "review_paper_async", fake_paper)
    monkeypatch.setattr(exam_service, "_search_problems",
                        lambda *_a: [{"canonical_code": "C1", "graph_evidence": [{"kind": "TESTS", "slug": "count"}]}])
    monkeypatch.setattr(exam_service, "_resolve_difficulty_signal", lambda _slug: "signal")
    monkeypatch.setattr(exam_service, "get_settings",
                        lambda: SimpleNamespace(max_critic_revision_rounds=0, generator_model_id="m"))
    monkeypatch.setattr(exam_service.rest_client, "match_pool_questions", lambda **_k: pool_matches)
    monkeypatch.setattr(exam_service.rest_client, "finalize_paper", fake_finalize)
    monkeypatch.setattr(
        exam_service.rest_client, "fail_paper",
        lambda quiz_id, student_id, message: calls.update(
            failed=(quiz_id, student_id, message)
        ),
    )
    monkeypatch.setattr(exam_service.rest_client, "post_generation_event",
                        lambda _qid, **event: calls["events"].append(event["ordinal"]))
    return calls


def test_run_generation_serves_from_pool_first_and_adds_fresh_questions(monkeypatch):
    calls = _install_run_fakes(monkeypatch, pool_matches=[_match("p1", "pooled 1")], question_count=3)
    asyncio.run(exam_service.run_generation_async("quiz", "student", "nl"))

    assert calls["draft"] == 2  # only the slots the pool couldn't fill
    payload = calls["finalize"]
    assert payload["pool_topic"] == "combinatorics"
    assert payload["pool_concept_slugs"] == ["count"]
    questions = payload["questions"]
    assert questions[0]["pool_question_id"] == "p1"
    assert [q.get("add_to_pool") for q in questions[1:]] == [True, True]


def test_run_generation_fails_paper_instead_of_persisting_rejected_question(monkeypatch):
    calls = _install_run_fakes(monkeypatch, pool_matches=[], question_count=1)

    async def reject_review(*_args, **_kwargs):
        return CriticVerdict(
            verdict="REVISE", correctness_ok=False, difficulty_match_ok=False,
            synthesis_ok=False, clarity_ok=True, math_format_ok=True,
            feedback="The answer is mathematically incorrect.",
        )

    monkeypatch.setattr(exam_service, "review_question_async", reject_review)

    import pytest
    with pytest.raises(exam_service.GenerationQualityError):
        asyncio.run(exam_service.run_generation_async("quiz", "student", "nl"))

    assert calls["finalize"] is None
    assert calls["failed"][:2] == ("quiz", "student")
    assert "did not approve" in calls["failed"][2]
    assert calls["events"] == sorted(calls["events"])  # progress delivered in ordinal order


def test_run_generation_drafts_slots_concurrently(monkeypatch):
    calls = _install_run_fakes(monkeypatch, pool_matches=[], question_count=6, delay=0.2)
    started = time.perf_counter()
    asyncio.run(exam_service.run_generation_async("quiz", "student", "nl"))
    elapsed = time.perf_counter() - started
    assert calls["draft"] == 6
    assert elapsed < 1.5  # sequential would be 6 * (0.2 + 0.2) = 2.4s


def test_run_generation_survives_pool_lookup_failure(monkeypatch):
    calls = _install_run_fakes(monkeypatch, pool_matches=[], question_count=2)

    def boom(**_k):
        raise RuntimeError("pool table missing")

    monkeypatch.setattr(exam_service.rest_client, "match_pool_questions", boom)
    asyncio.run(exam_service.run_generation_async("quiz", "student", "nl"))
    assert calls["draft"] == 2
