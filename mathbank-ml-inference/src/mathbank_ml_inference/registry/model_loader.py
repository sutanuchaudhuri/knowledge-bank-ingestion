"""Loads approved model artifacts for serving (requirements/13 §12 "rollback",
requirements/56 §6).
"""
from __future__ import annotations


def load_approved_model(model_family: str):
    """TODO (requirements/56): fetch the approved `ml.model_registry` row for
    `model_family` (reusing mathbank-ml-training's registry.model_registry_client.
    get_approved_model — TODO: decide whether to import that package as a dependency or
    duplicate the one read-only query; importing is probably fine since this is a
    read-only consumer relationship, unlike the contracts duplication question) and
    deserialize the artifact from `ml_model_artifact_bucket`."""
    raise NotImplementedError("requirements/56 — model loading")


def rollback_to_version(model_family: str, target_version: str) -> None:
    """TODO (requirements/13 §12): "every inference response records model/policy
    version. Deployment system supports immediate rollback to prior approved version."
    Not implemented — no deployment automation exists yet (requirements/56 §6 lists this
    as explicitly deferred)."""
    raise NotImplementedError("requirements/56 §6 — rollback (deferred, not in this pass)")


def list_registry() -> list[dict]:
    """Backs `GET /v1/admin/ml/model-registry` (requirements/56 §2). TODO: implement."""
    raise NotImplementedError("requirements/56 §2 — model registry listing")


def list_training_runs() -> list[dict]:
    """Backs `GET /v1/admin/ml/training-runs` (requirements/56 §2). TODO: implement."""
    raise NotImplementedError("requirements/56 §2 — training run listing")
