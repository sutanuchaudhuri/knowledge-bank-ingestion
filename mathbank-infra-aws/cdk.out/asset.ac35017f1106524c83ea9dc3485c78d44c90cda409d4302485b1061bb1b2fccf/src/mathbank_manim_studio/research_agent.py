"""The "research agent" (requirements/60 §1): topic + optional context -> a validated
SceneSpec JSON plus an explanation. Long-running and cloud-ready in the sense that it is
a plain async function driven entirely by Postgres job state (see jobs.py/worker.py) —
no in-memory state that would prevent running this on a different machine than the one
that enqueued the job.

Groundedness: the model is given mathbank-mcp-competitions's real corpus tools
(requirements/49) and is instructed to call them before answering, so a generated scene
about, say, "Vieta's formulas" is grounded in a real concept/problem the tools confirm
exists, not invented from the model's own unchecked prior.
"""
from __future__ import annotations

import json

from fastmcp import Client
from openai import AsyncOpenAI

from mathbank_manim_studio.config import get_settings
from mathbank_manim_studio.mcp_corpus_client import competitions_transport, mcp_tool_to_openai_tool
from mathbank_manim_studio.scene_spec_validation import (
    SUPPORTED_ACTIONS,
    SUPPORTED_OBJECT_TYPES,
    validate_scene_spec_dict,
)

_SYSTEM_PROMPT = f"""You are a math-explainer scene writer for MathBank's Manim Video Studio.

Given a topic (and optional context such as a concept_code or problem canonical_code),
first use the provided corpus tools to ground yourself in real MathBank content about
the topic — never invent a competition, problem, or concept the tools don't confirm.

Then produce ONE final JSON object (no other text) shaped exactly like:
{{"scene_spec": {{"scene_key": "...", "scene_version": 1, "objects": [...], "timeline": [...]}},
  "explanation": "2-4 sentences of narration explaining the idea"}}

SceneSpec rules (strict — only these are supported by the renderer):
- objects[].type must be one of: {sorted(SUPPORTED_OBJECT_TYPES)}
- timeline[].action must be one of: {sorted(SUPPORTED_ACTIONS)}
- every object needs a unique "id" and a "type" — EXACT required fields per type:
  - TITLE_TEXT, TEXT, STATE_NODE: "label" (plain display text — NEVER LaTeX/backslash
    commands; if you need math notation, use an EQUATION object instead)
  - EQUATION: "latex" (a MathTex-compatible LaTeX string, e.g. "x_1 + x_2 = -b")
  - MATRIX: "rows" (a list of rows, each a list of cell strings)
  - FUNCTION_GRAPH: "expr" (a single-variable expression in x using only +-*/** and
    sin/cos/tan/sqrt/exp/log/abs — nothing else)
  - GRAPH_POINT: "on" (a FUNCTION_GRAPH object id), "x", "y"
  - do not use any other field name ("text" is NOT valid — it is always "label")
- STATE_NODE/TEXT/EQUATION/FUNCTION_GRAPH objects also take optional "x"/"y" canvas
  coordinates (roughly -6..6 horizontally, -3..3 vertically)
- timeline entries need "at_ms" (milliseconds) and "action":
  - SHOW/HIDE/WRITE/HIGHLIGHT need "targets": [object ids]
  - DRAW_TRANSITION/EQUATION_MORPH need "from"/"to" object ids (DRAW_TRANSITION may also
    take a short "label" string for the arrow)
- every object must be shown with SHOW or WRITE at or before any later action that
  references it (DRAW_TRANSITION/HIGHLIGHT/EQUATION_MORPH/HIDE)
- keep it to 4-10 objects and 6-14 timeline entries — a short, focused explainer, not an
  exhaustive lecture
"""


async def run_research_agent(topic: str, context: dict | None = None,
                              *, model: str | None = None, max_turns: int = 6,
                              max_repair_attempts: int = 2) -> tuple[dict, str]:
    """Returns (scene_spec_dict, explanation). Raises ValueError if the model never
    produces a SceneSpec that passes validate_scene_spec_dict within the retry budget."""
    settings = get_settings()
    model = model or settings.openai_model
    context = context or {}

    async with Client(competitions_transport()) as mcp_client:
        mcp_tools = await mcp_client.list_tools()
        openai_tools = [mcp_tool_to_openai_tool(t) for t in mcp_tools
                         if t.name not in {"load_competition_problems", "open_competition_explorer"}]

        openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        user_prompt = f"Topic: {topic}"
        if context:
            user_prompt += f"\nContext: {json.dumps(context)}"
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        last_errors: list[str] = []
        for attempt in range(max_repair_attempts + 1):
            final_json: dict | None = None
            for _ in range(max_turns):
                response = await openai_client.chat.completions.create(
                    model=model, messages=messages, tools=openai_tools,
                )
                choice = response.choices[0]
                messages.append(choice.message.model_dump(exclude_none=True))

                if choice.message.tool_calls:
                    for tool_call in choice.message.tool_calls:
                        args = json.loads(tool_call.function.arguments or "{}")
                        result = await mcp_client.call_tool(tool_call.function.name, args)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result.data)[:4000],
                        })
                    continue

                content = choice.message.content or "{}"
                try:
                    final_json = json.loads(_strip_code_fence(content))
                except json.JSONDecodeError:
                    final_json = None
                break

            if final_json and "scene_spec" in final_json:
                errors = validate_scene_spec_dict(final_json["scene_spec"])
                if not errors:
                    return final_json["scene_spec"], final_json.get("explanation", "")
                last_errors = errors
                messages.append({
                    "role": "user",
                    "content": (
                        "That SceneSpec failed validation with these errors: "
                        f"{errors}. Return a corrected final JSON object only."
                    ),
                })
            else:
                last_errors = ["model did not return a scene_spec JSON object"]

        raise ValueError(f"research agent failed to produce a valid SceneSpec: {last_errors}")


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()
