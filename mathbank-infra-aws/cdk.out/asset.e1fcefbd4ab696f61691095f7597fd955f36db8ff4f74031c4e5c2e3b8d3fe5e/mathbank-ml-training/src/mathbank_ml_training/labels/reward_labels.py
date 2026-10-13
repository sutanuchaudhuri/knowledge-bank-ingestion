"""Multi-component tutor-action reward label (requirements/11 §4/§5, requirements/55 §5).

Never collapse to one scalar before storage (requirements/11 §5) — always return
mathbank_ml_training.contracts.RewardComponents, never a bare float.
"""
from __future__ import annotations

from mathbank_ml_training.contracts import RewardComponents


def label_tutor_reward(turn_outcome: dict) -> RewardComponents:
    """Computes the multi-component reward from requirements/11 §4's worked example:

    +1.0 correct without answer reveal
    +0.7 delayed transfer success
    +0.5 misconception probe resolved
    +0.3 correct after low-level hint
    +0.2 productive self-explanation
    -0.2 excessive time
    -0.3 repeated unproductive hint
    -0.5 abandonment
    -0.8 answer reveal before policy allowed
    -1.0 unsafe/unapproved action

    TODO: these weights are requirements/11 §4's own illustrative example, not a
    finalized reward function — do not treat them as final without an explicit pedagogy
    review. Implement the component computations first; keep the weights in one place
    (a dict constant at the top of this module, not scattered through the function body)
    so they're easy to revise without touching the computation logic itself.
    """
    raise NotImplementedError("requirements/55 §5 — tutor reward label")
