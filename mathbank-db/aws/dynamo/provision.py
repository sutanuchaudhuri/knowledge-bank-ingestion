"""Create or update the DynamoDB tables declared by the specs (idempotent).

    python -m aws.dynamo.provision --env dev [--only learner exam] [--dry-run]

Every table: on-demand billing, PITR, deletion protection, SSE, tags app=mathbank env=<env>,
string PK/SK plus declared GSIs, optional stream (NEW_AND_OLD_IMAGES) and TTL attribute "ttl".
Never deletes a table or a GSI.
"""
from __future__ import annotations

import argparse
import time

from ..common import LOG, Env, client, setup_logging
from . import registry


def _definition(env: Env, t) -> dict:
    attrs = {"PK", "SK"}
    gsis = []
    include = dict(t.include_gsis)
    for g in t.gsis:
        attrs |= {f"{g}PK", f"{g}SK"}
        if g in include:
            nk = sorted(set(include[g]) | {"type"})
            if len(nk) > 20:
                raise SystemExit(f"{t.ctx}.{g}: INCLUDE projects {len(nk)} attributes; DynamoDB allows at most 20")
            proj = {"ProjectionType": "INCLUDE", "NonKeyAttributes": nk}
        else:
            proj = {"ProjectionType": "KEYS_ONLY" if g in t.keys_only_gsis else "ALL"}
        gsis.append({"IndexName": g,
                     "KeySchema": [{"AttributeName": f"{g}PK", "KeyType": "HASH"},
                                   {"AttributeName": f"{g}SK", "KeyType": "RANGE"}],
                     "Projection": proj})
    d = {"TableName": env.table(t.ctx),
         "AttributeDefinitions": [{"AttributeName": a, "AttributeType": "S"} for a in sorted(attrs)],
         "KeySchema": [{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
         "BillingMode": "PAY_PER_REQUEST",
         "SSESpecification": {"Enabled": True, "SSEType": "KMS"} if env.name == "prod" else {"Enabled": False},
         "DeletionProtectionEnabled": True,
         "Tags": [{"Key": "app", "Value": "mathbank"}, {"Key": "env", "Value": env.name},
                  {"Key": "context", "Value": t.ctx}, {"Key": "managed-by", "Value": "mathbank-db/aws"}]}
    if gsis:
        d["GlobalSecondaryIndexes"] = gsis
    if t.stream:
        d["StreamSpecification"] = {"StreamEnabled": True, "StreamViewType": "NEW_AND_OLD_IMAGES"}
    return d


def _wait_active(ddb, name: str) -> dict:
    while True:
        desc = ddb.describe_table(TableName=name)["Table"]
        busy = desc["TableStatus"] != "ACTIVE" or any(g["IndexStatus"] != "ACTIVE" for g in desc.get("GlobalSecondaryIndexes", []))
        if not busy:
            return desc
        time.sleep(5)


def ensure(env: Env, t, dry: bool = False) -> None:
    ddb = client("dynamodb")
    d = _definition(env, t)
    name = d["TableName"]
    try:
        desc = ddb.describe_table(TableName=name)["Table"]
        LOG.info("exists %s (%s)", name, desc["TableStatus"])
    except ddb.exceptions.ResourceNotFoundException:
        LOG.info("create %s gsis=%s stream=%s ttl=%s", name, list(t.gsis), t.stream, t.ttl)
        if dry:
            return
        ddb.create_table(**d)
        desc = _wait_active(ddb, name)
    if dry:
        return
    desc = _wait_active(ddb, name)
    have = {g["IndexName"] for g in desc.get("GlobalSecondaryIndexes", [])}
    for g in d.get("GlobalSecondaryIndexes", []):
        if g["IndexName"] not in have:
            LOG.info("add gsi %s.%s", name, g["IndexName"])
            ddb.update_table(TableName=name, AttributeDefinitions=d["AttributeDefinitions"],
                             GlobalSecondaryIndexUpdates=[{"Create": g}])
            _wait_active(ddb, name)
    if t.stream and not desc.get("StreamSpecification", {}).get("StreamEnabled"):
        ddb.update_table(TableName=name, StreamSpecification=d["StreamSpecification"])
        _wait_active(ddb, name)
    if t.ttl:
        cur = ddb.describe_time_to_live(TableName=name)["TimeToLiveDescription"]
        if cur.get("TimeToLiveStatus") not in ("ENABLED", "ENABLING"):
            ddb.update_time_to_live(TableName=name, TimeToLiveSpecification={"Enabled": True, "AttributeName": "ttl"})
    pitr = ddb.describe_continuous_backups(TableName=name)["ContinuousBackupsDescription"]
    if pitr.get("PointInTimeRecoveryDescription", {}).get("PointInTimeRecoveryStatus") != "ENABLED":
        for attempt in range(30):  # a new table's backups initialise asynchronously
            try:
                ddb.update_continuous_backups(TableName=name,
                                              PointInTimeRecoverySpecification={"PointInTimeRecoveryEnabled": True})
                break
            except ddb.exceptions.ContinuousBackupsUnavailableException:
                time.sleep(10)
        else:
            raise SystemExit(f"{name}: point-in-time recovery could not be enabled")
    LOG.info("ready %s", name)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", default="dev")
    ap.add_argument("--only", nargs="*", help="spec modules (default: all)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    setup_logging()
    env = Env(a.env)
    for t in registry.tables(registry.load(a.only)).values():
        ensure(env, t, a.dry_run)


if __name__ == "__main__":
    main()
