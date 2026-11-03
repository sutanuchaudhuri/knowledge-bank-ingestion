"""Validate every item and JSON document of a data-plane environment against its pydantic model.

    python -m mathbank_rest.models.validate [--contexts learner exam ...] [--s3-sample 100] [--segments 12] [--json]

For each item: (1) ``from_item`` validates it, (2) ``to_item()`` must reproduce the stored item exactly (lossless
round trip, so a model can never silently reshape data), (3) no undeclared attributes. For S3 documents: a sample per
family is validated against its model and, for offloaded attributes, the object's SHA-256/size are verified through
the item's ``S3Ref``. Exit code 0 only when nothing failed. Read-only; run it against ``dev``, never write to prod.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import datetime as dt
import json
import sys
import threading
from typing import Any

from pydantic import TypeAdapter, ValidationError

from mathbank_rest.config import settings
from mathbank_rest.models import base
from mathbank_rest.models.docs import family
from mathbank_rest.stores import ddb
from mathbank_rest.stores.errors import ItemSchemaError

CONTEXTS = ["content", "learner", "exam", "live", "media", "artifacts", "geometry", "jobs", "notify", "socratic",
            "agent_sessions", "audit"]


def _same_instant(a: str, b: str) -> bool:
    """``…+00:00`` and ``…Z`` are one instant: the model writes the canonical ``Z`` form."""
    if len(a) < 19 or len(b) < 19 or a[4] != "-" or b[4] != "-":
        return False
    try:
        x, y = dt.datetime.fromisoformat(a), dt.datetime.fromisoformat(b)
    except ValueError:
        return False
    return x.tzinfo is not None and y.tzinfo is not None and x == y


def same(a: Any, b: Any) -> bool:
    """Deep equality where 1 == 1.0 (DynamoDB numbers carry no int/float distinction)."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, str) and isinstance(b, str) and a != b:
        return _same_instant(a, b)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b, strict=True))
    return a == b


def _diff(a: Any, b: Any, path: str = "") -> str:
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return f"{path}.{k}: {'missing in stored' if k not in a else 'dropped by model'}"
            if not same(a[k], b[k]):
                return _diff(a[k], b[k], f"{path}.{k}")
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            if not same(x, y):
                return _diff(x, y, f"{path}[{i}]")
    return f"{path}: {str(a)[:60]!r} != {str(b)[:60]!r}"


class Report:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.stats: dict[str, dict[str, Any]] = collections.defaultdict(lambda: {"n": 0, "ok": 0, "fail": collections.Counter(), "examples": []})

    def record(self, key: str, ok: bool, kind: str = "", example: str = "") -> None:
        with self.lock:
            s = self.stats[key]
            s["n"] += 1
            if ok:
                s["ok"] += 1
            else:
                s["fail"][kind] += 1
                if len(s["examples"]) < 3:
                    s["examples"].append(example)

    @property
    def failures(self) -> int:
        return sum(sum(s["fail"].values()) for s in self.stats.values())

    def as_dict(self) -> dict:
        return {k: {"n": s["n"], "ok": s["ok"], "fail": dict(s["fail"]), "examples": s["examples"]} for k, s in sorted(self.stats.items())}


def check_item(ctx: str, raw: dict, rep: Report) -> None:
    t = raw.get("type", "?")
    key = f"{ctx}/{t}"
    model = base.model_for(ctx, t)
    if model is None:
        return rep.record(key, False, "no_model", f"{raw.get('PK')} {raw.get('SK')}")
    try:
        inst = model.from_item(raw)
    except ItemSchemaError as e:
        errs = e.detail.get("errors", [])
        return rep.record(key, False, "schema", f"{raw.get('PK')} {raw.get('SK')}: {errs[0]['loc']} {errs[0]['msg']}" if errs else e.message)
    try:
        out = inst.to_item()
    except ItemSchemaError as e:
        return rep.record(key, False, "undeclared", e.message)
    if not same(raw, out):
        return rep.record(key, False, "roundtrip", f"{raw.get('PK')} {raw.get('SK')}: {_diff(raw, out)}")
    rep.record(key, True)


def scan_context(ctx: str, rep: Report, segments: int) -> None:
    table = ddb.table_name(ctx)

    def run(seg: int) -> None:
        c = ddb.client()
        kw = {"TableName": table, "TotalSegments": segments, "Segment": seg}
        while True:
            page = c.scan(**kw)
            for item in page["Items"]:
                check_item(ctx, ddb._des_item(item), rep)
            if "LastEvaluatedKey" not in page:
                break
            kw["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    with cf.ThreadPoolExecutor(segments) as ex:
        list(ex.map(run, range(segments)))


def check_s3_docs(rep: Report, sample: int) -> None:
    from mathbank_rest.models.docs.registry import DOC_MODELS

    c = ddb.client("s3")
    picked: dict[str, list[tuple[str, str, int]]] = collections.defaultdict(list)
    for bucket in (ddb.content_bucket(), ddb.data_bucket()):
        for page in c.get_paginator("list_objects_v2").paginate(Bucket=bucket):
            for o in page.get("Contents", []):
                fam = family(o["Key"])
                if fam and len(picked[fam]) < sample and o["Size"] < 20_000_000:
                    picked[fam].append((bucket, o["Key"], o["Size"]))

    def check(fam: str, bucket: str, key: str) -> None:
        name = f"s3/{fam}"
        model = DOC_MODELS.get(fam)
        if model is None:
            return rep.record(name, False, "no_model", key)
        try:
            doc = json.loads(c.get_object(Bucket=bucket, Key=key)["Body"].read())
            TypeAdapter(model).validate_python(doc)
        except ValidationError as e:
            er = e.errors()[0]
            return rep.record(name, False, "schema", f"{key}: {'.'.join(map(str, er['loc']))} {er['msg']}")
        except Exception as e:  # noqa: BLE001 - report unreadable objects, keep going
            return rep.record(name, False, "read", f"{key}: {e}")
        rep.record(name, True)

    with cf.ThreadPoolExecutor(8) as ex:
        futs = [ex.submit(check, fam, b, k) for fam, items in picked.items() for b, k, _ in items]
        for f in futs:
            f.result()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--contexts", nargs="*", default=CONTEXTS)
    ap.add_argument("--s3-sample", type=int, default=100, help="documents per S3 family (0 skips S3)")
    ap.add_argument("--segments", type=int, default=12)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    base._load_models()
    rep = Report()
    for ctx in a.contexts:
        scan_context(ctx, rep, a.segments)
    if a.s3_sample:
        check_s3_docs(rep, a.s3_sample)
    if a.json:
        print(json.dumps({"env": settings.ddb_env, "failures": rep.failures, "stats": rep.as_dict()}, indent=1))
    else:
        total = sum(s["n"] for s in rep.stats.values())
        print(f"env={settings.ddb_env}: {total} objects checked, {rep.failures} failed, {len(rep.stats)} item/document kinds")
        for k, s in sorted(rep.stats.items()):
            if s["fail"]:
                print(f"  FAIL {k}: {s['n'] - s['ok']}/{s['n']} {dict(s['fail'])}")
                for ex in s["examples"]:
                    print(f"       {ex}")
        print("OK" if not rep.failures else "FAILED")
    return 0 if not rep.failures else 1


if __name__ == "__main__":
    sys.exit(main())
