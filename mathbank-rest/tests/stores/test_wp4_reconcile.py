"""WP4 publisher contract and reconciliation of ``mb-content`` (requirement 70 C6 §4a, requirement 71 WP4).

moto (``content_table``) + ``MemoryVectorStore``; no AWS, no Postgres. The canonical hash is pinned against vectors
produced by the migration code (``mathbank-db/aws/common.py``), so a freshly migrated item reconciles with 0 diffs."""
from __future__ import annotations

import importlib
import random
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mathbank_rest import content_publisher as pub
from mathbank_rest import profiles
from mathbank_rest.config import settings
from mathbank_rest.routers import admin_content
from mathbank_rest.security import SERVICE_ACTOR_ID
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores.content import reconcile as rc
from mathbank_rest.stores.errors import ConditionFailed
from mathbank_rest.vector_catalog import DIMENSIONS, Family
from mathbank_rest.vector_store import MemoryVectorStore, VectorItem

KEY = "wp4-admin-key"
IMO, APMO = "IMO", "APMO"


# ------------------------------------------------------------------ canonical hash (pinned)

PINNED = {
    "competition": ({"competition_id": uuid.UUID("11111111-1111-4111-8111-111111111111"), "external_code": "IMO",
                     "name": "International Mathematical Olympiad", "organization": None, "country": "INT",
                     "level": "INTERNATIONAL"},
                    "4ae3bc6020fac351fc376c536fcb5b05661e78c12d620f3f6b3e160c2a261717"),
    "empty": ({}, "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"),
}


def _mixed() -> dict:
    import datetime as dt
    import decimal

    return {"b": [1, 2.5, {"z": None, "a": True}], "a": "é∑", "n": decimal.Decimal("1.50"), "f": 2.0,
            "d": dt.datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=dt.timezone(dt.timedelta(hours=-5))),
            "dd": dt.date(2026, 1, 2), "u": uuid.UUID(int=5), "s": {3, 1, 2}}


def _floats() -> dict:
    return {"c": 0.1, "big": 1e22, "neg": -3.0, "nan": float("nan")}


@pytest.mark.parametrize(("payload", "expected"), [
    (PINNED["competition"][0], PINNED["competition"][1]),
    (PINNED["empty"][0], PINNED["empty"][1]),
    (_mixed(), "0885b0dc1920071232f05f79ac62dd4b5c3ac16ac4f9e1f53529e68970362365"),
    (_floats(), "936bf09915b8cd816c4051e24b6c6c4c9181f2bcb76c91f7a0fb9392d2961a95"),
], ids=["competition", "empty", "mixed-types", "floats"])
def test_canonical_sha256_is_pinned_to_the_migration_vectors(payload, expected):
    assert pub.canonical_sha256(payload) == expected


def test_canonical_sha256_ignores_key_order_and_top_level_none_but_not_nested_none():
    a = {"x": 1, "y": {"k": None}, "z": None}
    assert pub.canonical_sha256(a) == pub.canonical_sha256({"y": {"k": None}, "x": 1})
    assert pub.canonical_sha256({"y": {"k": None}}) != pub.canonical_sha256({"y": {}})


def _migration_module():
    root = Path(__file__).resolve().parents[3] / "mathbank-db"
    if not (root / "aws" / "common.py").exists():
        pytest.skip("mathbank-db is not next to mathbank-rest")
    sys.path.insert(0, str(root))
    try:
        for name in [m for m in sys.modules if m == "aws" or m.startswith("aws.")]:
            del sys.modules[name]
        return importlib.import_module("aws.common"), importlib.import_module("aws.dynamo.specs.content")
    except ImportError as exc:  # pragma: no cover - optional cross-check
        pytest.skip(f"migration code not importable: {exc}")
    finally:
        sys.path.remove(str(root))


def test_canonical_sha256_equals_the_migration_function_on_random_payloads():
    common, _ = _migration_module()
    rnd = random.Random(7)
    for _ in range(50):
        payload = {f"k{i}": rnd.choice([1, 2.5, "ü", None, True, [1, {"a": None}], {"n": rnd.random()}, uuid.UUID(int=rnd.getrandbits(100))])
                   for i in range(rnd.randint(0, 8))}
        body = {k: v for k, v in payload.items() if v is not None}
        import hashlib
        assert pub.canonical_sha256(payload) == hashlib.sha256(common.json_bytes(common.to_ddb(body))).hexdigest()


def test_a_freshly_migrated_item_reconciles_with_zero_diffs(content_table):
    _, spec = _migration_module()
    row = {"competition_id": uuid.UUID(int=1), "external_code": IMO, "name": "IMO", "organization": None, "country": "INT",
           "level": "INTERNATIONAL"}
    item = next(spec._competition(row))
    toolkit.put_item("content", {k: v for k, v in item.items()})
    payload = {k: v for k, v in row.items()}
    agg = rc.SourceAggregate(type="COMPETITION", pk=item["PK"], sk=item["SK"], payload=payload, list_pk="CATALOG#COMPETITION")
    report = rc.reconcile([agg], sample_pct=100)
    assert report.ok, report.diffs
    assert report.types[0].sampled == 1


# ------------------------------------------------------------------ fixtures

class Spy:
    def __init__(self, inner):
        self._inner, self.calls = inner, []

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        def wrapped(*a, **k):
            self.calls.append(name)
            return attr(*a, **k)

        return wrapped


def seed(type_: str, pk: str, sk: str, payload: dict, *, rev: int = 0, gsi: dict | None = None, version: int = 1) -> dict:
    item = {**payload, "PK": pk, "SK": sk, "type": type_, **(gsi or {}), "version": version, "src_rev": rev,
            "content_sha256": pub.canonical_sha256(payload)}
    toolkit.put_item("content", item)
    return item


def agg(type_: str, pk: str, sk: str, payload: dict | None = None, **kw: Any) -> rc.SourceAggregate:
    return rc.SourceAggregate(type=type_, pk=pk, sk=sk, payload=payload, **kw)


def vec(seed_: int) -> list[float]:
    r = random.Random(seed_)
    return [r.uniform(-1, 1) for _ in range(DIMENSIONS)]


def put_vec(store: MemoryVectorStore, family: Family, key: str) -> None:
    """Straight into the in-memory index: the adapter's metadata validation is not what is under test here."""
    store._data.setdefault(family, {})[key] = VectorItem(key=key, vector=vec(sum(key.encode()) % 997 + 1), metadata={})


STEP_META = {"book_code": "B", "problem_code": "IMO_1", "eligible": True}


def world(vector_store: MemoryVectorStore | None = None) -> list[rc.SourceAggregate]:
    """Two competitions, three problems, two taxnodes, two steps (+facets), one micro-course: items in moto and the
    matching source aggregates."""
    out: list[rc.SourceAggregate] = []
    for code, name in ((IMO, "International Mathematical Olympiad"), (APMO, "Asian Pacific Mathematical Olympiad")):
        payload = {"competition_id": str(uuid.uuid4()), "external_code": code, "name": name, "level": "INTERNATIONAL"}
        sk = f"COMP#{name}#{payload['competition_id']}"
        seed("COMPETITION", "CATALOG#COMPETITION", sk, payload)
        out.append(agg("COMPETITION", "CATALOG#COMPETITION", sk, payload, list_pk="CATALOG#COMPETITION"))
    for code, comp in (("IMO_2010_P1", IMO), ("IMO_2010_P2", IMO), ("APMO_2010_P1", APMO)):
        payload = {"canonical_code": code, "visibility": "ACTIVE", "statement_text": f"Statement {code}"}
        seed("PROBLEM", f"PROBLEM#{code}", "META", payload, gsi={"GSI2PK": f"PLIST#{comp}", "GSI2SK": f"2010#{code}"})
        out.append(agg("PROBLEM", f"PROBLEM#{code}", "META", payload, list_index="GSI2", list_pk=f"PLIST#{comp}"))
    for nid, ntype in (("n1", "SKILL"), ("n2", "CONCEPT")):
        payload = {"taxonomy_node_id": nid, "node_type": ntype, "eligible": True}
        seed("TAXNODE", f"TAXNODE#{nid}", "META", payload, gsi={"GSI2PK": f"TAXTYPE#{ntype}", "GSI2SK": f"001##{nid}"})
        out.append(agg("TAXNODE", f"TAXNODE#{nid}", "META", payload, list_index="GSI2", list_pk=f"TAXTYPE#{ntype}"))
    payload = {"canonical_code": "MCX", "status": "ACTIVE"}
    seed("MC", "MC#MCX", "META", payload, gsi={"GSI2PK": "CATALOG#MC", "GSI2SK": "t#MCX"})
    out.append(agg("MC", "MC#MCX", "META", payload, list_index="GSI2", list_pk="CATALOG#MC"))
    for i, sid in enumerate(("s1", "s2")):
        keys = [str(uuid.UUID(int=100 + i))]
        payload = {**STEP_META, "solution_step_id": sid, "vector_state": {"index": "step-te3small-1536-v1", "keys": keys,
                                                                         "model": "m", "sha256": "a" * 64}}
        seed("STEP", f"STEP#{sid}", "META", payload)
        out.append(agg("STEP", f"STEP#{sid}", "META", payload))
        facet_pk = "FACET#STEP#PROBLEM#p1"
        seed("FACET", facet_pk, sid, {"unit": "STEP", "dim": "PROBLEM", "value": "p1", "entity_id": sid})
        out.append(agg("FACET", facet_pk, sid, {"unit": "STEP", "dim": "PROBLEM", "value": "p1", "entity_id": sid}, list_pk=facet_pk))
        if vector_store is not None:
            put_vec(vector_store, Family.STEP, keys[0])
    return out


@pytest.fixture()
def table(content_table):
    return content_table


def kinds(report: rc.ReconcileReport) -> dict[str, list[tuple[str, str]]]:
    out: dict[str, list[tuple[str, str]]] = {}
    for d in report.diffs:
        out.setdefault(d.kind, []).append((d.pk, d.sk))
    return out


# ------------------------------------------------------------------ reconcile

def test_clean_data_has_zero_diffs_and_hashes_every_sampled_aggregate(table):
    store = MemoryVectorStore()
    src = world(store)
    report = rc.reconcile(src, sample_pct=100, vector_keys_by_family={"step": list(store.keys(Family.STEP))})
    assert report.ok and report.diff_count == 0 and report.diffs == []
    by_type = {t.type: t for t in report.types}
    assert by_type["PROBLEM"].source == 3 and by_type["PROBLEM"].found == 3 and by_type["PROBLEM"].sampled == 3
    assert by_type["COMPETITION"].active == 2 and by_type["FACET"].found == 2
    assert [v.model_dump() for v in report.vectors] == [{"family": "step", "expected": 2, "in_store": 2, "missing": 0, "orphan": 0}]


def test_a_source_aggregate_missing_in_dynamodb_is_reported_but_a_withdrawn_one_is_not(table):
    src = world()
    toolkit.client().delete_item(TableName="mb-content-ut", Key={"PK": {"S": "PROBLEM#IMO_2010_P2"}, "SK": {"S": "META"}})
    src.append(agg("PROBLEM", "PROBLEM#RETIRED_1", "META", state="WITHDRAWN"))
    report = rc.reconcile(src, sample_pct=0)
    assert kinds(report) == {"missing": [("PROBLEM#IMO_2010_P2", "META")]}
    assert not report.ok and report.by_kind() == {"missing": 1}


def test_orphans_are_found_in_listing_partitions_including_unknown_competitions(table):
    src = world()
    seed("PROBLEM", "PROBLEM#GHOST_1", "META", {"canonical_code": "GHOST_1", "visibility": "ACTIVE"},
         gsi={"GSI2PK": f"PLIST#{IMO}", "GSI2SK": "2010#g"})
    seed("COMPETITION", "CATALOG#COMPETITION", "COMP#Zed#z", {"external_code": "ZZZ", "name": "Zed", "level": "L"})
    seed("PROBLEM", "PROBLEM#ZZZ_1", "META", {"canonical_code": "ZZZ_1", "visibility": "ACTIVE"},
         gsi={"GSI2PK": "PLIST#ZZZ", "GSI2SK": "2010#z"})
    seed("TAXNODE", "TAXNODE#stray", "META", {"taxonomy_node_id": "stray", "eligible": True},
         gsi={"GSI2PK": "TAXTYPE#SKILL", "GSI2SK": "001##stray"})
    seed("PROBLEM", "PROBLEM#OLD_1", "META", {"canonical_code": "OLD_1", "visibility": "WITHDRAWN"},
         gsi={"GSI2PK": f"PLIST#{IMO}", "GSI2SK": "2010#o"})
    report = rc.reconcile(src, sample_pct=0)
    assert sorted(kinds(report)["orphan"]) == sorted([
        ("PROBLEM#GHOST_1", "META"), ("CATALOG#COMPETITION", "COMP#Zed#z"), ("PROBLEM#ZZZ_1", "META"), ("TAXNODE#stray", "META")])
    assert set(kinds(report)) == {"orphan"}          # the withdrawn extra is not drift


def test_a_stale_src_rev_is_reported_both_ways(table):
    src = world()
    next(a for a in src if a.pk == "PROBLEM#IMO_2010_P1").src_rev = 3
    next(a for a in src if a.pk == "TAXNODE#n1").src_rev = 0
    toolkit.client().update_item(TableName="mb-content-ut", Key={"PK": {"S": "TAXNODE#n1"}, "SK": {"S": "META"}},
                                 UpdateExpression="SET src_rev = :r", ExpressionAttributeValues={":r": {"N": "9"}})
    report = rc.reconcile(src, sample_pct=0)
    got = {d.pk: (d.expected, d.actual) for d in report.diffs if d.kind == "src_rev_mismatch"}
    assert got == {"PROBLEM#IMO_2010_P1": ("3", "0"), "TAXNODE#n1": ("0", "9")}


def test_flipped_publication_state_is_reported_in_both_directions(table):
    src = world()
    toolkit.client().update_item(TableName="mb-content-ut", Key={"PK": {"S": "PROBLEM#IMO_2010_P1"}, "SK": {"S": "META"}},
                                 UpdateExpression="SET visibility = :v", ExpressionAttributeValues={":v": {"S": "WITHDRAWN"}})
    toolkit.client().update_item(TableName="mb-content-ut", Key={"PK": {"S": "TAXNODE#n2"}, "SK": {"S": "META"}},
                                 UpdateExpression="SET eligible = :v", ExpressionAttributeValues={":v": {"BOOL": False}})
    next(a for a in src if a.pk == "STEP#s1").state = "WITHDRAWN"          # published here, withdrawn in PG
    next(a for a in src if a.pk == "FACET#STEP#PROBLEM#p1" and a.sk == "s2").state = "WITHDRAWN"   # a stale facet
    report = rc.reconcile(src, sample_pct=0)
    got = {(d.pk, d.sk): (d.expected, d.actual) for d in report.diffs if d.kind == "state_mismatch"}
    assert got == {("PROBLEM#IMO_2010_P1", "META"): ("ACTIVE", "WITHDRAWN"), ("TAXNODE#n2", "META"): ("ACTIVE", "WITHDRAWN"),
                   ("STEP#s1", "META"): ("WITHDRAWN", "ACTIVE"), ("FACET#STEP#PROBLEM#p1", "s2"): ("WITHDRAWN", "ACTIVE")}
    # the unlisted problem is not double-reported as an orphan either
    assert "orphan" not in kinds(report)


def test_sha_mismatch_is_found_only_on_the_sampled_rebuild(table):
    src = world()
    changed = next(a for a in src if a.pk == "PROBLEM#IMO_2010_P1")
    changed.payload = {**changed.payload, "statement_text": "edited in PG after the last publish"}
    assert rc.reconcile(src, sample_pct=0).ok                      # not sampled: undetected between full runs
    full = rc.reconcile(src, sample_pct=100)
    assert [(d.kind, d.pk) for d in full.diffs] == [("sha_mismatch", "PROBLEM#IMO_2010_P1")]
    assert full.diffs[0].expected == pub.canonical_sha256(changed.payload)


def test_rebuilt_sha256_is_used_when_the_hash_is_not_the_plain_payload_hash(table):
    src = world()
    p = next(a for a in src if a.pk == "PROBLEM#IMO_2010_P2")
    p.payload, p.rebuilt_sha256 = None, "f" * 64
    report = rc.reconcile(src, sample_pct=100)
    assert [(d.kind, d.pk, d.expected) for d in report.diffs] == [("sha_mismatch", "PROBLEM#IMO_2010_P2", "f" * 64)]


def test_sampled_items_without_a_payload_are_counted_not_failed(table):
    src = world()
    for a in src:
        a.payload = None
    report = rc.reconcile(src, sample_pct=100)
    assert report.ok and sum(t.sample_skipped for t in report.types) == len(src) and any("not hash-checked" in n for n in report.notes)


def test_sampling_is_deterministic_and_close_to_the_requested_share():
    keys = [(f"PROBLEM#C{i}", "META") for i in range(4000)]
    picked = [k for k in keys if rc.is_sampled(*k, 5.0, "2026-11-03")]
    assert picked == [k for k in keys if rc.is_sampled(*k, 5.0, "2026-11-03")]
    assert 0.03 < len(picked) / len(keys) < 0.07
    assert picked != [k for k in keys if rc.is_sampled(*k, 5.0, "2026-11-04")]      # another seed, another 5 %
    assert all(rc.is_sampled(*k, 100) for k in keys[:20]) and not any(rc.is_sampled(*k, 0) for k in keys[:20])
    with pytest.raises(ValueError):
        rc.reconcile([], sample_pct=101)


def test_an_item_that_lost_its_listing_key_is_reported_as_unlisted(table):
    src = world()
    toolkit.client().update_item(TableName="mb-content-ut", Key={"PK": {"S": "PROBLEM#IMO_2010_P1"}, "SK": {"S": "META"}},
                                 UpdateExpression="REMOVE GSI2PK, GSI2SK")
    report = rc.reconcile(src, sample_pct=0)
    assert [(d.kind, d.pk, d.expected) for d in report.diffs] == [("unlisted", "PROBLEM#IMO_2010_P1", f"PLIST#{IMO}")]


def test_facet_partitions_detect_a_missing_and_a_stale_facet(table):
    src = world()
    toolkit.client().delete_item(TableName="mb-content-ut", Key={"PK": {"S": "FACET#STEP#PROBLEM#p1"}, "SK": {"S": "s1"}})
    seed("FACET", "FACET#STEP#PROBLEM#p1", "gone", {"unit": "STEP", "dim": "PROBLEM", "value": "p1", "entity_id": "gone"})
    report = rc.reconcile(src, sample_pct=0)
    assert kinds(report) == {"missing": [("FACET#STEP#PROBLEM#p1", "s1")], "orphan": [("FACET#STEP#PROBLEM#p1", "gone")]}


def test_vector_state_keys_are_compared_with_the_vector_store_per_family(table):
    store = MemoryVectorStore()
    src = world(store)
    missing_key = str(uuid.UUID(int=100))
    store.delete(Family.STEP, [missing_key])                                        # item says it has it, the index lost it
    put_vec(store, Family.STEP, "stale-vector")                                      # nobody references it
    toolkit.client().update_item(TableName="mb-content-ut", Key={"PK": {"S": "STEP#s2"}, "SK": {"S": "META"}},
                                 UpdateExpression="SET eligible = :v", ExpressionAttributeValues={":v": {"BOOL": False}})
    next(a for a in src if a.pk == "STEP#s2").state = "WITHDRAWN"
    report = rc.reconcile(src, sample_pct=0, vector_keys_by_family={"step": store.keys(Family.STEP), "problem": [], "nope": []})
    got = {(d.kind, d.pk, d.sk, d.expected, d.actual) for d in report.diffs}
    s2_key = str(uuid.UUID(int=101))
    assert got == {
        ("vector_missing", "STEP#s1", "META", missing_key, None),
        # the withdrawn item's vector must have been deleted: it is now an orphan in the index
        ("vector_orphan", "VECTOR#step", s2_key, None, s2_key),
        ("vector_orphan", "VECTOR#step", "stale-vector", None, "stale-vector"),
    }
    assert any("nope" in n for n in report.notes)
    assert report.by_kind() == {"vector_missing": 1, "vector_orphan": 2}


def test_reconcile_never_scans_and_only_queries_or_batch_gets(table, monkeypatch):
    src = world()
    spy_holder: list[Spy] = []
    original = toolkit.client

    def spying(service: str = "dynamodb"):
        c = original(service)
        if service != "dynamodb":
            return c
        spy = Spy(c)
        spy_holder.append(spy)
        return spy

    monkeypatch.setattr(toolkit, "client", spying)
    report = rc.reconcile(src, sample_pct=100)
    calls = {c for s in spy_holder for c in s.calls}
    assert calls <= {"query", "batch_get_item"}, calls
    assert "query" in calls and report.diff_count == 0


def test_max_diffs_bounds_the_listing_but_not_the_counts(table):
    src = world()
    for a in src:
        a.src_rev = 5
    report = rc.reconcile(src, sample_pct=0, max_diffs=3)
    assert len(report.diffs) == 3 and report.diff_count == len(src) and report.truncated == len(src) - 3


def test_the_reconciler_does_not_import_postgres():
    code = Path(rc.__file__).read_text()
    assert "postgres" not in code.lower().replace("postgresql", "") and "sqlalchemy" not in code


# ------------------------------------------------------------------ publisher

def comp_agg(rev: int, name: str = "IMO", **kw: Any) -> pub.PublishedAggregate:
    cid = str(uuid.UUID(int=1))
    return pub.PublishedAggregate(type="COMPETITION", id=cid, pk="CATALOG#COMPETITION", sk=f"COMP#IMO#{cid}", src_rev=rev,
                                  payload={"competition_id": cid, "external_code": "IMO", "name": name, "level": "INTERNATIONAL"}, **kw)


def stored(pk: str, sk: str) -> dict:
    return toolkit.get_item("content", pk, sk)


def problem_agg(rev: int, state: str = "ACTIVE", text: str = "S") -> pub.PublishedAggregate:
    pid = str(uuid.UUID(int=7))
    return pub.PublishedAggregate(
        type="PROBLEM", id="IMO_2010_P1", pk="PROBLEM#IMO_2010_P1", sk="META", src_rev=rev, state=state,
        gsi={"GSI1PK": f"PID#{pid}", "GSI1SK": "META", "GSI2PK": "PLIST#IMO", "GSI2SK": "2010#IMO-2010#000001"},
        payload={"canonical_code": "IMO_2010_P1", "problem_number": 1, "competition": {
            "competition_id": str(uuid.UUID(int=1)), "external_code": "IMO", "level": "L", "name": "IMO"},
            "images": [], "paper_code": "IMO-2010", "paper_id": str(uuid.UUID(int=2)), "problem_id": pid,
            "created_at": "2026-01-01T00:00:00.000000Z", "updated_at": "2026-01-01T00:00:00.000000Z",
            "statement_text": text})


def taxnode_agg(rev: int, state: str = "ACTIVE") -> pub.PublishedAggregate:
    return pub.PublishedAggregate(
        type="TAXNODE", id="n1", pk="TAXNODE#n1", sk="META", src_rev=rev, state=state,
        gsi={"GSI2PK": "TAXTYPE#SKILL", "GSI2SK": "001##n1"},
        payload={"taxonomy_node_id": "n1", "name": "N", "node_type": "SKILL", "lifecycle": "ACTIVE", "problem_count": 0,
                 "example_problem_codes": [], "updated_at": "2026-01-01T00:00:00.000000Z",
                 "vector_state": {"index": "taxonomy-node-te3small-1536-v1", "keys": ["n1"], "model": "m", "sha256": "a" * 64}})


def test_publish_writes_a_new_item_with_the_canonical_hash_and_bookkeeping(table):
    a = comp_agg(4)
    r = pub.publish_aggregate(a)
    assert r.status == "written" and r.applied and r.existing_src_rev is None
    item = stored(a.pk, a.sk)
    assert item["src_rev"] == 4 and item["version"] == 1 and item["type"] == "COMPETITION"
    assert item["content_sha256"] == pub.canonical_sha256(a.payload) == a.content_sha256


def test_publishing_the_same_revision_and_hash_again_is_a_noop(table):
    a = comp_agg(4)
    pub.publish_aggregate(a)
    before = stored(a.pk, a.sk)
    again = pub.publish_aggregate(comp_agg(4))
    assert again.status == "noop" and not again.applied
    assert stored(a.pk, a.sk) == before                      # nothing was written, not even `version`


def test_an_older_or_equal_revision_never_overwrites_a_newer_item(table):
    pub.publish_aggregate(comp_agg(5))
    before = stored(*(comp_agg(5).pk, comp_agg(5).sk))
    older = pub.publish_aggregate(comp_agg(3, name="IMO renamed"))
    assert older.status == "stale" and older.existing_src_rev == 5 and not older.applied
    same_rev_other_content = pub.publish_aggregate(comp_agg(5, name="IMO renamed"))
    assert same_rev_other_content.status == "conflict"
    assert stored(comp_agg(5).pk, comp_agg(5).sk) == before
    with pytest.raises(ConditionFailed):
        pub.publish_aggregate(comp_agg(2, name="x"), raise_on_stale=True)


def test_a_newer_revision_with_identical_content_only_bumps_src_rev(table):
    pub.publish_aggregate(comp_agg(1))
    r = pub.publish_aggregate(comp_agg(6))
    item = stored(comp_agg(1).pk, comp_agg(1).sk)
    assert r.status == "bumped" and item["src_rev"] == 6 and item["version"] == 2
    assert item["content_sha256"] == comp_agg(1).content_sha256 and item["name"] == "IMO"


def test_a_newer_revision_with_new_content_replaces_the_item(table):
    pub.publish_aggregate(comp_agg(1))
    r = pub.publish_aggregate(comp_agg(2, name="IMO (renamed)"))
    item = stored(comp_agg(1).pk, comp_agg(1).sk)
    assert r.status == "written" and item["name"] == "IMO (renamed)" and item["src_rev"] == 2 and item["version"] == 2


def test_losing_the_race_to_a_newer_publisher_is_reported_as_stale_not_an_error(table, monkeypatch):
    pub.publish_aggregate(comp_agg(9))
    real_get = pub.typed.get
    calls = {"n": 0}

    def stale_read_once(model, pk, sk, **kw):
        calls["n"] += 1
        return None if calls["n"] == 1 else real_get(model, pk, sk, **kw)

    monkeypatch.setattr(pub.typed, "get", stale_read_once)
    r = pub.publish_aggregate(comp_agg(4, name="old"))
    assert r.status == "stale" and r.existing_src_rev == 9
    assert stored(comp_agg(1).pk, comp_agg(1).sk)["src_rev"] == 9


def test_the_contract_rejects_inconsistent_aggregates():
    p = comp_agg(1).payload
    with pytest.raises(ValueError, match="does not match"):
        pub.PublishedAggregate(type="COMPETITION", id="x", pk="a", sk="b", src_rev=1, payload=p, content_sha256="0" * 64)
    with pytest.raises(ValueError, match="keys or bookkeeping"):
        pub.PublishedAggregate(type="COMPETITION", id="x", pk="a", sk="b", src_rev=1, payload={**p, "src_rev": 1})
    with pytest.raises(ValueError, match="cannot be published as WITHDRAWN"):
        pub.PublishedAggregate(type="COMPETITION", id="x", pk="a", sk="b", src_rev=1, payload=p, state="WITHDRAWN")
    with pytest.raises(ValueError, match="contradicts"):
        pub.PublishedAggregate(type="PROBLEM", id="x", pk="a", sk="b", src_rev=1, payload={"visibility": "WITHDRAWN"}, state="ACTIVE")
    with pytest.raises(ValueError, match="required"):
        pub.PublishedAggregate(type="MCREL", id="x", pk="a", sk="b", src_rev=1, payload=p, sha_basis="external")
    ext = pub.PublishedAggregate(type="MCREL", id="x", pk="a", sk="b", src_rev=1, payload=p, sha_basis="external", content_sha256="a" * 64)
    assert ext.content_sha256 == "a" * 64


def test_the_state_attribute_is_part_of_the_hashed_payload_like_in_the_migration():
    a = problem_agg(1)
    assert a.payload["visibility"] == "ACTIVE" and a.content_sha256 == pub.canonical_sha256(a.payload)
    assert taxnode_agg(1).payload["eligible"] is True and taxnode_agg(1, "WITHDRAWN").payload["eligible"] is False


def test_withdraw_flips_visibility_bumps_src_rev_and_drops_the_listing_keys(table):
    a = problem_agg(2)
    pub.publish_aggregate(a)
    assert stored(a.pk, a.sk)["GSI2PK"] == "PLIST#IMO"
    r = pub.withdraw_aggregate("PROBLEM", a.pk, a.sk, 5)
    item = stored(a.pk, a.sk)
    assert r.status == "withdrawn" and item["visibility"] == "WITHDRAWN" and item["src_rev"] == 5 and item["version"] == 2
    assert "GSI2PK" not in item and "GSI2SK" not in item and item["GSI1PK"].startswith("PID#")      # historic attempts still resolve
    assert item["statement_text"] == "S"                                                           # META is kept


def test_withdraw_flips_eligible_and_can_store_the_hash_of_the_withdrawn_payload(table):
    a = taxnode_agg(1)
    pub.publish_aggregate(a)
    new_sha = taxnode_agg(1, "WITHDRAWN").content_sha256
    r = pub.withdraw_aggregate("TAXNODE", a.pk, a.sk, 2, content_sha256=new_sha)
    item = stored(a.pk, a.sk)
    assert r.status == "withdrawn" and item["eligible"] is False and item["src_rev"] == 2 and item["content_sha256"] == new_sha


def test_withdraw_is_idempotent_ordered_and_safe_for_missing_items(table):
    a = problem_agg(2)
    assert pub.withdraw_aggregate("PROBLEM", a.pk, a.sk, 3).status == "absent"
    pub.publish_aggregate(a)
    assert pub.withdraw_aggregate("PROBLEM", a.pk, a.sk, 4).status == "withdrawn"
    assert pub.withdraw_aggregate("PROBLEM", a.pk, a.sk, 4).status == "noop"
    assert pub.withdraw_aggregate("PROBLEM", a.pk, a.sk, 3).status == "stale"
    assert pub.withdraw_aggregate("PROBLEM", a.pk, a.sk, 7).status == "bumped"          # already withdrawn: only the revision moves
    assert stored(a.pk, a.sk)["src_rev"] == 7
    # an older publish never resurrects a withdrawn item
    assert pub.publish_aggregate(problem_agg(3)).status == "stale"
    assert stored(a.pk, a.sk)["visibility"] == "WITHDRAWN"
    with pytest.raises(ValueError):
        pub.withdraw_aggregate("COMPETITION", "CATALOG#COMPETITION", "x", 1)


def test_a_newer_publish_reactivates_a_withdrawn_problem_with_its_listing_keys(table):
    pub.publish_aggregate(problem_agg(1))
    pub.withdraw_aggregate("PROBLEM", "PROBLEM#IMO_2010_P1", "META", 2)
    r = pub.publish_aggregate(problem_agg(3))
    item = stored("PROBLEM#IMO_2010_P1", "META")
    assert r.status == "written" and item["visibility"] == "ACTIVE" and item["GSI2PK"] == "PLIST#IMO" and item["src_rev"] == 3


def test_published_and_withdrawn_items_reconcile_cleanly_against_their_source(table):
    pub.publish_all([comp_agg(0), problem_agg(0), taxnode_agg(0)])
    pub.publish_aggregate(problem_agg(1, text="v2"))
    pub.withdraw_aggregate("TAXNODE", "TAXNODE#n1", "META", 1)
    p, t, c = problem_agg(1, text="v2"), taxnode_agg(1, "WITHDRAWN"), comp_agg(0)
    src = [
        rc.SourceAggregate(type="COMPETITION", pk=c.pk, sk=c.sk, payload=c.payload, list_pk="CATALOG#COMPETITION"),
        rc.SourceAggregate(type="PROBLEM", pk=p.pk, sk=p.sk, src_rev=1, payload=p.payload, list_index="GSI2", list_pk="PLIST#IMO"),
        rc.SourceAggregate(type="TAXNODE", pk=t.pk, sk=t.sk, src_rev=1, state="WITHDRAWN"),
    ]
    report = rc.reconcile(src, sample_pct=100)
    assert report.ok, report.diffs


# ------------------------------------------------------------------ admin route

@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(settings, "admin_api_key", KEY)
    app = FastAPI()
    app.include_router(admin_content.router)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def audited(monkeypatch):
    class Conn:
        pass

    class Engine:
        def begin(self):
            import contextlib

            @contextlib.contextmanager
            def cm():
                yield Conn()

            return cm()

    log: list[dict] = []
    monkeypatch.setattr(admin_content, "engine", Engine())
    monkeypatch.setattr(admin_content, "record_audit_event",
                        lambda conn, actor_type, actor_id, action, entity_type, entity_id, **kw: log.append(
                            {"actor_type": actor_type, "actor_id": actor_id, "action": action, "entity": (entity_type, entity_id), **kw}))
    return log


def test_the_reconcile_route_requires_admin_credentials(client, audited, monkeypatch):
    monkeypatch.setattr(admin_content, "_read_sources", lambda req, seed: ([], []))
    assert client.post("/v1/admin/content/reconcile", json={}).status_code == 401
    assert client.post("/v1/admin/content/reconcile", json={}, headers={"X-Admin-Api-Key": "wrong"}).status_code == 401
    assert client.get("/v1/admin/content/reconcile/status").status_code == 401
    assert audited == []
    ok = client.post("/v1/admin/content/reconcile", json={}, headers={"X-Admin-Api-Key": KEY})
    assert ok.status_code == 200 and ok.json()["ok"] is True


def test_the_reconcile_route_returns_the_report_and_audits_the_actor(client, audited, table, monkeypatch):
    src = world()
    next(a for a in src if a.pk == "PROBLEM#IMO_2010_P1").src_rev = 4
    seen = {}

    def read(req, seed):
        seen.update(types=req.types, pct=req.sample_pct, seed=seed)
        return src, ["pipeline.content_revision does not exist yet"]

    monkeypatch.setattr(admin_content, "_read_sources", read)
    r = client.post("/v1/admin/content/reconcile", headers={"X-Admin-Api-Key": KEY}, json={"types": ["PROBLEM"], "sample_pct": 100})
    body = r.json()
    assert r.status_code == 200 and body["ok"] is False and body["diff_count"] == 1
    assert body["diffs"][0]["kind"] == "src_rev_mismatch" and body["notes"][0].startswith("pipeline.content_revision")
    assert seen["types"] == ["PROBLEM"] and seen["pct"] == 100
    [entry] = audited
    assert (entry["actor_type"], entry["actor_id"], entry["action"], entry["entity"]) == ("ADMIN", SERVICE_ACTOR_ID, "CONTENT_RECONCILE", ("content", "mb-content"))
    assert entry["after_state"]["diff_count"] == 1 and entry["after_state"]["by_kind"] == {"src_rev_mismatch": 1}
    status = client.get("/v1/admin/content/reconcile/status", headers={"X-Admin-Api-Key": KEY}).json()
    assert status["last_run"]["actor"] == SERVICE_ACTOR_ID and status["last_run"]["diff_count"] == 1


def test_the_actor_cannot_be_supplied_by_the_client_and_bad_bodies_are_rejected(client, audited):
    h = {"X-Admin-Api-Key": KEY}
    assert client.post("/v1/admin/content/reconcile", headers=h, json={"actor": "mallory"}).status_code == 422
    assert client.post("/v1/admin/content/reconcile", headers=h, json={"sample_pct": 101}).status_code == 422
    assert client.post("/v1/admin/content/reconcile", headers=h, json={"types": ["NOPE"]}).status_code == 422
    assert audited == []


def test_include_vectors_lists_only_the_families_of_the_requested_types(client, audited, table, monkeypatch):
    from mathbank_rest.vector_store import set_vector_store_for_tests

    store = MemoryVectorStore()
    src = world(store)
    put_vec(store, Family.PROBLEM, "p-stray")
    set_vector_store_for_tests(store)
    try:
        monkeypatch.setattr(admin_content, "_read_sources", lambda req, seed: ([a for a in src if a.type == "STEP"], []))
        r = client.post("/v1/admin/content/reconcile", headers={"X-Admin-Api-Key": KEY},
                        json={"types": ["STEP"], "include_vectors": True})
        body = r.json()
        assert body["ok"] is True and [v["family"] for v in body["vectors"]] == ["step"]
    finally:
        set_vector_store_for_tests(None)


def test_the_router_is_registered_in_the_admin_group_only():
    groups = profiles.partition()
    assert "admin_content" in groups["admin"] and not any("admin_content" in groups[g] for g in ("runtime", "runtime_pending", "socratic"))
    assert "admin_content" in profiles.PROFILES["combined"] and "admin_content" not in profiles.PROFILES["runtime"]
    admin_paths = set(profiles.create_app("admin").openapi()["paths"])
    runtime_paths = set(profiles.create_app("runtime").openapi()["paths"])
    assert "/v1/admin/content/reconcile" in admin_paths and "/v1/admin/content/reconcile/status" in admin_paths
    assert not any(p.startswith("/v1/admin/content") for p in runtime_paths)


class FakeResult:
    def __init__(self, rows=None, scalar=None):
        self._rows, self._scalar = rows or [], scalar

    def mappings(self):
        return self._rows

    def scalar(self):
        return self._scalar


class FakeConn:
    """Answers each SQL by a marker substring of the statement; records every statement (all must be reads)."""

    def __init__(self, answers: dict[str, FakeResult]):
        self.answers, self.sql = answers, []

    def execute(self, stmt, *_a, **_k):
        sql = str(stmt)
        self.sql.append(sql)
        for marker, result in self.answers.items():
            if marker in sql:
                return result
        raise AssertionError(f"unexpected SQL: {sql[:80]}")


def test_build_sources_maps_postgres_facts_and_a_seeded_world_reconciles_clean(table):
    cid, aid = uuid.UUID(int=11), uuid.UUID(int=12)
    comp = {"competition_id": cid, "external_code": IMO, "name": "IMO", "organization": None, "country": "INT", "level": "L"}
    act = {"activity_id": aid, "activity_type": "MCQ", "prompt": "p", "options": ["a", "b"], "target_skill": None,
           "target_skill_id": None, "source_problem_id": None, "estimated_seconds": 30, "source_type": "PRECOMPILED",
           "persistence_mode": "STATIC", "status": "ACTIVE", "created_at": None, "published": True}
    conn = FakeConn({
        "to_regclass": FakeResult(scalar=None),
        "FROM core.competition\n": FakeResult([comp]),
        "FROM core.problem p": FakeResult([
            {"problem_id": uuid.UUID(int=1), "canonical_code": "IMO_2010_P1", "published": True, "competition_code": IMO},
            {"problem_id": uuid.UUID(int=2), "canonical_code": "IMO_2010_P2", "published": False, "competition_code": IMO}]),
        "FROM activity.definition": FakeResult([act]),
        "FROM pedagogy.solution_step s": FakeResult([
            {"solution_step_id": "s1", "solution_id": uuid.UUID(int=3), "problem_id": uuid.UUID(int=1), "published": True, "has_vec": True}]),
        "FROM pedagogy.learning_item li": FakeResult([
            {"learning_item_id": "l1", "target_subconcept_node_id": "sub1", "published": True, "has_vec": False}]),
        "FROM pedagogy.taxonomy_node": FakeResult([{"taxonomy_node_id": "n1", "node_type": "SKILL"}]),
        "FROM pedagogy.micro_course c": FakeResult([{"micro_course_id": uuid.UUID(int=4), "canonical_code": "MCX", "published": False}]),
    })
    req = admin_content.ReconcileRequest(sample_pct=100, include_facets=True)
    sources, notes = admin_content.build_sources(conn, req, "seed")
    assert notes and "pipeline.content_revision" in notes[0]
    by_pk = {(a.pk, a.sk): a for a in sources}
    assert by_pk[("PROBLEM#IMO_2010_P1", "META")].list_pk == "PLIST#IMO" and by_pk[("PROBLEM#IMO_2010_P1", "META")].state == "ACTIVE"
    retired = by_pk[("PROBLEM#IMO_2010_P2", "META")]
    assert retired.state == "WITHDRAWN" and retired.list_pk is None
    assert by_pk[("FACET#STEP#PROBLEM#" + str(uuid.UUID(int=1)), "s1")].state == "ACTIVE"
    assert by_pk[("FACET#LI#TARGET_SUBCONCEPT#sub1", "l1")].state == "WITHDRAWN"      # no vector, so no facet is expected
    assert by_pk[("MC#MCX", "META")].state == "WITHDRAWN" and by_pk[("TAXNODE#n1", "META")].list_pk == "TAXTYPE#SKILL"
    assert by_pk[("ACT#" + str(aid), "META")].payload["options"] == ["a", "b"]
    assert all(s.lstrip().upper().startswith(("SELECT", "WITH")) for s in conn.sql)            # read-only

    # seed DynamoDB the way the migration does for the same rows, and reconcile: 0 diffs
    seed("COMPETITION", "CATALOG#COMPETITION", f"COMP#IMO#{cid}", {k: v for k, v in comp.items()})
    seed("PROBLEM", "PROBLEM#IMO_2010_P1", "META", {"canonical_code": "IMO_2010_P1", "visibility": "ACTIVE"},
         gsi={"GSI2PK": "PLIST#IMO", "GSI2SK": "x"})
    seed("PROBLEM", "PROBLEM#IMO_2010_P2", "META", {"canonical_code": "IMO_2010_P2", "visibility": "WITHDRAWN"})
    seed("ACT", f"ACT#{aid}", "META", {k: v for k, v in act.items() if k != "published"})
    seed("STEP", "STEP#s1", "META", {"solution_step_id": "s1", "eligible": True})
    seed("FACET", f"FACET#STEP#PROBLEM#{uuid.UUID(int=1)}", "s1", {"entity_id": "s1"})
    seed("LI", "LI#l1", "META", {"learning_item_id": "l1", "eligible": True})
    seed("TAXNODE", "TAXNODE#n1", "META", {"taxonomy_node_id": "n1", "eligible": True}, gsi={"GSI2PK": "TAXTYPE#SKILL", "GSI2SK": "x"})
    seed("MC", "MC#MCX", "META", {"canonical_code": "MCX", "status": "UNPUBLISHED"})
    report = rc.reconcile(sources, sample_pct=100)
    assert report.ok, report.diffs
    by_type = {t.type: t for t in report.types}
    assert by_type["COMPETITION"].sampled == 1 and by_type["ACT"].sampled == 1 and by_type["PROBLEM"].sample_skipped == 1


def test_build_sources_compares_against_content_revision_when_the_table_exists():
    pid = uuid.UUID(int=1)
    conn = FakeConn({
        "to_regclass": FakeResult(scalar="pipeline.content_revision"),
        "FROM pipeline.content_revision": FakeResult([{"aggregate_type": "PROBLEM", "aggregate_id": str(pid), "rev": 6}]),
        "FROM core.problem p": FakeResult([{"problem_id": pid, "canonical_code": "C1", "published": True, "competition_code": IMO}]),
    })
    sources, notes = admin_content.build_sources(conn, admin_content.ReconcileRequest(types=["PROBLEM"]), "s")
    assert notes == [] and [a.src_rev for a in sources] == [6]


# ------------------------------------------------------------------ scripts/content_parity.py

def _parity_script():
    import importlib.util

    spec = importlib.util.spec_from_file_location("content_parity", Path(__file__).resolve().parents[2] / "scripts" / "content_parity.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_parity_script_turns_migration_items_into_expectations_and_renders_a_verdict(table):
    script = _parity_script()
    item = seed("PROBLEM", "PROBLEM#P1", "META", {"canonical_code": "P1", "visibility": "ACTIVE"}, gsi={"GSI2PK": "PLIST#IMO", "GSI2SK": "x"})
    a = script.aggregate_from_item(item)
    assert (a.type, a.state, a.list_index, a.list_pk, a.src_rev, a.rebuilt_sha256) == ("PROBLEM", "ACTIVE", "GSI2", "PLIST#IMO", 0, item["content_sha256"])
    facet = script.aggregate_from_item({"type": "FACET", "PK": "FACET#STEP#SKILL#k", "SK": "s", "src_rev": 0, "content_sha256": "a" * 64})
    assert facet.list_index is None and facet.list_pk == "FACET#STEP#SKILL#k"
    assert script.aggregate_from_item({**item, "visibility": "WITHDRAWN"}).state == "WITHDRAWN"
    ok = rc.reconcile([a], sample_pct=100)
    assert "PARITY OK: 0 diffs" in script.render(ok)
    bad = rc.reconcile([a.model_copy(update={"rebuilt_sha256": "b" * 64})], sample_pct=100)
    assert "PARITY FAILED: 1 diffs" in script.render(bad) and "sha_mismatch" in script.render(bad)
    assert script.main(["--env", "prod"]) == 2                         # refuses prod without --allow-prod
