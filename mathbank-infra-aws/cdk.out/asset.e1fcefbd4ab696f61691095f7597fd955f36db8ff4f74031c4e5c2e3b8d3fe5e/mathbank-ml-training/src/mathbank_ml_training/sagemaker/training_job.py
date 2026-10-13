"""SageMaker Training job wrapper (requirements/54 §4 phase 2)."""
from __future__ import annotations


def build_training_job_config(*, role_arn: str, image_uri: str, model_family: str,
                                 dataset_s3_uri: str, hyperparameters: dict) -> dict:
    """TODO (requirements/54 §4 phase 2): implement using `sagemaker.estimator.Estimator`
    (or a framework-specific estimator once a model library is chosen — requirements/55
    §6 deliberately defers that choice). On completion, must call
    registry.model_registry_client.record_training_run() — not implemented here either,
    see that module's own TODOs."""
    raise NotImplementedError("requirements/54 §4 phase 2 — SageMaker Training job")
