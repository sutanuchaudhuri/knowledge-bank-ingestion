"""MathBank PostgreSQL → AWS (DynamoDB + S3 + S3 Vectors) migration toolkit.

Layout (requirement 70, documentation/requirements/70_DYNAMODB_AND_S3_VECTORS_ADOPTION_PLAN.md):
    aws/common.py         configuration, read-only Neon source, type conversion, hashing
    aws/dynamo/           DynamoDB table specs, provisioning, data migration and verification
    aws/s3/               S3 buckets, S3 Vectors bucket/indexes, vector copy and verification

Run from the mathbank-db directory, e.g. `python -m aws.dynamo.provision --env dev`.
"""
