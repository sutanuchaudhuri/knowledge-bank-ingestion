"""Vector catalogue and adapter (requirement 71 §2.5): drift against the migration catalogue, filter semantics,
the in-memory exact store, the S3 Vectors store over a fake client, limits and error mapping."""
from __future__ import annotations

import inspect
import math
import random
import re
import sys
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from mathbank_rest.stores.errors import NotFound, StoreUnavailable, ValidationFailed
from mathbank_rest.vector_catalog import (
    DIMENSIONS,
    META_MODELS,
    Family,
    ProblemMeta,
    StepMeta,
    meta_model,
)
from mathbank_rest.vector_store import (
    MemoryVectorStore,
    S3VectorsStore,
    VectorHit,
    VectorItem,
    check_filter,
    cosine_distance,
    filter_keys,
    get_vector_store,
    matches,
    set_vector_store_for_tests,
    uses_s3_vectors,
    vf,
)

DB_AWS = Path(__file__).resolve().parents[2] / "mathbank-db"


def vec(seed: int) -> list[float]:
    r = random.Random(seed)
    return [r.uniform(-1, 1) for _ in range(DIMENSIONS)]


def problem_meta(code: str, comp: str = "IMO", year: int | None = 2010) -> dict:
    return ProblemMeta(competition=comp, year=year, problem_id="11111111-1111-1111-1111-111111111111", chunk_kind="FULL",
                       canonical_code=code, content_sha256="a" * 64, chunk_ordinal=0, representation_id="r1").to_metadata()


# ------------------------------------------------------------------ catalogue

def test_every_family_has_a_metadata_model_and_an_index_name():
    assert set(META_MODELS) == set(Family)
    assert Family.PROBLEM.index_name == "problem-te3small-1536-v1"
    assert all(f.index_name.endswith("te3small-1536-v1") for f in Family)


def test_catalogue_matches_the_migration_catalogue():
    """The REST catalogue and mathbank-db/aws/s3/vector_indexes.py describe the same indexes, metadata keys and filterability."""
    sys.path.insert(0, str(DB_AWS))
    try:
        from aws.s3 import vector_indexes as vi
    except Exception as exc:  # noqa: BLE001 - the migration toolkit needs optional deps
        pytest.skip(f"migration catalogue not importable: {exc}")
    finally:
        sys.path.remove(str(DB_AWS))
    by_name = {ix.name: ix for ix in vi.INDEXES}
    assert set(by_name) == {f.index_name for f in Family}
    for fam in Family:
        ix = by_name[fam.index_name]
        keys = set(re.findall(r'"(\w+)":', inspect.getsource(ix.metadata)))
        model = meta_model(fam)
        assert set(model.model_fields) == keys, f"{fam.value}: metadata keys differ"
        assert set(model.NON_FILTERABLE) == set(ix.non_filterable), f"{fam.value}: non-filterable keys differ"
        assert ix.dimension == DIMENSIONS and ix.metric == "cosine"


def test_to_metadata_drops_none_and_empty_lists():
    m = StepMeta(problem_id="p", solution_step_id="s", content_sha256="c", technique_node_ids=[], skill_node_id=None)
    assert m.to_metadata() == {"problem_id": "p", "solution_step_id": "s", "content_sha256": "c"}


def test_metadata_models_are_strict():
    with pytest.raises(Exception):
        ProblemMeta(**{**problem_meta("X"), "year": "2010"})
    with pytest.raises(Exception):
        ProblemMeta(**{**problem_meta("X"), "surprise": 1})


# ------------------------------------------------------------------ filters

def test_filter_keys_and_operators_are_validated():
    f = vf.and_(vf.eq("competition", "IMO"), vf.or_(vf.gte("year", 2000), vf.exists("year", False)))
    assert filter_keys(f) == {"competition", "year"}
    for bad in ({}, {"$and": []}, {"$nor": [{"a": {"$eq": 1}}]}, {"year": {"$like": 1}}, []):
        with pytest.raises(ValidationFailed):
            filter_keys(bad)  # type: ignore[arg-type]


def test_filter_on_a_non_filterable_key_is_rejected_before_the_call():
    check_filter(Family.PROBLEM, vf.eq("competition", "IMO"))
    with pytest.raises(ValidationFailed, match="canonical_code"):
        check_filter(Family.PROBLEM, vf.eq("canonical_code", "X"))
    with pytest.raises(ValidationFailed):
        check_filter(Family.ARTIFACT_PUBLIC, vf.eq("nonsense", 1))


def test_filter_evaluation_matches_the_service_semantics():
    meta = {"year": 2010, "competition": "IMO", "techs": ["A", "B"], "flag": True}
    assert matches(meta, vf.eq("competition", "IMO")) and not matches(meta, vf.eq("competition", "AMC"))
    assert matches(meta, vf.gte("year", 2010)) and not matches(meta, vf.gt("year", 2010))
    assert matches(meta, vf.eq("techs", "B")) and matches(meta, vf.in_("techs", ["Z", "A"]))      # any element
    assert not matches(meta, vf.nin("techs", ["A"])) and matches(meta, vf.nin("techs", ["Z"]))
    assert matches(meta, vf.and_(vf.eq("flag", True), vf.lt("year", 2020)))
    assert matches(meta, vf.or_(vf.eq("competition", "AMC"), vf.eq("year", 2010)))
    assert matches(meta, vf.exists("year")) and matches(meta, vf.exists("absent", False))
    assert not matches(meta, vf.eq("absent", 1)) and matches(meta, vf.ne("absent", 1))
    assert not matches({"year": "2010"}, vf.gte("year", 2000))                                   # numbers only
    assert vf.and_(None, None) is None and vf.and_(vf.eq("a", 1)) == {"a": {"$eq": 1}}


# ------------------------------------------------------------------ vector items

def test_vector_item_validation():
    VectorItem(key="k", vector=vec(1), metadata=problem_meta("X"))
    for bad in ({"vector": [0.0] * DIMENSIONS}, {"vector": vec(1)[:10]}, {"vector": [math.nan] + vec(1)[1:]}, {"key": ""}):
        with pytest.raises(Exception):
            VectorItem(**{"key": "k", "vector": vec(1), **bad})


def test_put_validates_metadata_against_the_family_model():
    st = MemoryVectorStore()
    with pytest.raises(ValidationFailed, match="metadata of 'k' invalid"):
        st.put(Family.PROBLEM, [VectorItem(key="k", vector=vec(1), metadata={"competition": "IMO"})])   # missing required keys
    with pytest.raises(ValidationFailed, match="needs the vector"):
        st.put(Family.PROBLEM, [VectorItem(key="k", metadata=problem_meta("X"))])
    with pytest.raises(ValidationFailed, match="2 KB"):
        big = ProblemMeta(**{**problem_meta("X"), "competition": "x" * 3000}).to_metadata()
        st.put(Family.PROBLEM, [VectorItem(key="k", vector=vec(1), metadata=big)])


# ------------------------------------------------------------------ memory store (exact)

def test_memory_store_is_exact_filtered_and_ordered():
    st = MemoryVectorStore()
    items = [VectorItem(key=f"k{i}", vector=vec(i), metadata=problem_meta(f"P{i}", "IMO" if i % 2 else "AMC", 2000 + i)) for i in range(20)]
    assert st.put(Family.PROBLEM, items) == 20
    q = vec(3)
    hits = st.query(Family.PROBLEM, q, top_k=5)
    assert hits[0].key == "k3" and hits[0].distance == pytest.approx(0.0, abs=1e-9) and hits[0].similarity == pytest.approx(1.0)
    assert [h.distance for h in hits] == sorted(h.distance for h in hits)
    brute = sorted(range(20), key=lambda i: (cosine_distance(q, vec(i)), f"k{i}"))[:5]
    assert [h.key for h in hits] == [f"k{i}" for i in brute]
    only = st.query(Family.PROBLEM, q, top_k=50, filter=vf.and_(vf.eq("competition", "IMO"), vf.gte("year", 2010)))
    assert only and all(h.metadata["competition"] == "IMO" and h.metadata["year"] >= 2010 for h in only)
    assert {h.key for h in only} == {f"k{i}" for i in range(20) if i % 2 and 2000 + i >= 2010}


def test_memory_store_get_delete_keys():
    st = MemoryVectorStore()
    st.put(Family.PROBLEM, [VectorItem(key=f"k{i}", vector=vec(i), metadata=problem_meta(f"P{i}")) for i in range(3)])
    assert [i.key for i in st.get(Family.PROBLEM, ["k1", "nope", "k1"])] == ["k1"]
    assert st.get(Family.PROBLEM, ["k1"], with_data=False)[0].vector is None
    assert st.delete(Family.PROBLEM, ["k1", "zzz"]) == 2
    assert list(st.keys(Family.PROBLEM)) == ["k0", "k2"]
    assert st.query(Family.STEP, vec(1)) == []                                                  # other family is empty


def test_query_limits_and_dimensions():
    st = MemoryVectorStore()
    for k in (0, 101):
        with pytest.raises(ValidationFailed, match="top_k"):
            st.query(Family.PROBLEM, vec(1), top_k=k)
    with pytest.raises(ValidationFailed, match="dimensions"):
        st.query(Family.PROBLEM, [1.0, 2.0])


# ------------------------------------------------------------------ S3 Vectors store over a fake client

class FakeS3Vectors:
    """Records calls; behaves like the service for the limits the adapter must respect."""

    def __init__(self):
        self.calls = []
        self.fail: ClientError | None = None
        self.vectors: dict[str, dict] = {}

    def _rec(self, op, kw):
        self.calls.append((op, kw))
        if self.fail:
            raise self.fail

    def put_vectors(self, **kw):
        self._rec("put", kw)
        assert len(kw["vectors"]) <= 500
        for v in kw["vectors"]:
            self.vectors[v["key"]] = v

    def delete_vectors(self, **kw):
        self._rec("delete", kw)
        assert len(kw["keys"]) <= 500

    def get_vectors(self, **kw):
        self._rec("get", kw)
        assert len(kw["keys"]) <= 100
        return {"vectors": [{"key": k, "data": {"float32": [0.5] * DIMENSIONS}, "metadata": {"a": "b"}} for k in kw["keys"]]}

    def query_vectors(self, **kw):
        self._rec("query", kw)
        return {"vectors": [{"key": "k1", "distance": 0.25, "metadata": {"competition": "IMO"}}]}

    def list_vectors(self, **kw):
        self._rec("list", kw)
        if kw.get("nextToken"):
            return {"vectors": [{"key": "b"}]}
        return {"vectors": [{"key": "a"}], "nextToken": "t"}


def err(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "m"}}, "op")


def test_s3_store_query_sends_the_index_filter_and_returns_typed_hits():
    fake = FakeS3Vectors()
    st = S3VectorsStore(bucket="vb-test", client=fake)
    f = vf.eq("competition", "IMO")
    hits = st.query(Family.PROBLEM, vec(1), top_k=7, filter=f)
    op, kw = fake.calls[0]
    assert op == "query" and kw["vectorBucketName"] == "vb-test" and kw["indexName"] == "problem-te3small-1536-v1"
    assert kw["topK"] == 7 and kw["filter"] == f and kw["returnDistance"] and kw["returnMetadata"] and len(kw["queryVector"]["float32"]) == DIMENSIONS
    assert hits == [VectorHit(key="k1", distance=0.25, metadata={"competition": "IMO"})] and hits[0].similarity == 0.75


def test_s3_store_chunks_put_get_delete_to_the_service_limits():
    fake = FakeS3Vectors()
    st = S3VectorsStore(bucket="vb-test", client=fake)
    items = [VectorItem(key=f"k{i}", vector=vec(1), metadata=problem_meta(f"P{i}")) for i in range(1203)]
    assert st.put(Family.PROBLEM, items) == 1203
    assert [len(kw["vectors"]) for op, kw in fake.calls if op == "put"] == [500, 500, 203]
    fake.calls.clear()
    got = st.get(Family.STEP, [f"k{i}" for i in range(250)] + ["k1"], with_data=False)
    assert len(got) == 250 and [len(kw["keys"]) for op, kw in fake.calls] == [100, 100, 50] and fake.calls[0][1]["returnData"] is False
    fake.calls.clear()
    assert st.delete(Family.STEP, [f"k{i}" for i in range(501)]) == 501 and [len(kw["keys"]) for _, kw in fake.calls] == [500, 1]
    assert list(st.keys(Family.STEP)) == ["a", "b"]                                              # follows nextToken


@pytest.mark.parametrize(("code", "expected"), [
    ("ThrottlingException", StoreUnavailable), ("ServiceUnavailableException", StoreUnavailable),
    ("NotFoundException", NotFound), ("ValidationException", ValidationFailed),
    ("AccessDeniedException", StoreUnavailable), ("SomethingElse", StoreUnavailable),
])
def test_s3_store_maps_service_errors_to_domain_errors(code, expected):
    fake = FakeS3Vectors()
    fake.fail = err(code)
    st = S3VectorsStore(bucket="vb-test", client=fake)
    with pytest.raises(expected):
        st.query(Family.PROBLEM, vec(1))
    assert expected.status_code in (404, 422, 503)


def test_s3_store_never_calls_the_service_for_an_invalid_request():
    fake = FakeS3Vectors()
    st = S3VectorsStore(bucket="vb-test", client=fake)
    with pytest.raises(ValidationFailed):
        st.query(Family.PROBLEM, vec(1), top_k=500)
    with pytest.raises(ValidationFailed):
        st.query(Family.PROBLEM, vec(1), filter=vf.eq("canonical_code", "X"))
    assert fake.calls == []


# ------------------------------------------------------------------ selection

def test_selection_follows_the_flag_and_can_be_overridden(monkeypatch):
    from mathbank_rest.config import settings

    monkeypatch.setattr(settings, "vector_store", "pgvector")
    assert not uses_s3_vectors()
    with pytest.raises(StoreUnavailable, match="pgvector"):
        get_vector_store()
    monkeypatch.setattr(settings, "vector_store", "s3vectors")
    assert uses_s3_vectors() and isinstance(get_vector_store(), S3VectorsStore)
    mem = MemoryVectorStore()
    set_vector_store_for_tests(mem)
    try:
        assert get_vector_store() is mem and uses_s3_vectors()
    finally:
        set_vector_store_for_tests(None)
