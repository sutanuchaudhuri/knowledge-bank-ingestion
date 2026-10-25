"""Cold-start configuration for the isolated Socratic-only Lambda."""
import json
import os

import boto3


def load_configuration() -> None:
    prefix = os.environ.pop("MATHBANK_SSM_PREFIX", "")
    mapping = os.environ.pop("MATHBANK_SECRET_MAP", "")
    if prefix and mapping:
        client = boto3.client("ssm")
        for pair in mapping.split(","):
            suffix, separator, target = pair.partition("=")
            if not separator or not suffix or not target:
                raise ValueError("Invalid isolated Socratic SSM configuration map")
            result = client.get_parameter(Name=f"{prefix}/{suffix}", WithDecryption=True)
            os.environ[target] = result["Parameter"]["Value"]
    if os.environ.get("SOCRATIC_AUTH_MODE", "cognito") != "cognito":
        raise ValueError("Isolated AWS Socratic API requires Cognito")
    # The parameter is created from the Function URL after the function resource,
    # avoiding a Function ↔ URL CloudFormation dependency cycle.
    origin_parameter = os.environ.pop("SOCRATIC_ORIGIN_PARAMETER", "")
    if origin_parameter:
        origin = boto3.client("ssm").get_parameter(Name=origin_parameter)["Parameter"]["Value"]
        os.environ["SOCRATIC_ALLOWED_ORIGINS"] = json.dumps([origin.rstrip("/")])


load_configuration()

from mangum import Mangum

from mathbank_rest.socratic_app import app

handler = Mangum(app)
