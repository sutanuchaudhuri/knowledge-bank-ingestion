"""Explicit isolated Socratic increment; never instantiates/deploys shared stacks."""
import os

import aws_cdk as cdk

from stacks.socratic_service_stack import SocraticServiceStack

app = cdk.App()
SocraticServiceStack(
    app, "MathBankSocraticStack",
    env=cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
                        region=os.environ.get("CDK_DEFAULT_REGION", "us-east-2")),
    description="Isolated Socratic draft API and same-origin prototype SPA; no model grants",
)
app.synth()
