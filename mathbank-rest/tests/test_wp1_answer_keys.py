"""WP1 answer-key regression tests (ACT-F01, PMC-F01, PMC-F21, PRD-F14, VIS-F04 theorems).

Everything runs offline: SQL is answered by a scripted fake connection that only returns
the columns a statement actually selects, so a query that still SELECTs an answer key
shows up in the payload.
"""
from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from uuid import uuid4

from fastapi.testclient import TestClient

from mathbank_rest import micro_course_service as mcs
from mathbank_rest import route_runtime
from mathbank_rest import theorem_service as theorems
from mathbank_rest.main import app

CORRECT_ANSWER = "KEY-correct-choice-text"
SEED = "KEY-worked-solution-seed"
POLICY_EXPLANATION = "KEY-policy-explanation"
OPTION_EXPLANATION = "KEY-option-explanation"
EXPECTED_RESPONSE = "KEY-expected-response"
FORBIDDEN_KEYS = {"correctness_policy", "correct_answer", "answer_or_solution_seed", "expected_response"}
SENTINELS = (SEED, POLICY_EXPLANATION, OPTION_EXPLANATION, EXPECTED_RESPONSE)

ITEM_ANSWERED = str(uuid4())
ITEM_OPEN = str(uuid4())
ACTIVITY_ANSWERED = str(uuid4())
ACTIVITY_OPEN = str(uuid4())
STATE_ID = str(uuid4())
RELEASE_ID = str(uuid4())
ENROLLMENT_ID = str(uuid4())


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def __iter__(self):
        return iter(self.rows)

    def one_or_none(self):
        return self.rows[0] if self.rows else None

    def one(self):
        return self.rows[0]

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return list(self.rows)

    def scalar(self):
        return next(iter(self.rows[0].values())) if self.rows else None

    scalar_one = scalar
    scalar_one_or_none = scalar

    def scalars(self):
        return iter([next(iter(row.values())) for row in self.rows])


def selected(sql: str, key: str) -> bool:
    return bool(re.search(rf"(?<![\w'])(?:\w+\.)?{key}(?![\w'\-]|>|\s+AS\b)", sql))


class FakeConn:
    """Routes a statement to the first matching fragment and projects the stored rows
    onto the columns that statement selects."""

    def __init__(self, routes):
        self.routes = routes
        self.statements = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append(sql)
        for fragment, rows in self.routes:
            raw = fragment.startswith("!")
            if fragment.removeprefix("!") in sql:
                return FakeResult([row if raw else {k: v for k, v in row.items() if selected(sql, k)} for row in rows])
        return FakeResult([])


def options():
    return [
        {"label": "x = 1", "explanation": OPTION_EXPLANATION, "correct": True},
        {"label": "x = 2", "is_correct": False, "feedback": OPTION_EXPLANATION},
    ]


LEARNING_ITEMS = [
    {"learning_item_id": ITEM_ANSWERED, "question_text": "Q1?", "choices": ["a", CORRECT_ANSWER],
     "correct_answer": CORRECT_ANSWER, "answer_or_solution_seed": SEED, "explanation": SEED,
     "purpose": "CHECK", "ordinal": 0, "required": True, "sequence_position": None},
    {"learning_item_id": ITEM_OPEN, "question_text": "Q2?", "choices": ["a", CORRECT_ANSWER],
     "correct_answer": CORRECT_ANSWER, "answer_or_solution_seed": SEED, "explanation": SEED,
     "purpose": "CHECK", "ordinal": 1, "required": True, "sequence_position": None},
]
ACTIVITIES = [
    {"activity_id": ACTIVITY_ANSWERED, "activity_type": "MCQ", "prompt": "P1", "options": options(),
     "correctness_policy": {"correct_index": 0, "explanation": POLICY_EXPLANATION},
     "explanation": POLICY_EXPLANATION, "ordinal": 0, "purpose": "EXECUTION", "required": False,
     "sequence_position": None},
    {"activity_id": ACTIVITY_OPEN, "activity_type": "MCQ", "prompt": "P2", "options": options(),
     "correctness_policy": {"correct_index": 0, "explanation": POLICY_EXPLANATION},
     "explanation": POLICY_EXPLANATION, "ordinal": 1, "purpose": "EXECUTION", "required": False,
     "sequence_position": None},
]
COURSE_ROW = {
    "micro_course_id": str(uuid4()), "canonical_code": "MC-1", "title": "T", "description": "D",
    "metadata": {}, "estimated_minutes": 5, "difficulty_level": 1, "release_id": RELEASE_ID,
    "version": 1, "learning_objectives": [], "prerequisite_summary": None,
}


def reader_conn():
    return FakeConn([
        ("c.canonical_code=:code", [COURSE_ROW]),
        ("FROM pedagogy.micro_course_state s", [{
            "state_id": STATE_ID, "module_id": None, "module_key": None, "state_key": "s1", "ordinal": 0,
            "state_type": "QUIZ", "title": "S", "objective": "O", "student_instruction": "I",
            "estimated_seconds": 60, "required": True, "skippable": False}]),
        ("FROM pedagogy.micro_course_state_learning_item", LEARNING_ITEMS),
        ("FROM pedagogy.micro_course_state_activity", ACTIVITIES),
    ])


def runtime_conn():
    state_row = {
        "enrollment_id": ENROLLMENT_ID, "enrollment_status": "IN_PROGRESS", "started_at": None,
        "completed_at": None, "micro_course_id": str(uuid4()), "release_id": RELEASE_ID, "version": 1,
        "state_version": 1, "canonical_code": "MC-1", "course_title": "T", "course_description": "D",
        "estimated_minutes": 5, "state_id": STATE_ID, "state_key": "s1", "state_ordinal": 0,
        "state_type": "QUIZ", "state_title": "S", "objective": "O", "student_instruction": "I",
        "estimated_seconds": 60, "required": True, "module_id": None, "module_title": None,
        "step_count": 1, "step_number": 1,
    }
    return FakeConn([
        ("!FROM learner.micro_course_enrollment e", [state_row]),
        ("event_type='ACTIVITY_RESPONSE'", [{"activity_id": ACTIVITY_ANSWERED, "is_correct": False}]),
        ("event_type='QUIZ_RESPONSE'", [{"learning_item_id": ITEM_ANSWERED, "is_correct": True}]),
        ("FROM pedagogy.micro_course_state_learning_item", LEARNING_ITEMS),
        ("FROM pedagogy.micro_course_state_activity", ACTIVITIES),
    ])


def assert_no_answer_keys(payload):
    text = json.dumps(payload, default=str)
    stack = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            assert not FORBIDDEN_KEYS & set(node), f"answer-key field leaked: {FORBIDDEN_KEYS & set(node)}"
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return text


def test_public_reader_payload_has_no_answer_keys():
    payload = mcs._assemble_course_reader_payload(reader_conn(), dict(COURSE_ROW))

    text = assert_no_answer_keys(payload)
    for sentinel in SENTINELS:
        assert sentinel not in text
    state = payload["states"][0]
    assert [item["question_text"] for item in state["learning_items"]] == ["Q1?", "Q2?"]
    assert state["learning_items"][0]["choices"] == ["a", CORRECT_ANSWER]
    assert state["activities"][0]["prompt"] == "P1"
    assert state["activities"][0]["options"] == [{"label": "x = 1"}, {"label": "x = 2"}]


def test_reader_sql_never_selects_answer_keys_by_default():
    conn = reader_conn()
    mcs._assemble_course_reader_payload(conn, dict(COURSE_ROW))

    sql = " ".join(conn.statements)
    assert "correct_answer" not in sql
    assert "answer_or_solution_seed" not in sql
    assert "correctness_policy" not in sql


def test_get_published_course_is_learner_safe():
    payload = mcs.get_published_course(reader_conn(), "MC-1")

    text = assert_no_answer_keys(payload)
    for sentinel in (SEED, POLICY_EXPLANATION, OPTION_EXPLANATION):
        assert sentinel not in text


def test_admin_preview_keeps_answer_keys():
    payload = mcs.get_course_preview(reader_conn(), "MC-1")

    state = payload["states"][0]
    assert state["learning_items"][0]["correct_answer"] == CORRECT_ANSWER
    assert state["learning_items"][0]["answer_or_solution_seed"] == SEED
    assert state["activities"][0]["correctness_policy"]["correct_index"] == 0
    assert state["activities"][0]["options"][0]["explanation"] == OPTION_EXPLANATION


def test_runtime_payload_has_no_answer_keys_for_unanswered_items():
    payload = mcs.get_enrollment_runtime(runtime_conn(), ENROLLMENT_ID, str(uuid4()))

    assert_no_answer_keys(payload)
    state = payload["current_state"]
    items = {item["learning_item_id"]: item for item in state["learning_items"]}
    activities = {item["activity_id"]: item for item in state["activities"]}
    assert "explanation" not in items[ITEM_OPEN]
    assert "answered_correctly" not in items[ITEM_OPEN]
    assert "explanation" not in activities[ACTIVITY_OPEN]
    assert activities[ACTIVITY_OPEN]["options"] == [{"label": "x = 1"}, {"label": "x = 2"}]
    assert OPTION_EXPLANATION not in json.dumps(payload, default=str)


def test_runtime_payload_reveals_explanation_only_after_answering():
    payload = mcs.get_enrollment_runtime(runtime_conn(), ENROLLMENT_ID, str(uuid4()))

    state = payload["current_state"]
    items = {item["learning_item_id"]: item for item in state["learning_items"]}
    activities = {item["activity_id"]: item for item in state["activities"]}
    assert items[ITEM_ANSWERED]["answered_correctly"] is True
    assert items[ITEM_ANSWERED]["explanation"] == SEED
    assert activities[ACTIVITY_ANSWERED]["answered_correctly"] is False
    assert activities[ACTIVITY_ANSWERED]["explanation"] == POLICY_EXPLANATION


def test_runtime_sql_never_selects_the_answer_key():
    conn = runtime_conn()
    mcs.get_enrollment_runtime(conn, ENROLLMENT_ID, str(uuid4()))

    sql = " ".join(conn.statements)
    assert "correct_answer" not in sql
    assert not re.search(r"correctness_policy(?!->>)", sql)


def test_learner_options_strips_nested_and_plain_values():
    assert mcs._learner_options(["x = 1", {"label": "L", "meta": {"correct": True, "text": "t"}}]) == [
        "x = 1", {"label": "L", "meta": {"text": "t"}}
    ]


def test_graders_still_return_feedback_after_submission(monkeypatch):
    class GraderConn:
        def __init__(self):
            self.calls = 0

        def execute(self, statement, params=None):
            sql = str(statement)
            if "FOR UPDATE OF e, rt" in sql:
                return FakeResult([{"status": "IN_PROGRESS", "release_id": RELEASE_ID, "current_state_id": STATE_ID}])
            if "FROM pedagogy.micro_course_state_learning_item si" in sql:
                return FakeResult([{"learning_item_id": ITEM_OPEN, "choices": ["a", CORRECT_ANSWER],
                                    "correct_answer": CORRECT_ANSWER, "answer_or_solution_seed": SEED}])
            return FakeResult([])

    wrong = mcs.submit_learning_item_response(GraderConn(), ENROLLMENT_ID, str(uuid4()), ITEM_OPEN, 0)
    right = mcs.submit_learning_item_response(GraderConn(), ENROLLMENT_ID, str(uuid4()), ITEM_OPEN, 1)
    gave_up = mcs.submit_learning_item_response(
        GraderConn(), ENROLLMENT_ID, str(uuid4()), ITEM_OPEN, None, gave_up=True
    )

    assert wrong["is_correct"] is False and "correct_answer" not in wrong
    assert right["is_correct"] is True and "correct_answer" not in right
    assert gave_up["correct_answer"] == CORRECT_ANSWER and gave_up["correct_choice_index"] == 1


# ---- PRD-F14: expected_response never reaches anonymous or learner route payloads -----------------

INSTRUCTION = {
    "goal_text": "GOAL", "recognition_cue": "CUE", "student_prompt": "PROMPT",
    "prerequisite_recap": "RECAP", "reasoning_explanation": "REASON", "expected_response": EXPECTED_RESPONSE,
    "short_explanation": "SHORT", "full_explanation": "FULL",
}
RELEASE = {
    "route_release_id": uuid4(), "solution_id": uuid4(), "approach_summary": "SUMMARY",
    "verification_status": "VERIFIED", "release_version": 1,
}


class RouteConn:
    def __init__(self, attempt_step=1):
        self.attempt_step = attempt_step

    def execute(self, statement, params=None):
        sql = str(statement)
        if "FROM pedagogy.solution_step_instruction" in sql:
            if "ORDER BY step_index" in sql:
                return FakeResult([{"content": INSTRUCTION}, {"content": INSTRUCTION}])
            return FakeResult([{"content": INSTRUCTION}])
        if "route_step_hint" in sql:
            return FakeResult([{"hint_text": "HINT"}])
        if "UPDATE learner.route_attempt" in sql:
            return FakeResult([])
        if "FROM learner.route_attempt" in sql:
            return FakeResult([{
                "route_attempt_id": uuid4(), "route_release_id": RELEASE["route_release_id"],
                "version": 1, "current_step": self.attempt_step, "tutor_explained_steps": [],
            }])
        return FakeResult([])


@contextmanager
def _patched_engine(monkeypatch):
    conn = RouteConn()

    class Engine:
        @contextmanager
        def connect(self):
            yield conn

    monkeypatch.setattr(route_runtime, "engine", Engine())
    monkeypatch.setattr(route_runtime, "select_published", lambda c, code: RELEASE)
    yield conn


def _assert_no_expected_response(payload):
    text = json.dumps(payload, default=str)
    assert EXPECTED_RESPONSE not in text
    assert "expected_response" not in text


def test_anonymous_route_plan_omits_expected_response(monkeypatch):
    with _patched_engine(monkeypatch):
        payload = route_runtime.plan("P-1")

    assert payload["first_checkpoint"] == "PROMPT"
    _assert_no_expected_response(payload)


def test_anonymous_route_coaching_omits_expected_response(monkeypatch):
    with _patched_engine(monkeypatch):
        payload = route_runtime.coaching("P-1", 2)

    assert payload["return_prompt"] == "PROMPT"
    _assert_no_expected_response(payload)


def test_learner_route_attempt_views_omit_expected_response(monkeypatch):
    conn = RouteConn()
    attempt = {"route_attempt_id": uuid4(), "route_release_id": RELEASE["route_release_id"],
               "version": 1, "current_step": 1, "tutor_explained_steps": []}

    view = route_runtime.current_view(conn, attempt)
    assisted = route_runtime.assist(conn, uuid4(), attempt["route_attempt_id"], 1, 5, True)

    assert view["student_prompt"] == "PROMPT"
    _assert_no_expected_response(view)
    _assert_no_expected_response(assisted)


# ---- VIS-F04 (theorem part) -------------------------------------------------------------------------

THEOREM_ROW = {"theorem_id": str(uuid4()), "slug": "pythagoras", "name": "Pythagoras", "review_status": "APPROVED"}
ASSET_ID = str(uuid4())
ASSET_ROWS = [
    {"asset_id": ASSET_ID, "ordinal": 1, "caption": "Figure", "uri": "object-store:diagrams/secret-key.png",
     "mime_type": "image/png", "source_url": None},
    {"asset_id": str(uuid4()), "ordinal": 2, "caption": "Video", "uri": "https://youtu.be/abc",
     "mime_type": "video/youtube", "source_url": "https://youtu.be/abc"},
]


class TheoremConn:
    def __init__(self):
        self.asset_sql = None

    def execute(self, statement, params=None):
        sql = str(statement)
        if "FROM knowledge.theorem_asset ta" in sql and "a.content_hash" not in sql:
            self.asset_sql = sql
            return FakeResult(ASSET_ROWS)
        if "FROM knowledge.theorem WHERE" in sql:
            return FakeResult([dict(THEOREM_ROW)])
        return FakeResult([])


def test_public_theorem_assets_are_valid_only_and_never_expose_the_uri():
    conn = TheoremConn()

    result = theorems.get_theorem(conn, "pythagoras")

    assert "validation_status = 'VALID'" in conn.asset_sql
    assert all("uri" not in asset for asset in result["assets"])
    assert "object-store:" not in json.dumps(result, default=str)
    private, external = result["assets"]
    assert private["private_object"] is True
    assert private["content_url"] == f"/v1/theorems/pythagoras/assets/{ASSET_ID}/content"
    assert external["private_object"] is False and external["source_url"] == "https://youtu.be/abc"


def test_admin_theorem_read_keeps_the_uri_and_unfiltered_assets():
    conn = TheoremConn()

    result = theorems.get_theorem(conn, "pythagoras", include_unapproved=True)

    assert "VALID" not in conn.asset_sql
    assert result["assets"][0]["uri"] == "object-store:diagrams/secret-key.png"


def test_published_theorem_asset_requires_approved_theorem_and_valid_asset():
    captured = {}

    class Conn:
        def execute(self, statement, params=None):
            captured["sql"] = str(statement)
            return FakeResult([{"uri": "object-store:k/1.png", "mime_type": "image/png",
                                "content_hash": "h", "object_size_bytes": 3}])

    asset = theorems.get_published_theorem_asset(Conn(), "pythagoras", ASSET_ID)

    assert "review_status = 'APPROVED'" in captured["sql"]
    assert "validation_status = 'VALID'" in captured["sql"]
    assert asset["object_key"] == "k/1.png"


def test_published_theorem_asset_hidden_when_missing_or_external():
    class Missing:
        def execute(self, statement, params=None):
            return FakeResult([])

    class External:
        def execute(self, statement, params=None):
            return FakeResult([{"uri": "https://example.com/x", "mime_type": "image/png",
                                "content_hash": None, "object_size_bytes": None}])

    try:
        theorems.get_published_theorem_asset(Missing(), "s", ASSET_ID)
    except theorems.TheoremNotFound:
        pass
    else:
        raise AssertionError("expected TheoremNotFound")
    try:
        theorems.get_published_theorem_asset(External(), "s", ASSET_ID)
    except theorems.TheoremConflict:
        pass
    else:
        raise AssertionError("expected TheoremConflict")


def _stub_theorem_router(monkeypatch, asset, data):
    from mathbank_rest.routers import theorems as router

    @contextmanager
    def begin():
        yield object()

    monkeypatch.setattr(router, "engine", type("E", (), {"begin": staticmethod(begin)})())
    monkeypatch.setattr(router.theorems, "get_published_theorem_asset", lambda conn, slug, asset_id: asset)
    monkeypatch.setattr(router.object_store, "read_bytes", lambda key: data)


def test_theorem_asset_content_route_is_public_and_verifies_integrity(monkeypatch):
    data = b"png-bytes"
    asset = {"object_key": "k/1.png", "mime_type": "image/png",
             "content_hash": hashlib.sha256(data).hexdigest(), "object_size_bytes": len(data)}
    _stub_theorem_router(monkeypatch, asset, data)

    response = TestClient(app).get(f"/v1/theorems/pythagoras/assets/{ASSET_ID}/content")

    assert response.status_code == 200
    assert response.content == data
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, no-store"


def test_theorem_asset_content_route_rejects_corrupt_object(monkeypatch):
    asset = {"object_key": "k/1.png", "mime_type": "image/png",
             "content_hash": "0" * 64, "object_size_bytes": 3}
    _stub_theorem_router(monkeypatch, asset, b"abc")

    response = TestClient(app).get(f"/v1/theorems/pythagoras/assets/{ASSET_ID}/content")

    assert response.status_code == 503
