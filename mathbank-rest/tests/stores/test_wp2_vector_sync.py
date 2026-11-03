"""WP2 embedding sync worker: idempotency, changed-chunk-only embedding, stale key deletion, withdraw, Stream record filtering,
partial-batch failures and rendered-chunk checksums. MemoryVectorStore + moto, no AWS, no Postgres."""
from __future__ import annotations

import datetime as dt
import hashlib
import random
import uuid

import pytest
from boto3.dynamodb.types import TypeSerializer

from mathbank_rest import vector_sync as vs
from mathbank_rest.models.ddb.content import ContentProblem, ContentTaxnode
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import typed
from mathbank_rest.stores.errors import NotFound, StoreError
from mathbank_rest.vector_catalog import (
    DIMENSIONS,
    Family,
    ProblemMeta,
    TaxonomySearchMeta,
    TheoremMeta,
)
from mathbank_rest.vector_store import MemoryVectorStore, set_vector_store_for_tests

NOW = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
SHA1, SHA2 = "1" * 64, "2" * 64


def vec(seed: int) -> list[float]:
    r = random.Random(seed)
    return [r.uniform(-1, 1) for _ in range(DIMENSIONS)]


class Embedder:
    """Deterministic batch embedder that records every call."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [vec(hash(t) % 10_000) for t in texts]

    @property
    def texts(self) -> list[str]:
        return [t for c in self.calls for t in c]


@pytest.fixture()
def world(ddb, monkeypatch):
    ddb.create_table(TableName="mb-content-ut", AttributeDefinitions=[{"AttributeName": a, "AttributeType": "S"} for a in ("PK", "SK")],
                     KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
                     BillingMode="PAY_PER_REQUEST")
    store = MemoryVectorStore()
    set_vector_store_for_tests(store)
    emb = Embedder()
    monkeypatch.setattr(vs, "BATCH_EMBEDDER", emb)
    yield store, emb
    set_vector_store_for_tests(None)


def put_problem(code: str, *, sha: str = SHA1, visibility: str = "ACTIVE", version: int | None = 1, keys: list[str] | None = None,
                state_sha: str | None = None) -> None:
    state = {"index": Family.PROBLEM.index_name, "keys": keys or [], "model": "text-embedding-3-small", "sha256": state_sha or sha}
    typed.put(ContentProblem.model_validate({
        "PK": f"PROBLEM#{code}", "SK": "META", "type": "PROBLEM", "canonical_code": code, "problem_number": 1,
        "competition": {"competition_id": str(uuid.uuid4()), "external_code": "IMO", "level": "L", "name": "IMO"},
        "content_sha256": "c" * 64, "created_at": NOW, "images": [], "paper_code": "IMO-2010", "paper_id": str(uuid.uuid4()),
        "problem_id": str(uuid.uuid4()), "src_rev": 1, "updated_at": NOW, "visibility": visibility, "concepts": [], "techniques": [],
        "statement_text": f"Statement of {code}", "source_url": f"https://x/{code}", "year": 2010, "search_render_sha256": sha,
        "vector_state": state, **({"version": version} if version is not None else {})}))


def chunk(code: str, text: str, *, sha: str = SHA1, key: str | None = None, ordinal: int = 0) -> vs.Chunk:
    return vs.Chunk(key=key or str(uuid.uuid4()), text=text, metadata=ProblemMeta(
        competition="IMO", year=2010, problem_id="p", chunk_kind="FULL", canonical_code=code, content_sha256=sha, chunk_ordinal=ordinal,
        representation_id="r").to_metadata())


def upsert(code: str, chunks: list[vs.Chunk], sha: str = SHA1, **kw) -> vs.VectorSyncEvent:
    return vs.VectorSyncEvent(family=Family.PROBLEM, entity_id=code, op="upsert", content_sha256=sha, chunks=chunks, **kw)


def state_of(code: str) -> dict:
    raw = toolkit.get_item("content", f"PROBLEM#{code}", "META")
    return raw["vector_state"]


# ------------------------------------------------------------------ apply_events

def test_first_apply_embeds_writes_and_records_the_state_and_a_second_apply_is_free(world):
    store, emb = world
    put_problem("IMO_2010_P1")
    chunks = [chunk("IMO_2010_P1", "alpha", ordinal=0), chunk("IMO_2010_P1", "beta", ordinal=1)]
    first = vs.apply_events([upsert("IMO_2010_P1", chunks)], store=store)
    assert first.ok and first.outcomes[0].status == "synced" and first.total("embedded") == 2 and first.total("written") == 2
    assert sorted(emb.texts) == ["alpha", "beta"] and len(emb.calls) == 1
    assert sorted(store.keys(Family.PROBLEM)) == sorted(c.key for c in chunks)
    st = state_of("IMO_2010_P1")
    assert sorted(st["keys"]) == sorted(c.key for c in chunks) and st["sha256"] == SHA1 and st["index"] == Family.PROBLEM.index_name
    assert toolkit.get_item("content", "PROBLEM#IMO_2010_P1", "META")["version"] == 2       # CAS bumped the version

    emb.calls.clear()
    second = vs.apply_events([upsert("IMO_2010_P1", chunks)], store=store)
    assert second.outcomes[0].status == "unchanged" and emb.calls == [] and second.total("written") == 0


def test_only_changed_chunks_are_embedded_and_unchanged_ones_reused(world):
    store, emb = world
    put_problem("IMO_2010_P1", sha=SHA1)
    a, b = chunk("IMO_2010_P1", "alpha", sha="a1", ordinal=0), chunk("IMO_2010_P1", "beta", sha="b1", ordinal=1)
    vs.apply_events([upsert("IMO_2010_P1", [a, b])], store=store)
    before = {i.key: i.vector for i in store.get(Family.PROBLEM, [a.key, b.key])}
    emb.calls.clear()
    put_problem("IMO_2010_P1", sha=SHA2, keys=[a.key, b.key], state_sha=SHA1)
    b2 = b.model_copy(update={"text": "beta v2", "metadata": {**b.metadata, "content_sha256": "b2"}})
    res = vs.apply_events([upsert("IMO_2010_P1", [a, b2], sha=SHA2)], store=store)
    assert res.outcomes[0].status == "synced" and (res.total("embedded"), res.total("reused"), res.total("written")) == (1, 1, 1)
    assert emb.texts == ["beta v2"]
    after = {i.key: i for i in store.get(Family.PROBLEM, [a.key, b.key])}
    assert after[a.key].vector == before[a.key] and after[b.key].vector != before[b.key] and after[b.key].metadata["content_sha256"] == "b2"
    assert state_of("IMO_2010_P1")["sha256"] == SHA2


def test_a_metadata_only_change_is_reput_without_a_paid_call(world):
    store, emb = world
    put_problem("IMO_2010_P1")
    a = chunk("IMO_2010_P1", "alpha", sha="a1")
    vs.apply_events([upsert("IMO_2010_P1", [a])], store=store)
    emb.calls.clear()
    put_problem("IMO_2010_P1", sha=SHA2, keys=[a.key], state_sha=SHA1)
    moved = a.model_copy(update={"metadata": {**a.metadata, "year": 2011}})
    res = vs.apply_events([upsert("IMO_2010_P1", [moved], sha=SHA2)], store=store)
    assert emb.calls == [] and res.total("written") == 1 and store.get(Family.PROBLEM, [a.key])[0].metadata["year"] == 2011


def test_stale_keys_are_deleted_after_the_new_state_is_stored(world):
    store, _ = world
    put_problem("IMO_2010_P1", sha=SHA1)
    a, b = chunk("IMO_2010_P1", "alpha"), chunk("IMO_2010_P1", "beta", ordinal=1)
    vs.apply_events([upsert("IMO_2010_P1", [a, b])], store=store)
    put_problem("IMO_2010_P1", sha=SHA2, keys=[a.key, b.key], state_sha=SHA1)
    c = chunk("IMO_2010_P1", "gamma", sha=SHA2, ordinal=1)
    res = vs.apply_events([upsert("IMO_2010_P1", [a.model_copy(update={"metadata": {**a.metadata, "content_sha256": SHA2}}), c], sha=SHA2)], store=store)
    assert res.outcomes[0].deleted == 1
    assert sorted(store.keys(Family.PROBLEM)) == sorted([a.key, c.key]) and b.key not in state_of("IMO_2010_P1")["keys"]


def test_a_batch_is_split_at_one_hundred_texts_per_embedding_call(world):
    store, emb = world
    put_problem("IMO_2010_P1")
    chunks = [chunk("IMO_2010_P1", f"text {i}", ordinal=i) for i in range(230)]
    res = vs.apply_events([upsert("IMO_2010_P1", chunks)], store=store)
    assert res.ok and [len(c) for c in emb.calls] == [100, 100, 30] and res.outcomes[0].embed_calls == 3
    assert len(list(store.keys(Family.PROBLEM))) == 230


def test_withdraw_deletes_every_vector_and_empties_the_state_keys(world):
    store, emb = world
    put_problem("IMO_2010_P1")
    chunks = [chunk("IMO_2010_P1", "alpha"), chunk("IMO_2010_P1", "beta", ordinal=1)]
    vs.apply_events([upsert("IMO_2010_P1", chunks)], store=store)
    res = vs.apply_events([vs.VectorSyncEvent(family=Family.PROBLEM, entity_id="IMO_2010_P1", op="withdraw", content_sha256=SHA1)], store=store)
    assert res.outcomes[0].status == "withdrawn" and res.outcomes[0].deleted == 2
    assert list(store.keys(Family.PROBLEM)) == [] and state_of("IMO_2010_P1")["keys"] == []
    again = vs.apply_events([vs.VectorSyncEvent(family=Family.PROBLEM, entity_id="IMO_2010_P1", op="withdraw", content_sha256=SHA1)], store=store)
    assert again.outcomes[0].status == "unchanged"
    # republishing the same render re-embeds: the empty key list is not "in sync"
    emb.calls.clear()
    assert vs.apply_events([upsert("IMO_2010_P1", chunks)], store=store).outcomes[0].status == "synced" and emb.texts


def test_an_upsert_for_an_item_withdrawn_meanwhile_withdraws_and_never_embeds(world):
    store, emb = world
    a = chunk("IMO_2010_P1", "alpha")
    put_problem("IMO_2010_P1", keys=[a.key])
    vs.apply_events([upsert("IMO_2010_P1", [a])], store=store)
    emb.calls.clear()
    put_problem("IMO_2010_P1", sha=SHA2, visibility="WITHDRAWN", keys=[a.key], state_sha=SHA1)
    res = vs.apply_events([upsert("IMO_2010_P1", [chunk("IMO_2010_P1", "new", sha=SHA2)], sha=SHA2)], store=store)
    assert res.outcomes[0].status == "withdrawn" and emb.calls == [] and list(store.keys(Family.PROBLEM)) == []


def test_withdrawing_a_deleted_item_removes_the_vectors_named_by_old_keys(world):
    store, _ = world
    a = chunk("IMO_2010_P9", "alpha")
    store.put(Family.PROBLEM, [vs.VectorItem(key=a.key, vector=vec(1), metadata=a.metadata)])
    ev = vs.VectorSyncEvent(family=Family.PROBLEM, entity_id="IMO_2010_P9", op="withdraw", content_sha256=SHA1, old_keys=[a.key])
    assert vs.apply_events([ev], store=store).outcomes[0].status == "withdrawn" and list(store.keys(Family.PROBLEM)) == []


def test_an_event_for_an_older_render_is_superseded_without_a_paid_call(world):
    store, emb = world
    put_problem("IMO_2010_P1", sha=SHA2)
    res = vs.apply_events([upsert("IMO_2010_P1", [chunk("IMO_2010_P1", "old")], sha=SHA1)], store=store)
    assert res.outcomes[0].status == "superseded" and emb.calls == [] and list(store.keys(Family.PROBLEM)) == []


def test_invalid_metadata_fails_the_event_before_any_paid_call_and_not_the_batch(world):
    store, emb = world
    put_problem("IMO_2010_P1"), put_problem("IMO_2010_P2")
    bad = vs.Chunk(key=str(uuid.uuid4()), text="x", metadata={"competition": "IMO"})
    res = vs.apply_events([upsert("IMO_2010_P1", [bad]), upsert("IMO_2010_P2", [chunk("IMO_2010_P2", "ok")])], store=store)
    assert [o.status for o in res.outcomes] == ["failed", "synced"] and "invalid" in (res.outcomes[0].error or "")
    assert emb.texts == ["ok"] and not res.ok


def test_an_item_without_a_version_gets_a_typed_put_of_the_same_item(world):
    store, _ = world
    put_problem("IMO_2010_P1", version=None)
    a = chunk("IMO_2010_P1", "alpha")
    assert vs.apply_events([upsert("IMO_2010_P1", [a])], store=store).ok
    raw = toolkit.get_item("content", "PROBLEM#IMO_2010_P1", "META")
    assert raw["vector_state"]["keys"] == [a.key] and "version" not in raw and raw["statement_text"] == "Statement of IMO_2010_P1"


def test_an_item_type_without_a_typed_model_is_updated_with_the_raw_cas(world):
    store, _ = world
    toolkit.put_item("content", {"PK": "THEOREM#t1", "SK": "META", "type": "THEOREM", "version": 1, "content_sha256": SHA1,
                                 "review_status": "APPROVED", "vector_state": {"index": Family.THEOREM.index_name, "keys": [],
                                                                                 "model": "text-embedding-3-small", "sha256": SHA1}})
    k = str(uuid.uuid4())
    c = vs.Chunk(key=k, text="Ceva", metadata=TheoremMeta(review_status="APPROVED", slug="ceva").to_metadata())
    ev = vs.VectorSyncEvent(family=Family.THEOREM, entity_id="t1", op="upsert", content_sha256=SHA1, chunks=[c])
    assert vs.apply_events([ev], store=store).outcomes[0].status == "synced"
    raw = toolkit.get_item("content", "THEOREM#t1", "META")
    assert raw["vector_state"]["keys"] == [k] and raw["version"] == 2


# ------------------------------------------------------------------ stream records

SER = TypeSerializer()


def problem_image(code: str = "IMO_2010_P1", *, sha: str = SHA1, visibility: str = "ACTIVE", keys: list[str] | None = None,
                  state_sha: str | None = None) -> dict:
    return {"PK": f"PROBLEM#{code}", "SK": "META", "type": "PROBLEM", "visibility": visibility, "search_render_sha256": sha,
            "content_sha256": "c" * 64, "version": 1,
            "vector_state": {"index": Family.PROBLEM.index_name, "keys": keys or [], "model": "m", "sha256": state_sha or sha}}


def record(old: dict | None, new: dict | None, *, raw: bool = False, seq: str = "1") -> dict:
    enc = (lambda d: {k: SER.serialize(v) for k, v in d.items()}) if raw else (lambda d: d)
    ref = new or old
    body = {"SequenceNumber": seq, "Keys": enc({"PK": ref["PK"], "SK": ref["SK"]})}
    if old:
        body["OldImage"] = enc(old)
    if new:
        body["NewImage"] = enc(new)
    return {"eventName": "MODIFY" if old and new else "INSERT" if new else "REMOVE", "eventSourceARN": "arn:aws:dynamodb:us-east-2:1:table/mb-content-dev/stream/x",
            "dynamodb": body}


def fake_loader(calls: list):
    def load(family, entity_id, sha):
        calls.append((family, entity_id, sha))
        return vs.RenderedChunks(family=family, entity_id=entity_id, content_sha256=sha, chunks=[chunk(entity_id, "text", sha=sha)])
    return load


@pytest.mark.parametrize("raw", [False, True])
def test_a_changed_render_hash_becomes_an_upsert_with_the_rendered_chunks(raw):
    calls: list = []
    old, new = problem_image(sha=SHA1, keys=["k1"]), problem_image(sha=SHA2, keys=["k1"], state_sha=SHA1)
    events = vs.events_from_stream_records([record(old, new, raw=raw, seq="7")], loader=fake_loader(calls))
    assert len(events) == 1 and events[0].op == "upsert" and events[0].family == Family.PROBLEM and events[0].entity_id == "IMO_2010_P1"
    assert events[0].content_sha256 == SHA2 and events[0].chunks[0].text == "text" and events[0].old_keys == ["k1"] and events[0].sequence_number == "7"
    assert calls == [(Family.PROBLEM, "IMO_2010_P1", SHA2)]


def test_unchanged_irrelevant_and_own_writeback_records_are_ignored():
    calls: list = []
    same = problem_image(keys=["k1"])
    writeback = problem_image(keys=["k9"], state_sha=SHA1)
    other_attr = {**same, "statement_text": "edited"}
    irrelevant = {"PK": "ACT#1", "SK": "META", "type": "ACT", "content_sha256": SHA2}
    other_ctx = record(problem_image(sha=SHA1), problem_image(sha=SHA2))
    other_ctx["eventSourceARN"] = "arn:aws:dynamodb:us-east-2:1:table/mb-learner-dev/stream/x"
    recs = [record(same, same), record(same, writeback), record(same, other_attr), record(irrelevant, {**irrelevant, "content_sha256": "9" * 64}),
            record(None, {"PK": "PROBLEM#X", "SK": "KEY#1", "type": "PROBLEM_KEY", "content_sha256": SHA2}), other_ctx]
    assert vs.events_from_stream_records(recs, loader=fake_loader(calls)) == [] and calls == []


def test_a_new_render_whose_state_already_matches_is_not_loaded():
    calls: list = []
    new = problem_image(sha=SHA2, keys=["k1"], state_sha=SHA2)
    assert vs.events_from_stream_records([record(problem_image(sha=SHA1), new)], loader=fake_loader(calls)) == [] and calls == []


def test_visibility_flips_become_withdraw_and_republish():
    calls: list = []
    live, gone = problem_image(keys=["k1", "k2"]), problem_image(visibility="WITHDRAWN", keys=["k1", "k2"])
    (w,) = vs.events_from_stream_records([record(live, gone)], loader=fake_loader(calls))
    assert w.op == "withdraw" and sorted(w.old_keys) == ["k1", "k2"] and w.chunks == [] and calls == []
    back = problem_image(keys=[])
    (u,) = vs.events_from_stream_records([record(gone, back)], loader=fake_loader(calls))
    assert u.op == "upsert" and calls == [(Family.PROBLEM, "IMO_2010_P1", SHA1)]
    assert vs.events_from_stream_records([record(gone, {**gone, "statement_text": "x"})], loader=fake_loader(calls)) == []


def test_a_removed_item_withdraws_its_old_keys_and_eligible_flags_are_honoured_for_steps():
    calls: list = []
    (w,) = vs.events_from_stream_records([record(problem_image(keys=["k1"]), None)], loader=fake_loader(calls))
    assert w.op == "withdraw" and w.old_keys == ["k1"]
    step = {"PK": "STEP#s1", "SK": "META", "type": "STEP", "eligible": True, "content_sha256": SHA1,
            "vector_state": {"index": "i", "keys": ["s-k"], "model": "m", "sha256": SHA1}}
    (w2,) = vs.events_from_stream_records([record(step, {**step, "eligible": False})], loader=fake_loader(calls))
    assert (w2.family, w2.entity_id, w2.op) == (Family.STEP, "s1", "withdraw")
    assert vs.events_from_stream_records([record(step, {**step, "eligible": True})], loader=fake_loader(calls)) == []


def test_a_taxonomy_node_emits_a_search_event_only_when_it_has_search_chunks():
    calls: list = []
    node = {"PK": "TAXNODE#n1", "SK": "META", "type": "TAXNODE", "eligible": True, "content_sha256": SHA1,
            "vector_state": {"index": "i", "keys": ["n"], "model": "m", "sha256": SHA1}}
    changed = {**node, "content_sha256": SHA2}
    assert [e.family for e in vs.events_from_stream_records([record(node, changed)], loader=fake_loader(calls))] == [Family.TAXONOMY_NODE]
    with_search = {"search_vector_state": {"index": "i", "keys": [], "model": "m", "sha256": SHA1}}
    fams = [e.family for e in vs.events_from_stream_records([record({**node, **with_search}, {**changed, **with_search})], loader=fake_loader(calls))]
    assert fams == [Family.TAXONOMY_NODE, Family.TAXONOMY_SEARCH]


# ------------------------------------------------------------------ rendered chunk documents

def rendered(code: str = "IMO_2010_P1", sha: str = SHA1) -> vs.RenderedChunks:
    return vs.RenderedChunks(family=Family.PROBLEM, entity_id=code, content_sha256=sha, chunks=[chunk(code, "alpha", sha=sha)])


def test_rendered_chunks_round_trip_and_the_key_layout(ddb):
    key = vs.put_rendered(rendered())
    assert key == f"vector-sync/problem/IMO_2010_P1/{SHA1}.json"
    doc = vs.load_rendered(Family.PROBLEM, "IMO_2010_P1", SHA1)
    assert doc.chunks[0].text == "alpha" and doc.chunks_sha256 == doc.digest()


def test_rendered_chunks_that_do_not_verify_are_refused(ddb):
    s3, bucket = toolkit.client("s3"), toolkit.data_bucket()
    key = vs.put_rendered(rendered())
    head = s3.head_object(Bucket=bucket, Key=key)
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()

    s3.put_object(Bucket=bucket, Key=key, Body=body.replace(b"alpha", b"ALPHA"), Metadata=head["Metadata"])      # body no longer matches its sha
    with pytest.raises(StoreError, match="checksum mismatch"):
        vs.load_rendered(Family.PROBLEM, "IMO_2010_P1", SHA1)

    tampered = rendered().model_copy(update={"chunks_sha256": "0" * 64}).model_dump_json().encode()           # document hash wrong, body hash right
    s3.put_object(Bucket=bucket, Key=key, Body=tampered, Metadata={"sha256": hashlib.sha256(tampered).hexdigest()})
    with pytest.raises(StoreError, match="checksum mismatch"):
        vs.load_rendered(Family.PROBLEM, "IMO_2010_P1", SHA1)

    bare = rendered().model_dump_json().encode()                                                              # no checksum anywhere
    s3.put_object(Bucket=bucket, Key=key, Body=bare)
    with pytest.raises(StoreError, match="no checksum"):
        vs.load_rendered(Family.PROBLEM, "IMO_2010_P1", SHA1)

    vs.put_rendered(rendered(sha=SHA2).model_copy(update={"content_sha256": SHA2}))                          # stored under the wrong name
    s3.copy_object(Bucket=bucket, Key=key, CopySource={"Bucket": bucket, "Key": vs.rendered_key(Family.PROBLEM, "IMO_2010_P1", SHA2)})
    with pytest.raises(StoreError, match="another entity or hash"):
        vs.load_rendered(Family.PROBLEM, "IMO_2010_P1", SHA1)


def test_missing_rendered_chunks_are_not_found(ddb):
    with pytest.raises(NotFound):
        vs.load_rendered(Family.PROBLEM, "IMO_2010_P1", SHA1)


# ------------------------------------------------------------------ Lambda handler

def test_handler_syncs_a_batch_and_reports_only_the_failing_records(world):
    store, _ = world
    for code in ("A_1", "B_1", "C_1"):
        put_problem(code, sha=SHA1, keys=[], state_sha="0" * 64)
    docs = {code: rendered(code) for code in ("A_1", "C_1")}      # B_1 has no rendered document: its mapping fails
    for doc in docs.values():
        vs.put_rendered(doc)
    recs = [record(problem_image(c, sha="0" * 64), problem_image(c, sha=SHA1, state_sha="0" * 64), seq=str(i))
            for i, c in enumerate(("A_1", "B_1", "C_1"), 1)]
    recs.append(record(problem_image("B_1", sha=SHA1), problem_image("B_1", sha=SHA2, state_sha=SHA1), seq="4"))      # same item as the failure
    out = vs.handler({"Records": recs}, None)
    assert out == {"batchItemFailures": [{"itemIdentifier": "2"}, {"itemIdentifier": "4"}]}
    assert sorted(store.keys(Family.PROBLEM)) == sorted(c.key for r in docs.values() for c in r.chunks)
    assert state_of("A_1")["sha256"] == SHA1 and state_of("A_1")["keys"]


def test_handler_reports_a_failing_embedder(world, monkeypatch):
    put_problem("A_1", state_sha="0" * 64)
    vs.put_rendered(rendered("A_1"))

    def boom(texts):
        raise RuntimeError("openai down")

    monkeypatch.setattr(vs, "BATCH_EMBEDDER", boom)
    rec = record(problem_image("A_1", sha="0" * 64), problem_image("A_1", sha=SHA1, state_sha="0" * 64), seq="9")
    assert vs.handler({"Records": [rec]}) == {"batchItemFailures": [{"itemIdentifier": "9"}]}
    assert state_of("A_1")["keys"] == []


def test_handler_ignores_irrelevant_records_and_returns_no_failures(world):
    assert vs.handler({"Records": [record(None, {"PK": "ACT#1", "SK": "META", "type": "ACT"})]}) == {"batchItemFailures": []}
    assert vs.handler({}) == {"batchItemFailures": []}


def test_taxonomy_search_family_uses_its_own_state_attribute(world):
    store, _ = world
    typed.put(ContentTaxnode.model_validate({
        "PK": "TAXNODE#n1", "SK": "META", "type": "TAXNODE", "content_sha256": SHA1, "eligible": True, "example_problem_codes": [],
        "lifecycle": "ACTIVE", "name": "Inversion", "node_type": "SKILL", "problem_count": 0, "src_rev": 1, "taxonomy_node_id": "n1",
        "updated_at": NOW, "version": 1,
        "vector_state": {"index": Family.TAXONOMY_NODE.index_name, "keys": ["n1"], "model": "m", "sha256": "z" * 64},
        "search_vector_state": {"index": Family.TAXONOMY_SEARCH.index_name, "keys": [], "model": "m", "sha256": "z" * 64}}))
    k = str(uuid.uuid4())
    c = vs.Chunk(key=k, text="inversion", metadata=TaxonomySearchMeta(node_type="SKILL", taxonomy_node_id="n1", content_sha256=SHA1,
                                                                        representation_id="r").to_metadata())
    ev = vs.VectorSyncEvent(family=Family.TAXONOMY_SEARCH, entity_id="n1", op="upsert", content_sha256=SHA1, chunks=[c])
    assert vs.apply_events([ev], store=store).outcomes[0].status == "synced"
    raw = toolkit.get_item("content", "TAXNODE#n1", "META")
    assert raw["search_vector_state"]["keys"] == [k] and raw["vector_state"]["keys"] == ["n1"]
