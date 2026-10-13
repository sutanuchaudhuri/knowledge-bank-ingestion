"""Opt-in synthetic quality gates. No database, storage, or real learner data."""

import json
import math
import os
import subprocess
from pathlib import Path
from uuid import UUID, uuid4

import fitz
import pytest
from openai import APIError

from mathbank_rest import media_processing as media
from mathbank_rest import runtime_ai

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_AI_QUALITY_LIVE") != "1",
    reason="Explicitly opt in to paid synthetic OpenAI quality checks",
)


class Meter:
    """Reserve a deliberately conservative ceiling before every paid request."""

    def __init__(self, client):
        self.client = client
        self.reserved = 0.0
        self.calls = []

    def reserve(self, ceiling):
        if self.reserved + ceiling > 9:
            raise RuntimeError("Synthetic quality-test reservation would exceed $9")
        self.reserved += ceiling

    def chat(self, **kwargs):
        serialized = json.dumps(kwargs["messages"])
        image_count = serialized.count("data:image/png;base64,")
        # GPT-4o-mini's image tokens can exceed 36,000 even for this small fixture.
        text_length = sum(
            len(json.dumps(message["content"])) if isinstance(message["content"], str) else 1000
            for message in kwargs["messages"]
        )
        self.reserve((text_length + image_count * 50000 + 1800) * 0.0001)
        kwargs["max_completion_tokens"] = 1800
        response = self.client.chat.completions.create(**kwargs)
        self.calls.append(
            {
                "stage": "chat",
                "model": kwargs["model"],
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }
        )
        return response

    def speech(self, **kwargs):
        self.reserve(0.10)  # Only the bounded, locally synthesized ten-second clip.
        response = self.client.audio.transcriptions.create(**kwargs)
        self.calls.append({"stage": "speech", "model": kwargs["model"]})
        return response

    def embed(self, **kwargs):
        self.reserve(sum(len(text) for text in kwargs["input"]) * 0.0001)
        response = self.client.embeddings.create(**kwargs)
        self.calls.append(
            {
                "stage": "embedding",
                "model": kwargs["model"],
                "input_tokens": response.usage.total_tokens,
            }
        )
        return response


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b)) / math.sqrt(
        sum(x * x for x in a) * sum(y * y for y in b)
    )


def test_synthetic_ai_quality(monkeypatch, tmp_path):
    from types import SimpleNamespace

    client = runtime_ai.client()
    assert runtime_ai.provider_name() == "openai"
    assert client.base_url.host == "api.openai.com"
    meter = Meter(client)
    proxy = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=meter.chat)),
        audio=SimpleNamespace(transcriptions=SimpleNamespace(create=meter.speech)),
    )
    monkeypatch.setattr(runtime_ai, "client", lambda: proxy)
    monkeypatch.setattr(runtime_ai, "speech_client", lambda: proxy)
    results = {
        "model": runtime_ai.model_name(),
        "synthetic_only": True,
        "checks": {},
        "calls": meter.calls,
    }
    report = os.environ.get("AI_QUALITY_REPORT")
    try:
        # Include intentionally wrong mathematics; transcription must not repair it.
        doc = fitz.open()
        page = doc.new_page(width=700, height=400)
        page.insert_text((50, 80), "Student work", fontsize=22)
        page.insert_text((50, 150), "2 + 2 = 5", fontsize=28)
        page.insert_text((50, 210), "3x = 12", fontsize=28)
        page.insert_text((50, 270), "x = 4", fontsize=28)
        image = page.get_pixmap().tobytes("png")
        doc.close()
        asset = {
            "media_asset_id": str(uuid4()),
            "asset_type": "IMAGE",
            "mime_type": "image/png",
            "page_count": 1,
        }
        regions, lines = media.transcribe_image(image, asset)
        raw = " ".join(line["plain_text"] for line in lines)
        compact = raw.replace(" ", "").replace("$", "")
        results["checks"]["wrong_math_preserved"] = "2+2=5" in compact
        results["checks"]["correct_math_preserved"] = "3x=12" in compact and "x=4" in compact
        results["transcription"] = raw
        transcript = media.segment(regions, lines, 1)
        results["checks"]["typed_spatial_evidence"] = (
            len(transcript.regions) >= 3
            and all(step.evidence_ids for step in transcript.steps)
            and all(region.page_number == 1 for region in transcript.regions)
        )

        # Four independent one-step flows; supplied canonical context is synthetic.
        cases = [
            ("error", "From 2x=8, divide both sides by 2 to get x=5.", 0.95, "INCORRECT"),
            (
                "alternate",
                "From 2x=8, subtract x from both sides to get x=8-x. Thus x+x=8 and x=4.",
                0.95,
                "CORRECT",
            ),
            (
                "unsupported",
                "Since 2x=8, x=4 because I guessed it; I have not checked my guess.",
                0.95,
                "UNJUSTIFIED",
            ),
            ("uncertain", "2x=8, maybe x=4 or 9; handwriting is unreadable.", 0.3, "UNCERTAIN"),
        ]
        # Analyse separately: combining unrelated flows could bias critique context.
        for name, plain, confidence, expected in cases:
            eid, sid = str(uuid4()), str(uuid4())
            view = {
                "steps": [
                    {
                        "step_id": sid,
                        "ordinal": 1,
                        "plain_text": plain,
                        "latex_text": plain,
                        "confidence": confidence,
                        "evidence_ids": [eid],
                    }
                ],
                "regions": [{"region_id": eid, "start_ms": 0, "end_ms": 2000}],
            }
            canonical = {
                "problem_statement": "Solve 2x=8 and justify your reasoning.",
                "steps": [
                    {
                        "solution_step_id": str(uuid4()),
                        "text": "Divide both sides by 2 to obtain x=4.",
                    }
                ],
                "dependencies": [],
            }
            assessed = media.analyse(view, canonical)
            results["checks"][name] = (
                len(assessed) == 1
                and assessed[0].correctness == expected
                and assessed[0].step_id == UUID(sid)
                and set(map(str, assessed[0].evidence_ids)) == {eid}
            )
            results.setdefault("assessments", {})[name] = [
                item.model_dump(mode="json") for item in assessed
            ]

        # macOS offline synthesis; paid provider only receives invented audio.
        speech = tmp_path / "synthetic.aiff"
        wav = tmp_path / "synthetic.wav"
        subprocess.run(
            [
                "say",
                "-r",
                "140",
                "-o",
                str(speech),
                "Two plus two equals five. That is what I wrote.",
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-i",
                str(speech),
                "-ac",
                "1",
                "-ar",
                "16000",
                str(wav),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        audio = wav.read_bytes()
        info = media.media_info(audio, "audio/wav")
        assert info["duration_ms"] <= 10000
        timed, spoken = media.transcribe_speech(
            audio,
            {
                "media_asset_id": str(uuid4()),
                "mime_type": "audio/wav",
                "duration_ms": info["duration_ms"],
            },
        )
        results["speech"] = [line["plain_text"] for line in spoken]
        results["checks"]["speech_preserves_error"] = any(
            "five" in line["plain_text"].lower() or "5" in line["plain_text"] for line in spoken
        )
        results["checks"]["exact_bounded_audio_evidence"] = all(
            0 <= r["start_ms"] < r["end_ms"] <= info["duration_ms"] for r in timed
        )

        embedded = meter.embed(
            model="text-embedding-3-small",
            dimensions=1536,
            input=[
                "A tangent is perpendicular to the radius at the point of contact.",
                "Circle diagram with a radius meeting a tangent at a right angle.",
                "Count the arrangements of five distinct books on a shelf.",
                "Solve a linear equation by subtracting and dividing both sides.",
            ],
        )
        vectors = [item.embedding for item in embedded.data]
        scores = [cosine(vectors[0], vector) for vector in vectors[1:]]
        results["embedding_scores"] = scores
        results["checks"]["embedding_dimensions"] = all(len(v) == 1536 for v in vectors)
        results["checks"]["semantic_retrieval"] = scores[0] > max(scores[1:]) + 0.10
        assert all(results["checks"].values()), results["checks"]
    except APIError as exc:
        results["provider_error"] = {
            "type": type(exc).__name__,
            "status": getattr(exc, "status_code", None),
            "code": exc.code,
        }
        raise
    finally:
        results["reserved_cost_ceiling_usd"] = round(meter.reserved, 4)
        if report:
            Path(report).write_text(json.dumps(results, indent=2) + "\n")
        print(json.dumps(results, indent=2))
        client.close()
