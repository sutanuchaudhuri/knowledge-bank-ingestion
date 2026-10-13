"""Artifact specialists composed through ADK AgentTool, not remote/public A2A."""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from typing import Any

from google.adk import Agent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.tool_context import ToolContext

from .tools.artifact_tools import (
    draw_geometry_diagram,
    preview_artifact,
    request_artifact,
    search_artifacts,
    validate_artifact_plan,
)
from .tools.step_runtime_tools import _token

_DELEGATED_STATE: ContextVar[dict | None] = ContextVar(
    "artifact_delegated_state", default=None
)


def _restore_invocation_state(callback_context):
    # AgentTool creates a new Runner; session creation does not retain temp: state.
    state = _DELEGATED_STATE.get()
    if state is None:
        raise RuntimeError(
            "Artifact specialists must be invoked through authenticated tutor delegation."
        )
    callback_context.state.update(state)


class ArtifactAgentTool(AgentTool):
    """Authenticated, bounded delegation using ADK's isolated child sessions."""

    async def run_async(
        self, *, args: dict[str, Any], tool_context: ToolContext
    ) -> Any:
        if not _token(tool_context):
            return {
                "error": "SIGN_IN_REQUIRED",
                "message": "Sign in to create instructional artifacts.",
            }
        if any(len(str(value)) > 128000 for value in args.values()):
            return {
                "error": "ARTIFACT_REQUEST_TOO_LARGE",
                "message": "Use a smaller artifact request.",
            }
        count = tool_context.state.get("temp:artifact_delegations", 0)
        if count >= 16:
            return {
                "error": "ARTIFACT_DELEGATION_LIMIT",
                "message": "Artifact delegation limit reached.",
            }
        tool_context.state["temp:artifact_delegations"] = count + 1
        context_token = _DELEGATED_STATE.set(
            {
                key: tool_context.state.get(key)
                for key in (
                    "temp:student_token",
                    "temp:artifact_delegations",
                    "temp:artifact_model_calls",
                )
                if tool_context.state.get(key) is not None
            }
        )
        try:
            return await asyncio.wait_for(
                super().run_async(args=args, tool_context=tool_context),
                timeout=120,
            )
        except TimeoutError:
            return {
                "error": "ARTIFACT_DELEGATION_TIMEOUT",
                "message": "Artifact specialist timed out. No publication was performed.",
            }
        finally:
            _DELEGATED_STATE.reset(context_token)


def _model_limit(callback_context, llm_request):
    count = callback_context.state.get("temp:artifact_model_calls", 0)
    if count >= 24:
        raise RuntimeError(
            "Artifact specialist model-call limit reached; no further inference allowed."
        )
    callback_context.state["temp:artifact_model_calls"] = count + 1


COMMON = """\
You are an instructional artifact specialist, called as a tool by the MathBank tutor.
Use only supplied learner-safe problem/context. Never invent a corpus source or reveal a
hidden solution. Preserve mathematical mistakes when quoting a learner. You do not approve
student work, publish/index artifacts, execute code, query databases, or access storage keys.
Authentication is supplied by the runtime; NEVER request/include tokens in your request or output.
Return a complete structured plan or the exact markdown_block returned by a rendering tool.
A failed tool is a failure, not a created artifact. Explain SIGN_IN_REQUIRED/unavailable errors.
Do not emit executable HTML or raw SVG. Generated illustrations are not publisher source figures.
An illustrative sketch does not prove hypotheses or the desired conclusion.

Plan contract: flat JSON {subject,topic,title,summary,width:800,height:600,elements,
overlays:[],frames:[]}. Subject GEOMETRY/ALGEBRA/COMBINATORICS/NUMBER_THEORY.
Element kinds: POINT {id,x,y,label,contact:false}; SEGMENT {id,start,end,auxiliary}; CIRCLE
{id,cx,cy,radius}; ANGLE {id,vertex,start_degrees,end_degrees,radius,label};
NODE {id,x,y,label,prime}; EDGE {id,start,end}; CELL {id,row,column,label}; EQUATION
{id,latex,reason,linked_step_id,terms:[{id,latex}]}. Every element also needs kind.
Coordinates need canvas margins, distinct stable IDs and readable label spacing.
Optional overlays [{id,caption,linked_step_id,explanation_text,concept_tag,hint_tag,
actions:[{action,targets,label,latex,region}]}], frames [{overlay_id,duration_ms,transition}].
Omit unused optional fields. All targets must exist. One pedagogical purpose per frame.
Do not fabricate linked step IDs; omit them if not supplied.
Number theory adds number_theory_mode MODULAR/FACTOR_TREE/EUCLIDEAN/DIVISIBILITY;
MODULAR requires modulus. Do not submit geometry-only incircle_triangles to generic validation.
"""

RULES = {
    "latex_artifact_agent": (
        "GENERATE_ALGEBRA_LATEX",
        (
            "Produce theorem/equation/derivation cards as EQUATION elements, never bare images. "
            "Use clean KaTeX-compatible LaTeX, stable aligned equivalent lines, reasons and supplied "
            "step metadata. Terms must concatenate exactly to their equation. Preserve notation."
        ),
    ),
    "svg_artifact_agent": (
        "GENERATE_STRUCTURED_SVG",
        (
            "Refine a declarative geometry/node/table plan for safe SVG generation. Keep stable semantic "
            "IDs, labelled points, segment endpoints and ample margins. Never write raw SVG. Preserve "
            "base/annotation/overlay targets. Do not change the mathematics to improve appearance."
        ),
    ),
    "overlay_frame_agent": (
        "GENERATE_OVERLAY_SEQUENCE",
        (
            "Add ordered overlays/frames using existing stable IDs only. Actions HIGHLIGHT,DIM,SHOW,HIDE,"
            "LABEL,RELABEL,MARK_EQUAL,MARK_PARALLEL,MARK_PERPENDICULAR,SHOW_RATIO,FOCUS_REGION,"
            "EMPHASIZE_EQUATION_LINE,EMPHASIZE_TERM. Layout is RESET_TO_BASE_EACH_FRAME; each frame "
            "must explicitly include what it needs. Never mark equality/perpendicularity unless justified."
        ),
    ),
    "annotation_agent": (
        "ANNOTATE_ARTIFACT",
        (
            "Add brief readable captions, stable step numbers, concept/theorem tags, optional hint tags "
            "and supplied explanation/step links. Do not obscure base content or label circles as "
            "equal unless that is explicitly being described as a hypothesis, not drawn as proof."
        ),
    ),
    "validation_agent": (
        "VALIDATE_ARTIFACT",
        (
            "Call validate_artifact_plan on the exact final plan. Report the actual structural, "
            "layout and subject-rule validation errors/warnings. A valid renderer report is not proof "
            "of the mathematical theorem. Return {valid,errors,warnings,plan}; never approve invalid "
            "output or silently omit elements. Do not publish or infer learner mastery."
        ),
    ),
}

SUBJECTS = {
    "geometry_artifact_agent": (
        "GENERATE_GEOMETRY_SVG",
        (
            "Geometry prioritizes clarity. Vertices/contact points have visible dots and noncolliding "
            "labels; structural segments are prominent, auxiliary extensions dashed, circles thin/light. "
            "Use only relevant angle/equality marks. For incircles, call draw_geometry_diagram with "
            "incircle_triangles computed by the server, never guessed centers/radii. For the convex "
            "quadrilateral/equal-inradii problem, show four triangle incircles and diagonals as a "
            "generated construction sketch; do not assume a rectangle or assert sketch radii are equal."
        ),
    ),
    "algebra_artifact_agent": (
        "GENERATE_ALGEBRA_LATEX",
        (
            "Maintain stable aligned equation rows and highlight only changed terms. Supply reasons "
            "for equivalent transformations; chunk long derivations. Ask latex_artifact_agent to refine "
            "notation. Do not solve the next hidden step unless explicitly authorized in the context."
        ),
    ),
    "combinatorics_artifact_agent": (
        "GENERATE_COMBINATORICS_VISUAL",
        (
            "Use labelled NODE/SEGMENT trees, case CELL tables/grids, pairings or discrete paths. "
            "Separate and label cases, preserve symmetry and consistent spacing, sequentially reveal "
            "branches. Each current branch/pruning action needs an explanatory frame. Do not imply "
            "that overlapping cases are disjoint or duplicate outcomes without warning."
        ),
    ),
    "number_theory_artifact_agent": (
        "GENERATE_NUMBER_THEORY_VISUAL",
        (
            "Represent divisibility, factor trees, residues or Euclidean quotient/remainder steps. "
            "Specify number_theory_mode; modular cards explicitly state modulus. Label prime/composite "
            "nodes accurately and preserve implication flow. Use discrete cells/points rather than "
            "a continuous diagram that changes integer meaning."
        ),
    ),
}


def build_artifact_agents(model: str | BaseLlm) -> dict[str, Agent]:
    """Build a directed acyclic specialist network; each agent has one distinct role."""

    def create(name, capability, instruction, tools):
        return Agent(
            name=name,
            model=LiteLlm(model=model) if isinstance(model, str) else model,
            description=f"{capability}: {instruction}",
            instruction=COMMON + "\nYour role:\n" + instruction,
            tools=tools,
            before_model_callback=_model_limit,
            before_agent_callback=_restore_invocation_state,
            disallow_transfer_to_parent=True,
            disallow_transfer_to_peers=True,
        )

    agents = {}
    for name, (capability, instruction) in RULES.items():
        tools = [validate_artifact_plan] if name == "validation_agent" else []
        agents[name] = create(name, capability, instruction, tools)
    refinement = [ArtifactAgentTool(agent=agents[name]) for name in RULES]
    for name, (capability, instruction) in SUBJECTS.items():
        agents[name] = create(
            name,
            capability,
            instruction
            + """
For a simple requested drawing, produce a plan and render it immediately; no need to call
every helper. For complex artifacts delegate relevant LaTeX/SVG refinement, overlay and
annotation work, then validation. Preserve the whole plan at each handoff and use actual
validation errors to repair at most once. For geometry use draw_geometry_diagram; for other
subjects use preview_artifact. Return the exact rendering tool markdown_block, not just a
description of how to draw it. request_artifact is ONLY for explicitly requested staff
publication, not a prerequisite for ephemeral student drawings.
""",
            [
                *refinement,
                draw_geometry_diagram
                if name == "geometry_artifact_agent"
                else preview_artifact,
                request_artifact,
            ],
        )
    agents["subject_planning_agent"] = create(
        "subject_planning_agent",
        "PLAN_SUBJECT_ARTIFACT",
        "Interpret supplied subject, concept, audience, difficulty, goal and answer-visibility "
        "limits. First use search_artifacts to look for reusable published work when useful. "
        "For a new requested illustration route to exactly one subject specialist: "
        "geometry_artifact_agent, algebra_artifact_agent, combinatorics_artifact_agent or "
        "number_theory_artifact_agent. Relay supplied problem context and restrictions, then "
        "return its exact rendering markdown_block/result to the tutor. Do not fabricate "
        "source attribution or claim staff publication. Do not recursively delegate to yourself.",
        [
            search_artifacts,
            *[ArtifactAgentTool(agent=agents[name]) for name in SUBJECTS],
        ],
    )
    return agents


def artifact_agent_tools(agents: dict[str, Agent]) -> list[ArtifactAgentTool]:
    # Direct subject calls avoid planner overhead when the tutor already knows the subject.
    return [
        ArtifactAgentTool(agent=agents[name])
        for name in ("subject_planning_agent", *SUBJECTS)
    ]
