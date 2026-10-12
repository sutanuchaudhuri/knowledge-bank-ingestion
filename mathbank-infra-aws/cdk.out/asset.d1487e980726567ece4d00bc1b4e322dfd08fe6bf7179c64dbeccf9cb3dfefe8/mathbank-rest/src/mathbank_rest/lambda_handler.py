"""AWS Lambda entrypoint for `mathbank-rest` (requirements/62 §4, requirements/63).

A thin, additive wrapper — zero changes to `main.py` or any existing route/service code.
Wraps the exact same FastAPI `app` already used by local Uvicorn/pytest in Mangum's
ASGI-to-Lambda-event adapter, so local dev, tests and the Lambda deployment all run the
identical application code path.

Secrets are fetched from SSM Parameter Store at cold start (once per execution
environment, not per-request) and written into `os.environ` *before* `mathbank_rest.main`
is imported — this is the standard AWS pattern for Lambda + SSM secrets. A
CloudFormation dynamic reference (`{{resolve:ssm-secure:...}}`) directly in the
function's `Environment.Variables`, which is what an earlier version of this stack
tried, is **not supported there** — confirmed live (CloudFormation Validate rule
E1027: "Dynamic reference ... can only be used in resource properties"), so the CDK
stack instead passes `MATHBANK_SECRET_MAP` (a plain, non-secret list of
`SSM_SUFFIX=TARGET_ENV_VAR` pairs) and grants this function's role `ssm:GetParameter` on
exactly those parameter ARNs; the actual values are never in the CloudFormation
template, console, or any CDK-synthesized asset — only in SSM and in this process's
memory after cold start.
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

from mathbank_rest.main import app  # noqa: E402 — ditto

handler = Mangum(app)
