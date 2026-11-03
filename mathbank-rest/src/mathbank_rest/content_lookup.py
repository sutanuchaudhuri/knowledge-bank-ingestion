"""Typed reads from ``mb-content`` for vector search: eligibility re-check and result hydration (requirement 70 C6 §6e).

Every vector hit is re-checked against the content item it points to before it is returned, so a stale or withdrawn embedding
can never surface unpublished content:

* the item must exist and be published (``PROBLEM.visibility == ACTIVE``; ``STEP``/``LI``/``TAXNODE`` ``eligible``);
* the hit's vector key must be one of the item's *current* ``vector_state.keys`` (a re-embedded entity drops its old keys).

This is the read half of the content store that WP4 completes (answer keys, snapshots, listings). It is deliberately small and
typed: callers get pydantic models, never raw dicts.
"""
from __future__ import annotations

from collections.abc import Iterable

from mathbank_rest.models.ddb.content import ContentLi, ContentProblem, ContentStep, ContentTaxnode
from mathbank_rest.stores import typed
from mathbank_rest.stores.errors import ItemSchemaError


def _pk(prefix: str, ident: str) -> str:
    return f"{prefix}#{ident}"


def problems_by_code(codes: Iterable[str]) -> dict[str, ContentProblem]:
    items = typed.batch_get(ContentProblem, [(_pk("PROBLEM", c), "META") for c in dict.fromkeys(codes)])
    return {i.canonical_code: i for i in items}


def steps_by_id(ids: Iterable[str]) -> dict[str, ContentStep]:
    items = typed.batch_get(ContentStep, [(_pk("STEP", i), "META") for i in dict.fromkeys(ids)])
    return {i.solution_step_id: i for i in items}


def learning_items_by_id(ids: Iterable[str]) -> dict[str, ContentLi]:
    items = typed.batch_get(ContentLi, [(_pk("LI", i), "META") for i in dict.fromkeys(ids)])
    return {i.learning_item_id: i for i in items}


def taxonomy_nodes_by_id(ids: Iterable[str]) -> dict[str, ContentTaxnode]:
    items = typed.batch_get(ContentTaxnode, [(_pk("TAXNODE", i), "META") for i in dict.fromkeys(ids)])
    return {i.taxonomy_node_id: i for i in items}


def is_published(item: ContentProblem | ContentStep | ContentLi | ContentTaxnode) -> bool:
    if isinstance(item, ContentProblem):
        return item.visibility == "ACTIVE"
    return bool(item.eligible)


def current_vector_keys(item: ContentProblem | ContentStep | ContentLi | ContentTaxnode, *, search: bool = False) -> set[str]:
    """Vector keys the content item says are its live embeddings (``search=True``: a taxonomy node's *search* chunks)."""
    state = item.search_vector_state if (search and isinstance(item, ContentTaxnode)) else item.vector_state
    if state is None:
        return set()
    return {str(k) for k in state.keys}


def hit_is_current(item: ContentProblem | ContentStep | ContentLi | ContentTaxnode | None, vector_key: str, *, search: bool = False) -> bool:
    """True when the entity exists, is published and ``vector_key`` is one of its current vectors."""
    if item is None:
        return False
    try:
        return is_published(item) and vector_key in current_vector_keys(item, search=search)
    except ItemSchemaError:
        return False
