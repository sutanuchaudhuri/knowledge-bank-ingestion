"""Deterministic interaction runtime: semantic-event evaluation, misconception
evidence accumulation, and feedback-ladder selection
(requirements/41_INTERACTION_TEMPLATE_LIBRARY.md ITL-6/7/8/9).

Evaluation is template-specific and NEVER calls an LLM to decide correctness
(ITL-6). This module currently implements one evaluator —
TRANSITION_MATRIX_EDITOR_V1's row-submission check — as the proof-of-concept
required by the Markov golden test (ITL-18); additional template evaluators
are added the same way: a pure function of the submitted payload, no model
call, returning an outcome and (if wrong) a declared error_signature.
"""

from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy import text

ROW_SUM_TOLERANCE = 1e-6
# A single wrong answer only adds evidence; the misconception is "confirmed"
# (fixed intervention launched) only once accumulated confidence crosses this.
CONFIRMATION_THRESHOLD = 0.80


def evaluate_transition_matrix_row(row_values: list[float]) -> dict:
    """Deterministic check for one submitted transition-matrix row. Mirrors the
    Markov golden test's ROW_SUM_INVALID / NEGATIVE_PROBABILITY signatures."""
    if any(value < 0 for value in row_values):
        return {
            "outcome": "ERROR",
            "error_signature": "NEGATIVE_PROBABILITY",
            "detail": {"row": row_values},
        }
    total = sum(row_values)
    if abs(total - 1.0) > ROW_SUM_TOLERANCE:
        return {
            "outcome": "ERROR",
            "error_signature": "ROW_SUM_INVALID",
            "detail": {"row": row_values, "sum": total},
        }
    return {"outcome": "CORRECT", "error_signature": None, "detail": {"row": row_values}}


EVALUATORS = {
    "TRANSITION_MATRIX_EDITOR_V1": evaluate_transition_matrix_row,
}


def record_interaction_event(
    conn,
    student_id: str,
    interaction_instance_id: str,
    semantic_action: str,
    action_payload: dict,
    evaluation: dict,
    enrollment_id: str | None = None,
    course_state_id: str | None = None,
) -> str:
    return conn.execute(
        text("""
        INSERT INTO learner.interaction_event
            (student_id, enrollment_id, course_state_id, interaction_instance_id,
             event_type, semantic_action, action_payload, evaluation_outcome, error_signature)
        VALUES (:student, :enrollment, :state, :instance, 'SUBMIT', :action,
                CAST(:payload AS jsonb), :outcome, :signature)
        RETURNING interaction_event_id::text
    """),
        {
            "student": student_id,
            "enrollment": enrollment_id,
            "state": course_state_id,
            "instance": interaction_instance_id,
            "action": semantic_action,
            "payload": json.dumps(action_payload),
            "outcome": evaluation["outcome"],
            "signature": evaluation.get("error_signature"),
        },
    ).scalar_one()


def apply_evidence(
    conn,
    student_id: str,
    interaction_event_id: str,
    interaction_template_version_id: str,
    semantic_action: str,
    error_signature: str,
) -> dict | None:
    """Looks up the matching, APPROVED misconception_evidence_rule for this
    template version + semantic_action + error_signature, appends one
    learner.misconception_evidence row, and reports whether the misconception
    is now CONFIRMED (crossed CONFIRMATION_THRESHOLD) — never on a single
    wrong answer alone unless the rule's own weight already clears it."""
    rule = (
        conn.execute(
            text("""
        SELECT evidence_rule_id, misconception_id, evidence_weight, requires_probe,
               diagnostic_learning_item_id, feedback_template_id, intervention_id
        FROM pedagogy.misconception_evidence_rule
        WHERE interaction_template_version_id = :version
          AND semantic_action = :action AND error_signature = :signature
          AND review_status = 'APPROVED'
        LIMIT 1
    """),
            {
                "version": interaction_template_version_id,
                "action": semantic_action,
                "signature": error_signature,
            },
        )
        .mappings()
        .first()
    )
    if rule is None:
        return None

    prior = conn.execute(
        text("""
        SELECT confidence_after FROM learner.misconception_evidence
        WHERE student_id = :student AND misconception_id = :misconception
        ORDER BY created_at DESC LIMIT 1
    """),
        {"student": student_id, "misconception": rule["misconception_id"]},
    ).scalar()
    before = float(prior) if prior is not None else 0.0
    weight = float(rule["evidence_weight"])
    after = max(0.0, min(1.0, before + weight))

    conn.execute(
        text("""
        INSERT INTO learner.misconception_evidence
            (student_id, interaction_event_id, misconception_id, evidence_type,
             evidence_weight, confidence_before, confidence_after)
        VALUES (:student, :event, :misconception, 'OBSERVED_ERROR', :weight, :before, :after)
    """),
        {
            "student": student_id,
            "event": interaction_event_id,
            "misconception": rule["misconception_id"],
            "weight": Decimal(str(weight)),
            "before": Decimal(str(before)),
            "after": Decimal(str(after)),
        },
    )
    return {
        "misconception_id": str(rule["misconception_id"]),
        "before": before,
        "delta": weight,
        "after": after,
        "confirmed": after >= CONFIRMATION_THRESHOLD,
        "requires_probe": rule["requires_probe"],
        "diagnostic_learning_item_id": rule["diagnostic_learning_item_id"],
        "feedback_template_id": str(rule["feedback_template_id"])
        if rule["feedback_template_id"]
        else None,
        "intervention_id": str(rule["intervention_id"]) if rule["intervention_id"] else None,
    }


def select_feedback(
    conn, feedback_policy_id: str | None, attempt_number: int, error_signature: str | None
) -> dict:
    """Walks a feedback_policy's staged ladder (policy_json['stages']) and
    returns the first stage whose declared attempt number has been reached;
    falls back to a generic ladder position if no policy is attached."""
    default_ladder = [
        "neutral structural clue",
        "focused conceptual clue",
        "diagnostic probe",
        "confirmed misconception",
        "fixed remediation",
        "retry original interaction",
        "later transfer verification",
    ]
    stage_index = min(attempt_number - 1, len(default_ladder) - 1) if attempt_number > 0 else 0
    result = {
        "stage": default_ladder[stage_index],
        "feedback_template_id": None,
        "policy_json": None,
    }
    if feedback_policy_id is None:
        return result
    policy = conn.execute(
        text("SELECT policy_json FROM pedagogy.feedback_policy WHERE feedback_policy_id = :id"),
        {"id": feedback_policy_id},
    ).scalar_one_or_none()
    if policy is None:
        return result
    stages = policy.get("stages", [])
    if 0 <= stage_index < len(stages):
        result["feedback_template_id"] = stages[stage_index].get("feedback")
        result["policy_json"] = stages[stage_index]
    return result
