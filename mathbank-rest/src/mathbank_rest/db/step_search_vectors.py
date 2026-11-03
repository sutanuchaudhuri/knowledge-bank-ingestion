"""Step / learning-item / taxonomy search over S3 Vectors + mb-content (requirement 71 WP2; requirement 70 C6 section 6e).

Used only when ``vector_store.uses_s3_vectors()``; the pgvector SQL in ``step_search`` is untouched otherwise. No Postgres:
candidates come from the ``step`` / ``learning-item`` / ``taxonomy-search`` indexes, every hit is re-checked against its
``STEP#`` / ``LI#`` / ``TAXNODE#`` item in ``mb-content`` (published, and the hit's vector is one of the item's *current* vectors)
and rows are hydrated from that item with the same keys the SQL ``_STEP_DETAILS`` / ``_ITEM_DETAILS`` / ``_TAXONOMY_DETAILS``
queries return.

Ranking is **vector-only**: lexical (full-text) ranking lived in Postgres and is not applied with S3 Vectors, so ``lexical_rank``
is always ``None`` and ``rrf_score`` is the best similarity (``1 - cosine distance``) of the entity's vectors. ``semantic_rank``
is the 1-based position. A request with ``semantic=False`` therefore returns no rows.

Exact-or-ANN (requirement 70 C6): a *filtered* ANN query can silently miss rows, so when the most selective single-dimension
equality filter selects at most ``EXACT_MAX`` entities (counted from the ``FACET#<UNIT>#<DIM>#<value>`` items) the candidates'
vectors are fetched and ranked by exact cosine distance, applying the remaining filters in Python. Otherwise (no usable facet
dimension, or too many candidates) the filtered ANN query decides.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from mathbank_rest import content_lookup, embeddings
from mathbank_rest.models.ddb.content import ContentFacet, ContentLi, ContentStep, ContentTaxnode
from mathbank_rest.stores import typed
from mathbank_rest.vector_catalog import Family
from mathbank_rest.vector_store import (
    MAX_TOP_K,
    VectorHit,
    cosine_distance,
    get_vector_store,
    matches,
    vf,
)

EXACT_MAX = 300                 # largest candidate set ranked exactly instead of through the filtered ANN query
FACET_PAGE = 200

Item = ContentStep | ContentLi | ContentTaxnode


def _problem(value: Any) -> str:
    """UUID filters compare as canonical lower-case text (the SQL casts the parameter to uuid)."""
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        return str(value)


def _eq(key: str, *, norm: Callable[[Any], Any] = lambda v: v) -> Callable[[Any], dict]:
    return lambda v: vf.eq(key, norm(v))


@dataclass(frozen=True)
class _Unit:
    family: Family
    id_key: str                                         # metadata key holding the entity id
    facet_unit: str
    filters: dict[str, Callable[[Any], dict]]           # allow-listed filter name -> metadata filter
    facet_dims: tuple[tuple[str, str], ...]             # (filter name, FACET dimension), most selective first
    read: Callable[[Iterable[str]], dict[str, Any]]
    search_state: bool = False


_UNITS: dict[str, _Unit] = {
    "step": _Unit(
        family=Family.STEP, id_key="solution_step_id", facet_unit="STEP", read=content_lookup.steps_by_id,
        filters={
            "skill_node_id": _eq("skill_node_id"), "subconcept_node_id": _eq("subconcept_node_id"),
            "concept_node_id": _eq("concept_node_id"), "step_type": _eq("step_type"), "tutor_role": _eq("tutor_role"),
            "is_checkpoint": _eq("is_checkpoint"), "problem_id": _eq("problem_id", norm=_problem),
            "exclude_problem_id": lambda v: vf.ne("problem_id", _problem(v)),
            "max_hint_level": lambda v: vf.lte("hint_level", v),
            "technique_node_id": _eq("technique_node_ids"),
        },
        facet_dims=(("problem_id", "PROBLEM"), ("skill_node_id", "SKILL"), ("technique_node_id", "TECHNIQUE"),
                    ("subconcept_node_id", "SUBCONCEPT"), ("concept_node_id", "CONCEPT"))),
    "learning_item": _Unit(
        family=Family.LEARNING_ITEM, id_key="learning_item_id", facet_unit="LI", read=content_lookup.learning_items_by_id,
        filters={
            "target_skill_node_id": _eq("target_skill_node_id"),
            "target_subconcept_node_id": _eq("target_subconcept_node_id"),
            "learning_item_type": _eq("transformed_form"), "transformation_type": _eq("transformation_type"),
            "difficulty": _eq("difficulty_direction"), "anchor_step_id": _eq("anchor_step_ids"),
            "exclude_problem_id": lambda v: vf.ne("source_problem_id", _problem(v)),
        },
        facet_dims=(("anchor_step_id", "ANCHOR"), ("target_skill_node_id", "TARGET_SKILL"),
                    ("target_subconcept_node_id", "TARGET_SUBCONCEPT"))),
    "taxonomy": _Unit(
        family=Family.TAXONOMY_SEARCH, id_key="taxonomy_node_id", facet_unit="TAXSEARCH", search_state=True,
        read=content_lookup.taxonomy_nodes_by_id,
        filters={"node_types": lambda v: vf.in_("node_type", v), "chapter_number": _eq("chapter_number")},
        facet_dims=(("chapter_number", "CHAPTER"), ("node_types", "NODETYPE"))),
}


def parse_vector(query_vector: str | list[float]) -> list[float]:
    """A query vector given as pgvector text (``'[0.1,0.2,...]'``) or as a list of numbers."""
    try:
        raw = json.loads(query_vector) if isinstance(query_vector, str) else list(query_vector)
        return [float(x) for x in raw]
    except (TypeError, ValueError):
        raise ValueError("query_vector must be a pgvector text '[x,y,...]' or a list of numbers") from None


def build_filter(unit: str, filters: dict) -> dict | None:
    """Metadata filter for the supplied (non-None) filters; unknown names raise like the SQL builder."""
    spec = _UNITS[unit]
    unknown = set(filters) - set(spec.filters)
    if unknown:
        raise ValueError(f"Unsupported {unit} filter(s): {sorted(unknown)}")
    return vf.and_(*(spec.filters[k](v) for k, v in sorted(filters.items()) if v is not None))


# ------------------------------------------------------------------ exact path

def _facet_values(name: str, value: Any) -> list[str]:
    if name == "problem_id":
        return [_problem(value)]
    return [str(v) for v in value] if isinstance(value, (list, tuple, set)) else [str(value)]


def facet_candidates(unit: str, filters: dict, *, exact_max: int | None = None) -> dict[str, str] | None:
    """Vector keys (key -> entity id) of the entities selected by the most selective single-dimension equality filter, or
    ``None`` when no supplied filter has a FACET dimension or every one selects more than ``exact_max`` (or no) entities."""
    spec, limit = _UNITS[unit], EXACT_MAX if exact_max is None else exact_max
    for name, dim in spec.facet_dims:
        value = filters.get(name)
        if value is None or value == []:
            continue
        found: dict[str, ContentFacet] = {}
        for v in _facet_values(name, value):
            token = None
            while len(found) <= limit:
                page = typed.query(ContentFacet, f"FACET#{spec.facet_unit}#{dim}#{v}", limit=FACET_PAGE, next_token=token)
                for f in page.items:
                    found.setdefault(f.entity_id, f)
                token = page.next_token
                if token is None:
                    break
        if 0 < len(found) <= limit:
            return {str(k): f.entity_id for f in found.values() for k in f.vector_keys}
    return None


def _exact_hits(spec: _Unit, vector: list[float], keys: dict[str, str], flt: dict | None) -> list[VectorHit]:
    hits = []
    for item in get_vector_store().get(spec.family, keys):
        if item.vector is None or not matches(item.metadata, flt):
            continue
        meta = dict(item.metadata)
        meta.setdefault(spec.id_key, keys.get(item.key))
        hits.append(VectorHit(key=item.key, distance=cosine_distance(vector, item.vector), metadata=meta))
    hits.sort(key=lambda h: (h.distance, h.key))
    return hits


# ------------------------------------------------------------------ ranking

def _eligible(spec: _Unit, hits: list[VectorHit], seen: dict[str, tuple[float, Item]]) -> None:
    """Add each hit's entity to ``seen`` when it is current and published; the first (nearest) hit per entity wins."""
    ids = [h.metadata.get(spec.id_key) for h in hits]
    items = spec.read(i for i in ids if i and i not in seen)
    for h, ident in zip(hits, ids, strict=True):
        if not ident or ident in seen:
            continue
        item = items.get(ident)
        if item is not None and content_lookup.hit_is_current(item, h.key, search=spec.search_state):
            seen[ident] = (h.distance, item)


def rank(unit: str, vector: list[float], filters: dict, *, limit: int) -> list[tuple[float, Item]]:
    """Eligible, de-duplicated ``(distance, item)`` best-first (at most ``limit``)."""
    spec = _UNITS[unit]
    active = {k: v for k, v in filters.items() if v is not None}
    flt = build_filter(unit, active)
    top_k = min(MAX_TOP_K, max(limit * 4, 40))
    seen: dict[str, tuple[float, Item]] = {}
    exact = facet_candidates(unit, active)
    if exact is not None:
        ranked = _exact_hits(spec, vector, exact, flt)
        for i in range(0, len(ranked), top_k):                  # every candidate is known: keep going until `limit` are eligible
            _eligible(spec, ranked[i:i + top_k], seen)
            if len(seen) >= limit:
                break
    else:
        _eligible(spec, get_vector_store().query(spec.family, vector, top_k=top_k, filter=flt), seen)
    return list(seen.values())[:limit]


# ------------------------------------------------------------------ hydration (the SQL *_DETAILS shapes)

def step_row(s: ContentStep, *, with_text: bool) -> dict:
    row = {"solution_step_id": s.solution_step_id, "problem_id": str(s.problem_id), "solution_id": str(s.solution_id),
           "solution_part_id": s.solution_part_id, "global_step_index": s.global_step_index, "step_type": s.step_type,
           "tutor_role": s.tutor_role, "hint_level": s.hint_level, "is_checkpoint": s.is_checkpoint,
           "skill_node_id": s.skill_node_id, "skill_name": s.skill_name, "subconcept_node_id": s.subconcept_node_id,
           "concept_node_id": s.concept_node_id, "problem_code": s.problem_code}
    if with_text:
        row["step_text"] = s.resolve("step_text")
    return row


def learning_item_row(li: ContentLi) -> dict:
    return {"learning_item_id": li.learning_item_id, "source_problem_id": str(li.source_problem_id),
            "learning_item_type": li.transformed_form, "transformation_type": li.transformation_type,
            "target_skill_node_id": li.target_skill_node_id, "target_subconcept_node_id": li.target_subconcept_node_id,
            "difficulty_direction": li.difficulty_direction, "question_text": li.resolve("question_text"),
            "choices": li.resolve("choices"), "diagram_strategy": li.diagram_strategy}


def taxonomy_row(n: ContentTaxnode) -> dict:
    return {"taxonomy_node_id": n.taxonomy_node_id, "node_type": n.node_type, "name": n.name,
            "parent_node_id": n.parent.id_ if n.parent else None, "parent_name": n.parent.name if n.parent else None,
            "chapter_number": n.chapter_number, "section_number": n.section_number, "slug": n.slug,
            "slug_kind": n.slug_kind, "problem_count": n.problem_count, "example_problem_codes": list(n.example_problem_codes)}


def _row(unit: str, item: Item, with_step_text: bool) -> dict:
    if unit == "step":
        return step_row(item, with_text=with_step_text)             # type: ignore[arg-type]
    if unit == "learning_item":
        return learning_item_row(item)                              # type: ignore[arg-type]
    return taxonomy_row(item)                                       # type: ignore[arg-type]


def search(unit: str, query_text: str, filters: dict, *, semantic: bool, lexical: bool, limit: int,
           query_vector: str | list[float] | None = None, include_step_text: bool = False) -> list[dict]:
    """Drop-in for ``step_search._search`` rows when S3 Vectors is on (semantic only; ``lexical`` is not applied)."""
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    if not (semantic or lexical):
        raise ValueError("At least one of semantic or lexical ranking is required")
    build_filter(unit, filters)                                     # unknown filter names fail before any I/O
    if not semantic:
        return []
    vector = parse_vector(query_vector) if query_vector is not None else embeddings.embed_text(query_text)
    ranked = rank(unit, vector, filters, limit=limit)
    out = []
    for i, (distance, item) in enumerate(ranked, 1):
        row = _row(unit, item, include_step_text)
        row.update(rrf_score=1.0 - distance, semantic_rank=i, lexical_rank=None)
        out.append(row)
    return out


def similar_steps(solution_step_id: str, *, limit: int = 5, same_skill: bool = True) -> dict:
    """``step_search.similar_steps_for_step`` over S3 Vectors: the step's own stored vector is the query (no embedding call)."""
    anchor = content_lookup.steps_by_id([solution_step_id]).get(solution_step_id)
    if anchor is None or not content_lookup.is_published(anchor):
        raise LookupError(solution_step_id)
    keys = anchor.vector_state.keys
    stored = get_vector_store().get(Family.STEP, [str(keys[0])]) if keys else []
    vector = stored[0].vector if stored else None
    results = search(
        "step", anchor.skill_name or anchor.step_type or "step",
        {"skill_node_id": anchor.skill_node_id if same_skill and anchor.skill_node_id else None,
         "exclude_problem_id": str(anchor.problem_id)},
        semantic=vector is not None, lexical=True, limit=limit, query_vector=vector)
    return {"anchor": {"solution_step_id": anchor.solution_step_id, "skill_node_id": anchor.skill_node_id,
                       "skill_name": anchor.skill_name, "step_type": anchor.step_type},
            "embedding_available": vector is not None, "results": results}
