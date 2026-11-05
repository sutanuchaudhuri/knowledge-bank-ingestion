"""Black-box API test harness: a real uvicorn process (local) talking to real AWS DynamoDB / S3 / S3 Vectors.

`dev` holds the migrated data and is only ever opened read-only (MB_AWS_READONLY=1 blocks every non-read AWS call);
`test` is empty and writable, so journeys that create data run there.
"""
