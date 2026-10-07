"""Offline evidence, ownership, approval and stage-version regressions."""

from datetime import UTC
from unittest.mock import MagicMock
from uuid import uuid4

import fitz
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from mathbank_rest import attempt_media as runtime
from mathbank_rest import media_processing
from mathbank_rest.attempt_media_models import Region, Step, Transcript
from mathbank_rest.main import app
from mathbank_rest.routers import attempt_media as routes
from mathbank_rest.routers.fluid import staff_or_student


def region(**extra):
    return {
        "media_asset_id": uuid4(),
        "page_number": 1,
        "x_norm": 0.1,
        "y_norm": 0.2,
        "width_norm": 0.5,
        "height_norm": 0.1,
        **extra,
    }


@pytest.mark.parametrize(
    "extra",
    [
        {"width_norm": 0.95},
        {"height_norm": 0},
        {"x_norm": -1},
        {"start_ms": 1, "end_ms": 3},
        {"page_number": None},
    ],
)
def test_invalid_rectangles_are_rejected(extra):
    with pytest.raises(ValidationError):
        Region(**region(**extra))


def test_spatial_and_temporal_evidence_are_typed_and_exact():
    assert Region(**region()).page_number == 1
    timed = Region(media_asset_id=uuid4(), start_ms=11200, end_ms=17800, region_type="SPEECH")
    assert timed.end_ms - timed.start_ms == 6600
    with pytest.raises(ValidationError):
        Region(media_asset_id=uuid4(), start_ms=1000, end_ms=999)


def test_steps_require_evidence_and_stable_order():
    eid = uuid4()
    step = Step(ordinal=1, latex_text="x=2", evidence_ids=[eid])
    with pytest.raises(ValidationError):
        Step(ordinal=1, latex_text="x=2", evidence_ids=[])
    with pytest.raises(ValidationError):
        Transcript(expected_version=1, steps=[step, step])
    with pytest.raises(ValidationError):
        Transcript(expected_version=1, steps=[step.model_copy(update={"ordinal": 2})])


def test_owner_scope_is_non_enumerable_and_stale_version_rejected():
    conn = MagicMock()
    owner, stranger = str(uuid4()), str(uuid4())
    conn.execute.return_value.mappings.return_value.first.return_value = {
        "student_id": owner,
        "transcription_version": 2,
    }
    with pytest.raises(runtime.MediaError) as exc:
        runtime.submission(conn, uuid4(), {"role": "STUDENT", "student_id": stranger})
    assert exc.value.status_code == 404
    with pytest.raises(runtime.MediaError) as exc:
        runtime.submission(conn, uuid4(), {"role": "STUDENT", "student_id": owner}, expected=1)
    assert exc.value.code == "TRANSCRIPTION_VERSION_CONFLICT"


def test_only_student_can_approve_and_no_empty_approval(monkeypatch):
    conn = MagicMock()
    monkeypatch.setattr(runtime, "submission", lambda *a, **kw: {"transcription_version": 1})
    with pytest.raises(runtime.MediaError, match="STUDENT_APPROVAL_REQUIRED"):
        runtime.approve(conn, uuid4(), {"role": "ADMIN"}, 1)
    conn.execute.return_value.mappings.return_value.first.return_value = None
    monkeypatch.setattr(runtime, "snapshot", lambda *a: {"steps": []})
    with pytest.raises(runtime.MediaError, match="NO_STEPS_TO_APPROVE"):
        runtime.approve(conn, uuid4(), {"role": "STUDENT"}, 1)
    assert not any("INSERT INTO learner.attempt" in str(c) for c in conn.execute.call_args_list)


def test_faithful_image_transcription_does_not_repair_wrong_math(monkeypatch):
    asset = {"media_asset_id": uuid4(), "asset_type": "IMAGE", "mime_type": "image/png"}
    monkeypatch.setattr(media_processing, "raster_pages", lambda *a: [(1, b"test-image")])
    monkeypatch.setattr(
        media_processing,
        "json_stage",
        lambda system, content, output_model=None: {
            "lines": [
                {
                    "plain_text": "1+1=3",
                    "latex_text": "1+1=3",
                    "step_type": "ALGEBRA",
                    "confidence": 0.9,
                    "x_norm": 0.1,
                    "y_norm": 0.1,
                    "width_norm": 0.5,
                    "height_norm": 0.1,
                    "region_type": "MATH_LINE",
                }
            ]
        },
    )
    regions, lines = media_processing.transcribe_image(b"x", asset)
    assert lines[0]["latex_text"] == "1+1=3"
    assert lines[0]["plain_text"] == "1+1=3"
    assert lines[0]["evidence_ids"] == [regions[0]["region_id"]]


def test_segmentation_preserves_wrong_latex_and_every_source_line(monkeypatch):
    eid = uuid4()
    lines = [
        {
            "plain_text": "wrong",
            "latex_text": "1+1=3",
            "step_type": "ALGEBRA",
            "confidence": 0.9,
            "evidence_ids": [eid],
        }
    ]
    monkeypatch.setattr(media_processing, "json_stage", lambda *a: {"groups": [[0]]})
    result = media_processing.segment([], lines, 4)
    assert result.steps[0].latex_text == "1+1=3"
    monkeypatch.setattr(media_processing, "json_stage", lambda *a: {"groups": [[0, 0]]})
    with pytest.raises(runtime.MediaError, match="SEGMENTATION_INVENTORY_INVALID"):
        media_processing.segment([], lines, 4)


def test_pdf_page_numbers_and_original_bytes_preserved():
    with fitz.open() as doc:
        doc.new_page()
        doc.new_page()
        pdf = doc.tobytes()
    info = media_processing.media_info(pdf, "application/pdf")
    assert info["page_count"] == 2
    assert [page for page, _ in media_processing.raster_pages(pdf, info)] == [1, 2]
    with pytest.raises(runtime.MediaError, match="MEDIA_SIGNATURE_MISMATCH"):
        media_processing.media_info(b"<script>not a PDF</script>", "application/pdf")
    with pytest.raises(runtime.MediaError, match="UNSUPPORTED_MEDIA_TYPE"):
        media_processing.media_info(b"unsafe", "image/svg+xml")


def test_private_routes_require_authentication_and_instructor_override_is_staff_only():
    client = TestClient(app)
    sid = str(uuid4())
    assert client.get(f"/v1/attempt-media/submissions/{sid}").status_code == 401
    assert client.get(f"/v1/attempt-media/submissions/{sid}/events").status_code == 401
    app.dependency_overrides[staff_or_student] = lambda: {
        "role": "STUDENT",
        "student_id": str(uuid4()),
    }
    try:
        response = client.post(
            f"/v1/attempt-media/submissions/{sid}/override",
            json={
                "expected_version": 1,
                "step_id": str(uuid4()),
                "correctness": "CORRECT",
                "why": "Instructor explanation",
                "next_action": "Continue",
            },
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_stale_processing_result_is_not_disguised_as_provider_failure(monkeypatch):
    monkeypatch.setattr(
        routes,
        "run",
        lambda fn, *a, **kw: (
            {
                "assets": [
                    {
                        "role": "ORIGINAL",
                        "purged_at": None,
                        "asset_type": "IMAGE",
                        "media_asset_id": uuid4(),
                    }
                ]
            }
            if fn is routes._begin
            else (_ for _ in ()).throw(HTTPException(409, detail="stale"))
        ),
    )
    with pytest.raises(HTTPException) as exc:
        routes.process(uuid4(), routes.Versioned(expected_version=1), {"role": "STUDENT"})
    assert exc.value.status_code == 409


def test_pending_work_does_not_reduce_mastery():
    from datetime import datetime

    from mathbank_rest.mastery import compute_mastery_score

    now = datetime.now(UTC)
    evaluated = {"is_correct": True, "attempted_at": now, "difficulty_band": None}
    pending = {"is_correct": None, "attempted_at": now, "difficulty_band": None}
    assert compute_mastery_score([evaluated, pending], now=now) == compute_mastery_score(
        [evaluated], now=now
    )


def test_audio_transcript_has_exact_timestamp_evidence_and_preserves_raw_speech(monkeypatch):
    provider = MagicMock()
    segment = MagicMock()
    segment.start, segment.end, segment.text = 11.2, 17.8, "AB should correspond to AE."
    provider.audio.transcriptions.create.return_value.segments = [segment]
    monkeypatch.setattr(media_processing.runtime_ai, "speech_client", lambda: provider)
    monkeypatch.setattr(
        media_processing,
        "json_stage",
        lambda *a: {"latex_text": r"AB\leftrightarrow AE", "confidence": 0.8},
    )
    asset = {"media_asset_id": uuid4(), "duration_ms": 20000, "mime_type": "audio/wav"}
    regions, lines = media_processing.transcribe_speech(b"synthetic", asset)
    assert regions[0]["start_ms"] == 11200 and regions[0]["end_ms"] == 17800
    assert lines[0]["plain_text"] == segment.text
    assert lines[0]["evidence_ids"] == [regions[0]["region_id"]]
    assert provider.audio.transcriptions.create.call_args.kwargs["model"] == "whisper-1"


@pytest.mark.parametrize("has_audio", [True, False])
def test_video_normalization_uses_actual_frame_timestamps(tmp_path, has_audio):
    import shutil
    import subprocess

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe optional media tools unavailable")
    video = tmp_path / "synthetic.mp4"
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-nostdin",
        "-f",
        "lavfi",
        "-i",
        "color=c=white:s=320x240:d=2",
    ]
    if has_audio:
        command += ["-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-shortest"]
    command += [
        "-pix_fmt",
        "yuv420p",
        str(video),
    ]
    proc = subprocess.run(
        command,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert proc.returncode == 0
    data = video.read_bytes()
    info = media_processing.media_info(data, "video/mp4")
    assert 1900 <= info["duration_ms"] <= 2100
    audio, frames = media_processing.video_derivatives(data)
    assert audio.startswith(b"RIFF") if has_audio else audio is None
    assert len(frames) == 1
    assert frames[0][0] == 0
    assert frames[0][1].startswith(b"\x89PNG")


def test_mutated_step_is_revalidated_before_saving_transcript():
    step = Step(ordinal=1, plain_text="Original student work", evidence_ids=[uuid4()])
    step.plain_text = ""
    with pytest.raises(ValidationError):
        Transcript(expected_version=1, steps=[step])


def test_json_stage_always_satisfies_openai_json_mode_prompt(monkeypatch):
    provider = MagicMock()
    response = provider.chat.completions.create.return_value
    response.choices[0].finish_reason = "stop"
    response.choices[0].message.content = '{"groups":[[0]]}'
    monkeypatch.setattr(media_processing.runtime_ai, "client", lambda: provider)
    assert media_processing.json_stage("Group line indices.", "line") == {"groups": [[0]]}
    request = provider.chat.completions.create.call_args.kwargs
    assert request["response_format"] == {"type": "json_object"}
    assert "JSON" in request["messages"][0]["content"]


def test_transcription_uses_strict_schema_and_distinct_step_region_types(monkeypatch):
    provider = MagicMock()
    response = provider.chat.completions.create.return_value
    response.choices[0].finish_reason = "stop"
    response.choices[0].message.content = '{"lines":[]}'
    monkeypatch.setattr(media_processing.runtime_ai, "client", lambda: provider)
    assert media_processing.json_stage(
        "Transcribe.", "synthetic", media_processing.ImageTranscription
    ) == {"lines": []}
    response_format = provider.chat.completions.create.call_args.kwargs["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"]
    fields = response_format["json_schema"]["schema"]["$defs"]["ImageLine"]["properties"]
    assert "PROSE_LINE" in fields["region_type"]["enum"]
    assert "PROSE_LINE" not in fields["step_type"]["enum"]
