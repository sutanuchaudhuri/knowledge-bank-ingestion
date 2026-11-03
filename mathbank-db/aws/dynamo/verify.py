"""Verify DynamoDB contents against a migration manifest.

    python -m aws.dynamo.verify --env dev --manifest logs/aws/<run>/dynamo-manifest.json

Scans every table in the manifest (parallel segments, consistent reads), groups items by `type`,
recomputes the order-independent sha256 over item hashes and compares count + hash per (table, type).
Items present in the table but not in the manifest (e.g. written later by an application) are reported
as `extra`. Exit code 1 on any mismatch.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import hashlib
import json

from boto3.dynamodb.types import TypeDeserializer

from ..common import LOG, Env, client, item_hash, setup_logging, write_json

DES = TypeDeserializer()


def _refs(it: dict) -> list[dict]:
    return [v for k, v in it.items() if k.endswith("_ref") and isinstance(v, dict) and "key" in v and "sha256" in v]


def check_refs(refs: list[dict]) -> dict:
    """HEAD every S3 object referenced by an offloaded attribute; compare size and sha256 metadata."""
    s3 = client("s3")

    def one(r):
        try:
            h = s3.head_object(Bucket=r["bucket"], Key=r["key"])
        except s3.exceptions.ClientError:
            return "missing"
        if int(h["ContentLength"]) != int(r.get("bytes", h["ContentLength"])):
            return "size"
        return "ok" if h.get("Metadata", {}).get("sha256") == r["sha256"] else "sha256"

    with cf.ThreadPoolExecutor(32) as ex:
        return dict(collections.Counter(ex.map(one, refs)))


def scan_table(name: str, segments: int = 16, refs: list | None = None) -> dict[str, list[str]]:
    ddb = client("dynamodb")

    def seg(i):
        out = collections.defaultdict(list)
        kw = {"TableName": name, "Segment": i, "TotalSegments": segments, "ConsistentRead": True}
        while True:
            r = ddb.scan(**kw)
            for raw in r["Items"]:
                it = {k: DES.deserialize(v) for k, v in raw.items()}
                out[it.get("type", "?")].append(item_hash(it))
                if refs is not None:
                    refs.extend(_refs(it))
            if "LastEvaluatedKey" not in r:
                return out
            kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]

    merged = collections.defaultdict(list)
    with cf.ThreadPoolExecutor(segments) as ex:
        for part in ex.map(seg, range(segments)):
            for t, hs in part.items():
                merged[t].extend(hs)
    return merged


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", default="dev")
    ap.add_argument("--manifest", required=True, nargs="+",
                    help="one or more manifests; for each table the LAST manifest listing it wins")
    a = ap.parse_args()
    setup_logging()
    env = Env(a.env)
    tables: dict[str, tuple[str, dict]] = {}
    for path in a.manifest:
        man = json.load(open(path))
        if man.get("dry_run"):
            raise SystemExit(f"{path} is a dry-run manifest")
        for table, types in man["tables"].items():
            tables[table] = (path, types)
    report, failures = {}, 0
    for table, (src, types) in sorted(tables.items()):
        name = env.table(table)
        LOG.info("scan %s", name)
        refs: list[dict] = []
        live = scan_table(name, refs=refs)
        rows = []
        for typ, exp in sorted(types.items()):
            hs = live.pop(typ, [])
            got = hashlib.sha256("".join(sorted(hs)).encode()).hexdigest()
            ok = len(hs) == exp["items"] and got == exp["sha256"]
            failures += 0 if ok else 1
            rows.append({"type": typ, "expected": exp["items"], "found": len(hs), "hash_ok": got == exp["sha256"], "ok": ok})
            (LOG.info if ok else LOG.error)("  %-40s expected=%-8d found=%-8d hash=%s", typ, exp["items"], len(hs),
                                            "ok" if got == exp["sha256"] else "MISMATCH")
        extra = {t: len(h) for t, h in live.items()}
        if extra:
            LOG.warning("  extra item types not in manifest: %s", extra)
        ref_check = check_refs(refs) if refs else {}
        bad_refs = sum(n for k, n in ref_check.items() if k != "ok")
        failures += 1 if bad_refs else 0
        (LOG.info if not bad_refs else LOG.error)("  S3 references: %s", ref_check or "none")
        report[table] = {"manifest": src, "types": rows, "extra": extra, "s3_refs": ref_check}
    out = a.manifest[-1].replace("dynamo-manifest.json", "dynamo-verify.json")
    write_json(out, {"manifests": a.manifest, "failures": failures, "tables": report})
    LOG.info("verification %s (%d failures) → %s", "PASSED" if not failures else "FAILED", failures, out)
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
