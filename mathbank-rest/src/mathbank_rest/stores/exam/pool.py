"""Exam store, pool area (requirement 71 WP6; design C2 access patterns A12-A17 and A21, write paths "Pool write-back" and "Pool retire").

``PoolPostgres`` calls today's functions at call time (``quiz_runtime``), so behaviour and monkeypatching tests are unchanged.
``PoolDynamoDB`` is the ``mb-exam`` implementation: one transaction per operation through ``ExamUnitOfWork``, typed models
(``models/manual/exam_pool.py``), S3 Vectors through ``stores/exam/pool_vectors.py``, no scans and no PostgreSQL. A method name starts
with a ``stores.READ_PREFIXES`` entry exactly when it is a read, so a ``frozen`` store serves reads and rejects writes.
(``match_pool_questions`` keeps today's name and therefore counts as a write for the freeze: the agent treats the pool as best-effort.)

Seams used by the papers area (finalize), on the composed store:

* ``link_or_insert_pool_question(student_id, quiz_id, question_doc) -> pool_id | None`` (plural: ``link_or_insert_pool_questions``,
  one embedding call for the whole finalize). Runs its own transaction BEFORE the paper transaction; a vector failure never fails it.
* ``build_pool_serve_ops(student_id, pool_ids, *, quiz_id) -> list[ddb.TxOp]``: single-item ops for the paper's finalize transaction.
* ``match_pool_questions(...)``: today's signature and response shape.

Admin-facing (the admin wave exposes them): ``get_pool_question``, ``list_pool_questions``, ``set_pool_status`` (with an ``audit_ops``
hook), ``list_pool_served``. Stream consumer (``exam-pool-vector-indexer``): ``index_pending_pool_question``,
``update_pool_vector_status``. Private helpers are prefixed ``_pool_`` so no area defines the same name.
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import threading
import uuid
from collections import OrderedDict
from collections.abc import Callable, Sequence
from typing import Any, NamedTuple

from mathbank_rest.config import settings
from mathbank_rest.models.base import S3Ref
from mathbank_rest.models.manual.exam_pool import (
    BANDS,
    CONTENT_HASH_FIELD,
    INLINE_QUESTION_MAX_BYTES,
    NO_BAND,
    QUESTION_TYPES,
    STATUSES,
    STYLES,
    PoolConcept,
    PoolQuestion,
    PoolQuestionRow,
    PoolServed,
    PoolUniqueHash,
    concept_pk,
    concept_prefix,
    concept_sk,
    content_hash_of,
    is_uuid,
    normalize_band,
    normalize_prompt,
    pool_gsi1sk,
    pool_pk,
    pool_status_pk,
    poolkey,
    served_sk,
)
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.errors import (
    ConditionFailed,
    NotFound,
    RevisionConflict,
    StoreError,
    StoreNotImplemented,
    UniqueViolation,
    ValidationFailed,
)
from mathbank_rest.stores.exam.pool_vectors import PoolVectors, pool_id_of
from mathbank_rest.stores.exam.uow import ExamUnitOfWork, with_retries
from mathbank_rest.vector_store import cosine_distance

LOG = logging.getLogger("mathbank_rest.stores.exam.pool")

CTX = "exam"
MAX_LIMIT = 50                                   # match: same clamp as today's SQL
MAX_CANDIDATES = 500                             # candidates hydrated per match (topic hits first, then concept hits)
CONCEPT_PAGE = 100
CONCEPT_MAX_PAGES = 5
LIST_MAX_LIMIT = 100
LIST_MAX_PAGES = 20
SEEN_BATCHES = 64                                # finalize batches remembered for the in-memory pairwise duplicate check
# The finalize payload as stored in quiz.question_pool: everything except these (today's _POOL_QUESTION_EXCLUDED_FIELDS) ...
POOL_QUESTION_EXCLUDED_FIELDS = ("revision_log", "pool_question_id", "add_to_pool")
# ... and the context the papers area adds to the question dict (it comes from the paper and the request, not from the question).
DOC_CONTEXT_KEYS = ("style", "paper_difficulty_band", "generated_by", "pool_topic", "pool_concept_slugs")
# jsonb keeps nulls and DynamoDB does not: these keys of the finalize payload are nullable, so a missing one reads back as null.
NULLABLE_QUESTION_KEYS = ("prompt_latex", "options", "difficulty_band", "diagram")


def normalize_topic_key(topic: str | None) -> str:
    """Same as ``quiz_runtime.normalize_topic_key``: lower-cased, whitespace-collapsed, at most 200 characters."""
    return " ".join((topic or "").lower().split())[:200]


def _iso(value: Any) -> Any:
    return None if value is None else ddb.encode(value)


def _str(value: Any) -> str | None:
    return None if value is None else str(value)


# ------------------------------------------------------------------------------------------------ Postgres

class PoolPostgres:
    """Postgres backend: today's functions, called at call time. The admin pool operations have no PostgreSQL implementation
    (QUZ-E04-E06 are DynamoDB-first: there is no status column in ``quiz.question_pool``)."""

    def match_pool_questions(self, student_id, *, style: str, question_types: list[str], difficulty_band: str | None,
                             topic: str | None, concept_slugs: list[str] | None = None, limit: int = 20,
                             min_topic_similarity: float = 0.5) -> list[dict]:
        from mathbank_rest import quiz_runtime

        return quiz_runtime.match_pool_questions(
            student_id, style=style, question_types=question_types, difficulty_band=difficulty_band, topic=topic,
            concept_slugs=concept_slugs, limit=limit, min_topic_similarity=min_topic_similarity)

    def link_or_insert_pool_question(self, student_id, quiz_id, question_doc: dict) -> str | None:
        """One question's pool link in its own transaction (today's ``_link_pool_question``: bumps ``times_served`` when served
        from the pool, ``INSERT ... ON CONFLICT (content_hash)`` for a write-back). ``question_doc`` carries the context keys
        ``DOC_CONTEXT_KEYS``."""
        from mathbank_rest import quiz_runtime

        link, engine = getattr(quiz_runtime, "_link_pool_question", None), getattr(quiz_runtime, "engine", None)
        if link is None or engine is None:
            raise StoreNotImplemented("the PostgreSQL pool link is part of finalize_paper", context=CTX, backend="postgres")
        q = {k: v for k, v in question_doc.items() if k not in DOC_CONTEXT_KEYS}
        paper = {"style": question_doc["style"], "difficulty_band": question_doc.get("paper_difficulty_band"),
                 "generated_by": question_doc.get("generated_by")}
        with engine.begin() as conn:
            pool_id = link(conn, q, paper=paper, pool_topic_key=normalize_topic_key(question_doc.get("pool_topic")),
                           pool_concept_slugs=list(question_doc.get("pool_concept_slugs") or []), quiz_id=quiz_id,
                           generated_by=question_doc.get("generated_by"))
        return str(pool_id) if pool_id else None

    def link_or_insert_pool_questions(self, student_id, quiz_id, question_docs: Sequence[dict]) -> list[str | None]:
        return [self.link_or_insert_pool_question(student_id, quiz_id, d) for d in question_docs]

    def build_pool_serve_ops(self, student_id, pool_ids: Sequence[str], *, quiz_id) -> list[ddb.TxOp]:
        """No ops: PostgreSQL bumps ``times_served`` inside ``link_or_insert_pool_question`` and derives the learner's history from
        ``quiz.question.pool_question_id``."""
        return []

    def _pool_unsupported(self, what: str) -> StoreNotImplemented:
        return StoreNotImplemented(f"{what} needs the exam store on dynamodb (no PostgreSQL implementation)", context=CTX, backend="postgres")

    def get_pool_question(self, pool_id, *, include_question: bool = True) -> dict | None:
        raise self._pool_unsupported("get_pool_question")

    def list_pool_questions(self, *, status: str | None = "ACTIVE", style: str | None = None, question_type: str | None = None,
                            difficulty_band: str | None = None, q: str | None = None, limit: int = 50,
                            next_token: str | None = None) -> dict:
        raise self._pool_unsupported("list_pool_questions")

    def set_pool_status(self, pool_id, new_status: str, actor: str, reason: str | None = None, *,
                        expected_version: int | None = None, audit_ops=None) -> dict:
        raise self._pool_unsupported("set_pool_status")

    def list_pool_served(self, student_id, *, limit: int = 50, next_token: str | None = None) -> dict:
        raise self._pool_unsupported("list_pool_served")

    def index_pending_pool_question(self, pool_id) -> str:
        raise self._pool_unsupported("index_pending_pool_question")

    def update_pool_vector_status(self, pool_id, status: str) -> int:
        raise self._pool_unsupported("update_pool_vector_status")


# ------------------------------------------------------------------------------------------------ write-back planning

class _Plan(NamedTuple):
    """Everything a write-back needs, validated once (the model enforces the CHECK-style enums)."""

    doc: dict
    style: str
    question_type: str
    band: str | None
    topic_key: str
    concepts: list[str]
    techniques: list[str]
    payload: dict
    content_hash: str
    prompt: str
    generated_by: str | None


class _Seen(NamedTuple):
    vector: list[float]
    pool_id: str
    style: str
    question_type: str


_SEEN: OrderedDict[str, list[_Seen]] = OrderedDict()
_SEEN_LOCK = threading.Lock()


def _seen_for(quiz_id: Any) -> list[_Seen]:
    """Entries written during one finalize (this process): the vector index is eventually consistent, so near-duplicates inside a
    batch are compared here, pairwise, instead of through the index."""
    key = str(quiz_id)
    with _SEEN_LOCK:
        if key not in _SEEN:
            _SEEN[key] = []
            while len(_SEEN) > SEEN_BATCHES:
                _SEEN.popitem(last=False)
        _SEEN.move_to_end(key)
        return _SEEN[key]


def _offload_question(pool_id: str, payload: dict) -> dict:
    """The ``question`` attributes of a new item: inline, or ``question_ref`` to ``exam/pool/<pool_id>.json`` over 100 KB."""
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()
    if len(body) <= INLINE_QUESTION_MAX_BYTES:
        return {"question": payload}
    digest, key, bucket = hashlib.sha256(body).hexdigest(), f"exam/pool/{pool_id}.json", ddb.data_bucket()
    ddb.client("s3").put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json", ChecksumAlgorithm="SHA256",
                                Metadata={"sha256": digest})
    return {"question_ref": S3Ref(bucket=bucket, key=key, sha256=digest, bytes=len(body))}


def _question_payload(item: PoolQuestion) -> dict:
    payload = dict(item.resolve("question") or {})
    for key in NULLABLE_QUESTION_KEYS:
        payload.setdefault(key, None)
    return payload


class _AlreadyInStatus(Exception):
    """Raised inside the retry loop of ``set_pool_status``: not a race, so it must not be retried."""


# ------------------------------------------------------------------------------------------------ DynamoDB

class PoolDynamoDB:
    """DynamoDB backend over ``mb-exam`` and S3 Vectors."""

    _pool_rng: random.Random = random.Random()           # tests inject a seeded RNG: the final tie-break of the match order
    _pool_vectors_adapter: PoolVectors | None = None

    def _pool_vec(self) -> PoolVectors:
        if self._pool_vectors_adapter is None:
            self._pool_vectors_adapter = PoolVectors()
        return self._pool_vectors_adapter

    # ============================================================================================ match (A12-A15)

    def match_pool_questions(self, student_id, *, style: str, question_types: list[str], difficulty_band: str | None,
                             topic: str | None, concept_slugs: list[str] | None = None, limit: int = 20,
                             min_topic_similarity: float | None = None) -> list[dict]:
        """Pooled questions for an "almost the same" request: same style, one of the types, the same band, and either a similar
        topic (vector branch, cosine >= ``QUIZ_POOL_TOPIC_MIN_SIM``) or an overlapping concept (index branch), never one this learner
        was already served, ACTIVE only. Best topic match first, then the least served, then random. The topic branch is skipped
        (silently) when the vector store or the embedding is unavailable; the concept branch still answers."""
        topic_key = normalize_topic_key(topic)
        concepts = list(dict.fromkeys(s for s in (concept_slugs or []) if s))
        if not topic_key and not concepts:
            return []
        limit = max(1, min(int(limit), MAX_LIMIT))
        types = [t for t in dict.fromkeys(question_types or QUESTION_TYPES) if t in QUESTION_TYPES]
        band = normalize_band(difficulty_band)
        if style not in STYLES or not types or (band is not None and band not in BANDS):
            return []
        min_sim = settings.quiz_pool_topic_min_sim if min_topic_similarity is None else float(min_topic_similarity)

        sims, topic_ids = self._pool_topic_branch(topic_key, style, types, band, limit, min_sim)
        candidates = list(topic_ids)
        for slug in concepts:
            for qtype in types:
                candidates += self._pool_concept_ids(slug, style, qtype, band)
        candidates = [c for c in dict.fromkeys(candidates) if is_uuid(c)][:MAX_CANDIDATES]
        if not candidates:
            return []

        if student_id is not None:
            served = {str(s.pool_question_id) for s in typed.batch_get(
                PoolServed, [(ddb.student_pk(student_id), served_sk(c)) for c in candidates], consistent=True)}
            candidates = [c for c in candidates if c not in served]
        items = typed.batch_get(PoolQuestion, [(pool_pk(c), "POOL") for c in candidates], consistent=True)
        live = [i for i in items if i.status == "ACTIVE" and i.style == style and i.question_type in types
                and i.difficulty_band == band]
        rng = self._pool_rng
        ranked = sorted(live, key=lambda i: (-sims.get(str(i.pool_question_id), 0.0), i.times_served, rng.random()))[:limit]
        return [{"pool_question_id": str(i.pool_question_id), "question_type": i.question_type, "question": _question_payload(i),
                 "topic_similarity": float(sims.get(str(i.pool_question_id), 0.0))} for i in ranked]

    def _pool_topic_branch(self, topic_key: str, style: str, types: list[str], band: str | None, limit: int,
                           min_sim: float) -> tuple[dict[str, float], list[str]]:
        """A12. Returns (similarity per pool id seen, ids at or above the floor in similarity order)."""
        if not topic_key:
            return {}, []
        try:
            vec = self._pool_vec()
            hits = vec.query_topic(vec.embed(topic_key), style=style, question_types=types, difficulty_band=band,
                                   top_k=min(100, 4 * limit))
        except Exception:
            LOG.warning("question-pool topic branch unavailable; matching on concepts only", exc_info=True)
            return {}, []
        sims: dict[str, float] = {}
        for hit in hits:
            pid = pool_id_of(hit.key)
            sim = min(1.0, max(0.0, hit.similarity))                  # float noise must not report 1.0000000000000002
            sims[pid] = max(sims.get(pid, sim), sim)
        return sims, [pid for pid, s in sorted(sims.items(), key=lambda kv: -kv[1]) if s >= min_sim]

    def _pool_concept_ids(self, slug: str, style: str, question_type: str, band: str | None) -> list[str]:
        """A13: ACTIVE pool ids under one concept for this style, type and band (strong read, a few bounded pages)."""
        out, token = [], None
        for _ in range(CONCEPT_MAX_PAGES):
            page = typed.query(PoolConcept, concept_pk(slug), sk_begins=concept_prefix(style, question_type, band),
                               limit=CONCEPT_PAGE, next_token=token)
            out += [str(c.pool_question_id) for c in page.items if c.status == "ACTIVE"]
            token = page.next_token
            if not token:
                break
        return out

    # ============================================================================================ write-back (A16, A17)

    def link_or_insert_pool_question(self, student_id, quiz_id, question_doc: dict) -> str | None:
        """The pool id one finalized question should reference, or None. ``question_doc`` is the finalize question plus the context
        keys ``style``, ``paper_difficulty_band``, ``generated_by``, ``pool_topic`` and ``pool_concept_slugs``.

        * a question served from the pool (``pool_question_id``): that id when the entry exists (the usage bump is
          ``build_pool_serve_ops``, inside the paper transaction);
        * not ``add_to_pool``: None;
        * otherwise a write-back: the id behind an existing ``UNIQUE#content_hash`` sentinel; else the id of a near-duplicate
          (prompt vectors, cosine >= ``QUIZ_POOL_DUP_MIN_SIM``, or an earlier entry of the same finalize); else a new entry
          (POOL_QUESTION ``vector_state=PENDING`` + sentinel + POOL_CONCEPT per slug in one transaction) whose vectors are put after
          the commit. Vector and embedding failures leave the entry PENDING for the indexer and never raise."""
        return self.link_or_insert_pool_questions(student_id, quiz_id, [question_doc])[0]

    def link_or_insert_pool_questions(self, student_id, quiz_id, question_docs: Sequence[dict]) -> list[str | None]:
        """``link_or_insert_pool_question`` for a whole finalize: the prompts and the topic are embedded in ONE provider call and
        compared pairwise, in memory, with each other."""
        docs = list(question_docs)
        results: list[str | None] = [None] * len(docs)
        plans: dict[int, _Plan] = {}
        for i, doc in enumerate(docs):
            if doc.get("pool_question_id"):
                results[i] = self._pool_existing_id(doc["pool_question_id"])
            elif doc.get("add_to_pool"):
                plans[i] = self._pool_plan(doc)
        for i in list(plans):
            winner = self._pool_find_sentinel(plans[i].content_hash)          # A16: an exact duplicate needs no embedding
            if winner:
                results[i] = winner
                del plans[i]
        if not plans:
            return results
        vectors, topics = self._pool_embed_plans(list(plans.values()))
        seen = _seen_for(quiz_id)
        for n, (i, plan) in enumerate(plans.items()):
            results[i] = self._pool_link_one(student_id, quiz_id, plan, vectors[n] if vectors else None, topics, seen)
        return results

    def _pool_existing_id(self, pool_id: Any) -> str | None:
        item = typed.get(PoolQuestion, pool_pk(pool_id), "POOL", consistent=False) if is_uuid(str(pool_id)) else None
        return None if item is None else str(item.pool_question_id)

    def _pool_plan(self, doc: dict) -> _Plan:
        style = doc.get("style")
        if style not in STYLES:
            raise ValidationFailed(f"pool style must be one of {STYLES}", style=style)
        qtype = doc.get("question_type")
        if qtype not in QUESTION_TYPES:
            raise ValidationFailed(f"pool question_type must be one of {QUESTION_TYPES}", question_type=qtype)
        band = normalize_band(doc.get("paper_difficulty_band"))
        if band is not None and band not in BANDS:
            raise ValidationFailed(f"pool difficulty_band must be one of {BANDS}", difficulty_band=band)
        prompt = doc.get("prompt_text")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValidationFailed("pool write-back needs prompt_text")
        skip = set(POOL_QUESTION_EXCLUDED_FIELDS) | set(DOC_CONTEXT_KEYS)
        concepts = sorted({*(doc.get("concept_slugs") or []), *(doc.get("pool_concept_slugs") or [])} - {""})
        return _Plan(doc=doc, style=style, question_type=qtype, band=band, topic_key=normalize_topic_key(doc.get("pool_topic")),
                     concepts=concepts, techniques=list(doc.get("technique_slugs") or []),
                     payload={k: v for k, v in doc.items() if k not in skip}, content_hash=content_hash_of(prompt),
                     prompt=normalize_prompt(prompt), generated_by=doc.get("generated_by"))

    def _pool_embed_plans(self, plans: list[_Plan]) -> tuple[list[list[float]] | None, dict[str, list[float]]]:
        """One provider call for every prompt and every distinct topic of the batch."""
        topics = sorted({p.topic_key for p in plans if p.topic_key})
        try:
            got = self._pool_vec().embed_many([p.prompt for p in plans] + topics)
        except Exception:
            LOG.warning("question-pool embedding unavailable; writing back without the near-duplicate check", exc_info=True)
            return None, {}
        return got[:len(plans)], dict(zip(topics, got[len(plans):], strict=True))

    def _pool_find_sentinel(self, content_hash: str) -> str | None:
        pk, sk = ddb.unique_key(CONTENT_HASH_FIELD, content_hash)
        found = typed.get(PoolUniqueHash, pk, sk, consistent=True)
        return None if found is None else str(found.pool_question_id)

    def _pool_near_duplicate(self, plan: _Plan, vector: list[float], seen: list[_Seen]) -> str | None:
        floor = settings.quiz_pool_dup_min_sim
        for s in seen:
            if s.style == plan.style and s.question_type == plan.question_type and 1.0 - cosine_distance(vector, s.vector) >= floor:
                return s.pool_id
        try:
            hits = self._pool_vec().query_near_duplicate(vector, style=plan.style, question_type=plan.question_type, top_k=3)
        except Exception:
            LOG.warning("question-pool near-duplicate query unavailable; inserting without it", exc_info=True)
            return None
        return next((pool_id_of(h.key) for h in hits if h.similarity >= floor), None)

    def _pool_link_one(self, student_id, quiz_id, plan: _Plan, vector: list[float] | None, topics: dict[str, list[float]],
                       seen: list[_Seen]) -> str | None:
        if vector is not None:
            dup = self._pool_near_duplicate(plan, vector, seen)
            if dup:
                return dup
        pool_id = str(uuid.uuid4())
        item = PoolQuestion.build(
            pool_id=pool_id, created_at=ddb.now_iso(), content_hash=plan.content_hash, style=plan.style,
            question_type=plan.question_type, difficulty_band=plan.band, topic_key=plan.topic_key,
            concept_slugs=plan.concepts or None, technique_slugs=plan.techniques or None,
            source_quiz_id=str(quiz_id), generated_by=plan.generated_by, **_offload_question(pool_id, plan.payload))
        uow = ExamUnitOfWork(student_id)
        uow.sentinel(CONTENT_HASH_FIELD, plan.content_hash, {"pool_question_id": pool_id})
        uow.put_new(item, conflict=ConditionFailed("pool question already exists", op="POOL_QUESTION"))
        for slug in plan.concepts:
            uow.put_new(PoolConcept(PK=concept_pk(slug), SK=concept_sk(plan.style, plan.question_type, plan.band, pool_id),
                                    pool_question_id=pool_id, concept_slug=slug, status="ACTIVE"))
        try:
            uow.commit()
        except UniqueViolation:
            # a concurrent finalize won the sentinel between our read and our write: link its entry
            winner = self._pool_find_sentinel(plan.content_hash)
            if winner:
                return winner
            raise
        if vector is not None:
            seen.append(_Seen(vector, pool_id, plan.style, plan.question_type))
            self._pool_put_vectors(item, vector, topics.get(plan.topic_key))
        return pool_id

    def _pool_put_vectors(self, item: PoolQuestion, prompt_vector: list[float] | None, topic_vector: list[float] | None) -> bool:
        """PutVectors (prompt + topic) then ``vector_state = INDEXED``. Never raises: a failure leaves PENDING for the indexer."""
        try:
            self._pool_vec().put(
                str(item.pool_question_id), prompt_vector=prompt_vector, topic_vector=topic_vector, style=item.style,
                question_type=item.question_type, difficulty_band=item.difficulty_band, status=item.status,
                content_hash=item.content_hash, concept_slugs=item.concept_slugs, topic_key=item.topic_key)
            self._pool_mark_indexed(str(item.pool_question_id))
            return True
        except Exception:
            LOG.warning("question-pool vectors not written for %s; left PENDING for the indexer", item.pool_question_id, exc_info=True)
            return False

    def _pool_mark_indexed(self, pool_id: str) -> None:
        ddb.transact([ddb.Update(CTX, pool_pk(pool_id), "POOL", "SET #vs = :indexed", names={"#vs": "vector_state"},
                                 values={":indexed": "INDEXED"}, cond=ddb.EXISTS, label="POOL_QUESTION:indexed")])

    # ============================================================================================ serve ops (finalize transaction)

    def build_pool_serve_ops(self, student_id, pool_ids: Sequence[str], *, quiz_id) -> list[ddb.TxOp]:
        """Single-item ops for the FINALIZE transaction, at most two per pool question and none for an unknown id:

        * ``Update POOL ADD times_served 1 SET last_served_at, GSI1SK`` (``attribute_exists(PK)``: pool items are never deleted,
          retired ones included, so it cannot fail the paper transaction). Not for the entry this very paper wrote back
          (``source_quiz_id == quiz_id``): a new entry starts at 0 served, as in PostgreSQL. ``GSI1SK`` is computed from the count
          read now, so under concurrent serves it is approximate (the counter itself is exact).
        * ``Update POOL_SERVED`` as an upsert with ``if_not_exists`` on every attribute, so ``first_*`` and ``origin`` never change:
          ``origin`` is WRITE_BACK for the entry written from this paper, SERVED otherwise."""
        ids = [p for p in dict.fromkeys(str(x) for x in pool_ids) if is_uuid(p)]
        if not ids:
            return []
        items = {str(i.pool_question_id): i for i in typed.batch_get(PoolQuestion, [(pool_pk(p), "POOL") for p in ids], consistent=True)}
        sid, qid, now, ops = str(student_id), str(quiz_id), ddb.now_iso(), []
        for pid in ids:
            item = items.get(pid)
            if item is None:
                LOG.warning("question-pool entry %s not found; no serve ops for it", pid)
                continue
            written_back = _str(item.source_quiz_id) == qid
            if not written_back:
                ops.append(ddb.Update(
                    CTX, pool_pk(pid), "POOL", "SET last_served_at = :now, GSI1SK = :g ADD times_served :one",
                    values={":now": now, ":one": 1, ":g": pool_gsi1sk(item.status, item.times_served + 1, pid)},
                    cond=ddb.EXISTS, label="POOL_QUESTION:serve"))
            ops.append(ddb.Update(
                CTX, ddb.student_pk(sid), served_sk(pid),
                "SET #t = if_not_exists(#t, :t), #sid = if_not_exists(#sid, :sid), #pid = if_not_exists(#pid, :pid), "
                "#fq = if_not_exists(#fq, :q), #fs = if_not_exists(#fs, :now), #o = if_not_exists(#o, :o), "
                "#v = if_not_exists(#v, :one)",
                names={"#t": "type", "#sid": "student_id", "#pid": "pool_question_id", "#fq": "first_quiz_id",
                       "#fs": "first_served_at", "#o": "origin", "#v": "version"},
                values={":t": "POOL_SERVED", ":sid": sid, ":pid": pid, ":q": qid, ":now": now, ":one": 1,
                        ":o": "WRITE_BACK" if written_back else "SERVED"},
                label="POOL_SERVED"))
        return ops

    # ============================================================================================ admin reads (A21)

    def get_pool_question(self, pool_id, *, include_question: bool = True) -> dict | None:
        """One pool entry (staff view). With ``include_question`` the payload, answer key included, is resolved (S3 when offloaded)."""
        if not is_uuid(str(pool_id)):
            return None
        item = typed.get(PoolQuestion, pool_pk(pool_id), "POOL")
        if item is None:
            return None
        view = self._pool_view(item)
        if include_question:
            view["question"] = _question_payload(item)
        return view

    def list_pool_questions(self, *, status: str | None = "ACTIVE", style: str | None = None, question_type: str | None = None,
                            difficulty_band: str | None = None, q: str | None = None, limit: int = 50,
                            next_token: str | None = None) -> dict:
        """``{"items": [row], "next_token"}`` without question payloads. Newest first through GSI2 ``POOL_STATUS#<status>``; with
        style, type and band all given, least served first through GSI1 ``POOLKEY#...``. ``status=None`` lists ACTIVE then
        RETIRED. ``q`` is a vector search (prompt and topic vectors) followed by a BatchGet, best match first, not paginated.
        ``difficulty_band='NONE'`` means entries without a band."""
        limit = max(1, min(int(limit), LIST_MAX_LIMIT))
        if status is not None and status not in STATUSES:
            raise ValidationFailed(f"status must be one of {STATUSES}", status=status)
        if style is not None and style not in STYLES:
            raise ValidationFailed(f"style must be one of {STYLES}", style=style)
        if question_type is not None and question_type not in QUESTION_TYPES:
            raise ValidationFailed(f"question_type must be one of {QUESTION_TYPES}", question_type=question_type)
        band = None if difficulty_band is None else (NO_BAND if str(difficulty_band).upper() == NO_BAND else normalize_band(difficulty_band))
        if band not in (None, NO_BAND, *BANDS):
            raise ValidationFailed(f"difficulty_band must be one of {BANDS} or NONE", difficulty_band=difficulty_band)
        if q and q.strip():
            return self._pool_search(q, status, style, question_type, band, limit)

        statuses = [status] if status else list(STATUSES)
        bound = {"k": "pool_list", "f": hashlib.sha256(json.dumps([statuses, style, question_type, band]).encode()).hexdigest()[:16]}
        index, inner = 0, None
        if next_token:
            tok = ddb.verify_token(next_token, **bound)
            index, inner = int(tok["i"]), tok.get("t")
        items: list[dict] = []
        while index < len(statuses) and len(items) < limit:
            rows, inner = self._pool_list_partition(statuses[index], style, question_type, band, limit - len(items), inner)
            items += [self._pool_row_view(r) for r in rows]
            if inner is None:
                index += 1
        more = index < len(statuses)
        return {"items": items, "next_token": ddb.sign_token({**bound, "i": index, "t": inner}) if more else None}

    def _pool_list_partition(self, status: str, style: str | None, question_type: str | None, band: str | None, want: int,
                             token: str | None) -> tuple[list[PoolQuestionRow], str | None]:
        """Up to ``want`` rows of one status partition; the page size equals what is still needed, so the returned token resumes
        exactly where the last returned row was."""
        by_key = bool(style and question_type and band is not None)
        rows: list[PoolQuestionRow] = []
        for _ in range(LIST_MAX_PAGES):
            need = want - len(rows)
            if by_key:
                page = typed.query(PoolQuestionRow, poolkey(style, question_type, None if band == NO_BAND else band), index="GSI1",
                                   sk_begins=f"{status}#", limit=need, next_token=token)
            else:
                page = typed.query(PoolQuestionRow, pool_status_pk(status), index="GSI2", forward=False, limit=need, next_token=token)
            rows += [r for r in page.items if self._pool_row_matches(r, style, question_type, band)]
            token = page.next_token
            if token is None or len(rows) >= want:
                break
        return rows, token

    @staticmethod
    def _pool_row_matches(row: PoolQuestionRow, style: str | None, question_type: str | None, band: str | None) -> bool:
        return ((style is None or row.style == style) and (question_type is None or row.question_type == question_type)
                and (band is None or (row.difficulty_band or NO_BAND) == band))

    def _pool_search(self, q: str, status: str | None, style: str | None, question_type: str | None, band: str | None,
                     limit: int) -> dict:
        vec = self._pool_vec()
        hits = vec.search(vec.embed(q.strip()), status=status, style=style, question_type=question_type, difficulty_band=band,
                          top_k=min(100, 2 * limit))
        ids = [i for i in dict.fromkeys(pool_id_of(h.key) for h in hits) if is_uuid(i)][:limit]
        by_id = {str(i.pool_question_id): i for i in typed.batch_get(PoolQuestion, [(pool_pk(i), "POOL") for i in ids], consistent=False)}
        return {"items": [self._pool_row_view(by_id[i]) for i in ids if i in by_id], "next_token": None}

    def list_pool_served(self, student_id, *, limit: int = 50, next_token: str | None = None) -> dict:
        """The learner's history: ``{"items": [{pool_question_id, first_quiz_id, origin, first_served_at}], "next_token"}``."""
        page = typed.query(PoolServed, ddb.student_pk(student_id), sk_begins="POOLSERVED#", limit=limit, next_token=next_token)
        return {"items": [{"pool_question_id": str(s.pool_question_id), "first_quiz_id": _str(s.first_quiz_id), "origin": s.origin,
                           "first_served_at": _iso(s.first_served_at)} for s in page.items], "next_token": page.next_token}

    # ============================================================================================ retire / reactivate (E06)

    def set_pool_status(self, pool_id, new_status: str, actor: str, reason: str | None = None, *,
                        expected_version: int | None = None,
                        audit_ops: Callable[[dict], Sequence[ddb.TxOp]] | Sequence[ddb.TxOp] | None = None) -> dict:
        """Retire or reactivate one entry in ONE transaction: Update POOL (``status``, ``retired_at``/``retired_reason``, ``GSI1SK``,
        ``GSI2PK``; condition ``status = :from AND version = :v``) and a rewrite of every POOL_CONCEPT with the new status. The audit
        item belongs to the admin wave: ``audit_ops`` is a list of ops, or a callable receiving ``{pool_question_id, from_status,
        to_status, actor, reason, version}`` and returning them; they join the same transaction.

        With ``expected_version`` a stale client gets ``RevisionConflict`` (409); without it a concurrent change is re-read and
        retried. Setting the status the entry already has is ``ConditionFailed`` (409). The vector metadata follows from the stream
        (``update_pool_vector_status``), and the match re-checks ``status`` in DynamoDB. Returns the entry without its payload."""
        if new_status not in STATUSES:
            raise ValidationFailed(f"status must be one of {STATUSES}", status=new_status)
        actor = (actor or "").strip()
        if not actor:
            raise ValidationFailed("actor is required")
        reason = (reason or "").strip() or None
        if new_status == "RETIRED" and not reason:
            raise ValidationFailed("a reason is required to retire a pool question")
        if reason and len(reason) > 500:
            raise ValidationFailed("reason is at most 500 characters")
        if not is_uuid(str(pool_id)):
            raise NotFound(f"pool question {pool_id}")

        def attempt() -> None:
            item = typed.require(PoolQuestion, pool_pk(pool_id), "POOL")
            if expected_version is not None and item.version != expected_version:
                raise RevisionConflict(item.version)
            if item.status == new_status:
                raise _AlreadyInStatus
            pid = str(item.pool_question_id)
            changes: dict[str, Any] = {"status": new_status, "GSI1SK": pool_gsi1sk(new_status, item.times_served, pid),
                                       "GSI2PK": pool_status_pk(new_status)}
            if new_status == "RETIRED":
                changes |= {"retired_at": ddb.now_iso(), "retired_reason": reason}
            uow = ExamUnitOfWork(actor)
            uow.update(PoolQuestion, pool_pk(pid), "POOL", changes, expected={"version": item.version, "status": item.status},
                       remove=() if new_status == "RETIRED" else ("retired_at", "retired_reason"),
                       conflict=RevisionConflict(item.version) if expected_version is not None else None)
            for slug in item.concept_slugs or []:
                uow.put(PoolConcept(PK=concept_pk(slug), SK=concept_sk(item.style, item.question_type, item.difficulty_band, pid),
                                    pool_question_id=pid, concept_slug=slug, status=new_status))
            extra = audit_ops({"pool_question_id": pid, "from_status": item.status, "to_status": new_status, "actor": actor,
                               "reason": reason, "version": item.version}) if callable(audit_ops) else (audit_ops or ())
            for op in extra:
                uow.add(op)
            uow.commit()

        try:
            if expected_version is not None:
                attempt()
            else:
                with_retries(attempt, on=(ConditionFailed,))
        except _AlreadyInStatus:
            raise ConditionFailed(f"pool question is already {new_status}", status=new_status) from None
        view = self.get_pool_question(pool_id, include_question=False)
        if view is None:
            raise NotFound(f"pool question {pool_id}")
        return view

    # ============================================================================================ vector indexer (stream consumer)

    def index_pending_pool_question(self, pool_id) -> str:
        """``exam-pool-vector-indexer`` on a POOL_QUESTION INSERT with ``vector_state=PENDING`` (also repairs PutVectors that failed
        after a finalize): re-embed the prompt and the topic, PutVectors with the current ``status``, then ``vector_state=INDEXED``.
        Returns ``INDEXED``, ``ALREADY_INDEXED`` or ``MISSING``. Failures propagate so the consumer retries and eventually dead-letters."""
        item = typed.get(PoolQuestion, pool_pk(pool_id), "POOL") if is_uuid(str(pool_id)) else None
        if item is None:
            return "MISSING"
        if item.vector_state == "INDEXED":
            return "ALREADY_INDEXED"
        prompt = normalize_prompt(str(_question_payload(item).get("prompt_text") or ""))
        if not prompt:
            raise StoreError("pool question has no prompt_text to embed", pool_question_id=str(pool_id))
        vec = self._pool_vec()
        got = vec.embed_many([prompt] + ([item.topic_key] if item.topic_key else []))
        vec.put(str(item.pool_question_id), prompt_vector=got[0], topic_vector=got[1] if item.topic_key else None, style=item.style,
                question_type=item.question_type, difficulty_band=item.difficulty_band, status=item.status,
                content_hash=item.content_hash, concept_slugs=item.concept_slugs, topic_key=item.topic_key)
        self._pool_mark_indexed(str(item.pool_question_id))
        return "INDEXED"

    def update_pool_vector_status(self, pool_id, status: str) -> int:
        """``exam-pool-vector-indexer`` on a MODIFY of ``status``: the ``status`` metadata of the question's vectors becomes
        ``status``. Returns the number rewritten (0 when it was never indexed: the PENDING indexer writes the current status)."""
        if status not in STATUSES:
            raise ValidationFailed(f"status must be one of {STATUSES}", status=status)
        return self._pool_vec().update_status(str(pool_id), status)

    # ============================================================================================ views

    @staticmethod
    def _pool_view(item: PoolQuestion) -> dict:
        return {"pool_question_id": str(item.pool_question_id), "content_hash": item.content_hash, "style": item.style,
                "question_type": item.question_type, "difficulty_band": item.difficulty_band, "topic_key": item.topic_key,
                "concept_slugs": list(item.concept_slugs or []), "technique_slugs": list(item.technique_slugs or []),
                "source_quiz_id": _str(item.source_quiz_id), "generated_by": item.generated_by, "times_served": item.times_served,
                "last_served_at": _iso(item.last_served_at), "created_at": _iso(item.created_at), "status": item.status,
                "retired_at": _iso(item.retired_at), "retired_reason": item.retired_reason,
                "near_duplicate_of": _str(item.near_duplicate_of), "vector_state": item.vector_state, "version": item.version}

    @staticmethod
    def _pool_row_view(row: PoolQuestionRow | PoolQuestion) -> dict:
        pool_id = row.PK.split("#", 1)[1]
        return {"pool_question_id": pool_id, "style": row.style, "question_type": row.question_type,
                "difficulty_band": row.difficulty_band, "topic_key": row.topic_key, "concept_slugs": list(row.concept_slugs or []),
                "times_served": row.times_served, "created_at": _iso(row.created_at), "status": row.status}


POOL_STORE_METHODS = frozenset(
    name for cls in (PoolPostgres, PoolDynamoDB) for name, fn in vars(cls).items() if not name.startswith("_") and callable(fn))
"""Public method names of the pool area: no other area of the composed exam store may define one of them."""
