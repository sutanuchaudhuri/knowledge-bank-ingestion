"""CDK stack: `mathbank-agent` as a Lambda container image + Function URL
(requirements/62 §4, requirements/63). Unlike `mathbank-rest`'s stack, this service is
copied whole into `/var/task` rather than pip-installed (see Dockerfile.lambda's own
comment for why that's the correct, safer choice for this specific service's layout).
"""
from __future__ import annotations

from pathlib import Path

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from .ssm_config import grant_and_map_secrets, plain_env_vars

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE = "mathbank-agent"
SERVICE_DIR = REPO_ROOT / SERVICE

PLAIN_ENV_KEYS = [
    "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_SSLMODE",
    "MATHBANK_AGENT_MODEL", "MATHBANK_AGENT_DEFAULT_ROLE",
    "NEON_AI_GATEWAY_BASE_URL",
]

SECRET_KEY_TARGETS = {
    "POSTGRES_PASSWORD": "POSTGRES_PASSWORD",
    "OPENAI_API_KEY": "OPENAI_API_KEY",
    "NEON_AI_GATEWAY_TOKEN": "NEON_AI_GATEWAY_TOKEN",
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


class AgentServiceStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, *, rest_function_url: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        env_values = _parse_env_file(REPO_ROOT / SERVICE / ".env")
        environment = plain_env_vars(env_values, PLAIN_ENV_KEYS)
        # Points the deployed agent at the already-deployed mathbank-rest Lambda, not
        # localhost — the one piece of real cross-service wiring this stack needs.
        environment["MATHBANK_REST_BASE_URL"] = rest_function_url.rstrip("/")

        fn = lambda_.DockerImageFunction(
            self, "AgentFunction",
            function_name="mathbank-agent",
            code=lambda_.DockerImageCode.from_image_asset(
                # Scoped to this service's own directory, not REPO_ROOT — mathbank-agent
                # has no sibling-package dependency (unlike mathbank-rest), so there is
                # no need to expose the repo root (and its mathbank-infra-aws/cdk.out)
                # as the build context at all (GOTCHAS.md #44 — avoids the recursive
                # self-copy class of bug entirely rather than fighting CDK's `exclude`
                # glob matching against a directory that contains cdk.out).
                directory=str(SERVICE_DIR),
                file="Dockerfile.lambda",
                platform=ecr_assets.Platform.LINUX_ARM64,
            ),
            architecture=lambda_.Architecture.ARM_64,
            # Google ADK + litellm + google-genai's import graph is heavier than
            # mathbank-rest's; confirmed live locally needing meaningfully more memory
            # headroom than the REST service's 1024 MB.
            memory_size=2048,
            timeout=Duration.seconds(60),
            environment=environment,
        )

        present_secrets = {k: v for k, v in SECRET_KEY_TARGETS.items() if env_values.get(k)}
        secret_env = grant_and_map_secrets(self, fn, SERVICE, present_secrets)
        for key, value in secret_env.items():
            fn.add_environment(key, value)

        url = fn.add_function_url(auth_type=lambda_.FunctionUrlAuthType.NONE)
        self.function_url = url.url

        CfnOutput(self, "AgentFunctionUrl", value=url.url)
