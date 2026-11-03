"""Copy pgvector embeddings into S3 Vectors, archive them to Parquet, and verify fidelity and recall.

    python -m aws.s3.vectors copy   --env dev [--index NAME ...] [--limit N]
    python -m aws.s3.vectors verify --env dev [--index NAME ...] [--sample 300] [--k 8]

copy:   streams `key, embedding, metadata` from Neon (read-only), PutVectors in batches of 500 (no
        re-embedding), and writes a Parquet archive (key, embedding float32[], metadata json, sha256)
        to s3://<data bucket>/vectors-archive/<run>/<index>.parquet — the rollback copy required
        before pgvector columns are dropped. Manifest: logs/aws/<run>/vectors-manifest.json.
verify: baseline = the newest Parquet archive of the index (every row's sha256 recomputed) — the exact
        vectors read from Neon by `copy` — or `--baseline source` to re-read Neon (slow, ~2 GB).
        (1) count — ListVectors total == archive rows == live Neon count(*);
        (2) fidelity — GetVectors for a random sample, float32 data bit-identical, metadata equal;
        (3) recall@k — QueryVectors vs exact cosine top-k computed in NumPy over the baseline,
            within the same `filter_key` partition when the index defines one. Gate ≥ 0.95.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import io
import json
import os
import random
import time

import numpy as np

from ..common import LOG, RUN_DIR, Env, client, json_bytes, run_id, setup_logging, sha256, source, write_json
from .vector_indexes import INDEXES

BATCH = 500
RECALL_GATE = 0.95


def _parse(text: str) -> np.ndarray:
    return np.asarray(json.loads(text), dtype=np.float32)


def _select(names):
    sel = [ix for ix in INDEXES if not names or ix.name in names]
    unknown = set(names or []) - {ix.name for ix in INDEXES}
    if unknown:
        raise SystemExit(f"unknown index {unknown}")
    return sel


def _jsonable(md: dict) -> dict:
    return json.loads(json_bytes(md))


def load_source(conn, ix, limit=None):
    """Fetch vectors as binary float4 arrays (`vector::real[]`), about 3x fewer bytes than text."""
    keys, vecs, metas = [], [], []
    sql = ix.sql.replace("::text AS embedding", "::real[] AS embedding") + (f"\nLIMIT {int(limit)}" if limit else "")
    with conn.transaction():
        with conn.cursor(name=f"mbv_{os.getpid()}_{time.monotonic_ns()}", binary=True) as cur:
            cur.itersize = 2000
            cur.execute(sql)
            for row in cur:
                emb = row["embedding"]
                if emb is None:
                    continue
                v = np.asarray(emb, dtype=np.float32) if not isinstance(emb, str) else _parse(emb)
                if v.shape != (ix.dimension,):
                    raise ValueError(f"{ix.name}: key {row['key']} has dimension {v.shape}")
                keys.append(str(row["key"]))
                vecs.append(v)
                metas.append(_jsonable({k: x for k, x in ix.metadata(row).items() if x is not None}))
                if len(keys) % 10000 == 0:
                    LOG.info("  %s: %d vectors read", ix.name, len(keys))
    return keys, (np.vstack(vecs) if vecs else np.zeros((0, ix.dimension), np.float32)), metas


def copy(env: Env, names, limit, run):
    import pyarrow as pa
    import pyarrow.parquet as pq
    sv, s3 = client("s3vectors"), client("s3")
    out = []
    for ix in _select(names):
        t0 = time.time()
        # one short-lived read-only connection per index: Neon closes sessions left idle during long PUTs
        with source() as conn:
            keys, mat, metas = load_source(conn, ix, limit)
            expected = conn.execute(ix.expected_source).fetchone()["n"] if ix.expected_source and not limit else None
        LOG.info("%s: %d vectors read (expected %s) in %.0fs", ix.name, len(keys), expected, time.time() - t0)
        if len(set(keys)) != len(keys):
            raise SystemExit(f"{ix.name}: duplicate keys in source")
        batches = [range(i, min(i + BATCH, len(keys))) for i in range(0, len(keys), BATCH)]

        def put(rng):
            sv.put_vectors(vectorBucketName=env.vector_bucket, indexName=ix.name, vectors=[
                {"key": keys[i], "data": {"float32": mat[i].tolist()}, "metadata": metas[i]} for i in rng])

        with cf.ThreadPoolExecutor(8) as ex:
            list(ex.map(put, batches))
        sums = [sha256(mat[i].tobytes()) for i in range(len(keys))]
        table = pa.table({"key": keys,
                          "embedding": pa.array([m.tolist() for m in mat], type=pa.list_(pa.float32(), ix.dimension)),
                          "metadata": [json.dumps(m, sort_keys=True) for m in metas], "sha256": sums})
        buf = io.BytesIO()
        pq.write_table(table, buf, compression="zstd")
        akey = f"vectors-archive/{run}/{ix.name}.parquet"
        s3.put_object(Bucket=env.bucket("data"), Key=akey, Body=buf.getvalue(), ChecksumAlgorithm="SHA256")
        out.append({"index": ix.name, "vectors": len(keys), "expected": expected, "batches": len(batches),
                    "archive": f"s3://{env.bucket('data')}/{akey}", "archive_bytes": buf.tell(),
                    "seconds": round(time.time() - t0, 1)})
        LOG.info("%s: %d vectors written, archive %s (%.1f MB)", ix.name, len(keys), akey, buf.tell() / 1e6)
    man = {"run": run, "env": env.name, "limit": limit, "indexes": out}
    write_json(os.path.join(RUN_DIR, run, "vectors-manifest.json"), man)
    client("s3").put_object(Bucket=env.bucket("data"), Key=f"migration/{run}/vectors-manifest.json", Body=json_bytes(man))
    bad = [o for o in out if o["expected"] is not None and o["expected"] != o["vectors"]]
    if bad:
        raise SystemExit(f"count mismatch: {bad}")


def _count(env, ix) -> int:
    sv = client("s3vectors")

    def seg(i):
        n, kw = 0, dict(vectorBucketName=env.vector_bucket, indexName=ix.name, maxResults=1000, segmentCount=8, segmentIndex=i)
        while True:
            r = sv.list_vectors(**kw)
            n += len(r.get("vectors", []))
            if not r.get("nextToken"):
                return n
            kw["nextToken"] = r["nextToken"]

    with cf.ThreadPoolExecutor(8) as ex:
        return sum(ex.map(seg, range(8)))


def latest_archive(env: Env, ix) -> str | None:
    """Newest s3://<data>/vectors-archive/<run>/<index>.parquet for this index."""
    s3 = client("s3")
    keys = []
    for pg in s3.get_paginator("list_objects_v2").paginate(Bucket=env.bucket("data"), Prefix="vectors-archive/"):
        keys += [o["Key"] for o in pg.get("Contents", []) if o["Key"].endswith(f"/{ix.name}.parquet")]
    return max(keys) if keys else None


def load_archive(env: Env, ix):
    """Baseline from the Parquet archive written by `copy`; every row's sha256 is recomputed."""
    import pyarrow.parquet as pq
    key = latest_archive(env, ix)
    if key is None:
        raise SystemExit(f"{ix.name}: no archive under vectors-archive/; run copy first or use --baseline source")
    body = client("s3").get_object(Bucket=env.bucket("data"), Key=key)["Body"].read()
    t = pq.read_table(io.BytesIO(body))
    keys = t.column("key").to_pylist()
    if not keys:
        return key, [], np.zeros((0, ix.dimension), np.float32), []
    mat = np.asarray(t.column("embedding").combine_chunks().flatten(), np.float32).reshape(len(keys), ix.dimension)
    sums = t.column("sha256").to_pylist()
    bad = sum(1 for i in range(len(keys)) if sha256(mat[i].tobytes()) != sums[i])
    if bad:
        raise SystemExit(f"{ix.name}: {bad} archive rows fail their sha256")
    metas = [json.loads(m) for m in t.column("metadata").to_pylist()]
    return key, keys, mat, metas


def verify(env: Env, names, sample, k, run, baseline: str = "archive"):
    sv = client("s3vectors")
    report, failed = [], False
    for ix in _select(names):
        archive = None
        if baseline == "source":
            with source() as conn:
                keys, mat, metas = load_source(conn, ix)
            source_n = len(keys)
        else:
            archive, keys, mat, metas = load_archive(env, ix)
            with source() as conn:  # short query: live source count must equal the archive
                source_n = conn.execute(ix.expected_source).fetchone()["n"] if ix.expected_source else len(keys)
        LOG.info("%s: baseline=%s vectors=%d live_source=%d", ix.name, archive or "source", len(keys), source_n)
        if not keys:
            n = _count(env, ix)
            report.append({"index": ix.name, "source": source_n, "s3vectors": n, "ok": n == 0 and source_n == 0})
            LOG.info("%s: empty source, index holds %d", ix.name, n)
            failed |= n != 0 or source_n != 0
            continue
        n = _count(env, ix)
        rnd = random.Random(42)
        idx = rnd.sample(range(len(keys)), min(sample, len(keys)))
        # fidelity
        bad_data = bad_meta = missing = 0
        for i in range(0, len(idx), 100):
            chunk = idx[i:i + 100]
            got = {v["key"]: v for v in sv.get_vectors(vectorBucketName=env.vector_bucket, indexName=ix.name,
                                                        keys=[keys[j] for j in chunk], returnData=True,
                                                        returnMetadata=True)["vectors"]}
            for j in chunk:
                v = got.get(keys[j])
                if v is None:
                    missing += 1
                    continue
                if not np.array_equal(np.asarray(v["data"]["float32"], np.float32), mat[j]):
                    bad_data += 1
                if _jsonable(v.get("metadata") or {}) != metas[j]:
                    bad_meta += 1
        # recall@k vs exact cosine
        norm = mat / np.linalg.norm(mat, axis=1, keepdims=True)
        pos = {key: i for i, key in enumerate(keys)}
        parts = np.array([m.get(ix.filter_key) for m in metas]) if ix.filter_key else None
        hits = total = 0
        for j in idx:
            sims = norm @ norm[j]
            sims[j] = -np.inf
            kw = dict(vectorBucketName=env.vector_bucket, indexName=ix.name, topK=k + 1,
                      queryVector={"float32": mat[j].tolist()}, returnDistance=True)
            if parts is not None:
                sims[parts != parts[j]] = -np.inf
                kw["filter"] = {ix.filter_key: {"$eq": metas[j].get(ix.filter_key)}}
            kk = min(k, int(np.isfinite(sims).sum()))
            if kk == 0:
                continue
            # Tie-aware recall: a returned neighbour is a hit when it is at least as similar as the exact k-th
            # neighbour. Duplicate vectors (e.g. learning-item variants sharing text) make "the" exact top-k set
            # arbitrary among ties, so key-set intersection would count equally good answers as misses.
            kth = np.partition(-sims, kk - 1)[kk - 1] * -1
            got = [r["key"] for r in sv.query_vectors(**kw)["vectors"] if r["key"] != keys[j]][:kk]
            hits += sum(1 for g in got if g in pos and sims[pos[g]] >= kth - 1e-6)
            total += kk
        recall = hits / total if total else 1.0
        ok = n == len(keys) == source_n and not (bad_data or bad_meta or missing) and recall >= RECALL_GATE
        failed |= not ok
        row = {"index": ix.name, "baseline": archive or "source", "source": source_n, "baseline_vectors": len(keys),
               "s3vectors": n, "sample": len(idx), "missing": missing,
               "data_mismatch": bad_data, "metadata_mismatch": bad_meta, f"recall@{k}": round(recall, 4), "ok": ok}
        report.append(row)
        (LOG.info if ok else LOG.error)("%s", row)
    path = os.path.join(RUN_DIR, run, "vectors-verify.json")
    write_json(path, {"run": run, "env": env.name, "gate": RECALL_GATE, "indexes": report})
    LOG.info("vector verification %s → %s", "PASSED" if not failed else "FAILED", path)
    raise SystemExit(1 if failed else 0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["copy", "verify"])
    ap.add_argument("--env", default="dev")
    ap.add_argument("--index", nargs="*")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--sample", type=int, default=300)
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--baseline", choices=["archive", "source"], default="archive",
                    help="verify against the Parquet archive (+ live source count) or re-read Neon")
    a = ap.parse_args()
    setup_logging()
    env, run = Env(a.env), run_id()
    if a.action == "copy":
        copy(env, a.index, a.limit, run)
    else:
        verify(env, a.index, a.sample, a.k, run, a.baseline)


if __name__ == "__main__":
    main()
