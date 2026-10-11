"""Writes to `ml.training_run` / `ml.model_registry` (requirements/02 §1,
requirements/13 §5, requirements/55 §2 REGISTER stage).

requirements/13 §5: "MathBank registry owns business approval + deployment stage.
External registry (MLflow or equivalent) may own binaries/metrics/artifacts." This module
only talks to the MathBank-owned Postgres `ml.*` tables — it does not implement an MLflow
client (TODO: decide whether MLflow is actually adopted before adding that dependency;
doc 13 says "can use MLflow or equivalent", not "must").
"""
from __future__ import annotations

from mathbank_ml_training.contracts import ModelRegistryEntry, TrainingRun


def record_training_run(run: TrainingRun) -> None:
    """TODO: implement — INSERT into `ml.training_run`. Requires the `ml` schema
    migration to exist first (see requirements/54 §7 gotcha: not yet created in this
    pass, deliberately deferred until contracts.py is considered final)."""
    raise NotImplementedError("requirements/55 §2 REGISTER stage — training run")


def register_model(entry: ModelRegistryEntry) -> None:
    """TODO: implement — INSERT/UPSERT into `ml.model_registry`, status PENDING. Approval
    (PENDING -> APPROVED/REJECTED) is a separate, explicit admin action — never set
    approval_status=APPROVED from inside this function."""
    raise NotImplementedError("requirements/55 §2 REGISTER stage — model registration")


def get_approved_model(model_family: str) -> ModelRegistryEntry | None:
    """Used by mathbank-ml-inference to find the currently-approved model for a family.

    TODO: implement. Must only ever return a row with approval_status == "APPROVED" and
    deployment_stage in {"PRODUCTION", "CANARY", "SHADOW"} — never a PENDING/REJECTED
    entry, even accidentally."""
    raise NotImplementedError("requirements/55 §2 REGISTER stage — approved model lookup")
