"""Strict offline tutoring-program contracts; structural checks are not proof review."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def content_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


ClaimKey = Annotated[str, Field(pattern=r"^CLAIM_[A-Z0-9_-]{1,60}$")]
MisconceptionKey = Annotated[str, Field(pattern=r"^MIS_[A-Z0-9_-]{1,60}$")]


class Instruction(StrictModel):
    goal_text: str = Field(min_length=1, max_length=600)
    recognition_cue: str
    # Defaults preserve backward compatibility with routes persisted before this
    # field existed (RouteProgram.model_validate on older stored JSON); the OpenAI
    # strict-mode schema still forces these into "required" at generation time.
    has_diagram: bool = False
    diagram_description: str = Field(
        default="",
        max_length=1200,
        description="What the figure depicts, stated before any explanation. Empty if has_diagram is false.",
    )
    diagram_instructions: str = Field(
        default="",
        max_length=1600,
        description="Concrete enough to render the figure: labeled points/shapes/angles/measurements "
        "and their relative positions. Empty if has_diagram is false.",
    )
    reasoning_explanation: str
    why_this_works: str
    prerequisite_recap: str
    connection_to_previous_step: str
    connection_to_next_step: str
    common_error_summary: str
    student_prompt: str = Field(min_length=1, max_length=1200)
    expected_response: str = Field(min_length=1)
    short_explanation: str
    full_explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_diagram_fields(self):
        if self.has_diagram:
            if not self.diagram_description.strip() or not self.diagram_instructions.strip():
                raise ValueError(
                    "has_diagram is true but diagram_description/diagram_instructions are blank."
                )
        elif self.diagram_description.strip() or self.diagram_instructions.strip():
            raise ValueError(
                "has_diagram is false; diagram_description/diagram_instructions must be empty, "
                "not invented for a step without a figure."
            )
        return self


class Requirement(StrictModel):
    taxonomy_node_id: str
    role: Literal["REQUIRED", "HELPFUL", "RECOGNITION", "EXECUTION", "JUSTIFICATION", "USED"]
    required_level: int = Field(ge=1, le=5)
    importance: float = Field(ge=0, le=1)
    blocking: bool
    proposed_node_type: Literal["CONCEPT", "SUBCONCEPT", "SKILL", "TECHNIQUE", ""] = Field(
        default="",
        description="Blank when taxonomy_node_id is an existing canonical ID. Set this plus "
        "proposed_name/proposed_description together ONLY when proposing a genuinely new "
        "node absent from canonical_taxonomy; general problem-solving strategies use TECHNIQUE.",
    )
    proposed_name: str = Field(default="", max_length=200)
    proposed_description: str = Field(default="", max_length=600)

    @model_validator(mode="after")
    def validate_proposal_consistency(self):
        fields = (
            self.proposed_node_type,
            self.proposed_name.strip(),
            self.proposed_description.strip(),
        )
        if any(fields) and not all(fields):
            raise ValueError(
                "A taxonomy proposal needs proposed_node_type, proposed_name and "
                "proposed_description together, or none of them."
            )
        if self.proposed_node_type and not re.match(
            r"^[A-Z][A-Z0-9]*(\.[A-Z0-9_]+){1,6}$", self.taxonomy_node_id
        ):
            raise ValueError(
                "A proposed taxonomy_node_id must follow the dotted uppercase convention, "
                "e.g. ALG.C01.S02 or SKILL.NT.APPLY_CRT."
            )
        return self


class Asset(StrictModel):
    key: str = Field(
        pattern=r"^(CLAIM|MIS|THEORY|LI)_[A-Z0-9_-]{1,60}$",
        description="Unique ID. Prefix CLAIM_ for claims, MIS_ for misconceptions, THEORY_ for theory, LI_ for quizzes.",
    )
    kind: Literal["CLAIM", "MISCONCEPTION", "THEORY", "LEARNING_ITEM"]
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    canonical_expression: str
    symptom: str
    why_wrong: str
    correct_model: str
    recognition_cues: list[str]
    question: str
    expected_answer: str
    purpose: Literal[
        "PREREQUISITE_CHECK",
        "MISCONCEPTION_DIAGNOSTIC",
        "TECHNIQUE_RECOGNITION",
        "ISOLATED_EXECUTION",
        "GUIDED_PRACTICE",
        "TRANSFER",
        "MASTERY_CHECK",
        "NONE",
    ]
    taxonomy_node_ids: list[str]
    diagnoses: list[MisconceptionKey]
    remediates: list[MisconceptionKey]


class AssetLink(StrictModel):
    asset_key: str
    role: Literal["CAN_TRIGGER", "CHECKED_BY", "EXPLAINED_BY"]


class RouteStep(StrictModel):
    mathematical_result: str = Field(min_length=1)
    source_quote: str = Field(min_length=1)
    depends_on: list[int]
    produces: list[ClaimKey] = Field(
        description="IDs of CLAIM assets declared in assets, NOT result text. Empty if none."
    )
    uses_claims: list[ClaimKey] = Field(
        description="IDs of CLAIM assets produced by earlier steps, NOT text. Empty if none."
    )
    requirements: list[Requirement]
    instruction: Instruction
    hints: list[str] = Field(min_length=4, max_length=4)
    asset_links: list[AssetLink]


class RouteProgram(StrictModel):
    approach_name: str = Field(min_length=1, max_length=200)
    approach_summary: str = Field(min_length=1, max_length=600)
    difficulty_level: int = Field(ge=1, le=5)
    conceptual_load: int = Field(ge=1, le=5)
    algebraic_load: int = Field(ge=1, le=5)
    insight_load: int = Field(ge=1, le=5)
    steps: list[RouteStep] = Field(min_length=2, max_length=30)
    assets: list[Asset] = Field(max_length=100)

    @model_validator(mode="after")
    def validate_dag(self):
        assets = {asset.key: asset for asset in self.assets}
        if len(assets) != len(self.assets):
            raise ValueError("Asset keys must be unique.")
        produced: set[str] = set()
        for index, step in enumerate(self.steps, 1):
            if len(step.depends_on) != len(set(step.depends_on)) or any(
                prior < 1 or prior >= index for prior in step.depends_on
            ):
                raise ValueError(
                    f"Step {index} dependencies {step.depends_on} must reference earlier "
                    f"1-based indices (1..{index - 1}); cycles are forbidden."
                )
            for key in step.produces + step.uses_claims:
                if key not in assets or assets[key].kind != "CLAIM":
                    raise ValueError("Claim links must resolve to claims.")
            if not set(step.uses_claims) <= produced:
                raise ValueError("Used claims must be established by an earlier step.")
            produced.update(step.produces)
            kinds = {
                "CAN_TRIGGER": "MISCONCEPTION",
                "CHECKED_BY": "LEARNING_ITEM",
                "EXPLAINED_BY": "THEORY",
            }
            for link in step.asset_links:
                if link.asset_key not in assets or assets[link.asset_key].kind != kinds[link.role]:
                    raise ValueError("Step asset link has a missing or incompatible target.")
            targets = [(r.taxonomy_node_id, r.role) for r in step.requirements]
            if len(set(targets)) != len(targets):
                raise ValueError("Duplicate step requirements.")
            if any(not hint.strip() for hint in step.hints):
                raise ValueError("All four hint levels must be nonempty.")
        for asset in self.assets:
            prefix = {
                "CLAIM": "CLAIM_",
                "MISCONCEPTION": "MIS_",
                "THEORY": "THEORY_",
                "LEARNING_ITEM": "LI_",
            }
            if not asset.key.startswith(prefix[asset.kind]):
                raise ValueError("Asset key prefix must match its kind.")
            if asset.diagnoses and asset.kind != "LEARNING_ITEM":
                raise ValueError("Only learning items diagnose misconceptions.")
            if asset.remediates and asset.kind != "THEORY":
                raise ValueError("Only theory items remediate misconceptions.")
            for key in asset.diagnoses + asset.remediates:
                if key not in assets or assets[key].kind != "MISCONCEPTION":
                    raise ValueError("Diagnosis/remediation must target a declared misconception.")
            if asset.kind == "LEARNING_ITEM" and (
                not asset.question.strip()
                or not asset.expected_answer.strip()
                or asset.purpose == "NONE"
            ):
                raise ValueError(
                    "Learning items need a question, answer and instructional purpose."
                )
        return self


def validate_source(
    program: RouteProgram,
    source: str,
    taxonomy_ids: set[str],
    enforce_proposal_novelty: bool = True,
) -> None:
    normalized = " ".join(source.split())
    # A requirement may introduce a brand-new canonical node (role/level/etc. plus a
    # proposed_node_type/name/description) when nothing supplied genuinely applies;
    # persistence later upserts these into pedagogy.taxonomy_node for future runs.
    proposed_ids = {
        item.taxonomy_node_id
        for step in program.steps
        for item in step.requirements
        if item.proposed_node_type
    }
    allowed_ids = taxonomy_ids | proposed_ids
    # A single decomposition call must not collapse several genuinely different
    # proposed concepts onto one ID: whichever upserts first would silently fix
    # that ID's canonical name/description for every later, unrelated use of it.
    proposals_by_id: dict[str, tuple] = {}
    for step in program.steps:
        if " ".join(step.source_quote.split()) not in normalized:
            raise ValueError("Every step must cite an exact nonempty source excerpt.")
        for item in step.requirements:
            if item.taxonomy_node_id not in allowed_ids:
                raise ValueError(
                    "Requirement refers to an unknown canonical taxonomy ID without a proposal."
                )
            # This collision guard only makes sense against the small shortlist the
            # model actually saw at generation time (route_compiler.generate()). By
            # review/edit/publish time, taxonomy_ids is the FULL canonical table,
            # which by definition already contains this same program's own earlier
            # proposal once persisted — that is expected, not a new contradiction.
            if (
                enforce_proposal_novelty
                and item.taxonomy_node_id in taxonomy_ids
                and item.proposed_node_type
            ):
                raise ValueError(
                    "Requirement must not propose new metadata for an already-known taxonomy ID."
                )
            if item.proposed_node_type:
                signature = (item.proposed_node_type, item.proposed_name, item.proposed_description)
                existing = proposals_by_id.setdefault(item.taxonomy_node_id, signature)
                if existing != signature:
                    raise ValueError(
                        f"Proposed taxonomy_node_id {item.taxonomy_node_id!r} was used for two "
                        "different concepts in the same program; each new concept needs its own ID."
                    )
    for asset in program.assets:
        if not set(asset.taxonomy_node_ids) <= allowed_ids:
            raise ValueError("Asset refers to an unknown canonical taxonomy ID.")


def validate_enrichment(program: RouteProgram) -> None:
    """Drafts may be incomplete; review/publication requires connected teaching assets."""
    assets = {asset.key: asset for asset in program.assets}
    for index, step in enumerate(program.steps, 1):
        roles = {link.role for link in step.asset_links}
        if not step.produces or not {"CAN_TRIGGER", "EXPLAINED_BY", "CHECKED_BY"} <= roles:
            raise ValueError(
                f"Step {index} requires claim, misconception, theory and quiz enrichment."
            )
        misconceptions = {link.asset_key for link in step.asset_links if link.role == "CAN_TRIGGER"}
        theories = [
            assets[link.asset_key] for link in step.asset_links if link.role == "EXPLAINED_BY"
        ]
        quizzes = [assets[link.asset_key] for link in step.asset_links if link.role == "CHECKED_BY"]
        for key in step.produces:
            if not assets[key].description.strip():
                raise ValueError(f"Step {index} requires a substantive claim.")
        if any(not item.description.strip() for item in theories):
            raise ValueError(f"Step {index} requires substantive theory content.")
        if any(not item.question.strip() or not item.expected_answer.strip() for item in quizzes):
            raise ValueError(f"Step {index} requires a nonblank quiz and answer.")
        for key in misconceptions:
            asset = assets[key]
            if not all(
                text.strip() for text in (asset.symptom, asset.why_wrong, asset.correct_model)
            ):
                raise ValueError(f"Step {index} requires substantive misconception content.")
            if not any(key in item.remediates for item in theories):
                raise ValueError(f"Step {index} requires theory remediation for {key}.")
            if not any(key in item.diagnoses for item in quizzes):
                raise ValueError(f"Step {index} requires a diagnostic quiz for {key}.")


def program_digest(program: RouteProgram) -> str:
    """Hash semantic content independently of unordered relation/asset SQL row order."""
    payload = program.model_dump()
    payload["assets"].sort(key=lambda asset: asset["key"])
    for asset in payload["assets"]:
        for key in ("taxonomy_node_ids", "diagnoses", "remediates"):
            asset[key].sort()
    for step in payload["steps"]:
        for key in ("depends_on", "produces", "uses_claims"):
            step[key].sort()
        step["requirements"].sort(key=lambda item: (item["taxonomy_node_id"], item["role"]))
        step["asset_links"].sort(key=lambda item: (item["asset_key"], item["role"]))
    return content_hash(payload)
