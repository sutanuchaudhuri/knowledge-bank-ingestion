"""WP2 artifact vectors: the adapter (public/private routing, mandatory owner filter, tag filters, merge order) and the
S3 Vectors branches of ``artifact_runtime`` (semantic search, similar, index, reindex). MemoryVectorStore; the Postgres
bundle read is replaced by an in-memory fake; no AWS and no Postgres."""
from __future__ import annotations

import math
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mathbank_rest import artifact_runtime as ar
from mathbank_rest import artifact_vectors as av
from mathbank_rest import rate_limit, security
from mathbank_rest.routers import artifacts as artifacts_router
from mathbank_rest.stores.errors import ValidationFailed
from mathbank_rest.vector_catalog import DIMENSIONS, Family
from mathbank_rest.vector_store import (
    MemoryVectorStore,
    filter_keys,
    set_vector_store_for_tests,
)

ADMIN = {"role": "ADMIN", "student_id": None, "actor_id": "service"}
ALICE = {"role": "STUDENT", "student_id": str(uuid4())}
BOB = {"role": "STUDENT", "student_id": str(uuid4())}


def vec(angle: float) -> list[float]:
    """Unit vectors in a plane: cosine distance to vec(0) grows with the angle."""
    out = [0.0] * DIMENSIONS
    out[0], out[1] = math.cos(angle), math.sin(angle)
    return out


def bid() -> str:
    return str(uuid4())


class SpyStore(MemoryVectorStore):
    def __init__(self) -> None:
        super().__init__()
        self.queries: list[tuple[Family, dict | None]] = []

    def query(self, family, vector, top_k=10, filter=None):
        self.queries.append((family, filter))
        return super().query(family, vector, top_k, filter)


@pytest.fixture()
def store():
    st = SpyStore()
    set_vector_store_for_tests(st)
    yield st
    set_vector_store_for_tests(None)


def put_public(bundle: str, angle: float, *, status="PUBLISHED", subject="GEOMETRY", sha="a" * 64, concept=(), skill=(), theorem=()):
    av.index_bundle(bundle, sha, vec(angle), subject=subject, status=status, concept_tags=concept, skill_tags=skill,
                    theorem_tags=theorem)


# ------------------------------------------------------------------ adapter

def test_index_routes_public_and_private_and_moves_scope(store):
    pub, priv = bid(), bid()
    assert av.index_bundle(pub, "a" * 64, vec(0), subject="ALGEBRA", status="PUBLISHED", concept_tags=["c1"]) == "public"
    assert av.index_bundle(priv, "b" * 64, vec(0.1), subject="ALGEBRA", status="DRAFT", owner_student_id="s1") == "private"
    assert list(store.keys(Family.ARTIFACT_PUBLIC)) == [pub] and list(store.keys(Family.ARTIFACT_PRIVATE)) == [priv]
    assert store.get(Family.ARTIFACT_PRIVATE, [priv])[0].metadata["owner_student_id"] == "s1"
    assert "owner_student_id" not in store.get(Family.ARTIFACT_PUBLIC, [pub])[0].metadata
    # public -> private removes the public copy; private -> public removes the private copy
    av.index_bundle(pub, "a" * 64, vec(0), subject="ALGEBRA", status="PUBLISHED", owner_student_id="s1")
    assert list(store.keys(Family.ARTIFACT_PUBLIC)) == []
    av.index_bundle(pub, "a" * 64, vec(0), subject="ALGEBRA", status="PUBLISHED")
    assert pub not in list(store.keys(Family.ARTIFACT_PRIVATE)) and pub in list(store.keys(Family.ARTIFACT_PUBLIC))


def test_private_query_cannot_be_built_without_an_owner(store):
    for bad in ("", None):
        with pytest.raises(ValidationFailed):
            av.private_filter(bad)  # type: ignore[arg-type]
        with pytest.raises(ValidationFailed):
            av._query_private(store, vec(0), bad, 5, subject=None, status=None)  # type: ignore[arg-type]
    flt = av.private_filter("s1", subject="ALGEBRA", status="PUBLISHED")
    assert "owner_student_id" in filter_keys(flt)
    assert store.queries == []


def test_every_private_query_carries_the_viewer_filter_and_students_are_isolated(store):
    a_doc, b_doc, pub = bid(), bid(), bid()
    av.index_bundle(a_doc, "a" * 64, vec(0.0), subject="ALGEBRA", status="PUBLISHED", owner_student_id="alice")
    av.index_bundle(b_doc, "b" * 64, vec(0.0), subject="ALGEBRA", status="PUBLISHED", owner_student_id="bob")
    put_public(pub, 0.3, subject="ALGEBRA")
    hits = av.search(vec(0), viewer_student_id="alice", subject="ALGEBRA", status="PUBLISHED")
    assert [h.bundle_id for h in hits] == [a_doc, pub]
    assert {h.scope for h in hits} == {"private", "public"}
    private_queries = [f for fam, f in store.queries if fam is Family.ARTIFACT_PRIVATE]
    assert private_queries and all(f is not None and "owner_student_id" in filter_keys(f) for f in private_queries)
    assert {"owner_student_id": {"$eq": "alice"}} in (private_queries[0]["$and"])
    assert b_doc not in [h.bundle_id for h in av.search(vec(0), viewer_student_id="alice")]
    assert b_doc in [h.bundle_id for h in av.search(vec(0), viewer_student_id="bob")]


def test_anonymous_and_staff_without_a_student_never_query_private(store):
    priv = bid()
    av.index_bundle(priv, "a" * 64, vec(0), subject="ALGEBRA", status="PUBLISHED", owner_student_id="alice")
    assert av.search(vec(0)) == []
    assert av.search(vec(0), is_staff=True) == []
    assert all(fam is Family.ARTIFACT_PUBLIC for fam, _ in store.queries)
    # staff name the student explicitly
    assert [h.bundle_id for h in av.search(vec(0), is_staff=True, viewer_student_id="alice")] == [priv]


def test_private_hit_with_a_foreign_owner_is_dropped_even_if_the_store_returned_it(store, monkeypatch):
    foreign = bid()
    av.index_bundle(foreign, "a" * 64, vec(0), subject=None, status="PUBLISHED", owner_student_id="bob")
    monkeypatch.setattr(MemoryVectorStore, "query", lambda self, family, vector, top_k=10, filter=None: [
        av.VectorHit(key=foreign, distance=0.0, metadata={"owner_student_id": "bob", "status": "PUBLISHED"})]
        if family is Family.ARTIFACT_PRIVATE else [])
    assert av.search(vec(0), viewer_student_id="alice") == []


def test_tag_filters_use_in_on_lists_and_skip_the_private_index(store):
    p1, p2, p3, priv = bid(), bid(), bid(), bid()
    put_public(p1, 0.0, concept=["inversion", "circles"], skill=["s1"])
    put_public(p2, 0.1, concept=["parity"], theorem=["t9"])
    put_public(p3, 0.2, subject="ALGEBRA", concept=["inversion"])
    av.index_bundle(priv, "c" * 64, vec(0), subject="GEOMETRY", status="PUBLISHED", owner_student_id="alice")
    got = av.search(vec(0), viewer_student_id="alice", concept_tags=["circles", "parity"])
    assert [h.bundle_id for h in got] == [p1, p2]                           # any element matches; no private hit
    assert all(fam is Family.ARTIFACT_PUBLIC for fam, _ in store.queries)
    assert [h.bundle_id for h in av.search(vec(0), concept_tags=["inversion"], subject="ALGEBRA")] == [p3]
    assert [h.bundle_id for h in av.search(vec(0), theorem_tags=["t9"])] == [p2]
    assert av.search(vec(0), skill_tags=["nope"]) == []
    assert got[0].concept_tags == ["inversion", "circles"] and got[0].skill_tags == ["s1"]


def test_status_filter_and_merge_order_by_distance(store):
    pub_near, pub_far, pub_draft, priv_mid = bid(), bid(), bid(), bid()
    put_public(pub_near, 0.05)
    put_public(pub_far, 0.9)
    put_public(pub_draft, 0.01, status="DRAFT")
    av.index_bundle(priv_mid, "d" * 64, vec(0.4), subject="GEOMETRY", status="PUBLISHED", owner_student_id="alice")
    hits = av.search(vec(0), viewer_student_id="alice", status="PUBLISHED")
    assert [h.bundle_id for h in hits] == [pub_near, priv_mid, pub_far]
    assert hits[0].similarity > hits[1].similarity > hits[2].similarity
    assert hits[0].similarity == pytest.approx(1 - hits[0].distance)
    assert [h.bundle_id for h in av.search(vec(0), top_k=2, status="PUBLISHED", viewer_student_id="alice")] == [pub_near, priv_mid]
    assert pub_draft in [h.bundle_id for h in av.search(vec(0))]


def test_top_k_is_capped_at_the_service_limit(store):
    put_public(bid(), 0.0)
    assert len(av.search(vec(0), top_k=5000)) == 1                           # clamped to 100, not rejected


def test_erase_student_deletes_only_that_students_private_vectors(store):
    mine, other, public = bid(), bid(), bid()
    av.index_bundle(mine, "a" * 64, vec(0), subject=None, status="PUBLISHED", owner_student_id="alice")
    av.index_bundle(other, "b" * 64, vec(0), subject=None, status="PUBLISHED", owner_student_id="bob")
    put_public(public, 0.0)
    assert av.erase_student("alice", [mine, other, public, bid()]) == 1
    assert sorted(store.keys(Family.ARTIFACT_PRIVATE)) == [other] and list(store.keys(Family.ARTIFACT_PUBLIC)) == [public]
    with pytest.raises(ValidationFailed):
        av.erase_student("", [other])


def test_remove_set_status_and_get_vector(store):
    a, priv = bid(), bid()
    put_public(a, 0.2, status="DRAFT", concept=["c"])
    av.index_bundle(priv, "b" * 64, vec(0.3), subject=None, status="PUBLISHED", owner_student_id="alice")
    assert av.set_status(a, "PUBLISHED") is True and av.set_status(bid(), "PUBLISHED") is False
    got = store.get(Family.ARTIFACT_PUBLIC, [a])[0]
    assert got.metadata["status"] == "PUBLISHED" and got.metadata["concept_tags"] == ["c"] and got.vector == vec(0.2)
    assert av.get_vector(a).scope == "public" and av.get_vector(a).search_text_sha256 == "a" * 64
    assert av.get_vector(priv) is None and av.get_vector(priv, viewer_student_id="bob") is None
    assert av.get_vector(priv, viewer_student_id="alice").scope == "private"
    av.remove_bundle(a)
    av.remove_bundle(priv)
    assert av.get_vector(a) is None and av.get_vector(priv, viewer_student_id="alice") is None


def test_bulk_index_uses_the_boto3_engine_for_a_non_s3_store(store):
    rows = [av.IndexRow(bundle_id=bid(), search_text_sha256="a" * 64, vector=vec(i / 10), subject="ALGEBRA", status="PUBLISHED")
            for i in range(3)]
    rows.append(av.IndexRow(bundle_id=bid(), search_text_sha256="b" * 64, vector=vec(0.5), status="PUBLISHED", owner_student_id="s"))
    res = av.bulk_index(rows)
    assert (res.written, res.public, res.private, res.engine) == (4, 3, 1, "boto3")
    assert len(list(store.keys(Family.ARTIFACT_PUBLIC))) == 3 and len(list(store.keys(Family.ARTIFACT_PRIVATE))) == 1


# ------------------------------------------------------------------ artifact_runtime on S3 Vectors

class FakeConn:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def execute(self, statement, params=None):
        self.calls.append(str(statement))
        return self


class World:
    def __init__(self) -> None:
        self.bundles: dict[str, dict] = {}
        self.hydrated: list[list[str]] = []

    def add(self, angle: float, *, status="PUBLISHED", subject="GEOMETRY", text="search text", index=True, stale=False,
            difficulty="EASY", assets=("SVG_DIAGRAM",), **tags) -> str:
        b = bid()
        live = sha256(text.encode()).hexdigest()
        self.bundles[b] = {"artifact_bundle_id": b, "subject": subject, "topic": "t", "title": f"title {b[:4]}", "summary": "s",
                           "status": status, "metadata": {}, "difficulty_band": difficulty, "asset_types": list(assets),
                           "search_text_sha256": live}
        if index:
            av.index_bundle(b, "f" * 64 if stale else live, vec(angle), subject=subject, status=status, **tags)
        return b

    def hydrate(self, conn, ids):
        self.hydrated.append(list(ids))
        return {i: dict(self.bundles[i]) for i in ids if i in self.bundles}


@pytest.fixture()
def world(store, monkeypatch):
    w = World()
    monkeypatch.setattr(ar, "_hydrate_bundles", w.hydrate)
    monkeypatch.setattr(ar, "embedding_profile",
                        lambda: {"provider": "direct_openai", "model": "text-embedding-3-small", "dimensions": 1536})
    monkeypatch.setattr(ar, "record_audit_event", lambda *a, **k: calls_audit.append((a, k)))
    calls_audit.clear()
    return w


calls_audit: list = []


def sbody(**kw) -> ar.SearchBody:
    kw.setdefault("query_embedding", vec(0))
    return ar.SearchBody(**kw)


def ids(result) -> list[str]:
    return [str(r["artifact_bundle_id"]) for r in result["results"]]


def test_semantic_search_ranks_hydrates_and_reports_total_and_limit(world):
    near, mid, far = world.add(0.0), world.add(0.3), world.add(0.8)
    res = ar.search(FakeConn(), sbody(limit=2), ALICE, True)
    assert res["status"] == "AVAILABLE" and ids(res) == [near, mid]
    assert (res["total"], res["limit"], res["offset"]) == (3, 2, 0)
    assert res["results"][0]["score"] > res["results"][1]["score"]
    assert {"title", "summary", "subject", "topic", "status", "metadata"} <= set(res["results"][0])
    page2 = ar.search(FakeConn(), sbody(limit=2, offset=2), ALICE, True)
    assert ids(page2) == [far] and page2["total"] == 3
    assert ar.search(FakeConn(), sbody(limit=100), ALICE, True)["limit"] == 100
    beyond = ar.search(FakeConn(), sbody(limit=2, offset=50), ALICE, True)
    assert beyond["status"] == "AVAILABLE" and beyond["results"] == [] and beyond["total"] == 3
    assert len(world.hydrated[0]) == 3                                        # one batched read, not one per hit


def test_search_limit_cannot_exceed_the_service_cap():
    with pytest.raises(ValueError):
        sbody(limit=101)


def test_unpublished_missing_and_stale_vectors_are_dropped_for_learners_but_staff_see_drafts(world):
    ok = world.add(0.0)
    draft = world.add(0.1, status="DRAFT")
    stale = world.add(0.2, stale=True)
    gone = world.add(0.3)
    del world.bundles[gone]
    published_after = world.add(0.4, status="DRAFT")
    world.bundles[published_after]["status"] = "PUBLISHED"                   # vector says DRAFT, bundle is published now
    res = ar.search(FakeConn(), sbody(), ALICE, True)
    assert ids(res) == [ok]                                                  # DRAFT vectors are pre-filtered for learners
    staff = ar.search(FakeConn(), sbody(), ADMIN, True)
    assert set(ids(staff)) == {ok, draft, published_after} and stale not in ids(staff) and gone not in ids(staff)


def test_a_bundle_unpublished_after_indexing_is_dropped_by_the_recheck(world):
    b = world.add(0.0)
    world.bundles[b]["status"] = "DRAFT"                                     # vector still says PUBLISHED
    res = ar.search(FakeConn(), sbody(), ALICE, True)
    assert res["status"] == "UNAVAILABLE" and res["reason"] == "NO_INDEXED_VECTORS_FOR_FILTERS" and res["total"] == 0
    assert ids(ar.search(FakeConn(), sbody(), ADMIN, True)) == [b]


def test_filters_apply_to_vector_metadata_and_hydrated_bundles(world):
    a = world.add(0.0, subject="ALGEBRA", concept_tags=["c1"], difficulty="HARD", assets=("LATEX_CARD",))
    g = world.add(0.1, subject="GEOMETRY", concept_tags=["c1"], theorem_tags=["t1"], difficulty="EASY")
    world.add(0.2, subject="GEOMETRY", concept_tags=["c2"])
    assert ids(ar.search(FakeConn(), sbody(subject="ALGEBRA"), ALICE, True)) == [a]
    assert set(ids(ar.search(FakeConn(), sbody(concept_id="c1"), ALICE, True))) == {a, g}
    assert ids(ar.search(FakeConn(), sbody(theorem_id="t1"), ALICE, True)) == [g]
    assert ids(ar.search(FakeConn(), sbody(concept_id="c1", difficulty_band="HARD"), ALICE, True)) == [a]
    assert ids(ar.search(FakeConn(), sbody(concept_id="c1", asset_type="LATEX_CARD"), ALICE, True)) == [a]


def test_learner_cannot_see_another_learners_private_vectors_through_search_or_similar(world, store, monkeypatch):
    monkeypatch.setattr(ar, "get_bundle", lambda conn, bundle_id, actor: world.bundles[str(bundle_id)])
    mine = world.add(0.0, index=False)
    av.index_bundle(mine, world.bundles[mine]["search_text_sha256"], vec(0.0), subject="GEOMETRY", status="PUBLISHED",
                    owner_student_id=ALICE["student_id"])
    assert ids(ar.search(FakeConn(), sbody(), ALICE, True)) == [mine]
    assert ar.search(FakeConn(), sbody(), BOB, True)["status"] == "UNAVAILABLE"
    assert all(f is not None and "owner_student_id" in filter_keys(f) for fam, f in store.queries if fam is Family.ARTIFACT_PRIVATE)
    assert ar.similar(FakeConn(), _uuid(mine), ar.SearchBody(), BOB)["reason"] == "SOURCE_NOT_INDEXED"
    assert ar.similar(FakeConn(), _uuid(mine), ar.SearchBody(), ALICE)["status"] == "UNAVAILABLE"  # nothing else to return


def test_generate_embedding_is_staff_only_and_never_reaches_the_provider_for_a_learner(world, monkeypatch):
    world.add(0.0)
    calls: list[str] = []
    monkeypatch.setattr(ar, "EMBEDDER", lambda s: (calls.append(s), vec(0))[1])
    body = ar.SearchBody(query="inversion", generate_embedding=True)
    with pytest.raises(ar.ArtifactError) as exc:
        ar.search(FakeConn(), body, ALICE, True)
    assert exc.value.status_code == 403 and exc.value.code == "EMBEDDING_GENERATION_STAFF_ONLY" and calls == []
    res = ar.search(FakeConn(), body, ADMIN, True)
    assert res["status"] == "AVAILABLE" and len(res["results"]) == 1 and calls == ["inversion"]
    with rate_limit.embeddings_blocked(), pytest.raises(ar.ArtifactError) as blocked:
        ar.search(FakeConn(), body, ADMIN, True)
    assert blocked.value.status_code == 403 and calls == ["inversion"]


def test_semantic_search_without_a_vector_or_with_a_foreign_profile_is_unavailable(world, monkeypatch):
    world.add(0.0)
    assert ar.search(FakeConn(), ar.SearchBody(query="x"), ALICE, True)["reason"] == "QUERY_EMBEDDING_REQUIRED"
    assert ar.search(FakeConn(), sbody(model="other-model"), ALICE, True)["reason"] == "EMBEDDING_PROFILE_MISMATCH"
    monkeypatch.setattr(ar, "embedding_profile", lambda: {"provider": "gateway", "model": "m", "dimensions": 3072})
    assert ar.search(FakeConn(), sbody(model="m", dimensions=3072, query_embedding=[1.0] * 3072), ALICE, True)["reason"] == \
        "EMBEDDING_PROFILE_MISMATCH"


def test_similar_uses_the_stored_vector_excludes_itself_and_drops_stale_source(world, monkeypatch):
    monkeypatch.setattr(ar, "get_bundle", lambda conn, bundle_id, actor: world.bundles[str(bundle_id)])
    src, near, far = world.add(0.0), world.add(0.1), world.add(0.9)
    out = ar.similar(FakeConn(), _uuid(src), ar.SearchBody(), ALICE)
    assert ids(out) == [near, far] and out["total"] == 2
    stale = world.add(0.0, stale=True)
    assert ar.similar(FakeConn(), _uuid(stale), ar.SearchBody(), ALICE)["reason"] == "SOURCE_NOT_INDEXED"
    unindexed = world.add(0.0, index=False)
    assert ar.similar(FakeConn(), _uuid(unindexed), ar.SearchBody(), ALICE)["reason"] == "SOURCE_NOT_INDEXED"


def _uuid(value: str):
    return UUID(value)


def test_index_bundle_writes_postgres_and_s3_vectors(world, monkeypatch, store):
    b = world.add(0.0, index=False)
    text = "search text"
    sha = sha256(text.encode()).hexdigest()
    monkeypatch.setattr(ar, "get_bundle", lambda conn, bundle_id, actor: {**world.bundles[str(bundle_id)], "search_text": text})
    monkeypatch.setattr(ar, "_tags_for", lambda conn, ids_: {b: {"concept_tags": ["c1"], "theorem_tags": ["t1"]}})
    conn = FakeConn()
    out = ar.index_bundle(conn, _uuid(b), ar.IndexBody(embedding=vec(0.2), search_text_sha256=sha), ADMIN)
    assert out["status"] == "INDEXED" and any("artifact_embedding" in c for c in conn.calls)
    item = store.get(Family.ARTIFACT_PUBLIC, [b])[0]
    assert item.vector == vec(0.2) and item.metadata["search_text_sha256"] == sha
    assert item.metadata["concept_tags"] == ["c1"] and item.metadata["theorem_tags"] == ["t1"] and item.metadata["status"] == "PUBLISHED"
    assert "skill_tags" not in item.metadata


def test_index_bundle_rejects_a_profile_the_indexes_cannot_hold(world, monkeypatch):
    b = world.add(0.0, index=False)
    monkeypatch.setattr(ar, "get_bundle", lambda conn, bundle_id, actor: {**world.bundles[str(bundle_id)], "search_text": "search text"})
    monkeypatch.setattr(ar, "embedding_profile", lambda: {"provider": "gateway", "model": "x", "dimensions": 8})
    with pytest.raises(ar.ArtifactError) as exc:
        ar.index_bundle(FakeConn(), _uuid(b), ar.IndexBody(embedding=[1.0] * 8, dimensions=8, model="x",
                                                          search_text_sha256=world.bundles[b]["search_text_sha256"]), ADMIN)
    assert exc.value.code == "EMBEDDING_PROFILE_MISMATCH"


# ------------------------------------------------------------------ reindex

def stored_rows(n: int, *, stale: set[int] = frozenset()) -> list[dict]:
    rows = []
    for i in range(n):
        text = f"text {i}"
        rows.append({"id": f"00000000-0000-0000-0000-{i:012d}", "subject": "GEOMETRY", "status": "PUBLISHED", "search_text": text,
                     "embedding": str(vec(i / 10)).replace(" ", ""),
                     "search_text_sha256": "e" * 64 if i in stale else sha256(text.encode()).hexdigest()})
    return rows


@pytest.fixture()
def reindex_world(world, monkeypatch):
    state = {"rows": stored_rows(5, stale={3}), "reads": []}

    def read(conn, profile, after, ids_, size):
        state["reads"].append((after, size))
        rows = [r for r in state["rows"] if (after is None or r["id"] > after) and (ids_ is None or r["id"] in ids_)]
        return rows[:size]

    monkeypatch.setattr(ar, "_read_embeddings_batch", read)
    monkeypatch.setattr(ar, "_tags_for", lambda conn, ids_: {ids_[0]: {"skill_tags": ["s1"]}})
    monkeypatch.setattr(ar, "REINDEX_BATCH", 2)
    return state


def test_reindex_copies_embeddings_in_batches_and_skips_stale_ones(reindex_world, store):
    out = ar.reindex_bundles(FakeConn(), ar.ReindexBody(), ADMIN)
    assert (out["scanned"], out["indexed"], out["skipped_stale"], out["batches"], out["engine"]) == (5, 4, 1, 3, "boto3")
    assert len(list(store.keys(Family.ARTIFACT_PUBLIC))) == 4
    assert [r[1] for r in reindex_world["reads"]] == [2, 2, 2]               # keyset pagination, batch size honoured
    first = store.get(Family.ARTIFACT_PUBLIC, ["00000000-0000-0000-0000-000000000000"])[0]
    assert first.metadata["skill_tags"] == ["s1"]
    (args, kwargs), = calls_audit
    assert args[3] == "REINDEX" and args[2] == "service" and kwargs["after_state"]["indexed"] == 4


def test_reindex_limit_and_explicit_ids(reindex_world, store):
    out = ar.reindex_bundles(FakeConn(), ar.ReindexBody(limit=3), ADMIN)
    assert out["scanned"] == 3 and [r[1] for r in reindex_world["reads"]] == [2, 1]
    wanted = [reindex_world["rows"][4]["id"], reindex_world["rows"][0]["id"], str(uuid4())]
    out = ar.reindex_bundles(FakeConn(), ar.ReindexBody(bundle_ids=wanted), ADMIN)
    assert out["scanned"] == 2 and out["indexed"] == 2 and out["not_indexed"] == 1


def test_reindex_in_postgres_mode_is_a_409(reindex_world):
    set_vector_store_for_tests(None)
    with pytest.raises(ar.ArtifactError) as exc:
        ar.reindex_bundles(FakeConn(), ar.ReindexBody(), ADMIN)
    assert exc.value.status_code == 409 and "VECTOR_STORE=s3vectors" in str(exc.value)


def test_reindex_requires_staff(reindex_world):
    with pytest.raises(ar.ArtifactError) as exc:
        ar.reindex_bundles(FakeConn(), ar.ReindexBody(), ALICE)
    assert exc.value.status_code == 403


class Engine:
    def __init__(self, conn) -> None:
        self.conn = conn

    def begin(self):
        from contextlib import contextmanager

        @contextmanager
        def cm():
            yield self.conn

        return cm()


@pytest.fixture()
def client(monkeypatch):
    app = FastAPI()
    app.include_router(artifacts_router.router)
    app.include_router(artifacts_router.admin_router)
    monkeypatch.setattr(artifacts_router, "engine", Engine(FakeConn()))
    monkeypatch.setattr(security.settings, "admin_api_key", "artifact-test-admin")
    return TestClient(app)


KEY = {"X-Admin-Api-Key": "artifact-test-admin"}


def test_reindex_route_auth_body_and_actor(client, reindex_world, store):
    assert client.post("/v1/admin/artifacts/bundles/reindex").status_code == 401
    assert client.post("/v1/admin/artifacts/bundles/reindex", headers={"X-Admin-Api-Key": "wrong"}).status_code == 401
    res = client.post("/v1/admin/artifacts/bundles/reindex", headers=KEY)
    assert res.status_code == 200 and res.json()["indexed"] == 4 and res.json()["batches"] == 3
    (args, _), = calls_audit
    assert args[2] == security.SERVICE_ACTOR.id                              # the actor is recorded like the other admin routes
    res = client.post("/v1/admin/artifacts/bundles/reindex", headers=KEY, json={"limit": 1})
    assert res.json()["scanned"] == 1
    assert client.post("/v1/admin/artifacts/bundles/reindex", headers=KEY, json={"limit": 0}).status_code == 422
    assert client.post("/v1/admin/artifacts/bundles/reindex", headers=KEY, json={"bundle_ids": ["nope"]}).status_code == 422


def test_reindex_route_is_409_on_pgvector(client, reindex_world):
    set_vector_store_for_tests(None)
    res = client.post("/v1/admin/artifacts/bundles/reindex", headers=KEY)
    assert res.status_code == 409 and res.json()["detail"]["code"] == "VECTOR_STORE_NOT_S3VECTORS"


def test_semantic_route_rejects_learner_generate_embedding_and_returns_total(client, world, monkeypatch):
    world.add(0.0)
    monkeypatch.setattr(security, "decode_access_token", lambda token: ALICE["student_id"])
    monkeypatch.setattr(security, "assert_student_active", lambda student_id: None)
    student = {"Authorization": "Bearer t"}
    res = client.post("/v1/artifacts/search/semantic", headers=student, json={"query": "x", "generate_embedding": True})
    assert res.status_code == 403 and res.json()["detail"]["code"] == "EMBEDDING_GENERATION_STAFF_ONLY"
    res = client.post("/v1/artifacts/search/semantic", headers=student, json={"query_embedding": vec(0), "limit": 5})
    assert res.status_code == 200 and res.json()["total"] == 1 and res.json()["limit"] == 5


def test_postgres_mode_search_contract_is_untouched(monkeypatch):
    set_vector_store_for_tests(None)
    assert not ar.vector_store.uses_s3_vectors()
    res = ar.search(FakeConn(), ar.SearchBody(query="x"), ALICE, True)
    assert res == {"mode": "SEMANTIC", "status": "UNAVAILABLE", "reason": "QUERY_EMBEDDING_REQUIRED", "results": []}
