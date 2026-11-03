"""Copy PostgreSQL rows into DynamoDB (and S3 objects) according to the specs, then write a manifest.

    python -m aws.dynamo.migrate --env dev [--only learner exam] [--mapping learner.attempt] \
        [--dry-run] [--limit N] [--workers 24]

Idempotent: items are written with deterministic keys (PutItem semantics), so a re-run overwrites the
same items. Source sessions are read-only. The manifest (logs/aws/<run>/dynamo-manifest.json and
s3://<data bucket>/migration/<run>/dynamo-manifest.json) records, per mapping and per (table, type):
source rows, items, and an order-independent sha256 over item hashes — verify.py recomputes these
from the live tables.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import decimal
import hashlib
import os
import threading
import time

from boto3.dynamodb.types import TypeSerializer

from ..common import (LOG, RUN_DIR, Env, client, clean_item, item_hash, json_bytes, run_id, setup_logging,
                      sha256, source, stream, write_json)
from . import registry
from .spec import S3Put

MAX_ITEM = 350_000          # bytes; DynamoDB hard limit is 400 KB including attribute names
# Large-payload policy (requirement 70 §5): listed attributes above this size live in S3 with a reference.
OFFLOAD_THRESHOLD = int(os.environ.get("MB_OFFLOAD_THRESHOLD", 16_384))
REF_SUFFIX = "_ref"
# Attributes that identify the owning student of an item outside a STUDENT# partition.
OWNER_ATTRS = ("student_id", "linked_student_id", "owner_student_id")
SER = TypeSerializer()
OFFLOAD: dict[tuple[str, str], tuple[str, ...]] = {}   # filled from the spec modules in main()


class Agg:
    """Order-independent aggregate: count + XOR/sum of item hashes is weak; use sorted list hash instead."""

    def __init__(self):
        self.lock = threading.Lock()
        self.hashes: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
        self.keys: dict[str, dict[tuple[str, str], str]] = collections.defaultdict(dict)  # table -> key -> mapping

    def add(self, table: str, typ: str, key: tuple[str, str], h: str, mapping: str) -> bool:
        with self.lock:
            prev = self.keys[table].get(key)
            self.keys[table][key] = mapping
            self.hashes[(table, typ)].append(h)
            return prev is not None


def _size(item: dict) -> int:
    return len(json_bytes(item)) + sum(len(k) for k in item)


class Writer:
    def __init__(self, env: Env, workers: int, dry: bool, run: str):
        self.env, self.dry, self.run = env, dry, run
        self.ddb = client("dynamodb")
        self.s3 = client("s3")
        self.pool = cf.ThreadPoolExecutor(max_workers=workers)
        self.s3_pool = cf.ThreadPoolExecutor(max_workers=32)
        self.s3_futs: list[cf.Future] = []
        self.futs: list[cf.Future] = []
        self.buf: dict[str, list[dict]] = collections.defaultdict(list)
        self.stats = collections.Counter()
        self.lock = threading.Lock()

    # ---------- S3
    def put_s3(self, obj: S3Put) -> str:
        """Hash locally, upload asynchronously (bounded concurrency); errors surface in _drain/close."""
        body = obj.body if isinstance(obj.body, (bytes, bytearray)) else json_bytes(obj.body)
        digest = sha256(body)
        if not self.dry:
            self.s3_futs.append(self.s3_pool.submit(
                self.s3.put_object, Bucket=self.env.bucket(obj.bucket), Key=obj.key, Body=body,
                ContentType=obj.content_type, ChecksumAlgorithm="SHA256",
                Metadata={"sha256": digest, "migration-run": self.run}))
            if len(self.s3_futs) > 512:
                while len(self.s3_futs) > 256:
                    self.s3_futs.pop(0).result()
        with self.lock:
            self.stats["s3_objects"] += 1
            self.stats["s3_bytes"] += len(body)
        return digest

    def _offload_key(self, table: str, item: dict, attr: str) -> str:
        """Student-owned items live under offload/<table>/students/<sid>/… so erasure deletes one prefix.
        Ownership: a STUDENT#<sid> partition, else an explicit owner attribute on the item."""
        h = hashlib.sha256((item["PK"] + "|" + item["SK"]).encode()).hexdigest()
        sid = None
        if item["PK"].startswith("STUDENT#"):
            sid = item["PK"].split("#", 1)[1].split("#", 1)[0]
        else:
            sid = next((str(item[a]) for a in OWNER_ATTRS if isinstance(item.get(a), str) and item[a]), None)
        if sid:
            return f"offload/{table}/students/{sid}/{item['type']}/{h}/{attr}.json"
        return f"offload/{table}/{item['type']}/{h[:2]}/{h}/{attr}.json"

    def _offload_attr(self, table: str, item: dict, attr: str) -> None:
        key = self._offload_key(table, item, attr)
        body = json_bytes(item.pop(attr))
        digest = self.put_s3(S3Put("data", key, body))
        item[f"{attr}{REF_SUFFIX}"] = {"bucket": self.env.bucket("data"), "key": key, "sha256": digest,
                                       "bytes": len(body), "content_type": "application/json"}
        with self.lock:
            self.stats["offloaded_attrs"] += 1
            self.stats["offloaded_bytes"] += len(body)

    def offload(self, table: str, item: dict, attrs: tuple[str, ...] = (), threshold: int = OFFLOAD_THRESHOLD) -> dict:
        """(1) Policy: each listed attribute larger than `threshold` bytes goes to S3.
        (2) Safety net: then move the largest remaining attributes until the item fits under MAX_ITEM.
        Every offloaded attribute is replaced by <attr>_ref = {bucket, key, sha256, bytes, content_type}."""
        for attr in attrs:
            if attr in item and len(json_bytes(item[attr])) > threshold:
                self._offload_attr(table, item, attr)
        while _size(item) > MAX_ITEM:
            attr = max((k for k in item if k not in ("PK", "SK", "type", "version") and not k.endswith(("PK", "SK", REF_SUFFIX))),
                       key=lambda k: len(json_bytes(item[k])))
            self._offload_attr(table, item, attr)
        return item

    # ---------- DynamoDB
    def add(self, table: str, item: dict) -> None:
        self.buf[table].append(item)
        if len(self.buf[table]) == 25:
            self._flush(table)

    def delete(self, table: str, key: tuple[str, str]) -> None:
        """Remove an item a previous run may have written (e.g. now expired). Idempotent."""
        self.buf[table].append({"__delete__": True, "PK": key[0], "SK": key[1]})
        if len(self.buf[table]) == 25:
            self._flush(table)

    def _flush(self, table: str) -> None:
        batch, self.buf[table] = self.buf[table], []
        if batch and not self.dry:
            self.futs.append(self.pool.submit(self._batch_write, self.env.table(table), batch))
        if len(self.futs) > 400:
            self._drain(200)

    def _batch_write(self, name: str, items: list[dict]) -> None:
        reqs = [{"DeleteRequest": {"Key": {"PK": SER.serialize(it["PK"]), "SK": SER.serialize(it["SK"])}}}
                if it.get("__delete__") else {"PutRequest": {"Item": {k: SER.serialize(v) for k, v in it.items()}}}
                for it in items]
        puts = sum(1 for it in items if not it.get("__delete__"))
        delay = 0.05
        while reqs:
            resp = self.ddb.batch_write_item(RequestItems={name: reqs})
            reqs = resp.get("UnprocessedItems", {}).get(name, [])
            if reqs:
                with self.lock:
                    self.stats["retried_items"] += len(reqs)
                time.sleep(delay)
                delay = min(delay * 2, 5)
        with self.lock:
            self.stats["written_items"] += puts
            self.stats["deleted_items"] += len(items) - puts

    def _drain(self, keep: int = 0) -> None:
        while len(self.futs) > keep:
            self.futs.pop(0).result()

    def close(self) -> None:
        for t in list(self.buf):
            self._flush(t)
        self._drain()
        for f in self.s3_futs:
            f.result()
        self.s3_futs.clear()
        self.pool.shutdown()
        self.s3_pool.shutdown()


def run_mapping(conn, mp, w: Writer, agg: Agg, limit: int | None) -> dict:
    sql = mp.sql + (f"\nLIMIT {int(limit)}" if limit else "")
    rows = items = s3n = collisions = 0
    types = collections.Counter()
    expired = collections.Counter()
    now = int(time.time())
    t0 = time.time()
    for row in stream(conn, sql, mp.params):
        rows += 1
        for out in mp.transform(row) or ():
            if isinstance(out, S3Put):
                w.put_s3(out)
                s3n += 1
                continue
            item = clean_item(out)
            for k in [k for k in item if k.startswith("GSI") and k.endswith(("PK", "SK"))]:
                if item[k] == "" or item[k] is None:
                    del item[k]          # empty GSI keys are invalid; a missing key keeps the GSI sparse
                elif not isinstance(item[k], str):
                    item[k] = str(item[k])
            for req in ("PK", "SK", "type"):
                if not isinstance(item.get(req), str) or not item[req]:
                    raise ValueError(f"{mp.name}: item missing {req}: {str(item)[:300]}")
            ttl = item.get("ttl")
            if isinstance(ttl, (int, decimal.Decimal)) and not isinstance(ttl, bool) and ttl <= now:
                # Already expired: DynamoDB TTL would delete it anyway, and the design treats it as absent.
                expired[item["type"]] += 1
                w.delete(mp.table, (item["PK"], item["SK"]))
                continue
            item = w.offload(mp.table, item, OFFLOAD.get((mp.table, item["type"]), ()) + mp.offload_attrs,
                             mp.offload_threshold or OFFLOAD_THRESHOLD)
            if agg.add(mp.table, item["type"], (item["PK"], item["SK"]), item_hash(item), mp.name):
                collisions += 1
            types[item["type"]] += 1
            items += 1
            w.add(mp.table, item)
        if rows % 20000 == 0:
            LOG.info("  %s: %d rows → %d items (%.0f rows/s)", mp.name, rows, items, rows / max(time.time() - t0, 1e-6))
    expected = None
    if mp.expected_source and not limit:
        expected = conn.execute(f"SELECT count(*) AS n FROM {mp.expected_source}").fetchone()["n"]
    res = {"mapping": mp.name, "table": mp.table, "source_rows": rows, "expected_source_rows": expected,
           "items": items, "s3_objects": s3n, "types": dict(types), "expired_skipped": dict(expired),
           "key_collisions": collisions,
           "seconds": round(time.time() - t0, 1)}
    level = LOG.warning if collisions or (expected is not None and expected != rows) else LOG.info
    level("%s → %s: rows=%d (expected %s) items=%d s3=%d collisions=%d", mp.name, mp.table, rows, expected,
          items, s3n, collisions)
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", default="dev")
    ap.add_argument("--only", nargs="*", help="spec modules (default: all)")
    ap.add_argument("--mapping", nargs="*", help="only these mapping names")
    ap.add_argument("--dry-run", action="store_true", help="read and transform, write nothing")
    ap.add_argument("--limit", type=int, help="rows per mapping (testing)")
    ap.add_argument("--workers", type=int, default=24)
    a = ap.parse_args()
    setup_logging()
    env, run = Env(a.env), run_id()
    mods = registry.load(a.only)
    OFFLOAD.update(registry.offload(mods))
    LOG.info("offload policy (> %d bytes): %s", OFFLOAD_THRESHOLD, {f"{t}/{ty}": v for (t, ty), v in OFFLOAD.items()})
    maps = [m for m in registry.mappings(mods) if not a.mapping or m.name in a.mapping]
    w, agg, results = Writer(env, a.workers, a.dry_run, run), Agg(), []
    LOG.info("run %s env=%s mappings=%d dry=%s", run, env.name, len(maps), a.dry_run)
    try:
        with source() as conn:
            for mp in maps:
                results.append(run_mapping(conn, mp, w, agg, a.limit))
    finally:
        w.close()
    summary = {}
    for (table, typ), hs in sorted(agg.hashes.items()):
        summary.setdefault(table, {})[typ] = {"items": len(hs), "sha256": hashlib.sha256("".join(sorted(hs)).encode()).hexdigest()}
    manifest = {"run": run, "env": env.name, "dry_run": a.dry_run, "limit": a.limit, "partial": bool(a.mapping or a.only),
                "mappings": results, "tables": summary, "writer": dict(w.stats)}
    path = os.path.join(RUN_DIR, run, "dynamo-manifest.json")
    write_json(path, manifest)
    if not a.dry_run:
        client("s3").put_object(Bucket=env.bucket("data"), Key=f"migration/{run}/dynamo-manifest.json", Body=json_bytes(manifest))
    bad = [r for r in results if r["key_collisions"] or (r["expected_source_rows"] is not None and r["expected_source_rows"] != r["source_rows"])]
    LOG.info("done: %s; manifest %s", dict(w.stats), path)
    if bad:
        raise SystemExit(f"{len(bad)} mapping(s) with collisions or row-count mismatch: {[r['mapping'] for r in bad]}")


if __name__ == "__main__":
    main()
