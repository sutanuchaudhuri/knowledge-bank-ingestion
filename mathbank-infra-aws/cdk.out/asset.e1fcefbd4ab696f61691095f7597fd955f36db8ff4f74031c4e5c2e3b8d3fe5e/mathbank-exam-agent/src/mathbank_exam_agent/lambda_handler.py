"""AWS Lambda entrypoint for `mathbank-exam-agent` (requirements/64, requirements/63's
established pattern). A thin, additive wrapper — zero changes to `main.py` or any
existing route/service code. Wraps the exact same FastAPI `app` already used by local
Uvicorn/pytest in Mangum's ASGI-to-Lambda-event adapter, so local dev, tests and the
Lambda deployment all run the identical application code path.

Secrets are fetched from SSM Parameter Store at cold start (once per execution
environment, not per-request) and written into `os.environ` *before*
`mathbank_exam_agent.main` is imported — see `mathbank-rest`'s own `lambda_handler.py`
for the full rationale (a CloudFormation dynamic reference directly in
`Environment.Variables` is not supported for `AWS::Lambda::Function`).

Unlike `mathbank-rest`, this service's Cognito admin-API calls (`cognito_auth.py`) need
no explicit `AWS_PROFILE`/`AWS_DEFAULT_REGION` here — Lambda's execution role already
supplies ambient credentials and `AWS_REGION` to every boto3 client with zero extra
wiring (the "must export AWS_DEFAULT_REGION" gotcha documented in the project README is
a *local dev only* concern, specific to the `aws-sutanu-admin` SSO profile).
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

from mathbank_exam_agent.main import app  # noqa: E402 — ditto

handler = Mangum(app)
