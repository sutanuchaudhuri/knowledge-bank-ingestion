"""Structured-output schemas the generator/critic/diagnosis agents fill in via
`agent(prompt, structured_output_model=...)` (requirements/64 §4, §7) — Strands'
current, non-deprecated structured-output mechanism (confirmed live this session; the
older `Agent.structured_output()` method is deprecated in favor of this).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class GenerationIntake(BaseModel):
    """What a natural-language request like "a 10-question AIME-style paper on
    combinatorics, hard, 90 minutes" is parsed into (requirements/64 §3's "Intake"
    step) — the same style/question-type vocabulary requirements/53 already defines,
    not a new one."""
    style: str = Field(description="One of AIME, HMMT, PROOF_BASED, TOPIC_BASED, SKILL_BASED, MIXED")
    question_count: int = Field(ge=1, le=20)
    question_types: list[str] = Field(description="Subset of MCQ, FREE_TEXT, PROOF")
    target_concept_slugs: list[str] = Field(default_factory=list)
    target_skill_slugs: list[str] = Field(default_factory=list)
    topic_hint: str = Field(
        default="", description="Free-text topic the generator should resolve via list_concepts/"
                                 "list_techniques if no explicit slug was given"
    )
    difficulty_band: str | None = Field(default=None, description="easy, medium, hard, or very_hard")
    time_limit_seconds: int | None = Field(default=None, description="null if the request gave no time limit")
    title: str = Field(description="A short, human-readable paper title")


class QuestionOption(BaseModel):
    key: str
    text: str


class GeneratedQuestionDraft(BaseModel):
    """One drafted question, before critic review (requirements/64 §4)."""
    question_type: str = Field(description="MCQ, FREE_TEXT, or PROOF")
    prompt_text: str = Field(
        description="The full question statement, with any math written inline using "
                     "\\( ... \\) (or \\[ ... \\] for standalone display equations)."
    )
    prompt_latex: str | None = Field(
        default=None,
        description="Leave this null. It exists only for problems that are PURELY a "
                     "rendered diagram/equation with no surrounding prose — never repeat "
                     "or restate prompt_text here.",
    )
    options: list[QuestionOption] | None = Field(default=None, description="MCQ only, exactly 4 options")
    correct_key: str | None = Field(default=None, description="MCQ only — the correct option's key")
    option_explanations: dict[str, str] = Field(
        default_factory=dict,
        description="MCQ only — one entry per option key, explaining why it IS correct (for the "
                     "correct key) or specifically why it is WRONG (for every incorrect key), "
                     "e.g. identifying the exact miscalculation/misconception that choice represents",
    )
    expected_answer: str | None = Field(default=None, description="FREE_TEXT/PROOF only")
    grading_rubric: str | None = Field(default=None, description="FREE_TEXT/PROOF only")
    solution_text: str
    key_insight: str
    difficulty_band: str = Field(description="easy, medium, hard, or very_hard — the generator's own estimate")
    concept_slugs: list[str] = Field(default_factory=list)
    technique_slugs: list[str] = Field(default_factory=list)


class CriticVerdict(BaseModel):
    """The critic agent's review of one drafted question (requirements/64 §4)."""
    verdict: str = Field(description="APPROVE or REVISE")
    correctness_ok: bool
    difficulty_match_ok: bool = Field(description="False if the draft reads easier/harder than requested")
    clarity_ok: bool
    distractor_quality_ok: bool = Field(
        default=True, description="MCQ only — true/not-applicable for FREE_TEXT/PROOF"
    )
    feedback: str = Field(description="Specific, actionable — what exactly to fix if verdict is REVISE")


class PacingNote(BaseModel):
    question_ordinal: int
    time_spent_seconds: int | None
    difficulty_band: str | None
    note: str


class ReasoningGuidanceNote(BaseModel):
    question_ordinal: int
    guidance: str = Field(description="The kind of thinking that reaches the correct approach, not the solution")


class ImprovementArea(BaseModel):
    concept_or_technique: str
    current_mastery_tier: str
    evidence: str


class DiagnosisReport(BaseModel):
    """The diagnosis agent's holistic, post-exam report (requirements/64 §7)."""
    time_management_verdict: str
    pacing_notes: list[PacingNote]
    reasoning_guidance: list[ReasoningGuidanceNote]
    improvement_areas: list[ImprovementArea]
