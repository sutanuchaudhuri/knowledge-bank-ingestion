"""AWS Lambda entrypoint for `mathbank-ml-inference` (requirements/62 §4, requirements/63).

A thin, additive wrapper — zero changes to `main.py` or any route/service code. Mirrors
`mathbank-rest/src/mathbank_rest/lambda_handler.py`'s pattern exactly: secrets are
fetched from SSM Parameter Store at cold start and written into `os.environ` *before*
`mathbank_ml_inference.main` is imported, so `Settings()` (pydantic-settings, case-
insensitive env var matching) picks them up the same way it would from a real shell
environment or `.env` file — no `.env` file is ever present in this image (see
GOTCHAS.md #43 for why that must never be the source of secrets in a Lambda image).
"""
from __future__ import annotations

import os


def _load_secrets_from_ssm() -> None:
    prefix = os.environ.pop("MATHBANK_SSM_PREFIX", "")
    secret_map = os.environ.pop("MATHBANK_SECRET_MAP", "")
    if not prefix or not secret_map:
        return  # local/non-Lambda run — nothing to do
    import boto3

    client = boto3.client("ssm")
    for pair in secret_map.split(","):
        ssm_suffix, _, target_env_var = pair.partition("=")
        if not ssm_suffix or not target_env_var:
            continue
        name = f"{prefix}/{ssm_suffix}"
        resp = client.get_parameter(Name=name, WithDecryption=True)
        os.environ[target_env_var] = resp["Parameter"]["Value"]


_load_secrets_from_ssm()

from mangum import Mangum  # noqa: E402 — must follow the secrets load above

from mathbank_ml_inference.main import app  # noqa: E402 — ditto

handler = Mangum(app)
