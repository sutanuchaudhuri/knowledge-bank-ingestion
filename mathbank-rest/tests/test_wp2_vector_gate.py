"""WP2 vector gate: tie-aware recall, the ineligible counter, scenarios and the run-record layout (MemoryVectorStore, no AWS)."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import random
import sys
import uuid
from pathlib import Path

import numpy as np
import pytest

from mathbank_rest import content_lookup
from mathbank_rest.models.ddb.content import ContentStep
from mathbank_rest.vector_catalog import DIMENSIONS, Family, StepMeta
from mathbank_rest.vector_store import MemoryVectorStore, VectorHit, VectorItem

SPEC = importlib.util.spec_from_file_location("vector_gate", Path(__file__).resolve().parents[1] / "scripts" / "vector_gate.py")
vg = importlib.util.module_from_spec(SPEC)
sys.modules["vector_gate"] = vg
SPEC.loader.exec_module(vg)

NOW = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


def vec(seed: int) -> list[float]:
    r = random.Random(seed)
    return [r.uniform(-1, 1) for _ in range(DIMENSIONS)]


def step_meta(sid: str, skill: str, sha: str = "s") -> dict:
    return StepMeta(skill_node_id=skill, problem_id="p", solution_step_id=sid, content_sha256=sha).to_metadata()


def seed_steps(store: MemoryVectorStore, n: int = 40) -> list[tuple[str, str]]:
    """n step vectors over two skills; returns (vector key, solution_step_id)."""
    rows = []
    for i in range(n):
        key, sid = str(uuid.uuid4()), f"step-{i}"
        store.put(Family.STEP, [VectorItem(key=key, vector=vec(i), metadata=step_meta(sid, "skill-a" if i % 4 else "skill-b"))])
        rows.append((key, sid))
    return rows


def content_step(sid: str, key: str, *, eligible: bool = True, keys: list[str] | None = None) -> ContentStep:
    return ContentStep.model_validate({
        "PK": f"STEP#{sid}", "SK": "META", "type": "STEP", "book_code": "B", "concept_node_id": "c", "content_sha256": "x", "eligible": eligible,
        "global_step_index": 1, "hint_level": 1, "is_checkpoint": False, "problem_code": "P1", "problem_id": str(uuid.uuid4()),
        "skill_name": "s", "skill_node_id": "skill-a", "solution_id": str(uuid.uuid4()), "solution_part_id": "A", "solution_step_id": sid,
        "src_rev": 1, "step_index_in_part": 1, "step_type": "T", "subconcept_node_id": "sc", "technique_node_ids": [],
        "tutor_role": "CORE_BRIDGE", "updated_at": NOW,
        "vector_state": {"index": Family.STEP.index_name, "keys": keys if keys is not None else [key], "model": "m", "sha256": "z"}})


def gate(store, **kw):
    args = {"env": "ut", "sample": 25, "k": 5, "engine": "boto3", "cache_dir": None, "workers": 2, "validate_all": False}
    args.update(kw)
    return vg.gate_family(Family.STEP, store, args.pop("env"), seed=1, **args)


@pytest.fixture()
def lookup(monkeypatch):
    """content_lookup backed by a dict instead of DynamoDB: {solution_step_id: ContentStep}."""
    items: dict[str, ContentStep] = {}
    monkeypatch.setattr(content_lookup, "steps_by_id", lambda ids: {i: items[i] for i in ids if i in items})
    return items


# ------------------------------------------------------------------ pure recall

def test_tie_aware_recall_counts_equally_good_duplicates_as_hits():
    # keys a, b, c are exact duplicates and tie for the 2nd place with kk=2; an answer of {self-neighbour, c} is as good as {.., b}
    sims = np.array([-np.inf, 0.9, 0.7, 0.7, 0.7, 0.1], dtype=np.float32)
    keys = ["q", "n1", "a", "b", "c", "far"]
    pos = {k: i for i, k in enumerate(keys)}
    assert vg.tie_aware_hits(sims, 2, ["n1", "c"], pos) == 2
    assert vg.tie_aware_hits(sims, 2, ["n1", "far"], pos) == 1          # worse than the k-th exact neighbour: a miss
    assert vg.tie_aware_hits(sims, 2, ["n1", "unknown"], pos) == 1      # not in the baseline at all: a miss
    assert vg.tie_aware_hits(sims, 2, ["n1"], pos) == 1                 # fewer results than expected: the rest are misses


def test_query_recall_excludes_the_query_itself_and_respects_the_partition():
    mat = np.array([[1, 0], [0.99, 0.1], [0.5, 0.5], [0, 1], [1, 0.01]], dtype=np.float32)
    norm = mat / np.linalg.norm(mat, axis=1, keepdims=True)
    keys = ["q", "near", "mid", "orth", "other-partition"]
    pos = {k: i for i, k in enumerate(keys)}
    mask = np.array([True, True, True, True, False])
    assert vg.query_recall(norm, mask, 0, ["q", "near", "mid"], keys, pos, k=2) == (2, 2)
    assert vg.query_recall(norm, mask, 0, ["q", "near", "other-partition"], keys, pos, k=2) == (1, 2)     # out-of-partition result is a miss
    assert vg.query_recall(norm, np.array([True, False, False, False, False]), 0, ["q"], keys, pos, k=2) == (0, 0)


def test_make_filter_uses_the_most_common_value_and_the_median():
    metas = [{"competition": "IMO", "year": 2001}, {"competition": "AMC", "year": 2005}, {"competition": "AMC", "year": 2010},
             {"competition": None, "year": 2020}]
    assert vg.make_filter(vg.Scenario(name="c", key="competition", op="eq"), metas) == {"competition": {"$eq": "AMC"}}
    assert vg.make_filter(vg.Scenario(name="y", key="year", op="gte"), metas) == {"year": {"$gte": 2010}}
    assert vg.make_filter(vg.UNFILTERED, metas) is None and vg.make_filter(vg.Scenario(name="x", key="nope", op="eq"), metas) is None


# ------------------------------------------------------------------ the gate on a store

def test_an_exact_store_passes_with_recall_one_in_every_scenario(lookup):
    store = MemoryVectorStore()
    for key, sid in seed_steps(store):
        lookup[sid] = content_step(sid, key)
    row = gate(store)
    assert row.ok and row.vectors == 40 and row.recall == 1.0 and row.recall_min == 1.0
    assert [s.name for s in row.scenarios] == ["unfiltered", "skill_node_id"]
    unfiltered, skill = row.scenarios
    assert unfiltered.filter is None and unfiltered.queries == 25 and skill.filter == {"skill_node_id": {"$eq": "skill-a"}}
    assert skill.partition == 30 and row.metadata.invalid == 0 and row.metadata.checked == 25
    assert row.eligibility.ineligible == 0 and row.eligibility.checked > 0


def test_a_store_that_returns_poor_neighbours_fails_the_recall_gate(lookup):
    class Bad(MemoryVectorStore):
        def query(self, family, vector, top_k=10, filter=None):
            return sorted(super().query(family, vector, 100, filter), key=lambda h: -h.distance)[:top_k]       # farthest first

    store = Bad()
    for key, sid in seed_steps(store):
        lookup[sid] = content_step(sid, key)
    row = gate(store)
    assert not row.ok and row.recall_min < vg.RECALL_GATE and not any(s.ok for s in row.scenarios)


def test_ineligible_results_are_counted_by_reason_and_fail_the_gate(lookup):
    store = MemoryVectorStore()
    rows = seed_steps(store)
    for key, sid in rows:
        lookup[sid] = content_step(sid, key)
    lookup[rows[0][1]] = content_step(rows[0][1], rows[0][0], eligible=False)                       # withdrawn
    lookup[rows[1][1]] = content_step(rows[1][1], rows[1][0], keys=[str(uuid.uuid4())])                 # re-embedded: old key no longer current
    del lookup[rows[2][1]]                                                                          # entity gone
    row = gate(store, sample=40)
    assert not row.ok and row.recall == 1.0
    assert set(row.eligibility.reasons) == {"unpublished", "key_not_current", "item_missing"} and row.eligibility.ineligible_keys == 3
    assert row.eligibility.ineligible >= 3 and len(row.eligibility.examples) == 3


def test_invalid_stored_metadata_fails_the_gate(lookup):
    store = MemoryVectorStore()
    for key, sid in seed_steps(store, 10):
        lookup[sid] = content_step(sid, key)
    store._data[Family.STEP][next(iter(store._data[Family.STEP]))].metadata["unexpected"] = "x"    # bypasses put validation
    row = gate(store, sample=10)
    assert not row.ok and row.metadata.invalid == 1 and "unexpected" in row.metadata.examples[0]


def test_empty_families_are_skipped_and_do_not_fail():
    row = vg.gate_family(Family.PROBLEM, MemoryVectorStore(), "ut", sample=5, k=5, seed=1, engine="boto3", cache_dir=None, workers=1,
                         validate_all=False)
    assert row.skipped and row.ok and row.vectors == 0


def test_the_disk_cache_serves_the_second_run_and_refetches_a_stale_one(lookup, tmp_path):
    store = MemoryVectorStore()
    rows = seed_steps(store, 12)
    first = vg.load_family(store, Family.STEP, "ut", cache_dir=tmp_path, workers=2)
    assert len(first.keys) == 12 and (tmp_path / "ut" / "step.npz").exists()

    class Counting(MemoryVectorStore):
        gets = 0

    counting = Counting()
    counting._data = store._data
    original = counting.get

    def counted(family, keys, **kw):
        Counting.gets += len(list(keys))
        return original(family, keys, **kw)

    counting.get = counted
    again = vg.load_family(counting, Family.STEP, "ut", cache_dir=tmp_path, workers=2, spot_check=3)
    assert Counting.gets == 3 and again.keys == first.keys and np.array_equal(again.matrix, first.matrix)

    key = rows[0][0]                                                                                  # a vector changes: spot check or listing catches it
    store._data[Family.STEP].pop(key)
    store.put(Family.STEP, [VectorItem(key=key, vector=vec(999), metadata=step_meta("step-0", "skill-b"))])
    changed = vg.load_family(store, Family.STEP, "ut", cache_dir=tmp_path, workers=2, spot_check=12)
    assert np.array_equal(changed.matrix[changed.keys.index(key)], np.asarray(vec(999), np.float32))


# ------------------------------------------------------------------ record and CLI

def test_run_record_layout_and_exit_code(lookup, tmp_path, capsys):
    store = MemoryVectorStore()
    for key, sid in seed_steps(store, 20):
        lookup[sid] = content_step(sid, key)
    code = vg.main(["--families", "step", "problem", "--sample", "10", "--k", "5", "--no-cache", "--runs-dir", str(tmp_path)],
                   store_factory=lambda: store)
    out = capsys.readouterr().out
    assert code == 0 and "vector gate PASSED" in out and "skipped (empty)" in out
    (path,) = tmp_path.glob("*/vector-gate.json")
    assert path.parent.name.endswith("Z") and len(path.parent.name) == 16
    doc = json.loads(path.read_bytes())
    assert path.read_bytes() == json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()    # same encoding as the other records
    assert {"run", "env", "gate", "k", "sample", "seed", "engine", "passed", "indexes"} <= set(doc) and doc["gate"] == 0.95 and doc["passed"] is True
    step, problem = doc["indexes"]
    assert step["index"] == Family.STEP.index_name and step["ok"] is True and step["recall@5"] == 1.0 and step["vectors"] == 20
    assert {"name", "queries", "partition", "recall@5", "filter"} <= set(step["scenarios"][1])
    assert step["eligibility"]["ineligible"] == 0 and step["metadata"]["invalid"] == 0
    assert problem["skipped"] is True and problem["ok"] is True


def test_exit_code_is_one_when_a_family_fails(lookup, tmp_path):
    store = MemoryVectorStore()
    for key, sid in seed_steps(store, 10):
        lookup[sid] = content_step(sid, key, eligible=False)
    assert vg.main(["--families", "step", "--sample", "5", "--k", "3", "--no-cache", "--runs-dir", str(tmp_path)], store_factory=lambda: store) == 1
    assert json.loads(next(tmp_path.glob("*/vector-gate.json")).read_bytes())["passed"] is False


def test_a_failing_family_is_reported_not_raised(monkeypatch, tmp_path):
    store = MemoryVectorStore()
    seed_steps(store, 6)
    monkeypatch.setattr(content_lookup, "steps_by_id", lambda ids: (_ for _ in ()).throw(RuntimeError("table unavailable")))
    row = gate(store, sample=5, k=3)
    assert not row.ok and "table unavailable" in row.error


def test_hits_with_no_entity_id_are_ineligible(lookup):
    check = vg.check_eligibility(Family.STEP, [("k1", {}), ("k2", {"solution_step_id": "missing"})])
    assert check.ineligible == 2 and check.reasons == {"no_entity_id": 1, "item_missing": 1}
    assert VectorHit(key="k", distance=0.0).similarity == 1.0


# ------------------------------------------------------------------ scripts/generate_similarity_embeddings.py --source s3vectors (pure part)

GSE_SPEC = importlib.util.spec_from_file_location("gse", Path(__file__).resolve().parents[1] / "scripts" / "generate_similarity_embeddings.py")
gse = importlib.util.module_from_spec(GSE_SPEC)
sys.modules["gse"] = gse
GSE_SPEC.loader.exec_module(gse)


def hit(key: str, similarity: float) -> VectorHit:
    return VectorHit(key=key, distance=1.0 - similarity)


def test_neighbours_drop_self_rank_by_ann_order_and_apply_the_similarity_floor():
    hits = [hit("a", 1.0), hit("n1", 0.95), hit("n2", 0.85), hit("n3", 0.79), hit("n4", 0.9)]
    rows = gse.neighbours_from_hits("a", hits)
    assert [(r[1], r[3]) for r in rows] == [("n1", 1), ("n2", 2), ("n4", 4)]            # n3 is below 0.80 but still consumed rank 3
    assert rows[0][0] == "a" and rows[0][2] == pytest.approx(0.95)


def test_neighbours_keep_at_most_top_k_even_when_the_vector_itself_is_missing_from_the_hits():
    hits = [hit(f"n{i}", 0.99 - i / 100) for i in range(9)]                          # 9 results, self not among them
    rows = gse.neighbours_from_hits("a", hits)
    assert [r[3] for r in rows] == list(range(1, 9)) and "n8" not in [r[1] for r in rows]
    assert gse.neighbours_from_hits("a", []) == [] and gse.neighbours_from_hits("a", [hit("a", 1.0)]) == []
    assert [r[3] for r in gse.neighbours_from_hits("a", hits, top_k=3)] == [1, 2, 3]


def test_query_groups_split_taxonomy_by_node_type_and_skip_nodes_that_no_longer_exist():
    metas = [{"node_type": "SKILL", "lifecycle": "ACTIVE"}, {"node_type": "CONCEPT", "lifecycle": "ACTIVE"},
             {"node_type": "SKILL", "lifecycle": "DELETED"}, {"lifecycle": "ACTIVE"}, {"node_type": "SKILL", "lifecycle": "ACTIVE"}]
    groups = list(gse.query_groups(Family.TAXONOMY_NODE, metas))
    assert [idx for _, idx in groups] == [[1], [0, 4]]
    assert groups[1][0] == {"$and": [{"node_type": {"$eq": "SKILL"}}, {"lifecycle": {"$eq": "ACTIVE"}}]}
    assert list(gse.query_groups(Family.MISCONCEPTION, [{}, {}])) == [(None, [0, 1])]


def test_similarity_rows_run_through_the_adapter_in_batches():
    from mathbank_rest.vector_catalog import MisconceptionMeta, TaxonomyNodeMeta
    store = MemoryVectorStore()
    base = vec(1)
    near = [x * 1.01 + 0.001 for x in base]
    store.put(Family.MISCONCEPTION, [
        VectorItem(key=k, vector=v, metadata=MisconceptionMeta(lifecycle="ACTIVE").to_metadata())
        for k, v in (("m1", base), ("m2", near), ("m3", [-x for x in base]))])
    keys, matrix, metas = gse.fetch_vectors(store, Family.MISCONCEPTION, workers=2)
    rows = gse.similarity_rows(Family.MISCONCEPTION, keys, matrix, metas, store, "boto3", batch=2)
    assert {(a, b) for a, b, _, _ in rows} == {("m1", "m2"), ("m2", "m1")}              # m3 is the opposite vector: below the floor
    assert all(s > 0.99 for _, _, s, _ in rows)

    store.put(Family.TAXONOMY_NODE, [
        VectorItem(key="t1", vector=base, metadata=TaxonomyNodeMeta(node_type="SKILL", lifecycle="ACTIVE").to_metadata()),
        VectorItem(key="t2", vector=near, metadata=TaxonomyNodeMeta(node_type="CONCEPT", lifecycle="ACTIVE").to_metadata())])
    keys, matrix, metas = gse.fetch_vectors(store, Family.TAXONOMY_NODE)
    assert gse.similarity_rows(Family.TAXONOMY_NODE, keys, matrix, metas, store, "boto3") == []   # near-identical, but different node types
