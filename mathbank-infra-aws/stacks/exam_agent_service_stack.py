"""CDK stack: `mathbank-exam-agent` as a Lambda container image + Function URL
(requirements/64, following requirements/62/63's established pattern — see
`rest_service_stack.py`/`agent_service_stack.py` for the sibling precedents this
mirrors). Build context is this service's own directory — it has no sibling-package
dependency, unlike `mathbank-rest` (it only ever reaches `mathbank-rest` and
`mathbank-mcp-competitions` over HTTP/MCP, exactly like `mathbank-agent`'s own stack).

Cognito admin-API calls (`cognito_auth.py`) need explicit IAM grants on this function's
execution role — `AdminCreateUser`/`AdminSetUserPassword`/`AdminInitiateAuth`/
`AdminGetUser` are the only Cognito actions that require one; `ForgotPassword`/
`ConfirmForgotPassword` are "public" Cognito API actions (no IAM permission required for
any principal, by Cognito's own IAM model — they're gated by the App Client, not an IAM
policy), so they are deliberately not listed here.
"""
from __future__ import annotations

from pathlib import Path

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from .ssm_config import grant_and_map_secrets, plain_env_vars

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE = "mathbank-exam-agent"
SERVICE_DIR = REPO_ROOT / SERVICE

PLAIN_ENV_KEYS = [
    "GENERATOR_MODEL_ID", "CRITIC_MODEL_ID", "DIAGNOSIS_MODEL_ID",
    "BEDROCK_MODEL_ID", "AWS_REGION", "MAX_CRITIC_REVISION_ROUNDS",
    "COGNITO_USER_POOL_ID", "COGNITO_CLIENT_ID",
]

SECRET_KEY_TARGETS = {
    "OPENAI_API_KEY": "OPENAI_API_KEY",
    "ADMIN_API_KEY": "ADMIN_API_KEY",
    "COGNITO_CLIENT_SECRET": "COGNITO_CLIENT_SECRET",
}


def _parse_env_file(path: Path) -> dict[str, str]:
    """Keys are normalized to uppercase — unlike every other service's `.env` (always
    uppercase, matching `SECRET_KEY_TARGETS`/`PLAIN_ENV_KEYS` above exactly),
    `mathbank-exam-agent/.env` uses lowercase keys (pydantic-settings matches env vars
    case-insensitively, so the app itself is unaffected — but a case-sensitive lookup
    here against upper-case target keys silently found nothing, leaving every "secret"
    unwired: confirmed live, this exact bug shipped first, requirements/64's own
    GOTCHAS-worthy mistake to not repeat). Mirrors `seed_ssm.sh`'s existing
    case-insensitive `grep -iE` handling of the same lowercase-.env convention."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip().upper()] = value.strip().strip('"')
    return values


class ExamAgentServiceStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, *,
        rest_function_url: str, mcp_competitions_function_url: str, **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        env_values = _parse_env_file(REPO_ROOT / SERVICE / ".env")
        environment = plain_env_vars(env_values, PLAIN_ENV_KEYS)
        # Points the deployed agent at the already-deployed mathbank-rest/
        # mathbank-mcp-competitions Lambdas, not localhost — the one piece of real
        # cross-service wiring this stack needs (mirrors AgentServiceStack's own
        # rest_function_url pattern).
        environment["MATHBANK_REST_BASE_URL"] = rest_function_url.rstrip("/")
        environment["MCP_COMPETITIONS_URL"] = mcp_competitions_function_url.rstrip("/") + "/mcp"

        fn = lambda_.DockerImageFunction(
            self, "ExamAgentFunction",
            function_name="mathbank-exam-agent",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=str(SERVICE_DIR),
                file="Dockerfile.lambda",
                platform=ecr_assets.Platform.LINUX_ARM64,
            ),
            architecture=lambda_.Architecture.ARM_64,
            memory_size=1024,
            # Generator->critic rounds (up to 3 LLM calls per question, times however
            # many questions a paper requests) are the slowest path through this
            # service — confirmed live locally taking 60-90s for a 2-question paper.
            timeout=Duration.seconds(300),
            environment=environment,
        )

        present_secrets = {k: v for k, v in SECRET_KEY_TARGETS.items() if env_values.get(k)}
        secret_env = grant_and_map_secrets(self, fn, SERVICE, present_secrets)
        for key, value in secret_env.items():
            fn.add_environment(key, value)

        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "cognito-idp:AdminCreateUser", "cognito-idp:AdminSetUserPassword",
                    "cognito-idp:AdminInitiateAuth", "cognito-idp:AdminGetUser",
                ],
                resources=[
                    self.format_arn(
                        service="cognito-idp", resource="userpool",
                        resource_name=env_values.get("COGNITO_USER_POOL_ID", "*"),
                    )
                ],
            )
        )

        url = fn.add_function_url(auth_type=lambda_.FunctionUrlAuthType.NONE)
        self.function_url = url.url

        CfnOutput(self, "ExamAgentFunctionUrl", value=url.url)
