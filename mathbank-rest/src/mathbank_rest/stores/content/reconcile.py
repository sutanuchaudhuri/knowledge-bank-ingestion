"""Reconciliation of ``mb-content`` against the authoritative source (requirement 70 C6 §4a, requirement 71 WP4).

``reconcile`` takes the facts the caller read from PostgreSQL (``SourceAggregate``; this module never imports
PostgreSQL) and compares them with the items in ``mb-content``:

================  ============================================================================================
kind              meaning
================  ============================================================================================
missing           published in the source, no item in DynamoDB
orphan            ACTIVE item in a listing partition that the source does not know
src_rev_mismatch  ``src_rev`` differs from the source revision (stale item, or a revision never applied)
state_mismatch    ``visibility``/``eligible``/``status`` disagrees (published in PG but withdrawn here, or the reverse)
sha_mismatch      sampled rebuild: the canonical sha256 of the rebuilt payload differs from ``content_sha256``
unlisted          ACTIVE item exists but is not in the listing partition where its list endpoint would find it
vector_missing    ``vector_state.keys`` of an ACTIVE item that S3 Vectors does not hold
vector_orphan     a key in S3 Vectors that no ACTIVE item references (e.g. the vector of a withdrawn item)
================  ============================================================================================

No scan: items are read by ``BatchGetItem`` of the source keys and by ``Query`` of listing partitions (a GSI2
partition such as ``PLIST#<comp>``, ``TAXTYPE#<node_type>``, ``CATALOG#MC``, or the main-table partitions
``CATALOG#COMPETITION`` and ``FACET#...``). Orphans are therefore only detectable where a listing partition exists:

* COMPETITION, PROBLEM (``PLIST#<competition code>``), TAXNODE (``TAXTYPE#<type>``), MC (``CATALOG#MC``) and FACET
  (its own ``FACET#...`` partition, when the caller supplies FACET aggregates).
* STEP, LI, ACT, SOLDAG, CONCEPT... have no listing partition: a stray item there is not found unless its FACET
  partition is reconciled. A PROBLEM withdrawn in place loses ``GSI2PK``, so a withdrawn-but-present problem is
  found by BatchGet of the source key, not by listing.
* Listing partitions are only queried when the source holds at least one aggregate for the type (or, for the static
  catalogues, the type is present), so an unknown competition/node type with no source rows is not discovered.

Queries return whole items (GSI projection ALL); the largest partitions (a competition's problems) are paged by 200.
"""
from __future__ import annotations

import datetime as dt
import hashlib
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field

from mathbank_rest.content_publisher import ContentBookkeeping, State, canonical_sha256
from mathbank_rest.stores import typed

DiffKind = Literal["missing", "orphan", "src_rev_mismatch", "state_mismatch", "sha_mismatch", "unlisted",
                   "vector_missing", "vector_orphan"]

PAGE = 200
# Partitions that always exist for a catalogue type: (index, partition key).
STATIC_PARTITIONS: dict[str, tuple[tuple[str | None, str], ...]] = {
    "COMPETITION": ((None, "CATALOG#COMPETITION"),),
    "MC": (("GSI2", "CATALOG#MC"),),
    "TAXNODE": tuple(("GSI2", f"TAXTYPE#{t}") for t in ("CONCEPT", "DOMAIN", "SKILL", "SUBCONCEPT", "TECHNIQUE")),
}
# vector family -> (item type, attribute holding {"keys": [...]}) (requirement 70 C6 §3 ``vector_state``)
VECTOR_FAMILIES: dict[str, tuple[str, str]] = {
    "problem": ("PROBLEM", "vector_state"),
    "solution": ("SOLUTION", "vector_state"),
    "step": ("STEP", "vector_state"),
    "learning-item": ("LI", "vector_state"),
    "taxonomy-node": ("TAXNODE", "vector_state"),
    "taxonomy-search": ("TAXNODE", "search_vector_state"),
    "misconception": ("MISCONCEPTION", "vector_state"),
    "theorem": ("THEOREM", "vector_state"),
}

Key = tuple[str, str]


class SourceAggregate(BaseModel):
    """What the source (PostgreSQL) says about one ``mb-content`` item."""

    type: str
    pk: str
    sk: str
    id: str | None = None
    src_rev: int = 0
    state: State = "ACTIVE"
    list_index: str | None = Field(default=None, description="GSI where the item is listed; None = main table")
    list_pk: str | None = Field(default=None, description="partition where the item is listed (ACTIVE items only)")
    payload: dict[str, Any] | None = Field(default=None, description="rebuilt canonical payload (sampled items only)")
    rebuilt_sha256: str | None = Field(default=None, description="rebuilt hash when it is not the plain payload hash")

    @property
    def key(self) -> Key:
        return self.pk, self.sk


class ReconcileDiff(BaseModel):
    type: str
    kind: DiffKind
    pk: str
    sk: str
    expected: str | None = None
    actual: str | None = None
    detail: str | None = None


class TypeSummary(BaseModel):
    type: str
    source: int = 0
    active: int = 0
    found: int = 0
    sampled: int = 0
    sample_skipped: int = 0
    diffs: dict[str, int] = Field(default_factory=dict)


class VectorSummary(BaseModel):
    family: str
    expected: int
    in_store: int
    missing: int
    orphan: int


class ReconcileReport(BaseModel):
    started_at: str
    sample_pct: float
    sample_seed: str
    types: list[TypeSummary]
    vectors: list[VectorSummary] = Field(default_factory=list)
    diff_count: int = 0
    diffs: list[ReconcileDiff] = Field(default_factory=list)
    truncated: int = 0
    notes: list[str] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ok(self) -> bool:
        return self.diff_count == 0

    def by_kind(self) -> dict[str, int]:
        out: dict[str, int] = defaultdict(int)
        for t in self.types:
            for k, n in t.diffs.items():
                out[k] += n
        return {k: n for k, n in out.items() if n}


def is_sampled(pk: str, sk: str, sample_pct: float, seed: str = "") -> bool:
    """Deterministic sampling: the same (seed, key) is always in or out, so a caller can build payloads only for the
    sampled aggregates. ``sample_pct=100`` selects everything (the weekly full run), 0 nothing."""
    if sample_pct >= 100:
        return True
    if sample_pct <= 0:
        return False
    bucket = int(hashlib.sha256(f"{seed}|{pk}|{sk}".encode()).hexdigest()[:8], 16) % 10_000
    return bucket < sample_pct * 100


def _query_partition(index: str | None, pk: str) -> list[ContentBookkeeping]:
    items: list[ContentBookkeeping] = []
    token: str | None = None
    while True:
        kw: dict[str, Any] = {"limit": PAGE, "next_token": token}
        if index:
            kw["index"] = index
        page = typed.query(ContentBookkeeping, pk, **kw)
        items.extend(page.items)
        token = page.next_token
        if not token:
            return items


def _vector_keys(item: ContentBookkeeping, attr: str) -> list[str]:
    state = getattr(item, attr, None) or {}
    return [str(k) for k in state.get("keys") or []]


class _Run:
    def __init__(self, source: list[SourceAggregate], sample_pct: float, seed: str, max_diffs: int) -> None:
        self.source = source
        self.by_key: dict[Key, SourceAggregate] = {a.key: a for a in source}
        self.sample_pct, self.seed, self.max_diffs = sample_pct, seed, max_diffs
        self.summary: dict[str, TypeSummary] = {}
        self.diffs: list[ReconcileDiff] = []
        self.diff_count = 0
        self.items: dict[Key, ContentBookkeeping] = {}
        self.listed: dict[tuple[str | None, str], set[Key]] = {}
        self.notes: list[str] = []

    def add(self, d: ReconcileDiff) -> None:
        self.diff_count += 1
        s = self.summary.setdefault(d.type, TypeSummary(type=d.type))
        s.diffs[d.kind] = s.diffs.get(d.kind, 0) + 1
        if len(self.diffs) < self.max_diffs:
            self.diffs.append(d)

    # -------------------------------------------------------------- reading

    def partitions(self) -> list[tuple[str | None, str]]:
        types = {a.type for a in self.source}
        wanted: dict[tuple[str | None, str], None] = {}
        for t in types:
            for p in STATIC_PARTITIONS.get(t, ()):
                wanted[p] = None
        for a in self.source:
            if a.list_pk:
                wanted[(a.list_index, a.list_pk)] = None
        return list(wanted)

    def read(self) -> None:
        todo = self.partitions()
        queried: set[tuple[str | None, str]] = set()
        while todo:
            part = todo.pop(0)
            if part in queried:
                continue
            queried.add(part)
            found = _query_partition(*part)
            self.listed[part] = {(i.PK, i.SK) for i in found}
            for i in found:
                self.items[(i.PK, i.SK)] = i
            # one PLIST partition per competition: discover codes that exist in DynamoDB but not in the source
            if part == (None, "CATALOG#COMPETITION") and any(a.type == "PROBLEM" for a in self.source):
                for i in found:
                    code = (i.model_extra or {}).get("external_code")
                    if code:
                        todo.append(("GSI2", f"PLIST#{code}"))
        missing = [a.key for a in self.source if a.key not in self.items]
        for i in typed.batch_get(ContentBookkeeping, missing, consistent=False):
            self.items[(i.PK, i.SK)] = i

    # -------------------------------------------------------------- comparing

    def compare(self) -> None:
        for a in self.source:
            s = self.summary.setdefault(a.type, TypeSummary(type=a.type))
            s.source += 1
            s.active += a.state == "ACTIVE"
            item = self.items.get(a.key)
            if item is None:
                if a.state == "ACTIVE":
                    self.add(ReconcileDiff(type=a.type, kind="missing", pk=a.pk, sk=a.sk, expected="ACTIVE", actual=None))
                continue
            s.found += 1
            if item.rev != a.src_rev:
                self.add(ReconcileDiff(type=a.type, kind="src_rev_mismatch", pk=a.pk, sk=a.sk, expected=str(a.src_rev),
                                       actual=str(item.rev)))
            if item.state != a.state:
                self.add(ReconcileDiff(type=a.type, kind="state_mismatch", pk=a.pk, sk=a.sk, expected=a.state, actual=item.state))
            if a.state == "ACTIVE" and a.list_pk and a.key not in self.listed.get((a.list_index, a.list_pk), set()):
                self.add(ReconcileDiff(type=a.type, kind="unlisted", pk=a.pk, sk=a.sk, expected=a.list_pk, actual=None,
                                       detail=f"not in {a.list_index or 'main table'} partition (GSI lag or dropped key)"))
            if a.state == "ACTIVE" and is_sampled(a.pk, a.sk, self.sample_pct, self.seed):
                self.compare_sha(a, item, s)

    def compare_sha(self, a: SourceAggregate, item: ContentBookkeeping, s: TypeSummary) -> None:
        if a.rebuilt_sha256 is not None:
            rebuilt = a.rebuilt_sha256
        elif a.payload is not None:
            rebuilt = canonical_sha256(a.payload)
        else:
            s.sample_skipped += 1
            return
        s.sampled += 1
        if rebuilt != item.content_sha256:
            self.add(ReconcileDiff(type=a.type, kind="sha_mismatch", pk=a.pk, sk=a.sk, expected=rebuilt, actual=item.content_sha256))

    def orphans(self) -> None:
        for (index, pk), keys in self.listed.items():
            for key in sorted(keys):
                item = self.items[key]
                if key not in self.by_key and item.state == "ACTIVE":
                    self.add(ReconcileDiff(type=item.type, kind="orphan", pk=key[0], sk=key[1], expected=None, actual="ACTIVE",
                                           detail=f"listed in {index or 'main table'} partition {pk}, unknown to the source"))

    # -------------------------------------------------------------- vectors

    def vectors(self, in_store: Mapping[str, Iterable[str]]) -> list[VectorSummary]:
        out: list[VectorSummary] = []
        types = {a.type for a in self.source}
        for family, keys in in_store.items():
            if family not in VECTOR_FAMILIES:
                self.notes.append(f"vector family {family!r} is not known to the reconciler; skipped")
                continue
            type_, attr = VECTOR_FAMILIES[family]
            if type_ not in types:
                self.notes.append(f"vector family {family!r} skipped: the source has no {type_} aggregates")
                continue
            store = {str(k) for k in keys}
            owner: dict[str, Key] = {}
            for key, item in self.items.items():
                if item.type == type_ and item.state == "ACTIVE":
                    for k in _vector_keys(item, attr):
                        owner[k] = key
            missing, orphan = sorted(set(owner) - store), sorted(store - set(owner))
            for k in missing:
                self.add(ReconcileDiff(type=type_, kind="vector_missing", pk=owner[k][0], sk=owner[k][1], expected=k,
                                       actual=None, detail=f"family {family}"))
            for k in orphan:
                self.add(ReconcileDiff(type=type_, kind="vector_orphan", pk=f"VECTOR#{family}", sk=k, expected=None, actual=k,
                                       detail="no ACTIVE item references this vector"))
            out.append(VectorSummary(family=family, expected=len(owner), in_store=len(store), missing=len(missing),
                                     orphan=len(orphan)))
        return out


def reconcile(source: Iterable[SourceAggregate], *, sample_pct: float = 5.0, sample_seed: str = "",
              vector_keys_by_family: Mapping[str, Iterable[str]] | None = None, max_diffs: int = 1000) -> ReconcileReport:
    """Compare ``source`` with ``mb-content``. ``vector_keys_by_family`` maps a vector family to the keys S3 Vectors
    holds for it (``VectorStore.keys``); only those families are checked. ``max_diffs`` bounds the listed diffs, the
    counts stay exact."""
    if not 0 <= sample_pct <= 100:
        raise ValueError("sample_pct must be between 0 and 100")
    run = _Run(list(source), sample_pct, sample_seed, max_diffs)
    run.read()
    run.compare()
    run.orphans()
    vectors = run.vectors(vector_keys_by_family) if vector_keys_by_family else []
    if any(s.sample_skipped for s in run.summary.values()):
        run.notes.append("sampled items without a rebuilt payload were not hash-checked (see sample_skipped per type)")
    return ReconcileReport(
        started_at=dt.datetime.now(dt.UTC).replace(tzinfo=None).isoformat(timespec="seconds") + "Z",
        sample_pct=sample_pct, sample_seed=sample_seed, types=sorted(run.summary.values(), key=lambda t: t.type),
        vectors=vectors, diff_count=run.diff_count, diffs=run.diffs, truncated=max(0, run.diff_count - len(run.diffs)),
        notes=run.notes)
