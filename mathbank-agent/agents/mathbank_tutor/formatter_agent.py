"""Meaning-preserving presentation specialist and deterministic final-output guard."""

from __future__ import annotations

import json
import re
from contextvars import ContextVar
from dataclasses import dataclass
from itertools import pairwise

from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm

from .artifact_agents import ArtifactAgentTool, _model_limit, _restore_invocation_state

CODE = re.compile(
    r"(^[ \t]*(`{3,}|~{3,})[^\n]*\n[\s\S]*?"
    r"(?:\n[ \t]*\2[ \t]*(?=\n|$)|(?![\s\S]))"
    r"|(`+)[^\n]*?\3|\[asy\][\s\S]*?(?:\[/asy\]|(?![\s\S]))|\]\([^\n]*?\))",
    re.IGNORECASE | re.MULTILINE,
)
MATH = re.compile(
    r"\\{1,2}\([\s\S]*?\\{1,2}\)|\\{1,2}\[[\s\S]*?\\{1,2}\]|\$\$[\s\S]*?\$\$|(?<!\\)\$[^$\n]+(?<!\\)\$"
)
STYLES = {"bold", "italic", "given", "goal", "insight", "warning"}


@dataclass
class _FormatInvocation:
    text: str
    result: str | None = None


_FORMAT_SOURCE: ContextVar[_FormatInvocation | None] = ContextVar(
    "formatter_source", default=None
)


class FormatterAgentTool(ArtifactAgentTool):
    async def run_async(self, *, args, tool_context):
        try:
            if not isinstance(args.get("request"), str):
                raise TypeError("Formatting request must be a JSON string.")
            request = json.loads(args.get("request", ""))
            if not isinstance(request, dict) or set(request) != {
                "text",
                "instructions",
            }:
                raise ValueError("Use a JSON request with text and instructions only.")
            if not isinstance(request["text"], str) or not isinstance(
                request["instructions"], str
            ):
                raise TypeError("Formatting text and instructions must be strings.")
            if len(request["text"]) > 64000 or len(request["instructions"]) > 4000:
                raise ValueError(
                    "Formatting text or instructions exceed the size limit."
                )
        except (ValueError, TypeError) as exc:
            return {"error": "FORMAT_INVALID", "message": str(exc)}
        invocation = _FormatInvocation(request["text"])
        source_token = _FORMAT_SOURCE.set(invocation)
        tool_context.state["temp:formatted_reply"] = None
        try:
            result = await super().run_async(args=args, tool_context=tool_context)
            if isinstance(result, str):
                tool_context.state["temp:formatted_reply"] = (
                    invocation.result
                    or "Formatting failed: no validated formatting tool result."
                )
            return result
        finally:
            _FORMAT_SOURCE.reset(source_token)


def normalize_math(text: str) -> str:
    """Canonicalize only complete prose delimiters, never program/code strings."""

    def prose(value: str) -> str:
        value = re.sub(
            r"\\{1,2}\[([\s\S]*?)\\{1,2}\]",
            lambda m: "\n\n$$\n" + m[1].strip() + "\n$$\n\n",
            value,
        )
        return re.sub(
            r"\\{1,2}\(([\s\S]*?)\\{1,2}\)", lambda m: "$" + m[1].strip() + "$", value
        )

    parts = []
    offset = 0
    for match in CODE.finditer(text):
        parts.extend((prose(text[offset : match.start()]), match[0]))
        offset = match.end()
    return "".join(parts) + prose(text[offset:])


def format_tutor_text(text: str, annotations_json: str = "[]") -> dict:
    """Format exact text without rewriting it.

    annotations_json is a list of {start,end,style} with Python character offsets
    into the ORIGINAL text. Styles: bold, italic, given, goal, insight, warning.
    Select complete inline math expressions, not a subset. No code, links,
    existing markup, multi-line spans or overlapping selections are permitted.
    Returns validated markdown_block or an explicit FORMAT_INVALID error.
    """
    try:
        if len(text) > 64000 or len(annotations_json) > 16000:
            raise ValueError("Formatting input exceeds the size limit.")
        annotations = json.loads(annotations_json)
        if not isinstance(annotations, list) or len(annotations) > 24:
            raise ValueError("Use a list with at most 24 annotations.")
        protected = [(m.start(), m.end()) for m in CODE.finditer(text)]
        # Existing links/images must keep their original destinations and labels.
        protected += [
            (m.start(), m.end()) for m in re.finditer(r"!?\[[^\n]*?\]\([^\n]*?\)", text)
        ]
        math = [(m.start(), m.end()) for m in MATH.finditer(text)]
        protected += [
            (m.start(), m.end())
            for m in re.finditer(r"(\*{1,2}|_{1,2})(?!\s)[^\n]+?(?<!\s)\1", text)
            if not any(a <= m.start() and m.end() <= b for a, b in math)
        ]
        selections = []
        for item in annotations:
            if not isinstance(item, dict) or set(item) != {"start", "end", "style"}:
                raise ValueError("Each annotation requires only start, end and style.")
            start, end, style = item["start"], item["end"], item["style"]
            if (
                type(start) is not int
                or type(end) is not int
                or not isinstance(style, str)
                or style not in STYLES
                or not 0 <= start < end <= len(text)
            ):
                raise ValueError("Invalid annotation offsets or style.")
            selected = text[start:end]
            prose = MATH.sub("", selected)
            if (
                selected != selected.strip()
                or re.search(r"[\n\r]", selected)
                or re.search(r"[\[\]`*_<>]", prose)
                or "$$" in selected
                or re.search(r"\\{1,2}\[", selected)
                or re.search(r"\$|\\{1,2}[()[\]]", prose)
            ):
                raise ValueError(
                    "Select plain inline prose or complete inline math, without existing markup."
                )
            if any(start < b and end > a for a, b in protected):
                raise ValueError("Code, links and images cannot be restyled.")
            if any(
                start < b and end > a and not (start <= a and end >= b) for a, b in math
            ):
                raise ValueError(
                    "An annotation must contain the entire math expression."
                )
            selections.append((start, end, style))
        selections.sort()
        if any(left[1] > right[0] for left, right in pairwise(selections)):
            raise ValueError("Annotations must not overlap.")
        output = text
        for start, end, style in reversed(selections):
            value = normalize_math(text[start:end])
            wrapper = (
                f"**{value}**"
                if style == "bold"
                else f"*{value}*"
                if style == "italic"
                else f"[{value}](#mb-tone-{style})"
            )
            output = output[:start] + wrapper + output[end:]
        return {
            "valid": True,
            "markdown_block": normalize_math(output),
            "annotation_count": len(selections),
        }
    except ValueError as exc:
        return {"error": "FORMAT_INVALID", "message": str(exc), "valid": False}


def guard_tutor_output(callback_context, llm_response):
    """Apply the offline guard before final model text is emitted and persisted."""
    if not llm_response.partial and llm_response.content:
        parts = llm_response.content.parts or []
        formatted = (
            callback_context.state.get("temp:formatted_reply")
            if callback_context
            else None
        )
        visible = [part for part in parts if part.text and not part.thought]
        if formatted and visible and not any(part.function_call for part in parts):
            visible[0].text = formatted
            for part in visible[1:]:
                part.text = ""
        for part in parts:
            if part.text and not part.thought:
                part.text = normalize_math(part.text)


def _bind_format_input(tool, args, tool_context):
    invocation = _FORMAT_SOURCE.get()
    if tool.name == "format_tutor_text" and (
        invocation is None or args.get("text") != invocation.text
    ):
        response = {
            "error": "FORMAT_TEXT_CHANGED",
            "valid": False,
            "message": "Formatter must use the exact original request text.",
        }
        tool_context.state["temp:formatted_reply"] = (
            f"Formatting failed: {response['message']}"
        )
        if invocation is not None:
            invocation.result = tool_context.state["temp:formatted_reply"]
        return response
    return None


def _remember_format(tool, args, tool_context, tool_response):
    if tool.name == "format_tutor_text":
        tool_context.state["temp:formatted_reply"] = (
            tool_response["markdown_block"]
            if tool_response.get("valid")
            else f"Formatting failed: {tool_response['message']}"
        )
        invocation = _FORMAT_SOURCE.get()
        if invocation is not None:
            invocation.result = tool_context.state["temp:formatted_reply"]


def _guard_formatter_output(callback_context, llm_response):
    content = llm_response.content
    validated = callback_context.state.get("temp:formatted_reply")
    if (
        not llm_response.partial
        and content
        and not any(p.function_call for p in content.parts or [])
    ):
        visible = [p for p in content.parts or [] if p.text and not p.thought]
        if visible:
            visible[0].text = (
                validated or "Formatting failed: no validated formatting tool result."
            )
            for part in visible[1:]:
                part.text = ""


def build_formatter_agent(model):
    return Agent(
        name="formatter_agent",
        model=LiteLlm(model=model) if isinstance(model, str) else model,
        description='Format learner-safe text without rewriting mathematics. Request must be JSON {"text":"exact original", "instructions":"desired styles"}.',
        instruction=(
            "You are the MathBank presentation formatter, not a solver or proof reviewer. "
            "Preserve supplied text, mistakes, mathematics, source links and diagram blocks exactly. "
            "Never add/remove facts or hidden solutions. Never request or output credentials. "
            "The request is JSON {text,instructions}. Use text EXACTLY as supplied; the server "
            "rejects any change before formatting. Follow instructions for presentation only. "
            "Call format_tutor_text with the original text and exact character-offset annotations. "
            "Use at most 24 sparse selections: bold for key terms, italic for qualifications; "
            "given (blue), goal (indigo), insight (green), warning (amber). Color is semantic, "
            "not proof of correctness. Honor requested styles; never arbitrary HTML/CSS/color codes. "
            "Select whole inline math, never part of an equation; do not select existing markup, "
            "code, images, source links or entire problem statements. Empty annotations normalizes math only. "
            "Return only the tool's markdown_block verbatim after valid=true; on failure report "
            "the explicit error, never pretend the formatting succeeded."
        ),
        tools=[format_tutor_text],
        before_agent_callback=_restore_invocation_state,
        before_model_callback=_model_limit,
        before_tool_callback=_bind_format_input,
        after_tool_callback=_remember_format,
        after_model_callback=_guard_formatter_output,
    )


def formatter_agent_tool(model):
    return FormatterAgentTool(agent=build_formatter_agent(model))
