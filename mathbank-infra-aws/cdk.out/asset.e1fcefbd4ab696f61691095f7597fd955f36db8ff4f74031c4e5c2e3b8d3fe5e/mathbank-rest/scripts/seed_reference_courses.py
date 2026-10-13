"""Seed three real, published reference micro-courses — Markov state/transition
analysis, Vieta's formulas, and Jensen's inequality — using the exact shared
service layer (micro_course_service) and the exact template keys the student
renderer (mathbank-web InteractionTemplateRenderer.jsx) already supports.

This replaces the Playwright-only MC-REFERENCE fixture with real, queryable
rows: a student can open /learn/courses and click through the live Markov
graph/matrix/recurrence, Vieta roots-to-coefficients, and Jensen curve/chord
interactions instead of only seeing them via mocked browser tests.

Authors real (non-placeholder) JSON Schemas + accessibility policy for the
five seeded-but-DRAFT template versions these courses need, then publishes
them through the same validator the REST/CLI publish path uses
(requirements/41_INTERACTION_TEMPLATE_LIBRARY.md ITL-1/ITL-17). Interaction
instances and courses are created once and approved/published the same way;
once PUBLISHED, migration 033/034 triggers make them immutable, so re-running
this script is a no-op for anything already seeded.

Usage:
    cd mathbank-rest && .venv/bin/python scripts/seed_reference_courses.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import text

from mathbank_rest import interaction_catalog, interaction_validators
from mathbank_rest import micro_course_service as svc
from mathbank_rest.db.postgres import engine

SEED_AUTHOR = "reference-course-seed"

ACCESSIBILITY_BASE = {
    "keyboard_navigable": True,
    "focus_order": "linear, matches visual reading order",
    "screen_reader_summary": "An accessible text description accompanies every diagram or plot.",
    "reduced_motion": "static; no required animation",
}

TEMPLATE_SCHEMAS: dict[str, dict] = {
    "STATE_GRAPH_EXPLORER_V1": {
        "input_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["states", "transitions"],
            "properties": {
                "states": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id"],
                        "properties": {"id": {"type": "string"}, "label": {"type": "string"}},
                    },
                },
                "transitions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["from", "to", "p"],
                        "properties": {
                            "from": {"type": "string"},
                            "to": {"type": "string"},
                            "p": {"type": "string", "description": "probability, as a decimal or fraction literal"},
                        },
                    },
                },
            },
        },
        "state_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "current_state": {"type": "string"},
                "visited_states": {"type": "array", "items": {"type": "string"}},
                "visited_transitions": {"type": "array", "items": {"type": "string"}},
            },
        },
        "event_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["event"],
            "properties": {
                "event": {"enum": ["SELECT_STATE", "FOLLOW_TRANSITION"]},
                "from": {"type": "string"},
                "to": {"type": "string"},
            },
        },
        "output_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "visited_all_states": {"type": "boolean"},
                "visited_all_transitions": {"type": "boolean"},
            },
        },
        "allowed_controls": [],
        "allowed_icons": ["GRAPH", "START_STATE", "TARGET_STATE"],
    },
    "TRANSITION_MATRIX_EDITOR_V1": {
        "input_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["states"],
            "properties": {
                "states": {"type": "array", "items": {"type": "object"}},
                "transitions": {"type": "array", "items": {"type": "object"}},
                "matrix": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
            },
        },
        "state_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "description": "Map of m{row}_{column} cell keys to the student-entered probability.",
            "additionalProperties": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "event_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["event", "row"],
            "properties": {
                "event": {"const": "SUBMIT_ROW"},
                "row": {"type": "integer", "minimum": 0},
                "values": {"type": "array", "items": {"type": "number"}},
            },
        },
        "output_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "row_sums": {"type": "array", "items": {"type": "number"}},
                "all_rows_valid": {"type": "boolean"},
            },
        },
        "allowed_controls": ["PROBABILITY_MATRIX_CELL"],
        "allowed_icons": ["MATRIX"],
    },
    "RECURRENCE_EXPLORER_V1": {
        "input_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["recurrence", "initial"],
            "properties": {
                "recurrence": {"type": "string"},
                "initial": {"type": "string"},
                "fixed_point": {"type": "string"},
            },
        },
        "state_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "sequence": {"type": "array", "items": {"type": "number"}},
                "step": {"type": "integer", "minimum": 0},
            },
        },
        "event_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["event"],
            "properties": {"event": {"const": "ADVANCE_STEP"}},
        },
        "output_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "converged": {"type": "boolean"},
                "limit_estimate": {"type": "number"},
            },
        },
        "allowed_controls": [],
        "allowed_icons": ["FORMULA"],
    },
    "POLYNOMIAL_ROOT_COEFFICIENT_EXPLORER_V1": {
        "input_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["controls"],
            "properties": {
                "controls": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "control": {"type": "string"},
                            "min": {"type": "number"},
                            "max": {"type": "number"},
                            "step": {"type": "number"},
                            "initial": {"type": "number"},
                        },
                    },
                }
            },
        },
        "state_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"r1": {"type": "number"}, "r2": {"type": "number"}, "r3": {"type": "number"}},
        },
        "event_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["event", "root_key", "value"],
            "properties": {
                "event": {"const": "ADJUST_ROOT"},
                "root_key": {"enum": ["r1", "r2", "r3"]},
                "value": {"type": "number"},
            },
        },
        "output_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "e1": {"type": "number"},
                "e2": {"type": "number"},
                "e3": {"type": "number"},
                "polynomial": {"type": "string"},
            },
        },
        "allowed_controls": ["REAL_SLIDER"],
        "allowed_icons": ["FORMULA"],
    },
    "FUNCTION_GRAPH_EXPLORER_V1": {
        "input_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["controls", "function"],
            "properties": {
                "controls": {"type": "object"},
                "function": {
                    "type": "object",
                    "required": ["expression", "convexity"],
                    "properties": {
                        "expression": {"type": "string"},
                        "convexity": {"enum": ["CONVEX", "CONCAVE"]},
                    },
                },
            },
        },
        "state_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "x1": {"type": "number"},
                "x2": {"type": "number"},
                "lambda": {"type": "number", "minimum": 0, "maximum": 1},
            },
        },
        "event_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["event", "key", "value"],
            "properties": {
                "event": {"const": "ADJUST_SLIDER"},
                "key": {"enum": ["x1", "x2", "lambda"]},
                "value": {"type": "number"},
            },
        },
        "output_schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "f_of_mean": {"type": "number"},
                "mean_of_f": {"type": "number"},
                "inequality_holds": {"type": "boolean"},
            },
        },
        "allowed_controls": ["REAL_SLIDER", "PROBABILITY_SLIDER"],
        "allowed_icons": ["GRAPH"],
    },
}

MARKOV_STATES = [{"id": "A", "label": "Heads streak"}, {"id": "B", "label": "Tails streak"}]
MARKOV_TRANSITIONS = [
    {"from": "A", "to": "A", "p": "1/4"},
    {"from": "A", "to": "B", "p": "3/4"},
    {"from": "B", "to": "A", "p": "1/4"},
    {"from": "B", "to": "B", "p": "3/4"},
]

INTERACTION_SEEDS = [
    {
        "canonical_code": "INT-MARKOV-STATE-GRAPH-V1",
        "template_key": "STATE_GRAPH_EXPLORER_V1",
        "title": "Two-state coin-streak model",
        "instance_config": {"states": MARKOV_STATES, "transitions": MARKOV_TRANSITIONS},
        "learning_objective": "Describe the possible transitions between the two streak states.",
        "success_criteria": {
            "type": "EXPLORATION",
            "description": "Visit both states and follow every transition at least once.",
        },
    },
    {
        "canonical_code": "INT-MARKOV-TRANSITION-MATRIX-V1",
        "template_key": "TRANSITION_MATRIX_EDITOR_V1",
        "title": "Transition matrix for the coin-streak model",
        "instance_config": {"states": MARKOV_STATES, "transitions": MARKOV_TRANSITIONS},
        "learning_objective": "Connect the state graph's probabilities to a transition matrix.",
        "success_criteria": {"type": "ROW_SUM_CHECK", "target": 1.0, "tolerance": 1e-6},
    },
    {
        "canonical_code": "INT-MARKOV-RECURRENCE-V1",
        "template_key": "RECURRENCE_EXPLORER_V1",
        "title": "Streak-probability recurrence",
        "instance_config": {
            "recurrence": "p[n+1]=0.5*(1-p[n])",
            "initial": "p[0]=1",
            "fixed_point": "1/3",
        },
        "learning_objective": "Follow the recurrence toward its fixed point.",
        "success_criteria": {"type": "SEQUENCE_CONVERGENCE", "target": "1/3"},
    },
    {
        "canonical_code": "INT-VIETA-ROOTS-V1",
        "template_key": "POLYNOMIAL_ROOT_COEFFICIENT_EXPLORER_V1",
        "title": "Roots and coefficients",
        "instance_config": {
            "controls": {
                "r1": {"control": "REAL_SLIDER", "min": -5, "max": 5, "step": 0.1, "initial": 1},
                "r2": {"control": "REAL_SLIDER", "min": -5, "max": 5, "step": 0.1, "initial": 2},
                "r3": {"control": "REAL_SLIDER", "min": -5, "max": 5, "step": 0.1, "initial": -3},
            }
        },
        "learning_objective": "Map three roots to the elementary symmetric sums (Vieta's formulas).",
        "success_criteria": {
            "type": "COEFFICIENT_MATCH",
            "description": "Match e1, e2, e3 to the monic cubic's coefficients.",
        },
    },
    {
        "canonical_code": "INT-JENSEN-CONVEXITY-V1",
        "template_key": "FUNCTION_GRAPH_EXPLORER_V1",
        "title": "Convexity and Jensen's inequality",
        "instance_config": {
            "controls": {
                "x1": {"control": "REAL_SLIDER", "min": -4, "max": 4, "step": 0.1, "initial": -2},
                "x2": {"control": "REAL_SLIDER", "min": -4, "max": 4, "step": 0.1, "initial": 3},
                "lambda": {"control": "PROBABILITY_SLIDER", "min": 0, "max": 1, "step": 0.01, "initial": 0.4},
            },
            "function": {"expression": "x^2", "convexity": "CONVEX"},
        },
        "learning_objective": "Connect the convexity of x^2 to the direction of Jensen's inequality.",
        "success_criteria": {"type": "INEQUALITY_DIRECTION", "expected": "f(E[X]) <= E[f(X)]"},
    },
]

COURSE_SEEDS = [
    {
        "canonical_code": "MC-MARKOV-STREAKS",
        "title": "Coin-streak Markov chains",
        "description": "Model a coin-streak process as a two-state Markov chain: explore the "
        "state graph, read off the transition matrix, and watch the streak "
        "probability converge under the recurrence it implies.",
        "target": ("CONCEPT", "prob-markov"),
        "learning_objectives": [
            "Represent a repeated process as a finite Markov chain.",
            "Read transition probabilities directly from a state graph or matrix.",
            "Recognize when a recurrence converges to a fixed point.",
        ],
        "interactions": [
            "INT-MARKOV-STATE-GRAPH-V1",
            "INT-MARKOV-TRANSITION-MATRIX-V1",
            "INT-MARKOV-RECURRENCE-V1",
        ],
        "state": {
            "key": "EXPLORE",
            "title": "Explore the coin-streak chain",
            "objective": "See the same Markov chain as a graph, a matrix, and a recurrence.",
            "instruction": "Compare the state graph, the transition matrix, and the recurrence — "
            "they all describe the same process.",
        },
    },
    {
        "canonical_code": "MC-VIETA-FORMULAS",
        "title": "Vieta's formulas",
        "description": "Drag three real roots and watch the elementary symmetric sums — and "
        "the monic cubic they define — update live.",
        "target": ("CONCEPT", "alg-vieta"),
        "learning_objectives": [
            "State Vieta's formulas for a monic cubic in terms of its roots.",
            "Compute e1, e2, e3 from three chosen roots.",
        ],
        "interactions": ["INT-VIETA-ROOTS-V1"],
        "state": {
            "key": "EXPLORE",
            "title": "Explore roots and coefficients",
            "objective": "Connect root choices to the resulting cubic's coefficients.",
            "instruction": "Move each root slider and watch the symmetric sums and the cubic "
            "update together.",
        },
    },
    {
        "canonical_code": "MC-JENSEN-INEQUALITY",
        "title": "Jensen's inequality",
        "description": "Compare f(weighted mean) against the weighted mean of f for the convex "
        "function x^2, and see why convexity fixes the inequality's direction.",
        "target": ("TECHNIQUE", "ineq-jensen"),
        "learning_objectives": [
            "State Jensen's inequality for a convex function.",
            "Explain why the chord lies above the curve for a convex function.",
        ],
        "interactions": ["INT-JENSEN-CONVEXITY-V1"],
        "state": {
            "key": "EXPLORE",
            "title": "Explore convexity and Jensen's inequality",
            "objective": "See why f(E[X]) <= E[f(X)] holds for a convex function.",
            "instruction": "Move x1, x2 and the weight lambda and compare the curve point to "
            "the chord point.",
        },
    },
]


def _schema_hash(payload: dict) -> str:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return f"schema:{digest[:32]}"


def ensure_template_version_published(conn, template_key: str) -> str:
    row = conn.execute(
        text("""
        SELECT v.interaction_template_version_id, v.status
        FROM visual.interaction_template_version v
        JOIN visual.interaction_template t USING (interaction_template_id)
        WHERE t.template_key = :key AND v.version = 1
    """),
        {"key": template_key},
    ).mappings().one()
    version_id = str(row["interaction_template_version_id"])
    if row["status"] == "PUBLISHED":
        return version_id
    schema = TEMPLATE_SCHEMAS[template_key]
    conn.execute(
        text("""
        UPDATE visual.interaction_template_version
        SET input_schema=CAST(:input AS jsonb), state_schema=CAST(:state AS jsonb),
            event_schema=CAST(:event AS jsonb), output_schema=CAST(:output AS jsonb),
            allowed_controls=CAST(:controls AS jsonb), allowed_icons=CAST(:icons AS jsonb),
            accessibility_policy=CAST(:a11y AS jsonb), content_hash=:hash
        WHERE interaction_template_version_id=:id
    """),
        {
            "id": version_id,
            "input": json.dumps(schema["input_schema"]),
            "state": json.dumps(schema["state_schema"]),
            "event": json.dumps(schema["event_schema"]),
            "output": json.dumps(schema["output_schema"]),
            "controls": json.dumps(schema["allowed_controls"]),
            "icons": json.dumps(schema["allowed_icons"]),
            "a11y": json.dumps(ACCESSIBILITY_BASE),
            "hash": _schema_hash(schema),
        },
    )
    errors = interaction_validators.validate_interaction_template_version(conn, version_id)
    if errors:
        raise RuntimeError(f"{template_key} template version failed validation: {errors}")
    conn.execute(
        text("""
        UPDATE visual.interaction_template_version
        SET status='PUBLISHED', published_at=now(), reviewed_by=:author
        WHERE interaction_template_version_id=:id AND status IN ('DRAFT','REVIEWED')
    """),
        {"id": version_id, "author": SEED_AUTHOR},
    )
    return version_id


def ensure_interaction_instance(conn, seed: dict, version_id: str) -> str:
    existing = conn.execute(
        text("SELECT interaction_instance_id FROM visual.interaction_instance WHERE canonical_code=:code"),
        {"code": seed["canonical_code"]},
    ).scalar_one_or_none()
    if existing is not None:
        return str(existing)
    content_hash = _schema_hash({"config": seed["instance_config"], "objective": seed["learning_objective"]})
    instance_id = conn.execute(
        text("""
        INSERT INTO visual.interaction_instance
            (interaction_template_version_id, canonical_code, title, instance_config,
             learning_objective, success_criteria, content_hash, created_by)
        VALUES (:version, :code, :title, CAST(:config AS jsonb),
                :objective, CAST(:criteria AS jsonb), :hash, :author)
        RETURNING interaction_instance_id
    """),
        {
            "version": version_id,
            "code": seed["canonical_code"],
            "title": seed["title"],
            "config": json.dumps(seed["instance_config"]),
            "objective": seed["learning_objective"],
            "criteria": json.dumps(seed["success_criteria"]),
            "hash": content_hash,
            "author": SEED_AUTHOR,
        },
    ).scalar_one()
    errors = interaction_validators.validate_interaction_instance(conn, str(instance_id))
    if errors:
        raise RuntimeError(f"{seed['canonical_code']} instance failed validation: {errors}")
    conn.execute(
        text("""
        UPDATE visual.interaction_instance
        SET review_status='APPROVED', approved_by=:author, approved_at=now()
        WHERE interaction_instance_id=:id
    """),
        {"id": instance_id, "author": SEED_AUTHOR},
    )
    return str(instance_id)


def _target_id(conn, target_type: str, slug: str) -> str:
    table, id_column = svc.TARGETS[target_type]
    return str(
        conn.execute(
            text(f"SELECT {id_column} FROM {table} WHERE slug=:slug"), {"slug": slug}
        ).scalar_one()
    )


def ensure_course(conn, seed: dict, instance_ids: dict[str, str]) -> dict:
    existing = conn.execute(
        text("SELECT micro_course_id FROM pedagogy.micro_course WHERE canonical_code=:code"),
        {"code": seed["canonical_code"]},
    ).scalar_one_or_none()
    if existing is not None:
        return {"canonical_code": seed["canonical_code"], "status": "ALREADY_SEEDED"}

    target_type, slug = seed["target"]
    target_id = _target_id(conn, target_type, slug)
    svc.create_course(
        conn,
        seed["canonical_code"],
        seed["title"],
        SEED_AUTHOR,
        [{"target_type": target_type, "target_id": target_id, "role": "PRIMARY"}],
        description=seed["description"],
        estimated_minutes=8,
        metadata={"collection": "reference-examples", "source": "seed_reference_courses"},
    )
    release_id = svc.create_release(conn, seed["canonical_code"], SEED_AUTHOR)
    conn.execute(
        text("""
        UPDATE pedagogy.micro_course_release
        SET learning_objectives=CAST(:objectives AS jsonb)
        WHERE release_id=:id
    """),
        {"id": release_id, "objectives": json.dumps(seed["learning_objectives"])},
    )
    state = seed["state"]
    state_id = svc.add_state(
        conn,
        release_id,
        state["key"],
        0,
        "VISUAL",
        state["title"],
        objective=state["objective"],
        student_instruction=state["instruction"],
    )
    for ordinal, interaction_code in enumerate(seed["interactions"]):
        svc.attach_interaction(conn, state_id, instance_ids[interaction_code], ordinal)

    errors = svc.validate_release(conn, release_id)
    if errors:
        raise RuntimeError(f"{seed['canonical_code']} validate_release failed: {errors}")
    review = svc.review_release(conn, release_id, "APPROVED", SEED_AUTHOR, note="Reference example seed.")
    if review["status"] != "APPROVED":
        raise RuntimeError(f"{seed['canonical_code']} review_release failed: {review}")
    publish = svc.publish_release(conn, release_id, SEED_AUTHOR)
    if publish["status"] != "PUBLISHED":
        raise RuntimeError(f"{seed['canonical_code']} publish_release failed: {publish}")
    return {
        "canonical_code": seed["canonical_code"],
        "status": "PUBLISHED",
        "release_id": release_id,
        "content_hash": publish["content_hash"],
    }


def main() -> None:
    report: dict = {"templates": {}, "interactions": {}, "courses": []}
    with engine.begin() as conn:
        report["catalog"] = interaction_catalog.load_all(conn)
        version_ids = {
            key: ensure_template_version_published(conn, key) for key in TEMPLATE_SCHEMAS
        }
        report["templates"] = version_ids
        instance_ids = {
            seed["canonical_code"]: ensure_interaction_instance(
                conn, seed, version_ids[seed["template_key"]]
            )
            for seed in INTERACTION_SEEDS
        }
        report["interactions"] = instance_ids
        for seed in COURSE_SEEDS:
            report["courses"].append(ensure_course(conn, seed, instance_ids))
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
