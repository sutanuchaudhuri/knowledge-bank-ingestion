"""WP4 pedagogy area of the content store: solution DAG, steps, published routes, taxonomy, topic candidates, video, hints.

DynamoDB side: moto ``mb-content`` seeded with typed items and content-addressed S3 snapshots. Postgres side: today's SQL answered
by a scripted fake connection, so shapes are compared on equivalent canned data. No test touches a real database or AWS.
"""
from __future__ import annotations

import hashlib
import json
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "parity"))

from parity_harness import ParityCase, assert_parity

from mathbank_rest import route_runtime, step_runtime, step_tutor, stores
from mathbank_rest.db import topic_pedagogy
from mathbank_rest.main import app
from mathbank_rest.models.ddb.content import (
    ContentFacet,
    ContentProblem,
    ContentRouterel,
    ContentSoldag,
    ContentStep,
    ContentTaxnode,
)
from mathbank_rest.models.manual.content_pedagogy import (
    ContentRouteptr,
    ContentVideo,
    ContentVtranscript,
)
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import typed
from mathbank_rest.stores.content import DynamoDBContentStore, PostgresContentStore
from mathbank_rest.stores.content.snapshots import SnapshotStore
from mathbank_rest.stores.errors import NotFound, StoreError, StoreFrozen

NOW = datetime(2026, 1, 1, tzinfo=UTC)
CODE = "PRASOLOV_PGV1_1.1"
PROBLEM_ID = "11111111-1111-4111-8111-111111111111"
SOLUTION_ID = "22222222-2222-4222-8222-222222222222"
EXPECTED = "KEY-expected-response"
STATEMENT = "Prove that the three altitudes of a triangle are concurrent."


def uid(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012d}"


def put_object(key: str, body: bytes) -> None:
    toolkit.client("s3").put_object(Bucket=toolkit.content_bucket(), Key=key, Body=body)


def jbytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


# ---------------------------------------------------------------------------------------------------------- routes

INSTRUCTION = {
    **{k: k.upper() for k in ("goal_text", "recognition_cue", "reasoning_explanation", "why_this_works", "prerequisite_recap",
                              "connection_to_previous_step", "connection_to_next_step", "common_error_summary",
                              "student_prompt", "short_explanation", "full_explanation")},
    "has_diagram": False, "diagram_description": "", "diagram_instructions": "",
}


def route_docs(rid: str, *, leak: bool = False):
    steps, server_steps = [], []
    for i in (1, 2):
        instr = {**INSTRUCTION, "goal_text": f"GOAL{i}", "student_prompt": f"PROMPT{i}"}
        steps.append({
            "step_index": i, "step_id": f"s{i}", "instruction": instr | ({"expected_response": EXPECTED} if leak else {}),
            "hints": [{"hint_level": lv, "hint_variant": "default", "misconception_key": "", "hint_text": f"H{i}.{lv}"}
                      for lv in range(1, 6)] + [{"hint_level": 1, "hint_variant": "alt", "misconception_key": "MIS_X", "hint_text": "variant"}],
            "requirements": [], "asset_links": []})
        server_steps.append({"step_index": i, "expected_response": EXPECTED if i == 1 else f"{EXPECTED}-{i}",
                             "mathematical_result": f"result{i}", "source_quote": f"quote{i}",
                             "depends_on": [] if i == 1 else [1], "produces": [], "uses_claims": [], "generation_metadata": {}})
    learner = {"schema": "route-release/learner/v1", "route_release_id": rid, "approach_name": "Angle chase",
               "approach_summary": "SUMMARY", "difficulty_level": 2, "conceptual_load": 2, "algebraic_load": 1,
               "insight_load": 1, "steps": steps}
    return learner, {"schema": "route-release/server/v1", "route_release_id": rid, "steps": server_steps, "assets": []}


def ptr_sk(rid: str, *, preferred: bool, quality: float | None, difficulty: int, version: int) -> str:
    """Same encoding as the publisher: ascending order == ``select_published`` ORDER BY."""
    pref = 9 - (1 if preferred else 0)
    inv_q = 9999 if quality is None else 9998 - max(0, min(9998, round(quality * 1000)))
    return f"ROUTE#{pref}#{inv_q:04d}#{difficulty:02d}#{999999 - version:06d}#{rid}"


def seed_route(rid: str, *, code: str = CODE, preferred: bool = False, quality: float | None = None, difficulty: int = 2,
               version: int = 1, leak: bool = False, status: str = "PUBLISHED", sha: str | None = None) -> None:
    learner, server = route_docs(rid, leak=leak)
    sha = sha or hashlib.sha256(jbytes({"learner": learner, "server": server})).hexdigest()
    base = f"releases/route/{rid}/{sha}"
    put_object(f"{base}/learner.json", jbytes(learner))
    put_object(f"{base}/server.json", jbytes(server))
    typed.put(ContentRouterel(
        PK=f"ROUTEREL#{rid}", SK="META", approach_name="Angle chase", content_sha256=sha, difficulty_level=difficulty,
        generator_version="g", problem_code=code, problem_id=PROBLEM_ID, published_at=NOW, release_version=version,
        route_release_id=rid, s3_learner_key=f"{base}/learner.json", s3_server_key=f"{base}/server.json",
        solution_id=SOLUTION_ID, source_content_hash="h", source_hash="sh", src_rev=1, status=status, step_count=2))
    typed.put(ContentRouteptr(
        PK=f"PROBLEM#{code}", SK=ptr_sk(rid, preferred=preferred, quality=quality, difficulty=difficulty, version=version),
        content_sha256=sha, difficulty_level=difficulty, preferred_for_tutoring=preferred, release_version=version,
        route_release_id=rid, solution_id=SOLUTION_ID, src_rev=1, verification_status="VERIFIED", route_quality=quality))


@pytest.fixture()
def store(content_table):
    return DynamoDBContentStore()


@pytest.fixture()
def no_postgres(monkeypatch):
    """Any Postgres access fails loudly."""
    class Boom:
        def connect(self, *a, **k):
            raise AssertionError("DynamoDB content store touched Postgres")

        begin = connect

    from mathbank_rest.db import postgres

    for mod in (postgres, route_runtime, topic_pedagogy):
        monkeypatch.setattr(mod, "engine", Boom())


def test_route_selection_follows_the_published_ordering(store):
    a, b, c, d = uid(1), uid(2), uid(3), uid(4)
    seed_route(a, quality=0.9, difficulty=1, version=5)                   # better quality but not preferred
    seed_route(b, preferred=True, quality=0.5, difficulty=3, version=1)   # preferred wins
    seed_route(c, preferred=True, quality=0.5, difficulty=2, version=1)   # tie on quality -> lower difficulty
    seed_route(d, preferred=True, quality=0.5, difficulty=2, version=3)   # tie again -> newer release
    assert str(store.find_published_route(CODE)["route_release_id"]) == d
    row = store.find_published_route(CODE)
    assert row["canonical_code"] == CODE and row["verification_status"] == "VERIFIED" and row["approach_summary"] == "SUMMARY"
    assert row["preferred_for_tutoring"] is True and row["route_quality"] == 0.5 and row["status"] == "PUBLISHED"
    assert store.find_published_route("NO_SUCH") is None


def test_unpublished_release_is_not_selected_or_fetched(store):
    seed_route(uid(1), status="RETIRED")
    assert store.find_published_route(CODE) is None
    assert store.get_published_route(CODE, uid(1)) is None


def test_get_published_route_requires_the_same_problem(store):
    seed_route(uid(1))
    assert str(store.get_published_route(CODE, uid(1))["route_release_id"]) == uid(1)
    assert store.get_published_route("OTHER", uid(1)) is None


def test_learner_views_never_contain_expected_response_but_server_load_does(store):
    seed_route(uid(1), leak=True)       # even a publisher bug cannot leak: learner reads scrub it again
    view = store.load_route_learner_view(uid(1))
    assert EXPECTED not in json.dumps(view) and "expected_response" not in json.dumps(view)
    for payload in (store.list_route_instructions(uid(1)), store.get_route_step_instruction(uid(1), 1)):
        assert "expected_response" not in json.dumps(payload)
    program = store.load_route_program(uid(1))
    assert program.steps[0].instruction.expected_response == EXPECTED
    assert program.steps[1].instruction.expected_response == f"{EXPECTED}-2"


def test_load_route_program_rebuilds_the_program_with_default_hints_only(store):
    seed_route(uid(1))
    program = store.load_route_program(uid(1))
    assert program.approach_name == "Angle chase" and program.difficulty_level == 2
    assert program.steps[0].hints == ["H1.1", "H1.2", "H1.3", "H1.4"]       # levels <= 4, default variant only
    assert program.steps[1].depends_on == [1] and program.steps[1].mathematical_result == "result2"
    assert program.assets == []
    with pytest.raises(NotFound):
        store.load_route_program(uid(99))


def test_route_step_accessors(store):
    seed_route(uid(1))
    assert [i["goal_text"] for i in store.list_route_instructions(uid(1))] == ["GOAL1", "GOAL2"]
    assert store.get_route_step_instruction(uid(1), 2)["student_prompt"] == "PROMPT2"
    assert store.get_route_step_instruction(uid(1), 3) is None
    assert store.get_route_step_hint(uid(1), 1, 5) == "H1.5"
    assert store.get_route_step_hint(uid(1), 1, 6) is None


def test_snapshot_key_must_match_the_release_hash(store):
    seed_route(uid(1), sha="f" * 64)
    learner, _ = route_docs(uid(1))
    rel = typed.require(ContentRouterel, f"ROUTEREL#{uid(1)}", "META")
    # a pointer whose snapshot directory is not its content hash is refused
    object.__setattr__(rel, "content_sha256", "0" * 64)
    with pytest.raises(StoreError, match="content hash"):
        store._route_docs(rel)
    assert learner["route_release_id"] == uid(1)


def test_snapshot_checksum_and_lru(content_table):
    body = jbytes({"a": 1})
    good = hashlib.sha256(body).hexdigest()
    put_object(f"snap/{good}.json", body)
    put_object(f"snap/{'0' * 64}.json", body)                       # content does not hash to its key
    store = SnapshotStore(max_bytes=20)
    assert store.get_json(f"snap/{good}.json") == {"a": 1}
    with pytest.raises(StoreError, match="checksum"):
        store.get_json(f"snap/{'0' * 64}.json")
    toolkit.client("s3").delete_object(Bucket=toolkit.content_bucket(), Key=f"snap/{good}.json")
    assert store.get_json(f"snap/{good}.json") == {"a": 1}          # served from the in-process LRU
    other = jbytes({"b": "x" * 30})
    put_object("snap/plain.json", other)                            # not content-addressed: no hash check
    store.get_json("snap/plain.json")                               # over budget -> the oldest entry is evicted
    with pytest.raises(toolkit.client("s3").exceptions.NoSuchKey):      # the evicted entry is really gone
        store.get_json(f"snap/{good}.json")


# ---------------------------------------------------------------------------------------------------- solution DAG

def step_doc(i: int, part: str, text: str | None = None) -> dict:
    return {"concept_node_id": "C1", "global_step_index": i, "hint_level": 1, "is_checkpoint": i == 1, "occurrence": 1,
            "skill_name": f"skill{i}", "skill_node_id": f"SK{i}", "solution_part_id": part, "solution_step_id": f"st{i}",
            "source_metadata": {"solution_part": "MAIN", "source_row": i}, "source_step_id": f"src{i}", "step_index_in_part": i,
            "step_text": text or f"step text {i}", "step_type": "SETUP", "subconcept_node_id": "SC1", "tutor_role": "CORE_BRIDGE"}


def seed_dag(*, big: bool = False) -> None:
    steps = [step_doc(2, "p1", "x" * 20000 if big else None), step_doc(1, "p1"), step_doc(3, "p2")]
    dep = {"approval_method": "automatic", "confidence": 0.9, "logical_dependency": "INFERENCE_FROM_PREVIOUS", "metadata": {},
           "relationship_type": "DEPENDS_ON", "review_status": "REVIEWED", "source_type": "IMPORTED_PACKAGE"}
    tech = {"approval_method": "automatic", "approved_at": NOW.isoformat(), "confidence": 0.8, "derivation_version": "rules-v1",
            "evidence": "e", "review_status": "APPROVED", "solution_step_id": "st2", "source_type": "RULE_STEP_TEXT_NAMED",
            "technique_node_id": "TECH.A"}
    typed.put(ContentSoldag(
        PK=f"PROBLEM#{CODE}", SK=f"SOLDAG#{SOLUTION_ID}", content_sha256="s", problem_code=CODE, problem_id=PROBLEM_ID,
        solution_id=SOLUTION_ID, src_rev=1, step_count=3, steps=steps,
        parts=[{"book_code": "B", "occurrence": 1, "part_label": "B2", "part_ordinal": 2, "part_text_normalized": "", "solution_part_id": "p2",
                "source_part_id": "sp2", "source_step_count": 1, "step_count": 1},
               {"book_code": "B", "occurrence": 1, "part_label": "MAIN", "part_ordinal": 1, "part_text_normalized": "", "solution_part_id": "p1",
                "source_part_id": "sp1", "source_step_count": 2, "step_count": 2}],
        dependencies=[{**dep, "from_step_id": "st1", "to_step_id": "st2"},
                      {**dep, "from_step_id": "st2", "to_step_id": "st3", "relationship_type": "NEXT"},
                      {**dep, "from_step_id": "st1", "to_step_id": "st3", "review_status": "REJECTED"}],
        step_techniques=[tech, {**tech, "technique_node_id": "TECH.B", "review_status": "PENDING"}]))


def test_solution_dag_shape_order_and_filters(store):
    seed_dag()
    dag = store.get_solution_dag(CODE)
    assert [s["solution_step_id"] for s in dag["steps"]] == ["st1", "st2", "st3"]
    first = dag["steps"][0]
    assert set(first) == {"solution_step_id", "source_step_id", "occurrence", "solution_id", "solution_part_id", "part_label",
                          "global_step_index", "step_index_in_part", "step_text", "step_type", "tutor_role", "concept_node_id",
                          "subconcept_node_id", "skill_node_id", "skill_name", "hint_level", "is_checkpoint"}
    assert first["part_label"] == "MAIN" and dag["steps"][2]["part_label"] == "B2" and first["solution_id"] == SOLUTION_ID
    assert [p["part_label"] for p in dag["parts"]] == ["MAIN", "B2"]
    assert [(d["from_step_id"], d["to_step_id"]) for d in dag["dependencies"]] == [("st1", "st2"), ("st2", "st3")]   # REJECTED dropped
    assert [t["technique_node_id"] for t in dag["step_techniques"]] == ["TECH.A"]                                  # APPROVED only
    assert dag["problem_code"] == CODE and dag["problem_id"] == PROBLEM_ID and dag["solutions"] == [SOLUTION_ID]


def test_solution_dag_resolves_offloaded_steps(store):
    seed_dag(big=True)
    item = typed.require(ContentSoldag, f"PROBLEM#{CODE}", f"SOLDAG#{SOLUTION_ID}")
    assert item.ref("steps") is not None and item.steps is None      # really in S3
    assert store.get_solution_dag(CODE)["steps"][1]["step_text"] == "x" * 20000


def test_solution_dag_by_problem_id_uses_gsi1(store):
    seed_dag()
    typed.put(problem_item())
    assert store.get_solution_dag(problem_id=PROBLEM_ID)["steps"][0]["solution_step_id"] == "st1"
    assert store.get_solution_dag("UNKNOWN") == {"problem_code": "UNKNOWN", "problem_id": None, "solutions": [], "parts": [],
                                                 "steps": [], "dependencies": [], "step_techniques": []}
    with pytest.raises(ValueError):
        store.get_solution_dag()


def test_step_runtime_reads_the_dag_through_the_store(store, no_postgres):
    seed_dag()
    typed.put(problem_item())
    with stores.override_store("content", store):
        steps, prereqs = step_runtime._steps(object(), PROBLEM_ID)
    assert [(s.solution_step_id, s.solution_part_id, s.global_step_index) for s in steps] == [("st1", "p1", 1), ("st2", "p1", 2), ("st3", "p2", 3)]
    assert prereqs == {"st2": {"st1"}}      # only DEPENDS_ON; NEXT and REJECTED edges are not prerequisites


# ------------------------------------------------------------------------------------------------------------ steps

def problem_item() -> ContentProblem:
    return ContentProblem(
        PK=f"PROBLEM#{CODE}", SK="META", GSI1PK=f"PID#{PROBLEM_ID}", GSI1SK="META", canonical_code=CODE,
        competition={"competition_id": uid(7), "external_code": "PRASOLOV", "level": "X", "name": "Prasolov"},
        content_sha256="c", created_at=NOW, images=[], paper_code="P", paper_id=uid(8), problem_id=PROBLEM_ID, problem_number=1,
        src_rev=1, updated_at=NOW, visibility="ACTIVE", statement_text=STATEMENT,
        enrichment={"concept_node_id": "C1", "difficulty_band_source_order": 3, "primary_skill_node_id": "SK1",
                    "problem_form": "PROOF", "solution_step_count": 3, "solution_step_skill_ids": ["SK1"], "subconcept_node_id": "SC1",
                    "taxonomy_confidence": 0.75, "taxonomy_mapping_basis": "b", "technique_ids": []})


def step_item(i: int, *, eligible: bool = True, code: str = CODE, skill: str | None = None) -> ContentStep:
    return ContentStep(
        PK=f"STEP#st{i}", SK="META", book_code="B", concept_node_id="C1", content_sha256="c", eligible=eligible, global_step_index=i,
        hint_level=1, is_checkpoint=i == 1, problem_code=code, problem_id=PROBLEM_ID, skill_name=f"skill{i}",
        skill_node_id=skill or f"SK{i}", solution_id=SOLUTION_ID, solution_part_id="p1" if i < 3 else "p2", solution_step_id=f"st{i}",
        src_rev=1, step_index_in_part=i, step_text=f"step text {i}", step_type="SETUP", subconcept_node_id="SC1",
        technique_node_ids=[], tutor_role="CORE_BRIDGE", updated_at=NOW,
        vector_state={"index": "i", "keys": [uid(i)], "model": "m", "sha256": "s"})


def test_step_details_and_eligibility(store):
    typed.put(step_item(1))
    typed.put(step_item(2, eligible=False))
    rows = store.get_step_details(["st1", "st2", "missing"])
    assert set(rows) == {"st1", "st2"} and rows["st2"]["eligible"] is False and "step_text" not in rows["st1"]
    assert set(rows["st1"]) == {"solution_step_id", "problem_id", "solution_id", "solution_part_id", "global_step_index", "step_type",
                                "tutor_role", "hint_level", "is_checkpoint", "skill_node_id", "skill_name", "subconcept_node_id",
                                "concept_node_id", "problem_code", "eligible"}
    assert store.get_step_details(["st1"], include_step_text=True)["st1"]["step_text"] == "step text 1"
    assert [r["solution_step_id"] for r in store.get_steps_by_ids(["st2", "st1", "missing"])] == ["st1"]   # withdrawn / unknown dropped


def test_step_level_reads_for_tutor_and_recovery(store):
    seed_dag()
    typed.put(problem_item())
    for i in (1, 2, 3):
        typed.put(step_item(i))
    ctx = store.get_step_tutor_context("st3")
    assert ctx["statement_text"] == STATEMENT and ctx["part_label"] == "B2" and ctx["previous_steps"] == ["step text 1", "step text 2"]
    assert ctx["solution_id"] == SOLUTION_ID and ctx["global_step_index"] == 3
    assert store.get_step_origin("st2") == {"canonical_code": CODE, "part_label": "MAIN", "step_index_in_part": 2, "global_step_index": 2}
    assert store.get_step_recovery_target("st2") == {"skill_node_id": "SK2", "subconcept_node_id": "SC1", "label": "skill2"}
    example = store.get_step_worked_example("st1")
    assert example["canonical_code"] == CODE and example["statement_text"] == STATEMENT and example["step_text"] == "step text 1"
    with pytest.raises(NotFound):
        store.get_step_origin("nope")


# ------------------------------------------------------------------------------------------------------- taxonomy

def taxnode(nid: str, name: str, ntype: str = "SKILL", parent: tuple[str, str] | None = None, **kw) -> ContentTaxnode:
    gsi = {"GSI1PK": f"TAXCHILD#{parent[0]}", "GSI1SK": f"{ntype}#{name}"} if parent else {}
    return ContentTaxnode(
        PK=f"TAXNODE#{nid}", SK="META", GSI2PK=f"TAXTYPE#{ntype}", GSI2SK=f"001##{nid}", **gsi, content_sha256="c", eligible=True,
        example_problem_codes=[CODE], lifecycle="ACTIVE", name=name, node_type=ntype, problem_count=4, src_rev=1, taxonomy_node_id=nid,
        updated_at=NOW, vector_state={"index": "i", "keys": [nid], "model": "m", "sha256": "s"}, chapter_number=1, section_number="1",
        slug="power-of-a-point", slug_kind="technique", parent={"id": parent[0], "name": parent[1]} if parent else None, **kw)


def test_taxonomy_nodes_children_and_type_listing(store):
    typed.put(taxnode("CON.1", "Circles", "CONCEPT"))
    typed.put(taxnode("SK.B", "Beta", "SKILL", ("CON.1", "Circles")))
    typed.put(taxnode("SK.A", "Alpha", "SKILL", ("CON.1", "Circles")))
    typed.put(taxnode("TECH.X", "Power of a point", "TECHNIQUE", ("CON.1", "Circles")))
    assert [n["taxonomy_node_id"] for n in store.list_taxonomy_children("CON.1")] == ["SK.A", "SK.B", "TECH.X"]   # node_type#name order
    assert store.list_taxonomy_children("EMPTY") == []
    nodes = store.get_taxonomy_nodes(["SK.A", "missing"])
    assert set(nodes) == {"SK.A"}
    assert nodes["SK.A"] == {"taxonomy_node_id": "SK.A", "node_type": "SKILL", "name": "Alpha", "parent_node_id": "CON.1",
                             "parent_name": "Circles", "chapter_number": 1, "section_number": "1", "slug": "power-of-a-point",
                             "slug_kind": "technique", "problem_count": 4, "example_problem_codes": [CODE]}
    listed = store.list_taxonomy_nodes(("SKILL", "TECHNIQUE"))
    assert [n["taxonomy_node_id"] for n in listed] == ["SK.A", "SK.B", "TECH.X"] and set(listed[0]) == {"taxonomy_node_id", "name", "node_type"}


def test_topic_plan_exact_and_ambiguous_without_postgres(store, no_postgres):
    typed.put(taxnode("TECH.X", "Power of a Point", "TECHNIQUE"))
    typed.put(taxnode("SK.P", "Power of a prime", "SKILL"))
    with stores.override_store("content", store):
        hit = topic_pedagogy.topic_plan("power of the point")          # articles dropped, exact normalised match
        miss = topic_pedagogy.topic_plan("power")
    assert hit["matched"] and hit["node"]["taxonomy_node_id"] == "TECH.X" and hit["node"]["problem_count"] == 4
    assert not miss["matched"] and {c["taxonomy_node_id"] for c in miss["candidates"]} == {"TECH.X", "SK.P"}


def test_topic_candidates_from_step_facets_without_postgres(store, no_postgres, monkeypatch):
    typed.put(taxnode("SK1", "Angle chase", "SKILL"))
    typed.put(problem_item())
    typed.put(step_item(1))
    typed.put(ContentFacet(PK="FACET#STEP#SKILL#SK1", SK="st1", content_sha256="c", dim="SKILL", entity_id="st1", src_rev=1, unit="STEP",
                           value="SK1", vector_keys=[uid(1)]))
    with stores.override_store("content", store):
        rows = store.list_topic_candidates("SK1")
        monkeypatch.setattr(topic_pedagogy, "load_profile", lambda version: {"minimum_confidence": 0.0})
        monkeypatch.setattr(topic_pedagogy, "rank_candidates", lambda cands, **kw: cands)
        result = topic_pedagogy.topic_candidates("angle chase")
    assert rows == [{"canonical_code": CODE, "node_type": "SKILL", "confidence": 0.75, "difficulty": 3, "skill_ids": ["SK1"],
                     "structure_key": "SC1|PROOF|SK1"}]
    assert result["matched"] and result["candidates"][0]["canonical_code"] == CODE and result["candidates"][0]["exposure_known"] is False
    assert store.list_topic_candidates("missing") == []


# ---------------------------------------------------------------------------------------------------------- video

def seed_video(vid: str = uid(50)) -> None:
    segs = [{"segment_id": f"g{i}", "segment_index": i, "start_ms": i * 1000, "end_ms": i * 1000 + 800, "transcript_text": f"t{i}", "speaker": None}
            for i in range(5)]
    body = jbytes({"schema": "video-transcript/v1", "video_asset_id": vid, "language_code": "en", "version": 2, "segments": segs[::-1]})
    sha = hashlib.sha256(body).hexdigest()
    key = f"video/{vid}/en/v2/{sha}.json"
    put_object(key, body)
    typed.put(ContentVideo(PK=f"VIDEO#{vid}", SK="META", video_asset_id=vid, provider="YOUTUBE", url="https://y/1", title="T", duration_ms=5000,
                           review_status="APPROVED"))
    typed.put(ContentVtranscript(PK=f"VIDEO#{vid}", SK="TRANSCRIPT#en", language_code="en", transcript_version=2, s3_key=key, sha256=sha,
                                 segment_count=5))


def test_video_transcript_and_segment_search(store):
    seed_video()
    vid = uid(50)
    assert store.get_video(vid)["title"] == "T" and store.get_video(uid(51)) is None
    doc = store.get_video_transcript(vid)
    assert doc["version"] == 2 and [s["segment_id"] for s in doc["segments"]] == ["g0", "g1", "g2", "g3", "g4"]      # sorted by start_ms
    assert set(doc["segments"][0]) == {"segment_id", "segment_index", "start_ms", "end_ms", "transcript_text", "speaker"}
    assert store.find_video_segment_at(vid, 2500)["segment_id"] == "g2"
    assert store.find_video_segment_at(vid, 2000)["segment_id"] == "g2"          # boundary belongs to the segment that starts there
    assert store.find_video_segment_at(vid, 2900) is None                        # gap between segments
    assert store.find_video_segment_at(vid, 99999) is None and store.find_video_segment_at(vid, -5) is None
    assert [s["segment_id"] for s in store.list_video_segments(vid, limit=2)] == ["g0", "g1"]
    assert store.get_video_transcript(vid, "fr") is None and store.list_video_segments(uid(51)) == []


def test_video_transcript_key_must_match_its_pointer(store):
    seed_video()
    typed.put(ContentVtranscript(PK=f"VIDEO#{uid(50)}", SK="TRANSCRIPT#en", language_code="en", transcript_version=2,
                                 s3_key=f"video/{uid(50)}/en/v2/{'a' * 64}.json", sha256="b" * 64, segment_count=5))
    with pytest.raises(StoreError, match="pointer"):
        store.get_video_transcript(uid(50))


# ----------------------------------------------------------------------------------------------------- cached hints

def test_cached_hint_put_is_idempotent_and_reads_are_strong(store):
    assert store.get_cached_step_hint("st1", 3, "v1") is None
    assert store.put_cached_step_hint("st1", 3, "v1", "first", "m") is True          # levels 1-5 are valid (not just 1-2)
    assert store.put_cached_step_hint("st1", 3, "v1", "second", "m2") is False       # second put is a no-op, first writer wins
    assert store.get_cached_step_hint("st1", 3, "v1") == "first"
    assert store.get_cached_step_hint("st1", 3, "v2") is None                        # prompt versions are separate
    store.put_cached_step_hint("st1", 1, "v1", "one", "m")
    store.put_cached_step_hint("st1", 2, "v1", "two", "m")
    assert store.list_cached_step_hints("st1", 3, "v1") == ["one", "two"] and store.list_cached_step_hints("st1", 1, "v1") == []
    item = typed.require(typing_hint(), "HINT#st1", "L1#v1")
    assert item.model == "m" and item.leak_checked is True and item.content_sha256 == hashlib.sha256(b"one").hexdigest()


def typing_hint():
    from mathbank_rest.models.manual.content_pedagogy import ContentHint

    return ContentHint


def test_invalidated_hint_is_ignored(store):
    store.put_cached_step_hint("st1", 1, "v1", "one", "m")
    typed.put(typing_hint()(PK="HINT#st1", SK="L1#v1", solution_step_id="st1", hint_level=1, prompt_version="v1", hint_text="old", model="m",
                            leak_checked=True, src_rev=0, content_sha256="x", created_at=NOW, invalidated_at=NOW))
    assert store.get_cached_step_hint("st1", 1, "v1") is None


def test_frozen_store_blocks_the_hint_write_but_serves_reads(store):
    store.put_cached_step_hint("st1", 1, "v1", "one", "m")
    frozen = stores.FrozenProxy("content", store)
    assert frozen.get_cached_step_hint("st1", 1, "v1") == "one"
    assert frozen.find_published_route("NO_SUCH") is None
    with pytest.raises(StoreFrozen):
        frozen.put_cached_step_hint("st1", 2, "v1", "two", "m")
    assert store.get_cached_step_hint("st1", 2, "v1") is None


class _NoState:
    """Connection double for the learner-state lookup in step_tutor.load_step_context (no attempt state yet)."""

    def execute(self, *a, **k):
        return self

    def mappings(self):
        return self

    def first(self):
        return None


def test_step_tutor_caches_hints_in_dynamodb_and_survives_a_freeze(store, no_postgres):
    seed_dag()
    typed.put(problem_item())
    typed.put(step_item(2))
    calls = []

    def writer(ctx, level, lower, stricter=False):
        calls.append(level)
        return "Think about which angle is shared by both triangles."

    with stores.override_store("content", store):
        first = step_tutor.get_or_create_hint(_NoState(), "a", "st2", 1, writer)
        again = step_tutor.get_or_create_hint(_NoState(), "a", "st2", 1, writer)
    assert first["hint_source"] == "GENERATED" and again == {"hint_text": first["hint_text"], "hint_source": "CACHED"} and calls == [1]
    with stores.override_store("content", stores.FrozenProxy("content", store)):
        frozen = step_tutor.get_or_create_hint(_NoState(), "a", "st2", 2, writer)    # the freeze must not fail the student
    assert frozen["hint_source"] == "GENERATED" and store.get_cached_step_hint("st2", 2, step_tutor.HINT_PROMPT_VERSION) is None


# ---------------------------------------------------------------- Postgres shapes on equivalent canned data

class Rows:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def __iter__(self):
        return iter(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None

    def one(self):
        return self.rows[0]

    def scalar(self):
        return next(iter(self.rows[0].values())) if self.rows else None

    def scalars(self):
        return iter([next(iter(r.values())) for r in self.rows])

    scalar_one = scalar


class CannedConn:
    """Answers the SQL of the Postgres store with canned rows, picked by a fragment of the statement."""

    def __init__(self, answers: dict[str, list[dict]]):
        self.answers = answers

    def execute(self, statement, params=None):
        sql = str(statement)
        for fragment, rows in self.answers.items():
            if fragment in sql:
                return Rows(rows)
        raise AssertionError(f"unexpected SQL: {sql[:80]}")


def test_dag_shape_equals_the_postgres_shape(store):
    seed_dag()
    ddb_dag = store.get_solution_dag(CODE)
    rows = [{**{k: s[k] for k in s}, "problem_id": PROBLEM_ID, "problem_code": CODE} for s in ddb_dag["steps"]]
    conn = CannedConn({"FROM pedagogy.solution_step s JOIN": rows, "FROM pedagogy.solution_part": ddb_dag["parts"],
                       "FROM pedagogy.solution_step_dependency": ddb_dag["dependencies"],
                       "FROM pedagogy.solution_step_technique": ddb_dag["step_techniques"]})
    assert PostgresContentStore().get_solution_dag(CODE, conn=conn) == ddb_dag


def test_hint_cache_reads_have_the_postgres_return_types(store):
    conn = CannedConn({"hint_level < :l": [{"hint_text": "one"}, {"hint_text": "two"}], "hint_level = :l": [{"hint_text": "three"}]})
    pg = PostgresContentStore()
    assert pg.get_cached_step_hint("st1", 3, "v1", conn=conn) == "three" and pg.list_cached_step_hints("st1", 3, "v1", conn=conn) == ["one", "two"]
    store.put_cached_step_hint("st1", 3, "v1", "three", "m")
    store.put_cached_step_hint("st1", 1, "v1", "one", "m")
    store.put_cached_step_hint("st1", 2, "v1", "two", "m")
    assert store.get_cached_step_hint("st1", 3, "v1") == "three" and store.list_cached_step_hints("st1", 3, "v1") == ["one", "two"]


class _PgRoutes:
    """The route tables of a Postgres holding the same release as ``seed_route``."""

    def __init__(self, rid: str):
        learner, _ = route_docs(rid)
        release = {"route_release_id": UUID(rid), "solution_id": UUID(SOLUTION_ID), "approach_summary": "SUMMARY",
                   "verification_status": "VERIFIED", "release_version": 1}
        self.conn = CannedConn({
            "FROM pedagogy.solution_route_release r JOIN core.problem": [release],
            "route_step_hint": [{"hint_text": "H1.2"}],
            "ORDER BY step_index": [{"content": {**s["instruction"], "expected_response": EXPECTED}} for s in learner["steps"]],
            "WHERE route_release_id=:r AND step_index=:i": [{"content": {**learner["steps"][0]["instruction"], "expected_response": EXPECTED}}],
        })

    @contextmanager
    def connect(self):
        yield self.conn


def test_route_plan_and_coaching_are_identical_on_both_backends(store, monkeypatch):
    rid = uid(1)
    seed_route(rid, leak=True)
    monkeypatch.setattr(route_runtime, "engine", _PgRoutes(rid))
    with stores.override_store("content", PostgresContentStore()):
        pg_plan, pg_coaching = route_runtime.plan(CODE), route_runtime.coaching(CODE, 2)
    with stores.override_store("content", store):
        ddb_plan, ddb_coaching = route_runtime.plan(CODE), route_runtime.coaching(CODE, 2)
    assert ddb_plan == pg_plan and ddb_coaching == pg_coaching
    assert ddb_plan["first_checkpoint"] == "PROMPT1" and ddb_coaching["hint"] == "H1.2" and ddb_coaching["return_prompt"] == "PROMPT1"
    assert EXPECTED not in json.dumps([ddb_plan, ddb_coaching])


def test_route_without_a_published_release_has_no_plan_or_coaching(store, no_postgres):
    with stores.override_store("content", store):
        assert route_runtime.plan(CODE) is None and route_runtime.coaching(CODE, 1) is None


class _BackendClient:
    """A TestClient that serves each request with the content store of one backend."""

    def __init__(self, client: TestClient, content_store):
        self.client, self.content_store = client, content_store

    def request(self, *a, **k):
        with stores.override_store("content", self.content_store):
            return self.client.request(*a, **k)


def test_guidance_plan_endpoint_parity(store, monkeypatch):
    rid = uid(1)
    seed_route(rid, leak=True)
    monkeypatch.setattr(route_runtime, "engine", _PgRoutes(rid))
    client = TestClient(app)
    clients = {"postgres": _BackendClient(client, PostgresContentStore()), "dynamodb": _BackendClient(client, store)}
    res = assert_parity(clients, ParityCase("published route plan", "POST", "/v1/tutor/guidance-plan", json={"problem_code": CODE}, expect_status=200))
    body = res["dynamodb"][1]
    assert body["provenance"]["source"] == "published-route" and body["route_release_id"] == rid
    assert EXPECTED not in json.dumps(body)
