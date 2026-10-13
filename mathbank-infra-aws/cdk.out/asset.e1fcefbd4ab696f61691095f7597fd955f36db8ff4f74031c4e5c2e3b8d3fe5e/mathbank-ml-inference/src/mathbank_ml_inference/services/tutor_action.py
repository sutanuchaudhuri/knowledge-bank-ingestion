"""Tutor-action scoring (requirements/11, requirements/14 §2/§8, requirements/56 §2).

requirements/11 §6 — action masks are applied by the CALLER (the production tutor,
mathbank-agent or whatever eventually calls this) before this service ever sees the
candidate action list. This module ranks among an already-filtered set; it must never
itself decide "which actions are allowed."
"""
from __future__ import annotations

from mathbank_ml_inference.contracts import (
    ScoreTutorActionsRequest,
    ScoreTutorActionsResponse,
    TutorPolicyStatusResponse,
)


def score_tutor_actions(request: ScoreTutorActionsRequest) -> ScoreTutorActionsResponse:
    """TODO (requirements/56 §2, requirements/11 §6): load the approved tutor_policy
    model (stage-appropriate — requirements/11 §1's maturity path), score
    `request.allowed_action_ids` only. Must refuse (raise, not silently ignore) if any
    action ID in the request isn't in the policy's known action vocabulary — never
    silently score an unknown action."""
    raise NotImplementedError("requirements/56 §2 — POST /v1/admin/ml/tutor-policy/score-actions")


def get_policy_status() -> TutorPolicyStatusResponse:
    """Backs `GET /v1/admin/ml/tutor-policy` (requirements/56 §2). TODO: implement,
    reading from registry.model_loader.list_registry() filtered to model_family==
    "tutor_policy"."""
    raise NotImplementedError("requirements/56 §2 — GET /v1/admin/ml/tutor-policy")
