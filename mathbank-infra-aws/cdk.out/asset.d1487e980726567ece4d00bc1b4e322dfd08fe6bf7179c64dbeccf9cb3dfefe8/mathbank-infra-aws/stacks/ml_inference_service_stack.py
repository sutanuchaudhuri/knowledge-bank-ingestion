"""CDK stack: `mathbank-ml-inference` as a Lambda container image + Function URL
(requirements/62 §4, requirements/63). The service is scaffolded-only (every endpoint
returns 501 MLUnavailable; `/health` doesn't touch Postgres at all) — no real `.env` or
secret exists yet (requirements/56's own TODO list), so this stack deploys with no SSM
secrets wired at all. Add real plain/secret env vars here once the service has a real
Postgres read-only role provisioned (requirements/56 §1).
"""
from __future__ import annotations

from pathlib import Path

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from .ssm_config import DOCKER_ASSET_EXCLUDES

SERVICE_DIR = Path(__file__).resolve().parents[2] / "mathbank-ml-inference"


class MlInferenceServiceStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        fn = lambda_.DockerImageFunction(
            self, "MlInferenceFunction",
            function_name="mathbank-ml-inference",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=str(SERVICE_DIR),
                file="Dockerfile.lambda",
                platform=ecr_assets.Platform.LINUX_ARM64,
                exclude=DOCKER_ASSET_EXCLUDES,
            ),
            architecture=lambda_.Architecture.ARM_64,
            # Scaffolded stub — no DB connection at cold start, far lighter import graph
            # than mathbank-rest/mathbank-agent; confirmed live locally at ~140ms cold
            # init with the Lambda default 3008MB RIE emulator memory.
            memory_size=512,
            timeout=Duration.seconds(30),
        )

        url = fn.add_function_url(auth_type=lambda_.FunctionUrlAuthType.NONE)
        self.function_url = url.url

        CfnOutput(self, "MlInferenceFunctionUrl", value=url.url)
