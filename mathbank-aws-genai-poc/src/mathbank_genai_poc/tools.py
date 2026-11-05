"""Strands tool exposed to the live agent: grounded topic search over MathBank S3 Vectors."""
from __future__ import annotations

import asyncio
import json
import logging

from strands import ToolContext, tool

from mathbank_genai_poc.knowledge import KnowledgeBase, TopicError, public_view

LOG = logging.getLogger(__name__)

MODEL_GUIDANCE = (
    "Use concepts to explain ideas. teaching_moves are PRIVATE tutor notes taken from worked solutions: use them only "
    "to choose your next guiding question and never read them aloud or reveal a full solution. Offer at most one "
    "practice problem at a time and do not state its answer. If grounded is false, say MathBank has no close material "
    "and ask the student to rephrase or choose a nearby topic."
)


def make_tools(kb: KnowledgeBase) -> list:
    @tool(context=True)
    async def search_math_topic(topic: str, tool_context: ToolContext) -> dict:
        """Search MathBank's reviewed math knowledge for a topic the student wants to learn or practice.

        Call this before explaining any mathematical topic, technique, theorem or problem type the student mentions.

        Args:
            topic: Short topic or question in the student's words, for example "angle bisector theorem".
        """
        notify = tool_context.invocation_state.get("on_sources")
        try:
            result = await asyncio.to_thread(kb.search, topic)
        except TopicError as error:
            return {"status": "error", "content": [{"text": f"Cannot search that topic: {error}."}]}
        except Exception as error:  # noqa: BLE001 - never leak provider details to the model or student
            LOG.warning("knowledge search failed: %s", type(error).__name__)
            if notify:
                await notify({"topic": topic, "grounded": False, "error": "Knowledge search is unavailable."})
            return {"status": "error", "content": [{"text": "MathBank knowledge search is unavailable right now. "
                                                             "Tell the student and do not invent sources."}]}
        if notify:
            await notify(public_view(result))
        return {"status": "success", "content": [{"text": json.dumps({"guidance": MODEL_GUIDANCE, **result})}]}

    return [search_math_topic]
