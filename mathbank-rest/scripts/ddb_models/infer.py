"""Profile the real DynamoDB items and S3 JSON documents of one environment (default `dev`).

Output (JSON): for every (table ctx, item `type`) and every S3 JSON document family, a recursive attribute profile -
observed kinds, string formats, distinct low-cardinality values, presence counts, nested records and map-valued dicts.
`generate.py` turns it into pydantic models; nothing here is imported by the service.

    python scripts/ddb_models/infer.py --out .ddb_profile/dev.json [--s3-sample 150]
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import datetime as dt
import decimal
import json
import re
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from mathbank_rest.config import settings  # noqa: E402
from mathbank_rest.stores import ddb  # noqa: E402

CONTEXTS = ["content", "learner", "exam", "live", "media", "artifacts", "geometry", "jobs", "notify", "socratic",
            "agent_sessions", "audit"]
TS = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(Z|[+-]\d\d:\d\d)$")
DATE = re.compile(r"^\d{4}-\d\d-\d\d$")
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
MAP_KEYS = 60            # a dict with more distinct keys is a map<string, V>, not a record
MAX_VALUES = 25
MAX_LIST = 2500


def new() -> dict:
    return {"n": 0, "kinds": {}, "fmt": {}, "vals": {}, "vals_overflow": False, "strmax": 0, "dict_n": 0,
            "children": {}, "item": None, "mapping": False, "num_min": None, "num_max": None, "list_min": None, "list_max": None}


def _bump(d: dict, k: str, by: int = 1) -> None:
    d[k] = d.get(k, 0) + by


def observe(node: dict, v, depth: int = 0) -> None:
    node["n"] += 1
    if v is None:
        _bump(node["kinds"], "null")
    elif isinstance(v, bool):
        _bump(node["kinds"], "bool")
    elif isinstance(v, (int, decimal.Decimal)):
        integral = isinstance(v, int) or v == v.to_integral_value()
        _bump(node["kinds"], "int" if integral else "float")
        f = float(v)
        node["num_min"] = f if node["num_min"] is None else min(node["num_min"], f)
        node["num_max"] = f if node["num_max"] is None else max(node["num_max"], f)
    elif isinstance(v, float):
        _bump(node["kinds"], "float" if v != int(v) else "int")
    elif isinstance(v, str):
        _bump(node["kinds"], "str")
        fmt = "ts" if TS.match(v) else "date" if DATE.match(v) else "uuid" if UUID.match(v) else "other"
        _bump(node["fmt"], fmt)
        node["strmax"] = max(node["strmax"], len(v))
        if not node["vals_overflow"]:
            node["vals"][v] = node["vals"].get(v, 0) + 1
            if len(node["vals"]) > MAX_VALUES:
                node["vals_overflow"], node["vals"] = True, {}
    elif isinstance(v, (list, tuple)):
        _bump(node["kinds"], "list")
        n = len(v)
        node["list_min"] = n if node["list_min"] is None else min(node["list_min"], n)
        node["list_max"] = n if node["list_max"] is None else max(node["list_max"], n)
        if node["item"] is None:
            node["item"] = new()
        for x in list(v)[:MAX_LIST]:
            observe(node["item"], x, depth + 1)
    elif isinstance(v, dict):
        _bump(node["kinds"], "dict")
        node["dict_n"] += 1
        if node["mapping"]:
            if node["item"] is None:
                node["item"] = new()
            for x in v.values():
                observe(node["item"], x, depth + 1)
            return
        for k, x in v.items():
            observe(node["children"].setdefault(k, new()), x, depth + 1)
        if len(node["children"]) > MAP_KEYS:
            node["mapping"] = True
            merged = node["item"] or new()
            for c in node["children"].values():
                merge(merged, c)
            node["item"], node["children"] = merged, {}
    else:
        _bump(node["kinds"], "other")


def merge(a: dict, b: dict) -> dict:
    a["n"] += b["n"]
    a["dict_n"] += b["dict_n"]
    a["strmax"] = max(a["strmax"], b["strmax"])
    for k, c in b["kinds"].items():
        _bump(a["kinds"], k, c)
    for k, c in b["fmt"].items():
        _bump(a["fmt"], k, c)
    for key in ("num_min", "list_min"):
        if b[key] is not None:
            a[key] = b[key] if a[key] is None else min(a[key], b[key])
    for key in ("num_max", "list_max"):
        if b[key] is not None:
            a[key] = b[key] if a[key] is None else max(a[key], b[key])
    if b["vals_overflow"] or a["vals_overflow"]:
        a["vals_overflow"], a["vals"] = True, {}
    else:
        for k, c in b["vals"].items():
            _bump(a["vals"], k, c)
        if len(a["vals"]) > MAX_VALUES:
            a["vals_overflow"], a["vals"] = True, {}
    if b["item"] is not None:
        a["item"] = merge(a["item"] or new(), b["item"])
    a["mapping"] = a["mapping"] or b["mapping"]
    for k, c in b["children"].items():
        a["children"][k] = merge(a["children"].get(k) or new(), c)
    return a


def to_python(v):
    if isinstance(v, decimal.Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, dict):
        return {k: to_python(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [to_python(x) for x in v]
    if isinstance(v, (set, frozenset)):
        return sorted(to_python(x) for x in v)
    return v


def scan_table(ctx: str, segments: int = 16) -> dict[str, dict]:
    """Profile every item of one table, grouped by `type`. Segments run in parallel threads."""
    table = ddb.table_name(ctx)
    lock = threading.Lock()
    out: dict[str, dict] = {}

    def run(seg: int) -> None:
        local: dict[str, dict] = {}
        c = ddb.client()
        kw = {"TableName": table, "TotalSegments": segments, "Segment": seg, "ConsistentRead": False}
        while True:
            page = c.scan(**kw)
            for raw in page["Items"]:
                item = to_python(ddb._des_item(raw))
                t = item.get("type", "?")
                observe(local.setdefault(t, new()), item)
            if "LastEvaluatedKey" not in page:
                break
            kw["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        with lock:
            for t, node in local.items():
                out[t] = merge(out[t], node) if t in out else node

    with cf.ThreadPoolExecutor(segments) as ex:
        list(ex.map(run, range(segments)))
    return out


def family(bucket: str, key: str) -> str:
    parts = key.split("/")
    if parts[0] == "offload":
        # offload/<table>/[students/<sid>/]<TYPE>/…/<attr>.json
        rest = parts[2:]
        if rest and rest[0] == "students":
            rest = rest[2:]
        return f"offload:{parts[1]}:{rest[0]}:{parts[-1].removesuffix('.json')}"
    if parts[0] == "catalog":
        return f"content:catalog:{parts[1]}"
    if parts[0] == "releases":
        return "content:release"
    return f"{bucket}:{parts[0]}"


def s3_json_families(sample: int) -> dict[str, dict]:
    """Sample the JSON documents in the content and data buckets, grouped into families by key prefix."""
    c = ddb.client("s3")
    picks: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
    for bucket in (ddb.content_bucket(), ddb.data_bucket()):
        for page in c.get_paginator("list_objects_v2").paginate(Bucket=bucket):
            for o in page.get("Contents", []):
                if o["Key"].endswith(".json") and o["Size"] < 20_000_000:
                    seen = picks[family(bucket, o["Key"])]
                    if len(seen) < sample:
                        seen.append((bucket, o["Key"]))
    print(f"  s3 families: {len(picks)}", flush=True)

    def fetch(bk: tuple[str, str]):
        try:
            return json.loads(c.get_object(Bucket=bk[0], Key=bk[1])["Body"].read())
        except Exception as e:  # noqa: BLE001 - a profile may skip an unreadable object
            print("  skip", bk[1], e, file=sys.stderr)
            return None

    fams: dict[str, dict] = {}
    with cf.ThreadPoolExecutor(8) as ex:
        for f, keys in picks.items():
            node = new()
            for doc in ex.map(fetch, keys):
                if doc is not None:
                    observe(node, doc)
            node["_sampled"] = len(keys)
            fams[f] = node
    return fams


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".ddb_profile/dev.json")
    ap.add_argument("--s3-sample", type=int, default=150)
    ap.add_argument("--contexts", nargs="*", default=CONTEXTS)
    a = ap.parse_args()
    prof = {"env": settings.ddb_env, "profiled_at": dt.datetime.now(dt.timezone.utc).isoformat(), "tables": {}, "s3": {}}
    for ctx in a.contexts:
        prof["tables"][ctx] = scan_table(ctx)
        print(f"{ctx}: {len(prof['tables'][ctx])} item types, {sum(n['n'] for n in prof['tables'][ctx].values())} items", flush=True)
    prof["s3"] = s3_json_families(a.s3_sample)
    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(prof))
    print("wrote", p, f"{p.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
