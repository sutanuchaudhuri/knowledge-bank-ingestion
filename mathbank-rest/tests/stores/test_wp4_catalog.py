"""WP4 catalog area of the content store (requirement 71 WP4, requirement 70 C6 access patterns A1-A13).

moto ``mb-content-ut`` is seeded with typed items built from one logical corpus. The same corpus drives a small Python oracle
that mirrors what the Postgres functions in ``db/queries.py`` return, and each route is compared through the parity harness:
the postgres side is the real ``CatalogPostgres`` with ``db.queries`` monkeypatched to the oracle, the dynamodb side is the real
``CatalogDynamoDB`` over moto. No AWS, no Postgres.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "parity"))
from parity_harness import ParityCase, assert_parity

from mathbank_rest import stores
from mathbank_rest.config import settings
from mathbank_rest.db import problem_images, queries
from mathbank_rest.main import app
from mathbank_rest.models.ddb.content import (
    ContentCatalogptr,
    ContentCompetition,
    ContentConcept,
    ContentImage,
    ContentProblem,
    ContentProblemKey,
    ContentPtag,
    ContentSolution,
    ContentStats,
    ContentTechnique,
)
from mathbank_rest.routers import step_runtime
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import typed
from mathbank_rest.stores.content import (
    DynamoDBContentStore,
    PostgresContentStore,
    catalog,
)
from mathbank_rest.stores.errors import StoreUnavailable

NS = uuid.UUID("11111111-2222-3333-4444-555555555555")
NOW = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
SHA = "c" * 64


def uid(name: str) -> str:
    return str(uuid.uuid5(NS, name))


# ---------------------------------------------------------------------------------------------------- logical corpus

COMPS = {"AIME": ("AIME", "L2"), "AMC10": ("AMC 10", "L1"), "USAMO": ("USAMO", "L3")}


@dataclass
class P:
    code: str
    comp: str
    year: int
    paper: str
    num: int
    answer: str | None
    concepts: list = field(default_factory=list)     # (slug, role, confidence)
    techniques: list = field(default_factory=list)   # (slug, role, confidence)
    withdrawn: bool = False
    images: list = field(default_factory=list)       # (ordinal, source, local_path)
    solutions: list = field(default_factory=list)    # (kind, revision, body)
    statement: str = ""

    @property
    def comp_name(self) -> str:
        return COMPS[self.comp][0]


PROBLEMS = [
    P("AIME_2005_I_Q01", "AIME", 2005, "I", 1, "123", [("count-subset", "PRIMARY", 0.9)], [("power-point", "PRIMARY", 0.8)]),
    P("AIME_2005_I_Q02", "AIME", 2005, "I", 2, "45", [("count-perm", "PRIMARY", 0.7), ("count-subset", "SECONDARY", 0.95)]),
    P("AIME_2005_II_Q01", "AIME", 2005, "II", 1, "7", [("geometry-basic", "PRIMARY", 0.6)], [("power-point", "STEP_SUPPORTED", 0.9)]),
    P("AIME_2006_I_Q01", "AIME", 2006, "I", 1, "88", [("count", "SECONDARY", 0.5), ("loop-b", "PRIMARY", 0.3)]),
    P("AMC10_2005A_Q01", "AMC10", 2005, "A", 1, "B",
      [("count-subset-pie", "PRIMARY", 0.85), ("count-subset", "SECONDARY", 0.99)], [("similar-triangles", "PRIMARY", 0.7)],
      images=[(1, "PDF_QUESTION_FIGURE", "a/q1-fig1.png"), (2, "AOPS_PROBLEM_DIAGRAM", "a/q1-fig2.png")],
      solutions=[("TEXTBOOK", 1, "Textbook solution."), ("AOPS_COMMUNITY", 2, "Community solution.")]),
    P("AMC10_2005A_Q02", "AMC10", 2005, "A", 2, "C", [("count-subset", "SECONDARY", 0.4), ("count-perm", "SECONDARY", 0.6)]),
    P("AMC10_2005B_Q01", "AMC10", 2005, "B", 1, "D", [("geometry-basic", "PRIMARY", 0.9)], [("power-point", "PRIMARY", 0.5)]),
    P("AMC10_2006A_Q01", "AMC10", 2006, "A", 1, None, [("count-perm", "PRIMARY", 0.4)]),
    P("AMC10_2006A_Q02", "AMC10", 2006, "A", 2, "E", [("count-perm", "PRIMARY", 0.8)]),
    P("AMC10_2006A_Q03", "AMC10", 2006, "A", 3, "A", [("count-perm", "PRIMARY", 0.8)], withdrawn=True),
    P("USAMO_2005_P_Q01", "USAMO", 2005, "P", 1, "1", [("geometry-basic", "PRIMARY", 0.5)]),
]
LIVE = [p for p in PROBLEMS if not p.withdrawn]
REJECTED_TAG = ("AMC10_2005B_Q01", "count")   # stored but REJECTED: must never be served

# slug -> (name, level, aliases, description)
CONCEPTS = {
    "count": ("Counting", 1, ["combinatorics"], "Counting arguments."),
    "count-subset": ("Subset counting", 2, [], "Counting subsets."),
    "count-subset-pie": ("Inclusion-exclusion", 3, ["pie"], "PIE."),
    "count-perm": ("Permutations", 2, [], "Orderings."),
    "geometry-basic": ("Basic geometry", None, ["planar"], "Plane geometry."),
    "loop-a": ("Loop A", 4, [], "Cycle."),
    "loop-b": ("Loop B", 4, [], "Cycle."),
}
RELATIONS = [  # (from, to, type, strength)
    ("count", "count-subset", "HAS_SUBCONCEPT", 0.9), ("count", "count-perm", "HAS_SUBCONCEPT", 0.8),
    ("count-subset", "count-subset-pie", "HAS_SUBCONCEPT", 0.7), ("count-perm", "count-subset-pie", "PREREQUISITE_OF", 0.5),
    ("count-perm", "geometry-basic", "RELATED_CONCEPT", 0.2),
    ("loop-a", "loop-b", "HAS_SUBCONCEPT", 0.4), ("loop-b", "loop-a", "HAS_SUBCONCEPT", 0.4),
]
TECHNIQUES = {  # slug -> (name, description, aliases)
    "power-point": ("Power of a point", "Chord products.", ["pop"]),
    "similar-triangles": ("Similar triangles", "AA similarity.", []),
    "inversion": ("Inversion", "Circle inversion.", ["circle inversion"]),
}
COVERAGE = [
    {"competition": "AIME", "papers": 3, "problems": 4, "problems_with_concept": 4, "problems_with_technique": 2},
    {"competition": "AMC 10", "papers": 4, "problems": 5, "problems_with_concept": 5, "problems_with_technique": 2},
]
PNG = b"\x89PNG-fixture"
def IMAGE_VERSION(source: str, path: str) -> str:
    return hashlib.sha256(f"{source}:{path}".encode()).hexdigest()[:12]


def image_id(code: str, ordinal: int) -> str:
    return uid(f"image:{code}:{ordinal}")


# ---------------------------------------------------------------------------------------------------- seeding

def pid(code: str) -> str:
    return uid(f"problem:{code}")


def _problem_item(p: P) -> ContentProblem:
    cid, comp = uid(f"comp:{p.comp}"), COMPS[p.comp]
    return ContentProblem.model_validate({
        "PK": f"PROBLEM#{p.code}", "SK": "META", "type": "PROBLEM", "GSI1PK": f"PID#{pid(p.code)}", "GSI1SK": "META",
        "GSI2PK": f"PLIST#{p.comp}", "GSI2SK": f"{p.year:04d}#{p.paper}#{p.num:06d}",
        "canonical_code": p.code, "problem_id": pid(p.code), "problem_number": p.num, "year": p.year, "paper_code": p.paper,
        "paper_id": uid(f"paper:{p.comp}:{p.year}:{p.paper}"), "statement_text": p.statement or f"Statement of {p.code}.",
        "source_url": f"https://example.org/{p.code}", "difficulty_band": "EASY", "classification_status": "FINE_CONCEPT_MAPPED",
        "competition": {"competition_id": cid, "external_code": p.comp, "level": comp[1], "name": comp[0]},
        "concepts": [{"concept_id": uid(f"concept:{s}"), "slug": s, "name": CONCEPTS[s][0], "role": r, "confidence": c}
                     for s, r, c in sorted(p.concepts, key=lambda t: (t[0], t[1]))],
        "techniques": [{"technique_id": uid(f"technique:{s}"), "slug": s, "name": TECHNIQUES[s][0], "role": r, "confidence": c}
                       for s, r, c in sorted(p.techniques, key=lambda t: (t[0], t[1])) if r != "STEP_SUPPORTED"],
        "images": [{"problem_image_id": image_id(p.code, o), "ordinal": o, "source": s, "version": IMAGE_VERSION(s, path)}
                   for o, s, path in p.images],
        "content_sha256": SHA, "src_rev": 1, "created_at": NOW, "updated_at": NOW,
        "visibility": "WITHDRAWN" if p.withdrawn else "ACTIVE"})


def _tag(p: P, kind: str, slug: str, role: str, conf: float, *, status: str = "REVIEWED") -> ContentPtag:
    entity = uid(f"{'concept' if kind == 'CONCEPT' else 'technique'}:{slug}")
    base = {"PK": f"PROBLEM#{p.code}", "SK": f"TAG#{kind}#{entity}", "type": "PTAG", "GSI1PK": f"{'CONCEPT' if kind == 'CONCEPT' else 'TECHNIQUE'}#{entity}",
            "GSI1SK": f"{p.year:04d}#{p.num:06d}#{p.code}", "competition_name": p.comp_name, "confidence": conf, "content_sha256": SHA,
            "problem_code": p.code, "problem_id": pid(p.code), "problem_number": p.num, "review_status": status, "role": role,
            "slug": slug, "source_roles": [role], "src_rev": 1, "tag_kind": kind, "year": p.year}
    return ContentPtag.model_validate({**base, ("concept_id" if kind == "CONCEPT" else "technique_id"): entity})


def _rel(attr_slug: str, to: str, kind: str, strength: float) -> dict:
    return {"concept_id": uid(f"concept:{to}"), "name": CONCEPTS[to][0], "relation_id": uid(f"rel:{attr_slug}:{to}:{kind}"),
            "relation_type": kind, "review_status": "REVIEWED", "slug": to, "strength": strength}


def _concept_item(slug: str) -> ContentConcept:
    name, level, aliases, description = CONCEPTS[slug]
    out = sorted(((b, t, s) for a, b, t, s in RELATIONS if a == slug), key=lambda r: (r[1], r[0]))
    inc = sorted(((a, t, s) for a, b, t, s in RELATIONS if b == slug), key=lambda r: (r[1], r[0]))
    return ContentConcept.model_validate({
        "PK": f"CONCEPT#{uid(f'concept:{slug}')}", "SK": "META", "type": "CONCEPT", "GSI1PK": f"SLUG#CONCEPT#{slug}", "GSI1SK": "META",
        "aliases": aliases, "concept_id": uid(f"concept:{slug}"), "content_sha256": SHA, "description": description, "name": name,
        "relations_in": [_rel(slug, a, t, s) for a, t, s in inc], "relations_out": [_rel(slug, b, t, s) for b, t, s in out],
        "slug": slug, "src_rev": 1, "status": "ACTIVE", **({"level": level} if level is not None else {})})


def _technique_item(slug: str) -> ContentTechnique:
    name, description, aliases = TECHNIQUES[slug]
    return ContentTechnique.model_validate({
        "PK": f"TECHNIQUE#{uid(f'technique:{slug}')}", "SK": "META", "type": "TECHNIQUE", "GSI1PK": f"SLUG#TECHNIQUE#{slug}",
        "GSI1SK": "META", "aliases": aliases, "content_sha256": SHA, "description": description, "name": name, "slug": slug,
        "src_rev": 1, "status": "ACTIVE", "technique_id": uid(f"technique:{slug}")})


def _snapshot(kind: str, items: list[dict]) -> None:
    body = json.dumps({"schema": f"catalog/{kind}/v1", "kind": kind, "items": items}, sort_keys=True, separators=(",", ":")).encode()
    sha = hashlib.sha256(body).hexdigest()
    key = f"catalog/{kind}/{sha}.json"
    toolkit.client("s3").put_object(Bucket=toolkit.content_bucket(), Key=key, Body=body)
    typed.put(ContentCatalogptr.model_validate({
        "PK": f"CATALOG#{kind.upper()}", "SK": "SNAPSHOT", "type": "CATALOGPTR", "content_sha256": SHA, "count": len(items), "kind": kind,
        "s3_key": key, "sha256": sha, "src_rev": 1}))


def seed() -> None:
    for code, (name, level) in COMPS.items():
        typed.put(ContentCompetition.model_validate({
            "PK": "CATALOG#COMPETITION", "SK": f"COMP#{name}#{uid(f'comp:{code}')}", "type": "COMPETITION", "competition_id": uid(f"comp:{code}"),
            "content_sha256": SHA, "external_code": code, "level": level, "name": name, "src_rev": 1}))
    for p in PROBLEMS:
        typed.put(_problem_item(p))
        if p.answer is not None:
            typed.put(ContentProblemKey.model_validate({"PK": f"PROBLEM#{p.code}", "SK": "KEY#ANSWER", "type": "PROBLEM_KEY", "content_sha256": SHA,
                                                        "problem_id": pid(p.code), "src_rev": 1, "official_answer": p.answer}))
        for kind, rev, body in p.solutions:
            sid = uid(f"solution:{p.code}:{kind}:{rev}")
            typed.put(ContentSolution.model_validate({
                "PK": f"PROBLEM#{p.code}", "SK": f"KEY#SOLUTION#{kind}#{rev:04d}#{sid}", "type": "SOLUTION", "content_sha256": SHA, "created_at": NOW,
                "problem_id": pid(p.code), "revision": rev, "solution_id": sid, "solution_kind": kind, "src_rev": 1,
                "verification_status": "UNVERIFIED", "body_markdown": body}))
        if not p.withdrawn:
            for slug, role, conf in p.concepts:
                typed.put(_tag(p, "CONCEPT", slug, role, conf))
            for slug, role, conf in p.techniques:
                typed.put(_tag(p, "TECHEV", slug, role, conf, status="STEP_SUPPORTED" if role == "STEP_SUPPORTED" else "REVIEWED"))
        for ordinal, source, path in p.images:
            iid = image_id(p.code, ordinal)
            toolkit.client("s3").put_object(Bucket=toolkit.content_bucket(), Key=f"images/{hashlib.sha256(PNG + iid.encode()).hexdigest()}",
                                            Body=PNG + iid.encode())
            body = PNG + iid.encode()
            typed.put(ContentImage.model_validate({
                "PK": f"IMAGE#{iid}", "SK": "META", "type": "IMAGE", "audience": "STUDENT", "bytes": len(body), "content_sha256": SHA,
                "image_version": IMAGE_VERSION(source, path), "mime": "image/png", "ordinal": ordinal, "problem_code": p.code,
                "problem_id": pid(p.code), "problem_image_id": iid, "s3_key": f"images/{hashlib.sha256(body).hexdigest()}",
                "sha256": hashlib.sha256(body).hexdigest(), "source": source, "src_rev": 1}))
    rejected = next(p for p in PROBLEMS if p.code == REJECTED_TAG[0])
    typed.put(_tag(rejected, "CONCEPT", REJECTED_TAG[1], "PRIMARY", 0.99, status="REJECTED"))
    for slug in CONCEPTS:
        typed.put(_concept_item(slug))
    for slug in TECHNIQUES:
        typed.put(_technique_item(slug))
    typed.put(ContentStats.model_validate({"PK": "STATS#CORPUS", "SK": "COVERAGE", "type": "STATS", "content_sha256": SHA, "src_rev": 1, "rows": COVERAGE}))
    _snapshot("concept", [
        {"aliases": CONCEPTS[s][2], "concept_id": uid(f"concept:{s}"), "description": CONCEPTS[s][3], "name": CONCEPTS[s][0],
         "relations_out": [{"concept_id": uid(f"concept:{b}"), "relation_type": t} for a, b, t, _ in RELATIONS if a == s], "slug": s,
         **({"level": CONCEPTS[s][1]} if CONCEPTS[s][1] is not None else {})} for s in sorted(CONCEPTS)])
    _snapshot("technique", [
        {"aliases": TECHNIQUES[s][2], "description": TECHNIQUES[s][1], "name": TECHNIQUES[s][0], "slug": s, "technique_id": uid(f"technique:{s}")}
        for s in sorted(TECHNIQUES)])


# ---------------------------------------------------------------------------------------------------- the Postgres oracle

def pg_competitions() -> list[dict]:
    return [{"competition_id": uid(f"comp:{c}"), "external_code": c, "name": COMPS[c][0], "level": COMPS[c][1]}
            for c in sorted(COMPS, key=lambda c: COMPS[c][0])]


def pg_list_problems(*, competition=None, year_min=None, year_max=None, concept=None, technique=None, limit=25, offset=0) -> list[dict]:
    rows = []
    for p in LIVE:
        if competition and p.comp != competition:
            continue
        if year_min is not None and p.year < year_min:
            continue
        if year_max is not None and p.year > year_max:
            continue
        if concept and not any(s == concept for s, _, _ in p.concepts):
            continue
        if technique and not any(s == technique for s, _, _ in p.techniques):
            continue
        rows.append(p)
    rows.sort(key=lambda p: (p.comp_name, p.year, p.paper, p.num, p.code))
    return [{"canonical_code": p.code, "problem_number": p.num, "official_answer": p.answer, "source_url": f"https://example.org/{p.code}",
             "paper_code": p.paper, "year": p.year, "competition": p.comp_name} for p in rows[offset:offset + limit]]


def _diagrams(p: P) -> list[dict]:
    """The real ``list_images`` formatting over the rows Postgres would return."""
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value = [
        {"problem_image_id": image_id(p.code, o), "ordinal": o, "source": s, "asset_path": path} for o, s, path in p.images]
    return problem_images.list_images(conn, p.code)


def pg_problem_by_code(code: str) -> dict | None:
    p = next((p for p in LIVE if p.code == code), None)
    if p is None:
        return None
    return {
        "canonical_code": p.code, "problem_number": p.num, "statement_text": p.statement or f"Statement of {p.code}.",
        "official_answer": p.answer, "source_url": f"https://example.org/{p.code}", "difficulty_band": "EASY",
        "classification_status": "FINE_CONCEPT_MAPPED", "paper_code": p.paper, "year": p.year, "competition": p.comp_name,
        "concepts": [{"slug": s, "name": CONCEPTS[s][0], "role": r, "confidence": c} for s, r, c in sorted(p.concepts, key=lambda t: (t[0], t[1]))],
        "techniques": [{"slug": s, "name": TECHNIQUES[s][0], "role": r, "confidence": c}
                       for s, r, c in sorted(p.techniques, key=lambda t: (t[0], t[1])) if r != "STEP_SUPPORTED"],
        "solutions": [{"solution_kind": k, "revision": rev, "body_markdown": body, "verification_status": "UNVERIFIED"}
                      for k, rev, body in sorted(p.solutions)],
        "diagrams": _diagrams(p)}


def _closure(slug: str) -> set[str]:
    seen, todo = {slug}, [slug]
    while todo:
        cur = todo.pop()
        for a, b, t, _ in RELATIONS:
            if a == cur and t == "HAS_SUBCONCEPT" and b not in seen:
                seen.add(b)
                todo.append(b)
    return seen


def pg_concept_problems(slug: str, *, limit=25, offset=0) -> list[dict]:
    if slug not in CONCEPTS:
        return []
    closure, rows = _closure(slug), []
    for p in LIVE:
        matches = [(s, r, c) for s, r, c in p.concepts if s in closure]
        if not matches:
            continue
        s, r, c = min(matches, key=lambda m: (m[1] != "PRIMARY", -m[2]))
        rows.append((p, s, r, c))
    rows.sort(key=lambda t: (t[0].year, t[0].num, t[0].code))
    return [{"canonical_code": p.code, "problem_number": p.num, "competition": p.comp_name, "year": p.year, "role": r, "confidence": c,
             "matched_concept_slug": s} for p, s, r, c in rows[offset:offset + limit]]


def pg_technique_problems(slug: str, *, limit=25, offset=0) -> list[dict]:
    rows = [(p, r, c) for p in LIVE for s, r, c in p.techniques if s == slug]
    rows.sort(key=lambda t: (t[0].year, t[0].num, t[0].code))
    return [{"canonical_code": p.code, "problem_number": p.num, "competition": p.comp_name, "year": p.year, "role": r, "confidence": c}
            for p, r, c in rows[offset:offset + limit]]


def pg_concepts(*, domain=None, limit=50, offset=0) -> list[dict]:
    rows = [(s, v) for s, v in CONCEPTS.items() if not domain or domain.lower() in v[0].lower() or any(domain.lower() in a.lower() for a in v[2])]
    rows.sort(key=lambda t: (t[1][1] is None, t[1][1] or 0, t[1][0].lower()))
    return [{"slug": s, "name": v[0], "level": v[1], "description": v[3]} for s, v in rows[offset:offset + limit]]


def pg_techniques(*, q=None, limit=50, offset=0) -> list[dict]:
    rows = [(s, v) for s, v in TECHNIQUES.items()
            if not q or q.lower() in v[0].lower() or q.lower() in s.lower() or any(q.lower() in a.lower() for a in v[2])]
    rows.sort(key=lambda t: t[1][0].lower())
    return [{"slug": s, "name": v[0], "description": v[1]} for s, v in rows[offset:offset + limit]]


def pg_neighbors(slug: str) -> list[dict]:
    out = sorted(((b, t, s) for a, b, t, s in RELATIONS if a == slug), key=lambda r: (r[1], r[0]))
    inc = sorted(((a, t, s) for a, b, t, s in RELATIONS if b == slug), key=lambda r: (r[1], r[0]))
    return ([{"slug": b, "name": CONCEPTS[b][0], "relation_type": t, "strength": s, "direction": "outgoing"} for b, t, s in out]
            + [{"slug": a, "name": CONCEPTS[a][0], "relation_type": t, "strength": s, "direction": "incoming"} for a, t, s in inc])


# ---------------------------------------------------------------------------------------------------- fixtures

class Backend:
    """A TestClient that serves each request with one content store (the flag, per request)."""

    def __init__(self, store):
        self.store, self.client = store, TestClient(app)

    def request(self, *a, **k):
        with stores.override_store("content", self.store):
            return self.client.request(*a, **k)


@pytest.fixture()
def corpus(content_table):
    catalog._CATALOGUES.clear()
    seed()
    yield
    catalog._CATALOGUES.clear()


@pytest.fixture()
def pg(monkeypatch):
    """Postgres side: ``db.queries`` replaced by the oracle; the engine used by the image/diagram routes is a mock."""
    monkeypatch.setattr(queries, "list_competitions", pg_competitions)
    monkeypatch.setattr(queries, "list_problems", pg_list_problems)
    monkeypatch.setattr(queries, "get_problem_by_code", pg_problem_by_code)
    monkeypatch.setattr(queries, "list_concepts", pg_concepts)
    monkeypatch.setattr(queries, "get_concept_problems", pg_concept_problems)
    monkeypatch.setattr(queries, "get_concept_neighbors", pg_neighbors)
    monkeypatch.setattr(queries, "list_techniques", pg_techniques)
    monkeypatch.setattr(queries, "get_technique_problems", pg_technique_problems)
    monkeypatch.setattr(queries, "corpus_coverage", lambda: COVERAGE)

    by_id = {image_id(p.code, o): (p, o, s, path) for p in LIVE for o, s, path in p.images}

    def execute(sql, params=None):
        if "SELECT i.local_path" in str(sql):
            hit = by_id.get(params["i"])
            return SimpleNamespace(scalar=lambda: f"object-store:{params['i']}" if hit else None)
        code = params["code"]
        p = next((p for p in LIVE if p.code == code), None)
        rows = [{"problem_image_id": image_id(code, o), "ordinal": o, "source": s, "asset_path": path} for o, s, path in (p.images if p else [])]
        return SimpleNamespace(mappings=lambda: rows)

    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.side_effect = execute
    monkeypatch.setattr(step_runtime, "engine", engine)
    from mathbank_rest import object_store

    monkeypatch.setattr(object_store, "read_bytes", lambda key: PNG + key.encode())


@pytest.fixture()
def clients(corpus, pg):
    return {"postgres": Backend(PostgresContentStore()), "dynamodb": Backend(DynamoDBContentStore())}


@pytest.fixture()
def store(corpus):
    return DynamoDBContentStore()


def check(clients, path, params=None, *, status=200, unordered=()):
    return assert_parity(clients, ParityCase(path, "GET", path, params=params, expect_status=status, unordered=unordered))


# ---------------------------------------------------------------------------------------------------- parity through the routes

def test_competitions_parity(clients):
    res = check(clients, "/v1/competitions")
    assert [c["name"] for c in res["dynamodb"][1]] == ["AIME", "AMC 10", "USAMO"]


@pytest.mark.parametrize("params", [
    {"limit": 200},
    {"competition": "AMC10", "limit": 200},
    {"competition": "AIME", "year_min": 2006, "limit": 200},
    {"competition": "AIME", "year_max": 2005, "limit": 200},
    {"year_min": 2005, "year_max": 2005, "limit": 200},
    {"year_min": 2006, "year_max": 2005},
    {"year_max": 2004},
    {"year_min": 2007},
    {"competition": "NOPE"},
    {"limit": 3, "offset": 0}, {"limit": 3, "offset": 2}, {"limit": 4, "offset": 8}, {"limit": 5, "offset": 50},
    {"concept": "count-subset", "limit": 200},
    {"concept": "count-subset", "limit": 1, "offset": 1},
    {"concept": "count", "limit": 200},      # exact slug (no closure): the rejected tag on AMC10_2005B_Q01 stays out
    {"concept": "geometry-basic", "competition": "AMC10"},
    {"concept": "geometry-basic", "year_min": 2005, "year_max": 2005, "limit": 200},
    {"concept": "unknown-concept"},
    {"technique": "power-point", "limit": 200},
    {"technique": "power-point", "limit": 1, "offset": 2},
    {"technique": "power-point", "competition": "AIME", "limit": 200},
    {"technique": "inversion"},
    {"concept": "geometry-basic", "technique": "power-point", "limit": 200},
    {"concept": "count-subset", "technique": "power-point", "limit": 200},
])
def test_list_problems_parity(clients, params):
    check(clients, "/v1/problems", params)


def test_list_problems_pagination_is_a_slice_of_the_full_listing(store):
    full = store.list_problems(limit=200)
    assert [r["canonical_code"] for r in full] == [r["canonical_code"] for r in pg_list_problems(limit=200)]
    for limit in (1, 2, 3, 5):
        for offset in range(len(full) + 2):
            assert store.list_problems(limit=limit, offset=offset) == full[offset:offset + limit]
    assert store.list_problems(limit=0) == []
    tagged = store.list_problems(concept="geometry-basic", limit=200)
    for offset in range(4):
        assert store.list_problems(concept="geometry-basic", limit=1, offset=offset) == tagged[offset:offset + 1]


def test_list_problems_pages_through_multi_page_queries(store, monkeypatch):
    monkeypatch.setattr(catalog, "PAGE", 2)    # every GSI query now spans several Query pages
    assert store.list_problems(limit=200) == pg_list_problems(limit=200)
    assert store.list_problems(competition="AMC10", year_min=2005, year_max=2006, limit=3, offset=1) == \
        pg_list_problems(competition="AMC10", year_min=2005, year_max=2006, limit=3, offset=1)
    assert store.list_problems(concept="count-perm", limit=200) == pg_list_problems(concept="count-perm", limit=200)
    assert store.get_concept_problems("count", limit=200) == pg_concept_problems("count", limit=200)
    assert store.get_technique_problems("power-point", limit=1, offset=1) == pg_technique_problems("power-point", limit=1, offset=1)
    assert len(store.list_competitions()) == 3


def test_problem_by_code_parity_found_and_not_found(clients):
    for p in LIVE:
        check(clients, f"/v1/problems/by-code/{p.code}")
    check(clients, "/v1/problems/by-code/NOPE", status=404)
    check(clients, "/v1/problems/by-code/AMC10_2006A_Q03", status=404)      # withdrawn: not projected
    body = check(clients, "/v1/problems/by-code/AMC10_2005A_Q01")["dynamodb"][1]
    assert [s["solution_kind"] for s in body["solutions"]] == ["AOPS_COMMUNITY", "TEXTBOOK"]
    assert [d["ordinal"] for d in body["diagrams"]] == [1, 2] and body["diagrams"][0]["url"].startswith("/v1/problem-images/")
    assert check(clients, "/v1/problems/by-code/AMC10_2006A_Q01")["dynamodb"][1]["official_answer"] is None


@pytest.mark.parametrize("params", [
    {}, {"limit": 2}, {"limit": 2, "offset": 2}, {"domain": "count"}, {"domain": "combinatorics"}, {"domain": "PLANAR"}, {"domain": "zzz"},
    {"limit": 200, "offset": 3},
])
def test_concepts_parity(clients, params):
    body = check(clients, "/v1/concepts", params)["dynamodb"][1]
    if not params:
        assert body[-1]["level"] is None and body[-1]["slug"] == "geometry-basic"      # NULLS LAST


@pytest.mark.parametrize("params", [{}, {"q": "point"}, {"q": "POP"}, {"q": "similar"}, {"q": "circle inv"}, {"limit": 1, "offset": 1}, {"q": "zzz"}])
def test_techniques_parity(clients, params):
    check(clients, "/v1/techniques", params)


@pytest.mark.parametrize("slug", ["count", "count-subset", "count-subset-pie", "count-perm", "geometry-basic", "loop-a", "loop-b", "nope"])
def test_concept_problems_and_neighbours_parity(clients, slug):
    check(clients, f"/v1/concepts/{slug}/problems", {"limit": 200})
    check(clients, f"/v1/concepts/{slug}/neighbors")
    for limit, offset in ((1, 0), (2, 1), (2, 3), (3, 99)):
        check(clients, f"/v1/concepts/{slug}/problems", {"limit": limit, "offset": offset})


def test_concept_closure_prefers_primary_then_confidence_and_orders_ties_by_code(store):
    rows = store.get_concept_problems("count", limit=200)
    by_code = {r["canonical_code"]: r for r in rows}
    assert by_code["AMC10_2005A_Q01"]["role"] == "PRIMARY" and by_code["AMC10_2005A_Q01"]["matched_concept_slug"] == "count-subset-pie"
    assert by_code["AMC10_2005A_Q02"]["matched_concept_slug"] == "count-perm"              # highest confidence among SECONDARY
    assert by_code["AIME_2005_I_Q02"]["matched_concept_slug"] == "count-perm"              # PRIMARY beats the 0.95 SECONDARY
    assert "AMC10_2005B_Q01" not in by_code                                                   # only a REJECTED tag
    assert len({r["canonical_code"] for r in rows}) == len(rows)
    keys = [(r["year"], r["problem_number"], r["canonical_code"]) for r in rows]
    assert keys == sorted(keys) and keys[0][:2] == (2005, 1) and keys[0][2] == "AIME_2005_I_Q01" and keys[1][2] == "AMC10_2005A_Q01"
    assert [r["canonical_code"] for r in store.get_concept_problems("loop-a", limit=10)] == ["AIME_2006_I_Q01"]     # cycle terminates


@pytest.mark.parametrize("slug", ["power-point", "similar-triangles", "inversion", "nope"])
def test_technique_problems_parity(clients, slug):
    check(clients, f"/v1/techniques/{slug}/problems", {"limit": 200})
    check(clients, f"/v1/techniques/{slug}/problems", {"limit": 1, "offset": 1})
    rows = check(clients, "/v1/techniques/power-point/problems")["dynamodb"][1]
    assert any(r["role"] == "STEP_SUPPORTED" for r in rows)


def test_coverage_parity(clients):
    check(clients, "/v1/corpus/coverage")


def test_diagrams_parity(clients):
    for code in ("AMC10_2005A_Q01", "AIME_2005_I_Q01", "NOPE"):
        check(clients, f"/v1/problems/by-code/{code}/diagrams")


def test_student_image_bytes_parity_and_hidden_images(clients, corpus):
    hit = image_id("AMC10_2005A_Q01", 2)
    res = {name: c.request("GET", f"/v1/problem-images/{hit}") for name, c in clients.items()}
    assert {r.status_code for r in res.values()} == {200}
    assert res["postgres"].content == res["dynamodb"].content == PNG + hit.encode()
    assert res["dynamodb"].headers["content-type"] == "image/png" and res["dynamodb"].headers["x-content-type-options"] == "nosniff"
    check(clients, f"/v1/problem-images/{uuid.uuid4()}", status=404)
    item = typed.require(ContentImage, f"IMAGE#{hit}", "META")
    typed.put(ContentImage.model_validate({**item.to_item(), "audience": "STAFF"}))
    assert clients["dynamodb"].request("GET", f"/v1/problem-images/{hit}").status_code == 404


def test_student_image_storage_failures_are_503_not_404(store):
    iid = image_id("AMC10_2005A_Q01", 1)
    toolkit.client("s3").put_object(Bucket=toolkit.content_bucket(), Key=typed.require(ContentImage, f"IMAGE#{iid}", "META").s3_key, Body=b"tampered")
    with pytest.raises(StoreUnavailable):
        store.get_student_image(iid)
    toolkit.client("s3").delete_object(Bucket=toolkit.content_bucket(), Key=typed.require(ContentImage, f"IMAGE#{iid}", "META").s3_key)
    with pytest.raises(StoreUnavailable):
        store.get_student_image(iid)


# ---------------------------------------------------------------------------------------------------- store-level behaviour

def test_problem_by_id_batch_and_tags(store):
    p = next(p for p in LIVE if p.code == "AMC10_2005A_Q01")
    assert store.get_problem_by_id(pid(p.code)) == pg_problem_by_code(p.code)
    assert store.get_problem_by_id(uid("missing")) is None
    assert store.get_problem_by_id(pid("AMC10_2006A_Q03")) is None
    got = store.get_problems_by_codes(["AIME_2005_I_Q01", "NOPE", "AMC10_2005A_Q01", "AIME_2005_I_Q01", "AMC10_2006A_Q03"])
    assert [r["canonical_code"] for r in got] == ["AIME_2005_I_Q01", "AMC10_2005A_Q01"]
    expected = {k: v for k, v in pg_problem_by_code("AIME_2005_I_Q01").items() if k not in ("official_answer", "solutions")}
    assert got[0] == expected and "official_answer" not in got[0] and "solutions" not in got[0]
    assert len(store.get_problems_by_codes([p.code for p in LIVE] * 15)) == len(LIVE)

    tags = store.get_problem_tags(code="AMC10_2005B_Q01")
    assert tags == {"concept_ids": [uuid.UUID(uid("concept:geometry-basic"))], "technique_ids": [uuid.UUID(uid("technique:power-point"))]}
    assert store.get_problem_tags(problem_id=pid("AMC10_2005B_Q01")) == tags
    assert store.get_problem_tags(code="AIME_2005_II_Q01")["technique_ids"] == [uuid.UUID(uid("technique:power-point"))]
    assert store.get_problem_tags(code="NOPE") == {"concept_ids": [], "technique_ids": []}
    assert store.get_problem_tags(problem_id=uid("missing")) == {"concept_ids": [], "technique_ids": []}
    with pytest.raises(ValueError):
        store.get_problem_tags()


def test_public_answers_flag_withholds_keys_and_solutions(store, monkeypatch):
    monkeypatch.setattr(settings, "content_public_answers", False)
    row = store.get_problem_by_code("AMC10_2005A_Q01")
    assert row["official_answer"] is None and row["solutions"] == []
    assert all(r["official_answer"] is None for r in store.list_problems(limit=200))
    assert "official_answer" not in store.get_problems_by_codes(["AMC10_2005A_Q01"])[0]


def test_offloaded_attributes_resolve_transparently(content_table, store):
    catalog._CATALOGUES.clear()
    seed()
    big = "x" * 40_000
    p = P("BIG_2020_A_Q01", "AIME", 2020, "A", 1, "9", [("count", "PRIMARY", 0.5)], solutions=[("TEXTBOOK", 1, big)], statement=big)
    typed.put(_problem_item(p))
    typed.put(ContentSolution.model_validate({
        "PK": "PROBLEM#BIG_2020_A_Q01", "SK": f"KEY#SOLUTION#TEXTBOOK#0001#{uid('big')}", "type": "SOLUTION", "content_sha256": SHA, "created_at": NOW,
        "problem_id": pid(p.code), "revision": 1, "solution_id": uid("big"), "solution_kind": "TEXTBOOK", "src_rev": 1,
        "verification_status": "UNVERIFIED", "body_markdown": big}))
    raw = toolkit.get_item("content", "PROBLEM#BIG_2020_A_Q01", "META")
    assert "statement_text" not in raw and "statement_text_ref" in raw
    row = store.get_problem_by_code("BIG_2020_A_Q01")
    assert row["statement_text"] == big and row["solutions"][0]["body_markdown"] == big


def test_catalogue_snapshot_missing_is_a_503_not_an_empty_list(content_table):
    catalog._CATALOGUES.clear()
    with pytest.raises(StoreUnavailable):
        DynamoDBContentStore().list_concepts()
    assert DynamoDBContentStore().get_corpus_coverage() == []
    assert DynamoDBContentStore().list_competitions() == []


class _Spy:
    def __init__(self, inner, calls):
        self._inner, self.calls = inner, calls

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if callable(attr) and not name.startswith("_"):
            self.calls.append(name)
        return attr


def test_dynamodb_methods_never_scan_and_never_touch_postgres(store, monkeypatch):
    from mathbank_rest.db import postgres

    class NoPostgres:
        def __getattr__(self, name):
            raise AssertionError("PostgreSQL used by the DynamoDB content store")

    for module in (postgres, queries, step_runtime):
        monkeypatch.setattr(module, "engine", NoPostgres())
    calls: list[str] = []
    real = toolkit.client
    monkeypatch.setattr(toolkit, "client", lambda service="dynamodb": _Spy(real(service), calls))
    iid = image_id("AMC10_2005A_Q01", 1)
    store.list_competitions()
    store.list_problems(limit=50)
    store.list_problems(competition="AIME", year_min=2005, year_max=2006, concept="count-subset")
    store.list_problems(technique="power-point")
    store.get_problem_by_code("AMC10_2005A_Q01")
    store.get_problem_by_id(pid("AMC10_2005A_Q01"))
    store.get_problems_by_codes(["AMC10_2005A_Q01"])
    store.list_concepts()
    store.get_concept_problems("count")
    store.get_concept_neighbors("count")
    store.list_techniques()
    store.get_technique_problems("power-point")
    store.get_problem_tags(code="AMC10_2005B_Q01")
    store.get_corpus_coverage()
    store.list_problem_diagrams("AMC10_2005A_Q01")
    store.get_student_image(iid)
    assert calls and set(calls) <= {"get_item", "query", "batch_get_item", "get_object"}, set(calls)
    assert "scan" not in calls
    ddb_source = Path(catalog.__file__).read_text().split("class CatalogDynamoDB")[1]
    assert "db.postgres" not in ddb_source and "sqlalchemy" not in ddb_source and "db import" not in ddb_source


def test_every_catalog_method_is_a_read_by_name():
    for cls in (catalog.CatalogPostgres, catalog.CatalogDynamoDB):
        names = [n for n in vars(cls) if not n.startswith("_")]
        assert names and all(n.startswith(stores.READ_PREFIXES) for n in names), names
    assert set(vars(catalog.CatalogPostgres)) - {"__module__", "__doc__", "__dict__", "__weakref__"} >= \
        {n for n in vars(catalog.CatalogDynamoDB) if not n.startswith("_")}
    frozen = stores.FrozenProxy("content", DynamoDBContentStore())
    assert callable(frozen.list_competitions) and callable(frozen.get_student_image)


def test_postgres_backend_looks_functions_up_at_call_time(monkeypatch):
    seen = []
    monkeypatch.setattr(queries, "list_competitions", lambda: seen.append("a") or [{"x": 1}])
    store = PostgresContentStore()
    assert store.list_competitions() == [{"x": 1}]
    monkeypatch.setattr(queries, "list_competitions", lambda: seen.append("b") or [])
    assert store.list_competitions() == [] and seen == ["a", "b"]
    monkeypatch.setattr(queries, "get_problem_by_code", lambda code: {"canonical_code": code, "official_answer": "1", "solutions": [], "k": 2})
    assert store.get_problems_by_codes(["X", "X"]) == [{"canonical_code": "X", "k": 2}]
    assert store.get_problem_by_code("Y")["official_answer"] == "1"
