"""Read-only AWS preflight: credentials, Nova Sonic availability, S3 Vectors indexes and the content table.

No model is invoked and nothing is written. Prints only resource metadata, never credentials or content.
"""
from __future__ import annotations

import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from mathbank_genai_poc.config import get_settings
from mathbank_genai_poc.knowledge import DIMENSIONS, INDEXES


def main() -> int:
    s = get_settings()
    ok = True
    session = boto3.Session(profile_name=s.aws_profile or None)

    def check(label: str, call):  # noqa: ANN001
        nonlocal ok
        try:
            print(f"PASS {label}: {call()}")
        except (ClientError, BotoCoreError) as error:
            ok = False
            print(f"FAIL {label}: {type(error).__name__}: {getattr(error, 'response', {}).get('Error', {}).get('Code', '')}")

    check("identity", lambda: session.client("sts", region_name=s.data_region).get_caller_identity()["Account"])
    check(f"model {s.sonic_model_id} in {s.sonic_region}", lambda: (lambda m: f"{m['modelLifecycle']['status']}, "
          f"in={m['inputModalities']} out={m['outputModalities']}")(
        session.client("bedrock", region_name=s.sonic_region).get_foundation_model(
            modelIdentifier=s.sonic_model_id)["modelDetails"]))
    vectors = session.client("s3vectors", region_name=s.data_region)
    for family, index in INDEXES.items():
        def index_info(index: str = index) -> str:
            info = vectors.get_index(vectorBucketName=s.vector_bucket, indexName=index)["index"]
            if info["dimension"] != DIMENSIONS or info["distanceMetric"] != "cosine":
                raise ClientError({"Error": {"Code": "UnexpectedIndexShape"}}, "GetIndex")
            return f"{info['dimension']}d {info['distanceMetric']}"
        check(f"{s.vector_bucket}/{index} ({family})", index_info)
    check(f"table {s.content_table}", lambda: session.client("dynamodb", region_name=s.data_region).describe_table(
        TableName=s.content_table)["Table"]["TableStatus"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
