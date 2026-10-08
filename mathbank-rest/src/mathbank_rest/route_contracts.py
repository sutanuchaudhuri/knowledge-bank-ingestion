"""Strict offline tutoring-program contracts; structural checks are not proof review."""

from __future__ import annotations

import hashlib
import json
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


class Requirement(StrictModel):
    taxonomy_node_id: str
    role: Literal["REQUIRED", "HELPFUL", "RECOGNITION", "EXECUTION", "JUSTIFICATION", "USED"]
    required_level: int = Field(ge=1, le=5)
    importance: float = Field(ge=0, le=1)
    blocking: bool


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


def validate_source(program: RouteProgram, source: str, taxonomy_ids: set[str]) -> None:
    normalized = " ".join(source.split())
    for step in program.steps:
        if " ".join(step.source_quote.split()) not in normalized:
            raise ValueError("Every step must cite an exact nonempty source excerpt.")
        if any(item.taxonomy_node_id not in taxonomy_ids for item in step.requirements):
            raise ValueError("Requirement refers to an unknown canonical taxonomy ID.")
    for asset in program.assets:
        if not set(asset.taxonomy_node_ids) <= taxonomy_ids:
            raise ValueError("Asset refers to an unknown canonical taxonomy ID.")


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
