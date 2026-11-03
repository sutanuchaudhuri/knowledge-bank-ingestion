"""WP2 acceptance gate, run through the vector adapter (requirement 71 WP2; requirement 70 C6 §8b).

    python scripts/vector_gate.py [--families step problem] [--sample 300] [--k 8] [--engine auto|boto3|bodo] [--no-cache]
    make vector-gate ARGS="--families step --sample 100"          (DDB_ENV=dev by default, read-only)

Per family (problem, solution, step, learning-item, taxonomy-search, misconception, taxonomy-node; empty ones are skipped):

1. **metadata** - stored metadata of a sample validates against the family's pydantic model (``--validate-all``: every vector);
2. **recall** - a deterministic sample of stored vectors is queried with ``bulk_query`` (unfiltered, and with the family's real
   filters: competition / year for problem, skill_node_id for step, node_type for taxonomy ...); the exact top-k is computed
   in NumPy over the vectors of the scenario's filter partition, fetched with ``keys()`` + ``get`` and cached under
   ``.vector_gate_cache/``. **Tie-aware recall@k** exactly as ``mathbank-db/aws/s3/vectors.py verify``: a returned neighbour is
   a hit when it is at least as similar as the exact k-th neighbour (duplicate vectors make "the" top-k set arbitrary);
3. **eligibility** - for families with an ``mb-content`` entity (problem, step, learning-item, taxonomy-search) every returned
   hit is re-checked with ``content_lookup.hit_is_current``; ineligible results must be zero.

The run record goes to ``mathbank-db/aws/runs/<UTC timestamp>/vector-gate.json`` (same layout as ``vectors-verify.json``); the
exit code is 1 when any recall < 0.95, any ineligible result, or any invalid metadata.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures as cf
import dataclasses
import datetime as dt
import functools
import json
import logging
import random
import sys
import time
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, Field, ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mathbank_rest import content_lookup
from mathbank_rest.config import settings
from mathbank_rest.vector_bulk import Engine, bulk_query
from mathbank_rest.vector_catalog import DIMENSIONS, Family, meta_model
from mathbank_rest.vector_store import (
    S3VectorsStore,
    VectorStore,
    get_vector_store,
    matches,
    uses_s3_vectors,
    vf,
)

LOG = logging.getLogger("vector_gate")
RECALL_GATE = 0.95
DEFAULT_K = 8
DEFAULT_SAMPLE = 300
SEED = 42
TIE_EPS = 1e-6
FETCH_BATCH = 100
CACHE_DIR = ROOT / ".vector_gate_cache"
RUNS_DIR = ROOT.parent / "mathbank-db" / "aws" / "runs"

GATE_FAMILIES: tuple[Family, ...] = (Family.PROBLEM, Family.SOLUTION, Family.STEP, Family.LEARNING_ITEM, Family.TAXONOMY_SEARCH,
                                     Family.MISCONCEPTION, Family.TAXONOMY_NODE)


# ------------------------------------------------------------------ scenarios and entities

class Scenario(BaseModel):
    """One query setting: ``op`` None is unfiltered; ``eq`` filters on the most common value of ``key``; ``gte`` on its median."""

    name: str
    key: str | None = None
    op: Literal["eq", "gte"] | None = None


UNFILTERED = Scenario(name="unfiltered")
SCENARIOS: dict[Family, list[Scenario]] = {
    Family.PROBLEM: [UNFILTERED, Scenario(name="competition", key="competition", op="eq"), Scenario(name="year>=median", key="year", op="gte")],
    Family.SOLUTION: [UNFILTERED, Scenario(name="competition", key="competition", op="eq")],
    Family.STEP: [UNFILTERED, Scenario(name="skill_node_id", key="skill_node_id", op="eq")],
    Family.LEARNING_ITEM: [UNFILTERED, Scenario(name="kind", key="kind", op="eq")],
    Family.TAXONOMY_SEARCH: [UNFILTERED, Scenario(name="node_type", key="node_type", op="eq")],
    Family.MISCONCEPTION: [UNFILTERED, Scenario(name="lifecycle", key="lifecycle", op="eq")],
    Family.TAXONOMY_NODE: [UNFILTERED, Scenario(name="node_type", key="node_type", op="eq")],
}


class Entity(BaseModel):
    """How a vector hit maps to its ``mb-content`` item: the metadata key naming the entity and the ``content_lookup`` loader."""

    meta_key: str
    loader: str
    search: bool = False


ENTITIES: dict[Family, Entity] = {
    Family.PROBLEM: Entity(meta_key="canonical_code", loader="problems_by_code"),
    Family.STEP: Entity(meta_key="solution_step_id", loader="steps_by_id"),
    Family.LEARNING_ITEM: Entity(meta_key="learning_item_id", loader="learning_items_by_id"),
    Family.TAXONOMY_SEARCH: Entity(meta_key="taxonomy_node_id", loader="taxonomy_nodes_by_id", search=True),
}


# ------------------------------------------------------------------ result models

class ScenarioResult(BaseModel):
    name: str
    filter: dict | None = None
    partition: int = 0
    queries: int = 0
    hits: int = 0
    total: int = 0
    recall: float | None = None
    ok: bool = True
    note: str | None = None


class MetadataCheck(BaseModel):
    checked: int = 0
    invalid: int = 0
    examples: list[str] = Field(default_factory=list)


class EligibilityCheck(BaseModel):
    checked: int = 0                      # returned hits re-checked (every result of every query)
    ineligible: int = 0
    ineligible_keys: int = 0              # distinct vector keys among them
    reasons: dict[str, int] = Field(default_factory=dict)
    examples: list[str] = Field(default_factory=list)


class FamilyResult(BaseModel):
    index: str
    family: str
    vectors: int = 0
    skipped: bool = False
    ok: bool = True
    error: str | None = None
    recall: float | None = None           # aggregate over the scenarios
    recall_min: float | None = None       # the gate applies to every scenario
    metadata: MetadataCheck = Field(default_factory=MetadataCheck)
    scenarios: list[ScenarioResult] = Field(default_factory=list)
    eligibility: EligibilityCheck | None = None
    seconds: float = 0.0


class GateRecord(BaseModel):
    run: str
    env: str
    gate: float
    k: int
    sample: int
    seed: int
    engine: str
    passed: bool
    indexes: list[FamilyResult]


# ------------------------------------------------------------------ recall (pure)

def kth_similarity(sims: np.ndarray, kk: int) -> float:
    """The kk-th largest similarity (``sims`` holds -inf for excluded vectors)."""
    return float(np.partition(-sims, kk - 1)[kk - 1] * -1)


def tie_aware_hits(sims: np.ndarray, kk: int, got: Sequence[str], pos: dict[str, int]) -> int:
    """Returned keys that are at least as similar as the exact kk-th neighbour (so ties never count as misses)."""
    kth = kth_similarity(sims, kk)
    return sum(1 for g in list(got)[:kk] if g in pos and sims[pos[g]] >= kth - TIE_EPS)


def query_recall(norm: np.ndarray, mask: np.ndarray, j: int, got: Sequence[str], keys: Sequence[str], pos: dict[str, int],
                 k: int) -> tuple[int, int]:
    """(hits, expected) for query ``j``: neighbours within ``mask`` (the filter partition), the query itself excluded."""
    sims = norm @ norm[j]
    sims[~mask] = -np.inf
    sims[j] = -np.inf
    kk = min(k, int(np.isfinite(sims).sum()))
    if kk == 0:
        return 0, 0
    return tie_aware_hits(sims, kk, [g for g in got if g != keys[j]], pos), kk


def make_filter(spec: Scenario, metas: Sequence[dict[str, Any]]) -> dict | None:
    """The scenario's filter built from the stored metadata, or None when there is nothing to filter on."""
    if spec.op is None or spec.key is None:
        return None
    values = [m[spec.key] for m in metas if m.get(spec.key) is not None and not isinstance(m[spec.key], list)]
    if not values:
        return None
    if spec.op == "eq":
        top = collections.Counter(values).most_common()
        best = max(c for _, c in top)
        return vf.eq(spec.key, min((v for v, c in top if c == best), key=str))
    nums = sorted(v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool))
    return vf.gte(spec.key, nums[len(nums) // 2]) if nums else None


# ------------------------------------------------------------------ vectors: keys() + get, cached on disk

@dataclasses.dataclass
class FamilyData:
    keys: list[str]
    matrix: np.ndarray                    # float32 (n, 1536)
    metas: list[dict[str, Any]]

    @functools.cached_property
    def norm(self) -> np.ndarray:
        n = np.linalg.norm(self.matrix, axis=1, keepdims=True)
        return self.matrix / np.where(n == 0, 1.0, n)


def _fetch(store: VectorStore, family: Family, keys: Sequence[str], workers: int) -> dict[str, tuple[np.ndarray, dict]]:
    def one(chunk: Sequence[str]):
        for attempt in range(4):
            try:
                return store.get(family, chunk, with_data=True)
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(0.5 * 2 ** attempt)

    chunks = [keys[i:i + FETCH_BATCH] for i in range(0, len(keys), FETCH_BATCH)]
    out: dict[str, tuple[np.ndarray, dict]] = {}
    with cf.ThreadPoolExecutor(max(1, min(workers, len(chunks) or 1))) as ex:
        for done, items in enumerate(ex.map(one, chunks), 1):
            for it in items:
                if it.vector is not None:
                    out[it.key] = (np.asarray(it.vector, np.float32), dict(it.metadata))
            if done % 50 == 0:
                LOG.info("  %s: %d/%d keys fetched", family.value, min(done * FETCH_BATCH, len(keys)), len(keys))
    return out


def _cache_path(cache_dir: Path, env: str, family: Family) -> Path:
    return cache_dir / env / f"{family.value}.npz"


def _read_cache(path: Path) -> dict[str, tuple[np.ndarray, dict]]:
    if not path.exists():
        return {}
    with np.load(path, allow_pickle=False) as z:
        keys, mat, metas = z["keys"].tolist(), z["vectors"], z["metadata"].tolist()
    return {k: (mat[i], json.loads(metas[i])) for i, k in enumerate(keys)}


def _write_cache(path: Path, data: FamilyData) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, keys=np.array(data.keys, dtype=str), vectors=data.matrix,
             metadata=np.array([json.dumps(m, sort_keys=True) for m in data.metas], dtype=str))


def load_family(store: VectorStore, family: Family, env: str, *, cache_dir: Path | None = CACHE_DIR, workers: int = 8,
                spot_check: int = 20) -> FamilyData:
    """Every vector of the family (``keys()`` + ``get``). Cached vectors are reused for keys still listed, after a spot check
    that cached vectors and metadata still equal the live ones; anything missing is fetched."""
    listed = sorted(store.keys(family))
    listed_set = set(listed)
    cached = _read_cache(_cache_path(cache_dir, env, family)) if cache_dir else {}
    cached = {k: v for k, v in cached.items() if k in listed_set}
    if cached:
        probe = random.Random(SEED).sample(sorted(cached), min(spot_check, len(cached)))
        live = _fetch(store, family, probe, workers)
        if any(k not in live or not np.array_equal(live[k][0], cached[k][0]) or live[k][1] != cached[k][1] for k in probe):
            LOG.info("%s: cache is stale, refetching", family.value)
            cached = {}
    missing = [k for k in listed if k not in cached]
    if missing:
        LOG.info("%s: fetching %d of %d vectors", family.value, len(missing), len(listed))
        cached.update(_fetch(store, family, missing, workers))
    keys = [k for k in listed if k in cached]
    data = FamilyData(keys=keys, matrix=np.vstack([cached[k][0] for k in keys]) if keys else np.zeros((0, DIMENSIONS), np.float32),
                      metas=[cached[k][1] for k in keys])
    if cache_dir and missing and keys:
        _write_cache(_cache_path(cache_dir, env, family), data)
    return data


# ------------------------------------------------------------------ the three checks

def check_metadata(family: Family, data: FamilyData, sample: int, *, seed: int = SEED, validate_all: bool = False) -> MetadataCheck:
    model = meta_model(family)
    n = len(data.keys)
    idx = range(n) if validate_all else random.Random(f"{seed}:{family.value}:metadata").sample(range(n), min(sample, n))
    out = MetadataCheck()
    for j in idx:
        out.checked += 1
        try:
            model.model_validate(data.metas[j])
        except ValidationError as exc:
            out.invalid += 1
            if len(out.examples) < 3:
                e = exc.errors()[0]
                out.examples.append(f"{data.keys[j]}: {'.'.join(map(str, e['loc']))}: {e['msg']}")
    return out


class ScenarioRun(BaseModel):
    result: ScenarioResult
    returned: list[tuple[str, dict[str, Any]]] = Field(default_factory=list)   # (key, metadata) of every returned hit


def run_scenario(family: Family, store: VectorStore, data: FamilyData, spec: Scenario, *, sample: int, k: int, seed: int,
                 engine: Engine) -> ScenarioRun:
    flt = make_filter(spec, data.metas)
    res = ScenarioResult(name=spec.name, filter=flt)
    if spec.op is not None and flt is None:
        res.note = f"no {spec.key} values stored; scenario skipped"
        return ScenarioRun(result=res)
    mask = np.fromiter((matches(m, flt) for m in data.metas), dtype=bool, count=len(data.keys))
    members = np.flatnonzero(mask)
    res.partition = len(members)
    if len(members) < 2:
        res.note = "fewer than two vectors in the partition; scenario skipped"
        return ScenarioRun(result=res)
    pos = {key: i for i, key in enumerate(data.keys)}
    idx = [int(j) for j in random.Random(f"{seed}:{family.value}:{spec.name}").sample(list(members), min(sample, len(members)))]
    answers = bulk_query(family, [data.matrix[j].tolist() for j in idx], top_k=k + 1, filter=flt, engine=engine, store=store)
    returned: list[tuple[str, dict[str, Any]]] = []
    norm = data.norm
    for j, hits in zip(idx, answers, strict=True):
        returned.extend((h.key, h.metadata) for h in hits)
        h, n = query_recall(norm, mask, j, [x.key for x in hits], data.keys, pos, k)
        res.hits, res.total = res.hits + h, res.total + n
        res.queries += 1 if n else 0
    res.recall = round(res.hits / res.total, 4) if res.total else 1.0
    res.ok = res.recall >= RECALL_GATE
    return ScenarioRun(result=res, returned=returned)


def check_eligibility(family: Family, returned: Iterable[tuple[str, dict[str, Any]]]) -> EligibilityCheck:
    """Re-check every returned hit with ``content_lookup.hit_is_current`` (the read path's own rule)."""
    ent = ENTITIES[family]
    hits = list(returned)
    ids = {m.get(ent.meta_key) for _, m in hits if m.get(ent.meta_key)}
    items = getattr(content_lookup, ent.loader)(sorted(ids)) if ids else {}
    out, bad_keys, reasons = EligibilityCheck(checked=len(hits)), set(), collections.Counter()
    for key, meta in hits:
        entity = meta.get(ent.meta_key)
        item = items.get(entity) if entity else None
        if content_lookup.hit_is_current(item, key, search=ent.search):
            continue
        reason = ("no_entity_id" if not entity else "item_missing" if item is None
                  else "unpublished" if not content_lookup.is_published(item) else "key_not_current")
        out.ineligible += 1
        reasons[reason] += 1
        if key not in bad_keys and len(out.examples) < 5:
            out.examples.append(f"{key} ({entity}): {reason}")
        bad_keys.add(key)
    out.ineligible_keys, out.reasons = len(bad_keys), dict(reasons)
    return out


def gate_family(family: Family, store: VectorStore, env: str, *, sample: int, k: int, seed: int, engine: Engine,
                cache_dir: Path | None, workers: int, validate_all: bool,
                scenarios: Sequence[Scenario] | None = None) -> FamilyResult:
    t0 = time.time()
    out = FamilyResult(index=family.index_name, family=family.value)
    try:
        data = load_family(store, family, env, cache_dir=cache_dir, workers=workers)
        out.vectors = len(data.keys)
        if not data.keys:
            out.skipped = True
            return out
        out.metadata = check_metadata(family, data, sample, seed=seed, validate_all=validate_all)
        returned: list[tuple[str, dict[str, Any]]] = []
        for spec in scenarios or SCENARIOS[family]:
            run = run_scenario(family, store, data, spec, sample=sample, k=k, seed=seed, engine=engine)
            out.scenarios.append(run.result)
            returned.extend(run.returned)
        scored = [s for s in out.scenarios if s.recall is not None]
        total = sum(s.total for s in scored)
        out.recall = round(sum(s.hits for s in scored) / total, 4) if total else None
        out.recall_min = min((s.recall for s in scored if s.recall is not None), default=None)
        if family in ENTITIES:
            out.eligibility = check_eligibility(family, returned)
        out.ok = (out.metadata.invalid == 0 and all(s.ok for s in out.scenarios)
                  and (out.eligibility is None or out.eligibility.ineligible == 0))
    except Exception as exc:
        LOG.exception("%s: gate error", family.value)
        out.ok, out.error = False, f"{type(exc).__name__}: {str(exc)[:300]}"
    out.seconds = round(time.time() - t0, 1)
    return out


def run_gate(store: VectorStore, families: Sequence[Family] = GATE_FAMILIES, *, env: str, sample: int = DEFAULT_SAMPLE, k: int = DEFAULT_K,
             seed: int = SEED, engine: Engine = "auto", cache_dir: Path | None = CACHE_DIR, workers: int = 8, validate_all: bool = False,
             run: str | None = None) -> GateRecord:
    rows = [gate_family(f, store, env, sample=sample, k=k, seed=seed, engine=engine, cache_dir=cache_dir, workers=workers,
                        validate_all=validate_all) for f in families]
    return GateRecord(run=run or dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ"), env=env, gate=RECALL_GATE, k=k, sample=sample,
                      seed=seed, engine=engine, passed=all(r.ok for r in rows), indexes=rows)


def write_record(record: GateRecord, runs_dir: Path = RUNS_DIR) -> Path:
    """Same encoding as the other run records: sorted keys, compact, UTF-8; ``recall@<k>`` keys like ``vectors-verify.json``."""
    doc = record.model_dump(mode="json", exclude_none=True)
    for row in doc["indexes"]:
        for target in (row, *row.get("scenarios", [])):
            if "recall" in target:
                target[f"recall@{record.k}"] = target.pop("recall")
    path = runs_dir / record.run / "vector-gate.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())
    return path


# ------------------------------------------------------------------ CLI

def format_table(record: GateRecord) -> str:
    lines = [f"{'family':<16}{'vectors':>8} {'meta bad':>8} {'recall@' + str(record.k):>9} {'min':>7} {'inelig':>9}  scenarios", "-" * 110]
    for r in record.indexes:
        if r.skipped:
            lines.append(f"{r.family:<16}{0:>8}  skipped (empty)")
            continue
        inel = "-" if r.eligibility is None else f"{r.eligibility.ineligible}/{r.eligibility.checked}"
        scen = ", ".join(f"{s.name}={s.recall if s.recall is not None else 'n/a'} ({s.queries}q of {s.partition})" for s in r.scenarios)
        rec = "n/a" if r.recall is None else f"{r.recall:.4f}"
        mn = "n/a" if r.recall_min is None else f"{r.recall_min:.4f}"
        flag = (f"  ERROR {r.error}" if r.error else "") + ("" if r.ok else "  FAILED")
        lines.append(f"{r.family:<16}{r.vectors:>8} {r.metadata.invalid:>8} {rec:>9} {mn:>7} {inel:>9}  {scen}{flag}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None, *, store_factory: Callable[[], VectorStore] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--families", nargs="*", choices=[f.value for f in GATE_FAMILIES], help="default: all gate families")
    ap.add_argument("--sample", type=int, default=DEFAULT_SAMPLE, help="query vectors per scenario and metadata sample size")
    ap.add_argument("--k", type=int, default=DEFAULT_K)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--engine", choices=["auto", "boto3", "bodo"], default="auto")
    ap.add_argument("--workers", type=int, default=8, help="parallel GetVectors calls while loading a family")
    ap.add_argument("--no-cache", action="store_true", help="do not read or write .vector_gate_cache/")
    ap.add_argument("--validate-all", action="store_true", help="validate the metadata of every vector, not just the sample")
    ap.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    store = store_factory() if store_factory else (get_vector_store() if uses_s3_vectors() else S3VectorsStore())
    engine: Engine = args.engine if isinstance(store, S3VectorsStore) else "boto3"
    families = [Family(f) for f in args.families] if args.families else list(GATE_FAMILIES)
    record = run_gate(store, families, env=settings.ddb_env, sample=args.sample, k=args.k, seed=args.seed, engine=engine,
                      cache_dir=None if args.no_cache else CACHE_DIR, workers=args.workers, validate_all=args.validate_all)
    path = write_record(record, args.runs_dir)
    print(format_table(record))
    print(f"\nvector gate {'PASSED' if record.passed else 'FAILED'} (recall gate {RECALL_GATE}, k={record.k}, env={record.env}) -> {path}")
    return 0 if record.passed else 1


if __name__ == "__main__":
    sys.exit(main())
