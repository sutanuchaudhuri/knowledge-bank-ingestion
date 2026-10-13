"""SageMaker Processing job wrapper (requirements/54 §4 phase 1).

Wraps extract/features/labels code (this same package) as a SageMaker Processing job,
reading from a Postgres snapshot exported to S3/Parquet rather than hitting the live OLTP
database from inside AWS (requirements/13 §2 "do not train from live mutable graph state
without a recorded projection watermark" applies equally to Postgres snapshots here).
"""
from __future__ import annotations


def build_processing_job_config(*, role_arn: str, image_uri: str, input_s3_uri: str,
                                   output_s3_uri: str) -> dict:
    """TODO (requirements/54 §4 phase 1): implement using `sagemaker.processing.
    ScriptProcessor` or `FrameworkProcessor`. Not implemented in this pass — phase 0
    (local-only) must be working first; do not start phase 1 before phase 0's
    extract/features/labels functions have real logic (see requirements/55 §2/§4/§5's
    own NotImplementedError stubs)."""
    raise NotImplementedError("requirements/54 §4 phase 1 — SageMaker Processing job")


def run_local_equivalent(*, student_cohort_query_hash: str) -> dict:
    """The phase-0 local stand-in for the above — runs the same feature/label code
    directly against the dev Postgres instance, no AWS involved. TODO: implement once
    extract/features/labels have real logic; this function's job is purely to call
    through to them with the same inputs the SageMaker job would eventually receive, so
    switching between local and SageMaker execution later is a config change, not a code
    rewrite."""
    raise NotImplementedError("requirements/54 §4 phase 0 — local equivalent run")
