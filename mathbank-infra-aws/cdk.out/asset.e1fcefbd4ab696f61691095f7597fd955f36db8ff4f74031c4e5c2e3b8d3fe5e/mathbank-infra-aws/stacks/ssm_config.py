"""Shared helpers for every service stack (requirements/62 §4, requirements/63).

Sensitive config is stored in SSM Parameter Store as `SecureString` parameters (the
default AWS-managed KMS key — no extra charge, unlike Secrets Manager's $0.40/secret/
month, consistent with doc 62's "minimum cost" goal).

**Not** resolved via a CloudFormation dynamic reference in the Lambda's
`Environment.Variables` — confirmed live that CloudFormation rejects that combination
(Validate rule E1027: "Dynamic reference ... to SSM secure strings can only be used in
resource properties", not `AWS::Lambda::Function`'s `Environment.Variables`). Instead,
the Lambda function itself fetches these values from SSM at cold start
(`lambda_handler.py`'s `_load_secrets_from_ssm`), using two plain (non-secret)
environment variables this module builds: `MATHBANK_SSM_PREFIX` (the parameter path
prefix) and `MATHBANK_SECRET_MAP` (`SSM_SUFFIX=TARGET_ENV_VAR` pairs, comma-separated) —
and the function's execution role is granted read-only access to exactly those
parameter ARNs, nothing broader.
"""
from __future__ import annotations

from aws_cdk import Stack
from aws_cdk import aws_iam as iam

SSM_PREFIX = "/mathbank/dev"

# Which `.env`-style keys are secrets (SSM SecureString, fetched by the Lambda at cold
# start) versus plain config (read straight from the local .env at synth time and
# written as literal Lambda environment variables — acceptable for non-sensitive values
# such as hostnames/ports in a personal, root-owned dev account's CloudFormation
# template). Keep this list in sync with any new sensitive key added to a service's .env.
SECRET_ENV_KEYS = {
    "POSTGRES_PASSWORD",
    "NEO4J_PASSWORD",
    "JWT_SECRET",
    "ADMIN_API_KEY",
    "OPENAI_API_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "NEON_AI_GATEWAY_TOKEN",
    "ELEVEN_API_KEY",
    "ADMIN_SESSION_SECRET",
    "ADMIN_LOGIN_PASSWORD",
    "COGNITO_CLIENT_SECRET",
}

# Set automatically by the Lambda runtime itself — attempting to set these as a
# user-supplied environment variable fails CDK synth outright (confirmed live:
# "AWS_REGION environment variable is reserved by the lambda runtime").
RESERVED_LAMBDA_ENV_KEYS = {
    "AWS_REGION", "AWS_DEFAULT_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN", "AWS_LAMBDA_FUNCTION_NAME", "AWS_EXECUTION_ENV",
}

# `from_image_asset(directory=REPO_ROOT, ...)` stages a copy of the build context under
# `mathbank-infra-aws/cdk.out/asset.<hash>/` *before* invoking docker. The root
# `.dockerignore` is not reliably honoured by this staging copy (confirmed live: a fresh,
# just-deleted `cdk.out/` still self-nested within a single synth run — CDK copied
# `mathbank-infra-aws/cdk.out/` into itself as it was being created, racing its own
# walk). Pass `exclude` explicitly to every `from_image_asset(directory=REPO_ROOT, ...)`
# call instead of relying on the implicit `.dockerignore` pickup — this list must also
# exclude anything containing real secrets (`.env`), mirroring the root `.dockerignore`.
DOCKER_ASSET_EXCLUDES = [
    "mathbank-infra-aws/cdk.out",
    "mathbank-infra-aws/cdk.out/**",
    "**/cdk.out",
    "**/cdk.out/**",
    ".git",
    ".git/**",
    "archive",
    "archive/**",
    "**/node_modules",
    "**/node_modules/**",
    "**/.next",
    "**/.next/**",
    "**/__pycache__",
    "**/__pycache__/**",
    "**/*.egg-info",
    "**/*.egg-info/**",
    "**/.venv",
    "**/.venv/**",
    "**/venv",
    "**/venv/**",
    "**/.pytest_cache",
    "**/.pytest_cache/**",
    "**/.ruff_cache",
    "**/.ruff_cache/**",
    "**/.env",
    "**/.env.*",
    "!**/.env.example",
    "mathbank-data-ingestion/data",
    "mathbank-data-ingestion/data/**",
    "mathbank-data-ingestion/data_textbook",
    "mathbank-data-ingestion/data_textbook/**",
]


def ssm_parameter_name(service: str, key: str) -> str:
    return f"{SSM_PREFIX}/{service}/{key}"


def plain_env_vars(env_values: dict[str, str], keys: list[str]) -> dict[str, str]:
    """Literal (non-secret) Lambda environment variables, straight from a parsed .env
    dict — only ever called with keys NOT in SECRET_ENV_KEYS, and silently skipping any
    Lambda-reserved key (the runtime already provides it; see RESERVED_LAMBDA_ENV_KEYS)."""
    result = {}
    for key in keys:
        if key in SECRET_ENV_KEYS:
            raise ValueError(f"{key} is a secret — use grant_and_map_secrets(), not plain_env_vars()")
        if key in RESERVED_LAMBDA_ENV_KEYS:
            continue
        value = env_values.get(key)
        if value is not None:
            result[key] = value
    return result


def grant_and_map_secrets(
    stack: Stack, fn, service: str, secret_to_target: dict[str, str],
) -> dict[str, str]:
    """Grants `fn`'s execution role `ssm:GetParameter` on exactly the given secrets'
    parameter ARNs, and returns the two plain env vars `lambda_handler.py` needs to fetch
    them at cold start. `secret_to_target` maps each `.env` key to the Lambda environment
    variable name it should end up under (identity for most; a renamed alias for the
    handful that collide with Lambda-reserved names, e.g. `AWS_SECRET_ACCESS_KEY` ->
    `MATHBANK_S3_SECRET_ACCESS_KEY`, see object_store.py)."""
    if not secret_to_target:
        return {}
    for key in secret_to_target:
        if key not in SECRET_ENV_KEYS:
            raise ValueError(f"{key} is not in SECRET_ENV_KEYS — add it there first")
    arns = [
        stack.format_arn(
            service="ssm", resource="parameter",
            resource_name=ssm_parameter_name(service, key).lstrip("/"),
        )
        for key in secret_to_target
    ]
    fn.add_to_role_policy(
        iam.PolicyStatement(actions=["ssm:GetParameter"], resources=arns)
    )
    secret_map = ",".join(f"{key}={target}" for key, target in secret_to_target.items())
    return {
        "MATHBANK_SSM_PREFIX": f"{SSM_PREFIX}/{service}",
        "MATHBANK_SECRET_MAP": secret_map,
    }
