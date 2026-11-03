"""Profile the PK/SK *shapes* of every item type (e.g. ``STUDENT#{uuid}`` / ``OUTCOME#{uuid}``) so the generated
models can enforce key patterns. Key-only projection keeps the scan light.

    python scripts/ddb_models/keys.py --out .ddb_profile/dev_keys.json
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from infer import CONTEXTS, TS, UUID  # noqa: E402

from mathbank_rest.stores import ddb  # noqa: E402

HEX = re.compile(r"^[0-9a-f]{16,}$")
NUM = re.compile(r"^-?\d+$")
MAX_LITERALS = 24


def seg_class(s: str) -> str:
    if UUID.match(s):
        return "{uuid}"
    if HEX.match(s):
        return "{hex}"
    if NUM.match(s):
        return "{n}"
    if TS.match(s):
        return "{ts}"
    return s if len(s) <= 40 else "{*}"


def add(stats: dict, attr: str, value: str) -> None:
    segs = value.split("#")
    a = stats.setdefault(attr, {"nseg": {}, "pos": {}})
    a["nseg"][len(segs)] = a["nseg"].get(len(segs), 0) + 1
    for i, s in enumerate(segs):
        p = a["pos"].setdefault(f"{len(segs)}:{i}", {})
        c = seg_class(s)
        if c in p or len(p) < MAX_LITERALS:
            p[c] = p.get(c, 0) + 1
        else:
            p["{*}"] = p.get("{*}", 0) + 1


def merge(into: dict, other: dict) -> None:
    for attr, o in other.items():
        a = into.setdefault(attr, {"nseg": {}, "pos": {}})
        for k, v in o["nseg"].items():
            a["nseg"][k] = a["nseg"].get(k, 0) + v
        for pos, vals in o["pos"].items():
            p = a["pos"].setdefault(pos, {})
            for c, n in vals.items():
                p[c] = p.get(c, 0) + n


def scan(ctx: str, segments: int = 12) -> dict:
    lock = threading.Lock()
    out: dict[str, dict] = {}

    def run(seg: int) -> None:
        local: dict[str, dict] = {}
        c = ddb.client()
        kw = {"TableName": ddb.table_name(ctx), "TotalSegments": segments, "Segment": seg,
              "ProjectionExpression": "PK, SK, #t", "ExpressionAttributeNames": {"#t": "type"}}
        while True:
            page = c.scan(**kw)
            for raw in page["Items"]:
                t = raw.get("type", {}).get("S", "?")
                stats = local.setdefault(t, {})
                add(stats, "PK", raw["PK"]["S"])
                add(stats, "SK", raw["SK"]["S"])
            if "LastEvaluatedKey" not in page:
                break
            kw["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        with lock:
            for t, st in local.items():
                merge(out.setdefault(t, {}), st)

    with cf.ThreadPoolExecutor(segments) as ex:
        list(ex.map(run, range(segments)))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".ddb_profile/dev_keys.json")
    a = ap.parse_args()
    res = {}
    for ctx in CONTEXTS:
        res[ctx] = scan(ctx)
        print(ctx, len(res[ctx]), flush=True)
    Path(a.out).write_text(json.dumps(res))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
