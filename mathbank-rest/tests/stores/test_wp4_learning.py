"""WP4 learning area of the content store on DynamoDB (requirement 71 WP4; access patterns A16-A20, A23, A31).

moto only: `content_table` seeded with items shaped like the migration spec's (`mathbank-db/aws/dynamo/specs/content.py`)
and S3 release snapshots. The reader payload is compared with what the Postgres assembler builds from the same logical
course (canned rows), and the micro-course and theorem routes run through the dual-backend parity harness.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "parity"))
from parity_harness import ParityCase, assert_parity

from mathbank_rest import micro_course_service as courses
from mathbank_rest import stores
from mathbank_rest import theorem_service as theorem_svc
from mathbank_rest.main import app
from mathbank_rest.routers import micro_courses as mc_router
from mathbank_rest.routers import theorems as thm_router
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores.content.learning import LearningDynamoDB, LearningPostgres
from mathbank_rest.stores.content.snapshots import SnapshotStore, snapshots
from mathbank_rest.stores.errors import StoreError

SHA = "a" * 64
KEY_SENTINELS = ("SENTINEL-correct-answer", "SENTINEL-seed-explanation", "SENTINEL-policy-explanation", "SENTINEL-source-expl")
FORBIDDEN_KEYS = {"correctness_policy", "correct_answer", "answer_or_solution_seed", "canonical_policy", "expected_response",
                  "correct_index", "correct_value"}


def uid(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012d}"


COURSE_ID, REL1, REL2 = uid(1), uid(2), uid(3)
STATE1, STATE2, MODULE1 = uid(10), uid(11), uid(12)
LI1, LI2, ACT1, ACT2 = "LI-prasolov-1", "LI-prasolov-2", uid(20), uid(21)
ASSET_PRIVATE, ASSET_EXTERNAL, ASSET_VIDEO, ASSET_OTHER = uid(30), uid(31), uid(32), uid(33)
INTERACTION1 = uid(40)
CONCEPT_ID, SKILL_ID = uid(50), uid(51)
NOW = "2026-10-06T00:55:03.270501Z"
UTC_NOW = dt.datetime(2026, 10, 6, 0, 55, 3, 270501, tzinfo=dt.UTC)


class DdbStore(LearningDynamoDB):
    pass


STORE = DdbStore()


def item(pk, sk, typ, gsi=None, **attrs):
    return {"PK": pk, "SK": sk, "type": typ, **(gsi or {}), **attrs, "version": 1, "src_rev": 1, "content_sha256": SHA}


def put(raw: dict) -> None:
    toolkit.put_item("content", raw)


def put_object(key: str, body: bytes) -> None:
    toolkit.client("s3").put_object(Bucket=toolkit.content_bucket(), Key=key, Body=body)


def put_snapshot(key: str, doc) -> bytes:
    body = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
    put_object(key, body)
    return body


# ------------------------------------------------------------------ the logical course

def options():
    return [{"label": "x = 1", "explanation": KEY_SENTINELS[2], "correct": True},
            {"label": "x = 2", "is_correct": False, "feedback": KEY_SENTINELS[2]}]


def learner_snapshot(release_id=REL1, version=1, title="Linear equations"):
    state1 = {
        "state_id": STATE1, "module_id": MODULE1, "module_key": "m1", "state_key": "s1", "ordinal": 0,
        "state_type": "QUIZ", "title": "First", "objective": "Solve", "student_instruction": "Read then answer",
        "estimated_seconds": 120, "required": True, "skippable": False,
        "assets": [
            {"asset_id": ASSET_PRIVATE, "asset_kind": "IMAGE", "title": "Diagram", "source_url": None, "mime_type": "image/png",
             "object_size_bytes": 12, "content_hash": SHA, "ordinal": 0, "presentation_role": "PRIMARY",
             "sequence_position": None, "private_object": True, "video_asset_id": None, "video_url": None, "duration_ms": None}],
        "qa_contexts": [{"qa_context_id": uid(60), "context_type": "FAQ", "question_pattern": "why", "approved_content": "because",
                         "concept_id": CONCEPT_ID, "technique_id": None, "skill_id": None, "misconception_id": None, "priority": 3}],
        "learning_items": [
            {"learning_item_id": LI1, "question_text": "Q1?", "choices": ["a", "b"], "transformed_form": "MCQ",
             "diagram_strategy": "NONE", "purpose": "CHECK", "ordinal": 0, "required": True, "sequence_position": None},
            {"learning_item_id": LI2, "question_text": "Q2?", "choices": ["c", "d"], "transformed_form": "MCQ",
             "diagram_strategy": "NONE", "purpose": "CHECK", "ordinal": 1, "required": False, "sequence_position": None}],
        "transcript_segments": [{"segment_id": uid(61), "video_asset_id": ASSET_VIDEO, "language_code": "en", "transcript_version": 1,
                                 "start_ms": 0, "end_ms": 900, "transcript_text": "hello", "speaker": None, "segment_index": 0}],
        "interactions": [{
            "interaction_instance_id": INTERACTION1, "canonical_code": "INT-1", "title": "Slider", "instance_config": {"a": 1},
            "initial_state": {"x": 0}, "learning_objective": "explore", "success_criteria": {"type": "x"}, "template_version": 1,
            "template_key": "slider", "interaction_family": "GRAPH", "default_layout": {"w": 1}, "allowed_controls": ["c"],
            "allowed_icons": [], "accessibility_policy": {"reduced_motion": "static"}, "scene_json": None,
            "rendered_video_asset_id": ASSET_VIDEO, "ordinal": 0, "required": False, "sequence_position": None}],
        "activities": [
            {"activity_id": ACT1, "activity_type": "MCQ", "prompt": "P1", "options": options(), "estimated_seconds": 30,
             "ordinal": 0, "purpose": "EXECUTION", "required": False, "sequence_position": None},
            {"activity_id": ACT2, "activity_type": "NUMERIC", "prompt": "P2", "options": [], "estimated_seconds": 30,
             "ordinal": 1, "purpose": "EXECUTION", "required": False, "sequence_position": None}],
        "concepts": [], "techniques": [], "skills": [], "misconceptions": [], "timeline_markers": [],
    }
    state2 = {**{k: None for k in state1}, "state_id": STATE2, "module_id": MODULE1, "module_key": "m1", "state_key": "s2",
              "ordinal": 1, "state_type": "SUMMARY", "title": "Second", "objective": "Wrap", "student_instruction": "Done",
              "estimated_seconds": 30, "required": True, "skippable": False, "assets": [], "qa_contexts": [],
              "learning_items": [], "transcript_segments": [], "interactions": [], "activities": []}
    return {
        "schema": "micro-course-release/learner/v1",
        "course": {"micro_course_id": COURSE_ID, "canonical_code": "MC-1", "title": title, "description": "Intro",
                   "estimated_minutes": 15, "difficulty_level": 2, "metadata": {"collection": "core"}},
        "release": {"release_id": release_id, "version": version, "parent_release_id": None, "learning_objectives": ["solve"],
                    "prerequisite_summary": None, "published_at": NOW, "source_content_hash": SHA},
        "targets": [
            {"target_type": "CONCEPT", "role": "PRIMARY", "ordinal": 0, "concept_id": CONCEPT_ID, "name": "Equation", "slug": "equation"},
            {"target_type": "SKILL", "role": "PREREQUISITE", "ordinal": 0, "skill_id": SKILL_ID, "name": "Arithmetic", "slug": "arith"}],
        "modules": [{"module_id": MODULE1, "module_key": "m1", "ordinal": 0, "title": "Mod", "objective": "obj",
                     "estimated_seconds": 150, "required": True}],
        "states": [state1, state2],
        "transitions": [{"transition_id": uid(70), "from_state_id": STATE1, "to_state_id": STATE2, "transition_type": "NEXT",
                         "condition_type": "ALWAYS", "condition_payload": {}, "priority": 0}],
        "interventions": [],
    }


def seed_course(*, current=REL1):
    """MC#MC-1 with release REL1 (and, when ``current`` is REL2, a newer REL2 with different content)."""
    rels = {REL1: learner_snapshot(REL1, 1, "Linear equations"), REL2: learner_snapshot(REL2, 2, "Linear equations v2")}
    keys = {}
    for rid, snap in rels.items():
        base = f"releases/micro-course/{rid}/{SHA}"
        body = put_snapshot(f"{base}/learner.json", snap)
        put_snapshot(f"{base}/server.json", {"schema": "micro-course-release/server/v1", "release_id": rid,
                                             "learning_item_keys": [{"learning_item_id": LI1, "correct_answer": KEY_SENTINELS[0]}]})
        keys[rid] = f"{base}/learner.json"
        put(item(f"MCREL#{rid}", "META", "MCREL", {"GSI1PK": "MCRELS#MC-1", "GSI1SK": f"{snap['release']['version']:04d}"},
                 release_id=rid, release_version=snap["release"]["version"], canonical_code="MC-1", micro_course_id=COURSE_ID,
                 status="PUBLISHED" if rid == current else "SUPERSEDED", source_content_hash=SHA, s3_learner_key=keys[rid],
                 s3_server_key=f"{base}/server.json", learner_bytes=len(body), server_bytes=10, published_at=NOW, approved_at=NOW))
    snap = rels[current]
    put(item("MC#MC-1", "META", "MC", {"GSI2PK": "CATALOG#MC", "GSI2SK": f"{snap['course']['title']}#MC-1"},
             micro_course_id=COURSE_ID, canonical_code="MC-1", title=snap["course"]["title"], description="Intro",
             estimated_minutes=15, difficulty_level=2, metadata={"collection": "core"}, status="ACTIVE", created_at=NOW,
             updated_at=NOW, current_release_id=current, current_release_version=snap["release"]["version"], current_sha256=SHA,
             current_s3_key=keys[current], current_s3_server_key=keys[current].replace("learner", "server"),
             current_published_at=NOW,
             targets=[{"target_type": "CONCEPT", "role": "PRIMARY", "ordinal": 0, "concept_id": CONCEPT_ID, "name": "Equation",
                       "slug": "equation", "skill_id": None, "technique_id": None, "theorem_id": None},
                      {"target_type": "SKILL", "role": "PREREQUISITE", "ordinal": 0, "skill_id": SKILL_ID, "name": "Arithmetic",
                       "slug": "arith", "concept_id": None, "technique_id": None, "theorem_id": None}]))
    return keys


def seed_keys():
    put(item(f"LI#{LI1}", "KEY", "LI_KEY", learning_item_id=LI1, correct_answer="b", answer_or_solution_seed=KEY_SENTINELS[1]))
    put(item(f"LI#{LI2}", "KEY", "LI_KEY", learning_item_id=LI2, correct_answer=KEY_SENTINELS[0]))
    put(item(f"ACT#{ACT1}", "META", "ACT", activity_id=ACT1, activity_type="MCQ", prompt="P1", options=["x = 1", "x = 2"],
             estimated_seconds=30, source_type="PRECOMPILED", persistence_mode="STATIC", status="ACTIVE", created_at=NOW))
    put(item(f"ACT#{ACT1}", "KEY", "ACT_KEY", activity_id=ACT1,
             correctness_policy={"schema": "activity-key/v1", "kind": "single", "answer": 0, "tolerance": None,
                                 "explanation": KEY_SENTINELS[2]},
             source_correctness_policy={"correct_index": 0, "explanation": KEY_SENTINELS[3]}))
    put(item(f"ACT#{ACT2}", "META", "ACT", activity_id=ACT2, activity_type="NUMERIC", prompt="P2", options=[],
             estimated_seconds=30, source_type="PRECOMPILED", persistence_mode="STATIC", status="ACTIVE", created_at=NOW))
    put(item(f"ACT#{ACT2}", "KEY", "ACT_KEY", activity_id=ACT2,
             correctness_policy={"schema": "activity-key/v1", "kind": "numeric", "answer": 4, "tolerance": 0, "explanation": "e"},
             source_correctness_policy={"correct_value": 4, "explanation": "e"}))


def vasset(asset_id, *, source_uri=None, external_url=None, valid=True, size=None, sha=SHA, mime="image/png"):
    attrs = {"asset_id": asset_id, "mime": mime, "sha256": sha, "kind": "IMAGE", "title": "t", "source_url": "https://src",
             "rights_note": "ok", "persistence_mode": "PRIVATE", "validation_status": "VALID" if valid else "INVALID",
             "private_object": bool(source_uri)}
    if external_url:
        attrs["external_url"] = external_url
    if source_uri:
        attrs["source_uri"] = source_uri
    if size is not None:
        attrs["size"] = size
    return item(f"VASSET#{asset_id}", "META", "VASSET", **attrs)


@pytest.fixture()
def seeded(content_table):
    seed_course()
    seed_keys()
    return content_table


class Spy:
    """Count S3 GetObject calls on the shared client."""

    def __init__(self):
        self.gets = 0
        toolkit.client("s3").meta.events.register("before-call.s3.GetObject", self._hit)

    def _hit(self, **_kw):
        self.gets += 1


def assert_no_keys(payload):
    text = json.dumps(payload, default=str)
    for sentinel in KEY_SENTINELS:
        assert sentinel not in text
    stack = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            assert not FORBIDDEN_KEYS & set(node), FORBIDDEN_KEYS & set(node)
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)


# ------------------------------------------------------------------ Postgres assembler with canned rows

class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def __iter__(self):
        return iter(self.rows)

    def one_or_none(self):
        return self.rows[0] if self.rows else None

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return list(self.rows)


class FakeConn:
    def __init__(self, routes):
        self.routes = routes

    def execute(self, statement, params=None):
        sql = str(statement)
        for fragment, rows in self.routes:
            if fragment in sql:
                return FakeResult(rows(params or {}) if callable(rows) else rows)
        return FakeResult([])


def pg_course_conn():
    """The same logical course as ``learner_snapshot`` in the rows the Postgres assembler's statements return."""
    snap = learner_snapshot()
    s1 = snap["states"][0]
    by_state = lambda rows1, rows2=(): (lambda p: list(rows1) if p.get("id") == STATE1 else list(rows2))
    return FakeConn([
        ("c.canonical_code=:code", [{
            "micro_course_id": COURSE_ID, "canonical_code": "MC-1", "title": "Linear equations", "description": "Intro",
            "metadata": {"collection": "core"}, "estimated_minutes": 15, "difficulty_level": 2, "release_id": REL1,
            "version": 1, "learning_objectives": ["solve"], "prerequisite_summary": None}]),
        ("t.role='PRIMARY'", [{"target_type": "CONCEPT", "name": "Equation", "slug": "equation"}]),
        ("t.role='PREREQUISITE'", [{"target_type": "SKILL", "name": "Arithmetic", "slug": "arith"}]),
        ("SELECT module_id, module_key, ordinal", [{
            "module_id": MODULE1, "module_key": "m1", "ordinal": 0, "title": "Mod", "objective": "obj",
            "estimated_seconds": 150, "required": True}]),
        ("FROM pedagogy.micro_course_state s", [
            {k: st[k] for k in ("state_id", "module_id", "module_key", "state_key", "ordinal", "state_type", "title", "objective",
                                "student_instruction", "estimated_seconds", "required", "skippable")} for st in snap["states"]]),
        ("seg.segment_id", by_state([{k: s1["transcript_segments"][0][k] for k in
                                      ("segment_id", "start_ms", "end_ms", "transcript_text", "speaker", "segment_index")}])),
        ("a.validation_status='VALID'", by_state([{
            "asset_id": ASSET_PRIVATE, "uri": "object-store:abc.png", "asset_kind": "IMAGE", "title": "Diagram", "source_url": None,
            "mime_type": "image/png", "object_size_bytes": 12, "ordinal": 0, "presentation_role": "PRIMARY",
            "sequence_position": None, "video_url": None, "duration_ms": None}])),
        ("FROM pedagogy.state_qa_context", by_state([{k: s1["qa_contexts"][0][k] for k in (
            "context_type", "question_pattern", "approved_content", "concept_id", "technique_id", "skill_id", "misconception_id")}])),
        ("FROM pedagogy.micro_course_state_learning_item", by_state([
            {k: li[k] for k in ("learning_item_id", "question_text", "choices", "purpose", "ordinal", "required", "sequence_position")}
            for li in s1["learning_items"]])),
        ("FROM pedagogy.micro_course_state_interaction", by_state([{
            k: s1["interactions"][0][k] for k in (
                "interaction_instance_id", "canonical_code", "title", "instance_config", "initial_state", "learning_objective",
                "success_criteria", "template_version", "template_key", "interaction_family", "default_layout", "allowed_controls",
                "allowed_icons", "accessibility_policy", "scene_json", "rendered_video_asset_id", "ordinal", "required",
                "sequence_position")}])),
        ("FROM pedagogy.micro_course_state_activity", by_state([
            {k: a[k] for k in ("activity_id", "activity_type", "prompt", "options", "ordinal", "purpose", "required",
                               "sequence_position")} for a in s1["activities"]])),
        ("FROM pedagogy.micro_course_transition", [{k: snap["transitions"][0][k] for k in (
            "from_state_id", "to_state_id", "transition_type", "condition_type", "condition_payload", "priority")}]),
    ])


def norm(payload):
    return json.loads(json.dumps(payload, default=str))


# ------------------------------------------------------------------ A18 / A19: reader, catalogue, pinned release

def test_reader_payload_shape_equals_postgres_assembler(seeded):
    expected = courses.get_published_course(pg_course_conn(), "MC-1")
    actual = STORE.get_micro_course_reader(None, "MC-1")
    assert norm(actual) == norm(expected)
    assert list(actual) == list(expected)
    assert [list(s) for s in actual["states"]] == [list(s) for s in expected["states"]]


def test_reader_options_are_stripped_of_correctness_flags(seeded):
    payload = STORE.get_micro_course_reader(None, "MC-1")
    assert payload["states"][0]["activities"][0]["options"] == [{"label": "x = 1"}, {"label": "x = 2"}]


def test_reader_and_listings_never_carry_answer_keys(seeded):
    seed_keys()
    outputs = [
        STORE.get_micro_course_reader(None, "MC-1"), STORE.get_pinned_micro_course_reader(None, REL1),
        STORE.list_published_micro_courses(None),
    ]
    for payload in outputs:
        assert_no_keys(payload)
    assert "KEY" not in json.dumps(outputs)


def test_published_list_shape_sorted_and_paged(seeded):
    rows = STORE.list_published_micro_courses(None)
    assert rows == [{
        "canonical_code": "MC-1", "title": "Linear equations", "description": "Intro", "metadata": {"collection": "core"},
        "estimated_minutes": 15, "difficulty_level": 2, "release_id": REL1, "version": 1, "state_count": 2,
        "primary_targets": [{"target_type": "CONCEPT", "name": "Equation", "slug": "equation"}]}]
    assert list(rows[0]) == ["canonical_code", "title", "description", "metadata", "estimated_minutes", "difficulty_level",
                             "release_id", "version", "state_count", "primary_targets"]
    assert STORE.list_published_micro_courses(None, limit=1, offset=1) == []
    with pytest.raises(ValueError):
        STORE.list_published_micro_courses(None, limit=0)


def test_unpublished_or_unknown_course_is_not_found(seeded):
    put(item("MC#MC-DRAFT", "META", "MC", micro_course_id=uid(9), canonical_code="MC-DRAFT", title="Draft", description="d",
             metadata={}, targets=[], status="UNPUBLISHED", created_at=NOW, updated_at=NOW))
    for code in ("MC-DRAFT", "MC-NOPE"):
        with pytest.raises(courses.MicroCourseNotFound):
            STORE.get_micro_course_reader(None, code)
    with pytest.raises(ValueError):
        STORE.get_micro_course_reader(None, "  ")
    assert [r["canonical_code"] for r in STORE.list_published_micro_courses(None)] == ["MC-1"]


def test_pinned_release_returns_pinned_content_after_current_release_changes(seeded):
    # the current release moves to REL2; an enrollment pinned to REL1 still reads REL1
    seed_course(current=REL2)
    assert STORE.get_micro_course_reader(None, "MC-1")["title"] == "Linear equations v2"
    assert STORE.get_micro_course_reader(None, "MC-1")["release_id"] == REL2
    pinned = STORE.get_pinned_micro_course_reader(None, REL1)
    assert (pinned["title"], pinned["release_id"], pinned["version"]) == ("Linear equations", REL1, 1)
    with pytest.raises(courses.MicroCourseNotFound):
        STORE.get_pinned_micro_course_reader(None, uid(999))


def test_release_snapshot_lru_second_read_makes_no_s3_get(seeded):
    snapshots.clear()
    spy = Spy()
    STORE.get_micro_course_reader(None, "MC-1")
    assert spy.gets == 1
    STORE.get_micro_course_reader(None, "MC-1")
    STORE.get_pinned_micro_course_reader(None, REL1)
    assert spy.gets == 1


def test_returned_payload_is_a_copy_of_the_cached_snapshot(seeded):
    first = STORE.get_micro_course_reader(None, "MC-1")
    first["states"][0]["learning_items"][0]["choices"].append("MUTATED")
    assert STORE.get_micro_course_reader(None, "MC-1")["states"][0]["learning_items"][0]["choices"] == ["a", "b"]


def test_content_addressed_snapshot_checksum_mismatch_raises(content_table):
    good = b'{"items":[]}'
    sha = hashlib.sha256(good).hexdigest()
    put_object(f"catalog/widget-library/{sha}.json", b'{"items":[1]}')            # body does not match its address
    with pytest.raises(StoreError, match="checksum"):
        SnapshotStore().get_json(f"catalog/widget-library/{sha}.json")
    put_object(f"catalog/widget-library/{sha}.json", good)
    assert SnapshotStore().get_json(f"catalog/widget-library/{sha}.json") == {"items": []}


# ------------------------------------------------------------------ A16 / A17: keys, grading

def test_key_methods_read_strongly_and_only_here_keys_appear(seeded, monkeypatch):
    reads = []
    real = toolkit.get_item

    def spy(ctx, pk, sk, *, consistent=True):
        reads.append((pk, sk, consistent))
        return real(ctx, pk, sk, consistent=consistent)

    monkeypatch.setattr(toolkit, "get_item", spy)
    key = STORE.get_learning_item_key(None, LI1)
    definition = STORE.get_activity_definition(None, ACT1)
    akey = STORE.get_activity_key(None, ACT1)
    monkeypatch.setattr(toolkit, "get_item", real)
    assert key == {"learning_item_id": LI1, "correct_answer": "b", "answer_or_solution_seed": KEY_SENTINELS[1]}
    assert akey["correctness_policy"] == {"correct_index": 0, "explanation": KEY_SENTINELS[3]}
    assert akey["canonical_policy"]["kind"] == "single"
    assert definition["activity_type"] == "MCQ" and "correctness_policy" not in definition
    assert_no_keys(definition)
    assert all(consistent for *_, consistent in reads) and len(reads) == 3
    assert STORE.get_learning_item_key(None, "LI-none") is None
    assert STORE.get_activity_key(None, uid(999)) is None


def test_grading_item_membership_comes_from_the_pinned_release(seeded):
    graded = STORE.get_grading_item(None, REL1, STATE1, LI1)
    assert graded == {"learning_item_id": LI1, "choices": ["a", "b"], "correct_answer": "b",
                      "answer_or_solution_seed": KEY_SENTINELS[1]}
    assert STORE.get_grading_item(None, REL1, STATE2, LI1) is None        # not an item of that state
    assert STORE.get_grading_item(None, REL1, STATE1, "LI-other") is None
    with pytest.raises(courses.MicroCourseNotFound):
        STORE.get_grading_item(None, uid(999), STATE1, LI1)


def test_grading_activity_uses_source_policy_and_release_membership(seeded):
    graded = STORE.get_grading_activity(None, REL1, ACT1)
    assert graded == {"state_id": STATE1, "activity_type": "MCQ", "options": ["x = 1", "x = 2"],
                      "correctness_policy": {"correct_index": 0, "explanation": KEY_SENTINELS[3]}}
    assert STORE.get_grading_activity(None, REL1, uid(999)) is None
    from mathbank_rest import activity_scoring

    assert activity_scoring.score_choice_index(graded["options"], graded["correctness_policy"], 0) is True
    numeric = STORE.get_grading_activity(None, REL1, ACT2)
    assert activity_scoring.score_numeric(numeric["correctness_policy"], 4) is True


def test_grading_a_learning_item_through_the_service_uses_the_store(seeded):
    runtime = {"status": "IN_PROGRESS", "release_id": REL1, "current_state_id": STATE1}
    events = []

    class Conn:
        def execute(self, statement, params=None):
            sql = str(statement)
            if "FROM learner.micro_course_enrollment" in sql:
                return FakeResult([runtime])
            events.append(params)
            return FakeResult([])

    with stores.override_store("content", STORE):
        right = courses.submit_learning_item_response(Conn(), uid(80), uid(81), LI1, 1)
        gave_up = courses.submit_learning_item_response(Conn(), uid(80), uid(81), LI1, None, gave_up=True)
        with pytest.raises(courses.MicroCourseNotFound):
            courses.submit_learning_item_response(Conn(), uid(80), uid(81), "LI-not-here", 0)
        activity = courses.submit_activity_response(Conn(), uid(80), uid(81), ACT1, choice_index=0)
    assert right["is_correct"] is True and right["explanation"] == KEY_SENTINELS[1]
    assert gave_up["correct_answer"] == "b" and gave_up["correct_choice_index"] == 1
    assert activity["is_correct"] is True and activity["activity_id"] == ACT1


# ------------------------------------------------------------------ A20: course assets

def test_course_asset_must_be_listed_in_the_release_snapshot(seeded):
    put(vasset(ASSET_PRIVATE, source_uri="object-store:abc.png", size=12))
    put(vasset(ASSET_OTHER, source_uri="object-store:zzz.png", size=3))                  # VALID but not in this release
    assert STORE.get_course_asset(None, "MC-1", ASSET_PRIVATE) == {
        "object_key": "abc.png", "mime_type": "image/png", "content_hash": SHA, "object_size_bytes": 12}
    with pytest.raises(courses.MicroCourseNotFound):
        STORE.get_course_asset(None, "MC-1", ASSET_OTHER)


def test_course_asset_rules_match_postgres(seeded):
    put(vasset(ASSET_PRIVATE, source_uri="object-store:abc.png", size=12, valid=False))
    with pytest.raises(courses.MicroCourseNotFound):                                     # validation_status must be VALID
        STORE.get_course_asset(None, "MC-1", ASSET_PRIVATE)
    put(vasset(ASSET_PRIVATE, external_url="https://example.org/x.png"))
    with pytest.raises(courses.MicroCourseConflict):                                     # not in the private object store
        STORE.get_course_asset(None, "MC-1", ASSET_PRIVATE)
    put(vasset(ASSET_VIDEO, source_uri="object-store:vid.mp4", size=None, mime="video/mp4"))
    found = STORE.get_course_asset(None, "MC-1", ASSET_VIDEO)                            # rendered video of an approved scene
    assert found["object_key"] == "vid.mp4" and found["object_size_bytes"] is None
    with pytest.raises(courses.MicroCourseNotFound):                                     # VASSET item absent
        STORE.get_course_asset(None, "MC-NOPE", ASSET_PRIVATE)


# ------------------------------------------------------------------ A23: theorems

T_AXIOM, T_LEMMA, T_THM, T_COR = uid(100), uid(101), uid(102), uid(103)
TECH_ID, NODE_ID = uid(110), "node-geo-1"


def theorem(tid, slug, name, kind="THEOREM", assets=(), sources=()):
    return item(f"THEOREM#{tid}", "META", "THEOREM", {"GSI1PK": f"SLUG#THEOREM#{slug}", "GSI1SK": "META"},
                theorem_id=tid, slug=slug, name=name, kind=kind, field="GEOMETRY", statement_text=f"{name} statement",
                source="HUMAN", review_status="APPROVED", approval_method="human", approved_at=NOW, created_at=NOW,
                updated_at=NOW, sources=list(sources), assets=list(assets))


def rel(frm, rtype, to, to_slug, to_name):
    return item(f"THEOREM#{frm}", f"REL#{rtype}#{to}", "THEOREM_REL", relation_id=uid(900), relation_type=rtype,
                to_theorem_id=to, to_slug=to_slug, to_name=to_name, review_status="APPROVED")


def seed_theorems():
    put(theorem(T_AXIOM, "axiom-a", "Axiom A", "AXIOM"))
    put(theorem(T_LEMMA, "lemma-l", "Lemma L", "LEMMA"))
    put(theorem(T_THM, "thm-t", "Theorem T", assets=[
        {"asset_id": ASSET_PRIVATE, "mime": "image/png", "sha256": SHA, "asset_kind": "IMAGE", "ordinal": 0, "caption": "fig"},
        {"asset_id": ASSET_EXTERNAL, "mime": "image/png", "sha256": SHA, "asset_kind": "IMAGE", "ordinal": 1, "caption": "web"},
        {"asset_id": ASSET_OTHER, "mime": "image/png", "sha256": SHA, "asset_kind": "IMAGE", "ordinal": 2, "caption": "bad"}],
        sources=[{"theorem_source_id": uid(120), "url": "https://s", "label": "Ref", "source_type": "REFERENCE", "ordinal": 0}]))
    put(theorem(T_COR, "cor-c", "Corollary C", "COROLLARY"))
    put(vasset(ASSET_PRIVATE, source_uri="object-store:abc.png", size=12))
    put(vasset(ASSET_EXTERNAL, external_url="https://example.org/x.png"))
    put(vasset(ASSET_OTHER, source_uri="object-store:bad.png", size=1, valid=False))
    # Theorem T depends on Lemma L and on Axiom A; L depends on A (A is reached at depths 1 and 2); A depends back on T (cycle)
    put(rel(T_THM, "DEPENDS_ON", T_LEMMA, "lemma-l", "Lemma L"))
    put(rel(T_THM, "DEPENDS_ON", T_AXIOM, "axiom-a", "Axiom A"))
    put(rel(T_LEMMA, "DEPENDS_ON", T_AXIOM, "axiom-a", "Axiom A"))
    put(rel(T_AXIOM, "DEPENDS_ON", T_THM, "thm-t", "Theorem T"))
    put(rel(T_THM, "GENERALIZES", T_COR, "cor-c", "Corollary C"))                         # cross-reference, not lineage
    put(rel(T_COR, "COROLLARY_OF", T_THM, "thm-t", "Theorem T"))
    put(item(f"THEOREM#{T_THM}", f"LINK#TECHNIQUE#{TECH_ID}#JUSTIFIES", "THEOREM_LINK",
             {"GSI2PK": f"THMBY#TECHNIQUE#{TECH_ID}", "GSI2SK": "thm-t"}, link_kind="TECHNIQUE", theorem_id=T_THM,
             technique_id=TECH_ID, technique_slug="angle-chase", slug="thm-t", name="Theorem T", role="JUSTIFIES"))
    put(item(f"THEOREM#{T_LEMMA}", f"LINK#TECHNIQUE#{TECH_ID}#APPLIES", "THEOREM_LINK",
             {"GSI2PK": f"THMBY#TECHNIQUE#{TECH_ID}", "GSI2SK": "lemma-l"}, link_kind="TECHNIQUE", theorem_id=T_LEMMA,
             technique_id=TECH_ID, technique_slug="angle-chase", slug="lemma-l", name="Lemma L", role="APPLIES"))
    put(item(f"THEOREM#{T_THM}", f"LINK#TAXNODE#{NODE_ID}", "THEOREM_LINK", {"GSI2PK": f"THMBY#TAXNODE#{NODE_ID}", "GSI2SK": "thm-t"},
             link_kind="TAXNODE", theorem_id=T_THM, taxonomy_node_id=NODE_ID, slug="thm-t", name="Theorem T", role="RELATED"))
    put(item(f"THEOREM#{T_LEMMA}", f"LINK#TAXNODE#{NODE_ID}", "THEOREM_LINK", {"GSI2PK": f"THMBY#TAXNODE#{NODE_ID}", "GSI2SK": "lemma-l"},
             link_kind="TAXNODE", theorem_id=T_LEMMA, taxonomy_node_id=NODE_ID, slug="lemma-l", name="Lemma L", role="PRIMARY"))
    put(item(f"TAXNODE#{NODE_ID}", "META", "TAXNODE", name="Angle chasing", node_type="SKILL", taxonomy_node_id=NODE_ID))
    put(item(f"TECHNIQUE#{TECH_ID}", "META", "TECHNIQUE", {"GSI1PK": "SLUG#TECHNIQUE#angle-chase", "GSI1SK": "META"},
             aliases=[], description="d", name="Angle chase", slug="angle-chase", status="ACTIVE", technique_id=TECH_ID))


@pytest.fixture()
def theorems_seeded(content_table):
    seed_theorems()
    return content_table


def test_theorem_by_slug_shape_valid_assets_only_and_no_uri(theorems_seeded):
    result = STORE.get_theorem_by_slug(None, "thm-t")
    assert list(result)[:15] == ["theorem_id", "slug", "name", "kind", "field", "statement_text", "statement_latex", "description",
                                 "proof_sketch", "source", "review_status", "approval_method", "approved_at", "created_at",
                                 "updated_at"]
    assert result["statement_latex"] is None and result["created_at"] == UTC_NOW
    assert result["sources"] == [{"theorem_source_id": uid(120), "url": "https://s", "label": "Ref", "source_type": "REFERENCE",
                                  "ordinal": 0, "review_status": "APPROVED"}]
    assert result["assets"] == [
        {"asset_id": ASSET_PRIVATE, "ordinal": 0, "caption": "fig", "mime_type": "image/png", "private_object": True,
         "content_url": f"/v1/theorems/thm-t/assets/{ASSET_PRIVATE}/content"},
        {"asset_id": ASSET_EXTERNAL, "ordinal": 1, "caption": "web", "mime_type": "image/png", "private_object": False,
         "source_url": "https://src"}]                                  # the INVALID asset is not served
    assert "uri" not in json.dumps(result, default=str) and "object-store" not in json.dumps(result, default=str)
    assert result["taxonomy_links"] == [{"taxonomy_node_id": NODE_ID, "role": "RELATED", "node_type": "SKILL", "name": "Angle chasing"}]
    with pytest.raises(theorem_svc.TheoremNotFound):
        STORE.get_theorem_by_slug(None, "nope")


def test_unapproved_theorem_is_invisible(theorems_seeded):
    raw = theorem(uid(104), "pending-p", "Pending P")
    raw["review_status"] = "PENDING_REVIEW"
    put(raw)
    with pytest.raises(theorem_svc.TheoremNotFound):
        STORE.get_theorem_by_slug(None, "pending-p")


def test_prerequisites_walk_depth_limit_and_cycles(theorems_seeded):
    full = STORE.get_theorem_prerequisites(None, "thm-t")
    assert full["theorem"] == {"slug": "thm-t", "name": "Theorem T"}
    # depth 1: Axiom A, Lemma L; depth 2: Axiom A again (via L); the cycle back to T is never followed, and the
    # GENERALIZES edge is not lineage
    assert [(r["depth"], r["slug"]) for r in full["prerequisites"]] == [(1, "axiom-a"), (1, "lemma-l"), (2, "axiom-a")]
    assert set(full["prerequisites"][0]) == {"depth", "theorem_id", "slug", "name", "kind"}
    assert [r["slug"] for r in STORE.get_theorem_prerequisites(None, "thm-t", max_depth=1)["prerequisites"]] == ["axiom-a", "lemma-l"]
    # the corollary reaches T by COROLLARY_OF, then T's own lineage (depth limit 2)
    cor = STORE.get_theorem_prerequisites(None, "cor-c", max_depth=2)
    assert [(r["depth"], r["slug"]) for r in cor["prerequisites"]] == [(1, "thm-t"), (2, "axiom-a"), (2, "lemma-l")]
    for bad in (0, 11):
        with pytest.raises(ValueError):
            STORE.get_theorem_prerequisites(None, "thm-t", max_depth=bad)


def test_prerequisite_walk_terminates_on_a_long_cycle(content_table):
    ids = [uid(300 + i) for i in range(6)]
    for i, tid in enumerate(ids):
        put(theorem(tid, f"c{i}", f"C{i}"))
        nxt = ids[(i + 1) % len(ids)]
        put(rel(tid, "DEPENDS_ON", nxt, f"c{(i + 1) % len(ids)}", f"C{(i + 1) % len(ids)}"))
    rows = STORE.get_theorem_prerequisites(None, "c0", max_depth=10)["prerequisites"]
    assert [r["depth"] for r in rows] == [1, 2, 3, 4, 5]               # never revisits c0 on a path


def test_theorems_by_technique_and_taxonomy_node(theorems_seeded):
    assert STORE.get_theorems_for_technique(None, "angle-chase") == {"items": [
        {"slug": "lemma-l", "name": "Lemma L", "kind": "LEMMA", "role": "APPLIES"},
        {"slug": "thm-t", "name": "Theorem T", "kind": "THEOREM", "role": "JUSTIFIES"}]}
    assert STORE.get_theorems_for_technique(None, "unknown-technique") == {"items": []}
    assert STORE.list_theorems_for_taxonomy_node(None, NODE_ID) == {"items": [
        {"slug": "lemma-l", "name": "Lemma L", "kind": "LEMMA", "field": "GEOMETRY", "role": "PRIMARY"},
        {"slug": "thm-t", "name": "Theorem T", "kind": "THEOREM", "field": "GEOMETRY", "role": "RELATED"}]}
    assert STORE.list_theorems_for_taxonomy_node(None, "node-none") == {"items": []}


def test_theorem_asset_route_data(theorems_seeded):
    assert STORE.get_theorem_asset(None, "thm-t", ASSET_PRIVATE) == {
        "object_key": "abc.png", "mime_type": "image/png", "content_hash": SHA, "object_size_bytes": 12}
    with pytest.raises(theorem_svc.TheoremConflict):
        STORE.get_theorem_asset(None, "thm-t", ASSET_EXTERNAL)
    for asset in (ASSET_OTHER, uid(999)):                                   # INVALID, or not a diagram of this theorem
        with pytest.raises(theorem_svc.TheoremNotFound):
            STORE.get_theorem_asset(None, "thm-t", asset)


# ------------------------------------------------------------------ A31: interaction catalogue

def test_interaction_template_instance_and_widget_library(content_table):
    put(item("ITPL#slider", "V#0001", "ITPLVER", interaction_template_version_id=uid(200), interaction_template_id=uid(201),
             template_key="slider", template_name="Slider", interaction_family="GRAPH", template_version=1,
             input_schema={"a": "int"}, state_schema={}, event_schema={}, output_schema={}, default_layout={"w": 1},
             allowed_controls=["c"], allowed_icons=[], diagnostic_capabilities=[], animation_slots=[],
             accessibility_policy={"reduced_motion": "static"}, source_content_hash=SHA, status="PUBLISHED", published_at=NOW))
    put(item("ITPL#slider", "V#0002", "ITPLVER", interaction_template_version_id=uid(202), interaction_template_id=uid(201),
             template_key="slider", template_name="Slider", interaction_family="GRAPH", template_version=2,
             allowed_controls=[], allowed_icons=[], diagnostic_capabilities=[], animation_slots=[], source_content_hash=SHA,
             status="DRAFT", published_at=NOW))
    put(item(f"IINST#{INTERACTION1}", "META", "IINST", interaction_instance_id=INTERACTION1, interaction_template_version_id=uid(200),
             template_key="slider", template_version=1, canonical_code="INT-1", title="Slider", instance_config={"a": 1},
             initial_state={"x": 0}, learning_objective="explore", success_criteria={"type": "x"}, source_content_hash=SHA,
             review_status="APPROVED", approved_at=NOW, concept_ids=[], skill_ids=[], technique_ids=[], misconception_ids=[]))
    version = STORE.get_interaction_template_version(None, "slider", 1)
    assert version["template_key"] == "slider" and version["version"] == 1 and version["input_schema"] == {"a": "int"}
    assert version["accessibility_policy"] == {"reduced_motion": "static"} and version["status"] == "PUBLISHED"
    assert STORE.get_interaction_template_version(None, "slider", 2) is None          # DRAFT versions are not served
    assert STORE.get_interaction_template_version(None, "slider", 9) is None
    instance = STORE.get_interaction_instance(None, INTERACTION1)
    assert instance["instance_config"] == {"a": 1} and instance["success_criteria"] == {"type": "x"}
    assert STORE.get_interaction_instance(None, uid(999)) is None

    library = {"schema": "catalog/widget-library/v1", "kind": "widget-library", "items": {
        "interaction_templates": [{"interaction_template_id": uid(201), "template_key": "slider", "name": "Slider",
                                   "interaction_family": "GRAPH", "description": None,
                                   "versions": [{"version": 1, "status": "PUBLISHED", "content_hash": SHA, "published_at": NOW}]}],
        "controls": [{"control_template_id": uid(210), "control_key": "knob", "control_type": "RANGE",
                      "config_schema": {}, "accessibility_schema": {}}],
        "icons": [{"icon_token_id": uid(211), "token_key": "star", "icon_class": "bi-star", "semantic_role": None, "asset_id": None,
                   "accessible_label": "Star", "allowed_contexts": []}],
        "animations": [{"animation_template_id": uid(212), "animation_key": "fade", "name": "Fade", "input_schema": {},
                        "semantic_output_events": [], "reduced_motion_behavior": {}}]}}
    body = json.dumps(library, sort_keys=True, separators=(",", ":")).encode()
    sha = hashlib.sha256(body).hexdigest()
    put_object(f"catalog/widget-library/{sha}.json", body)
    put(item("CATALOG#WIDGET-LIBRARY", "SNAPSHOT", "CATALOGPTR", kind="widget-library", s3_key=f"catalog/widget-library/{sha}.json",
             sha256=sha, count=4))
    assert STORE.get_widget_library(None) == {
        "templates": [{"interaction_template_id": uid(201), "template_key": "slider", "interaction_family": "GRAPH",
                       "status": "ACTIVE", "interaction_template_version_id": uid(200), "version": 1, "version_status": "PUBLISHED"}],
        "controls": [{"control_key": "knob", "control_type": "RANGE", "status": "ACTIVE"}],
        "icons": [{"token_key": "star", "icon_class": "bi-star", "accessible_label": "Star", "status": "ACTIVE"}],
        "animations": [{"animation_key": "fade", "name": "Fade", "status": "ACTIVE"}]}
    put_object(f"catalog/widget-library/{sha}.json", b'{"tampered":true}')
    snapshots.clear()
    with pytest.raises(StoreError, match="checksum"):
        STORE.get_widget_library(None)


# ------------------------------------------------------------------ no Postgres, backend contract

class _NoPostgres:
    def __getattr__(self, name):
        raise AssertionError(f"DynamoDB content store touched PostgreSQL ({name})")


@contextmanager
def no_postgres(monkeypatch):
    import mathbank_rest.db.postgres as pg

    monkeypatch.setattr(pg, "engine", _NoPostgres())
    monkeypatch.setattr(mc_router, "engine", _NoPostgres())
    monkeypatch.setattr(thm_router, "engine", _NoPostgres())
    yield


def test_dynamodb_methods_never_touch_postgres(seeded, monkeypatch):
    seed_theorems()
    put(vasset(ASSET_PRIVATE, source_uri="object-store:abc.png", size=12))
    with no_postgres(monkeypatch):
        STORE.get_micro_course_reader(None, "MC-1")
        STORE.get_pinned_micro_course_reader(None, REL1)
        STORE.list_published_micro_courses(None)
        STORE.get_course_asset(None, "MC-1", ASSET_PRIVATE)
        STORE.get_grading_item(None, REL1, STATE1, LI1)
        STORE.get_grading_activity(None, REL1, ACT1)
        STORE.get_theorem_by_slug(None, "thm-t")
        STORE.get_theorem_prerequisites(None, "thm-t")
        STORE.get_theorems_for_technique(None, "angle-chase")
        STORE.list_theorems_for_taxonomy_node(None, NODE_ID)


def test_every_method_name_is_a_read_so_frozen_serves_it(seeded):
    methods = [m for m in vars(LearningDynamoDB) if not m.startswith("_") and callable(getattr(LearningDynamoDB, m))]
    assert methods and all(m.startswith(stores.READ_PREFIXES) for m in methods)
    assert {m for m in vars(LearningPostgres) if not m.startswith("_") and callable(getattr(LearningPostgres, m))} == set(methods)
    frozen = stores.FrozenProxy("content", STORE)
    assert frozen.get_micro_course_reader(None, "MC-1")["canonical_code"] == "MC-1"


def test_postgres_backend_delegates_to_the_service_functions_at_call_time(monkeypatch):
    pg = LearningPostgres()
    seen = []
    monkeypatch.setattr(courses, "get_published_course", lambda conn, code: seen.append(("reader", code)) or {"ok": 1})
    monkeypatch.setattr(courses, "list_published_courses", lambda conn, limit, offset: seen.append(("list", limit, offset)) or [])
    monkeypatch.setattr(courses, "get_published_asset", lambda conn, code, asset: seen.append(("asset", code, asset)) or {})
    monkeypatch.setattr(theorem_svc, "get_theorem", lambda conn, slug, include_unapproved: seen.append(("thm", slug, include_unapproved)) or {})
    monkeypatch.setattr(theorem_svc, "get_theorem_prerequisites",
                        lambda conn, slug, max_depth, include_unapproved: seen.append(("pre", slug, max_depth, include_unapproved)) or {})
    pg.get_micro_course_reader(object(), "X")
    pg.list_published_micro_courses(object(), 5, 2)
    pg.get_course_asset(object(), "X", "a")
    pg.get_theorem_by_slug(object(), "s")
    pg.get_theorem_prerequisites(object(), "s", max_depth=3)
    assert seen == [("reader", "X"), ("list", 5, 2), ("asset", "X", "a"), ("thm", "s", False), ("pre", "s", 3, False)]


# ------------------------------------------------------------------ route parity (Postgres vs DynamoDB)

class BackendClient:
    """A TestClient for one backend: the content store is switched per request."""

    def __init__(self, store):
        self.http, self.store = TestClient(app), store

    def request(self, method, path, **kwargs):
        with stores.override_store("content", self.store):
            return self.http.request(method, path, **kwargs)


class FakeEngine:
    def __init__(self, conn):
        self.conn = conn

    @contextmanager
    def begin(self):
        yield self.conn


def theorem_pg_conn():
    row = {"theorem_id": T_THM, "slug": "thm-t", "name": "Theorem T", "kind": "THEOREM", "field": "GEOMETRY",
           "statement_text": "Theorem T statement", "statement_latex": None, "description": None, "proof_sketch": None,
           "source": "HUMAN", "review_status": "APPROVED", "approval_method": "human", "approved_at": UTC_NOW,
           "created_at": UTC_NOW, "updated_at": UTC_NOW}
    return FakeConn([
        ("SELECT * FROM knowledge.theorem", [row]),
        ("FROM knowledge.theorem_source", [{"theorem_source_id": uid(120), "url": "https://s", "label": "Ref",
                                            "source_type": "REFERENCE", "ordinal": 0, "review_status": "APPROVED"}]),
        ("FROM knowledge.theorem_asset ta", [
            {"asset_id": ASSET_PRIVATE, "ordinal": 0, "caption": "fig", "uri": "object-store:abc.png", "mime_type": "image/png",
             "source_url": "https://src"},
            {"asset_id": ASSET_EXTERNAL, "ordinal": 1, "caption": "web", "uri": "https://example.org/x.png",
             "mime_type": "image/png", "source_url": "https://src"}]),
        ("JOIN pedagogy.taxonomy_node tn", [{"taxonomy_node_id": NODE_ID, "role": "RELATED", "node_type": "SKILL",
                                             "name": "Angle chasing"}]),
        ("WITH RECURSIVE", [{"depth": 1, "theorem_id": T_AXIOM, "slug": "axiom-a", "name": "Axiom A", "kind": "AXIOM"},
                            {"depth": 1, "theorem_id": T_LEMMA, "slug": "lemma-l", "name": "Lemma L", "kind": "LEMMA"},
                            {"depth": 2, "theorem_id": T_AXIOM, "slug": "axiom-a", "name": "Axiom A", "kind": "AXIOM"}]),
        ("FROM knowledge.technique_theorem tt", [
            {"slug": "lemma-l", "name": "Lemma L", "kind": "LEMMA", "role": "APPLIES"},
            {"slug": "thm-t", "name": "Theorem T", "kind": "THEOREM", "role": "JUSTIFIES"}]),
        ("FROM knowledge.theorem_taxonomy_link tl JOIN knowledge.theorem t", [
            {"slug": "lemma-l", "name": "Lemma L", "kind": "LEMMA", "field": "GEOMETRY", "role": "PRIMARY"},
            {"slug": "thm-t", "name": "Theorem T", "kind": "THEOREM", "field": "GEOMETRY", "role": "RELATED"}]),
    ])


def test_micro_course_routes_have_parity_across_backends(seeded, monkeypatch):
    seed_course()
    put(vasset(ASSET_PRIVATE, source_uri="object-store:abc.png", size=12))
    clients = {"postgres": BackendClient(LearningPostgres()), "dynamodb": BackendClient(STORE)}
    monkeypatch.setattr(mc_router, "engine", FakeEngine(pg_course_conn()))
    monkeypatch.setattr(courses, "list_published_courses", lambda conn, limit, offset: [{
        "canonical_code": "MC-1", "title": "Linear equations", "description": "Intro", "metadata": {"collection": "core"},
        "estimated_minutes": 15, "difficulty_level": 2, "release_id": REL1, "version": 1, "state_count": 2,
        "primary_targets": [{"target_type": "CONCEPT", "name": "Equation", "slug": "equation"}]}])
    asset_bytes = b"x" * 12
    sha = hashlib.sha256(asset_bytes).hexdigest()
    put(vasset(ASSET_PRIVATE, source_uri="object-store:abc.png", size=12, sha=sha))
    monkeypatch.setattr(courses, "get_published_asset", lambda conn, code, asset: {
        "object_key": "abc.png", "mime_type": "image/png", "content_hash": sha, "object_size_bytes": 12})
    monkeypatch.setattr(mc_router.object_store, "read_bytes", lambda key: asset_bytes)

    assert_parity(clients, ParityCase("list", "GET", "/v1/micro-courses", expect_status=200))
    res = assert_parity(clients, ParityCase("reader", "GET", "/v1/micro-courses/MC-1", expect_status=200))
    assert_no_keys(res["dynamodb"][1])
    res = assert_parity(clients, ParityCase("asset", "GET", f"/v1/micro-courses/MC-1/assets/{ASSET_PRIVATE}/content"))
    assert res["dynamodb"][0] == 200


def test_micro_course_missing_course_is_404_on_both_backends(seeded, monkeypatch):
    clients = {"postgres": BackendClient(LearningPostgres()), "dynamodb": BackendClient(STORE)}
    monkeypatch.setattr(mc_router, "engine", FakeEngine(FakeConn([])))
    assert_parity(clients, ParityCase("missing", "GET", "/v1/micro-courses/MC-NOPE", expect_status=404))
    assert_parity(clients, ParityCase("missing asset", "GET", f"/v1/micro-courses/MC-NOPE/assets/{ASSET_PRIVATE}/content",
                                      expect_status=404))


def test_theorem_routes_have_parity_across_backends(theorems_seeded, monkeypatch):
    clients = {"postgres": BackendClient(LearningPostgres()), "dynamodb": BackendClient(STORE)}
    monkeypatch.setattr(thm_router, "engine", FakeEngine(theorem_pg_conn()))
    for name, path in (("detail", "/v1/theorems/thm-t"), ("prerequisites", "/v1/theorems/thm-t/prerequisites"),
                       ("by technique", "/v1/theorems/by-technique/angle-chase"),
                       ("by taxonomy", f"/v1/theorems/by-taxonomy/{NODE_ID}")):
        assert_parity(clients, ParityCase(name, "GET", path, expect_status=200))
    detail = clients["dynamodb"].request("GET", "/v1/theorems/thm-t").json()
    assert "uri" not in json.dumps(detail)


def test_theorem_missing_and_asset_errors_have_parity(theorems_seeded, monkeypatch):
    clients = {"postgres": BackendClient(LearningPostgres()), "dynamodb": BackendClient(STORE)}
    monkeypatch.setattr(thm_router, "engine", FakeEngine(FakeConn([])))
    assert_parity(clients, ParityCase("missing", "GET", "/v1/theorems/nope", expect_status=404))
    assert_parity(clients, ParityCase("missing asset", "GET", f"/v1/theorems/nope/assets/{ASSET_PRIVATE}/content", expect_status=404))


def test_dynamodb_routes_serve_without_a_database_connection(seeded, monkeypatch):
    seed_theorems()
    client = BackendClient(STORE)
    with no_postgres(monkeypatch):
        assert client.request("GET", "/v1/micro-courses").status_code == 200
        assert client.request("GET", "/v1/micro-courses/MC-1").status_code == 200
        assert client.request("GET", "/v1/theorems/thm-t").status_code == 200
        assert client.request("GET", "/v1/theorems/thm-t/prerequisites").status_code == 200
        assert client.request("GET", "/v1/theorems/by-technique/angle-chase").status_code == 200
        assert client.request("GET", "/v1/micro-courses/MC-NOPE").status_code == 404


def test_snapshot_documents_are_not_mutated_by_reads(seeded):
    before = copy.deepcopy(snapshots.get_json(f"releases/micro-course/{REL1}/{SHA}/learner.json"))
    STORE.get_micro_course_reader(None, "MC-1")
    STORE.get_grading_item(None, REL1, STATE1, LI1)
    assert snapshots.get_json(f"releases/micro-course/{REL1}/{SHA}/learner.json") == before
