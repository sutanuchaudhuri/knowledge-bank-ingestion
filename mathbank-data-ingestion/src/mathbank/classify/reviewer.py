"""
OpenAI reviewer for classified questions.

The reviewer is a second-pass quality check that runs AFTER classify_crawled.py.
It uses GPT-4o (with vision for diagram questions) to verify that:
  1. The primary concept mapping is correct for the problem
  2. The difficulty band is appropriate for the exam level
  3. Images actually show what the classifier described

Outputs one of:
  APPROVED         — mapping is correct, confidence upgraded to 'high'
  CORRECTED        — mapping was wrong; reviewer supplies the right concept_id
  NEEDS_HUMAN_REVIEW — ambiguous or multi-topic; flag for manual inspection

The reviewer is intentionally separate from the classifier so it can be:
  - Run independently on any subset of questions
  - Re-run after taxonomy changes
  - Run with a different model than the classifier
"""
from __future__ import annotations

import base64
import json
import sqlite3
import textwrap
from dataclasses import dataclass, field
from pathlib import Path


# ── Output ────────────────────────────────────────────────────────────────────

@dataclass
class ReviewResult:
    question_id: str
    model: str
    verdict: str              # APPROVED | CORRECTED | NEEDS_HUMAN_REVIEW
    corrected_concept_id: str # non-empty only when verdict=CORRECTED
    confidence: str           # high | medium | low
    review_notes: str
    raw_response: str


# ── Image helpers ─────────────────────────────────────────────────────────────

def _load_image_b64(path: str) -> str | None:
    """Load a local image file as base64 data-URI for GPT-4o vision."""
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return None
    suffix = p.suffix.lower().lstrip(".")
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "gif": "image/gif", "webp": "image/webp"}.get(suffix, "image/png")
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM = textwrap.dedent("""\
You are an expert competition mathematics reviewer.

A previous classifier has already assigned a PRIMARY CONCEPT to this problem.
Your job is to verify whether the assignment is correct by reading the problem
statement and solution carefully — and, when images are provided, examining them.

CRITERIA
1. Is the primary concept accurately describing the main mathematical idea needed?
2. Is the difficulty band reasonable for the exam level?
3. Do any provided images change the classification (e.g. the image reveals it is
   a geometry problem when the text alone suggested combinatorics)?

VERDICT (pick exactly one):
  APPROVED           — the primary concept mapping is correct
  CORRECTED          — the primary concept is wrong; supply the correct concept_id
  NEEDS_HUMAN_REVIEW — ambiguous, multi-topic, or insufficient evidence

When CORRECTED, the corrected_concept_id must be an existing taxonomy ID from
the list supplied, or a proposed new ID following the existing naming convention.

RESPONSE FORMAT (strict JSON, no markdown fences):
{
  "verdict": "APPROVED|CORRECTED|NEEDS_HUMAN_REVIEW",
  "corrected_concept_id": "<existing or new ID, or empty string>",
  "confidence": "high|medium|low",
  "review_notes": "<one to three sentences explaining the decision>"
}
""")


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_messages(
    question_id: str,
    exam_level: str,
    primary_concept_id: str,
    concept_path: str,
    difficulty_band: str,
    problem_text: str,
    solution_text: str,
    image_paths: list[str],
    taxonomy_snippet: str,
) -> list[dict]:
    text_block = (
        f"QUESTION ID: {question_id}\n"
        f"EXAM LEVEL: {exam_level}\n"
        f"CLASSIFIED AS: {primary_concept_id}  ({concept_path})\n"
        f"DIFFICULTY: {difficulty_band}\n\n"
        "## Problem Statement\n"
        f"{problem_text.strip()}\n\n"
        "## Solution (first)\n"
        f"{solution_text.strip()[:1500]}\n\n"
        "## Taxonomy snippet (top-30 relevant entries)\n"
        f"{taxonomy_snippet}\n\n"
        "Review the classification above and return your verdict."
    )

    content: list[dict] = [{"type": "text", "text": text_block}]

    # Attach local images for GPT-4o vision (max 4 to control cost).
    for path in image_paths[:4]:
        b64 = _load_image_b64(path)
        if b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": b64, "detail": "low"},
            })

    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user",   "content": content},
    ]


# ── API call ──────────────────────────────────────────────────────────────────

def _call_openai(messages: list[dict], model: str) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package not installed") from exc
    from mathbank.project_credentials import configure_openai
    api_key = configure_openai()
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=messages,
        temperature=0.1,
        max_tokens=512,
    )
    return resp.choices[0].message.content or "{}"


# ── Taxonomy snippet ──────────────────────────────────────────────────────────

def _taxonomy_snippet(conn: sqlite3.Connection, primary_concept_id: str) -> str:
    """Return the primary concept + its siblings (same domain) as a compact list."""
    domain_row = conn.execute(
        "SELECT domain FROM concepts WHERE canonical_topic_id = ?",
        (primary_concept_id,),
    ).fetchone()
    domain = domain_row[0] if domain_row else ""

    rows = conn.execute(
        "SELECT canonical_topic_id, canonical_path, node_type "
        "FROM concepts WHERE (domain = ? OR canonical_topic_id = ?) "
        "AND canonical_path IS NOT NULL ORDER BY canonical_path LIMIT 30",
        (domain, primary_concept_id),
    ).fetchall()

    return "\n".join(f"  {r[0]} | {r[1]} | {r[2] or '?'}" for r in rows)


# ── Public API ────────────────────────────────────────────────────────────────

def review_question(
    conn: sqlite3.Connection,
    question_id: str,
    exam_level: str,
    primary_concept_id: str,
    difficulty_band: str,
    problem_text: str,
    solution_text: str,
    image_paths: list[str],
) -> ReviewResult:
    """Review one classified question. Always uses gpt-4o for vision support."""
    model = "gpt-4o"

    # Look up the concept canonical path for context.
    path_row = conn.execute(
        "SELECT canonical_path FROM concepts WHERE canonical_topic_id = ?",
        (primary_concept_id,),
    ).fetchone()
    concept_path = path_row[0] if path_row else primary_concept_id

    taxonomy_snippet = _taxonomy_snippet(conn, primary_concept_id)

    messages = _build_messages(
        question_id, exam_level, primary_concept_id, concept_path,
        difficulty_band, problem_text, solution_text,
        image_paths, taxonomy_snippet,
    )

    raw = _call_openai(messages, model)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"verdict": "NEEDS_HUMAN_REVIEW", "review_notes": "Invalid JSON from model"}

    return ReviewResult(
        question_id=question_id,
        model=model,
        verdict=data.get("verdict", "NEEDS_HUMAN_REVIEW"),
        corrected_concept_id=data.get("corrected_concept_id", ""),
        confidence=data.get("confidence", "medium"),
        review_notes=data.get("review_notes", ""),
        raw_response=raw,
    )
