"""Hand-written DynamoDB item models for the contexts that had no data when the generated models were built:
``media``, ``artifacts``, ``jobs``, ``notify`` (models/manual/*.py).

Samples come from the real migration transforms (mathbank-db/aws/dynamo/specs/media.py) fed with synthetic source
rows, post-processed like the engine does (``clean_item``, empty GSI keys dropped) and decoded like a DynamoDB read
(Decimal -> int/float). ``mb-notify`` has no migration, so its samples and the design-only item types are written by
hand from requirement 70 §13. The spec-driven samples are skipped when ``mathbank-db`` cannot be imported.
"""
from __future__ import annotations

import ast
import copy
import datetime as dt
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter

from mathbank_rest.models import base
from mathbank_rest.models.base import DdbItem, parse_item
from mathbank_rest.models.manual import artifacts, jobs, media, notify
from mathbank_rest.models.validate import same
from mathbank_rest.stores import ddb
from mathbank_rest.stores.errors import ItemSchemaError

CTXS = ("media", "artifacts", "jobs", "notify")
MODULES = {"media": media, "artifacts": artifacts, "jobs": jobs, "notify": notify}
DB_ROOT = Path(__file__).resolve().parents[2] / "mathbank-db"
GEOMETRY_TRANSFORMS = {"t_scene", "t_scenever", "t_receipt", "t_run"}


def _u() -> uuid.UUID:
    return uuid.uuid4()


def _ts(day: int, micro: int = 123456) -> dt.datetime:
    return dt.datetime(2026, 10, day, 12, 30, 15, micro, tzinfo=dt.UTC)


def _z(day: int) -> str:
    return f"2026-10-{day:02d}T12:30:15.123456Z"


def _sha(c: str = "a") -> str:
    return c * 64


REF = {"bucket": "mathbank-data-dev-123456789012", "key": "offload/x/y/attr.json", "sha256": _sha("b"),
       "bytes": 20000, "content_type": "application/json"}


# ------------------------------------------------------------------ spec loading

def _load_specs():
    sys.path.insert(0, str(DB_ROOT))
    try:
        from aws import common
        from aws.dynamo.specs import media as media_spec
        from aws.dynamo.specs import staff as staff_spec
    except ImportError:
        return None
    finally:
        sys.path.remove(str(DB_ROOT))
    return common, media_spec, staff_spec


SPECS = _load_specs()


def _emit(transform, row: dict) -> list[dict]:
    """What lands in DynamoDB: the engine's clean_item + sparse-GSI rule, read back through ``ddb.decode``."""
    common = SPECS[0]
    out = []
    for raw in transform(row) or ():
        item = common.clean_item(raw)
        for k in [k for k in item if k.startswith("GSI") and k.endswith(("PK", "SK"))]:
            if item[k] in ("", None):
                del item[k]
        out.append(ddb.decode(item))
    return out


# ------------------------------------------------------------------ synthetic source rows

def _media_samples(m) -> list[tuple[str, str, dict]]:
    sid, student, problem, tv = _u(), _u(), _u(), 2
    step_ids, region_ids = [_u(), _u()], [_u(), _u(), _u()]
    asset_id = _u()
    out: list[tuple[str, str, dict]] = []

    def add(label: str, transform, row: dict) -> None:
        for i, item in enumerate(_emit(transform, row)):
            out.append(("media", f"{label}-{item['type']}", item))

    submission = {"submission_id": sid, "student_id": student, "problem_id": problem, "canonical_code": "ALG-001",
                  "status": "TRANSCRIPTION_READY", "transcription_version": tv, "approved_version": 1,
                  "last_sequence": 14, "error_code": None, "created_at": _ts(1), "updated_at": _ts(2, 7),
                  "active_original_count": 2}
    add("a", m.t_submission, submission)
    add("failed", m.t_submission, {**submission, "submission_id": _u(), "status": "FAILED", "canonical_code": None,
                                   "error_code": "OCR_TIMEOUT", "approved_version": 0})
    asset = {"media_asset_id": asset_id, "submission_id": sid, "student_id": student, "role": "ORIGINAL",
             "parent_asset_id": None, "asset_type": "IMAGE", "object_key": f"{sid}/original.png",
             "mime_type": "image/png", "sha256": _sha("c"), "size_bytes": 482113, "page_count": None,
             "duration_ms": None, "timestamp_ms": None, "retention_class": "RAW_MEDIA", "purged_at": None,
             "created_at": _ts(1)}
    add("orig", m.t_asset, asset)
    add("page", m.t_asset, {**asset, "media_asset_id": _u(), "role": "PAGE", "asset_type": "PDF", "page_count": 3,
                            "parent_asset_id": asset_id, "purged_at": _ts(9), "duration_ms": 1500, "timestamp_ms": 0})
    steps = [{"step_id": str(step_ids[0]), "ordinal": 1, "plain_text": "x+1=2", "latex_text": "x+1=2",
              "step_type": "EQUATION", "confidence": 0.93, "evidence_ids": [str(region_ids[0])]},
             {"step_id": str(step_ids[1]), "ordinal": 2, "plain_text": "x=1", "latex_text": "x=1",
              "step_type": "RESULT", "confidence": 1.0, "evidence_ids": [str(region_ids[1]), str(region_ids[2])]}]
    regions = [{"region_id": str(region_ids[0]), "media_asset_id": str(asset_id), "page_number": 1, "x_norm": 0.1,
                "y_norm": 0.25, "width_norm": 0.5, "height_norm": 0.125, "start_ms": None, "end_ms": None,
                "region_type": "LINE", "reading_order": 0, "confidence": 0.9, "first_version": 1},
               {"region_id": str(region_ids[1]), "media_asset_id": str(asset_id), "page_number": None,
                "x_norm": None, "y_norm": None, "width_norm": None, "height_norm": None, "start_ms": 100,
                "end_ms": 900, "region_type": "SPEECH", "reading_order": 1, "confidence": 1.0, "first_version": 2}]
    transcript = {"submission_id": sid, "student_id": student, "version": 1, "source": "MACHINE",
                  "machine_output": {"model": "m1", "blocks": [{"t": "x+1=2"}], "score": 0.5},
                  "model_profile": "ocr-v1", "created_at": _ts(1, 5), "steps": steps, "regions": regions}
    add("machine", m.t_transcript, transcript)
    add("student", m.t_transcript, {**transcript, "version": 2, "source": "STUDENT", "machine_output": None,
                                    "model_profile": None})
    attempt = _u()
    add("appr", m.t_approval, {"submission_id": sid, "student_id": student, "approved_version": 1,
                               "transcription_version": tv, "learner_attempt_id": attempt, "approved_at": _ts(3),
                               "student_edit_summary": "fixed the second line"})
    assessments = [{"assessment_id": str(_u()), "step_id": str(step_ids[0]), "assessment_version": 1,
                    "correctness": "CORRECT", "alignment_type": "MATCH", "canonical_solution_step_id": "SS-1",
                    "confidence": 0.8, "why": "valid move", "failure_mode": "NONE", "next_action": "continue",
                    "evidence_ids": [str(region_ids[0])], "model_profile": "grader-v2",
                    "created_at": "2026-10-03T12:30:15.123456Z"},
                   {"assessment_id": str(_u()), "step_id": str(step_ids[1]), "assessment_version": 2,
                    "correctness": "UNCERTAIN", "alignment_type": "UNMATCHED", "canonical_solution_step_id": None,
                    "confidence": 1.0, "why": "?", "failure_mode": "NONE", "next_action": "ask",
                    "evidence_ids": [], "model_profile": "grader-v2", "created_at": "2026-10-03T12:30:16.000000Z"}]
    run = {"submission_id": sid, "student_id": student, "transcription_version": tv, "run_no": 1, "source": "AI",
           "actor_id": "grader", "approved_version": 1, "created_at": _ts(3, 9), "assessments": assessments}
    add("ai", m.t_asmtrun, run)
    add("staff", m.t_asmtrun, {**run, "run_no": 2, "source": "INSTRUCTOR", "actor_id": "admin-key:k1"})
    events = [{"sequence": 13, "event_type": "TRANSCRIPT_EDITED", "transcription_version": 2, "approved_version": 1,
               "payload": {"step": 1, "text": "x=1", "ratio": 0.25}, "created_at": "2026-10-04T12:30:15.123456Z"},
              {"sequence": 14, "event_type": "ANALYZED", "transcription_version": 2, "approved_version": 1,
               "payload": {}, "created_at": "2026-10-04T12:30:15.123456Z"}]
    add("evt", m.t_evtblock, {"submission_id": sid, "student_id": student, "first_seq": 13, "last_seq": 14,
                              "events": events})
    return out


def _artifact_samples(m) -> list[tuple[str, str, dict]]:
    out: list[tuple[str, str, dict]] = []

    def add(label: str, transform, row: dict) -> None:
        for item in _emit(transform, row):
            out.append(("artifacts", f"{label}-{item['type']}", item))

    owner, rid, bid, root, asset, manifest = _u(), _u(), _u(), _u(), _u(), _u()
    req = {"artifact_request_id": rid, "owner_student_id": owner, "created_by": "student", "request_source": "TUTOR",
           "subject": "GEOMETRY", "topic": "triangles", "subtopic": None, "goal_type": "EXPLAIN",
           "linked_problem_id": _u(), "linked_solution_step_id": "SS-4", "status": "REQUESTED",
           "created_at": _ts(5), "bundle_id": None,
           "spec": {"goal": "show the proof", "frames": [{"n": 1, "ratio": 0.5}]}}
    add("learner", m.t_artreq, req)
    add("staff", m.t_artreq, {**req, "artifact_request_id": _u(), "owner_student_id": None, "created_by": "admin",
                              "subtopic": "similarity", "linked_problem_id": None, "linked_solution_step_id": None,
                              "status": "GENERATED", "bundle_id": bid})
    bundle = {
        "artifact_bundle_id": bid, "artifact_request_id": rid, "parent_bundle_id": None, "root_bundle_id": root,
        "subject": "GEOMETRY", "topic": "triangles", "subtopic": None, "title": "Similar triangles",
        "summary": "A walk-through", "difficulty_band": "EASY", "grade_band": "G8_9", "status": "PUBLISHED",
        "version": 2, "created_by_agent": "artifact-agent", "rule_profile_id": "rp1", "annotation_profile_id": "ap1",
        "search_text": "similar triangles proof", "metadata": {"k": [1, 2.5], "nested": {"a": None}},
        "created_at": _ts(6), "published_at": _ts(7), "is_request_sentinel": True, "is_root_version_sentinel": True,
        "owner_student_id": owner, "spec": req["spec"], "generator_version": "g1", "source_spec_sha256": _sha("d"),
        "manifest_asset_id": manifest, "ordered_overlay_ids": [_u(), _u()], "embedding_model": "te3small",
        "embedding_dimensions": 1536, "embedding_search_text_sha256": _sha("e"), "embedding_indexed_at": _ts(8),
        "child_count": 3,
        "assets": [{"artifact_asset_id": str(asset), "asset_type": "SVG_DIAGRAM", "object_key": "a" * 32 + ".svg",
                    "sha256": _sha("f"), "size_bytes": 1200, "mime_type": "image/svg+xml", "render_format": "svg",
                    "width": 640, "height": None, "element_ids": ["p1", "p2"],
                    "created_at": "2026-10-06T12:30:15.123456Z"}],
        "asset_types": ["SVG_DIAGRAM"],
        "tags": {"concept": ["similarity"], "skill": [], "theorem": ["AA"]},
    }
    add("pub", m.t_bundle, bundle)
    add("draft", m.t_bundle, {**bundle, "artifact_bundle_id": _u(), "status": "DRAFT", "parent_bundle_id": bid,
                              "version": 1, "published_at": None, "embedding_model": None, "metadata": {},
                              "is_request_sentinel": False, "is_root_version_sentinel": False,
                              "generator_version": None, "source_spec_sha256": None, "manifest_asset_id": None,
                              "ordered_overlay_ids": None, "assets": [], "asset_types": [], "search_text": None,
                              "tags": {"concept": [], "skill": [], "theorem": []}, "child_count": 0})
    add("tag", m.t_bundletag, {"artifact_bundle_id": bid, "tag_type": "theorem", "tag": "AA", "status": "PUBLISHED",
                               "subject": "GEOMETRY", "difficulty_band": "EASY", "asset_types": ["SVG_DIAGRAM"],
                               "created_at": _ts(6)})
    add("val", m.t_validation, {"artifact_bundle_id": bid, "validation_result_id": _u(), "valid": False,
                                "validator_version": "v3", "report": {"errors": [{"code": "E1", "w": 0.5}]},
                                "created_at": _ts(7, 1)})
    return out


def _job_samples(m) -> list[tuple[str, str, dict]]:
    out: list[tuple[str, str, dict]] = []
    research = {"scene_research_job_id": _u(), "status": "DONE", "topic": "Pythagoras",
                "context_json": {"grade": 8, "tags": ["a"]}, "result_scene_spec": {"scene": {"w": 1.5}},
                "result_explanation": "because", "error_message": None, "created_at": _ts(20), "updated_at": _ts(20, 9),
                "expires_at": _ts(21), "live": True}
    render = {"video_render_job_id": _u(), "status": "DONE", "source_research_job_id": research["scene_research_job_id"],
              "scene_spec_json": {"scene": {"w": 2}}, "video_object_key": "manim-studio/v.mp4",
              "video_duration_ms": 8200, "error_message": None, "created_at": _ts(20), "updated_at": _ts(20, 9),
              "expires_at": _ts(21), "promoted_scene_spec_id": _u(), "live": True}
    for label, transform, row in (
        ("done", lambda r: m._job(r, "RESEARCH", "scene_research_job_id"), research),
        ("failed", lambda r: m._job(r, "RESEARCH", "scene_research_job_id"),
         {**research, "scene_research_job_id": _u(), "status": "FAILED", "result_scene_spec": None,
          "result_explanation": None, "error_message": "boom", "context_json": {}}),
        ("done", lambda r: m._job(r, "RENDER", "video_render_job_id"), render),
        ("pending", lambda r: m._job(r, "RENDER", "video_render_job_id"),
         {**render, "video_render_job_id": _u(), "status": "PENDING", "source_research_job_id": None,
          "video_object_key": None, "video_duration_ms": None, "promoted_scene_spec_id": None}),
        ("failed", lambda r: m._job(r, "RENDER", "video_render_job_id"),
         {**render, "video_render_job_id": _u(), "status": "FAILED", "video_object_key": None,
          "video_duration_ms": None, "promoted_scene_spec_id": None, "error_message": "render crashed"}),
    ):
        for item in _emit(transform, row):
            out.append(("jobs", f"{label}-{item['type']}", item))
    return out


# ------------------------------------------------------------------ hand-written samples (no migration emits them)

def _handwritten_samples() -> list[tuple[str, str, dict]]:
    sid, nid, nid2, other = _u(), _u(), _u(), _u()
    notification = {
        "PK": f"RCPT#STUDENT#{sid}", "SK": f"N#{nid}", "type": "NOTIFICATION",
        "GSI1PK": f"UNREAD#STUDENT#{sid}", "GSI1SK": f"N#{nid}", "notification_id": str(nid),
        "recipient_type": "STUDENT", "recipient_id": str(sid), "notification_type": "QUIZ_GRADED",
        "severity": "SUCCESS", "title": "Your quiz was graded", "body": "Score: 80%",
        "payload": {"quiz_id": str(other), "is_correct": True}, "dedupe_key": f"mb-quiz#QUIZ#{other}#RESP#1#3",
        "created_at": _z(10), "ttl": 1_800_000_000}
    admin = {"PK": "RCPT#ADMIN", "SK": f"N#{nid2}", "type": "NOTIFICATION", "notification_type": "ADMIN_REVIEW_NEEDED",
             "severity": "ACTION_NEEDED", "title": "Release ready", "payload": {"release_id": "R1"},
             "read_at": _z(11), "acknowledged_by": "admin-key:k1", "created_at": _z(10), "ttl": 1_800_000_000}
    items = [
        ("notify", "student-NOTIFICATION", notification),
        ("notify", "admin-NOTIFICATION", admin),
        ("notify", "DEDUPE", {"PK": f"RCPT#STUDENT#{sid}", "SK": f"DEDUPE#mb-quiz#QUIZ#{other}#RESP#1#3",
                              "type": "DEDUPE", "notification_id": str(nid), "ttl": 1_800_000_000}),
        ("notify", "INBOX_COUNTER", {"PK": f"RCPT#STUDENT#{sid}", "SK": "COUNTER", "type": "INBOX_COUNTER",
                                     "unread_count": 4, "version": 7}),
        ("media", "design-AUDIT", {"PK": "AUDIT#MEDIA#202610", "SK": f"{_z(12)}#{_u()}", "type": "AUDIT",
                                   "actor": "admin-key:k1", "action": "PURGE_ASSET", "target": "SUBMISSION#x",
                                   "before_sha256": _sha("1"), "after_sha256": _sha("2")}),
        ("artifacts", "design-AUDIT", {"PK": "AUDIT#ARTIFACTS#202610", "SK": f"{_z(12)}#{_u()}", "type": "AUDIT",
                                      "actor": "admin-key:k1", "action": "PUBLISH", "target": f"BUNDLE#{_u()}"}),
        ("artifacts", "design-RATE", {"PK": f"RATE#STUDENT#{sid}", "SK": "EMBED#2026100912", "type": "RATE",
                                      "count": 2, "ttl": 1_800_000_000}),
    ]
    return items


def _all_samples() -> list[tuple[str, str, dict]]:
    out = _handwritten_samples()
    if SPECS:
        out += _media_samples(SPECS[1]) + _artifact_samples(SPECS[1]) + _job_samples(SPECS[1])
    return out


SAMPLES = _all_samples()
SAMPLE_PARAMS = [pytest.param(ctx, item, id=f"{ctx}/{label}") for ctx, label, item in SAMPLES]


def _offload_params() -> list[Any]:
    base._load_models()
    out = []
    for ctx, label, item in SAMPLES:
        model = base.ITEM_MODELS[(ctx, item["type"])]
        for attr in sorted(model.OFFLOADED):
            if attr in item:
                out.append(pytest.param(ctx, item, attr, id=f"{ctx}/{label}/{attr}"))
    return out


OFFLOAD_PARAMS = _offload_params()


def _need_specs() -> None:
    if SPECS is None:
        pytest.importorskip("aws.dynamo.specs.media")
        pytest.skip("mathbank-db specs not importable")


def _break(item: dict, key: str, prefix: str) -> dict:
    return {**item, key: prefix + item[key]}


# ------------------------------------------------------------------ registry and exports

def test_every_context_item_type_is_registered_and_exported():
    base._load_models()
    for ctx, mod in MODULES.items():
        registered = {t: m for (c, t), m in base.ITEM_MODELS.items() if c == ctx}
        assert registered, ctx
        assert {m.TYPE for m in mod.ITEM_MODELS} == set(registered)
        for m in mod.ITEM_MODELS:
            assert registered[m.TYPE] is m and m.CTX == ctx and issubclass(m, DdbItem)
            assert m.model_fields["type"].default == m.TYPE
        union = getattr(mod, f"{ctx.capitalize()}Item")
        adapter = TypeAdapter(union)
        for c, item in ((c, i) for c, _, i in SAMPLES if c == ctx):
            assert type(adapter.validate_python(item)) is registered[item["type"]]


def test_expected_item_types_per_context():
    base._load_models()
    got = {c: {t for (cc, t) in base.ITEM_MODELS if cc == c} for c in CTXS}
    assert got["media"] == {"SUBMISSION", "SUBREF", "ASSET", "TRANSCRIPT", "APPROVAL", "TXAPPROVED", "LATTEMPTREF",
                            "ASMTRUN", "EVTBLOCK", "AUDIT"}
    assert got["artifacts"] == {"ARTREQ", "BUNDLE", "BUNDLETAG", "UNIQUE", "VALIDATION", "AUDIT", "RATE"}
    assert got["jobs"] == {"RESEARCHJOB", "RENDERJOB"}
    assert got["notify"] == {"NOTIFICATION", "DEDUPE", "INBOX_COUNTER"}


def test_every_item_type_has_a_sample():
    base._load_models()
    sampled = {(c, i["type"]) for c, _, i in SAMPLES}
    missing = {k for k in base.ITEM_MODELS if k[0] in CTXS} - sampled
    if SPECS is None:  # only the hand-written samples exist
        missing = {k for k in missing if k[0] == "notify" or k[1] in {"AUDIT", "RATE"}}
    assert not missing


# ------------------------------------------------------------------ per-item behaviour

@pytest.mark.parametrize(("ctx", "item"), SAMPLE_PARAMS)
def test_from_item_round_trips_losslessly_and_parse_item_picks_the_model(ctx, item):
    model = base.model_for(ctx, item["type"])
    inst = model.from_item(item)
    assert not inst.model_extra, inst.model_extra
    assert same(item, inst.to_item()), (item, inst.to_item())
    assert same(inst.to_item(), model.from_item(inst.to_item()).to_item())
    assert type(parse_item(ctx, item)) is model


@pytest.mark.parametrize(("ctx", "item"), SAMPLE_PARAMS)
def test_wrong_key_prefix_is_rejected(ctx, item):
    model = base.model_for(ctx, item["type"])
    for key in ("PK", "SK"):
        with pytest.raises(ItemSchemaError):
            model.from_item(_break(item, key, "X#"))
    with pytest.raises(ItemSchemaError):
        model.from_item({**item, "PK": item["PK"] + "#"})


@pytest.mark.parametrize(("ctx", "item"), SAMPLE_PARAMS)
def test_undeclared_attributes_are_kept_on_read_but_rejected_on_write(ctx, item):
    model = base.model_for(ctx, item["type"])
    inst = model.from_item({**item, "surprise": 1})
    assert inst.model_extra == {"surprise": 1}
    with pytest.raises(ItemSchemaError):
        inst.to_item()


@pytest.mark.parametrize(("ctx", "item", "attr"), OFFLOAD_PARAMS)
def test_inline_and_ref_together_is_rejected_and_offloaded_form_round_trips(ctx, item, attr):
    model = base.model_for(ctx, item["type"])
    assert attr in model.OFFLOADED and f"{attr}_ref" in model.model_fields
    with pytest.raises(ItemSchemaError):
        model.from_item({**item, f"{attr}_ref": REF})
    offloaded = {k: v for k, v in item.items() if k != attr} | {f"{attr}_ref": REF}
    inst = model.from_item(offloaded)
    assert same(offloaded, inst.to_item())
    assert inst.ref(attr).bytes == REF["bytes"]


def test_every_offloadable_attribute_is_exercised_inline_by_a_sample():
    base._load_models()
    seen = {(c, i["type"], a) for c, i, a in ((p.values[0], p.values[1], p.values[2]) for p in OFFLOAD_PARAMS)}
    for (ctx, typ), model in base.ITEM_MODELS.items():
        if ctx in CTXS:
            for attr in model.OFFLOADED:
                if SPECS is None and ctx != "notify":
                    continue
                assert (ctx, typ, attr) in seen, (ctx, typ, attr)


def test_strict_scalar_types_are_enforced():
    item = next(i for c, _, i in SAMPLES if c == "notify" and i["type"] == "INBOX_COUNTER")
    for bad in ({"unread_count": "4"}, {"unread_count": -1}, {"unread_count": True}, {"unread_count": 1.5}):
        with pytest.raises(ItemSchemaError):
            notify.NotifyInboxCounter.from_item({**item, **bad})
    n = next(i for c, _, i in SAMPLES if c == "notify" and i["type"] == "NOTIFICATION")
    for bad in ({"severity": "LOUD"}, {"notification_type": "NOPE"}, {"title": 5}, {"created_at": "yesterday"},
                {"payload": {"quiz_id": 5}}, {"recipient_type": "TEACHER"}):
        with pytest.raises(ItemSchemaError):
            notify.NotifyNotification.from_item({**n, **bad})


def test_nested_documents_are_typed():
    _need_specs()
    tx = next(i for c, _, i in SAMPLES if c == "media" and i["type"] == "TRANSCRIPT" and i.get("machine_output"))
    inst = media.MediaTranscript.from_item(tx)
    assert isinstance(inst.steps[0], media.MediaTranscriptStep) and isinstance(inst.regions[0], media.MediaTranscriptRegion)
    bad = copy.deepcopy(tx)
    bad["steps"][0]["step_id"] = "not-a-uuid"
    with pytest.raises(ItemSchemaError):
        media.MediaTranscript.from_item(bad)
    bundle = next(i for c, _, i in SAMPLES if c == "artifacts" and i["type"] == "BUNDLE" and "embedding" in i)
    inst = artifacts.ArtifactsBundle.from_item(bundle)
    assert inst.tags.theorem == ["AA"] and inst.embedding.dimensions == 1536 and inst.assets[0].bucket


def test_design_only_attributes_are_accepted():
    _need_specs()
    research = next(i for c, _, i in SAMPLES if c == "jobs" and i["type"] == "RESEARCHJOB")
    extra = {"claim_token": "t", "lease_until": _z(21), "requested_by": "admin", "attempts": 1}
    assert same({**research, **extra}, jobs.JobsResearchjob.from_item({**research, **extra}).to_item())
    bundle = next(i for c, _, i in SAMPLES if c == "artifacts" and i["type"] == "BUNDLE")
    extra = {"status": "RETIRED", "retired_by": "admin", "retired_at": _z(15), "retired_reason": "dup",
             "published_by": "admin"}
    assert same({**bundle, **extra}, artifacts.ArtifactsBundle.from_item({**bundle, **extra}).to_item())


# ------------------------------------------------------------------ spec coverage

def _static_types(src: str) -> dict[str, set[str]]:
    """``"type": "<X>"`` literals (and ``_job(row, "<KIND>", ...)`` calls) per spec transform function."""
    tree = ast.parse(src)
    found: dict[str, set[str]] = {}
    for fn in (n for n in tree.body if isinstance(n, ast.FunctionDef)):
        for node in ast.walk(fn):
            if isinstance(node, ast.Dict):
                for k, v in zip(node.keys, node.values, strict=True):
                    if isinstance(k, ast.Constant) and k.value == "type" and isinstance(v, ast.Constant):
                        found.setdefault(fn.name, set()).add(v.value)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_job"
                and len(node.args) > 1 and isinstance(node.args[1], ast.Constant)):
            found.setdefault("_job", set()).add(f"{node.args[1].value}JOB")
    return found


def test_every_type_the_spec_emits_has_a_registered_model():
    _need_specs()
    media_spec = SPECS[1]
    base._load_models()
    per_fn = _static_types(Path(media_spec.__file__).read_text())
    emitted = {t for fn, ts in per_fn.items() if fn not in GEOMETRY_TRANSFORMS for t in ts}
    assert {"SUBMISSION", "SUBREF", "ASSET", "TRANSCRIPT", "APPROVAL", "TXAPPROVED", "LATTEMPTREF", "ASMTRUN",
            "EVTBLOCK", "ARTREQ", "BUNDLE", "UNIQUE", "BUNDLETAG", "VALIDATION", "RESEARCHJOB",
            "RENDERJOB"} <= emitted
    table_of = {}
    for mp in media_spec.MEDIA + media_spec.ARTIFACTS + media_spec.JOBS:
        table_of[mp.table] = True
    assert set(table_of) == {"media", "artifacts", "jobs"}
    registered = {t for (c, t) in base.ITEM_MODELS if c in ("media", "artifacts", "jobs")}
    assert emitted <= registered, emitted - registered
    sampled = {i["type"] for c, _, i in SAMPLES if c in ("media", "artifacts", "jobs")}
    assert emitted <= sampled, f"no sample exercises {emitted - sampled}"


def test_offload_policy_of_the_spec_matches_the_models():
    _need_specs()
    media_spec, staff_spec = SPECS[1], SPECS[2]
    base._load_models()
    policy = {**media_spec.OFFLOAD, **staff_spec.OFFLOAD}
    for (ctx, typ), attrs in policy.items():
        if ctx in ("media", "artifacts", "jobs", "notify"):
            assert base.ITEM_MODELS[(ctx, typ)].OFFLOADED == frozenset(attrs), (ctx, typ)


def test_notify_has_no_migration_mapping():
    _need_specs()
    assert [m.name for m in SPECS[2].MAPPINGS if m.table == "notify"] == []
