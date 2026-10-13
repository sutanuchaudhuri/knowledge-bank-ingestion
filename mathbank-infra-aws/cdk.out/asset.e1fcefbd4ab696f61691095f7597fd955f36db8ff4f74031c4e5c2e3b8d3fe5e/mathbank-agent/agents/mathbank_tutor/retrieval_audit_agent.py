"""Bounded audit specialist; stored server evidence, not model opinion, is authoritative."""

import asyncio
import json

from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.agent_tool import AgentTool


class RetrievalAuditAgentTool(AgentTool):
    async def run_async(self, *, args, tool_context):
        snapshot = tool_context.state.get("temp:retrieval_audit_evidence")
        if not snapshot or args.get("request") != json.dumps(snapshot):
            return {"error": "AUDIT_EVIDENCE_REQUIRED", "message": "Audit the exact server-recorded pending feedback evidence."}
        if tool_context.state.get("temp:audit_agent_called"):
            return {"error": "AUDIT_LIMIT", "message": "One retrieval audit delegation per invocation."}
        tool_context.state["temp:audit_agent_called"] = True
        safe = {key: snapshot.get(key) for key in (
            "version", "published_step_count", "supporting_step_ids",
            "structural_validation", "suggested_error_kind", "review_status",
        )}
        try:
            await asyncio.wait_for(
                super().run_async(args={"request": json.dumps(safe)}, tool_context=tool_context),
                timeout=30,
            )
        except TimeoutError:
            return {"error": "AUDIT_TIMEOUT", "message": "Audit specialist timed out. The pending report remains saved; no correction was applied."}
        return {"audit_version": snapshot["version"], "review_status": "PENDING",
                "supporting_steps": len(snapshot.get("supporting_step_ids", [])),
                "suggested_error_kind": snapshot["suggested_error_kind"],
                "message": "Source/solution review required. No canonical correction or training was applied."}


def retrieval_audit_tool(model):
    return RetrievalAuditAgentTool(agent=Agent(
        name="retrieval_audit_agent",
        description="Inspect server-recorded relevance feedback evidence; never mutate canonical taxonomy or train.",
        model=LiteLlm(model=model) if isinstance(model, str) else model,
        instruction="Review only the supplied evidence limits. Missing structural signatures are not proof "
                    "of irrelevance. Distinguish a possible metadata problem from retrieval mismatch and "
                    "insufficient evidence. All conclusions remain PENDING human source/solution review. "
                    "Never fabricate telemetry, disclose private reasoning, approve, publish, or train.",
    ))
