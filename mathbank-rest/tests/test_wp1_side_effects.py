"""WP1: anonymous reads are side-effect free and never spend money; public aggregates are k-anonymous.

Offline: DB, OpenAI and the model client are replaced by fakes that fail the test if touched.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from mathbank_rest import pedagogy, rate_limit, route_runtime, security, solution_guidance, tutor
from mathbank_rest.config import settings
from mathbank_rest.db import hybrid_search, problem_sources, queries, step_search, vector_search
from mathbank_rest.db import learner as learner_db
from mathbank_rest.main import app
from mathbank_rest.routers import pedagogy as pedagogy_routes
from mathbank_rest.routers import step_runtime
from mathbank_rest.routers import v1 as v1_routes

client = TestClient(app)
ADMIN = {"X-Admin-Api-Key": settings.admin_api_key}
LEARNER = {"Authorization": "Bearer learner-token"}
PROBLEM = {"canonical_code": "FIXTURE", "statement_text": "Count a fixed-size subset."}
COACH_BODY = {"problem_code": "FIXTURE", "diagnosis": "concept", "student_attempt": "A subset."}


@pytest.fixture(autouse=True)
def _isolation(monkeypatch):
    rate_limit.limiter.reset()
    learner_id = uuid4()

    def learner_only(credentials):
        if credentials.credentials != "learner-token":
            raise HTTPException(401, "invalid or expired token")
        return learner_id

    monkeypatch.setattr(security, "get_current_student_id", learner_only)
    yield
    rate_limit.limiter.reset()


class ForbiddenEngine:
    """Any database access fails the test."""

    def connect(self):
        raise AssertionError("anonymous request touched the database")

    begin = connect


class RecordingConnection:
    def __init__(self, sql: list[str], rows=None, scalar=None):
        self.sql, self.rows, self.scalar = sql, rows or [], scalar

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, statement, params=None):
        text = str(statement)
        assert not text.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")), text
        self.sql.append(text)
        return FakeResult(self.rows, self.scalar)


class FakeResult:
    def __init__(self, rows, scalar):
        self._rows, self._scalar = rows, scalar

    def mappings(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar_one_or_none(self):
        return self._scalar

    def __iter__(self):
        return iter(self._rows)


class RecordingEngine:
    def __init__(self, rows=None, scalar=None):
        self.sql: list[str] = []
        self.rows, self.scalar = rows, scalar

    def connect(self):
        return RecordingConnection(self.sql, self.rows, self.scalar)

    def begin(self):
        raise AssertionError("a read must not open a write transaction")


def fail(*_a, **_k):
    raise AssertionError("paid or writing call on an anonymous request")


# ── learning-context: no enrichment from a GET ────────────────────────────────────────────────

@pytest.mark.parametrize("query", ["", "?enrich=true", "?enrich=false"])
def test_get_learning_context_never_enriches_or_writes(monkeypatch, query):
    from mathbank_rest import enrichment

    monkeypatch.setattr(pedagogy_routes, "ensure_learning_metadata", fail)
    monkeypatch.setattr(enrichment, "enrich_problem", fail)
    engine = RecordingEngine(scalar="FAILED")
    monkeypatch.setattr(enrichment, "engine", engine)
    monkeypatch.setattr(
        pedagogy, "learning_context", lambda code: {"problem": PROBLEM, "metadata_status": "unenriched"}
    )
    response = client.get(f"/v1/tutor/learning-context/FIXTURE{query}")
    assert response.status_code == 200
    assert response.json()["enrichment_status"] == "failed"
    assert all(s.lstrip().upper().startswith("SELECT") for s in engine.sql)


def test_enriched_problem_reports_enriched_without_a_job_lookup(monkeypatch):
    monkeypatch.setattr(pedagogy_routes, "enrichment_status", fail)
    monkeypatch.setattr(
        pedagogy, "learning_context", lambda code: {"problem": PROBLEM, "metadata_status": "reviewed"}
    )
    assert client.get("/v1/tutor/learning-context/FIXTURE").json()["enrichment_status"] == "enriched"


def test_enrichment_status_defaults_to_not_enriched(monkeypatch):
    from mathbank_rest import enrichment

    monkeypatch.setattr(enrichment, "engine", RecordingEngine(scalar=None))
    assert enrichment.enrichment_status("FIXTURE") == "not_enriched"


def test_enrich_requires_sign_in_and_is_rate_limited(monkeypatch):
    calls = []
    monkeypatch.setattr(
        pedagogy_routes, "ensure_learning_metadata", lambda code: calls.append(code) or {"status": "done"}
    )
    monkeypatch.setattr(pedagogy_routes, "enrichment_status", lambda code: "completed")
    url = "/v1/tutor/learning-context/FIXTURE/enrich"
    anonymous = client.post(url)
    assert anonymous.status_code == 401 and calls == []
    assert client.post(url, headers={"Authorization": "Bearer nope"}).status_code == 401
    for headers in (LEARNER, ADMIN):
        response = client.post(url, headers=headers)
        assert response.status_code == 200
        assert response.json() == {
            "problem_code": "FIXTURE", "enrichment": {"status": "done"}, "enrichment_status": "completed"
        }
    assert calls == ["FIXTURE", "FIXTURE"]
    monkeypatch.setattr(settings, "search_rate_limit_per_minute", 1)
    rate_limit.limiter.reset()
    assert client.post(url, headers=LEARNER).status_code == 200
    limited = client.post(url, headers=LEARNER)
    assert limited.status_code == 429 and int(limited.headers["Retry-After"]) >= 1


# ── coach and the other paid tutor endpoints ─────────────────────────────────────────────────

def test_anonymous_coach_serves_published_hint_without_enrichment_or_model(monkeypatch):
    stored = {"problem_code": "FIXTURE", "hint": "Start by counting.", "provenance": {"review_status": "REVIEWED"}}
    monkeypatch.setattr(pedagogy_routes, "ensure_learning_metadata", fail)
    monkeypatch.setattr(pedagogy, "coach", fail)
    monkeypatch.setattr(route_runtime, "coaching", lambda code, level: stored)
    response = client.post("/v1/tutor/coach", json=COACH_BODY)
    assert response.status_code == 200 and response.json() == stored


def test_anonymous_coach_without_published_hint_is_401_and_makes_no_model_call(monkeypatch):
    monkeypatch.setattr(pedagogy_routes, "ensure_learning_metadata", fail)
    monkeypatch.setattr(pedagogy, "coach", fail)
    monkeypatch.setattr(tutor, "_client", None)
    monkeypatch.setattr(route_runtime, "coaching", lambda code, level: None)
    response = client.post("/v1/tutor/coach", json=COACH_BODY)
    assert response.status_code == 401 and "WWW-Authenticate" in response.headers


def test_signed_in_coach_generates_but_never_enriches(monkeypatch):
    generated = []
    monkeypatch.setattr(pedagogy_routes, "ensure_learning_metadata", fail)
    monkeypatch.setattr(pedagogy, "coach", lambda body: generated.append(body.problem_code) or {"hint": "h"})
    assert client.post("/v1/tutor/coach", json=COACH_BODY, headers=LEARNER).json() == {"hint": "h"}
    assert generated == ["FIXTURE"]


def test_decompose_and_check_need_sign_in(monkeypatch):
    monkeypatch.setattr(tutor, "decompose_problem", fail)
    monkeypatch.setattr(tutor, "check_subproblem_answer", fail)
    assert client.post("/v1/tutor/decompose", json={"problem_code": "X"}).status_code == 401
    body = {"subproblem_prompt": "p", "student_answer": "a"}
    assert client.post("/v1/tutor/check-subproblem", json=body).status_code == 401
    monkeypatch.setattr(tutor, "decompose_problem", lambda code, steps: {"problem_code": code, "subproblems": []})
    monkeypatch.setattr(tutor, "check_subproblem_answer", lambda p, a: {"correct": True, "feedback": "ok"})
    assert client.post("/v1/tutor/decompose", json={"problem_code": "X"}, headers=LEARNER).status_code == 200
    assert client.post("/v1/tutor/check-subproblem", json=body, headers=ADMIN).status_code == 200


def test_dynamic_guidance_fallback_needs_sign_in_but_published_plans_do_not(monkeypatch):
    seen = []
    monkeypatch.setattr(
        solution_guidance, "guidance_plan", lambda code, dynamic: seen.append(dynamic) or {"status": "ok"}
    )
    url = "/v1/tutor/guidance-plan"
    assert client.post(url, json={"problem_code": "X"}).status_code == 200
    assert client.post(url, json={"problem_code": "X", "allow_dynamic_fallback": True}).status_code == 401
    assert client.post(
        url, json={"problem_code": "X", "allow_dynamic_fallback": True}, headers=LEARNER
    ).status_code == 200
    assert seen == [False, True]


# ── search ────────────────────────────────────────────────────────────────────────────────────

class CountingEmbeddings:
    calls = 0

    def __init__(self):
        type(self).calls = 0
        self.embeddings = self

    def with_options(self, **_k):
        return self

    def create(self, **_k):
        type(self).calls += 1
        raise AssertionError("embedding provider called")


@pytest.fixture
def embedder(monkeypatch):
    fake = CountingEmbeddings()
    monkeypatch.setattr(vector_search, "_client", fake)
    return fake


def fake_vector_rows(semantic_flags: list[bool]):
    def search(query, *, semantic, **_k):
        semantic_flags.append(semantic)
        if semantic:
            vector_search.embed_query(query)
        return []

    return search


def test_anonymous_default_problem_search_is_lexical_and_makes_no_embedding_call(monkeypatch, embedder):
    flags: list[bool] = []
    monkeypatch.setattr(vector_search, "search_problems", fake_vector_rows(flags))
    body = {"query": "circles", "retrieval": {"lexical": True, "graph": False}}
    response = client.post("/v1/search/problems", json=body)
    assert response.status_code == 200
    assert flags == [False] and CountingEmbeddings.calls == 0
    assert response.json()["retrieval"]["semantic_requires_sign_in"] is True
    assert any("sign-in" in w for w in response.json()["warnings"])


def test_anonymous_explicit_semantic_is_401_without_embedding(monkeypatch, embedder):
    monkeypatch.setattr(hybrid_search, "search_problems", fail)
    body = {"query": "circles", "retrieval": {"semantic": True}}
    response = client.post("/v1/search/problems", json=body)
    assert response.status_code == 401 and CountingEmbeddings.calls == 0
    only_semantic = {"query": "circles", "retrieval": {"lexical": False, "graph": False}}
    assert client.post("/v1/search/problems", json=only_semantic).status_code == 401


def test_embedding_hook_blocks_the_provider_for_anonymous_scope(embedder):
    with rate_limit.embeddings_blocked(), pytest.raises(rate_limit.EmbeddingsNotPermitted):
        vector_search.embed_query("x")
    assert CountingEmbeddings.calls == 0


@pytest.mark.parametrize("headers", [LEARNER, ADMIN])
def test_signed_in_problem_search_is_semantic(monkeypatch, headers):
    seen = []
    monkeypatch.setattr(
        hybrid_search, "search_problems",
        lambda q, **k: seen.append(k["semantic"]) or {"results": [], "warnings": [], "retrieval": {}},
    )
    response = client.post("/v1/search/problems", json={"query": "circles"}, headers=headers)
    assert response.status_code == 200 and seen == [True]
    assert "semantic_requires_sign_in" not in response.json()["retrieval"]


def test_problem_search_rate_limit_is_per_caller_with_retry_after(monkeypatch):
    monkeypatch.setattr(settings, "search_rate_limit_per_minute", 2)
    monkeypatch.setattr(
        hybrid_search, "search_problems", lambda q, **k: {"results": [], "warnings": [], "retrieval": {}}
    )
    post = lambda headers: client.post("/v1/search/problems", json={"query": "q"}, headers=headers)
    assert [post(LEARNER).status_code for _ in range(2)] == [200, 200]
    limited = post(LEARNER)
    assert limited.status_code == 429 and int(limited.headers["Retry-After"]) >= 1
    assert post(ADMIN).status_code == 200
    anonymous_lexical = client.post(
        "/v1/search/problems", json={"query": "q", "retrieval": {"semantic": False}}
    )
    assert anonymous_lexical.status_code == 200


def test_concept_search_semantic_gating(monkeypatch):
    calls = []

    def fake(query, *, semantic, lexical, **kwargs):
        calls.append(semantic)
        return [{"taxonomy_node_id": "N"}]

    monkeypatch.setattr(step_search, "search_taxonomy_nodes", fake)
    anonymous = client.post("/v1/search/concepts", json={"query": "radical axis"})
    assert anonymous.status_code == 200 and calls == [False]
    assert anonymous.json()["retrieval"]["semantic"] == "requires_sign_in" and anonymous.json()["warnings"]
    explicit = client.post(
        "/v1/search/concepts", json={"query": "x", "retrieval": {"semantic": True, "lexical": True}}
    )
    assert explicit.status_code == 401
    assert client.post("/v1/search/concepts", json={"query": "x", "retrieval": {"lexical": False}}).status_code == 401
    signed_in = client.post("/v1/search/concepts", json={"query": "radical axis"}, headers=LEARNER)
    assert signed_in.status_code == 200 and calls == [False, True]
    assert signed_in.json()["retrieval"]["semantic"] == "queried"


def test_concept_search_is_rate_limited(monkeypatch):
    monkeypatch.setattr(settings, "search_rate_limit_per_minute", 1)
    monkeypatch.setattr(step_search, "search_taxonomy_nodes", lambda q, **k: [])
    assert client.post("/v1/search/concepts", json={"query": "x"}, headers=LEARNER).status_code == 200
    limited = client.post("/v1/search/concepts", json={"query": "x"}, headers=LEARNER)
    assert limited.status_code == 429 and "Retry-After" in limited.headers


def test_invalid_credentials_are_rejected_not_treated_as_anonymous(monkeypatch):
    monkeypatch.setattr(
        security, "require_admin_api_key", lambda *a: (_ for _ in ()).throw(HTTPException(401, "bad"))
    )
    monkeypatch.setattr(hybrid_search, "search_problems", fail)
    response = client.post(
        "/v1/search/problems", json={"query": "x"}, headers={"Authorization": "Bearer forged"}
    )
    assert response.status_code == 401


# ── token bucket ──────────────────────────────────────────────────────────────────────────────

def test_token_bucket_refills_over_time():
    now = [0.0]
    bucket = rate_limit.TokenBucketLimiter(clock=lambda: now[0])
    assert [bucket.acquire("a", 60) for _ in range(60)] == [0.0] * 60
    assert bucket.acquire("a", 60) == pytest.approx(1.0)
    assert bucket.acquire("b", 60) == 0.0
    now[0] += 2.5
    assert bucket.acquire("a", 60) == 0.0 and bucket.acquire("a", 60) == 0.0
    assert bucket.acquire("a", 60) > 0


def test_token_bucket_bounds_memory(monkeypatch):
    monkeypatch.setattr(rate_limit, "_MAX_BUCKETS", 3)
    bucket = rate_limit.TokenBucketLimiter()
    for key in "abcde":
        bucket.acquire(key, 5)
    assert len(bucket._buckets) == 3


# ── cohort k-anonymity ────────────────────────────────────────────────────────────────────────

def test_weak_concepts_enforces_the_cohort_floor_server_side(monkeypatch):
    seen = []
    monkeypatch.setattr(
        learner_db, "get_cohort_weak_concepts",
        lambda *, min_students, limit: seen.append(min_students) or [],
    )
    for asked in ("", "?min_students=1", "?min_students=3", "?min_students=25"):
        body = client.get(f"/v1/analytics/weak-concepts{asked}").json()
        assert body["suppressed"] is True and body["results"] == [] and body["note"]
    assert seen == [10, 10, 10, 25]


def test_weak_concepts_returns_rows_that_meet_the_floor(monkeypatch):
    monkeypatch.setattr(settings, "cohort_min_students", 5)
    rows = [{"slug": "count", "name": "Counting", "student_count": 7, "avg_mastery_score": 0.2, "total_attempts": 40}]
    seen = []
    monkeypatch.setattr(
        learner_db, "get_cohort_weak_concepts",
        lambda *, min_students, limit: seen.append(min_students) or rows,
    )
    body = client.get("/v1/analytics/weak-concepts?min_students=1").json()
    assert body == {"results": rows, "suppressed": False, "cohort_min_students": 5}
    assert seen == [5]
    assert v1_routes.get_weak_concepts(min_students=1, limit=20)["suppressed"] is False


# ── rejected tags are not served publicly ─────────────────────────────────────────────────────

def test_public_problem_and_concept_reads_exclude_rejected_tags(monkeypatch):
    engine = RecordingEngine(rows=[{"problem_id": 1, "canonical_code": "FIXTURE"}])
    monkeypatch.setattr(queries, "engine", engine)
    monkeypatch.setattr(queries, "list_images", lambda conn, code: [])
    queries.list_problems(concept="count")
    queries.get_concept_problems("count")
    queries.corpus_coverage()
    queries.get_problem_by_code("FIXTURE")
    assert engine.sql[0].count("review_status <> 'REJECTED'") == 1
    assert "review_status <> 'REJECTED'" in engine.sql[1]
    coverage = engine.sql[2]
    assert coverage.count("review_status <> 'REJECTED'") == 2
    concept_read = next(s for s in engine.sql if "FROM knowledge.problem_concept pc" in s and "c.slug, c.name" in s)
    assert "pc.review_status <> 'REJECTED'" in concept_read


# ── anonymous source routes keep SQL out of the router ────────────────────────────────────────

def test_source_routes_do_not_touch_the_database_directly(monkeypatch):
    monkeypatch.setattr(step_runtime, "engine", ForbiddenEngine())
    monkeypatch.setattr(step_runtime, "fetch_source_record", lambda code: {"problem": code})
    monkeypatch.setattr(step_runtime, "source_metadata", lambda record, code: {"kind": "web", "code": code})
    monkeypatch.setattr(step_runtime, "source_pdf", lambda record: None)
    assert client.get("/v1/problems/by-code/FIXTURE/source").json() == {"kind": "web", "code": "FIXTURE"}
    for suffix in ("source-pdf", "source-highlight", "source-marked-pdf"):
        assert client.get(f"/v1/problems/by-code/FIXTURE/{suffix}").status_code == 404


def test_fetch_source_record_owns_the_connection(monkeypatch):
    engine = RecordingEngine(rows=[{"source_url": "https://example.org/p.pdf"}])
    monkeypatch.setattr(problem_sources, "engine", engine)
    assert problem_sources.fetch_source_record("FIXTURE") == {"source_url": "https://example.org/p.pdf"}
    assert "pedagogy.problem_source_ref" in engine.sql[0]
    monkeypatch.setattr(problem_sources, "engine", RecordingEngine(rows=[]))
    assert problem_sources.fetch_source_record("MISSING") is None
