"""Live, rollback-only tests for the theorem/axiom/lemma/corollary catalog service
(requirements/61 THM-1..9). Gated behind ROUTE_DB_TESTS=1 like the sibling
taxonomy/interaction-template tests; every test runs inside a rolled-back transaction so
nothing persists against the shared database.
"""
import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from mathbank_rest import theorem_service as svc


@pytest.fixture
def live_conn():
    if os.environ.get("ROUTE_DB_TESTS") != "1":
        pytest.skip("Opt-in rollback-only theorem integration checks")
    from mathbank_rest.db.postgres import engine

    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            yield conn
        finally:
            transaction.rollback()


def _slug(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _make_theorem(conn, *, kind="THEOREM", auto_approve=True, **overrides):
    defaults = dict(
        slug=_slug("test-theorem"), name="Test Theorem", kind=kind, field="ALGEBRA",
        statement_text="A statement.", actor="pytest",
    )
    defaults.update(overrides)
    return svc.create_theorem(conn, auto_approve=auto_approve, **defaults)


def test_create_and_get_round_trip(live_conn):
    created = _make_theorem(live_conn, auto_approve=False)
    assert created["review_status"] == "PENDING_REVIEW"

    # Not visible to a student (default include_unapproved=False) until approved.
    with pytest.raises(svc.TheoremNotFound):
        svc.get_theorem(live_conn, created["slug"])

    approved = svc.approve_theorem(live_conn, created["slug"], actor="pytest")
    assert approved["review_status"] == "APPROVED"

    fetched = svc.get_theorem(live_conn, created["slug"])
    assert fetched["name"] == created["name"]
    assert fetched["sources"] == []
    assert fetched["assets"] == []
    assert fetched["taxonomy_links"] == []


def test_duplicate_slug_is_rejected(live_conn):
    slug = _slug("test-theorem")
    _make_theorem(live_conn, slug=slug)
    with pytest.raises(svc.TheoremConflict):
        _make_theorem(live_conn, slug=slug)


def test_invalid_kind_and_field_are_rejected(live_conn):
    with pytest.raises(ValueError):
        _make_theorem(live_conn, kind="NOT_A_KIND")
    with pytest.raises(ValueError):
        _make_theorem(live_conn, field="NOT_A_FIELD")


def test_broken_latex_is_rejected(live_conn):
    with pytest.raises(ValueError, match="LaTeX validation failed"):
        _make_theorem(live_conn, statement_text="unbalanced $x^2")


def test_axiom_cannot_depend_on_anything(live_conn):
    axiom = _make_theorem(live_conn, kind="AXIOM")
    theorem = _make_theorem(live_conn)
    with pytest.raises(svc.TheoremCycle, match="AXIOM"):
        svc.add_theorem_relation(
            live_conn, from_slug=axiom["slug"], to_slug=theorem["slug"],
            relation_type="DEPENDS_ON", assertion_source="human:pytest", actor="pytest",
        )


def test_real_cycle_is_rejected(live_conn):
    a = _make_theorem(live_conn)
    b = _make_theorem(live_conn)
    svc.add_theorem_relation(
        live_conn, from_slug=a["slug"], to_slug=b["slug"],
        relation_type="DEPENDS_ON", assertion_source="human:pytest", actor="pytest",
    )
    with pytest.raises(svc.TheoremCycle):
        svc.add_theorem_relation(
            live_conn, from_slug=b["slug"], to_slug=a["slug"],
            relation_type="DEPENDS_ON", assertion_source="human:pytest", actor="pytest",
        )


def test_non_lineage_relation_types_are_exempt_from_cycle_check(live_conn):
    """GENERALIZES/SPECIAL_CASE_OF/EQUIVALENT_TO are cross-references, not prerequisite
    edges (doc 61 §4.2) — they must never be blocked by the DAG cycle check."""
    a = _make_theorem(live_conn)
    b = _make_theorem(live_conn)
    svc.add_theorem_relation(
        live_conn, from_slug=a["slug"], to_slug=b["slug"],
        relation_type="GENERALIZES", assertion_source="human:pytest", actor="pytest",
    )
    # The reverse GENERALIZES-style edge should not be rejected as a cycle either,
    # since neither direction is a lineage type.
    svc.add_theorem_relation(
        live_conn, from_slug=b["slug"], to_slug=a["slug"],
        relation_type="SPECIAL_CASE_OF", assertion_source="human:pytest", actor="pytest",
    )


def test_prerequisite_lineage_walks_through_corollaries(live_conn):
    axiom = _make_theorem(live_conn, kind="AXIOM")
    base = _make_theorem(live_conn)
    corollary = _make_theorem(live_conn, kind="COROLLARY")
    svc.add_theorem_relation(
        live_conn, from_slug=base["slug"], to_slug=axiom["slug"],
        relation_type="DEPENDS_ON", assertion_source="human:pytest", actor="pytest",
    )
    svc.add_theorem_relation(
        live_conn, from_slug=corollary["slug"], to_slug=base["slug"],
        relation_type="COROLLARY_OF", assertion_source="human:pytest", actor="pytest",
    )
    prereqs = svc.get_theorem_prerequisites(live_conn, corollary["slug"], max_depth=4)
    slugs_by_depth = {p["depth"]: p["slug"] for p in prereqs["prerequisites"]}
    assert slugs_by_depth[1] == base["slug"]
    assert slugs_by_depth[2] == axiom["slug"]


def test_source_requires_approval_before_student_sees_it(live_conn):
    theorem = _make_theorem(live_conn)
    source = svc.add_theorem_source(
        live_conn, theorem_slug=theorem["slug"], url="https://example.org/a",
        label="Example", added_by="llm:test-model", review_status="PENDING_REVIEW",
    )
    assert source["review_status"] == "PENDING_REVIEW"
    detail_as_student = svc.get_theorem(live_conn, theorem["slug"])
    assert detail_as_student["sources"] == []

    svc.approve_theorem_source(live_conn, source["theorem_source_id"], actor="pytest")
    detail_after_approval = svc.get_theorem(live_conn, theorem["slug"])
    assert len(detail_after_approval["sources"]) == 1


def test_theorem_supports_multiple_sources(live_conn):
    theorem = _make_theorem(live_conn)
    svc.add_theorem_source(
        live_conn, theorem_slug=theorem["slug"], url="https://example.org/wiki",
        label="Wikipedia", source_type="REFERENCE", added_by="human:pytest", review_status="APPROVED",
    )
    svc.add_theorem_source(
        live_conn, theorem_slug=theorem["slug"], url="https://example.org/proof",
        label="Formal proof", source_type="FORMAL_PROOF", added_by="human:pytest", review_status="APPROVED",
    )
    detail = svc.get_theorem(live_conn, theorem["slug"])
    assert {s["label"] for s in detail["sources"]} == {"Wikipedia", "Formal proof"}


def test_theorem_taxonomy_link_role_primary_and_related(live_conn):
    theorem = _make_theorem(live_conn)
    node_id = live_conn.execute(
        text("SELECT taxonomy_node_id FROM pedagogy.taxonomy_node WHERE concept_id IS NOT NULL LIMIT 1")
    ).scalar_one_or_none()
    if node_id is None:
        pytest.skip("no concept-backed taxonomy_node available in this environment")
    svc.add_theorem_taxonomy_link(live_conn, theorem_slug=theorem["slug"], taxonomy_node_id=node_id, role="PRIMARY", actor="pytest")
    listed = svc.list_theorems_for_taxonomy_node(live_conn, node_id)
    assert any(t["slug"] == theorem["slug"] and t["role"] == "PRIMARY" for t in listed["items"])


def test_technique_theorem_link_and_lookup(live_conn):
    theorem = _make_theorem(live_conn)
    technique_slug = live_conn.execute(text("SELECT slug FROM knowledge.technique LIMIT 1")).scalar_one_or_none()
    if technique_slug is None:
        pytest.skip("no technique available in this environment")
    svc.add_technique_theorem(
        live_conn, technique_slug=technique_slug, theorem_slug=theorem["slug"],
        role="JUSTIFIES", assertion_source="human:pytest", actor="pytest",
    )
    linked = svc.get_theorems_for_technique(live_conn, technique_slug)
    assert any(t["slug"] == theorem["slug"] for t in linked["items"])


def test_search_matches_statement_text(live_conn):
    theorem = _make_theorem(
        live_conn, name="Searchable Theorem", statement_text="A very distinctive phrase xyzzy123 appears here.",
    )
    results = svc.search_theorems(live_conn, "distinctive phrase xyzzy123")
    assert any(r["slug"] == theorem["slug"] for r in results["items"])


def test_search_excludes_pending_review_by_default(live_conn):
    theorem = _make_theorem(
        live_conn, auto_approve=False, name="Hidden Theorem",
        statement_text="A very distinctive phrase zyxxxqq987 appears here.",
    )
    student_results = svc.search_theorems(live_conn, "zyxxxqq987")
    assert theorem["slug"] not in {r["slug"] for r in student_results["items"]}
    admin_results = svc.search_theorems(live_conn, "zyxxxqq987", include_unapproved=True)
    assert theorem["slug"] in {r["slug"] for r in admin_results["items"]}


def test_micro_course_target_supports_theorem(live_conn):
    from mathbank_rest import micro_course_service as mcs

    theorem = _make_theorem(live_conn)
    course_id = mcs.create_course(
        live_conn, _slug("TEST-COURSE").upper(), "A course about a theorem", "pytest",
        targets=[{"target_type": "THEOREM", "target_id": theorem["theorem_id"], "role": "PRIMARY"}],
    )
    assert course_id

    row = live_conn.execute(
        text("SELECT target_type, theorem_id FROM pedagogy.micro_course_target WHERE micro_course_id = :id"),
        {"id": course_id},
    ).mappings().one()
    assert row["target_type"] == "THEOREM"
    assert str(row["theorem_id"]) == theorem["theorem_id"]
