"""Local-development doctor: can this machine use the DynamoDB / S3 / S3 Vectors data plane?

    python -m mathbank_rest.stores.doctor                    # the contexts whose store flag is dynamodb
    python -m mathbank_rest.stores.doctor --all --write-check --vectors
    python -m mathbank_rest.stores.doctor --contexts learner exam --json

Checks, in order: AWS credentials (the profile in AWS_PROFILE / MB_AWS_PROFILE, else the default chain), every
selected table is ACTIVE, the data/content buckets exist, optionally a write/read/delete round trip of one throwaway
item (TTL 1 h) and the S3 Vectors bucket. Exit code 0 only when everything is reachable. Credentials problems print
the exact `aws login` command to run.
"""
from __future__ import annotations

import argparse
import json
import sys

from mathbank_rest import stores
from mathbank_rest.config import settings
from mathbank_rest.stores import ddb


def selected_contexts() -> list[str]:
    return [c for c in stores.CONTEXTS if stores.store_mode(c)[1] == "dynamodb"]


def render(result: dict) -> str:
    L = [f"data plane: env={result['env']} region={result['region']} profile={result['profile']}"]
    if ident := result.get("identity"):
        L.append(f"identity:   {ident['arn']} (account {ident['account']})")
    for name, t in result["tables"].items():
        extra = f" items≈{t['items_approx']} gsis={','.join(t['gsis'])}" if "gsis" in t else ""
        rt = {True: " write-roundtrip=ok", False: " write-roundtrip=FAILED"}.get(t.get("write_roundtrip"), "")
        L.append(f"  table {name}: {t['status']}{extra}{rt}")
    for b, st in result["buckets"].items():
        L.append(f"  bucket {b}: {st}")
    for e in result["errors"]:
        L.append(f"  ERROR [{e['code']}] {e['where']}: {e['message']}")
    L.append("OK" if result["ok"] else "NOT READY")
    if settings.ddb_env == "prod":
        L.append("WARNING: env=prod. Local development should use DDB_ENV=dev (migrated copy) or test (empty).")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--contexts", nargs="*", help="table contexts to check (default: flags set to dynamodb)")
    ap.add_argument("--all", action="store_true", help="check every context table")
    ap.add_argument("--write-check", action="store_true", help="put/get/delete one throwaway item per table")
    ap.add_argument("--vectors", action="store_true", help="also check the S3 Vectors bucket")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    ctxs = list(stores.CONTEXTS) if a.all else (a.contexts if a.contexts else selected_contexts())
    unknown = set(ctxs) - set(stores.CONTEXTS)
    if unknown:
        print(f"unknown context(s): {sorted(unknown)}; expected {list(stores.CONTEXTS)}", file=sys.stderr)
        return 2
    if not ctxs:
        print("no store is set to dynamodb; checking credentials only (use --all to check every table)")
    result = ddb.check_connectivity(ctxs, write_check=a.write_check, vectors=a.vectors or settings.vector_store == "s3vectors")
    print(json.dumps(result, indent=2, default=str) if a.json else render(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
