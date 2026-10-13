"""requirements/64: unit tests for mathbank-exam-agent's pure logic (no network/LLM
calls) — schema validation and the deterministic graph_evidence-slug-resolution helper.
A real, opt-in live end-to-end test (NL request -> generator<->critic loop -> persisted
paper -> response -> diagnosis, against the real OpenAI API, the real deployed MCP
server, and the real Neon Postgres instance) was run manually this session and is not
re-encoded here as an automated pytest case yet — each real call costs real tokens and
takes 60-120+ seconds, unlike every other live test in this repo's pytest suites (which
hit free local/Neon resources only). Tracked as a known gap in requirements/64 §11, not
silently skipped.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from mathbank_exam_agent.exam_service import _resolve_topic_concept_slug
from mathbank_exam_agent.schemas import (
    CriticVerdict,
    DiagnosisReport,
    GeneratedQuestionDraft,
    GenerationIntake,
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
        correct_key="B", solution_text="Direct addition.", key_insight="Basic arithmetic.",
        difficulty_band="easy",
    )
    assert draft.model_dump()["options"][1]["key"] == "B"


def test_critic_verdict_defaults_distractor_quality_ok_true():
    verdict = CriticVerdict(
        verdict="APPROVE", correctness_ok=True, difficulty_match_ok=True, clarity_ok=True,
        feedback="Looks good.",
    )
    assert verdict.distractor_quality_ok is True


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
