"""C4 — learner media, artifacts, geometry scenes and Studio jobs → mb-media, mb-artifacts, mb-geometry, mb-jobs.

Design: documentation/requirements/70_DYNAMODB_AND_S3_VECTORS_ADOPTION_PLAN.md §13 (C4).

Existing object-store bytes (attempt media, artifact assets, geometry frames/svgs/evidence, studio videos) stay
where they are: items carry descriptors {bucket, object_key, sha256, size_bytes}, never the bytes. Large JSON
payloads (student transcripts/edits, assessments, event payloads, model output, artifact specs/reports/search
text, scene lineage, job bodies) are declared in OFFLOAD and moved to S3 by the engine (<attr>_ref).

Mappings named "<schema>.<table>" read every source row exactly once (row counts checked). Child tables
that are embedded into an aggregate item are read by a count-only mapping that emits nothing and raises if a
row would not be embedded (no silent loss); the aggregate itself has a distinct "#..." name.
"""
from __future__ import annotations

import os
import uuid

from ...common import json_bytes, sha256, to_ddb
from ..spec import Mapping, Table, epoch, iso, s, ttl_after

_SUBMISSION_LIST = ("submission_id", "problem_id", "canonical_code", "status", "transcription_version",
                    "approved_version", "created_at")

TABLES = [
    Table("media", gsis=("GSI1", "GSI2"), stream=True, ttl=True,
          include_gsis=(("GSI1", _SUBMISSION_LIST),
                        ("GSI2", _SUBMISSION_LIST + ("student_id", "error_code"))),
          description="attempt_media: SUBMISSION/SUBREF/ASSET/TRANSCRIPT/APPROVAL/LATTEMPTREF/ASMTRUN/EVTBLOCK"),
    Table("artifacts", gsis=("GSI1", "GSI2"), stream=True, ttl=True,
          include_gsis=(("GSI2", ("subject", "topic", "title", "summary", "status", "owner_student_id",
                                  "difficulty_band", "asset_types")),),
          description="artifact_runtime: ARTREQ/BUNDLE/BUNDLETAG/UNIQUE/VALIDATION"),
    Table("geometry", gsis=("GSI1", "GSI2"), stream=True, ttl=True,
          include_gsis=(("GSI1", ("scene_id", "current_version", "created_at", "run_id", "review", "status")),
                        ("GSI2", ("owner", "run_id", "created_at", "review", "status"))),
          description="geometry_scene: SCENE/SCENEVER/RECEIPT/RUN/RUNREVIEW"),
    Table("jobs", gsis=("GSI1",), stream=True, ttl=True,
          description="studio: RESEARCHJOB/RENDERJOB"),
]

# Engine-managed S3 offload (> MB_OFFLOAD_THRESHOLD → <attr>_ref); STUDENT# items land under students/<sid>/.
OFFLOAD = {
    ("media", "TRANSCRIPT"): ("steps", "regions", "machine_output"),       # student transcript + model output
    ("media", "APPROVAL"): ("student_edit_summary",),                      # student-entered text
    ("media", "ASMTRUN"): ("assessments",),                                # grader output: why/next_action/evidence
    ("media", "EVTBLOCK"): ("events",),                                    # event payloads
    ("artifacts", "ARTREQ"): ("spec",),                                    # learner/staff-submitted artifact plan
    ("artifacts", "BUNDLE"): ("source_spec", "search_text", "metadata", "assets"),
    ("artifacts", "VALIDATION"): ("report",),
    ("geometry", "SCENEVER"): ("lineage", "assets"),
    ("geometry", "RUN"): ("review",),
    ("geometry", "RUNREVIEW"): ("review", "note"),
    ("jobs", "RESEARCHJOB"): ("context_json", "result_scene_spec", "result_explanation", "error_message"),
    ("jobs", "RENDERJOB"): ("scene_spec_json", "error_message"),
}

OBJECT_BUCKET = os.environ.get("MATHBANK_OBJECT_BUCKET") or os.environ.get("AWS_BUCKET_NAME") or "mathbank-runtime"
RECEIPT_TTL_DAYS = 30
RUN_TTL_DAYS = 180
ARTIFACT_INDEX = {"PUBLISHED": "artifact-public-te3small-1536-v1", "DRAFT": "artifact-private-te3small-1536-v1"}


def TS(col: str) -> str:
    """SQL expression rendering a timestamptz exactly like spec.iso() (UTC, microseconds, 'Z')."""
    return f"to_char(({col}) AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"')"


def pad(n, width: int) -> str:
    return str(int(n)).zfill(width)


def _bytes(body) -> bytes:
    return json_bytes(to_ddb(body))


def _obj(desc, **extra) -> dict | None:
    """Existing object-store descriptor + bucket (bytes are not copied)."""
    if desc is None:
        return None
    return {"bucket": OBJECT_BUCKET, **desc, **extra}


def _orphan(name: str, row: dict):
    raise ValueError(f"{name}: source row would not be embedded in any item (orphan): {row}")


# ======================================================================== mb-media (attempt_media.*)

def _student(row) -> str:
    return f"STUDENT#{row['student_id']}"


def t_submission(row):
    sid, pk, created = s(row["submission_id"]), _student(row), iso(row["created_at"])
    head = {
        "PK": pk, "SK": f"SUBMISSION#{sid}", "type": "SUBMISSION",
        "GSI1PK": f"{pk}#SUBMISSIONS", "GSI1SK": f"{created}#{sid}",
        "GSI2PK": f"SUBMISSIONS#{row['status']}", "GSI2SK": f"{created}#{sid}",
        "submission_id": sid, "student_id": row["student_id"], "problem_id": row["problem_id"],
        "canonical_code": row["canonical_code"], "status": row["status"],
        "transcription_version": row["transcription_version"], "approved_version": row["approved_version"],
        "last_sequence": row["last_sequence"], "active_original_count": row["active_original_count"],
        "error_code": row["error_code"], "version": 1, "created_at": row["created_at"], "updated_at": row["updated_at"],
    }
    ref = {"PK": f"SUBMISSION#{sid}", "SK": "REF", "type": "SUBREF", "owner_pk": pk, "student_id": row["student_id"]}
    return [head, ref]


def t_asset(row):
    sid = s(row["submission_id"])
    return [{
        "PK": _student(row), "SK": f"SUBMISSION#{sid}#ASSET#{row['media_asset_id']}", "type": "ASSET",
        "submission_id": sid, "media_asset_id": row["media_asset_id"], "role": row["role"],
        "parent_asset_id": row["parent_asset_id"], "asset_type": row["asset_type"], "bucket": OBJECT_BUCKET,
        "object_key": row["object_key"], "mime_type": row["mime_type"], "sha256": row["sha256"],
        "size_bytes": row["size_bytes"], "page_count": row["page_count"], "duration_ms": row["duration_ms"],
        "timestamp_ms": row["timestamp_ms"], "retention_class": row["retention_class"],
        "purged_at": row["purged_at"], "created_at": row["created_at"],
    }]


def t_transcript(row):
    sid, v = s(row["submission_id"]), row["version"]
    item = {
        "PK": _student(row), "SK": f"SUBMISSION#{sid}#TX#{pad(v, 8)}", "type": "TRANSCRIPT",
        "submission_id": sid, "version": v, "source": row["source"], "model_profile": row["model_profile"],
        "created_at": row["created_at"],
    }
    item["body_sha256"] = sha256(_bytes({"steps": row["steps"], "regions": row["regions"]}))
    item.update(steps=row["steps"], regions=row["regions"], machine_output=row["machine_output"])
    return [item]


def t_approval(row):
    sid, pk = s(row["submission_id"]), _student(row)
    av, tv = row["approved_version"], row["transcription_version"]
    return [
        {"PK": pk, "SK": f"SUBMISSION#{sid}#APPROVAL#{pad(av, 8)}", "type": "APPROVAL", "submission_id": sid,
         "approved_version": av, "transcription_version": tv, "learner_attempt_id": row["learner_attempt_id"],
         "approved_at": row["approved_at"], "student_edit_summary": row["student_edit_summary"]},
        {"PK": pk, "SK": f"SUBMISSION#{sid}#UNIQUE#approved_tv#{pad(tv, 8)}", "type": "TXAPPROVED",
         "submission_id": sid, "approved_version": av},
        {"PK": f"LATTEMPT#{row['learner_attempt_id']}", "SK": "REF", "type": "LATTEMPTREF", "owner_pk": pk,
         "submission_id": sid, "approved_version": av, "transcription_version": tv},
    ]


def t_asmtrun(row):
    sid, tv, run = s(row["submission_id"]), row["transcription_version"], row["run_no"]
    item = {
        "PK": _student(row), "SK": f"SUBMISSION#{sid}#ASMT#{pad(tv, 8)}#{pad(run, 8)}", "type": "ASMTRUN",
        "submission_id": sid, "transcription_version": tv, "run": run, "source": row["source"],
        "actor_type": "STAFF" if row["source"] == "INSTRUCTOR" else "SYSTEM", "actor_id": row["actor_id"],
        "approved_version": row["approved_version"], "assessments": row["assessments"],
        "created_at": row["created_at"],
    }
    return [item]


def t_evtblock(row):
    sid = s(row["submission_id"])
    return [{
        "PK": _student(row), "SK": f"SUBMISSION#{sid}#EVT#{pad(row['last_seq'], 12)}", "type": "EVTBLOCK",
        "submission_id": sid, "first_seq": row["first_seq"], "last_seq": row["last_seq"], "events": row["events"],
    }]


def count_only(name: str):
    def t(row):
        if not row.get("embedded", True):
            _orphan(name, row)
        return []
    return t


_SUB = "JOIN attempt_media.submission s ON s.submission_id = x.submission_id"

MEDIA = [
    Mapping("attempt_media.submission", "media", f"""
        SELECT s.submission_id, s.student_id, s.problem_id, p.canonical_code, s.status, s.transcription_version,
               s.approved_version, s.last_sequence, s.error_code, s.created_at, s.updated_at,
               (SELECT count(*) FROM attempt_media.media_asset a
                 WHERE a.submission_id = s.submission_id AND a.role = 'ORIGINAL' AND a.purged_at IS NULL)
                 AS active_original_count
          FROM attempt_media.submission s
          LEFT JOIN core.problem p ON p.problem_id = s.problem_id
         ORDER BY s.submission_id""", t_submission, expected_source="attempt_media.submission",
            note="SUBMISSION head + SUBREF pointer; canonical_code denormalised; active_original_count computed"),
    Mapping("attempt_media.media_asset", "media", f"""
        SELECT x.media_asset_id, x.submission_id, s.student_id, x.role, x.parent_asset_id, x.asset_type,
               x.object_key, x.mime_type, x.sha256, x.size_bytes, x.page_count, x.duration_ms, x.timestamp_ms,
               x.retention_class, x.purged_at, x.created_at
          FROM attempt_media.media_asset x {_SUB}
         ORDER BY x.submission_id, x.media_asset_id""", t_asset, expected_source="attempt_media.media_asset"),
    Mapping("attempt_media.transcription_candidate", "media", f"""
        SELECT x.submission_id, s.student_id, x.version, x.source, x.machine_output, x.model_profile, x.created_at,
               COALESCE((
                 SELECT json_agg(json_build_object(
                          'step_id', sc.step_id, 'ordinal', sc.ordinal, 'plain_text', sc.plain_text,
                          'latex_text', sc.latex_text, 'step_type', sc.step_type, 'confidence', sc.confidence,
                          'evidence_ids', COALESCE((
                             SELECT json_agg(e.region_id ORDER BY r.reading_order, e.region_id)
                               FROM attempt_media.step_candidate_evidence e
                               LEFT JOIN attempt_media.evidence_region r ON r.region_id = e.region_id
                              WHERE e.submission_id = sc.submission_id AND e.version = sc.version
                                AND e.step_id = sc.step_id), '[]'::json))
                        ORDER BY sc.ordinal)
                   FROM attempt_media.step_candidate sc
                  WHERE sc.submission_id = x.submission_id AND sc.version = x.version), '[]'::json) AS steps,
               COALESCE((
                 SELECT json_agg(json_build_object(
                          'region_id', r.region_id, 'media_asset_id', r.media_asset_id,
                          'page_number', r.page_number, 'x_norm', r.x_norm, 'y_norm', r.y_norm,
                          'width_norm', r.width_norm, 'height_norm', r.height_norm, 'start_ms', r.start_ms,
                          'end_ms', r.end_ms, 'region_type', r.region_type, 'reading_order', r.reading_order,
                          'confidence', r.confidence, 'first_version', r.transcription_version)
                        ORDER BY r.reading_order, r.region_id)
                   FROM attempt_media.evidence_region r
                  WHERE r.submission_id = x.submission_id AND r.transcription_version <= x.version), '[]'::json)
                 AS regions
          FROM attempt_media.transcription_candidate x {_SUB}
         ORDER BY x.submission_id, x.version""", t_transcript, expected_source="attempt_media.transcription_candidate",
            note="1 immutable TRANSCRIPT per version: steps + evidence_ids + cumulative regions embedded"),
    Mapping("attempt_media.step_candidate", "media", """
        SELECT x.submission_id, x.version, x.step_id,
               EXISTS (SELECT 1 FROM attempt_media.transcription_candidate t JOIN attempt_media.submission s
                         ON s.submission_id = t.submission_id
                        WHERE t.submission_id = x.submission_id AND t.version = x.version) AS embedded
          FROM attempt_media.step_candidate x
         ORDER BY x.submission_id, x.version, x.step_id""", count_only("attempt_media.step_candidate"),
            expected_source="attempt_media.step_candidate", note="embedded in TRANSCRIPT.steps[]"),
    Mapping("attempt_media.step_candidate_evidence", "media", """
        SELECT x.submission_id, x.version, x.step_id, x.region_id,
               EXISTS (SELECT 1 FROM attempt_media.step_candidate c JOIN attempt_media.transcription_candidate t
                         ON t.submission_id = c.submission_id AND t.version = c.version
                        WHERE c.submission_id = x.submission_id AND c.version = x.version
                          AND c.step_id = x.step_id) AS embedded
          FROM attempt_media.step_candidate_evidence x
         ORDER BY x.submission_id, x.version, x.step_id, x.region_id""",
            count_only("attempt_media.step_candidate_evidence"),
            expected_source="attempt_media.step_candidate_evidence", note="embedded in TRANSCRIPT.steps[].evidence_ids"),
    Mapping("attempt_media.evidence_region", "media", """
        SELECT x.region_id, x.submission_id, x.transcription_version,
               EXISTS (SELECT 1 FROM attempt_media.transcription_candidate t
                        WHERE t.submission_id = x.submission_id AND t.version >= x.transcription_version) AS embedded
          FROM attempt_media.evidence_region x
         ORDER BY x.submission_id, x.region_id""", count_only("attempt_media.evidence_region"),
            expected_source="attempt_media.evidence_region",
            note="embedded in TRANSCRIPT.regions[] of every version >= first_version"),
    Mapping("attempt_media.approval", "media", f"""
        SELECT x.submission_id, s.student_id, x.approved_version, x.transcription_version, x.learner_attempt_id,
               x.approved_at, x.student_edit_summary
          FROM attempt_media.approval x {_SUB}
         ORDER BY x.submission_id, x.approved_version""", t_approval, expected_source="attempt_media.approval",
            note="APPROVAL + TXAPPROVED sentinel (UNIQUE submission,tv) + LATTEMPTREF pointer"),
    Mapping("attempt_media.step_assessment#runs", "media", f"""
        WITH a AS (
            SELECT x.*, s.student_id,
                   dense_rank() OVER (PARTITION BY x.submission_id, x.transcription_version
                                      ORDER BY x.created_at, x.source, x.actor_id, x.approved_version) AS run_no
              FROM attempt_media.step_assessment x {_SUB})
        SELECT submission_id, student_id, transcription_version, run_no, source, actor_id, approved_version,
               min(created_at) AS created_at,
               json_agg(json_build_object(
                   'assessment_id', assessment_id, 'step_id', step_id, 'assessment_version', assessment_version,
                   'correctness', correctness, 'alignment_type', alignment_type,
                   'canonical_solution_step_id', canonical_solution_step_id, 'confidence', confidence,
                   'why', why, 'failure_mode', failure_mode, 'next_action', next_action,
                   'evidence_ids', evidence_ids, 'model_profile', model_profile,
                   'created_at', {TS('created_at')})
                 ORDER BY step_id, assessment_version, assessment_id) AS assessments
          FROM a
         GROUP BY submission_id, student_id, transcription_version, run_no, source, actor_id, approved_version
         ORDER BY submission_id, transcription_version, run_no""", t_asmtrun,
            note="ASMTRUN = one analyse/override call: rows grouped by (submission, tv, created_at, source, actor)"),
    Mapping("attempt_media.step_assessment", "media", """
        SELECT x.assessment_id FROM attempt_media.step_assessment x ORDER BY x.assessment_id""",
            count_only("attempt_media.step_assessment"), expected_source="attempt_media.step_assessment",
            note="row-count check; items come from attempt_media.step_assessment#runs"),
    Mapping("attempt_media.event#blocks", "media", f"""
        WITH e AS (
            SELECT x.*, s.student_id,
                   x.sequence - row_number() OVER (PARTITION BY x.submission_id, x.created_at
                                                   ORDER BY x.sequence) AS grp
              FROM attempt_media.event x {_SUB})
        SELECT submission_id, student_id, min(sequence) AS first_seq, max(sequence) AS last_seq,
               json_agg(json_build_object(
                   'sequence', sequence, 'event_type', event_type,
                   'transcription_version', transcription_version, 'approved_version', approved_attempt_version,
                   'payload', payload, 'created_at', {TS('created_at')})
                 ORDER BY sequence) AS events
          FROM e
         GROUP BY submission_id, student_id, created_at, grp
         ORDER BY submission_id, last_seq""", t_evtblock,
            note="EVTBLOCK = contiguous events of one command (equal created_at), keyed by last sequence"),
    Mapping("attempt_media.event", "media", """
        SELECT x.submission_id, x.sequence FROM attempt_media.event x ORDER BY x.submission_id, x.sequence""",
            count_only("attempt_media.event"), expected_source="attempt_media.event",
            note="row-count check; items come from attempt_media.event#blocks"),
]


# ======================================================================== mb-artifacts (artifact_runtime.*)

def t_artreq(row):
    rid, created = s(row["artifact_request_id"]), iso(row["created_at"])
    owner = row["owner_student_id"]
    item = {
        "PK": f"STUDENT#{owner}" if owner else "STAFF#ARTIFACTS", "SK": f"ARTREQ#{created}#{rid}", "type": "ARTREQ",
        "GSI1PK": f"ARTREQ#{rid}", "GSI1SK": "META",
        "GSI2PK": f"ARTREQ#STATUS#{row['status']}", "GSI2SK": f"{created}#{rid}",
        "artifact_request_id": rid, "owner_student_id": owner, "created_by": row["created_by"],
        "request_source": row["request_source"], "subject": row["subject"], "topic": row["topic"],
        "subtopic": row["subtopic"], "goal_type": row["goal_type"], "linked_problem_id": row["linked_problem_id"],
        "linked_solution_step_id": row["linked_solution_step_id"], "status": row["status"],
        "bundle_id": row["bundle_id"], "version": 1, "created_at": row["created_at"],
    }
    item["spec"] = row["spec"]
    item["spec_sha256"] = sha256(_bytes(row["spec"]))
    return [item]


def t_bundle(row):
    bid, rid, status = s(row["artifact_bundle_id"]), s(row["artifact_request_id"]), row["status"]
    created = iso(row["created_at"])
    item = {
        "PK": f"BUNDLE#{bid}", "SK": "META", "type": "BUNDLE",
        "GSI1PK": f"BUNDLE#{status}#{row['subject']}", "GSI1SK": f"{created}#{bid}",
        "artifact_bundle_id": bid, "artifact_request_id": rid, "owner_student_id": row["owner_student_id"],
        "parent_bundle_id": row["parent_bundle_id"], "root_bundle_id": row["root_bundle_id"],
        "bundle_version": row["version"], "subject": row["subject"], "topic": row["topic"],
        "subtopic": row["subtopic"], "title": row["title"], "summary": row["summary"],
        "difficulty_band": row["difficulty_band"], "grade_band": row["grade_band"], "status": status,
        "generator_version": row["generator_version"], "source_spec_sha256": row["source_spec_sha256"],
        "rule_profile_id": row["rule_profile_id"], "annotation_profile_id": row["annotation_profile_id"],
        "assets": [_obj(a) for a in row["assets"]], "asset_types": row["asset_types"],
        "manifest_asset_id": row["manifest_asset_id"], "ordered_overlay_ids": row["ordered_overlay_ids"],
        "tags": row["tags"], "metadata": row["metadata"], "generated_by": row["created_by_agent"],
        "published_at": row["published_at"], "child_count": row["child_count"], "version": 1,
        "created_at": row["created_at"],
    }
    if row["embedding_model"] is not None:
        item["embedding"] = {"index_name": ARTIFACT_INDEX.get(status, ARTIFACT_INDEX["DRAFT"]),
                             "model": row["embedding_model"], "dimensions": row["embedding_dimensions"],
                             "search_text_sha256": row["embedding_search_text_sha256"],
                             "indexed_at": iso(row["embedding_indexed_at"])}
    out: list = []
    item["search_text"] = row["search_text"]
    item["search_text_sha256"] = sha256((row["search_text"] or "").encode())
    item["source_spec"] = row["spec"]                # frozen copy of the plan
    if row["is_request_sentinel"]:
        out.append({"PK": f"UNIQUE#bundle_request#{rid}", "SK": "UNIQUE", "type": "UNIQUE", "bundle_id": bid})
    if row["is_root_version_sentinel"]:
        out.append({"PK": f"UNIQUE#bundle_root_version#{row['root_bundle_id']}#{row['version']}", "SK": "UNIQUE",
                    "type": "UNIQUE", "bundle_id": bid})
    return [item, *out]


def t_bundletag(row):
    bid, typ, tag = s(row["artifact_bundle_id"]), row["tag_type"], row["tag"]
    return [{
        "PK": f"BUNDLE#{bid}", "SK": f"TAG#{typ}#{tag}", "type": "BUNDLETAG",
        "GSI2PK": f"TAG#{typ}#{tag}", "GSI2SK": f"{row['status']}#{iso(row['created_at'])}#{bid}",
        "artifact_bundle_id": bid, "tag_type": typ, "tag": tag, "status": row["status"],
        "subject": row["subject"], "difficulty_band": row["difficulty_band"], "asset_types": row["asset_types"],
    }]


def t_validation(row):
    bid, vid = s(row["artifact_bundle_id"]), s(row["validation_result_id"])
    item = {
        "PK": f"BUNDLE#{bid}", "SK": f"VALIDATION#{iso(row['created_at'])}#{vid}", "type": "VALIDATION",
        "validation_result_id": vid, "artifact_bundle_id": bid, "valid": row["valid"],
        "validator_version": row["validator_version"], "report": row["report"], "created_at": row["created_at"],
    }
    return [item]


_ASSET_TYPES = """COALESCE((SELECT json_agg(DISTINCT a.asset_type ORDER BY a.asset_type)
                             FROM artifact_runtime.artifact_asset a
                            WHERE a.artifact_bundle_id = {b}), '[]'::json)"""

ARTIFACTS = [
    Mapping("artifact_runtime.artifact_request", "artifacts", """
        SELECT r.artifact_request_id, r.owner_student_id, r.created_by, r.request_source, r.subject, r.topic,
               r.subtopic, r.goal_type, r.linked_problem_id, r.linked_solution_step_id, r.spec, r.status,
               r.created_at,
               (SELECT b.artifact_bundle_id FROM artifact_runtime.artifact_bundle b
                 WHERE b.artifact_request_id = r.artifact_request_id
                 ORDER BY b.version DESC, b.created_at DESC, b.artifact_bundle_id LIMIT 1) AS bundle_id
          FROM artifact_runtime.artifact_request r
         ORDER BY r.artifact_request_id""", t_artreq, expected_source="artifact_runtime.artifact_request"),
    Mapping("artifact_runtime.artifact_bundle", "artifacts", f"""
        WITH RECURSIVE anc AS (
            SELECT artifact_bundle_id AS bid, artifact_bundle_id AS cur, parent_bundle_id AS parent, 0 AS depth
              FROM artifact_runtime.artifact_bundle
            UNION ALL
            SELECT anc.bid, p.artifact_bundle_id, p.parent_bundle_id, anc.depth + 1
              FROM anc JOIN artifact_runtime.artifact_bundle p ON p.artifact_bundle_id = anc.parent
             WHERE anc.depth < 1000),
        root AS (SELECT DISTINCT ON (bid) bid, cur AS root_bundle_id FROM anc ORDER BY bid, depth DESC),
        b AS (
            SELECT b.*, root.root_bundle_id,
                   row_number() OVER (PARTITION BY b.artifact_request_id
                                      ORDER BY b.version DESC, b.created_at DESC, b.artifact_bundle_id) = 1
                     AS is_request_sentinel,
                   row_number() OVER (PARTITION BY root.root_bundle_id, b.version
                                      ORDER BY b.created_at, b.artifact_bundle_id) = 1 AS is_root_version_sentinel
              FROM artifact_runtime.artifact_bundle b JOIN root ON root.bid = b.artifact_bundle_id)
        SELECT b.artifact_bundle_id, b.artifact_request_id, b.parent_bundle_id, b.root_bundle_id, b.subject,
               b.topic, b.subtopic, b.title, b.summary, b.difficulty_band, b.grade_band, b.status, b.version,
               b.created_by_agent, b.rule_profile_id, b.annotation_profile_id, b.search_text, b.metadata,
               b.created_at, b.published_at, b.is_request_sentinel, b.is_root_version_sentinel,
               r.owner_student_id, r.spec, l.generator_version, l.source_spec_sha256,
               fs.manifest_asset_id, to_json(fs.ordered_overlay_state_ids) AS ordered_overlay_ids,
               e.model AS embedding_model, e.dimensions AS embedding_dimensions,
               e.search_text_sha256 AS embedding_search_text_sha256, e.indexed_at AS embedding_indexed_at,
               (SELECT count(*) FROM artifact_runtime.artifact_bundle c
                 WHERE c.parent_bundle_id = b.artifact_bundle_id) AS child_count,
               COALESCE((
                 SELECT json_agg(json_build_object(
                          'artifact_asset_id', a.artifact_asset_id, 'asset_type', a.asset_type,
                          'object_key', a.object_key, 'sha256', a.sha256, 'size_bytes', a.size_bytes,
                          'mime_type', a.mime_type, 'render_format', a.render_format, 'width', a.width,
                          'height', a.height, 'element_ids', a.element_ids, 'created_at', {TS('a.created_at')})
                        ORDER BY a.created_at, a.artifact_asset_id)
                   FROM artifact_runtime.artifact_asset a
                  WHERE a.artifact_bundle_id = b.artifact_bundle_id), '[]'::json) AS assets,
               {_ASSET_TYPES.format(b='b.artifact_bundle_id')} AS asset_types,
               (SELECT json_build_object(
                         'concept', COALESCE(json_agg(DISTINCT t.tag ORDER BY t.tag) FILTER (WHERE t.tag_type = 'concept'), '[]'::json),
                         'skill', COALESCE(json_agg(DISTINCT t.tag ORDER BY t.tag) FILTER (WHERE t.tag_type = 'skill'), '[]'::json),
                         'theorem', COALESCE(json_agg(DISTINCT t.tag ORDER BY t.tag) FILTER (WHERE t.tag_type = 'theorem'), '[]'::json))
                  FROM (SELECT st.tag_type, st.tag FROM artifact_runtime.artifact_search_tag st
                         WHERE st.artifact_bundle_id = b.artifact_bundle_id
                        UNION
                        SELECT v.tag_type, v.tag
                          FROM artifact_runtime.artifact_metadata m
                          JOIN artifact_runtime.artifact_asset a ON a.artifact_asset_id = m.artifact_asset_id
                          CROSS JOIN LATERAL (
                              SELECT 'concept' AS tag_type, unnest(m.concept_ids) AS tag
                              UNION ALL SELECT 'skill', unnest(m.skill_ids)
                              UNION ALL SELECT 'theorem', unnest(m.theorem_ids)) v
                         WHERE a.artifact_bundle_id = b.artifact_bundle_id) t) AS tags
          FROM b
          JOIN artifact_runtime.artifact_request r ON r.artifact_request_id = b.artifact_request_id
          LEFT JOIN artifact_runtime.artifact_lineage l ON l.artifact_bundle_id = b.artifact_bundle_id
          LEFT JOIN artifact_runtime.frame_sequence fs ON fs.artifact_bundle_id = b.artifact_bundle_id
          LEFT JOIN artifact_runtime.artifact_embedding e ON e.artifact_bundle_id = b.artifact_bundle_id
         ORDER BY b.artifact_bundle_id""", t_bundle, expected_source="artifact_runtime.artifact_bundle",
            note="BUNDLE with assets/lineage/frame manifest/tags/metadata/source_spec embedded, UNIQUE sentinels"),
    Mapping("artifact_runtime.artifact_asset", "artifacts", """
        SELECT x.artifact_asset_id,
               EXISTS (SELECT 1 FROM artifact_runtime.artifact_bundle b
                        WHERE b.artifact_bundle_id = x.artifact_bundle_id) AS embedded
          FROM artifact_runtime.artifact_asset x ORDER BY x.artifact_asset_id""",
            count_only("artifact_runtime.artifact_asset"), expected_source="artifact_runtime.artifact_asset",
            note="embedded in BUNDLE.assets[] (bytes stay in the object store)"),
    Mapping("artifact_runtime.artifact_metadata", "artifacts", """
        SELECT x.artifact_asset_id,
               EXISTS (SELECT 1 FROM artifact_runtime.artifact_asset a
                        WHERE a.artifact_asset_id = x.artifact_asset_id) AS embedded
          FROM artifact_runtime.artifact_metadata x ORDER BY x.artifact_asset_id""",
            count_only("artifact_runtime.artifact_metadata"), expected_source="artifact_runtime.artifact_metadata",
            note="ART-F09: concept/skill/theorem ids folded into BUNDLE.tags; other fields already on BUNDLE"),
    Mapping("artifact_runtime.overlay_state", "artifacts", """
        SELECT x.overlay_state_id FROM artifact_runtime.overlay_state x ORDER BY x.overlay_state_id""",
            count_only("artifact_runtime.overlay_state"), expected_source="artifact_runtime.overlay_state",
            note="ART-F10: not migrated; overlays live in the manifest asset + BUNDLE.ordered_overlay_ids"),
    Mapping("artifact_runtime.frame_sequence", "artifacts", """
        SELECT x.frame_sequence_id,
               EXISTS (SELECT 1 FROM artifact_runtime.artifact_bundle b
                        WHERE b.artifact_bundle_id = x.artifact_bundle_id) AS embedded
          FROM artifact_runtime.frame_sequence x ORDER BY x.frame_sequence_id""",
            count_only("artifact_runtime.frame_sequence"), expected_source="artifact_runtime.frame_sequence",
            note="manifest_asset_id + ordered_overlay_ids on BUNDLE; transition_notes dropped (ART-F11)"),
    Mapping("artifact_runtime.artifact_annotation", "artifacts", """
        SELECT x.artifact_annotation_id FROM artifact_runtime.artifact_annotation x
         ORDER BY x.artifact_annotation_id""",
            count_only("artifact_runtime.artifact_annotation"), expected_source="artifact_runtime.artifact_annotation",
            note="ART-F12: not migrated; annotation text is served from the manifest asset"),
    Mapping("artifact_runtime.artifact_lineage", "artifacts", """
        SELECT x.artifact_bundle_id,
               EXISTS (SELECT 1 FROM artifact_runtime.artifact_bundle b
                        WHERE b.artifact_bundle_id = x.artifact_bundle_id) AS embedded
          FROM artifact_runtime.artifact_lineage x ORDER BY x.artifact_bundle_id""",
            count_only("artifact_runtime.artifact_lineage"), expected_source="artifact_runtime.artifact_lineage",
            note="ART-F14: generator_version/source_spec_sha256/parent/root on BUNDLE"),
    Mapping("artifact_runtime.artifact_search_tag", "artifacts", f"""
        SELECT t.artifact_bundle_id, t.tag_type, t.tag, b.status, b.subject, b.difficulty_band, b.created_at,
               {_ASSET_TYPES.format(b='t.artifact_bundle_id')} AS asset_types
          FROM artifact_runtime.artifact_search_tag t
          JOIN artifact_runtime.artifact_bundle b ON b.artifact_bundle_id = t.artifact_bundle_id
         ORDER BY t.artifact_bundle_id, t.tag_type, t.tag""", t_bundletag,
            expected_source="artifact_runtime.artifact_search_tag"),
    Mapping("artifact_runtime.validation_result", "artifacts", """
        SELECT x.validation_result_id, x.artifact_bundle_id, x.valid, x.validator_version, x.report, x.created_at
          FROM artifact_runtime.validation_result x
         ORDER BY x.artifact_bundle_id, x.created_at, x.validation_result_id""", t_validation,
            expected_source="artifact_runtime.validation_result"),
]


# ======================================================================== mb-geometry (geometry_scene.*)

def owner_key(owner: str) -> tuple[str, dict]:
    """'admin'/'standalone'/X-Actor-Id → STAFF#<principal>; canonical UUID → STUDENT#<uuid>."""
    try:
        u = str(uuid.UUID(owner))
    except (ValueError, AttributeError, TypeError):
        u = None
    if u is not None and u == owner.lower():
        return f"STUDENT#{u}", {"student_id": u}
    return f"STAFF#{owner}", {"staff_principal": owner}


def t_scene(row):
    pk, who = owner_key(row["owner"])
    sid = row["scene_id"]
    return [{
        "PK": pk, "SK": f"SCENE#{sid}", "type": "SCENE",
        "GSI1PK": f"{pk}#SCENES", "GSI1SK": f"{iso(row['created_at'])}#{sid}",
        "scene_id": sid, "owner": row["owner"], **who, "current_version": row["current_version"], "version": 1,
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }]


def t_scenever(row):
    pk, _ = owner_key(row["owner"])
    sid = row["scene_id"]
    assets = {k: _obj(v) for k, v in (row["assets"] or {}).items()}
    return [{
        "PK": pk, "SK": f"SCENE#{sid}#V#{pad(row['version'], 8)}", "type": "SCENEVER",
        "scene_id": sid, "version": row["version"], "assets": assets, "lineage": row["lineage"],
        "created_at": row["created_at"],
    }]


def t_receipt(row):
    pk, _ = owner_key(row["owner"])
    return [{
        "PK": pk, "SK": f"RECEIPT#{row['key']}", "type": "RECEIPT",
        "key": row["key"], "request_hash": row["request_hash"], "scene_id": row["scene_id"],
        "version": row["version"], "created_at": row["created_at"],
        "version_created_at": row["version_created_at"], "ttl": ttl_after(row["created_at"], RECEIPT_TTL_DAYS),
    }]


def t_run(row):
    pk, _ = owner_key(row["owner"])
    rid, created, review = row["run_id"], iso(row["created_at"]), row["review"]
    ttl = ttl_after(row["created_at"], RUN_TTL_DAYS)
    decision = (review or {}).get("decision") if isinstance(review, dict) else None
    item = {
        "PK": pk, "SK": f"RUN#{rid}", "type": "RUN",
        "GSI1PK": f"{pk}#RUNS", "GSI1SK": f"{created}#{rid}",
        "GSI2PK": f"RUNS#{decision or 'NONE'}", "GSI2SK": f"{created}#{row['owner']}#{rid}",
        "run_id": rid, "owner": row["owner"], "evidence_asset": _obj(row["evidence_asset"]),
        "evidence_hash": row["evidence_hash"], "status": "FAILED_CANDIDATE" if rid.startswith("failed_") else None,
        "review": review, "review_count": 1 if review is not None else 0,
        "created_at": row["created_at"], "ttl": ttl,
    }
    out = [item]
    if review is not None:
        out.append({"PK": pk, "SK": f"RUN#{rid}#REVIEW#{pad(1, 8)}", "type": "RUNREVIEW", "run_id": rid,
                    "decision": decision, "note": review.get("note") if isinstance(review, dict) else None,
                    "review": review, "ttl": ttl})
    return out


GEOMETRY = [
    Mapping("geometry_scene.scenes", "geometry", """
        SELECT s.scene_id, s.owner, s.current_version, s.created_at,
               COALESCE((SELECT max(v.created_at) FROM geometry_scene.versions v WHERE v.scene_id = s.scene_id),
                        s.created_at) AS updated_at
          FROM geometry_scene.scenes s
         ORDER BY s.owner, s.scene_id""", t_scene, expected_source="geometry_scene.scenes"),
    Mapping("geometry_scene.versions", "geometry", """
        SELECT v.scene_id, s.owner, v.version, v.assets, v.lineage, v.created_at
          FROM geometry_scene.versions v JOIN geometry_scene.scenes s ON s.scene_id = v.scene_id
         ORDER BY s.owner, v.scene_id, v.version""", t_scenever, expected_source="geometry_scene.versions"),
    Mapping("geometry_scene.receipts", "geometry", """
        SELECT r.owner, r.key, r.request_hash, r.scene_id, r.version,
               date_trunc('day', now()) AS created_at, v.created_at AS version_created_at
          FROM geometry_scene.receipts r
          LEFT JOIN geometry_scene.versions v ON v.scene_id = r.scene_id AND v.version = r.version
         ORDER BY r.owner, r.key""", t_receipt, expected_source="geometry_scene.receipts",
            note="PG has no created_at: created_at = migration day (UTC, day-truncated so same-day re-runs are "
                 "identical), ttl = +30 d; version_created_at keeps the original commit time"),
    Mapping("geometry_scene.runs", "geometry", """
        SELECT r.owner, r.run_id, r.evidence_asset, r.evidence_hash, r.review, r.created_at
          FROM geometry_scene.runs r
         ORDER BY r.owner, r.run_id""", t_run, expected_source="geometry_scene.runs",
            note="RUN (+ RUNREVIEW#1 when reviewed); ttl = created_at + 180 d"),
]


# ======================================================================== mb-jobs (studio.*)

def _job(row, kind: str, id_col: str):
    if not row["live"]:                            # design §7: copy only expires_at > now
        return []
    jid, created = s(row[id_col]), iso(row["created_at"])
    item = {
        "PK": f"{kind}#{jid}", "SK": "META", "type": f"{kind}JOB",
        "GSI1PK": f"{kind}#STATUS#{row['status']}", "GSI1SK": f"{created}#{jid}",
        id_col: jid, "status": row["status"], "attempts": 0, "version": 1,
        "created_at": row["created_at"], "updated_at": row["updated_at"], "expires_at": row["expires_at"],
        "ttl": epoch(row["expires_at"]),
    }
    for col in ("topic", "context_json", "result_scene_spec", "scene_spec_json", "result_explanation", "error_message",
                "source_research_job_id", "video_duration_ms", "promoted_scene_spec_id"):
        if col in row:
            item[col] = row[col]
    if row.get("video_object_key") is not None:
        item["video_bucket"] = OBJECT_BUCKET
        item["video_object_key"] = row["video_object_key"]
    return [item]


JOBS = [
    Mapping("studio.scene_research_job", "jobs", """
        SELECT j.scene_research_job_id, j.status, j.topic, j.context_json, j.result_scene_spec,
               j.result_explanation, j.error_message, j.created_at, j.updated_at, j.expires_at,
               j.expires_at > now() AS live
          FROM studio.scene_research_job j
         ORDER BY j.created_at, j.scene_research_job_id""",
            lambda r: _job(r, "RESEARCH", "scene_research_job_id"),
            expected_source="studio.scene_research_job", note="only non-expired jobs become items"),
    Mapping("studio.video_render_job", "jobs", """
        SELECT j.video_render_job_id, j.status, j.source_research_job_id, j.scene_spec_json, j.video_object_key,
               j.video_duration_ms, j.error_message, j.created_at, j.updated_at, j.expires_at,
               j.promoted_scene_spec_id, j.expires_at > now() AS live
          FROM studio.video_render_job j
         ORDER BY j.created_at, j.video_render_job_id""",
            lambda r: _job(r, "RENDER", "video_render_job_id"),
            expected_source="studio.video_render_job", note="only non-expired jobs become items"),
]

MAPPINGS = MEDIA + ARTIFACTS + GEOMETRY + JOBS
