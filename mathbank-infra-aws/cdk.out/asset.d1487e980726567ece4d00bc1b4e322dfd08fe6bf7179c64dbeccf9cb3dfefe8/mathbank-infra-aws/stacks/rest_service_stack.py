"""CDK stack: `mathbank-rest` as a Lambda container image + Function URL
(requirements/62 §4, requirements/63). No VPC (Neon/AuraDB are public TLS endpoints —
confirmed in doc 62 §2/§9) and no API Gateway (a Function URL is the cheapest front door
for a single-function dev deployment — doc 62 §4.1).
"""
from __future__ import annotations

from pathlib import Path

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from .ssm_config import DOCKER_ASSET_EXCLUDES, grant_and_map_secrets, plain_env_vars

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE = "mathbank-rest"

# Non-secret config, read straight from the local .env and written as literal Lambda
# environment variables (see ssm_config.py's module docstring for the security
# rationale). AWS_REGION/AWS_ACCESS_KEY_ID are deliberately excluded — both are
# Lambda-reserved names (see object_store.py's MATHBANK_S3_* alias fix, requirements/63)
# and are set below instead, under their non-colliding alias names.
PLAIN_ENV_KEYS = [
    "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_SSLMODE",
    "NEO4J_URI", "NEO4J_USER",
    "NEON_AI_GATEWAY_BASE_URL",
    "MATHBANK_OBJECT_BUCKET", "MATHBANK_OBJECT_BACKEND", "MATHBANK_RUNTIME_AI_PROVIDER",
    "MANIM_STUDIO_BASE_URL",
]

# .env key -> Lambda env var name secrets are fetched into at cold start (identity for
# most; aliased where the real name collides with a Lambda-reserved variable).
SECRET_KEY_TARGETS = {
    "POSTGRES_PASSWORD": "POSTGRES_PASSWORD",
    "NEO4J_PASSWORD": "NEO4J_PASSWORD",
    "JWT_SECRET": "JWT_SECRET",
    "ADMIN_API_KEY": "ADMIN_API_KEY",
    "OPENAI_API_KEY": "OPENAI_API_KEY",
    "AWS_SECRET_ACCESS_KEY": "MATHBANK_S3_SECRET_ACCESS_KEY",
}


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"')
    return values


class RestServiceStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, region: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        env_values = _parse_env_file(REPO_ROOT / SERVICE / ".env")
        environment = plain_env_vars(env_values, PLAIN_ENV_KEYS)

        # Neon's S3-compatible storage endpoint/region, under the MATHBANK_S3_* alias
        # names object_store.py now checks first — never the bare AWS_* names, which
        # Lambda reserves for its own execution-role credentials/region.
        if env_values.get("AWS_ENDPOINT_URL_S3"):
            environment["MATHBANK_S3_ENDPOINT_URL"] = env_values["AWS_ENDPOINT_URL_S3"]
        if env_values.get("AWS_REGION"):
            environment["MATHBANK_S3_REGION"] = env_values["AWS_REGION"]
        if env_values.get("AWS_ACCESS_KEY_ID"):
            environment["MATHBANK_S3_ACCESS_KEY_ID"] = env_values["AWS_ACCESS_KEY_ID"]

        fn = lambda_.DockerImageFunction(
            self, "RestFunction",
            function_name="mathbank-rest",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=str(REPO_ROOT),
                file="mathbank-rest/Dockerfile.lambda",
                platform=ecr_assets.Platform.LINUX_ARM64,
                exclude=DOCKER_ASSET_EXCLUDES,
            ),
            architecture=lambda_.Architecture.ARM_64,
            memory_size=1024,
            # Lambda Function URLs carry no separate timeout cap of their own (unlike
            # API Gateway's 29s integration limit) — this is just a sensible app-level
            # ceiling for a typical request, well under Lambda's own 900s hard max.
            timeout=Duration.seconds(60),
            environment=environment,
        )

        # Secrets present in .env get fetched from SSM at cold start (lambda_handler.py)
        # — see ssm_config.py's module docstring for why this replaces a dynamic
        # reference directly in Environment.Variables.
        present_secrets = {k: v for k, v in SECRET_KEY_TARGETS.items() if env_values.get(k)}
        secret_env = grant_and_map_secrets(self, fn, SERVICE, present_secrets)
        for key, value in secret_env.items():
            fn.add_environment(key, value)

        url = fn.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,  # dev-only; the app has its own API-key gates
        )
        self.function_url = url.url

        CfnOutput(self, "RestFunctionUrl", value=url.url)
