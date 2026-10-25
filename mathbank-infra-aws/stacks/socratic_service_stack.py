"""Opt-in isolated draft API. Secrets from SSM, no Bedrock/AgentCore privileges."""
from __future__ import annotations

import hashlib
from pathlib import Path

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_ssm as ssm
from constructs import Construct
from dotenv import dotenv_values

from .ssm_config import DOCKER_ASSET_EXCLUDES, SSM_PREFIX

ROOT = Path(__file__).resolve().parents[2]
SERVICE = "mathbank-socratic-api"
SECRET_KEYS = ("POSTGRES_PASSWORD", "COGNITO_CLIENT_SECRET", "SOCRATIC_CSRF_SECRET")
PLAIN_KEYS = (
    "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_SSLMODE",
    "COGNITO_REGION", "COGNITO_USER_POOL_ID", "COGNITO_CLIENT_ID", "COGNITO_ADMIN_GROUP",
    "SOCRATIC_MATH_REVIEWER_GROUP", "SOCRATIC_PEDAGOGY_REVIEWER_GROUP", "SOCRATIC_PUBLISHER_GROUP",
)


class SocraticServiceStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        values = dotenv_values(ROOT / "mathbank-rest/.env", interpolate=False)
        required = (*SECRET_KEYS, "POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER",
                    "COGNITO_USER_POOL_ID", "COGNITO_CLIENT_ID")
        if any(not values.get(key) for key in required):
            raise ValueError("Isolated Socratic deployment requires existing REST DB/Cognito/CSRF configuration")
        dist = ROOT / "mathbank-socratic-admin/dist"
        if not (dist / "index.html").is_file():
            raise ValueError("Build mathbank-socratic-admin before deploying the isolated stack")
        dependency_hash = hashlib.sha256()
        dependencies = [*dist.rglob("*"), ROOT / "mathbank-geometry-engine/pyproject.toml",
                        *(ROOT / "mathbank-geometry-engine/src").rglob("*")]
        for path in sorted(dependencies):
            if path.is_file() and "__pycache__" not in path.parts:
                dependency_hash.update(str(path.relative_to(ROOT)).encode())
                dependency_hash.update(path.read_bytes())
        prefix = f"{SSM_PREFIX}/{SERVICE}"
        origin_name = f"{prefix}/STUDIO_ORIGIN"
        environment = {key: values[key] for key in PLAIN_KEYS if values.get(key)}
        environment.update({
            "SOCRATIC_AUTH_MODE": "cognito", "SOCRATIC_COOKIE_SECURE": "true",
            "SOCRATIC_AWS_PROFILE": "", "SOCRATIC_SESSION_SECONDS": "900",
            "SOCRATIC_ORIGIN_PARAMETER": origin_name,
            "MATHBANK_SSM_PREFIX": prefix,
            "MATHBANK_SECRET_MAP": ",".join(f"{key}={key}" for key in SECRET_KEYS),
        })
        fn = lambda_.DockerImageFunction(
            self, "SocraticFunction", function_name=SERVICE,
            code=lambda_.DockerImageCode.from_image_asset(
                directory=str(ROOT / "mathbank-rest"), file="Dockerfile.socratic",
                platform=ecr_assets.Platform.LINUX_ARM64, exclude=DOCKER_ASSET_EXCLUDES,
                build_contexts={"socratic_ui": str(dist), "geometry": str(ROOT / "mathbank-geometry-engine")},
                extra_hash=dependency_hash.hexdigest(),
            ),
            architecture=lambda_.Architecture.ARM_64,
            memory_size=512, timeout=Duration.seconds(30),
            log_retention=logs.RetentionDays.ONE_WEEK, environment=environment,
        )
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["ssm:GetParameter"], resources=[
                self.format_arn(service="ssm", resource="parameter",
                                resource_name=f"{prefix}/{key}".lstrip("/"))
                for key in (*SECRET_KEYS, "STUDIO_ORIGIN")
            ],
        ))
        fn.add_to_role_policy(iam.PolicyStatement(
            actions=["cognito-idp:AdminInitiateAuth", "cognito-idp:AdminListGroupsForUser"],
            resources=[self.format_arn(service="cognito-idp", resource="userpool",
                                       resource_name=values["COGNITO_USER_POOL_ID"])],
        ))
        url = fn.add_function_url(auth_type=lambda_.FunctionUrlAuthType.NONE)
        ssm.StringParameter(self, "StudioOrigin", parameter_name=origin_name, string_value=url.url)
        CfnOutput(self, "StudioUrl", value=url.url)
