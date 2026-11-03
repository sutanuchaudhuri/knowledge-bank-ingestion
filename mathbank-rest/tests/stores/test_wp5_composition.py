"""The composed learner store (requirement 71 WP5): area mixins must not shadow each other and both backends expose one interface.

A helper with the same name in two areas silently resolves to the first mixin in the MRO (found once: ``_load``/``_event`` in the
identity, solve and micro-course areas), so every method name - private helpers included - must belong to exactly one area.
"""
from __future__ import annotations

import collections

import pytest

from mathbank_rest.stores import learner as L

AREAS = ("Identity", "Outcomes", "Solve", "Diagnosis", "Recovery", "MicroCourse", "Routes", "Admin")
# Backend-specific building blocks other areas call while assembling their own transaction (documented seams).
DYNAMODB_ONLY = {"stage_outcome", "finish_deferred_mastery"}


@pytest.mark.parametrize("backend", ["Postgres", "DynamoDB"])
def test_no_two_areas_define_the_same_method(backend):
    owners = collections.defaultdict(list)
    for area in AREAS:
        for name in vars(getattr(L, f"{area}{backend}")):
            if not name.startswith("__"):
                owners[name].append(area)
    assert {n: o for n, o in owners.items() if len(o) > 1} == {}


def test_both_backends_expose_the_same_public_interface():
    pg = {m for m in dir(L.PostgresLearnerStore) if not m.startswith("_")}
    dd = {m for m in dir(L.DynamoDBLearnerStore) if not m.startswith("_")}
    assert pg - dd == set() and dd - pg <= DYNAMODB_ONLY


def test_public_method_names_follow_the_read_write_prefix_rule():
    """A `frozen` store serves methods starting with a READ_PREFIX and rejects the rest, so a write must not look like a read."""
    from mathbank_rest.stores import READ_PREFIXES

    writes_that_look_like_reads = [m for m in dir(L.DynamoDBLearnerStore)
                                   if not m.startswith("_") and m.startswith(READ_PREFIXES) and m.startswith(("get_or_create", "load_and_"))]
    assert writes_that_look_like_reads == []
