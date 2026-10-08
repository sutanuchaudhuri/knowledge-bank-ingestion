"""Model-independent orchestration contracts; providers live outside the deterministic core."""

from __future__ import annotations

import json
import re
import time
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import Field, model_validator

from .errors import GeometryError, InvalidFrame
from .schemas import (
    ESTABLISHED,
    Frame,
    Identifier,
    Model,
    Relation,
    RelationStatus,
    SceneInput,
    StateDelta,
    VisualDelta,
)
from .service import apply_delta, create_scene
from .theorems import SNAPSHOT, establish, lookup

PROMPT_VERSION = "geometry-agent-v2"


class GeometryRequest(Model):
    problem_text: str = Field(min_length=1, max_length=20000)
    goal: str = Field(min_length=1, max_length=2000)
    context: tuple[dict, ...] = Field(default=(), max_length=128)
    scene_id: Identifier | None = None
    expected_version: int | None = Field(default=None, ge=0)
    required_entities: tuple[Identifier, ...] = ()
    forbidden_entities: tuple[Identifier, ...] = ()
    trusted_facts: tuple[Relation, ...] = ()
    current_math_step: str = Field(default="", max_length=200)
    seed: int = Field(default=17, ge=0, le=2147483647)
    rendering_mode: Literal["EXACT_OR_CONSTRAINED", "SCHEMATIC"] = "EXACT_OR_CONSTRAINED"
    problem_id: str | None = Field(default=None, max_length=200)
    solution_step_id: str | None = Field(default=None, max_length=200)
    solve_attempt_id: UUID | None = None

    @model_validator(mode="after")
    def version_pair(self):
        if len(json.dumps(self.context)) > 32768:
            raise ValueError("context exceeds 32 KiB")
        if (self.scene_id is None) != (self.expected_version is None):
            raise ValueError("scene_id and expected_version must be supplied together")
        if set(self.required_entities) & set(self.forbidden_entities):
            raise ValueError("an entity cannot be both required and forbidden")
        return self


class ClaimEvidence(Model):
    relation_id: Identifier
    source_quote: str = Field(default="", max_length=4000)
    trusted_fact_id: Identifier | None = None
    theorem_id: str | None = Field(default=None, max_length=80)
    premise_ids: tuple[Identifier, ...] = ()


class GeometryPlan(Model):
    schema_version: Literal["1"] = "1"
    initial: SceneInput | None = None
    delta: StateDelta | None = None
    evidence: tuple[ClaimEvidence, ...] = ()
    required_entities: tuple[Identifier, ...] = ()
    forbidden_entities: tuple[Identifier, ...] = ()
    theorem_snapshot: Literal["geometry-theorems-v1"] = "geometry-theorems-v1"

    @model_validator(mode="after")
    def exclusive_operation(self):
        if (self.initial is None) == (self.delta is None):
            raise ValueError("provide exactly one initial scene or delta")
        return self


class Review(Model):
    accept: bool
    reasons: tuple[str, ...] = Field(default=(), max_length=16)


class ModelProvider(Protocol):
    model: str
    records: list[dict]

    def complete(
        self, role: str, payload: dict, output_type: type[Model], timeout: float
    ) -> Model: ...


class OrchestrationFailure(GeometryError):
    code = "GEOMETRY_PLAN_EXHAUSTED"

    def __init__(self, message, evidence):
        super().__init__(message)
        self.evidence = evidence


def _source(request):
    return (
        request.problem_text
        + "\n"
        + request.goal
        + "\n"
        + "\n".join(str(c.get("fact", "")) for c in request.context)
    )


def _same_fact(first, second):
    return first.type == second.type and first.args == second.args and first.value == second.value


def validate_evidence(request, plan, previous):
    source = _source(request)
    initial = plan.initial
    delta = plan.delta
    facts = list(previous.math_state.relations) if previous else []
    objects = dict(previous.math_state.objects) if previous else {}
    if initial:
        objects.update(initial.objects)
        additions = list(initial.relations)
    else:
        objects.update(delta.add_objects)
        additions = list(delta.add_relations)
        for change in delta.change_status:
            existing = next((r for r in facts if r.id == change.relation_id), None)
            if existing is None:
                raise GeometryError(f"unknown changed relation {change.relation_id}")
            additions.append(existing.model_copy(update={"status": change.status}))
    evidence = {e.relation_id: e for e in plan.evidence}
    for claim in additions:
        if claim.status == "DISPROVEN":
            proof = evidence.get(claim.id)
            trusted = next(
                (r for r in request.trusted_facts if proof and r.id == proof.trusted_fact_id), None
            )
            if trusted is None or trusted.status != "DISPROVEN" or not _same_fact(trusted, claim):
                raise GeometryError(f"model prose cannot authorize DISPROVEN: {claim.id}")
            continue
        if claim.status not in ESTABLISHED:
            continue
        proof = evidence.get(claim.id)
        if proof is None:
            raise GeometryError(f"missing mathematical evidence for {claim.id}")
        original = next((r for r in facts if _same_fact(r, claim)), None)
        if (
            original
            and original.status not in ESTABLISHED
            and not (proof.trusted_fact_id or proof.theorem_id)
        ):
            raise GeometryError(
                f"source prose cannot promote an existing target/unknown: {claim.id}"
            )
        if proof.trusted_fact_id:
            trusted = next(
                (r for r in request.trusted_facts if r.id == proof.trusted_fact_id), None
            )
            if (
                trusted is None
                or trusted.status not in ESTABLISHED
                or not _same_fact(trusted, claim)
            ):
                raise GeometryError(f"trusted fact does not justify {claim.id}")
            if claim.status == RelationStatus.PROVEN and trusted.status != RelationStatus.PROVEN:
                raise GeometryError("given evidence cannot be relabeled as a proof")
        elif proof.theorem_id:
            establish(proof.theorem_id, claim, facts, objects, proof.premise_ids)
        else:
            if claim.status == RelationStatus.PROVEN:
                raise GeometryError(f"model prose cannot authorize PROVEN: {claim.id}")
            quote = proof.source_quote
            if not quote or quote not in source:
                raise GeometryError(f"source quote is not grounded: {claim.id}")
            if claim.status == "GIVEN" and (
                quote not in request.problem_text
                or re.search(r"\b(?:prove|show that|goal|target to prove)\b", quote, re.IGNORECASE)
            ):
                raise GeometryError(f"a requested target/construction is not a given: {claim.id}")
            if claim.status == "ASSUMED_FOR_CONSTRUCTION" and re.search(
                r"\b(?:prove|show that|target to prove)\b", quote, re.IGNORECASE
            ):
                raise GeometryError(
                    f"a proof goal cannot become a construction assumption: {claim.id}"
                )
            if not all(
                re.search(rf"(?<![A-Za-z0-9]){re.escape(arg)}(?![a-z0-9])", quote)
                or arg in re.findall(r"\b[A-Z][A-Z0-9]+\b", quote)[0:128]
                or arg in quote
                for arg in claim.args
            ):
                raise GeometryError(f"source quote lacks claimed objects: {claim.id}")
        facts = [r for r in facts if r.id != claim.id] + [claim]


def check_disclosure(frame, required, forbidden, previous=None):
    visible = {
        name
        for name, style in frame.visual_state.styles.items()
        if style.visible and style.opacity > 0
    }
    absent = set(required) - visible
    leaked = set(forbidden) & visible
    if absent or leaked:
        raise GeometryError(
            f"goal/disclosure violation: absent={sorted(absent)}, forbidden={sorted(leaked)}"
        )
    if previous and not set(previous.scene_state.entities).issubset(frame.scene_state.entities):
        raise GeometryError("base scene identities were lost")
    for name in required:
        if name.startswith("triangle_") and name not in frame.scene_state.entities:
            raise GeometryError("requested triangle construction was not realized")


def defining_triangle(name, source):
    return re.search(
        rf"\b{re.escape(name)}\s*(?:is|=)\s*(?:the\s*)?"
        r"(?:circumcenter\s*(?:of\s*)?|center\s*of\s*(?:the\s*)?"
        r"circumcircle\s*(?:of|through)\s*)"
        r"(?:triangle\s*)?[\(\s]*([A-Z])[\s,]*([A-Z])[\s,]*([A-Z])",
        source,
        re.IGNORECASE,
    )


def circumcenter_goal_guards(request):
    source = _source(request)
    match = re.search(r"\b(A\d+|B\d+|C\d+|D\d+)\b", request.goal)
    if not match:
        return (), ()
    name = match[1]
    definition = defining_triangle(name, source)
    if not definition:
        return (), ()
    triangle = "".join(definition.groups())
    required = ("point_" + name, "triangle_" + triangle)
    other = re.findall(r"\b([A-D]\d+)\b", source)
    forbidden = tuple("point_" + p for p in sorted(set(other)) if p != name)
    return required, forbidden


def orchestrate(
    request: GeometryRequest,
    provider: ModelProvider,
    previous: Frame | None = None,
    max_attempts=3,
    max_calls=9,
    deadline_seconds=120,
):
    if not 1 <= max_attempts <= 5 or not 3 <= max_calls <= 15 or not 1 <= deadline_seconds <= 300:
        raise GeometryError("invalid orchestration budget")
    if previous and (
        request.scene_id != previous.scene_state.scene_id
        or request.expected_version != previous.version
    ):
        raise GeometryError("request does not match the accepted base version")
    if request.scene_id and previous is None:
        raise GeometryError("missing accepted base scene")
    started = time.monotonic()
    if previous and request.problem_text != previous.math_state.problem_text:
        raise GeometryError("problem text cannot change within a cumulative scene")
    attempts = []
    calls = 0
    required_goal, forbidden_goal = circumcenter_goal_guards(request)
    if previous:
        forbidden_goal = tuple(
            entity for entity in forbidden_goal if entity not in previous.scene_state.entities
        )
    packet: dict[str, Any] = {
        "request": request.model_dump(mode="json"),
        "previous": previous.model_dump(mode="json") if previous else None,
        "theorems": lookup(),
        "feedback": [],
        "required_entities": list(set(request.required_entities) | set(required_goal)),
        "forbidden_entities": list(set(request.forbidden_entities) | set(forbidden_goal)),
    }

    def model_call(role, payload, output):
        nonlocal calls
        remaining = deadline_seconds - (time.monotonic() - started)
        if calls >= max_calls or remaining <= 0:
            raise GeometryError("geometry model call/time budget exhausted")
        calls += 1
        return provider.complete(role, payload, output, min(remaining, 45))

    for attempt in range(max_attempts):
        record: dict[str, Any] = {
            "attempt": attempt + 1,
            "previous": packet["previous"],
            "status": "FAILED",
        }
        try:
            plan = GeometryPlan.model_validate(
                model_call("reasoning", packet, GeometryPlan).model_dump()
            )
            record["plan"] = plan.model_dump(mode="json")
            if (previous is None) != (plan.initial is not None):
                raise GeometryError("plan operation does not match create/update request")
            if plan.initial and plan.initial.problem_text != request.problem_text:
                raise GeometryError("plan must preserve the exact problem text")
            if plan.initial and (
                plan.initial.seed != request.seed
                or plan.initial.rendering_mode != request.rendering_mode
            ):
                raise GeometryError("plan must preserve requested seed/mode")
            validate_evidence(request, plan, previous)
            if plan.initial:
                preview = create_scene(plan.initial.model_copy(update={"visual": VisualDelta()}))
            else:
                if plan.delta is None or previous is None:
                    raise GeometryError("delta requires an accepted base scene")
                preview = apply_delta(
                    previous, plan.delta.model_copy(update={"visual": VisualDelta()})
                )
            if not preview.scene_state.entities:
                raise GeometryError("no goal-relevant mathematical construction was specified")
            visual = VisualDelta.model_validate(
                model_call(
                    "presentation",
                    {
                        "context": packet,
                        "plan": record["plan"],
                        "available_entities": preview.scene_state.model_dump(mode="json")[
                            "entities"
                        ],
                        "default_styles": preview.visual_state.model_dump(mode="json")["styles"],
                    },
                    VisualDelta,
                ).model_dump()
            )
            record["visual"] = visual.model_dump(mode="json")
            if plan.initial:
                candidate = create_scene(plan.initial.model_copy(update={"visual": visual}))
            else:
                if plan.delta is None or previous is None:
                    raise GeometryError("delta requires an accepted base scene")
                if plan.delta.expected_version != request.expected_version:
                    raise GeometryError("plan uses a stale version")
                candidate = apply_delta(previous, plan.delta.model_copy(update={"visual": visual}))
            record["candidate"] = candidate.model_dump(mode="json")
            required = {*packet["required_entities"], *plan.required_entities}
            forbidden = {*packet["forbidden_entities"], *plan.forbidden_entities}
            check_disclosure(candidate, required, forbidden, previous)
            if any(name in candidate.scene_state.entities for name in forbidden_goal):
                raise GeometryError(
                    "future circumcenter point was constructed before its focus stage"
                )
            for point_id in required:
                if not point_id.startswith("point_"):
                    continue
                name = point_id.removeprefix("point_")
                expected = defining_triangle(name, _source(request))
                if expected and not any(
                    r.type == "CIRCUMCENTER"
                    and r.args == (name, *expected.groups())
                    and r.status in ESTABLISHED
                    for r in candidate.math_state.relations
                ):
                    raise GeometryError("circumcenter focus has the wrong defining triangle")
            review = Review.model_validate(
                model_call(
                    "review",
                    {"context": packet, "plan": record["plan"], "candidate": record["candidate"]},
                    Review,
                ).model_dump()
            )
            record["review"] = review.model_dump(mode="json")
            if not review.accept:
                raise GeometryError("semantic/goal review rejected: " + "; ".join(review.reasons))
            record["status"] = "ACCEPTED"
            attempts.append(record)
            return candidate, {
                "schema_version": "1",
                "prompt_version": PROMPT_VERSION,
                "theorem_snapshot": SNAPSHOT,
                "request": request.model_dump(mode="json"),
                "model": provider.model,
                "attempts": attempts,
                "calls": calls,
                "provider_calls": provider.records,
                "elapsed_seconds": time.monotonic() - started,
                "status": "ACCEPTED",
            }
        except (GeometryError, ValueError) as exc:
            record["error"] = str(exc)
            if isinstance(exc, GeometryError):
                record["diagnostics"] = exc.details
            if isinstance(exc, InvalidFrame):
                record["candidate"] = exc.frame.model_dump(mode="json")
            attempts.append(record)
            packet["feedback"] = [
                {"error": r.get("error"), "validation": r.get("candidate", {}).get("validation")}
                for r in attempts
            ]
            if time.monotonic() - started >= deadline_seconds or calls >= max_calls:
                break
    raise OrchestrationFailure(
        "No valid, goal-relevant geometry candidate was accepted.",
        {
            "schema_version": "1",
            "prompt_version": PROMPT_VERSION,
            "theorem_snapshot": SNAPSHOT,
            "request": request.model_dump(mode="json"),
            "model": provider.model,
            "attempts": attempts,
            "calls": calls,
            "provider_calls": provider.records,
            "status": "FAILED",
            "elapsed_seconds": time.monotonic() - started,
        },
    )
