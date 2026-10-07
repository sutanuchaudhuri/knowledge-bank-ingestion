"""Bounded media normalization and faithful, separately staged model processing."""

from __future__ import annotations

import base64
import io
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Literal
from uuid import uuid4

import fitz
from pydantic import BaseModel, ConfigDict

from mathbank_rest import runtime_ai
from mathbank_rest.attempt_media import MediaError
from mathbank_rest.attempt_media_models import Assessment, Transcript

MAX_BYTES = 20 * 1024 * 1024
MAX_DURATION_MS = 120_000
MODEL = runtime_ai.model_name()
MAX_OUTPUT_TOKENS = 8000


class ImageLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plain_text: str
    latex_text: str
    step_type: Literal["OBSERVATION", "ALGEBRA", "RATIO", "CONCLUSION", "QUESTION_OR_UNCERTAINTY"]
    confidence: float
    x_norm: float
    y_norm: float
    width_norm: float
    height_norm: float
    region_type: Literal[
        "MATH_LINE", "PROSE_LINE", "SCRATCH", "CANCELLED", "DIAGRAM_LABEL", "DIAGRAM_MARK"
    ]


class ImageTranscription(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lines: list[ImageLine]


def media_info(data: bytes, mime: str) -> dict:
    if not data or len(data) > MAX_BYTES:
        raise MediaError(413, "MEDIA_SIZE_LIMIT")
    mime = mime.split(";")[0].lower()
    types = {
        "image/png": (b"\x89PNG\r\n\x1a\n", "IMAGE", ".png"),
        "image/jpeg": (b"\xff\xd8\xff", "IMAGE", ".jpg"),
        "application/pdf": (b"%PDF-", "PDF", ".pdf"),
        "audio/wav": (b"RIFF", "AUDIO", ".wav"),
        "audio/x-wav": (b"RIFF", "AUDIO", ".wav"),
        "audio/mpeg": (None, "AUDIO", ".mp3"),
        "audio/mp4": (None, "AUDIO", ".m4a"),
        "audio/webm": (b"\x1a\x45\xdf\xa3", "AUDIO", ".webm"),
        "video/webm": (b"\x1a\x45\xdf\xa3", "VIDEO", ".webm"),
        "video/mp4": (None, "VIDEO", ".mp4"),
    }
    if mime not in types:
        raise MediaError(415, "UNSUPPORTED_MEDIA_TYPE")
    magic, kind, suffix = types[mime]
    if magic and not data.startswith(magic):
        raise MediaError(415, "MEDIA_SIGNATURE_MISMATCH")
    if mime == "audio/mpeg" and not (data.startswith(b"ID3") or data[0] == 0xFF):
        raise MediaError(415, "MEDIA_SIGNATURE_MISMATCH")
    if mime in ("audio/mp4", "video/mp4") and data[4:8] != b"ftyp":
        raise MediaError(415, "MEDIA_SIGNATURE_MISMATCH")
    result = {
        "asset_type": kind,
        "mime_type": mime,
        "suffix": suffix,
        "page_count": None,
        "duration_ms": None,
    }
    if kind in ("PDF", "IMAGE"):
        try:
            with fitz.open(stream=data, filetype="pdf" if kind == "PDF" else suffix[1:]) as doc:
                if doc.needs_pass or not 1 <= doc.page_count <= 10:
                    raise MediaError(422, "PDF_PAGE_OR_PASSWORD_LIMIT")
                if any(page.rect.width * page.rect.height > 25_000_000 for page in doc):
                    raise MediaError(422, "IMAGE_RESOLUTION_LIMIT")
                result["page_count"] = doc.page_count
        except (RuntimeError, ValueError):
            raise MediaError(422, "MEDIA_DECODE_FAILED") from None
    else:
        if not shutil.which("ffprobe"):
            raise MediaError(503, "FFPROBE_REQUIRED")
        with tempfile.TemporaryDirectory(prefix="mathbank-media-") as folder:
            path = Path(folder) / ("source" + suffix)
            path.write_bytes(data)
            try:
                proc = subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration:stream=codec_type",
                        "-of",
                        "json",
                        str(path),
                    ],
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
                if proc.returncode:
                    raise MediaError(422, "MEDIA_DECODE_FAILED")
                info = json.loads(proc.stdout)
                duration = round(float(info["format"]["duration"]) * 1000)
                if not 0 < duration <= MAX_DURATION_MS:
                    raise MediaError(422, "MEDIA_DURATION_LIMIT")
                expected = "video" if kind == "VIDEO" else "audio"
                if not any(s.get("codec_type") == expected for s in info.get("streams", [])):
                    raise MediaError(422, "MEDIA_STREAM_MISSING")
                result["duration_ms"] = duration
            except (subprocess.TimeoutExpired, ValueError, KeyError):
                raise MediaError(422, "MEDIA_PROBE_FAILED") from None
    return result


def raster_pages(data, asset):
    filetype = (
        "pdf"
        if asset["asset_type"] == "PDF"
        else ("png" if asset["mime_type"] == "image/png" else "jpg")
    )
    with fitz.open(stream=data, filetype=filetype) as doc:
        for number, page in enumerate(doc, 1):
            scale = min(2, 1600 / max(page.rect.width, page.rect.height))
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            yield number, pix.tobytes("png")


def json_stage(system, content, output_model=None):
    response_format = {"type": "json_object"}
    if output_model is not None:
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": output_model.__name__,
                "strict": True,
                "schema": output_model.model_json_schema(),
            },
        }
    response = runtime_ai.client().chat.completions.create(
        model=MODEL,
        max_completion_tokens=MAX_OUTPUT_TOKENS,
        response_format=response_format,
        messages=[
            {"role": "system", "content": system + "\nReturn only a valid JSON object."},
            {"role": "user", "content": content},
        ],
    )
    if not response.choices or response.choices[0].finish_reason != "stop":
        raise MediaError(502, "MODEL_OUTPUT_INCOMPLETE")
    output = json.loads(response.choices[0].message.content or "")
    if output_model is not None:
        return output_model.model_validate(output).model_dump()
    return output


def transcribe_image(data, asset):
    regions, lines = [], []
    for page, png in raster_pages(data, asset):
        output = json_stage(
            "Faithfully transcribe student's handwriting, including ALL mathematical mistakes, scratch and "
            "cancelled work. Do not critique, solve, or repair mathematics. Return JSON {lines:[{plain_text,"
            "latex_text,step_type,confidence,x_norm,y_norm,width_norm,height_norm,region_type}]}. "
            "Coordinates are 0..1 relative to this image. Preserve reading order. Flag unreadable content "
            "explicitly at low confidence. Each mathematical line must have faithful LaTeX. "
            "step_type is OBSERVATION or ALGEBRA or RATIO or CONCLUSION or QUESTION_OR_UNCERTAINTY. "
            "region_type is MATH_LINE, PROSE_LINE, SCRATCH, CANCELLED, DIAGRAM_LABEL or DIAGRAM_MARK.",
            [
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode()},
                }
            ],
            ImageTranscription,
        )
        for line in output["lines"]:
            eid = str(uuid4())
            regions.append(
                {
                    "region_id": eid,
                    "media_asset_id": str(asset["media_asset_id"]),
                    "page_number": page,
                    "reading_order": len(regions),
                    **{
                        k: line[k]
                        for k in (
                            "x_norm",
                            "y_norm",
                            "width_norm",
                            "height_norm",
                            "region_type",
                            "confidence",
                        )
                    },
                }
            )
            lines.append(
                {k: line[k] for k in ("plain_text", "latex_text", "step_type", "confidence")}
                | {"evidence_ids": [eid]}
            )
    return regions, lines


def transcribe_speech(data, asset):
    stream = io.BytesIO(data)
    stream.name = "attempt" + {
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/webm": ".webm",
    }.get(asset["mime_type"], ".wav")
    raw = runtime_ai.speech_client().audio.transcriptions.create(
        model="whisper-1",
        file=stream,
        response_format="verbose_json",
        timestamp_granularities=["segment"],
    )
    regions, lines = [], []
    if not raw.segments:
        raise MediaError(422, "NO_TIMESTAMPED_SPEECH")
    for segment in raw.segments:
        eid = str(uuid4())
        start = round(segment.start * 1000)
        end = min(asset["duration_ms"], round(segment.end * 1000))
        regions.append(
            {
                "region_id": eid,
                "media_asset_id": str(asset["media_asset_id"]),
                "start_ms": start,
                "end_ms": end,
                "reading_order": len(regions),
                "confidence": 0.7,
                "region_type": "SPEECH",
            }
        )
        output = json_stage(
            "Convert spoken mathematical notation to LaTeX without correcting the mathematics. "
            "Preserve mistakes and uncertainty. Return {latex_text:string,confidence:number 0..1}.",
            segment.text,
        )
        lines.append(
            {
                "plain_text": segment.text,
                "latex_text": output["latex_text"],
                "confidence": min(0.7, output["confidence"]),
                "step_type": "OBSERVATION",
                "evidence_ids": [eid],
            }
        )
    return regions, lines


def video_derivatives(data):
    if not shutil.which("ffmpeg"):
        raise MediaError(503, "FFMPEG_REQUIRED")
    if not shutil.which("ffprobe"):
        raise MediaError(503, "FFPROBE_REQUIRED")
    with tempfile.TemporaryDirectory(prefix="mathbank-video-") as folder:
        root = Path(folder)
        (root / "source").write_bytes(data)
        try:
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "a",
                    "-show_entries",
                    "stream=codec_type",
                    "-of",
                    "json",
                    str(root / "source"),
                ],
                capture_output=True,
                timeout=15,
                check=False,
            )
            if probe.returncode:
                raise MediaError(422, "MEDIA_PROBE_FAILED")
            try:
                has_audio = bool(json.loads(probe.stdout)["streams"])
            except (ValueError, KeyError):
                raise MediaError(422, "MEDIA_PROBE_FAILED") from None
            audio = (
                subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-nostdin",
                        "-i",
                        str(root / "source"),
                        "-vn",
                        "-ac",
                        "1",
                        "-ar",
                        "16000",
                        str(root / "speech.wav"),
                    ],
                    capture_output=True,
                    timeout=40,
                    check=False,
                )
                if has_audio
                else None
            )
            frames = subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "info",
                    "-nostdin",
                    "-i",
                    str(root / "source"),
                    "-vf",
                    "select='isnan(prev_selected_t)+gte(t-prev_selected_t,10)',showinfo,scale=1280:-2",
                    "-vsync",
                    "vfr",
                    "-frames:v",
                    "12",
                    str(root / "frame-%02d.png"),
                ],
                capture_output=True,
                timeout=40,
                check=False,
            )
            if (audio is not None and audio.returncode) or frames.returncode:
                raise MediaError(422, "VIDEO_NORMALIZATION_FAILED")
            times = [
                round(float(value) * 1000)
                for value in re.findall(
                    r"showinfo[^\n]*n:\s*\d+[^\n]*pts_time:([0-9.]+)",
                    frames.stderr.decode(errors="replace"),
                )
            ]
            paths = sorted(root.glob("frame-*.png"))
            if len(times) != len(paths):
                raise MediaError(422, "KEYFRAME_TIMESTAMPS_UNAVAILABLE")
            return (root / "speech.wav").read_bytes() if has_audio else None, [
                (timestamp, path.read_bytes()) for timestamp, path in zip(times, paths)
            ]
        except subprocess.TimeoutExpired:
            raise MediaError(422, "VIDEO_NORMALIZATION_TIMEOUT") from None


def segment(regions, lines, version):
    if not lines:
        raise MediaError(422, "NO_TRANSCRIPTION_STEPS")
    # Segmentation is a distinct stage, never allowed to invent or rewrite content.
    output = json_stage(
        "Group transcript LINE INDICES into mathematical reasoning steps, not sentence-based splits. "
        "Do not rewrite, correct or omit ANY line. Return {groups:[[zero_based_indices]]}; "
        "each line must occur exactly once in original order. Adjacent lines can form one step.",
        json.dumps([{"index": i, **line} for i, line in enumerate(lines)], default=str),
    )
    groups = output["groups"]
    if (
        not groups
        or any(not group for group in groups)
        or [index for group in groups for index in group] != list(range(len(lines)))
    ):
        raise MediaError(502, "SEGMENTATION_INVENTORY_INVALID")
    steps = []
    for ordinal, group in enumerate(groups, 1):
        selected = [lines[index] for index in group]
        steps.append(
            {
                "ordinal": ordinal,
                "plain_text": "\n".join(s["plain_text"] for s in selected),
                "latex_text": "\n".join(s["latex_text"] for s in selected),
                "step_type": selected[0]["step_type"],
                "confidence": min(s["confidence"] for s in selected),
                "evidence_ids": [eid for s in selected for eid in s["evidence_ids"]],
            }
        )
    return Transcript(expected_version=version, regions=regions, steps=steps)


def analyse(view, canonical):
    alignments = json_stage(
        "Align APPROVED student steps to supplied canonical DAG steps. Allow valid alternate reasoning. "
        "Similarity is not correctness. Return {alignments:[{step_id,alignment_type,canonical_solution_step_id}]}. "
        "alignment_type is MATCHES_SOLUTION_STEP, VALID_ALTERNATE_STEP, PARTIAL_STEP, PREREQUISITE_STEP, "
        "IRRELEVANT_STEP, UNSUPPORTED_LEAP, UNMATCHED_BUT_PLAUSIBLE. Use null canonical ID when uncertain. "
        "Return exactly every approved step, preserve IDs; no assessments yet.",
        json.dumps({"steps": view["steps"], "canonical": canonical}, default=str),
    )
    mapped = {a["step_id"]: a for a in alignments["alignments"]}
    if set(mapped) != {str(s["step_id"]) for s in view["steps"]}:
        raise MediaError(502, "ALIGNMENT_INVENTORY_INVALID")
    output = json_stage(
        "Critique APPROVED mathematics against its preceding flow, not merely the canonical answer. "
        "Treat valid alternate methods fairly. A true unsupported assertion is UNJUSTIFIED. "
        "confidence<0.7 transcription must yield UNCERTAIN, not learner blame. Never reveal the full "
        "solution or next complete canonical step. Give repair, directional hint, concept reminder or "
        "prerequisite recovery. Cite only provided evidence IDs (timestamps/rectangles). "
        "Return {assessments:[{step_id,correctness,alignment_type,canonical_solution_step_id,confidence,"
        "why,failure_mode,next_action,evidence_ids}]}; correctness CORRECT/PARTIALLY_CORRECT/INCORRECT/"
        "UNJUSTIFIED/UNCERTAIN. Preserve supplied alignment fields. Exactly one assessment per step.",
        json.dumps(
            {
                "steps": view["steps"],
                "regions": view["regions"],
                "alignments": mapped,
                "canonical": canonical,
            },
            default=str,
        ),
    )
    assessments = [Assessment.model_validate(a) for a in output["assessments"]]
    for assessment in assessments:
        aligned = mapped.get(str(assessment.step_id))
        if (
            not aligned
            or assessment.alignment_type != aligned["alignment_type"]
            or (assessment.canonical_solution_step_id != aligned["canonical_solution_step_id"])
        ):
            raise MediaError(502, "CRITIQUE_ALIGNMENT_MISMATCH")
    return assessments
