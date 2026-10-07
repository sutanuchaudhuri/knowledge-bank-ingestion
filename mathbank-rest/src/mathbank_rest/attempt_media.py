"""Versioned private evidence runtime. Provider stages run outside database locks."""

from __future__ import annotations

import json

from sqlalchemy import text

from mathbank_rest.attempt_media_models import Assessment, Transcript


class MediaError(Exception):
    def __init__(self, status: int, code: str):
        self.status_code, self.code = status, code
        super().__init__(code)


def submission(conn, sid, actor, *, lock=False, expected=None):
    row = (
        conn.execute(
            text(
                "SELECT * FROM attempt_media.submission WHERE submission_id=:id"
                + (" FOR UPDATE" if lock else "")
            ),
            {"id": str(sid)},
        )
        .mappings()
        .first()
    )
    if not row or (actor["role"] != "ADMIN" and str(row["student_id"]) != actor["student_id"]):
        raise MediaError(404, "SUBMISSION_NOT_FOUND")
    row = dict(row)
    if expected is not None and row["transcription_version"] != expected:
        raise MediaError(409, "TRANSCRIPTION_VERSION_CONFLICT")
    return row


def event(conn, row, name, payload=None):
    sequence = conn.execute(
        text(
            "UPDATE attempt_media.submission SET last_sequence=last_sequence+1,updated_at=now() "
            "WHERE submission_id=:id RETURNING last_sequence"
        ),
        {"id": str(row["submission_id"])},
    ).scalar_one()
    values = {
        "id": str(row["submission_id"]),
        "seq": sequence,
        "name": name,
        "v": row["transcription_version"],
        "a": row["approved_version"],
        "payload": json.dumps(payload or {}),
    }
    conn.execute(
        text(
            "INSERT INTO attempt_media.event (submission_id,sequence,event_type,transcription_version,"
            "approved_attempt_version,payload) VALUES (:id,:seq,:name,:v,:a,CAST(:payload AS jsonb))"
        ),
        values,
    )
    # Only identifiers/version reach the general outbox, never private work or media.
    conn.execute(
        text(
            "INSERT INTO pipeline.outbox_event(event_type,aggregate_type,aggregate_id,payload) "
            "VALUES (:name,'MULTIMODAL_ATTEMPT',:id,CAST(:payload AS jsonb))"
        ),
        {
            "name": name,
            "id": values["id"],
            "payload": json.dumps(
                {
                    "submission_id": values["id"],
                    "sequence": sequence,
                    "transcription_version": values["v"],
                }
            ),
        },
    )


def set_status(conn, row, status, name, payload=None):
    conn.execute(
        text(
            "UPDATE attempt_media.submission SET status=:status,error_code=NULL "
            "WHERE submission_id=:id"
        ),
        {"id": str(row["submission_id"]), "status": status},
    )
    row["status"] = status
    event(conn, row, name, payload)


def snapshot(conn, sid, actor):
    row = submission(conn, sid, actor)
    sid = str(sid)
    row["assets"] = [
        dict(r)
        for r in conn.execute(
            text(
                "SELECT media_asset_id,submission_id,role,parent_asset_id,asset_type,mime_type,sha256,size_bytes,"
                "page_count,duration_ms,timestamp_ms,purged_at FROM attempt_media.media_asset "
                "WHERE submission_id=:id ORDER BY created_at,media_asset_id"
            ),
            {"id": sid},
        ).mappings()
    ]
    for asset in row["assets"]:
        asset["content_url"] = (
            f"/v1/attempt-media/submissions/{sid}/assets/{asset['media_asset_id']}/content"
        )
    row["regions"] = [
        dict(r)
        for r in conn.execute(
            text(
                "SELECT * FROM attempt_media.evidence_region WHERE submission_id=:id ORDER BY reading_order,region_id"
            ),
            {"id": sid},
        ).mappings()
    ]
    row["steps"] = [
        dict(r)
        for r in conn.execute(
            text(
                "SELECT s.*,COALESCE((SELECT jsonb_agg(e.region_id ORDER BY e.region_id) FROM "
                "attempt_media.step_candidate_evidence e WHERE e.submission_id=s.submission_id AND "
                "e.version=s.version AND e.step_id=s.step_id),'[]'::jsonb) AS evidence_ids "
                "FROM attempt_media.step_candidate s WHERE s.submission_id=:id AND s.version=:v ORDER BY ordinal"
            ),
            {"id": sid, "v": row["transcription_version"]},
        ).mappings()
    ]
    row["approvals"] = [
        dict(r)
        for r in conn.execute(
            text(
                "SELECT * FROM attempt_media.approval WHERE submission_id=:id ORDER BY approved_version"
            ),
            {"id": sid},
        ).mappings()
    ]
    history = [
        dict(r)
        for r in conn.execute(
            text(
                "SELECT * FROM attempt_media.step_assessment WHERE submission_id=:id "
                "ORDER BY created_at,assessment_version"
            ),
            {"id": sid},
        ).mappings()
    ]
    current = {}
    for assessment in history:
        if assessment["transcription_version"] == row["transcription_version"]:
            current[str(assessment["step_id"])] = assessment
    row["assessments"] = list(current.values())
    row["assessment_history"] = history if actor["role"] == "ADMIN" else []
    row["events"] = events(conn, sid, actor, 0)
    return row


def events(conn, sid, actor, after):
    submission(conn, sid, actor)
    return [
        dict(r)
        for r in conn.execute(
            text(
                "SELECT * FROM attempt_media.event WHERE submission_id=:id AND sequence>:after "
                "ORDER BY sequence LIMIT 500"
            ),
            {"id": str(sid), "after": after},
        ).mappings()
    ]


def validate_links(conn, row, transcript):
    assets = {
        str(r["media_asset_id"]): dict(r)
        for r in conn.execute(
            text("SELECT * FROM attempt_media.media_asset WHERE submission_id=:id"),
            {"id": str(row["submission_id"])},
        ).mappings()
    }
    regions = {
        str(r["region_id"]): dict(r)
        for r in conn.execute(
            text("SELECT * FROM attempt_media.evidence_region WHERE submission_id=:id"),
            {"id": str(row["submission_id"])},
        ).mappings()
    }
    for region in transcript.regions or []:
        data = region.model_dump(mode="json")
        asset = assets.get(str(region.media_asset_id))
        if not asset or asset["purged_at"]:
            raise MediaError(422, "EVIDENCE_ASSET_UNAVAILABLE")
        if region.page_number is not None:
            if asset["asset_type"] not in ("IMAGE", "PDF") or region.page_number > (
                asset["page_count"] or 1
            ):
                raise MediaError(422, "EVIDENCE_PAGE_INVALID")
        elif asset["asset_type"] not in ("AUDIO", "VIDEO") or region.end_ms > (
            asset["duration_ms"] or 0
        ):
            raise MediaError(422, "EVIDENCE_INTERVAL_INVALID")
        if str(region.region_id) in regions and any(
            str(regions[str(region.region_id)][key]) != str(data[key])
            for key in (
                "media_asset_id",
                "page_number",
                "x_norm",
                "y_norm",
                "width_norm",
                "height_norm",
                "start_ms",
                "end_ms",
                "region_type",
                "reading_order",
                "confidence",
            )
        ):
            raise MediaError(409, "EVIDENCE_IMMUTABLE_CREATE_NEW_REGION")
        regions[str(region.region_id)] = data
    for step in transcript.steps:
        if any(str(e) not in regions for e in step.evidence_ids):
            raise MediaError(422, "UNKNOWN_EVIDENCE")
        if any(
            assets[str(regions[str(e)]["media_asset_id"])]["purged_at"] for e in step.evidence_ids
        ):
            raise MediaError(422, "EVIDENCE_ASSET_UNAVAILABLE")
    return regions


def save_transcript(conn, sid, actor, transcript: Transcript, *, machine=None, profile=None):
    row = submission(conn, sid, actor, lock=True, expected=transcript.expected_version)
    validate_links(conn, row, transcript)
    version = row["transcription_version"] + 1
    conn.execute(
        text(
            "INSERT INTO attempt_media.transcription_candidate "
            "(submission_id,version,source,machine_output,model_profile) "
            "VALUES (:id,:v,:source,CAST(:output AS jsonb),:profile)"
        ),
        {
            "id": str(sid),
            "v": version,
            "source": "MACHINE" if machine is not None else "STUDENT",
            "output": json.dumps(machine) if machine is not None else None,
            "profile": profile,
        },
    )
    for region in transcript.regions or []:
        data = region.model_dump(mode="json")
        data.update(submission_id=str(sid), transcription_version=version)
        inserted = conn.execute(
            text(
                "INSERT INTO attempt_media.evidence_region ("
                + ",".join(data)
                + ") VALUES ("
                + ",".join(":" + key for key in data)
                + ") ON CONFLICT (region_id) DO UPDATE SET region_id=EXCLUDED.region_id "
                "WHERE attempt_media.evidence_region.submission_id=EXCLUDED.submission_id RETURNING region_id"
            ),
            data,
        ).scalar()
        if not inserted:
            raise MediaError(422, "EVIDENCE_ID_UNAVAILABLE")
    for step in transcript.steps:
        data = step.model_dump(mode="json")
        evidence = data.pop("evidence_ids")
        data.update(submission_id=str(sid), version=version)
        conn.execute(
            text(
                "INSERT INTO attempt_media.step_candidate ("
                + ",".join(data)
                + ") VALUES ("
                + ",".join(":" + key for key in data)
                + ")"
            ),
            data,
        )
        for eid in evidence:
            conn.execute(
                text(
                    "INSERT INTO attempt_media.step_candidate_evidence "
                    "VALUES (:id,:v,:step,:evidence)"
                ),
                {"id": str(sid), "v": version, "step": str(step.step_id), "evidence": eid},
            )
    conn.execute(
        text(
            "UPDATE attempt_media.submission SET transcription_version=:v,status=:status,error_code=NULL "
            "WHERE submission_id=:id"
        ),
        {
            "id": str(sid),
            "v": version,
            "status": "TRANSCRIPTION_READY" if machine is not None else "STUDENT_REVIEWING",
        },
    )
    row["transcription_version"] = version
    event(conn, row, "attempt.transcription.ready")
    return snapshot(conn, sid, actor)


def approve(conn, sid, actor, expected):
    row = submission(conn, sid, actor, lock=True, expected=expected)
    if actor["role"] != "STUDENT":
        raise MediaError(403, "STUDENT_APPROVAL_REQUIRED")
    if row.get("status") == "TRANSCRIBING":
        raise MediaError(409, "WAIT_FOR_TRANSCRIPTION_OR_EDIT_FIRST")
    previous = (
        conn.execute(
            text(
                "SELECT * FROM attempt_media.approval WHERE submission_id=:id AND transcription_version=:v"
            ),
            {"id": str(sid), "v": expected},
        )
        .mappings()
        .first()
    )
    if previous:
        return dict(previous)
    steps = snapshot(conn, sid, actor)["steps"]
    if not steps:
        raise MediaError(422, "NO_STEPS_TO_APPROVE")
    answer = "\n".join(s["latex_text"] or s["plain_text"] for s in steps)
    attempt = conn.execute(
        text(
            "INSERT INTO learner.attempt(student_id,problem_id,is_correct,submitted_answer,source) "
            "VALUES (:student,:problem,NULL,:answer,'multimodal_approved') RETURNING attempt_id"
        ),
        {"student": str(row["student_id"]), "problem": str(row["problem_id"]), "answer": answer},
    ).scalar_one()
    row["approved_version"] += 1
    result = (
        conn.execute(
            text(
                "INSERT INTO attempt_media.approval(submission_id,approved_version,transcription_version,"
                "learner_attempt_id,student_edit_summary) VALUES (:id,:a,:v,:attempt,:summary) RETURNING *"
            ),
            {
                "id": str(sid),
                "a": row["approved_version"],
                "v": expected,
                "attempt": attempt,
                "summary": "Explicit student approval of the reviewed evidence-linked transcription",
            },
        )
        .mappings()
        .one()
    )
    conn.execute(
        text("UPDATE attempt_media.submission SET approved_version=:a WHERE submission_id=:id"),
        {"a": row["approved_version"], "id": str(sid)},
    )
    set_status(conn, row, "APPROVED", "attempt.approved")
    return dict(result)


def ensure_approved(conn, row):
    if not conn.execute(
        text(
            "SELECT 1 FROM attempt_media.approval WHERE submission_id=:id AND transcription_version=:v"
        ),
        {"id": str(row["submission_id"]), "v": row["transcription_version"]},
    ).scalar():
        raise MediaError(409, "APPROVE_CURRENT_TRANSCRIPTION_FIRST")


def save_assessments(conn, sid, actor, expected, assessments: list[Assessment], source="AI"):
    row = submission(conn, sid, actor, lock=True, expected=expected)
    ensure_approved(conn, row)
    view = snapshot(conn, sid, actor)
    steps = {str(s["step_id"]): s for s in view["steps"]}
    if source == "AI" and {str(a.step_id) for a in assessments} != set(steps):
        raise MediaError(422, "ASSESSMENT_STEP_INVENTORY_MISMATCH")
    if len({a.step_id for a in assessments}) != len(assessments):
        raise MediaError(422, "DUPLICATE_ASSESSMENT")
    for assessment in assessments:
        step = steps.get(str(assessment.step_id))
        if not step or not set(map(str, assessment.evidence_ids)).issubset(
            set(map(str, step["evidence_ids"]))
        ):
            raise MediaError(422, "ASSESSMENT_EVIDENCE_MISMATCH")
        if source == "AI" and step["confidence"] < 0.7 and assessment.correctness != "UNCERTAIN":
            raise MediaError(422, "LOW_CONFIDENCE_REQUIRES_UNCERTAIN")
        if (
            assessment.canonical_solution_step_id
            and not conn.execute(
                text(
                    "SELECT 1 FROM pedagogy.solution_step "
                    "WHERE solution_step_id=:step AND problem_id=:problem AND publication_status='PUBLISHED'"
                ),
                {"step": assessment.canonical_solution_step_id, "problem": str(row["problem_id"])},
            ).scalar()
        ):
            raise MediaError(422, "ALIGNMENT_OUTSIDE_PROBLEM")
        if (
            source == "AI"
            and conn.execute(
                text(
                    "SELECT 1 FROM attempt_media.step_assessment WHERE submission_id=:id "
                    "AND transcription_version=:v AND step_id=:step AND source='INSTRUCTOR'"
                ),
                {"id": str(sid), "v": expected, "step": str(assessment.step_id)},
            ).scalar()
        ):
            continue  # Retries cannot overwrite instructor decisions.
        number = conn.execute(
            text(
                "SELECT COALESCE(max(assessment_version),0)+1 FROM attempt_media.step_assessment "
                "WHERE submission_id=:id AND transcription_version=:v AND step_id=:step"
            ),
            {"id": str(sid), "v": expected, "step": str(assessment.step_id)},
        ).scalar_one()
        values = assessment.model_dump(mode="json")
        values.update(
            id=str(sid),
            v=expected,
            a=row["approved_version"],
            number=number,
            source=source,
            actor=actor.get("student_id") or "instructor",
            profile="multimodal-v1",
        )
        values["evidence_ids"] = json.dumps(values["evidence_ids"])
        conn.execute(
            text(
                "INSERT INTO attempt_media.step_assessment (submission_id,transcription_version,step_id,"
                "approved_version,assessment_version,source,actor_id,correctness,alignment_type,"
                "canonical_solution_step_id,confidence,why,failure_mode,next_action,evidence_ids,model_profile) "
                "VALUES (:id,:v,:step_id,:a,:number,:source,:actor,:correctness,:alignment_type,"
                ":canonical_solution_step_id,:confidence,:why,:failure_mode,:next_action,"
                "CAST(:evidence_ids AS jsonb),:profile)"
            ),
            values,
        )
        event(
            conn,
            row,
            "attempt.step.assessed",
            {"step_id": str(assessment.step_id), "assessment_version": number},
        )
    set_status(conn, row, "READY", "attempt.visual.ready")
    event(conn, row, "attempt.analysis.complete")
    return snapshot(conn, sid, actor)
