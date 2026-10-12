"""Offline policy evaluation (requirements/11 §7/§8, requirements/55 §2 OFFLINE_EVAL
stage).

requirements/11 §7: "Before deployment use: direct method outcome model, inverse
propensity scoring when logging propensities exist, doubly robust estimate, replay where
deterministic compatibility allows." requirements/11 §8: "Prefer methods that avoid
out-of-distribution actions."
"""
from __future__ import annotations


def direct_method_estimate(trajectories: list[dict], candidate_policy) -> float:
    """TODO: implement. Trains an outcome model on logged (state, action, reward) and
    evaluates the candidate policy's expected reward under that model."""
    raise NotImplementedError("requirements/55 §2 OFFLINE_EVAL — direct method")


def inverse_propensity_score(trajectories: list[dict], candidate_policy) -> float:
    """TODO: implement. Requires the *logging* policy's action propensity to be stored
    on each trajectory (requirements/11 §7 "store logging probability of the chosen
    action") — confirm contracts.TutorTurn or a sibling field carries this before
    assuming it's available."""
    raise NotImplementedError("requirements/55 §2 OFFLINE_EVAL — IPS")


def doubly_robust_estimate(trajectories: list[dict], candidate_policy) -> float:
    """TODO: implement. Combines direct_method_estimate and inverse_propensity_score —
    implement both of those first."""
    raise NotImplementedError("requirements/55 §2 OFFLINE_EVAL — doubly robust")
