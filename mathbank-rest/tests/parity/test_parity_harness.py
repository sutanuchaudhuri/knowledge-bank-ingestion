"""The parity harness itself (requirement 71 §5)."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from parity_harness import ParityCase, assert_parity, diff, run_case


def make_app(payload, status=200):
    app = FastAPI()

    @app.get("/thing")
    def thing():
        from fastapi.responses import JSONResponse

        return JSONResponse(payload, status_code=status)

    return TestClient(app)


def clients(a, b, sa=200, sb=200):
    return {"postgres": make_app(a, sa), "dynamodb": make_app(b, sb)}


CASE = ParityCase("thing", "GET", "/thing")


def test_identical_responses_pass():
    assert_parity(clients({"id": 1, "items": [1, 2]}, {"id": 1, "items": [1, 2]}), CASE)


def test_volatile_keys_are_ignored():
    a = {"id": 1, "created_at": "2026-01-01", "request_id": "x", "next_token": "t1"}
    b = {"id": 1, "created_at": "2026-02-02", "request_id": "y", "next_token": "t2"}
    assert_parity(clients(a, b), CASE)


def test_value_difference_is_reported_with_its_path():
    with pytest.raises(AssertionError, match=r"\$\.items\[1\]\.score: 0\.5 vs 0\.6"):
        assert_parity(clients({"items": [{"score": 0.4}, {"score": 0.5}]}, {"items": [{"score": 0.4}, {"score": 0.6}]}), CASE)


def test_missing_and_extra_keys_are_reported():
    problems = diff({"a": 1, "only_pg": 2}, {"a": 1, "only_ddb": 3})
    assert any("only_pg: only in postgres" in p for p in problems) and any("only_ddb: only in dynamodb" in p for p in problems)


def test_status_difference_fails():
    with pytest.raises(AssertionError, match="status: postgres=200 dynamodb=409"):
        assert_parity(clients({}, {}, 200, 409), CASE)


def test_expected_status_is_enforced_on_both():
    assert_parity(clients({"detail": "x"}, {"detail": "x"}, 404, 404), ParityCase("nf", "GET", "/thing", expect_status=404))
    with pytest.raises(AssertionError, match="expected status 404"):
        assert_parity(clients({}, {}, 200, 200), ParityCase("nf", "GET", "/thing", expect_status=404))


def test_allowed_differences_must_be_listed_explicitly():
    a, b = {"items": [{"rank": 1}, {"rank": 2}]}, {"items": [{"rank": 3}, {"rank": 4}]}
    with pytest.raises(AssertionError):
        assert_parity(clients(a, b), CASE)
    assert_parity(clients(a, b), CASE, allowed=["$.items[*].rank"])
    with pytest.raises(AssertionError):  # an allowance for one path does not hide another
        assert_parity(clients({"x": 1, "y": 1}, {"x": 2, "y": 2}), CASE, allowed=["$.x"])


def test_unordered_lists_compare_as_sets():
    a, b = {"items": [{"id": 1}, {"id": 2}]}, {"items": [{"id": 2}, {"id": 1}]}
    with pytest.raises(AssertionError):
        assert_parity(clients(a, b), CASE)
    assert_parity(clients(a, b), ParityCase("t", "GET", "/thing", unordered=("$.items",)))


def test_list_length_difference_is_reported():
    assert diff({"items": [1, 2, 3]}, {"items": [1, 2]}) == ["$.items: length 3 vs 2"]


def test_run_case_returns_status_and_body_per_backend():
    res = run_case(clients({"a": 1}, {"a": 1}), CASE)
    assert res == {"postgres": (200, {"a": 1}), "dynamodb": (200, {"a": 1})}
