from __future__ import annotations

import re

from mathbank_exam_agent.schemas import GeneratedQuestionDraft

_CONTROL_COMMANDS = {
    "\x08egin": r"\begin",
    "\x0crac": r"\frac",
    "\right": r"\right",
    "\text": r"\text",
}


def normalize_math_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value
    for malformed, command in _CONTROL_COMMANDS.items():
        normalized = normalized.replace(malformed, command)
    for delimiter in ("(", ")", "[", "]"):
        normalized = re.sub(rf"\\{{2,}}{re.escape(delimiter)}", rf"\\{delimiter}", normalized)
    normalized = normalized.replace(r"\n", "\n")
    return normalized


def normalize_draft_math(draft: GeneratedQuestionDraft) -> GeneratedQuestionDraft:
    draft.prompt_text = normalize_math_text(draft.prompt_text) or ""
    draft.prompt_latex = normalize_math_text(draft.prompt_latex)
    draft.expected_answer = normalize_math_text(draft.expected_answer)
    draft.grading_rubric = normalize_math_text(draft.grading_rubric)
    draft.solution_steps = [normalize_math_text(step) or "" for step in draft.solution_steps]
    draft.key_insight = normalize_math_text(draft.key_insight) or ""
    draft.option_explanations = {
        key: normalize_math_text(value) or "" for key, value in draft.option_explanations.items()
    }
    if draft.options:
        for option in draft.options:
            option.text = normalize_math_text(option.text) or ""
    return draft


def math_format_issues(draft: GeneratedQuestionDraft) -> list[str]:
    fields = [draft.prompt_text, draft.prompt_latex, draft.expected_answer, draft.grading_rubric]
    fields.extend(draft.solution_steps)
    fields.extend(draft.option_explanations.values())
    fields.extend(option.text for option in draft.options or [])
    issues: list[str] = []
    for value in fields:
        if not value:
            continue
        if any(character in value for character in ("\x08", "\x0c", "\r", "\t")):
            issues.append("contains a control character produced by an unescaped TeX command")
        if value.count(r"\(") != value.count(r"\)"):
            issues.append("has unbalanced inline-math delimiters")
        if value.count(r"\[") != value.count(r"\]"):
            issues.append("has unbalanced display-math delimiters")
    return sorted(set(issues))


def mcq_structure_issues(draft: GeneratedQuestionDraft) -> list[str]:
    if draft.question_type != "MCQ":
        return []
    options = draft.options or []
    issues: list[str] = []
    if len(options) != 4:
        issues.append("MCQ must have exactly four options")
    keys = [option.key.strip().upper() for option in options]
    if len(set(keys)) != len(keys):
        issues.append("MCQ option keys must be unique")
    if draft.correct_key is None or draft.correct_key.strip().upper() not in keys:
        issues.append("correct_key must identify one of the four options")
    if len({option.text.strip() for option in options}) != len(options):
        issues.append("MCQ option texts must be distinct")
    if set(draft.option_explanations) != set(keys):
        issues.append("option_explanations must contain exactly one entry for every option key")
    return issues
