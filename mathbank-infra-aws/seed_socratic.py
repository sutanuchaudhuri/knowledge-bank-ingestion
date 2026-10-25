"""Seed only isolated Socratic SSM secrets from existing REST configuration."""
from pathlib import Path

import boto3
from dotenv import dotenv_values

from stacks.socratic_service_stack import SECRET_KEYS, SERVICE
from stacks.ssm_config import SSM_PREFIX


def main():
    values = dotenv_values(Path(__file__).resolve().parents[1] / "mathbank-rest/.env", interpolate=False)
    if any(not values.get(key) for key in SECRET_KEYS):
        raise ValueError("Missing required secret configuration; no SSM values written")
    session = boto3.Session(profile_name="aws-sutanu-admin", region_name="us-east-2")
    if session.client("sts").get_caller_identity()["Account"] != "848941468793":
        raise ValueError("Refusing unexpected AWS account")
    client = session.client("ssm")
    for key in SECRET_KEYS:
        client.put_parameter(Name=f"{SSM_PREFIX}/{SERVICE}/{key}",
                             Value=values[key], Type="SecureString", Overwrite=True)
        print(f"Seeded isolated {key} (value hidden)")


if __name__ == "__main__":
    main()
