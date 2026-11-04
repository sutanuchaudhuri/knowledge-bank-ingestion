"""WP6 question pool on moto + the in-memory vector store (stores/exam/pool.py, pool_vectors.py, models/manual/exam_pool.py).

Vectors are ``MemoryVectorStore`` (``vector_store.set_vector_store_for_tests``); embeddings are a deterministic bag-of-words hash, so
two prompts that share 23 of 24 words are 0.958 similar and two with no words in common are orthogonal.
"""
from __future__ import annotations

import hashlib
import logging
import random
import re
import uuid

import pytest

from mathbank_rest import embeddings, vector_sync
from mathbank_rest import vector_store as vs
from mathbank_rest.config import settings
from mathbank_rest.models.base import DdbItem
from mathbank_rest.models.manual.exam_pool import (
    PoolConcept,
    PoolQuestion,
    PoolQuestionRow,
    PoolServed,
    PoolUniqueHash,
    concept_pk,
    concept_sk,
    content_hash_of,
    pool_pk,
    served_sk,
)
from mathbank_rest.stores import READ_PREFIXES, ddb, typed
from mathbank_rest.stores.errors import (
    ConditionFailed,
    InvalidToken,
    ItemSchemaError,
    RevisionConflict,
    StoreNotImplemented,
    StoreUnavailable,
    ValidationFailed,
)
from mathbank_rest.stores.exam import pool as pool_module
from mathbank_rest.stores.exam.pool import POOL_STORE_METHODS, PoolDynamoDB, PoolPostgres
from mathbank_rest.vector_catalog import Family, QuizQuestionMeta
from mathbank_rest.vector_store import MemoryVectorStore

STUDENT_A = "11111111-1111-4111-8111-111111111111"
STUDENT_B = "22222222-2222-4222-8222-222222222222"
TOPIC = "counting with bijections"


# ------------------------------------------------------------------------------------------------ support

def fake_vec(text: str) -> list[float]:
    v = [0.0] * 1536
    for w in re.findall(r"\w+", text.lower()) or ["empty"]:
        v[int(hashlib.sha1(w.encode()).hexdigest(), 16) % 1536] += 1.0
    return v


def words(prefix: str, n: int = 24, replace_last: str | None = None) -> str:
    ws = [f"{prefix}{i}" for i in range(n)]
    if replace_last:
        ws[-1] = replace_last
    return " ".join(ws)


def qdoc(prompt: str, *, style: str = "AIME", band: str | None = "medium", topic: str | None = TOPIC, concepts=("combinatorics",),
         qtype: str = "MCQ", **extra) -> dict:
    return {"question_type": qtype, "prompt_text": prompt, "prompt_latex": None, "options": [{"key": "A", "text": "4"}],
            "correct_answer": {"correct_key": "A"}, "option_explanations": {}, "solution_text": "because", "solution_steps": [],
            "key_insight": "", "difficulty_band": None, "revision_log": [{"round": 1}], "concept_slugs": list(concepts),
            "technique_slugs": [], "skill_slugs": [], "inspiration_sources": [], "diagram": None, "add_to_pool": True,
            "style": style, "paper_difficulty_band": band, "generated_by": "agent-1", "pool_topic": topic, "pool_concept_slugs": [],
            **extra}


class Broken:
    """A vector store that is down."""

    def query(self, *a, **k):
        raise StoreUnavailable("vectors down")

    get = put = delete = keys = query


@pytest.fixture()
def env(ddb, monkeypatch):
    mem = MemoryVectorStore()
    vs.set_vector_store_for_tests(mem)
    embeddings.reset_for_tests()
    monkeypatch.setattr(embeddings, "EMBEDDER", fake_vec)
    monkeypatch.setattr(vector_sync, "BATCH_EMBEDDER", lambda texts: [fake_vec(t) for t in texts])
    pool_module._SEEN.clear()
    store = PoolDynamoDB()
    store._pool_rng = random.Random(7)
    yield store, mem
    vs.set_vector_store_for_tests(None)
    embeddings.reset_for_tests()
    pool_module._SEEN.clear()


@pytest.fixture(autouse=True)
def no_postgres(monkeypatch):
    """DynamoDB paths never touch PostgreSQL: any use of the engine fails the test."""
    from mathbank_rest.db import postgres

    class Boom:
        def __getattr__(self, name):
            raise AssertionError(f"PostgreSQL used in a DynamoDB path ({name})")

    monkeypatch.setattr(postgres, "engine", Boom())


def add(store, prompt: str, *, quiz_id: str | None = None, student: str = STUDENT_A, **kw) -> str:
    pid = store.link_or_insert_pool_question(student, quiz_id or str(uuid.uuid4()), qdoc(prompt, **kw))
    assert pid
    return pid


def item(pid: str) -> PoolQuestion:
    return typed.require(PoolQuestion, pool_pk(pid), "POOL")


def pool_ids() -> list[str]:
    return [r.pool_id for r in typed.query(PoolQuestionRow, "POOL_STATUS#ACTIVE", index="GSI2", limit=200).items]


def serve(store, student: str, pids: list[str], quiz_id: str | None = None) -> list[ddb.TxOp]:
    ops = store.build_pool_serve_ops(student, pids, quiz_id=quiz_id or str(uuid.uuid4()))
    ddb.transact(ops)
    return ops


def match(store, student=STUDENT_A, **kw) -> list[dict]:
    args = {"style": "AIME", "question_types": ["MCQ"], "difficulty_band": "medium", "topic": TOPIC, "concept_slugs": [], "limit": 20}
    return store.match_pool_questions(student, **{**args, **kw})


# ------------------------------------------------------------------------------------------------ models

def test_models_accept_the_migrated_shapes_losslessly():
    pid, qid, sha = str(uuid.uuid4()), str(uuid.uuid4()), "a" * 64
    raw = {"PK": f"POOL#{pid}", "SK": "POOL", "type": "POOL_QUESTION", "GSI1PK": "POOLKEY#AIME#MCQ#NONE", "GSI1SK": f"ACTIVE#00000003#{pid}",
           "GSI2PK": "POOL_STATUS#ACTIVE", "GSI2SK": f"2026-01-01T00:00:00.000000Z#{pid}", "pool_question_id": pid, "content_hash": sha,
           "style": "AIME", "question_type": "MCQ", "topic_key": "t", "source_quiz_id": qid, "generated_by": "a", "times_served": 3,
           "created_at": "2026-01-01T00:00:00.000000Z", "concept_slugs": ["c"], "question": {"prompt_text": "p"}, "status": "ACTIVE",
           "vector_state": "PENDING", "version": 1}
    assert PoolQuestion.from_item(raw).to_item() == raw
    unique = {"PK": f"UNIQUE#content_hash#{sha}", "SK": "UNIQUE", "type": "UNIQUE", "pool_question_id": pid}
    assert PoolUniqueHash.from_item(unique).to_item() == unique
    unique2 = {**unique, "type": "UNIQUE_CONTENT_HASH", "version": 1}
    assert PoolUniqueHash.from_item(unique2).to_item() == unique2
    concept = {"PK": "POOLCONCEPT#c", "SK": f"AIME#MCQ#NONE#{pid}", "type": "POOL_CONCEPT", "pool_question_id": pid, "concept_slug": "c",
               "status": "ACTIVE"}
    assert PoolConcept.from_item(concept).to_item() == concept
    served = {"PK": f"STUDENT#{STUDENT_A}", "SK": f"POOLSERVED#{pid}", "type": "POOL_SERVED", "student_id": STUDENT_A, "pool_question_id": pid,
              "first_quiz_id": qid, "first_served_at": "2026-01-01T00:00:00.000000Z", "origin": "SERVED"}
    assert PoolServed.from_item(served).to_item() == served


def test_the_model_rejects_what_the_design_forbids():
    base = {"pool_id": str(uuid.uuid4()), "created_at": "2026-01-01T00:00:00.000000Z", "content_hash": "a" * 64, "style": "AIME",
            "question_type": "MCQ", "question": {"prompt_text": "p"}}
    PoolQuestion.build(**base)
    for bad in ({"style": "OLYMPIAD"}, {"question_type": "ESSAY"}, {"difficulty_band": "Easy"}, {"status": "GONE"},
                {"status": "RETIRED"}, {"question": None}, {"question_ref": {"bucket": "bbb", "key": "k", "sha256": "b" * 64, "bytes": 1}}):
        with pytest.raises(ValueError):
            PoolQuestion.build(**{**base, **bad})
    good = PoolQuestion.build(**base).to_item()
    with pytest.raises(ItemSchemaError):
        PoolQuestion.from_item({**good, "GSI2PK": "POOL_STATUS#RETIRED"})            # keys must agree with the attributes
    with pytest.raises(ItemSchemaError):
        PoolQuestion.from_item({**good, "GSI1PK": "POOLKEY#AIME#PROOF#NONE"})


def test_helpers_equal_the_postgres_functions():
    from mathbank_rest import quiz_runtime

    for topic in (None, "  Counting   WITH\tBijections ", "x" * 500):
        assert pool_module.normalize_topic_key(topic) == quiz_runtime.normalize_topic_key(topic)
    assert content_hash_of("What is 2 + 2?") == quiz_runtime._pool_content_hash("  what IS 2 +  2? ")
    assert set(pool_module.POOL_QUESTION_EXCLUDED_FIELDS) == set(quiz_runtime._POOL_QUESTION_EXCLUDED_FIELDS)


def test_vector_metadata_model_carries_the_design_keys():
    f = QuizQuestionMeta.filterable()
    assert {"kind", "style", "question_type", "difficulty_band", "status"} <= f
    assert {"content_hash", "model", "topic_key_sha256"}.isdisjoint(f)
    assert settings.quiz_pool_topic_min_sim == 0.80 and settings.quiz_pool_dup_min_sim == 0.95
    assert settings.quiz_pool_vector_index == Family.QUIZ_QUESTION.index_name == "quiz-question-te3small-1536-v1"


def test_method_names_follow_the_read_prefix_rule():
    reads = {"get_pool_question", "list_pool_questions", "list_pool_served"}
    public = {n for n in POOL_STORE_METHODS}
    assert {n for n in public if n.startswith(READ_PREFIXES)} == reads
    assert {n for n in vars(PoolPostgres) if n.startswith(READ_PREFIXES)} == reads
    assert {"match_pool_questions", "link_or_insert_pool_question", "build_pool_serve_ops", "set_pool_status",
            "index_pending_pool_question", "update_pool_vector_status"} <= public
    from mathbank_rest.stores.exam import AdminDynamoDB, PapersDynamoDB

    for other in (PapersDynamoDB, AdminDynamoDB):
        assert POOL_STORE_METHODS.isdisjoint({n for n in vars(other) if not n.startswith("_")}), other.__name__


# ------------------------------------------------------------------------------------------------ write-back (A16, A17)

def test_write_back_writes_the_whole_entry_and_its_vectors(env):
    store, mem = env
    quiz = str(uuid.uuid4())
    d = qdoc(words("a"), concepts=("combinatorics", "counting"), pool_concept_slugs=["graphs"])
    pid = store.link_or_insert_pool_question(STUDENT_A, quiz, d)
    p = item(pid)
    assert (p.status, p.vector_state, p.version, p.times_served) == ("ACTIVE", "INDEXED", 1, 0)
    assert (p.style, p.question_type, p.difficulty_band, p.topic_key, str(p.source_quiz_id), p.generated_by) == (
        "AIME", "MCQ", "medium", TOPIC, quiz, "agent-1")
    assert p.concept_slugs == ["combinatorics", "counting", "graphs"]
    assert (p.GSI1PK, p.GSI1SK[:9], p.GSI2PK) == ("POOLKEY#AIME#MCQ#medium", "ACTIVE#00", "POOL_STATUS#ACTIVE")
    payload = p.resolve("question")
    assert not set(payload) & {"revision_log", "add_to_pool", "pool_question_id", "style", "pool_topic", "paper_difficulty_band", "generated_by",
                               "pool_concept_slugs"}
    assert payload["prompt_text"] == words("a") and payload["correct_answer"] == {"correct_key": "A"}
    sentinel = typed.require(PoolUniqueHash, f"UNIQUE#content_hash#{p.content_hash}", "UNIQUE")
    assert str(sentinel.pool_question_id) == pid
    for slug in ("combinatorics", "counting", "graphs"):
        c = typed.require(PoolConcept, concept_pk(slug), concept_sk("AIME", "MCQ", "medium", pid))
        assert c.status == "ACTIVE" and str(c.pool_question_id) == pid
    assert sorted(mem.keys(Family.QUIZ_QUESTION)) == sorted([f"{pid}#prompt", f"{pid}#topic"])
    meta = {v.key: v.metadata for v in mem.get(Family.QUIZ_QUESTION, [f"{pid}#prompt", f"{pid}#topic"])}
    assert meta[f"{pid}#prompt"]["kind"] == "prompt" and meta[f"{pid}#topic"]["kind"] == "topic"
    assert meta[f"{pid}#topic"]["status"] == "ACTIVE" and meta[f"{pid}#topic"]["difficulty_band"] == "medium"
    assert meta[f"{pid}#prompt"]["content_hash"] == p.content_hash and meta[f"{pid}#prompt"]["model"] == "text-embedding-3-small"
    assert "prompt_text" not in str(meta) and STUDENT_A not in str(meta)                  # no free text, no learner id


def test_a_null_band_is_none_in_the_vectors_and_the_keys(env):
    store, mem = env
    pid = add(store, words("n"), band=None, topic=None)
    assert item(pid).GSI1PK == "POOLKEY#AIME#MCQ#NONE" and item(pid).difficulty_band is None
    assert list(mem.keys(Family.QUIZ_QUESTION)) == [f"{pid}#prompt"]                  # no topic, no topic vector
    assert mem.get(Family.QUIZ_QUESTION, [f"{pid}#prompt"])[0].metadata["difficulty_band"] == "NONE"


def test_served_and_non_pool_questions_write_nothing(env):
    store, _ = env
    real = add(store, words("a"))
    assert store.link_or_insert_pool_question(STUDENT_A, str(uuid.uuid4()), qdoc(words("b"), add_to_pool=False)) is None
    assert store.link_or_insert_pool_question(STUDENT_A, str(uuid.uuid4()), qdoc(words("b"), pool_question_id=real)) == real
    assert store.link_or_insert_pool_question(STUDENT_A, str(uuid.uuid4()), qdoc(words("b"), pool_question_id=str(uuid.uuid4()))) is None
    assert pool_ids() == [real]


def test_an_exact_duplicate_links_the_existing_entry_without_embedding(env, monkeypatch):
    store, _ = env
    first = add(store, "What  is the SUM of two and two?")
    monkeypatch.setattr(vector_sync, "BATCH_EMBEDDER", lambda texts: pytest.fail("an exact duplicate must not embed"))
    assert add(store, "what is the sum of two and two?", student=STUDENT_B) == first
    assert pool_ids() == [first]


def test_the_sentinel_race_links_the_winner(env, monkeypatch):
    """The loser read no sentinel, then the winner committed, then the loser's transaction fails on the sentinel and re-reads it."""
    store, mem = env
    winner = add(store, words("a"))
    real_find, calls = store._pool_find_sentinel, []

    def find(content_hash):
        calls.append(content_hash)
        return None if len(calls) == 1 else real_find(content_hash)

    monkeypatch.setattr(store, "_pool_find_sentinel", find)
    monkeypatch.setattr(vector_sync, "BATCH_EMBEDDER", lambda texts: [fake_vec(words("q")) for _ in texts])      # defeat the near-duplicate check
    loser = store.link_or_insert_pool_question(STUDENT_B, str(uuid.uuid4()), qdoc(words("a"), concepts=("other",)))
    assert loser == winner and len(calls) == 2
    assert pool_ids() == [winner]
    assert typed.query(PoolConcept, concept_pk("other")).items == []                  # the loser's transaction rolled back completely
    assert sorted(mem.keys(Family.QUIZ_QUESTION)) == sorted([f"{winner}#prompt", f"{winner}#topic"])


def test_a_near_duplicate_links_the_existing_entry_above_the_threshold(env, monkeypatch):
    store, _ = env
    first = add(store, words("a"))
    assert add(store, words("a", replace_last="other"), student=STUDENT_B) == first              # 23 of 24 words: 0.958 >= 0.95
    assert pool_ids() == [first]
    different = add(store, words("z"))
    assert different != first and sorted(pool_ids()) == sorted([first, different])
    monkeypatch.setattr(settings, "quiz_pool_dup_min_sim", 0.99)
    third = add(store, words("a", replace_last="again"))
    assert third not in (first, different)


def test_near_duplicates_are_scoped_to_style_and_type(env):
    store, _ = env
    first = add(store, words("a"))
    assert add(store, words("a", replace_last="o"), style="HMMT") != first
    assert add(store, words("a", replace_last="p"), qtype="PROOF") != first


def test_pairwise_check_inside_one_finalize_works_without_the_index(env):
    store, _ = env
    vs.set_vector_store_for_tests(Broken())                                      # the index cannot answer: only the in-memory check can
    quiz = str(uuid.uuid4())
    docs = [qdoc(words("a")), qdoc(words("a", replace_last="b")), qdoc(words("z")), qdoc(words("a", replace_last="c"), add_to_pool=False)]
    ids = store.link_or_insert_pool_questions(STUDENT_A, quiz, docs)
    assert ids[1] == ids[0] and ids[2] not in (None, ids[0]) and ids[3] is None
    assert sorted(pool_ids()) == sorted([ids[0], ids[2]])
    assert item(ids[0]).vector_state == "PENDING"                                # nothing could be indexed


def test_one_batched_embedding_call_per_finalize(env, monkeypatch):
    store, _ = env
    calls = []
    monkeypatch.setattr(vector_sync, "BATCH_EMBEDDER", lambda texts: calls.append(list(texts)) or [fake_vec(t) for t in texts])
    store.link_or_insert_pool_questions(STUDENT_A, str(uuid.uuid4()), [qdoc(words("a")), qdoc(words("z")), qdoc(words("y"))])
    assert len(calls) == 1 and len(calls[0]) == 4                                # three prompts and the one topic


def test_a_vector_failure_leaves_the_entry_pending_and_never_raises(env, monkeypatch, caplog):
    store, mem = env
    vs.set_vector_store_for_tests(Broken())
    with caplog.at_level(logging.WARNING):
        pid = add(store, words("a"))
    assert item(pid).vector_state == "PENDING" and "left PENDING" in caplog.text
    monkeypatch.setattr(vector_sync, "BATCH_EMBEDDER", lambda texts: (_ for _ in ()).throw(RuntimeError("openai down")))
    vs.set_vector_store_for_tests(mem)
    pid2 = add(store, words("z"))
    assert item(pid2).vector_state == "PENDING" and list(mem.keys(Family.QUIZ_QUESTION)) == []


def test_the_indexer_repairs_pending_entries_and_is_idempotent(env):
    store, mem = env
    vs.set_vector_store_for_tests(Broken())
    pid = add(store, words("a"), concepts=("combinatorics",))
    vs.set_vector_store_for_tests(mem)
    assert store.index_pending_pool_question(pid) == "INDEXED"
    assert item(pid).vector_state == "INDEXED"
    assert sorted(mem.keys(Family.QUIZ_QUESTION)) == sorted([f"{pid}#prompt", f"{pid}#topic"])
    assert store.index_pending_pool_question(pid) == "ALREADY_INDEXED"
    assert store.index_pending_pool_question(str(uuid.uuid4())) == "MISSING"
    assert match(store, STUDENT_B)[0]["pool_question_id"] == pid                 # the repaired vectors answer the topic branch


def test_the_indexer_failure_propagates_for_the_consumer_to_retry(env):
    store, _ = env
    vs.set_vector_store_for_tests(Broken())
    pid = add(store, words("a"))
    with pytest.raises(StoreUnavailable):
        store.index_pending_pool_question(pid)
    assert item(pid).vector_state == "PENDING"


def test_vector_status_follows_a_retire(env):
    store, mem = env
    pid = add(store, words("a"))
    assert store.update_pool_vector_status(pid, "RETIRED") == 2
    assert {v.metadata["status"] for v in mem.get(Family.QUIZ_QUESTION, [f"{pid}#prompt", f"{pid}#topic"])} == {"RETIRED"}
    assert store.update_pool_vector_status(str(uuid.uuid4()), "RETIRED") == 0
    with pytest.raises(ValidationFailed):
        store.update_pool_vector_status(pid, "GONE")


def test_transactions_stay_within_the_limit(env, monkeypatch):
    store, _ = env
    sizes = []
    real = ddb.transact
    monkeypatch.setattr(ddb, "transact", lambda ops, **k: (sizes.append(len(ops)), real(ops, **k))[1])
    slugs = [f"c{i}" for i in range(10)]
    add(store, words("a"), concepts=slugs)
    docs = [qdoc(words(f"q{i}_"), pool_concept_slugs=[f"p{i}_{j}" for j in range(10)], concepts=slugs) for i in range(20)]
    store.link_or_insert_pool_questions(STUDENT_A, str(uuid.uuid4()), docs)
    assert max(sizes) <= 2 + 20 and all(s <= 100 for s in sizes)
    pids = pool_ids()[:20]
    assert len(store.build_pool_serve_ops(STUDENT_A, pids, quiz_id=str(uuid.uuid4()))) <= 2 * len(pids) <= 40


def test_a_large_payload_goes_to_s3(env):
    store, _ = env
    pid = add(store, words("a"), solution_text="x" * 120_000)
    p = item(pid)
    assert p.question is None and p.question_ref.key == f"exam/pool/{pid}.json"
    body = ddb.client("s3").get_object(Bucket=ddb.data_bucket(), Key=f"exam/pool/{pid}.json")["Body"].read()
    assert len(body) == p.question_ref.bytes and hashlib.sha256(body).hexdigest() == p.question_ref.sha256
    assert len(store.get_pool_question(pid)["question"]["solution_text"]) == 120_000
    assert len(match(store, STUDENT_B)[0]["question"]["solution_text"]) == 120_000
    assert "question" not in store.get_pool_question(pid, include_question=False)


def test_invalid_pool_metadata_is_a_validation_error(env):
    store, _ = env
    for bad in ({"style": "OLYMPIAD"}, {"qtype": "ESSAY"}, {"band": "extreme"}):
        with pytest.raises(ValidationFailed):
            add(store, words("a"), **bad)
    d = qdoc(words("a"))
    d.pop("style")
    with pytest.raises(ValidationFailed):
        store.link_or_insert_pool_question(STUDENT_A, str(uuid.uuid4()), d)


# ------------------------------------------------------------------------------------------------ serve ops

def test_serve_ops_shape_and_effect(env):
    store, _ = env
    a, b = add(store, words("a")), add(store, words("z"), topic="graph colouring")
    quiz1, quiz2 = str(uuid.uuid4()), str(uuid.uuid4())
    ops = store.build_pool_serve_ops(STUDENT_B, [a, b, a, "not-a-uuid", str(uuid.uuid4())], quiz_id=quiz1)
    assert len(ops) == 4 and all(o.kind == "update" for o in ops)
    assert [(o.pk, o.sk) for o in ops] == [(pool_pk(a), "POOL"), (f"STUDENT#{STUDENT_B}", served_sk(a)), (pool_pk(b), "POOL"),
                                           (f"STUDENT#{STUDENT_B}", served_sk(b))]
    assert ops[0].cond == ddb.EXISTS and ops[1].cond is None
    ddb.transact(ops)
    assert (item(a).times_served, item(a).GSI1SK, item(a).last_served_at is not None) == (1, f"ACTIVE#00000001#{a}", True)
    s = typed.require(PoolServed, f"STUDENT#{STUDENT_B}", served_sk(a))
    assert (str(s.first_quiz_id), s.origin, str(s.student_id)) == (quiz1, "SERVED", STUDENT_B)
    ddb.transact(store.build_pool_serve_ops(STUDENT_B, [a], quiz_id=quiz2))
    s2 = typed.require(PoolServed, f"STUDENT#{STUDENT_B}", served_sk(a))
    assert str(s2.first_quiz_id) == quiz1 and s2.first_served_at == s.first_served_at          # first_* never change
    assert item(a).times_served == 2
    assert [x["pool_question_id"] for x in store.list_pool_served(STUDENT_B)["items"]] == sorted([a, b])


def test_the_entry_written_back_by_this_paper_is_a_write_back_without_a_bump(env):
    store, _ = env
    quiz = str(uuid.uuid4())
    pid = store.link_or_insert_pool_question(STUDENT_A, quiz, qdoc(words("a")))
    ops = store.build_pool_serve_ops(STUDENT_A, [pid], quiz_id=quiz)
    assert len(ops) == 1
    ddb.transact(ops)
    assert typed.require(PoolServed, f"STUDENT#{STUDENT_A}", served_sk(pid)).origin == "WRITE_BACK" and item(pid).times_served == 0
    assert match(store, STUDENT_A) == []                                         # the author is never served their own question


def test_serve_ops_do_not_fail_for_a_retired_entry(env):
    store, _ = env
    pid = add(store, words("a"))
    store.set_pool_status(pid, "RETIRED", "staff", "bad")
    ddb.transact(store.build_pool_serve_ops(STUDENT_B, [pid], quiz_id=str(uuid.uuid4())))
    assert item(pid).times_served == 1 and item(pid).GSI1SK.startswith("RETIRED#00000001#")


# ------------------------------------------------------------------------------------------------ match (A12-A15)

def test_match_returns_todays_shape(env):
    store, _ = env
    pid = add(store, words("a"), concepts=("combinatorics",))
    out = match(store, STUDENT_B)
    assert set(out[0]) == {"pool_question_id", "question_type", "question", "topic_similarity"}
    assert (out[0]["pool_question_id"], out[0]["question_type"]) == (pid, "MCQ") and out[0]["topic_similarity"] == pytest.approx(1.0)
    q = out[0]["question"]
    assert q["prompt_text"] == words("a") and q["prompt_latex"] is None and q["options"] == [{"key": "A", "text": "4"}]
    assert q["difficulty_band"] is None and q["diagram"] is None                  # nullable keys read back as null, as from jsonb
    assert isinstance(out[0]["topic_similarity"], float)


def test_match_without_topic_and_concepts_is_empty_and_filters_apply(env):
    store, _ = env
    add(store, words("a"))
    assert match(store, topic="  ", concept_slugs=[]) == []
    assert match(store, style="HMMT") == [] and match(store, question_types=["PROOF"]) == [] and match(store, difficulty_band="hard") == []
    assert match(store, difficulty_band=None) == [] and match(store, style="NOPE") == [] and match(store, question_types=["ESSAY"]) == []
    assert len(match(store, question_types=[])) == 1                              # no types = all of them
    assert len(match(store, question_types=["PROOF", "MCQ"], difficulty_band="Medium")) == 1


def test_topic_similarity_floor(env):
    store, _ = env
    add(store, words("a"), topic="counting with bijections")
    assert len(match(store, topic="counting bijections")) == 1                    # 0.816 >= 0.80
    assert match(store, topic="geometry of circles") == []
    assert len(match(store, topic="counting bijections", min_topic_similarity=0.9)) == 0
    near = match(store, topic="counting bijections")
    assert 0.80 <= near[0]["topic_similarity"] < 1.0


def test_a_null_band_matches_only_a_null_band(env):
    store, _ = env
    none_band = add(store, words("a"), band=None)
    add(store, words("z"), band="easy")
    assert [m["pool_question_id"] for m in match(store, difficulty_band=None)] == [none_band]


def test_history_exclusion_hides_served_entries_for_that_learner_only(env):
    store, _ = env
    a, b = add(store, words("a")), add(store, words("z"))
    serve(store, STUDENT_B, [a])
    assert {m["pool_question_id"] for m in match(store, STUDENT_B)} == {b}
    assert {m["pool_question_id"] for m in match(store, STUDENT_A)} == {a, b}
    assert {m["pool_question_id"] for m in match(store, str(uuid.uuid4()))} == {a, b}


def test_history_exclusion_covers_the_concept_branch_and_an_anonymous_caller_reads_no_history(env, monkeypatch):
    store, _ = env
    a = add(store, words("a"), concepts=("graphs",))
    serve(store, STUDENT_B, [a])
    assert match(store, STUDENT_B, topic=None, concept_slugs=["graphs"]) == []
    models = []
    real = typed.batch_get
    monkeypatch.setattr(typed, "batch_get", lambda model, keys, **k: (models.append(model), real(model, keys, **k))[1])
    out = match(store, None, topic=None, concept_slugs=["graphs"])
    assert [m["pool_question_id"] for m in out] == [a] and PoolServed not in models


def test_a_retired_entry_is_excluded_even_when_the_vector_still_says_active(env):
    store, mem = env
    a, b = add(store, words("a")), add(store, words("z"))
    store.set_pool_status(a, "RETIRED", "staff", "wrong answer key")
    assert mem.get(Family.QUIZ_QUESTION, [f"{a}#topic"])[0].metadata["status"] == "ACTIVE"      # the stream has not run yet
    assert {m["pool_question_id"] for m in match(store, STUDENT_B)} == {b}                       # DynamoDB re-check
    store.update_pool_vector_status(a, "RETIRED")
    assert {m["pool_question_id"] for m in match(store, STUDENT_B)} == {b}                       # and the vector filter
    store.set_pool_status(a, "ACTIVE", "staff")
    assert {m["pool_question_id"] for m in match(store, STUDENT_B, topic=None, concept_slugs=["combinatorics"])} == {a, b}


def test_the_concept_branch_works_with_vectors_disabled(env, caplog):
    store, _ = env
    a = add(store, words("a"), concepts=("graphs", "trees"))
    add(store, words("z"), concepts=("other",))
    for unavailable in (None, Broken()):
        vs.set_vector_store_for_tests(unavailable)                                # pgvector default: StoreUnavailable; or a store that is down
        with caplog.at_level(logging.WARNING):
            got = match(store, STUDENT_B, concept_slugs=["trees"])
        assert [m["pool_question_id"] for m in got] == [a] and got[0]["topic_similarity"] == 0.0
        assert match(store, STUDENT_B, topic=None, concept_slugs=["other", "trees"]) != []
    assert "topic branch unavailable" in caplog.text


def test_the_concept_branch_is_keyed_by_style_type_and_band(env):
    store, _ = env
    a = add(store, words("a"), concepts=("graphs",))
    add(store, words("z"), concepts=("graphs",), style="HMMT")
    add(store, words("y"), concepts=("graphs",), qtype="PROOF")
    add(store, words("x"), concepts=("graphs",), band="hard")
    assert [m["pool_question_id"] for m in match(store, STUDENT_B, topic=None, concept_slugs=["graphs"])] == [a]
    assert len(match(store, STUDENT_B, topic=None, concept_slugs=["graphs"], question_types=["MCQ", "PROOF"])) == 2


def test_ordering_is_similarity_then_least_served_then_random(env):
    store, _ = env
    exact = add(store, words("a"), topic=TOPIC, concepts=("graphs",))
    near = add(store, words("b"), topic="counting bijections", concepts=("graphs",))
    c1, c2, c3 = (add(store, words(p), topic=None, concepts=("graphs",)) for p in "cde")
    serve(store, STUDENT_B, [c1])
    serve(store, STUDENT_B, [c1], str(uuid.uuid4()))
    serve(store, STUDENT_B, [c2])
    out = [m["pool_question_id"] for m in match(store, STUDENT_A, topic=TOPIC, concept_slugs=["graphs"], limit=10)]
    assert out[:2] == [exact, near]                                              # topic similarity first
    assert out[2] == c3 and out[3:] == [c2, c1]                                  # then times_served 0, 1, 2
    no_topic = [m["pool_question_id"] for m in match(store, STUDENT_A, topic=None, concept_slugs=["graphs"], limit=10)]
    assert sorted(no_topic[:3]) == sorted([exact, near, c3]) and no_topic[3:] == [c2, c1]      # without a topic: served count only


def test_random_tie_break_uses_the_injected_rng(env):
    store, _ = env
    ids = [add(store, words(p), topic=None, concepts=("graphs",)) for p in "abcdef"]
    orders = set()
    for seed in range(6):
        store._pool_rng = random.Random(seed)
        orders.add(tuple(m["pool_question_id"] for m in match(store, STUDENT_B, topic=None, concept_slugs=["graphs"])))
    assert len(orders) > 1 and all(sorted(o) == sorted(ids) for o in orders)
    store._pool_rng = random.Random(3)
    first = [m["pool_question_id"] for m in match(store, STUDENT_B, topic=None, concept_slugs=["graphs"])]
    store._pool_rng = random.Random(3)
    assert first == [m["pool_question_id"] for m in match(store, STUDENT_B, topic=None, concept_slugs=["graphs"])]


def test_limit_is_clamped_like_today(env):
    store, _ = env
    for p in "abcde":
        add(store, words(p), topic=None, concepts=("graphs",))
    assert len(match(store, topic=None, concept_slugs=["graphs"], limit=2)) == 2
    assert len(match(store, topic=None, concept_slugs=["graphs"], limit=0)) == 1
    assert len(match(store, topic=None, concept_slugs=["graphs"], limit=500)) == 5


def test_topic_branch_asks_for_min_100_4x_limit(env, monkeypatch):
    store, mem = env
    add(store, words("a"))
    seen = []
    real = mem.query
    monkeypatch.setattr(mem, "query", lambda family, vector, top_k=10, filter=None: (seen.append((top_k, filter)), real(family, vector, top_k, filter))[1])
    match(store, limit=7)
    match(store, limit=50)
    assert [k for k, _ in seen] == [28, 100]
    flt = seen[0][1]["$and"]
    assert {"kind": {"$eq": "topic"}} in flt and {"status": {"$eq": "ACTIVE"}} in flt and {"difficulty_band": {"$eq": "medium"}} in flt
    assert {"question_type": {"$in": ["MCQ"]}} in flt


# ------------------------------------------------------------------------------------------------ admin (A21, E04-E06)

def test_get_pool_question_returns_the_staff_view(env):
    store, _ = env
    pid = add(store, words("a"))
    got = store.get_pool_question(pid)
    assert got["pool_question_id"] == pid and got["status"] == "ACTIVE" and got["question"]["prompt_text"] == words("a")
    assert got["vector_state"] == "INDEXED" and got["version"] == 1 and got["retired_at"] is None
    assert store.get_pool_question(str(uuid.uuid4())) is None and store.get_pool_question("nope") is None


def test_set_pool_status_retires_and_reactivates_in_one_transaction(env):
    store, _ = env
    pid = add(store, words("a"), concepts=("graphs", "trees"))
    out = store.set_pool_status(pid, "RETIRED", "staff:42", "answer key wrong")
    assert (out["status"], out["version"], out["retired_reason"]) == ("RETIRED", 2, "answer key wrong") and out["retired_at"]
    p = item(pid)
    assert (p.GSI2PK, p.GSI1SK.split("#")[0]) == ("POOL_STATUS#RETIRED", "RETIRED") and p.updated_at is not None
    for slug in ("graphs", "trees"):
        assert typed.require(PoolConcept, concept_pk(slug), concept_sk("AIME", "MCQ", "medium", pid)).status == "RETIRED"
    with pytest.raises(ConditionFailed):
        store.set_pool_status(pid, "RETIRED", "staff:42", "again")
    back = store.set_pool_status(pid, "ACTIVE", "staff:42")
    assert (back["status"], back["version"], back["retired_at"], back["retired_reason"]) == ("ACTIVE", 3, None, None)
    assert item(pid).GSI2PK == "POOL_STATUS#ACTIVE"
    assert typed.require(PoolConcept, concept_pk("graphs"), concept_sk("AIME", "MCQ", "medium", pid)).status == "ACTIVE"


def test_set_pool_status_validations_and_version_conflicts(env):
    store, _ = env
    pid = add(store, words("a"))
    for args in (("GONE", "staff", "r"), ("RETIRED", "", "r"), ("RETIRED", "staff", None), ("RETIRED", "staff", "x" * 501)):
        with pytest.raises(ValidationFailed):
            store.set_pool_status(pid, *args)
    with pytest.raises(RevisionConflict) as exc:
        store.set_pool_status(pid, "RETIRED", "staff", "r", expected_version=9)
    assert exc.value.current_revision == 1
    assert store.set_pool_status(pid, "RETIRED", "staff", "r", expected_version=1)["version"] == 2
    from mathbank_rest.stores.errors import NotFound

    with pytest.raises(NotFound):
        store.set_pool_status(str(uuid.uuid4()), "RETIRED", "staff", "r")


def test_a_concurrent_status_change_is_retried_without_a_client_version(env, monkeypatch):
    store, _ = env
    pid = add(store, words("a"))
    real, done = typed.require, []

    def racing(model, pk, sk, **k):
        got = real(model, pk, sk, **k)
        if model is PoolQuestion and not done:
            done.append(1)
            ddb.cas_update("exam", pk, sk, got.version, {"generated_by": "someone else"})      # a concurrent writer bumps the version
        return got

    monkeypatch.setattr(typed, "require", racing)
    assert store.set_pool_status(pid, "RETIRED", "staff", "r")["version"] == 3
    assert item(pid).generated_by == "someone else"


def test_the_audit_hook_joins_the_transaction(env):
    store, _ = env
    pid = add(store, words("a"))
    seen = []

    def audit(ctx):
        seen.append(ctx)
        return [ddb.Put("exam", {"PK": "AUDIT#2026-11", "SK": f"t#{pid}", "type": "ADMIN_AUDIT", "actor": ctx["actor"]}, ddb.NOT_EXISTS)]

    store.set_pool_status(pid, "RETIRED", "staff", "r", audit_ops=audit)
    assert seen[0]["from_status"] == "ACTIVE" and seen[0]["to_status"] == "RETIRED" and seen[0]["version"] == 1
    assert ddb.get_item("exam", "AUDIT#2026-11", f"t#{pid}")["actor"] == "staff"
    clash = [ddb.Put("exam", {"PK": "AUDIT#2026-11", "SK": f"t#{pid}", "type": "ADMIN_AUDIT"}, ddb.NOT_EXISTS)]
    with pytest.raises(ConditionFailed):
        store.set_pool_status(pid, "ACTIVE", "staff", audit_ops=clash)                    # a failing audit op rolls the whole change back
    assert item(pid).status == "RETIRED"


def test_list_pool_questions_pages_newest_first_through_gsi2(env):
    store, _ = env
    ids = [add(store, words(p)) for p in "abcde"]
    pages, token = [], None
    while True:
        page = store.list_pool_questions(limit=2, next_token=token)
        pages.append([r["pool_question_id"] for r in page["items"]])
        token = page["next_token"]
        if not token:
            break
    assert [len(p) for p in pages] == [2, 2, 1] and [i for page in pages for i in page] == list(reversed(ids))
    row = store.list_pool_questions(limit=1)["items"][0]
    assert set(row) == {"pool_question_id", "style", "question_type", "difficulty_band", "topic_key", "concept_slugs", "times_served",
                        "created_at", "status"} and row["status"] == "ACTIVE" and "question" not in row
    with pytest.raises(InvalidToken):
        store.list_pool_questions(limit=2, next_token=token or page["next_token"] or "x.y")
    first = store.list_pool_questions(limit=2)["next_token"]
    with pytest.raises(InvalidToken):
        store.list_pool_questions(limit=2, status="RETIRED", next_token=first)            # a token is bound to its filters


def test_list_pool_questions_by_status_and_filters(env):
    store, _ = env
    a = add(store, words("a"))
    b = add(store, words("b"), style="HMMT")
    c = add(store, words("c"), band=None, qtype="PROOF")
    store.set_pool_status(a, "RETIRED", "staff", "r")
    assert {r["pool_question_id"] for r in store.list_pool_questions()["items"]} == {b, c}
    assert [r["pool_question_id"] for r in store.list_pool_questions(status="RETIRED")["items"]] == [a]
    both = store.list_pool_questions(status=None, limit=1)
    assert both["next_token"] and both["items"][0]["status"] == "ACTIVE"
    allrows = store.list_pool_questions(status=None, limit=10)["items"]
    assert [r["status"] for r in allrows] == ["ACTIVE", "ACTIVE", "RETIRED"]
    assert [r["pool_question_id"] for r in store.list_pool_questions(style="HMMT")["items"]] == [b]
    assert [r["pool_question_id"] for r in store.list_pool_questions(question_type="PROOF")["items"]] == [c]
    assert [r["pool_question_id"] for r in store.list_pool_questions(difficulty_band="NONE")["items"]] == [c]
    for bad in ({"status": "GONE"}, {"style": "X"}, {"question_type": "X"}, {"difficulty_band": "extreme"}):
        with pytest.raises(ValidationFailed):
            store.list_pool_questions(**bad)


def test_list_pool_questions_by_key_is_least_served_first(env):
    store, _ = env
    a, b, c = (add(store, words(p)) for p in "abc")
    serve(store, STUDENT_B, [a])
    serve(store, STUDENT_B, [a], str(uuid.uuid4()))
    serve(store, STUDENT_B, [b])
    add(store, words("o"), style="HMMT")
    got = store.list_pool_questions(style="AIME", question_type="MCQ", difficulty_band="medium")
    assert [r["pool_question_id"] for r in got["items"]] == [c, b, a] and [r["times_served"] for r in got["items"]] == [0, 1, 2]
    store.set_pool_status(c, "RETIRED", "staff", "r")
    assert [r["pool_question_id"] for r in store.list_pool_questions(style="AIME", question_type="MCQ", difficulty_band="medium")["items"]] == [b, a]


def test_list_pool_questions_q_searches_the_vectors(env):
    store, _ = env
    a = add(store, words("a"), topic="counting with bijections")
    add(store, words("z"), topic="geometry of circles")
    out = store.list_pool_questions(q="counting with bijections", limit=1)
    assert [r["pool_question_id"] for r in out["items"]] == [a] and out["next_token"] is None
    assert store.list_pool_questions(q="counting with bijections", status="RETIRED")["items"] == []
    assert store.list_pool_questions(q=words("a"), style="AIME")["items"][0]["pool_question_id"] == a


def test_list_pool_served_pages(env):
    store, _ = env
    ids = [add(store, words(p)) for p in "abc"]
    serve(store, STUDENT_B, ids)
    first = store.list_pool_served(STUDENT_B, limit=2)
    rest = store.list_pool_served(STUDENT_B, limit=2, next_token=first["next_token"])
    assert [x["pool_question_id"] for x in first["items"] + rest["items"]] == sorted(ids) and rest["next_token"] is None
    assert store.list_pool_served(STUDENT_A)["items"] == []
    assert set(first["items"][0]) == {"pool_question_id", "first_quiz_id", "origin", "first_served_at"}


def test_projection_rows_are_partial_so_full_items_come_from_the_base_table(env):
    store, _ = env
    pid = add(store, words("a"))
    raw = ddb.query_page("exam", "POOL_STATUS#ACTIVE", index="GSI2")["items"][0]
    assert "question" not in raw and "content_hash" not in raw and raw["PK"] == pool_pk(pid)
    with pytest.raises(ItemSchemaError):
        PoolQuestion.from_item(raw)                                              # the full model needs the base item
    assert isinstance(PoolQuestionRow.from_item(raw), DdbItem)


# ------------------------------------------------------------------------------------------------ Postgres wrapper

def test_postgres_wrapper_calls_quiz_runtime_at_call_time(monkeypatch):
    from mathbank_rest import quiz_runtime

    calls = []
    monkeypatch.setattr(quiz_runtime, "match_pool_questions", lambda *a, **k: calls.append((a, k)) or [{"pool_question_id": "x"}])
    out = PoolPostgres().match_pool_questions(STUDENT_A, style="AIME", question_types=["MCQ"], difficulty_band=None, topic="t", limit=3)
    assert out == [{"pool_question_id": "x"}]
    assert calls == [((STUDENT_A,), {"style": "AIME", "question_types": ["MCQ"], "difficulty_band": None, "topic": "t",
                                     "concept_slugs": None, "limit": 3, "min_topic_similarity": 0.5})]
    assert PoolPostgres().build_pool_serve_ops(STUDENT_A, ["a"], quiz_id="q") == []


def test_postgres_link_calls_the_sql_link_with_the_paper_context(monkeypatch):
    from mathbank_rest import quiz_runtime

    seen = {}

    class Conn:
        def __enter__(self):
            return "conn"

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(quiz_runtime, "engine", type("E", (), {"begin": staticmethod(lambda: Conn())}))
    monkeypatch.setattr(quiz_runtime, "_link_pool_question", lambda conn, q, **k: seen.update(conn=conn, q=q, **k) or uuid.UUID(int=5))
    out = PoolPostgres().link_or_insert_pool_question(STUDENT_A, "quiz", qdoc("p", topic="  Graph   Colouring ", pool_concept_slugs=["x"]))
    assert out == str(uuid.UUID(int=5)) and seen["conn"] == "conn"
    assert seen["paper"] == {"style": "AIME", "difficulty_band": "medium", "generated_by": "agent-1"}
    assert seen["pool_topic_key"] == "graph colouring" and seen["pool_concept_slugs"] == ["x"] and "style" not in seen["q"]
    with pytest.raises(StoreNotImplemented):
        PoolPostgres().get_pool_question("x")
