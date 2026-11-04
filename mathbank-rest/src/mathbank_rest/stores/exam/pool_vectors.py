"""Vector adapter of the question pool (requirement 70 C2 sections 2 and 3, requirement 71 section 2.5).

Two vectors per pool question in the ``quiz-question-te3small-1536-v1`` index: ``<pool_id>#prompt`` (the normalised prompt, used to
find near-duplicates when writing back) and ``<pool_id>#topic`` (the topic key, used by the match). Metadata is enum-like only
(``QuizQuestionMeta``); ``difficulty_band`` is ``NONE`` for a null band. The adapter holds no state of its own: the store is
``vector_store.get_vector_store()`` resolved at call time (``MemoryVectorStore`` is the fake in tests), embeddings go through
``embeddings.embed_text`` (single, cached, rate limited) or one batched provider call (``embed_many``).
"""
from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Iterable, Sequence

from mathbank_rest import embeddings, rate_limit
from mathbank_rest import vector_store as vs
from mathbank_rest.config import settings
from mathbank_rest.vector_catalog import EMBEDDING_MODEL, Family, QuizQuestionMeta
from mathbank_rest.vector_store import VectorHit, VectorItem, VectorStore, vf

LOG = logging.getLogger("mathbank_rest.stores.exam.pool_vectors")

KIND_PROMPT = "prompt"
KIND_TOPIC = "topic"
NO_BAND = "NONE"
MAX_CONCEPTS_IN_METADATA = 20           # keeps the 2 KB filterable-metadata budget


def vector_key(pool_id: str, kind: str) -> str:
    return f"{pool_id}#{kind}"


def pool_id_of(key: str) -> str:
    return key.split("#", 1)[0]


def topic_hash(topic_key: str) -> str:
    return hashlib.sha256(topic_key.encode("utf-8")).hexdigest()


class PoolVectors:
    """``query_topic``, ``query_near_duplicate``, ``put`` and ``update_status`` on ``Family.QUIZ_QUESTION``."""

    def __init__(self, store: VectorStore | None = None, *, embed: Callable[[str], list[float]] | None = None,
                 embed_batch: Callable[[list[str]], list[list[float]]] | None = None) -> None:
        self._store, self._embed, self._embed_batch = store, embed, embed_batch
        if settings.quiz_pool_vector_index != Family.QUIZ_QUESTION.index_name:
            LOG.warning("QUIZ_POOL_VECTOR_INDEX=%s differs from the catalogue index %s; the catalogue wins",
                        settings.quiz_pool_vector_index, Family.QUIZ_QUESTION.index_name)

    @property
    def store(self) -> VectorStore:
        return self._store or vs.get_vector_store()

    # ------------------------------------------------------------------ embeddings

    def embed(self, text: str) -> list[float]:
        return (self._embed or embeddings.embed_text)(text)

    def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        """One provider call for all distinct texts (the finalize write-back embeds every prompt and the topic together)."""
        distinct = list(dict.fromkeys(t.strip() for t in texts))
        if not distinct:
            return []
        if self._embed_batch is not None:
            got = self._embed_batch(distinct)
        else:
            from mathbank_rest import vector_sync  # heavy import, only on the write-back path

            rate_limit.assert_embeddings_allowed()
            got = vector_sync.BATCH_EMBEDDER(distinct)
        if len(got) != len(distinct):
            raise ValueError("embedder returned a different number of vectors")
        by_text = dict(zip(distinct, got, strict=True))
        return [by_text[t.strip()] for t in texts]

    # ------------------------------------------------------------------ queries

    def query_topic(self, vector: Sequence[float], *, style: str, question_types: Sequence[str], difficulty_band: str | None,
                    top_k: int) -> list[VectorHit]:
        """A12: topic vectors of ACTIVE questions with this style, one of the types and this band."""
        flt = vf.and_(vf.eq("kind", KIND_TOPIC), vf.eq("style", style), vf.in_("question_type", list(question_types)),
                      vf.eq("difficulty_band", difficulty_band or NO_BAND), vf.eq("status", "ACTIVE"))
        return self.store.query(Family.QUIZ_QUESTION, vector, top_k=max(1, min(100, top_k)), filter=flt)

    def query_near_duplicate(self, vector: Sequence[float], *, style: str, question_type: str, top_k: int = 3) -> list[VectorHit]:
        """A17: prompt vectors of any status with this style and type (a retired near-duplicate still blocks a new entry)."""
        flt = vf.and_(vf.eq("kind", KIND_PROMPT), vf.eq("style", style), vf.eq("question_type", question_type))
        return self.store.query(Family.QUIZ_QUESTION, vector, top_k=max(1, min(100, top_k)), filter=flt)

    def search(self, vector: Sequence[float], *, status: str | None, style: str | None, question_type: str | None,
               difficulty_band: str | None, top_k: int) -> list[VectorHit]:
        """E04 ``q``: nearest vectors of both kinds under the admin list's filters."""
        flt = vf.and_(vf.eq("status", status) if status else None, vf.eq("style", style) if style else None,
                      vf.eq("question_type", question_type) if question_type else None,
                      vf.eq("difficulty_band", difficulty_band) if difficulty_band else None)
        return self.store.query(Family.QUIZ_QUESTION, vector, top_k=max(1, min(100, top_k)), filter=flt)

    # ------------------------------------------------------------------ writes

    @staticmethod
    def metadata(kind: str, *, style: str, question_type: str, difficulty_band: str | None, status: str, content_hash: str,
                 concept_slugs: Iterable[str] | None, topic_key: str) -> dict:
        slugs = sorted({s for s in (concept_slugs or []) if s})[:MAX_CONCEPTS_IN_METADATA]
        return QuizQuestionMeta(kind=kind, style=style, question_type=question_type, difficulty_band=difficulty_band or NO_BAND,
                                status=status, content_hash=content_hash, model=EMBEDDING_MODEL, concept_slugs=slugs or None,
                                topic_key_sha256=topic_hash(topic_key)).to_metadata()

    def put(self, pool_id: str, *, prompt_vector: Sequence[float] | None, topic_vector: Sequence[float] | None, style: str,
            question_type: str, difficulty_band: str | None, status: str, content_hash: str, concept_slugs: Iterable[str] | None,
            topic_key: str) -> int:
        """PutVectors for the prompt and (when the topic is not empty) the topic vector. Idempotent: the keys are fixed."""
        common = {"style": style, "question_type": question_type, "difficulty_band": difficulty_band, "status": status,
                  "content_hash": content_hash, "concept_slugs": concept_slugs, "topic_key": topic_key}
        items = []
        if prompt_vector is not None:
            items.append(VectorItem(key=vector_key(pool_id, KIND_PROMPT), vector=list(prompt_vector),
                                    metadata=self.metadata(KIND_PROMPT, **common)))
        if topic_vector is not None and topic_key:
            items.append(VectorItem(key=vector_key(pool_id, KIND_TOPIC), vector=list(topic_vector),
                                    metadata=self.metadata(KIND_TOPIC, **common)))
        return self.store.put(Family.QUIZ_QUESTION, items) if items else 0

    def update_status(self, pool_id: str, status: str) -> int:
        """Rewrite the ``status`` metadata of the question's vectors (S3 Vectors has no partial update: data is read and put back).
        Returns how many vectors were rewritten; questions that were never indexed have none (the indexer writes them with the
        current status)."""
        keys = [vector_key(pool_id, KIND_PROMPT), vector_key(pool_id, KIND_TOPIC)]
        found = [v for v in self.store.get(Family.QUIZ_QUESTION, keys, with_data=True) if v.vector]
        if not found:
            return 0
        return self.store.put(Family.QUIZ_QUESTION, [VectorItem(key=v.key, vector=v.vector, metadata={**v.metadata, "status": status})
                                                     for v in found])

    def delete(self, pool_id: str) -> int:
        return self.store.delete(Family.QUIZ_QUESTION, [vector_key(pool_id, KIND_PROMPT), vector_key(pool_id, KIND_TOPIC)])
