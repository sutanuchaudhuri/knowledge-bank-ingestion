#!/usr/bin/env python3
"""CDK app entrypoint (requirements/62, requirements/63).

Region is fixed to us-east-2, co-located with the confirmed Neon Postgres/S3 region
(doc 62 §2) — override via CDK_DEFAULT_REGION only if that changes.
"""
from __future__ import annotations

import os

import aws_cdk as cdk

from stacks.agent_service_stack import AgentServiceStack
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

AgentServiceStack(
    app, "MathBankAgentStack",
    rest_function_url=rest_stack.function_url,
    env=env,
    description="mathbank-agent on Lambda (container image) + Function URL (requirements/63)",
)

MlInferenceServiceStack(
    app, "MathBankMlInferenceStack",
    env=env,
    description="mathbank-ml-inference on Lambda (container image) + Function URL (requirements/63)",
)

McpCompetitionsServiceStack(
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

app.synth()
