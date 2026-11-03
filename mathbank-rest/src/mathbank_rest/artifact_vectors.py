"""Artifact-bundle vector search on S3 Vectors (requirement 71 WP2; ART-F05, ART-F16, ART-S06, ART-E07).

Adapter-level logic only: no Postgres, no bundle hydration (``artifact_runtime`` re-checks every hit against the bundle).

Two indexes, one key (the bundle id) in each:
* ``ARTIFACT_PUBLIC``  - reusable, staff-published bundles; filterable by subject, status and the concept/skill/theorem tags;
* ``ARTIFACT_PRIVATE`` - a student's own artifacts; every vector carries ``owner_student_id`` and **every** query of this
  index carries ``owner_student_id == viewer``. ``_query_private`` is the only place that queries it and it cannot be
  called without an owner (the filter is built there and checked again on the returned metadata).

Tag filters use ``$in`` on the list metadata (matches when any element matches). The private index stores no tags, so a
tag filter skips it. ``search_text_sha256`` is stored as non-filterable metadata so callers can drop stale vectors.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from mathbank_rest import vector_bulk
from mathbank_rest.stores.errors import ValidationFailed
from mathbank_rest.vector_catalog import ArtifactPrivateMeta, ArtifactPublicMeta, Family
from mathbank_rest.vector_store import (
    MAX_TOP_K,
    S3VectorsStore,
    VectorHit,
    VectorItem,
    VectorStore,
    filter_keys,
    get_vector_store,
    vf,
)

Scope = Literal["public", "private"]


class IndexRow(BaseModel):
    """One bundle's vector and the metadata that goes next to it."""

    model_config = ConfigDict(frozen=True)

    bundle_id: str
    search_text_sha256: str
    vector: list[float]
    subject: str | None = None
    status: str
    concept_tags: list[str] = Field(default_factory=list)
    skill_tags: list[str] = Field(default_factory=list)
    theorem_tags: list[str] = Field(default_factory=list)
    owner_student_id: str | None = None

    @property
    def family(self) -> Family:
        return Family.ARTIFACT_PRIVATE if self.owner_student_id else Family.ARTIFACT_PUBLIC

    def to_item(self) -> VectorItem:
        if self.owner_student_id:
            meta = ArtifactPrivateMeta(owner_student_id=self.owner_student_id, subject=self.subject, status=self.status,
                                       search_text_sha256=self.search_text_sha256).to_metadata()
        else:
            meta = ArtifactPublicMeta(subject=self.subject, status=self.status, concept_tags=self.concept_tags or None,
                                      skill_tags=self.skill_tags or None, theorem_tags=self.theorem_tags or None,
                                      search_text_sha256=self.search_text_sha256).to_metadata()
        return VectorItem(key=self.bundle_id, vector=self.vector, metadata=meta)


class ArtifactHit(BaseModel):
    bundle_id: str
    similarity: float
    distance: float
    scope: Scope
    subject: str | None = None
    status: str | None = None
    concept_tags: list[str] = Field(default_factory=list)
    skill_tags: list[str] = Field(default_factory=list)
    theorem_tags: list[str] = Field(default_factory=list)
    search_text_sha256: str | None = None
    owner_student_id: str | None = None


class StoredVector(BaseModel):
    bundle_id: str
    vector: list[float]
    search_text_sha256: str | None
    status: str | None
    scope: Scope


class BulkIndexResult(BaseModel):
    written: int
    public: int
    private: int
    engine: str


# ------------------------------------------------------------------ write

def index_bundle(bundle_id: str, search_text_sha256: str, vector: Sequence[float], *, subject: str | None, status: str,
                 concept_tags: Sequence[str] = (), skill_tags: Sequence[str] = (), theorem_tags: Sequence[str] = (),
                 owner_student_id: str | None = None, store: VectorStore | None = None) -> Scope:
    """Write (or overwrite) a bundle's vector. A private bundle is removed from the public index so a bundle that changes
    scope can never stay searchable by everyone."""
    row = IndexRow(bundle_id=bundle_id, search_text_sha256=search_text_sha256, vector=list(vector), subject=subject, status=status,
                   concept_tags=list(concept_tags), skill_tags=list(skill_tags), theorem_tags=list(theorem_tags),
                   owner_student_id=owner_student_id or None)
    st = store or get_vector_store()
    st.put(row.family, [row.to_item()])
    other = Family.ARTIFACT_PUBLIC if row.family is Family.ARTIFACT_PRIVATE else Family.ARTIFACT_PRIVATE
    st.delete(other, [bundle_id])
    return "private" if owner_student_id else "public"


def bulk_index(rows: Iterable[IndexRow], *, store: VectorStore | None = None) -> BulkIndexResult:
    """Many bundles at once through ``vector_bulk`` (Bodo when installed and the store is real S3 Vectors, boto3 otherwise)."""
    st = store or get_vector_store()
    engine = "auto" if isinstance(st, S3VectorsStore) else "boto3"      # never hand an in-memory store to Bodo
    by_family: dict[Family, list[VectorItem]] = {Family.ARTIFACT_PUBLIC: [], Family.ARTIFACT_PRIVATE: []}
    for row in rows:
        by_family[row.family].append(row.to_item())
    used = engine
    for family, items in by_family.items():
        if items:
            used = vector_bulk.bulk_put(family, items, engine=engine, store=st).engine
    pub, priv = len(by_family[Family.ARTIFACT_PUBLIC]), len(by_family[Family.ARTIFACT_PRIVATE])
    return BulkIndexResult(written=pub + priv, public=pub, private=priv, engine=used)


def remove_bundle(bundle_id: str, *, store: VectorStore | None = None) -> None:
    st = store or get_vector_store()
    st.delete(Family.ARTIFACT_PUBLIC, [bundle_id])
    st.delete(Family.ARTIFACT_PRIVATE, [bundle_id])


def set_status(bundle_id: str, status: str, *, store: VectorStore | None = None) -> bool:
    """Re-put a bundle's vector with a new ``status`` (publish changes it); False when the bundle has no vector."""
    st = store or get_vector_store()
    for family, model in ((Family.ARTIFACT_PUBLIC, ArtifactPublicMeta), (Family.ARTIFACT_PRIVATE, ArtifactPrivateMeta)):
        found = st.get(family, [bundle_id], with_data=True)
        if found:
            meta = {**found[0].metadata, "status": status}
            model.model_validate(meta)
            st.put(family, [VectorItem(key=bundle_id, vector=found[0].vector, metadata=meta)])
            return True
    return False


def erase_student(student_id: str, keys: Iterable[str], *, store: VectorStore | None = None) -> int:
    """Delete a student's private vectors (``keys`` are their bundle ids, from the system of record). Only vectors that
    really belong to the student are deleted, whatever ``keys`` contains."""
    if not student_id:
        raise ValidationFailed("erase_student needs a student id")
    st = store or get_vector_store()
    wanted = list(dict.fromkeys(keys))
    mine = [i.key for i in st.get(Family.ARTIFACT_PRIVATE, wanted, with_data=False)
            if i.metadata.get("owner_student_id") == student_id]
    if mine:
        st.delete(Family.ARTIFACT_PRIVATE, mine)
    return len(mine)


# ------------------------------------------------------------------ read

def get_vector(bundle_id: str, *, viewer_student_id: str | None = None, store: VectorStore | None = None) -> StoredVector | None:
    """The stored vector of a bundle the viewer may read: the public one, else the viewer's own private one."""
    st = store or get_vector_store()
    for item in st.get(Family.ARTIFACT_PUBLIC, [bundle_id], with_data=True):
        if item.vector:
            return StoredVector(bundle_id=item.key, vector=list(item.vector), scope="public",
                                search_text_sha256=item.metadata.get("search_text_sha256"), status=item.metadata.get("status"))
    if viewer_student_id:
        for item in st.get(Family.ARTIFACT_PRIVATE, [bundle_id], with_data=True):
            if item.vector and item.metadata.get("owner_student_id") == viewer_student_id:
                return StoredVector(bundle_id=item.key, vector=list(item.vector), scope="private",
                                    search_text_sha256=item.metadata.get("search_text_sha256"), status=item.metadata.get("status"))
    return None


def _tags(key: str, values: Sequence[str] | None) -> dict | None:
    return vf.in_(key, values) if values else None


def public_filter(*, subject: str | None, status: str | None, concept_tags: Sequence[str] | None,
                  skill_tags: Sequence[str] | None, theorem_tags: Sequence[str] | None) -> dict | None:
    return vf.and_(vf.eq("subject", subject) if subject else None, vf.eq("status", status) if status else None,
                   _tags("concept_tags", concept_tags), _tags("skill_tags", skill_tags), _tags("theorem_tags", theorem_tags))


def private_filter(owner_student_id: str, *, subject: str | None = None, status: str | None = None) -> dict:
    """The filter of every private query. The owner condition comes first and is not optional."""
    if not owner_student_id or not isinstance(owner_student_id, str):
        raise ValidationFailed("a private artifact query needs the owner student id")
    flt = vf.and_(vf.eq("owner_student_id", owner_student_id), vf.eq("subject", subject) if subject else None,
                  vf.eq("status", status) if status else None)
    assert flt is not None and "owner_student_id" in filter_keys(flt)
    return flt


def _query_private(store: VectorStore, vector: Sequence[float], owner_student_id: str, top_k: int, *, subject: str | None,
                   status: str | None) -> list[VectorHit]:
    flt = private_filter(owner_student_id, subject=subject, status=status)
    hits = store.query(Family.ARTIFACT_PRIVATE, vector, top_k=top_k, filter=flt)
    return [h for h in hits if h.metadata.get("owner_student_id") == owner_student_id]   # belt and braces


def _hit(h: VectorHit, scope: Scope) -> ArtifactHit:
    m = h.metadata
    return ArtifactHit(bundle_id=h.key, similarity=h.similarity, distance=h.distance, scope=scope, subject=m.get("subject"),
                       status=m.get("status"), concept_tags=list(m.get("concept_tags") or []), skill_tags=list(m.get("skill_tags") or []),
                       theorem_tags=list(m.get("theorem_tags") or []), search_text_sha256=m.get("search_text_sha256"),
                       owner_student_id=m.get("owner_student_id") if scope == "private" else None)


def search(query_vector: Sequence[float], *, viewer_student_id: str | None = None, is_staff: bool = False, subject: str | None = None,
           status: str | None = None, concept_tags: Sequence[str] | None = None, skill_tags: Sequence[str] | None = None,
           theorem_tags: Sequence[str] | None = None, top_k: int = 20, store: VectorStore | None = None) -> list[ArtifactHit]:
    """Nearest bundles, best first. Public bundles always; the viewer's own private bundles when a student id is given.

    ``is_staff`` does not widen visibility by itself: staff see another student's private vectors only by naming that
    student (``viewer_student_id``); without it they search the public index only. Callers still re-check each hit."""
    top_k = max(1, min(top_k, MAX_TOP_K))
    st = store or get_vector_store()
    pub = st.query(Family.ARTIFACT_PUBLIC, query_vector, top_k=top_k,
                   filter=public_filter(subject=subject, status=status, concept_tags=concept_tags, skill_tags=skill_tags,
                                        theorem_tags=theorem_tags))
    hits = [_hit(h, "public") for h in pub]
    has_tags = bool(concept_tags or skill_tags or theorem_tags)
    if viewer_student_id and not has_tags:
        hits += [_hit(h, "private") for h in _query_private(st, query_vector, viewer_student_id, top_k, subject=subject, status=status)]
    hits.sort(key=lambda h: (h.distance, h.bundle_id))
    return hits[:top_k]
