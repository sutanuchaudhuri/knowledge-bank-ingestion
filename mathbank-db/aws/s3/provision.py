"""Create or update S3 buckets and the S3 Vectors bucket + indexes (idempotent, never deletes).

    python -m aws.s3.provision --env dev [--dry-run]

Buckets:
  mathbank-data-<env>-<account>     private: media/payload offload, vector archives, migration manifests,
                                     DynamoDB exports. Versioned, SSE-S3, TLS-only, public access blocked.
  mathbank-content-<env>-<account>  private: immutable hash-addressed release snapshots (read model).
  mathbank-vectors-<env>            S3 Vectors bucket; one index per entry in aws/s3/vector_indexes.py.
"""
from __future__ import annotations

import argparse
import json

from ..common import LOG, REGION, Env, account_id, client, setup_logging

TAGS = lambda env: {"app": "mathbank", "env": env.name, "managed-by": "mathbank-db/aws"}  # noqa: E731


def ensure_bucket(env: Env, kind: str, dry: bool) -> None:
    s3 = client("s3")
    name = env.bucket(kind)
    try:
        s3.head_bucket(Bucket=name, ExpectedBucketOwner=account_id())
        LOG.info("exists s3://%s", name)
    except s3.exceptions.ClientError as e:
        if e.response["Error"]["Code"] not in ("404", "NoSuchBucket"):
            raise
        LOG.info("create s3://%s", name)
        if dry:
            return
        kw = {"Bucket": name}
        if REGION != "us-east-1":
            kw["CreateBucketConfiguration"] = {"LocationConstraint": REGION}
        s3.create_bucket(**kw)
    if dry:
        return
    s3.put_public_access_block(Bucket=name, PublicAccessBlockConfiguration={
        "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
    s3.put_bucket_encryption(Bucket=name, ServerSideEncryptionConfiguration={"Rules": [
        {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}, "BucketKeyEnabled": True}]})
    s3.put_bucket_versioning(Bucket=name, VersioningConfiguration={"Status": "Enabled"})
    s3.put_bucket_ownership_controls(Bucket=name, OwnershipControls={"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]})
    s3.put_bucket_policy(Bucket=name, Policy=json.dumps({"Version": "2012-10-17", "Statement": [{
        "Sid": "DenyInsecureTransport", "Effect": "Deny", "Principal": "*", "Action": "s3:*",
        "Resource": [f"arn:aws:s3:::{name}", f"arn:aws:s3:::{name}/*"],
        "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]}))
    s3.put_bucket_lifecycle_configuration(Bucket=name, LifecycleConfiguration={"Rules": [
        {"ID": "expire-noncurrent", "Status": "Enabled", "Filter": {"Prefix": ""},
         "NoncurrentVersionExpiration": {"NoncurrentDays": 30},
         "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7}}]})
    s3.put_bucket_tagging(Bucket=name, Tagging={"TagSet": [{"Key": k, "Value": v} for k, v in TAGS(env).items()]})
    LOG.info("ready s3://%s", name)


def ensure_vectors(env: Env, dry: bool) -> None:
    from .vector_indexes import INDEXES
    sv = client("s3vectors")
    try:
        sv.get_vector_bucket(vectorBucketName=env.vector_bucket)
        LOG.info("exists vector bucket %s", env.vector_bucket)
    except sv.exceptions.NotFoundException:
        LOG.info("create vector bucket %s", env.vector_bucket)
        if not dry:
            sv.create_vector_bucket(vectorBucketName=env.vector_bucket, encryptionConfiguration={"sseType": "AES256"},
                                    tags=TAGS(env))
    for ix in INDEXES:
        try:
            if dry:
                raise sv.exceptions.NotFoundException({"Error": {"Code": "NotFound", "Message": ""}}, "GetIndex")
            got = sv.get_index(vectorBucketName=env.vector_bucket, indexName=ix.name)["index"]
            if got["dimension"] != ix.dimension or got["distanceMetric"] != ix.metric:
                raise SystemExit(f"index {ix.name} exists with different dimension/metric: {got}")
            LOG.info("exists index %s", ix.name)
        except sv.exceptions.NotFoundException:
            LOG.info("create index %s dim=%d %s non_filterable=%s", ix.name, ix.dimension, ix.metric, list(ix.non_filterable))
            if dry:
                continue
            kw = dict(vectorBucketName=env.vector_bucket, indexName=ix.name, dataType="float32",
                      dimension=ix.dimension, distanceMetric=ix.metric, tags=TAGS(env))
            if ix.non_filterable:
                kw["metadataConfiguration"] = {"nonFilterableMetadataKeys": list(ix.non_filterable)}
            sv.create_index(**kw)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", default="dev")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-vectors", action="store_true")
    a = ap.parse_args()
    setup_logging()
    env = Env(a.env)
    for kind in ("data", "content"):
        ensure_bucket(env, kind, a.dry_run)
    if not a.skip_vectors:
        ensure_vectors(env, a.dry_run)


if __name__ == "__main__":
    main()
