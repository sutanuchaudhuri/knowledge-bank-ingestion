"""WP4 gate (requirement 71): a runtime route set with ZERO PostgreSQL access.

The runtime app is built from the runtime profile; every SQLAlchemy engine reachable from ``mathbank_rest`` is replaced by
the runtime guard (``RuntimeProfileHasNoPostgres``: any use raises), the content store is ``dynamodb`` (moto) and the vector
store is S3 Vectors (in-memory exact store). Each content-read route must answer without touching Postgres: a route that
still reaches SQL surfaces as a 500 (the guard's RuntimeError) and fails this test.

Seed data come from the area tests (catalogue, learning content, theorems) so the gate and the parity tests share one corpus.
"""
from __future__ import annotations

import random
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from test_wp2_problem_search import add as add_problem_vectors
from test_wp4_catalog import seed as seed_catalog
from test_wp4_learning import seed_course, seed_keys, seed_theorems

from mathbank_rest import embeddings, profiles
from mathbank_rest.config import settings
from mathbank_rest.db.postgres import RuntimeProfileHasNoPostgres
from mathbank_rest.stores.content import catalog
from mathbank_rest.vector_catalog import DIMENSIONS
from mathbank_rest.vector_store import MemoryVectorStore, set_vector_store_for_tests

ROUTERS = ("v1", "micro_course_student", "theorems_student", "step_runtime")
ADMIN_HEADERS = {"X-Admin-Api-Key": "gate-key"}


def vec(seed: int) -> list[float]:
    r = random.Random(seed)
    return [r.uniform(-1, 1) for _ in range(DIMENSIONS)]


@pytest.fixture()
def runtime_app(content_table, monkeypatch):
    for k, v in (("content_store", "dynamodb"), ("vector_store", "s3vectors"), ("admin_api_key", "gate-key")):
        monkeypatch.setattr(settings, k, v)
    catalog._CATALOGUES.clear()
    seed_catalog()
    seed_course()
    seed_keys()
    seed_theorems()
    mem = MemoryVectorStore()
    set_vector_store_for_tests(mem)
    embeddings.reset_for_tests()
    monkeypatch.setattr(embeddings, "EMBEDDER", lambda t: vec(7))
    add_problem_vectors(mem, "AIME_2099_I_Q01", 7, comp="AIME", year=2099)

    guard, replaced = RuntimeProfileHasNoPostgres(), 0
    for name, mod in list(sys.modules.items()):
        if name.startswith("mathbank_rest") and isinstance(getattr(mod, "engine", None), Engine):
            monkeypatch.setattr(mod, "engine", guard)
            replaced += 1
    assert replaced >= 5, "the guard replaced too few engines; the gate would prove nothing"
    app = profiles.create_app("runtime", extra=ROUTERS)
    yield TestClient(app, raise_server_exceptions=False)
    set_vector_store_for_tests(None)
    embeddings.reset_for_tests()
    catalog._CATALOGUES.clear()


# (method, path, params/json, expected status). Every route here is a content read or a search over content.
ROUTES = [
    ("GET", "/v1/competitions", None, 200),
    ("GET", "/v1/problems", {"competition": "AIME", "limit": 5}, 200),
    ("GET", "/v1/problems", {"concept": "count-subset", "year_min": 2005}, 200),
    ("GET", "/v1/problems/by-code/AIME_2005_I_Q01", None, 200),
    ("GET", "/v1/problems/by-code/NOPE_0000", None, 404),
    ("GET", "/v1/problems/by-code/AMC10_2005A_Q01/diagrams", None, 200),
    ("GET", "/v1/concepts", {"limit": 10}, 200),
    ("GET", "/v1/concepts/count-subset/problems", None, 200),
    ("GET", "/v1/concepts/count-subset/neighbors", None, 200),
    ("GET", "/v1/techniques", None, 200),
    ("GET", "/v1/techniques/power-point/problems", None, 200),
    ("GET", "/v1/corpus/coverage", None, 200),
    ("GET", "/v1/micro-courses", None, 200),
    ("GET", "/v1/micro-courses/MC-1", None, 200),
    ("GET", "/v1/micro-courses/NOPE", None, 404),
    ("GET", "/v1/theorems/thm-t", None, 200),
    ("GET", "/v1/theorems/thm-t/prerequisites", None, 200),
    ("GET", "/v1/theorems/nope", None, 404),
]


@pytest.mark.parametrize(("method", "path", "params", "status"), ROUTES, ids=[f"{m} {p} {s}" for m, p, _, s in ROUTES])
def test_content_route_answers_without_touching_postgres(runtime_app, method, path, params, status):
    r = runtime_app.request(method, path, params=params)
    assert r.status_code == status, f"{method} {path}: {r.status_code} {r.text[:300]}"


def test_search_over_s3_vectors_and_content_needs_no_postgres(runtime_app):
    r = runtime_app.post("/v1/search/problems", json={"query": "inversion", "limit": 3, "retrieval": {"semantic": True, "lexical": False, "graph": False}},
                         headers=ADMIN_HEADERS)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert [x["canonical_code"] for x in body["results"]] == ["AIME_2099_I_Q01"]
    assert body["results"][0]["statement_text"] and body["retrieval"]["engine"] == "s3vectors"


def test_the_gate_would_catch_a_route_that_still_uses_sql(runtime_app, monkeypatch):
    """Negative control: with the content store on Postgres the same route reaches SQL and the guard turns it into a 500."""
    monkeypatch.setattr(settings, "content_store", "postgres")
    assert runtime_app.get("/v1/competitions").status_code == 500


def test_no_student_payload_carries_answer_keys(runtime_app):
    for path in ("/v1/micro-courses/MC-1", "/v1/theorems/thm-t", "/v1/problems/by-code/AMC10_2005A_Q01"):
        text = runtime_app.get(path).text
        assert "correct_answer" not in text and "correctness_policy" not in text, path
