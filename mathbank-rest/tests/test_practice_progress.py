from contextlib import contextmanager
from uuid import UUID

from fastapi.testclient import TestClient

from mathbank_rest import security
from mathbank_rest.db import learner
from mathbank_rest.main import app


def test_progress_requires_auth():
    assert TestClient(app).get("/v1/learner/practice-progress").status_code == 401


def test_progress_is_scoped_and_has_no_answers(monkeypatch):
    student_id = UUID(int=42)
    row = {"kind": "technique", "slug": "geo-power", "name": "Power of a Point",
           "available": 10, "attempted": 2, "remaining": 8}
    calls = []

    def load(current):
        calls.append(current)
        return {"items": [row]}

    monkeypatch.setattr(learner, "get_practice_progress", load)
    app.dependency_overrides[security.get_current_student_id] = lambda: student_id
    try:
        response = TestClient(app).get("/v1/learner/practice-progress")
        assert response.status_code == 200
        assert response.json() == {"items": [row]}
        assert calls == [student_id]
    finally:
        app.dependency_overrides.pop(security.get_current_student_id, None)


def test_progress_query_counts_distinct_full_history_and_shared_evidence(monkeypatch):
    statements = []

    class Result:
        def mappings(self):
            return []

    class Connection:
        def execute(self, query, params):
            statements.append((str(query), params))
            return Result()

    class Engine:
        @contextmanager
        def connect(self):
            yield Connection()

    monkeypatch.setattr(learner, "engine", Engine())
    student_id = UUID(int=42)
    assert learner.get_practice_progress(student_id) == {"items": []}
    sql, params = statements[0]
    assert params == {"student_id": str(student_id)}
    assert "SELECT DISTINCT problem_id FROM learner.attempt WHERE student_id=:student_id" in sql
    assert "count(DISTINCT p.problem_id)" in sql
    assert "s.publication_status='PUBLISHED'" in sql
    assert "st.review_status='APPROVED'" in sql
    assert "pt.review_status='REVIEWED'" in sql
    assert ":technique" not in sql
    assert "LIMIT" not in sql
    assert "is_correct" not in sql
