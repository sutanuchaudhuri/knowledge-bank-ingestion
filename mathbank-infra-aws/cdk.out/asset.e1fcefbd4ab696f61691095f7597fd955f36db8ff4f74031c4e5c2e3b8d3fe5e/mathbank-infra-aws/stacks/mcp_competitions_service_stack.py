"""CDK stack: `mathbank-mcp-competitions` as a Lambda container image + Function URL
(requirements/62 §4.5, requirements/63). This is the **new**, separately-deployed HTTP
instance of this server — the stdio-subprocess use bundled into mathbank-manim-studio's
agent_demo is untouched by this stack. No secrets: the service only proxies read calls
to mathbank-rest's own already-authenticated `/v1/*` endpoints; `OPENAI_API_KEY` in its
`.env.example` is a dead/unused setting (confirmed live — grepped the whole package).
"""
from __future__ import annotations

from pathlib import Path

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

SERVICE_DIR = Path(__file__).resolve().parents[2] / "mathbank-mcp-competitions"


class McpCompetitionsServiceStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, *, rest_function_url: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        fn = lambda_.DockerImageFunction(
            self, "McpCompetitionsFunction",
            function_name="mathbank-mcp-competitions",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=str(SERVICE_DIR),
                file="Dockerfile.lambda",
                platform=ecr_assets.Platform.LINUX_ARM64,
            ),
            architecture=lambda_.Architecture.ARM_64,
            # FastMCP + prefab-ui's import graph is heavier than mathbank-ml-inference's
            # stub but lighter than the agent's google-adk/litellm stack; confirmed live
            # locally cold-initing at ~450ms with the RIE emulator's 3008MB default.
            memory_size=1024,
            timeout=Duration.seconds(30),
            environment={
                # Points this MCP server at the already-deployed mathbank-rest Lambda,
                # not localhost (same cross-stack pattern as AgentServiceStack).
                "MATHBANK_REST_BASE_URL": rest_function_url.rstrip("/"),
            },
        )

        url = fn.add_function_url(auth_type=lambda_.FunctionUrlAuthType.NONE)
        self.function_url = url.url

        CfnOutput(self, "McpCompetitionsFunctionUrl", value=url.url)
