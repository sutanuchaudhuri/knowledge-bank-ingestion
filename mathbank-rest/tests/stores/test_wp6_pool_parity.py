"""``POST /v1/quiz-integration/question-pool/match``: the same requests through the real router on both exam-store backends.

The "postgres" side is ``PostgresExamStore`` over ``PoolOracle``, an in-memory statement of today's SQL (``quiz_runtime.match_pool_questions``:
style, type list, ``IS NOT DISTINCT FROM`` band, topic similarity or concept overlap, not already served, ``ORDER BY similarity DESC,
times_served ASC``). pg_trgm similarity is replaced by exact equality of the topic key (1.0 or 0.0) and the DynamoDB side computes cosine
similarity on the same strings, so membership, order and shape must be identical; the similarity of a near, not identical, topic is the one
documented difference (trigram versus embedding) and is not exercised here. Ids are generated per backend and compared through the prompt.
"""
from __future__ import annotations

import random
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "parity"))

from parity_harness import ParityCase, diff
from test_wp6_pool import STUDENT_A, STUDENT_B, TOPIC, add, env, qdoc, serve, words  # noqa: F401

from mathbank_rest import quiz_runtime, stores
from mathbank_rest.config import settings
from mathbank_rest.main import app
from mathbank_rest.stores.exam import DynamoDBExamStore, PostgresExamStore
from mathbank_rest.stores.exam.pool import (
    DOC_CONTEXT_KEYS,
    POOL_QUESTION_EXCLUDED_FIELDS,
    normalize_topic_key,
)

KEY = {"X-Admin-Api-Key": settings.admin_api_key}
URL = "/v1/quiz-integration/question-pool/match"


class PoolOracle:
    """quiz.question_pool and quiz.question.pool_question_id as plain Python."""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.served: dict[str, set[str]] = {}

    def insert(self, doc: dict, times_served: int) -> str:
        pid = str(uuid.uuid4())
        skip = set(POOL_QUESTION_EXCLUDED_FIELDS) | set(DOC_CONTEXT_KEYS)
        self.rows.append({"id": pid, "style": doc["style"], "qtype": doc["question_type"], "band": doc["paper_difficulty_band"],
                          "topic": normalize_topic_key(doc["pool_topic"]), "concepts": set(doc["concept_slugs"]),
                          "question": {k: v for k, v in doc.items() if k not in skip}, "served": times_served})
        return pid

    def match_pool_questions(self, student_id, *, style, question_types, difficulty_band, topic, concept_slugs=None, limit=20,
                             min_topic_similarity=0.5):
        topic_key, concepts = normalize_topic_key(topic), {s for s in (concept_slugs or []) if s}
        if not topic_key and not concepts:
            return []
        types = question_types or list(quiz_runtime.QUESTION_TYPES)
        hits = []
        for r in self.rows:
            sim = 1.0 if topic_key and r["topic"] == topic_key else 0.0
            if (r["style"] == style and r["qtype"] in types and r["band"] == difficulty_band
                    and ((topic_key and sim >= min_topic_similarity) or (concepts and r["concepts"] & concepts))
                    and r["id"] not in self.served.get(str(student_id), set())):
                hits.append((sim, r))
        hits.sort(key=lambda h: (-h[0], h[1]["served"]))
        return [{"pool_question_id": r["id"], "question_type": r["qtype"], "question": r["question"], "topic_similarity": sim}
                for sim, r in hits[:max(1, min(limit, 50))]]


class Backend:
    def __init__(self, store) -> None:
        self.store, self.http = store, TestClient(app)

    def request(self, method, path, **kw):
        with stores.override_store("exam", self.store):
            return self.http.request(method, path, **kw)


@pytest.fixture()
def clients(env, monkeypatch):  # noqa: F811
    assert env
    dynamo = DynamoDBExamStore()
    dynamo._pool_rng = random.Random(5)
    oracle = PoolOracle()
    monkeypatch.setattr(quiz_runtime, "match_pool_questions", oracle.match_pool_questions)
    plan = [("a", {"concepts": ("graphs",)}, 3), ("b", {"concepts": ("graphs", "trees")}, 0),
            ("c", {"concepts": ("trees",), "topic": "other topic phrase"}, 2), ("d", {"style": "HMMT", "concepts": ("graphs",)}, 0),
            ("e", {"band": "easy", "concepts": ("graphs",)}, 0), ("f", {"qtype": "PROOF", "concepts": ("graphs",)}, 0),
            ("g", {"band": None, "concepts": ("graphs",)}, 0)]
    labels, ids = {}, {"postgres": {}, "dynamodb": {}}
    for prefix, kw, served in plan:
        doc = qdoc(words(prefix), **{k: v for k, v in kw.items()})
        pid = add(dynamo, words(prefix), **kw)
        for n in range(served):
            serve(dynamo, f"00000000-0000-4000-8000-00000000000{n}", [pid], str(uuid.uuid4()))
        labels[prefix] = words(prefix)
        ids["dynamodb"][pid] = ids["postgres"][oracle.insert(doc, served)] = prefix
    by_prefix = {v: k for k, v in ids["postgres"].items()}
    oracle.served[STUDENT_B] = {by_prefix["b"]}
    next(r for r in oracle.rows if r["id"] == by_prefix["b"])["served"] += 1              # serving it to B bumped the counter on both sides
    serve(dynamo, STUDENT_B, [k for k, v in ids["dynamodb"].items() if v == "b"])
    return {"postgres": Backend(PostgresExamStore()), "dynamodb": Backend(dynamo)}, ids


def run(clients_and_ids, case: ParityCase) -> dict:
    clients, ids = clients_and_ids
    out = {}
    for name, c in clients.items():
        r = c.request(case.method, case.path, json=case.json, headers=KEY)
        body = r.json()
        if r.status_code == 200:
            body = [{**m, "pool_question_id": ids[name][m["pool_question_id"]]} for m in body]
        out[name] = (r.status_code, body)
    return out


def assert_same(clients_and_ids, name: str, body: dict, expect: list[str] | None, status: int = 200) -> list:
    case = ParityCase(name, "POST", URL, json=body)
    res = run(clients_and_ids, case)
    (s0, b0), (s1, b1) = res["postgres"], res["dynamodb"]
    assert s0 == s1 == status, (name, s0, s1, b0, b1)
    assert diff(b0, b1) == [], name
    if expect is not None:
        assert [m["pool_question_id"] for m in b1] == expect, name
    return b1


def req(student=STUDENT_A, **over) -> dict:
    return {"student_id": student, "style": "AIME", "question_types": ["MCQ"], "difficulty_band": "medium", "topic": TOPIC,
            "concept_slugs": [], "limit": 20, **over}


def test_topic_requests_match_across_backends(clients):
    out = assert_same(clients, "topic", req(), ["b", "a"])                        # equal similarity: least served first
    assert [m["topic_similarity"] for m in out] == [pytest.approx(1.0)] * 2 and set(out[0]) == {
        "pool_question_id", "question_type", "question", "topic_similarity"}
    assert_same(clients, "topic + concept", req(concept_slugs=["trees"]), ["b", "a", "c"])
    assert_same(clients, "concept only", req(topic=None, concept_slugs=["trees"]), ["b", "c"])
    assert_same(clients, "concept only, several", req(topic=None, concept_slugs=["graphs", "trees"]), ["b", "c", "a"])


def test_filters_and_limits_match_across_backends(clients):
    assert_same(clients, "style", req(style="HMMT", topic=None, concept_slugs=["graphs"]), ["d"])
    assert_same(clients, "band", req(difficulty_band="easy", topic=None, concept_slugs=["graphs"]), ["e"])
    assert_same(clients, "null band", req(difficulty_band=None, topic=None, concept_slugs=["graphs"]), ["g"])
    assert_same(clients, "types", req(question_types=["PROOF"], topic=None, concept_slugs=["graphs"]), ["f"])
    assert_same(clients, "all types", req(question_types=[], topic=None, concept_slugs=["trees"]), ["b", "c"])
    assert_same(clients, "limit", req(limit=1), ["b"])
    assert_same(clients, "nothing to match on", req(topic="  ", concept_slugs=[]), [])
    assert_same(clients, "no such topic", req(topic="number theory of primes"), [])


def test_history_exclusion_matches_across_backends(clients):
    assert_same(clients, "served to B", req(student=STUDENT_B), ["a"])
    assert_same(clients, "served to B, concept", req(student=STUDENT_B, topic=None, concept_slugs=["trees"]), ["c"])
    assert_same(clients, "a new learner", req(student=str(uuid.uuid4())), ["b", "a"])


def test_request_validation_is_the_routers_on_both_backends(clients):
    assert_same(clients, "unknown field", {**req(), "bogus": 1}, None, status=422)
    assert_same(clients, "limit out of range", req(limit=0), None, status=422)
