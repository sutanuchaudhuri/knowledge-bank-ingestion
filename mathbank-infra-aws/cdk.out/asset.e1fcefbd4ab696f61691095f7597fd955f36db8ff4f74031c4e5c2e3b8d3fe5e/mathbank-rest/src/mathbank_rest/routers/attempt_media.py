"""Authenticated, version-checked multimodal submission commands and private assets."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from mathbank_rest import attempt_media as runtime
from mathbank_rest import media_processing, object_store
from mathbank_rest.attempt_media_models import Assessment, Override, Step, Transcript, Versioned
from mathbank_rest.db.postgres import engine
from mathbank_rest.routers.fluid import staff_or_student

router = APIRouter(prefix="/v1/attempt-media", tags=["multimodal-attempts"])
log = logging.getLogger(__name__)
TRANSCRIBE_IMAGE = media_processing.transcribe_image
TRANSCRIBE_SPEECH = media_processing.transcribe_speech
SEGMENT = media_processing.segment
ANALYSE = media_processing.analyse
Actor = Annotated[dict, Depends(staff_or_student)]


def run(fn, *args, **kwargs):
    try:
        with engine.begin() as conn:
            return fn(conn, *args, **kwargs)
    except runtime.MediaError as exc:
        raise HTTPException(exc.status_code, detail={"code": exc.code}) from None


class SubmissionIn(BaseModel):
    problem_ref: str = Field(min_length=1, max_length=200)


@router.post("/submissions", status_code=201)
def create(body: SubmissionIn, actor: Actor):
    if actor["role"] != "STUDENT":
        raise HTTPException(403, detail={"code": "STUDENT_SUBMISSION_REQUIRED"})

    def op(conn):
        problem = conn.execute(
            text(
                "SELECT problem_id FROM core.problem WHERE canonical_code=:ref OR problem_id::text=:ref"
            ),
            {"ref": body.problem_ref},
        ).scalar()
        if not problem:
            raise runtime.MediaError(404, "PROBLEM_NOT_FOUND")
        sid = conn.execute(
            text(
                "INSERT INTO attempt_media.submission(student_id,problem_id) "
                "VALUES (:student,:problem) RETURNING submission_id"
            ),
            {"student": actor["student_id"], "problem": problem},
        ).scalar_one()
        return runtime.snapshot(conn, sid, actor)

    return run(op)


@router.get("/submissions")
def listing(actor: Actor, limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
    def op(conn):
        rows = (
            conn.execute(
                text(
                    "SELECT s.submission_id,s.problem_id,s.status,s.transcription_version,s.approved_version,"
                    "p.canonical_code,s.created_at FROM attempt_media.submission s "
                    "JOIN core.problem p USING(problem_id) WHERE (:admin OR s.student_id=CAST(:student AS uuid)) "
                    "ORDER BY s.created_at DESC,s.submission_id LIMIT :n OFFSET :o"
                ),
                {
                    "admin": actor["role"] == "ADMIN",
                    "student": actor["student_id"],
                    "n": limit + 1,
                    "o": offset,
                },
            )
            .mappings()
            .all()
        )
        return {"items": [dict(r) for r in rows[:limit]], "has_more": len(rows) > limit}

    return run(op)


@router.get("/submissions/{sid}")
def get(sid: UUID, actor: Actor):
    return run(runtime.snapshot, sid, actor)


@router.get("/submissions/{sid}/events")
def events(sid: UUID, actor: Actor, after_sequence: int = Query(0, ge=0)):
    return {"events": run(runtime.events, sid, actor, after_sequence)}


def _asset(conn, sid, aid, actor):
    runtime.submission(conn, sid, actor)
    asset = (
        conn.execute(
            text(
                "SELECT * FROM attempt_media.media_asset WHERE submission_id=:id AND media_asset_id=:asset"
            ),
            {"id": str(sid), "asset": str(aid)},
        )
        .mappings()
        .first()
    )
    if not asset:
        raise runtime.MediaError(404, "ASSET_NOT_FOUND")
    if asset["purged_at"]:
        raise runtime.MediaError(410, "RAW_MEDIA_PURGED")
    return dict(asset)


def _store_asset(conn, sid, info, stored, *, role="ORIGINAL", parent=None, timestamp=None):
    params = {
        **stored,
        **info,
        "id": str(sid),
        "role": role,
        "parent": parent,
        "timestamp": timestamp,
    }
    return dict(
        conn.execute(
            text(
                "INSERT INTO attempt_media.media_asset(submission_id,role,parent_asset_id,asset_type,"
                "object_key,mime_type,sha256,size_bytes,page_count,duration_ms,timestamp_ms) "
                "VALUES (:id,:role,:parent,:asset_type,:object_key,:mime_type,:sha256,:size_bytes,"
                ":page_count,:duration_ms,:timestamp) RETURNING *"
            ),
            params,
        )
        .mappings()
        .one()
    )


@router.post("/submissions/{sid}/assets", status_code=201)
async def upload(
    sid: UUID,
    request: Request,
    actor: Actor,
    expected_version: int = Query(ge=1),
    filename: str = Query("upload", max_length=200),
):
    run(runtime.submission, sid, actor, expected=expected_version)
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > media_processing.MAX_BYTES:
            raise HTTPException(413, detail={"code": "MEDIA_SIZE_LIMIT"})
    try:
        info = media_processing.media_info(bytes(data), request.headers.get("content-type", ""))
        stored = object_store.put_bytes(bytes(data), info["suffix"])
    except runtime.MediaError as exc:
        raise HTTPException(exc.status_code, detail={"code": exc.code}) from None
    except (OSError, RuntimeError):
        raise HTTPException(503, detail={"code": "OBJECT_STORAGE_UNAVAILABLE"}) from None

    def op(conn):
        row = runtime.submission(conn, sid, actor, lock=True, expected=expected_version)
        count = conn.execute(
            text(
                "SELECT count(*) FROM attempt_media.media_asset WHERE submission_id=:id AND role='ORIGINAL' "
                "AND purged_at IS NULL"
            ),
            {"id": str(sid)},
        ).scalar_one()
        if count >= 10:
            raise runtime.MediaError(422, "ASSET_COUNT_LIMIT")
        asset = _store_asset(conn, sid, info, stored)
        conn.execute(
            text(
                "UPDATE attempt_media.submission SET transcription_version=transcription_version+1 "
                "WHERE submission_id=:id"
            ),
            {"id": str(sid)},
        )
        row["transcription_version"] += 1
        runtime.set_status(
            conn,
            row,
            "MEDIA_NORMALIZED",
            "attempt.upload.accepted",
            {"media_asset_id": str(asset["media_asset_id"])},
        )
        return {
            "media_asset_id": asset["media_asset_id"],
            "transcription_version": row["transcription_version"],
        }

    try:
        return run(op)
    except Exception:
        # Cross-store writes are not atomic; remove only this unreferenced upload.
        try:
            object_store.delete_object(stored["object_key"])
        except (OSError, RuntimeError):
            log.error("Unreferenced media object cleanup failed")
        raise


@router.get("/submissions/{sid}/assets/{aid}/content")
def content(sid: UUID, aid: UUID, actor: Actor):
    asset = run(_asset, sid, aid, actor)
    try:
        data = object_store.read_bytes(asset["object_key"])
    except (OSError, RuntimeError):
        raise HTTPException(503, detail={"code": "OBJECT_STORAGE_UNAVAILABLE"}) from None
    return Response(
        data,
        media_type=asset["mime_type"],
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/submissions/{sid}/assets/{aid}/pages/{page}")
def pdf_page(sid: UUID, aid: UUID, page: int, actor: Actor):
    asset = run(_asset, sid, aid, actor)
    if asset["asset_type"] not in ("IMAGE", "PDF") or not 1 <= page <= (asset["page_count"] or 1):
        raise HTTPException(404, detail={"code": "PAGE_NOT_FOUND"})
    try:
        data = object_store.read_bytes(asset["object_key"])
        png = next(
            png for number, png in media_processing.raster_pages(data, asset) if number == page
        )
    except (OSError, RuntimeError):
        raise HTTPException(503, detail={"code": "OBJECT_STORAGE_UNAVAILABLE"}) from None
    return Response(png, media_type="image/png", headers={"Cache-Control": "private, no-store"})


def _begin(conn, sid, actor, expected, analysis=False):
    row = runtime.submission(conn, sid, actor, lock=True, expected=expected)
    if analysis:
        runtime.ensure_approved(conn, row)
    if row["status"] in ("TRANSCRIBING", "ALIGNING", "CRITIQUING"):
        raise runtime.MediaError(409, "PROCESSING_ALREADY_RUNNING")
    runtime.set_status(
        conn,
        row,
        "ALIGNING" if analysis else "TRANSCRIBING",
        "attempt.analysis.started" if analysis else "attempt.transcription.started",
    )
    return runtime.snapshot(conn, sid, actor)


def _failure(conn, sid, actor, expected, code):
    row = runtime.submission(conn, sid, actor, lock=True)
    if row["transcription_version"] == expected:
        conn.execute(
            text(
                "UPDATE attempt_media.submission SET status='FAILED',error_code=:code "
                "WHERE submission_id=:id"
            ),
            {"id": str(sid), "code": code},
        )
        runtime.event(conn, row, "attempt.processing.failed", {"code": code})


@router.post("/submissions/{sid}/process")
def process(sid: UUID, body: Versioned, actor: Actor):
    """Explicit paid transcription request. Errors preserve uploads for manual review."""
    view = run(_begin, sid, actor, body.expected_version)
    try:
        regions, lines, machine = [], [], []
        originals = [a for a in view["assets"] if a["role"] == "ORIGINAL" and not a["purged_at"]]
        if not originals:
            raise runtime.MediaError(422, "UPLOAD_MEDIA_FIRST")
        for asset in originals:
            full = run(_asset, sid, asset["media_asset_id"], actor)
            data = object_store.read_bytes(full["object_key"])
            if asset["asset_type"] in ("IMAGE", "PDF"):
                new_regions, new_lines = TRANSCRIBE_IMAGE(data, asset)
            elif asset["asset_type"] == "AUDIO":
                new_regions, new_lines = TRANSCRIBE_SPEECH(data, asset)
            else:
                audio, frames = media_processing.video_derivatives(data)
                speech_asset = {**asset, "mime_type": "audio/wav"}
                new_regions, new_lines = (
                    TRANSCRIBE_SPEECH(audio, speech_asset) if audio is not None else ([], [])
                )
                for timestamp, png in frames:
                    stored = object_store.put_bytes(png, ".png")

                    def frame_op(conn, stored=stored, asset=asset, timestamp=timestamp):
                        runtime.submission(
                            conn, sid, actor, lock=True, expected=body.expected_version
                        )
                        return _store_asset(
                            conn,
                            sid,
                            {
                                "asset_type": "IMAGE",
                                "mime_type": "image/png",
                                "page_count": 1,
                                "duration_ms": None,
                            },
                            stored,
                            role="KEYFRAME",
                            parent=str(asset["media_asset_id"]),
                            timestamp=timestamp,
                        )

                    try:
                        frame_asset = run(frame_op)
                    except Exception:
                        object_store.delete_object(stored["object_key"])
                        raise
                    frame_regions, frame_lines = TRANSCRIBE_IMAGE(png, frame_asset)
                    temporal_id = str(uuid4())
                    if frame_lines:
                        new_regions.append(
                            {
                                "region_id": temporal_id,
                                "media_asset_id": str(asset["media_asset_id"]),
                                "start_ms": timestamp,
                                "end_ms": min(asset["duration_ms"], timestamp + 1),
                                "region_type": "KEYFRAME",
                                "reading_order": len(new_regions),
                                "confidence": 1,
                            }
                        )
                        for line in frame_lines:
                            line["evidence_ids"].append(temporal_id)
                    new_regions.extend(frame_regions)
                    new_lines.extend(frame_lines)
            regions.extend(new_regions)
            lines.extend(new_lines)
            machine.append(
                {
                    "asset_id": str(asset["media_asset_id"]),
                    "regions": new_regions,
                    "lines": new_lines,
                }
            )

            line_count = len(lines)

            def progress(conn, asset=asset, count=line_count):
                row = runtime.submission(
                    conn, sid, actor, lock=True, expected=body.expected_version
                )
                runtime.event(
                    conn,
                    row,
                    "attempt.transcription.progress",
                    {"media_asset_id": str(asset["media_asset_id"]), "lines_ready": count},
                )

            run(progress)
        transcript = SEGMENT(regions, lines, body.expected_version)
        return run(
            runtime.save_transcript,
            sid,
            actor,
            transcript,
            machine=machine,
            profile=media_processing.MODEL,
        )
    except HTTPException as exc:
        if exc.status_code != 409:
            run(_failure, sid, actor, body.expected_version, "TRANSCRIPTION_RESULT_INVALID")
        raise
    except Exception as exc:  # noqa: BLE001 - persist an explicit failed stage without logging private output
        code = exc.code if isinstance(exc, runtime.MediaError) else "TRANSCRIPTION_UNAVAILABLE"
        log.warning("Multimodal transcription failed (%s)", type(exc).__name__)
        run(_failure, sid, actor, body.expected_version, code)
        raise HTTPException(
            exc.status_code if isinstance(exc, runtime.MediaError) else 502,
            detail={"code": code, "manual_review_available": True},
        ) from None


@router.get("/submissions/{sid}/transcription")
def transcription(sid: UUID, actor: Actor):
    return run(runtime.snapshot, sid, actor)


@router.put("/submissions/{sid}/transcription")
def replace(sid: UUID, body: Transcript, actor: Actor):
    if actor["role"] != "STUDENT":
        raise HTTPException(403, detail={"code": "STUDENT_EDIT_REQUIRED"})
    return run(runtime.save_transcript, sid, actor, body)


class StepPatch(Versioned):
    plain_text: str | None = Field(default=None, max_length=4000)
    latex_text: str | None = Field(default=None, max_length=8000)


@router.patch("/submissions/{sid}/transcription/steps/{step_id}")
def patch(sid: UUID, step_id: UUID, body: StepPatch, actor: Actor):
    view = run(runtime.snapshot, sid, actor)
    steps = [Step.model_validate({k: s[k] for k in Step.model_fields}) for s in view["steps"]]
    step = next((s for s in steps if s.step_id == step_id), None)
    if step is None:
        raise HTTPException(404, detail={"code": "STEP_NOT_FOUND"})
    for name in ("plain_text", "latex_text"):
        if getattr(body, name) is not None:
            setattr(step, name, getattr(body, name))
    return replace(sid, Transcript(expected_version=body.expected_version, steps=steps), actor)


@router.post("/submissions/{sid}/approve")
def approve(sid: UUID, body: Versioned, actor: Actor):
    return run(runtime.approve, sid, actor, body.expected_version)


class Merge(Versioned):
    step_ids: list[UUID] = Field(min_length=2, max_length=100)


@router.post("/submissions/{sid}/transcription/merge")
def merge(sid: UUID, body: Merge, actor: Actor):
    view = run(runtime.snapshot, sid, actor)
    selected = set(map(str, body.step_ids))
    positions = [i for i, s in enumerate(view["steps"]) if str(s["step_id"]) in selected]
    if (
        not positions
        or len(positions) != len(body.step_ids)
        or positions != list(range(min(positions), max(positions) + 1))
    ):
        raise HTTPException(422, detail={"code": "MERGE_REQUIRES_ADJACENT_UNIQUE_STEPS"})
    group = [view["steps"][i] for i in positions]
    combined = {k: group[0][k] for k in Step.model_fields}
    combined.update(
        plain_text="\n".join(s["plain_text"] for s in group),
        latex_text="\n".join(s["latex_text"] for s in group),
        confidence=min(s["confidence"] for s in group),
        evidence_ids=list(dict.fromkeys(str(e) for s in group for e in s["evidence_ids"])),
    )
    steps = view["steps"][: positions[0]] + [combined] + view["steps"][positions[-1] + 1 :]
    return replace(
        sid,
        Transcript(
            expected_version=body.expected_version,
            steps=[
                {**{k: s[k] for k in Step.model_fields}, "ordinal": i}
                for i, s in enumerate(steps, 1)
            ],
        ),
        actor,
    )


class Split(Versioned):
    step_id: UUID
    parts: list[Step] = Field(min_length=2, max_length=10)


@router.post("/submissions/{sid}/transcription/split")
def split(sid: UUID, body: Split, actor: Actor):
    view = run(runtime.snapshot, sid, actor)
    position = next(
        (i for i, s in enumerate(view["steps"]) if str(s["step_id"]) == str(body.step_id)), None
    )
    if position is None:
        raise HTTPException(404, detail={"code": "STEP_NOT_FOUND"})
    parts = [part.model_dump(mode="json") for part in body.parts]
    steps = view["steps"][:position] + parts + view["steps"][position + 1 :]
    return replace(
        sid,
        Transcript(
            expected_version=body.expected_version,
            steps=[
                {**{k: s[k] for k in Step.model_fields}, "ordinal": i}
                for i, s in enumerate(steps, 1)
            ],
        ),
        actor,
    )


def _approved(conn, aid, actor):
    row = (
        conn.execute(
            text("SELECT * FROM attempt_media.approval WHERE learner_attempt_id=:id"),
            {"id": str(aid)},
        )
        .mappings()
        .first()
    )
    if not row:
        raise runtime.MediaError(404, "APPROVED_ATTEMPT_NOT_FOUND")
    runtime.submission(conn, row["submission_id"], actor)
    return dict(row)


@router.get("/attempts/{aid}/steps")
def approved_steps(aid: UUID, actor: Actor):
    def op(conn):
        approval = _approved(conn, aid, actor)
        steps = [
            dict(r)
            for r in conn.execute(
                text(
                    "SELECT * FROM attempt_media.approved_step WHERE learner_attempt_id=:id ORDER BY ordinal"
                ),
                {"id": str(aid)},
            ).mappings()
        ]
        return {"approval": approval, "steps": steps}

    return run(op)


@router.get("/attempts/{aid}/steps/{step_id}/assessment")
@router.get("/attempts/{aid}/steps/{step_id}/visual")
def approved_assessment(aid: UUID, step_id: UUID, actor: Actor):
    def op(conn):
        approval = _approved(conn, aid, actor)
        row = (
            conn.execute(
                text(
                    "SELECT * FROM attempt_media.step_assessment WHERE submission_id=:id "
                    "AND approved_version=:v AND step_id=:step ORDER BY assessment_version DESC LIMIT 1"
                ),
                {
                    "id": str(approval["submission_id"]),
                    "v": approval["approved_version"],
                    "step": str(step_id),
                },
            )
            .mappings()
            .first()
        )
        if not row:
            raise runtime.MediaError(404, "ASSESSMENT_NOT_AVAILABLE")
        return dict(row)

    return run(op)


@router.post("/submissions/{sid}/analyse")
def analyse(sid: UUID, body: Versioned, actor: Actor):
    """Explicit paid alignment then critique; uncertainty does not change mastery."""
    view = run(_begin, sid, actor, body.expected_version, analysis=True)
    try:
        with engine.connect() as conn:
            canonical_steps = [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT solution_step_id,step_text,step_type,concept_node_id,skill_node_id "
                        "FROM pedagogy.solution_step WHERE problem_id=:problem AND publication_status='PUBLISHED' "
                        "ORDER BY global_step_index LIMIT 100"
                    ),
                    {"problem": str(view["problem_id"])},
                ).mappings()
            ]
            statement = conn.execute(
                text("SELECT statement_text FROM core.problem WHERE problem_id=:problem"),
                {"problem": str(view["problem_id"])},
            ).scalar_one()
            dependencies = [
                dict(r)
                for r in conn.execute(
                    text(
                        "SELECT d.from_step_id,d.to_step_id,d.relationship_type,d.logical_dependency "
                        "FROM pedagogy.solution_step_dependency d JOIN pedagogy.solution_step s "
                        "ON s.solution_step_id=d.to_step_id WHERE s.problem_id=:problem "
                        "AND d.review_status='REVIEWED' AND s.publication_status='PUBLISHED'"
                    ),
                    {"problem": str(view["problem_id"])},
                ).mappings()
            ]
            canonical = {
                "statement": statement,
                "steps": canonical_steps,
                "dependencies": dependencies,
            }
        assessed = ANALYSE(view, canonical)
        return run(runtime.save_assessments, sid, actor, body.expected_version, assessed)
    except HTTPException as exc:
        if exc.status_code != 409:
            run(_failure, sid, actor, body.expected_version, "ANALYSIS_RESULT_INVALID")
        raise
    except Exception as exc:  # noqa: BLE001 - persist failure without disclosing provider data
        code = exc.code if isinstance(exc, runtime.MediaError) else "ANALYSIS_UNAVAILABLE"
        log.warning("Multimodal analysis failed (%s)", type(exc).__name__)
        run(_failure, sid, actor, body.expected_version, code)
        raise HTTPException(
            exc.status_code if isinstance(exc, runtime.MediaError) else 502,
            detail={"code": code, "approved_attempt_preserved": True},
        ) from None


@router.post("/submissions/{sid}/override")
def override(sid: UUID, body: Override, actor: Actor):
    if actor["role"] != "ADMIN":
        raise HTTPException(403, detail={"code": "INSTRUCTOR_REQUIRED"})
    view = run(runtime.snapshot, sid, actor)
    step = next((s for s in view["steps"] if str(s["step_id"]) == str(body.step_id)), None)
    if not step:
        raise HTTPException(404, detail={"code": "STEP_NOT_FOUND"})
    result = Assessment(
        step_id=body.step_id,
        correctness=body.correctness,
        why=body.why,
        next_action=body.next_action,
        alignment_type=body.alignment_type,
        confidence=1,
        evidence_ids=step["evidence_ids"],
    )
    return run(
        runtime.save_assessments, sid, actor, body.expected_version, [result], source="INSTRUCTOR"
    )


@router.delete("/submissions/{sid}/assets/{aid}")
def purge(sid: UUID, aid: UUID, actor: Actor):
    # Lock prevents a simultaneous approval or processing commit from using purged evidence.
    def op(conn):
        row = runtime.submission(conn, sid, actor, lock=True)
        asset = _asset(conn, sid, aid, actor)
        if row["status"] in ("TRANSCRIBING", "ALIGNING", "CRITIQUING"):
            raise runtime.MediaError(409, "WAIT_FOR_PROCESSING_BEFORE_PURGE")
        descendants = [
            dict(r)
            for r in conn.execute(
                text(
                    "SELECT media_asset_id,object_key FROM attempt_media.media_asset "
                    "WHERE submission_id=:id AND (media_asset_id=:asset OR parent_asset_id=:asset) "
                    "AND purged_at IS NULL"
                ),
                {"id": str(sid), "asset": str(aid)},
            ).mappings()
        ]
        for item in descendants:
            object_store.delete_object(item["object_key"])
            conn.execute(
                text(
                    "UPDATE attempt_media.media_asset SET purged_at=now() WHERE media_asset_id=:asset"
                ),
                {"asset": item["media_asset_id"]},
            )
        runtime.event(
            conn, row, "attempt.media.purged", {"media_asset_id": str(asset["media_asset_id"])}
        )
        return {"purged": True, "approved_attempt_preserved": True}

    try:
        return run(op)
    except (OSError, RuntimeError):
        raise HTTPException(503, detail={"code": "OBJECT_STORAGE_UNAVAILABLE"}) from None
