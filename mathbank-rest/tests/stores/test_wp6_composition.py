"""The composed exam store (requirement 71 WP6): area mixins must not shadow each other and both backends expose one interface.

Same rule as ``test_wp5_composition``: a method name (private helpers included, which is why the papers area prefixes its own with ``_pp_``)
that two areas define silently resolves to the first mixin of the MRO.
"""
from __future__ import annotations

import collections

import pytest

from mathbank_rest import stores
from mathbank_rest.stores import exam as E
from mathbank_rest.stores import exam as exam_store

AREAS = ("Papers", "Pool", "Admin")
# Backend-specific building blocks the papers area calls on the composed store while assembling its own transaction (documented seams).
DYNAMODB_ONLY: set[str] = set()
PAPERS_READS = {"get_paper_header", "get_quiz", "list_my_quizzes", "get_response_events", "list_generation_events", "get_review", "get_diagnosis",
                "get_paper_for_diagnosis", "get_quiz_evidence", "get_difficulty_distribution"}
PAPERS_WRITES = {"start_paper", "import_paper", "generate_quiz", "finalize_paper", "fail_paper", "save_exam_progress", "submit_response",
                 "log_response_event", "post_generation_event", "submit_exam", "write_diagnosis"}


@pytest.mark.parametrize("backend", ["Postgres", "DynamoDB"])
def test_no_two_areas_define_the_same_method(backend):
    owners = collections.defaultdict(list)
    for area in AREAS:
        for name in vars(getattr(E, f"{area}{backend}")):
            if not name.startswith("__"):
                owners[name].append(area)
    assert {n: o for n, o in owners.items() if len(o) > 1} == {}


@pytest.mark.parametrize("backend", ["Postgres", "DynamoDB"])
def test_the_papers_area_offers_exactly_the_operations_of_the_design(backend):
    area = getattr(E, f"Papers{backend}")
    public = {n for n in vars(area) if not n.startswith("_")}
    assert public == PAPERS_READS | PAPERS_WRITES


def test_both_backends_expose_the_same_public_interface():
    pg = {m for m in dir(exam_store.PostgresExamStore) if not m.startswith("_")}
    dd = {m for m in dir(exam_store.DynamoDBExamStore) if not m.startswith("_")}
    assert pg - dd == set() and dd - pg <= DYNAMODB_ONLY, (pg - dd, dd - pg)


def test_a_frozen_store_serves_reads_and_rejects_writes():
    """Reads are exactly the methods that start with a READ_PREFIXES entry (``FrozenProxy`` decides by the name)."""
    for backend in ("Postgres", "DynamoDB"):
        area = getattr(E, f"Papers{backend}")
        for name in (n for n in vars(area) if not n.startswith("_")):
            assert name.startswith(stores.READ_PREFIXES) == (name in PAPERS_READS), name


def test_the_papers_area_keeps_its_private_helpers_under_its_prefix():
    private = {n for n in vars(E.PapersDynamoDB) if n.startswith("_") and not n.startswith("__")}
    assert private and all(n.startswith("_pp_") for n in private), sorted(n for n in private if not n.startswith("_pp_"))
