#!/usr/bin/env python3
"""CDK app entrypoint (requirements/62, requirements/63).

Region is fixed to us-east-2, co-located with the confirmed Neon Postgres/S3 region
(doc 62 §2) — override via CDK_DEFAULT_REGION only if that changes.
"""
from __future__ import annotations

import os
from pathlib import Path

import aws_cdk as cdk

from stacks.agent_service_stack import AgentServiceStack
from stacks.exam_agent_service_stack import ExamAgentServiceStack
from stacks.exam_web_static_stack import ExamWebStaticStack
from stacks.fargate_web_stack import FargateAppSpec, FargateWebStack
from stacks.manim_studio_service_stack import ManimStudioServiceStack
from stacks.mcp_competitions_service_stack import McpCompetitionsServiceStack
from stacks.ml_inference_service_stack import MlInferenceServiceStack
from stacks.rest_service_stack import RestServiceStack

REGION = os.environ.get("CDK_DEFAULT_REGION", "us-east-2")
ACCOUNT = os.environ.get("CDK_DEFAULT_ACCOUNT")

app = cdk.App()

env = cdk.Environment(account=ACCOUNT, region=REGION)

rest_stack = RestServiceStack(
    app, "MathBankRestStack",
    region=REGION,
    env=env,
    description="mathbank-rest on Lambda (container image) + Function URL (requirements/63)",
)

agent_stack = AgentServiceStack(
    app, "MathBankAgentStack",
    rest_function_url=rest_stack.function_url,
    env=env,
    description="mathbank-agent on Lambda (container image) + Function URL (requirements/63)",
)

ml_inference_stack = MlInferenceServiceStack(
    app, "MathBankMlInferenceStack",
    env=env,
    description="mathbank-ml-inference on Lambda (container image) + Function URL (requirements/63)",
)

mcp_competitions_stack = McpCompetitionsServiceStack(
    app, "MathBankMcpCompetitionsStack",
    rest_function_url=rest_stack.function_url,
    env=env,
    description="mathbank-mcp-competitions on Lambda (container image) + Function URL (requirements/62 §4.5, requirements/63)",
)

ManimStudioServiceStack(
    app, "MathBankManimStudioStack",
    rest_function_url=rest_stack.function_url,
    env=env,
    description="mathbank-manim-studio on Lambda: API (container image) + Function URL, plus a scheduled worker function (requirements/60, requirements/63)",
)

ExamAgentServiceStack(
    app, "MathBankExamAgentStack",
    rest_function_url=rest_stack.function_url,
    mcp_competitions_function_url=mcp_competitions_stack.function_url,
    env=env,
    description="mathbank-exam-agent on Lambda (container image) + Function URL (requirements/64)",
)

ExamWebStaticStack(
    app, "MathBankExamWebStack",
    env=env,
    description="mathbank-exam-web static SPA on S3 + CloudFront (requirements/64)",
)

REPO_ROOT_PATH = Path(__file__).resolve().parents[1]
_WIDGETS_CTX = {"mathbank_widgets": str(REPO_ROOT_PATH / "mathbank-widgets"),
                "mathbank_scripts": str(REPO_ROOT_PATH / "mathbank-scripts")}

FargateWebStack(
    app, "MathBankFargateWebStack",
    env=env,
    description="mathbank-web, mathbank-live, mathbank-ml-frontend on Fargate — "
                 "run-on-demand (desired_count=0 by default), no ALB (requirements/62 §5/§6, revised)",
    apps=[
        FargateAppSpec(
            service="mathbank-web", port=5173,
            dockerfile="Dockerfile.fargate", build_context=REPO_ROOT_PATH / "mathbank-web",
            build_contexts=_WIDGETS_CTX,
            plain_env_keys=[
                "MATHBANK_REST_BASE_URL", "NEO4J_URI", "NEO4J_USER", "AWS_REGION",
                "COGNITO_USER_POOL_ID", "COGNITO_CLIENT_ID", "COGNITO_ADMIN_GROUP",
                "ADMIN_LOGIN_USERNAME", "AWS_ENDPOINT_URL_S3", "AWS_ACCESS_KEY_ID",
                "NEON_AI_GATEWAY_BASE_URL", "MATHBANK_OBJECT_BUCKET",
                "MATHBANK_OBJECT_BACKEND", "MATHBANK_RUNTIME_AI_PROVIDER",
            ],
            secret_keys=[
                "NEO4J_PASSWORD", "MATHBANK_ADMIN_API_KEY", "ADMIN_LOGIN_PASSWORD",
                "ADMIN_SESSION_SECRET", "COGNITO_CLIENT_SECRET", "OPENAI_API_KEY",
                "ELEVEN_API_KEY", "AWS_SECRET_ACCESS_KEY", "NEON_AI_GATEWAY_TOKEN",
            ],
            env_overrides={
                "MATHBANK_REST_BASE_URL": rest_stack.function_url.rstrip("/"),
                "MATHBANK_AGENT_BASE_URL": agent_stack.function_url.rstrip("/"),
            },
            needs_cognito=True,
        ),
        FargateAppSpec(
            service="mathbank-live", port=5174,
            dockerfile="Dockerfile.fargate", build_context=REPO_ROOT_PATH / "mathbank-live",
            build_contexts=_WIDGETS_CTX,
            plain_env_keys=[
                "MATHBANK_REST_BASE_URL", "LIVE_PORT", "AWS_REGION", "AWS_ENDPOINT_URL_S3",
                "AWS_ACCESS_KEY_ID", "NEON_AI_GATEWAY_BASE_URL", "MATHBANK_OBJECT_BUCKET",
                "MATHBANK_OBJECT_BACKEND", "MATHBANK_RUNTIME_AI_PROVIDER",
                "COGNITO_USER_POOL_ID", "COGNITO_ADMIN_GROUP", "COGNITO_CLIENT_ID",
                "ADMIN_LOGIN_USERNAME",
            ],
            secret_keys=[
                "ELEVEN_API_KEY", "MATHBANK_ADMIN_API_KEY", "ADMIN_LOGIN_PASSWORD",
                "ADMIN_SESSION_SECRET", "AWS_SECRET_ACCESS_KEY", "NEON_AI_GATEWAY_TOKEN",
                "COGNITO_CLIENT_SECRET",
            ],
            env_overrides={"MATHBANK_REST_BASE_URL": rest_stack.function_url.rstrip("/")},
            needs_cognito=True,
        ),
        FargateAppSpec(
            service="mathbank-ml-frontend", port=5175,
            dockerfile="Dockerfile.fargate",
            build_context=REPO_ROOT_PATH / "mathbank-ml-frontend",
            plain_env_keys=[],
            secret_keys=[],
            env_overrides={"ML_INFERENCE_BASE_URL": ml_inference_stack.function_url.rstrip("/")},
        ),
    ],
)

app.synth()
