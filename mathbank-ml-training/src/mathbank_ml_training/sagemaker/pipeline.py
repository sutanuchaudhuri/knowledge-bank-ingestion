"""SageMaker Pipeline: chains EXTRACT -> ... -> REGISTER as one pipeline
(requirements/54 §4 phase 3, requirements/13 §1's full stage list)."""
from __future__ import annotations


def build_pipeline(*, pipeline_name: str, role_arn: str) -> None:
    """TODO (requirements/54 §4 phase 3): implement using `sagemaker.workflow.pipeline.
    Pipeline`, chaining processing_job.py + training_job.py steps plus an evaluation/
    registration step. Do not start this phase before phases 1-2 are both working
    independently — a pipeline that chains two not-yet-working steps just hides two
    separate problems behind one failure."""
    raise NotImplementedError("requirements/54 §4 phase 3 — SageMaker Pipeline")
