"""Cluster validation gate (requirements/08 §4, requirements/58 §2).

None of these may be skipped before serving a cluster assignment to an admin
(services/cohort.py in mathbank-ml-inference is documented to refuse to serve clusters
that haven't passed all four — once these functions and that refusal logic both exist).
"""
from __future__ import annotations


def check_bootstrap_stability(cluster_assignments: list[dict], *, n_bootstrap: int = 100) -> bool:
    """TODO: implement — re-cluster on bootstrap resamples, check assignment agreement."""
    raise NotImplementedError("requirements/55/58 — cluster validation: bootstrap stability")


def check_interpretable_feature_differences(cluster_assignments: list[dict], features: list[dict]) -> bool:
    """TODO: implement — clusters must differ on named, explainable features, not just
    an opaque distance metric."""
    raise NotImplementedError("requirements/55/58 — cluster validation: interpretability")


def check_minimum_cluster_size(cluster_assignments: list[dict], *, min_size: int = 10) -> bool:
    """TODO: implement — trivial once cluster_assignments exist; included as its own
    named check so a validation report can show exactly which gate failed."""
    raise NotImplementedError("requirements/55/58 — cluster validation: minimum size")


def check_time_window_consistency(cluster_assignments_t0: list[dict], cluster_assignments_t1: list[dict]) -> bool:
    """TODO: implement — clusters should be reasonably stable across adjacent time
    windows, not reshuffled every run."""
    raise NotImplementedError("requirements/55/58 — cluster validation: time consistency")
