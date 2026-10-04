"""
OpenAI-powered concept classifier for competition math questions.

Maps a parsed problem+solution to existing taxonomy concepts.
If no good match exists, proposes a new concept to insert into the DB.

Prompt design:
  - System: role + full taxonomy in compact table form + output schema
  - User: problem statement + solution(s) + image references

Model selection:
  AMC10 / AMC12  → gpt-4o-mini  (cheaper, sufficient for standard competition math)
  AIME / HMMT    → gpt-4o        (harder problems need stronger reasoning)
"""
from __future__ import annotations

import json
import os
import random
import sqlite3
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── Output types ─────────────────────────────────────────────────────────────

@dataclass
class ConceptMapping:
    canonical_topic_id: str        # existing ID or proposed new ID
    is_new: bool                   # True → needs to be inserted into concepts table
    association_type: str          # "Primary Concept" | "Additional Concept"
    confidence: str                # high | medium | low
    evidence: str                  # one-sentence justification
    new_concept_data: dict | None = None  # filled only when is_new=True


@dataclass
class ClassificationResult:
    question_id: str
    model: str
    primary_mapping: ConceptMapping
    additional_mappings: list[ConceptMapping] = field(default_factory=list)
    suggested_difficulty: str = ""
    suggested_primary_topic: str = ""
    classifier_notes: str = ""
    raw_response: str = ""

    @property
    def all_mappings(self) -> list[ConceptMapping]:
        return [self.primary_mapping] + self.additional_mappings


# ── Taxonomy loader ───────────────────────────────────────────────────────────

def load_taxonomy_prompt_block(conn: sqlite3.Connection) -> str:
    """
    Build a compact taxonomy reference block for the prompt.
    Only includes rows with a canonical_path (from canonical_topic_hierarchy).
    """
    rows = conn.execute(
        """SELECT canonical_topic_id, canonical_path, node_type, definition
           FROM concepts
           WHERE canonical_path IS NOT NULL AND canonical_path != ''
           ORDER BY canonical_path"""
    ).fetchall()

    lines = ["TAXONOMY (ID | path | type | definition-excerpt)"]
    for cid, path, ntype, defn in rows:
        defn_short = (defn or "")[:80].replace("\n", " ")
        lines.append(f"  {cid} | {path} | {ntype or '?'} | {defn_short}")
    return "\n".join(lines)


def _model_for_level(exam_level: str) -> str:
    level = (exam_level or "").upper().replace(" ", "")
    if any(k in level for k in ("AIME", "HMMT", "PUMAC", "SMT", "CMM", "CHMMC")):
        return "gpt-4o"
    return "gpt-4o-mini"


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_TEMPLATE = textwrap.dedent("""\
You are an expert competition mathematics classifier.
Your task: read a competition problem and its solution(s), then map the question \
to the mathematical concept taxonomy provided below.

RULES
1. Identify the PRIMARY concept — the main mathematical idea required to solve the problem.
2. Identify up to 4 ADDITIONAL concepts that appear in the problem or solution.
3. For each concept, find the BEST MATCH from the taxonomy list using the ID column.
4. If no existing concept matches within 1 level of specificity, propose a NEW concept.
5. New concept IDs must follow the existing naming convention (e.g. PROB_COND_BAYES).
6. Assign confidence:
     high   → the solution text explicitly demonstrates the concept
     medium → the problem structure strongly implies the concept
     low    → uncertain, inferred from keywords only
7. Any image reference ([IMG:...] in the problem text) means the question uses a \
geometric figure or diagram — note this in classifier_notes.
8. The difficulty suggestion must match the exam level:
     AMC10/AMC12  → easy | medium | hard
     AIME         → entry | core | advanced | elite
     Others       → easy | medium | hard | very_hard

TAXONOMY
{taxonomy_block}

RESPONSE FORMAT (strict JSON, no markdown fences):
{{
  "primary_mapping": {{
    "canonical_topic_id": "<existing ID or null>",
    "is_new": false,
    "confidence": "high|medium|low",
    "evidence": "<one sentence>",
    "new_concept": null
  }},
  "additional_mappings": [
    {{
      "canonical_topic_id": "<existing ID or null>",
      "is_new": false,
      "confidence": "high|medium|low",
      "evidence": "<one sentence>",
      "new_concept": null
    }}
  ],
  "suggested_difficulty": "easy|medium|hard|very_hard|entry|core|advanced|elite",
  "suggested_primary_topic": "<domain-level label e.g. Algebra>",
  "classifier_notes": "<any remarks about visuals, ambiguity, edge cases>"
}}

When is_new is true, replace the "new_concept" field with:
{{
  "canonical_topic_id": "<proposed ID following naming convention>",
  "domain": "<Domain>",
  "topic": "<Topic>",
  "subtopic": "<Subtopic or empty>",
  "concept_or_technique": "<leaf name>",
  "node_type": "Concept|Subtopic|Technique",
  "canonical_path": "<Domain > Topic > Subtopic > Leaf>",
  "definition": "<one sentence definition>"
}}
""")


# ── User prompt ───────────────────────────────────────────────────────────────

def _build_user_prompt(
    question_id: str,
    exam_level: str,
    problem_text: str,
    solution_texts: list[str],
    image_paths: list[str],
    answer_value: str,
) -> str:
    parts = [
        f"QUESTION ID: {question_id}",
        f"EXAM LEVEL: {exam_level}",
        "",
        "## Problem Statement",
        problem_text.strip(),
    ]

    if image_paths:
        parts += ["", "## Visual References"]
        for ip in image_paths:
            parts.append(f"  [IMG:{ip}]")

    for i, sol in enumerate(solution_texts[:3], 1):  # cap at 3 solutions
        label = "Solution" if len(solution_texts) == 1 else f"Solution {i}"
        parts += ["", f"## {label}", sol.strip()]

    if answer_value:
        parts += ["", f"**Official Answer:** {answer_value}"]

    parts += ["", "Classify this question against the taxonomy."]
    return "\n".join(parts)


# ── API call ──────────────────────────────────────────────────────────────────

_MAX_RATE_LIMIT_RETRIES = 6
_BASE_BACKOFF_SECONDS = 5.0


def _call_openai(system: str, user: str, model: str) -> str:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    # Import lazily to avoid hard dependency if openai is not installed.
    try:
        from openai import OpenAI, RateLimitError  # type: ignore
    except ImportError as exc:
        raise RuntimeError("openai package not installed — run: pip install openai>=1.30") from exc

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set in the shell or ingestion .env; run make sync-openai-key"
        )

    client = OpenAI(api_key=api_key)
    # TPM (tokens-per-minute) is an org-wide limit shared across every concurrent
    # classify_crawled.py/classify_pdf_corpus.py process — running more parallel
    # batches than the account's TPM allows doesn't raise total throughput, it
    # just produces more 429s. Retry with exponential backoff + jitter so a
    # transient rate-limit window turns into a short wait instead of a permanent
    # PARTIAL/failed classification (see GOTCHAS.md for the incident this fixed).
    last_exc: Exception | None = None
    for attempt in range(_MAX_RATE_LIMIT_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.1,  # near-deterministic for classification
                max_tokens=1024,
            )
            return resp.choices[0].message.content or "{}"
        except RateLimitError as exc:
            last_exc = exc
            if attempt == _MAX_RATE_LIMIT_RETRIES - 1:
                break
            delay = _BASE_BACKOFF_SECONDS * (2**attempt) + random.uniform(0, 2.0)
            time.sleep(delay)
    raise last_exc  # type: ignore[misc] - loop always sets last_exc before falling through


# ── Response parser ───────────────────────────────────────────────────────────

def _parse_mapping(raw: dict, association_type: str) -> ConceptMapping:
    new_data = raw.get("new_concept") if raw.get("is_new") else None
    cid = (
        new_data.get("canonical_topic_id", "NEW_UNKNOWN")
        if new_data
        else (raw.get("canonical_topic_id") or "UNKNOWN")
    )
    return ConceptMapping(
        canonical_topic_id=cid,
        is_new=bool(raw.get("is_new", False)),
        association_type=association_type,
        confidence=raw.get("confidence", "low"),
        evidence=raw.get("evidence", ""),
        new_concept_data=new_data,
    )


def _parse_response(raw_json: str, question_id: str, model: str) -> ClassificationResult:
    try:
        data: dict[str, Any] = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"OpenAI returned invalid JSON for {question_id}: {exc}") from exc

    primary_raw = data.get("primary_mapping") or {}
    primary = _parse_mapping(primary_raw, "Primary Concept")

    additional: list[ConceptMapping] = []
    for m in (data.get("additional_mappings") or []):
        additional.append(_parse_mapping(m, "Additional Concept"))

    return ClassificationResult(
        question_id=question_id,
        model=model,
        primary_mapping=primary,
        additional_mappings=additional,
        suggested_difficulty=data.get("suggested_difficulty", ""),
        suggested_primary_topic=data.get("suggested_primary_topic", ""),
        classifier_notes=data.get("classifier_notes", ""),
        raw_response=raw_json,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def classify_question(
    conn: sqlite3.Connection,
    question_id: str,
    exam_level: str,
    problem_text: str,
    solution_texts: list[str],
    image_paths: list[str],
    answer_value: str,
    taxonomy_block: str,
) -> ClassificationResult:
    model = _model_for_level(exam_level)
    system = _SYSTEM_TEMPLATE.format(taxonomy_block=taxonomy_block)
    user = _build_user_prompt(
        question_id, exam_level, problem_text, solution_texts, image_paths, answer_value
    )
    raw = _call_openai(system, user, model)
    return _parse_response(raw, question_id, model)
