"""Presentation tools (requirements 27/29): declarative widgets and math formatting.

Both call deterministic mathbank-rest endpoints with the signed-in learner's token (ADK temp state,
never persisted). Neither calls a model. ``propose_widget`` returns a validated, student-safe widget
spec; the agent embeds it verbatim in a fenced ```widget JSON block, which mathbank-web renders through
the whitelisted WidgetHost (never executed). ``format_math`` normalises learner-typed math into LaTeX
(deterministic mode only — the paid agentic formatter is reserved for the learner's own button).
"""
from __future__ import annotations

import json
from typing import Any

from google.adk.tools.tool_context import ToolContext

from .step_runtime_tools import _call

MAX_INTENT = 300


def propose_widget(intent: str, tool_context: ToolContext, context_json: str = "") -> dict[str, Any]:
    """Compose a visual widget (geometry diagram, formula card, step progress, table) for the learner.

    Use sparingly — only when a picture or a formatted card genuinely helps (e.g. "power of a point
    with secant PAB and tangent PT", "formula: PA·PB = PT^2", "intersecting chords"). Never put a
    hidden answer or a solution step in a widget.

    Args:
      intent: Short plain-English description of the visual.
      context_json: Optional JSON object with extra fields (e.g. {"steps": [...]} or
        {"columns": [...], "rows": [...]}). Leave empty when not needed.

    Returns:
      {"widget_type", "markdown_block"} on success: copy markdown_block into your reply exactly as
      given (it is a fenced ```widget block). On failure an {"error": ...} dict — then just explain in
      text. SIGN_IN_REQUIRED means the chat is anonymous; do not retry.
    """
    intent = (intent or "").strip()[:MAX_INTENT]
    if not intent:
        return {"error": "EMPTY_INTENT"}
    context: dict = {}
    if context_json and context_json.strip():
        try:
            parsed = json.loads(context_json)
        except ValueError:
            return {"error": "BAD_CONTEXT_JSON", "message": "context_json must be a JSON object"}
        if not isinstance(parsed, dict):
            return {"error": "BAD_CONTEXT_JSON", "message": "context_json must be a JSON object"}
        context = parsed
    out = _call(tool_context, "POST", "/v1/widgets/generate", json={"intent": intent, "context": context})
    if "error" in out:
        return out
    validation = out.get("validation") or {}
    spec = out.get("spec")
    if not spec or not validation.get("valid"):
        return {"error": "WIDGET_INVALID", "message": "; ".join(map(str, validation.get("errors") or []))[:300]}
    block = "```widget\n" + json.dumps(spec, ensure_ascii=False, separators=(",", ":")) + "\n```"
    return {"widget_type": spec.get("widget_type"), "strategy": out.get("strategy"), "markdown_block": block}


def format_math(text: str, tool_context: ToolContext) -> dict[str, Any]:
    """Normalise math typed by the learner (e.g. "PA*PB = PT^2", "sqrt(2)") into clean LaTeX.

    Use when you quote the learner's expression back to them, so it renders properly. Deterministic;
    never changes the meaning. Returns {"formatted", "changed", "warnings"} or an {"error": ...} dict.
    """
    text = (text or "").strip()
    if not text:
        return {"error": "EMPTY_TEXT"}
    out = _call(tool_context, "POST", "/v1/tutor/format-math", json={"text": text[:4000], "mode": "deterministic"})
    if "error" in out:
        return out
    formatted = out.get("formatted", text)
    return {"formatted": formatted, "changed": formatted != text, "warnings": out.get("warnings") or []}


WIDGET_TOOLS = [propose_widget, format_math]
