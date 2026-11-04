"""Shared fixtures for the WP6 papers tests: a learner, a content read model (catalogues + two problems), an LLM stub and a
PostgreSQL guard. Everything runs on moto; nothing touches PostgreSQL or AWS."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from types import SimpleNamespace
from typing import Any

from mathbank_rest.models.ddb.content import ContentCatalogptr, ContentProblem, ContentPtag
from mathbank_rest.models.ddb.learner import LearnerProfile
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import typed

NOW = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
SHA = "c" * 64


def uid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"wp6:{name}"))


CONCEPTS = {"counting": "Counting", "parity": "Parity"}
TECHNIQUES = {"pigeonhole": "Pigeonhole principle"}
SKILLS = {"case-analysis": "Case analysis"}
CODES = {"AMC10_2005B_Q18": ("AMC 10", 2005, "hard"), "AIME_2010I_Q3": ("AIME", 2010, "very_hard")}


class NoPostgres:
    def __getattr__(self, name):
        raise AssertionError(f"the DynamoDB exam path must not touch PostgreSQL (engine.{name})")


def profile(sid: str, **over: Any) -> LearnerProfile:
    base = {
        "PK": toolkit.student_pk(sid), "SK": "PROFILE", "student_id": sid, "email": f"{sid[:8]}@x.org", "email_lc": f"{sid[:8]}@x.org",
        "first_name": "A", "last_name": "B", "display_name": "A B", "password_hash": "h", "search_blob": "a b", "status": "ACTIVE",
        "is_anonymous": False, "token_version": 1, "version": 1, "created_at": NOW, "updated_at": NOW,
    }
    return LearnerProfile(**{**base, **over})


def _snapshot(kind: str, items: list[dict]) -> None:
    body = json.dumps({"schema": f"catalog/{kind}/v1", "kind": kind, "items": items}, sort_keys=True, separators=(",", ":")).encode()
    sha = hashlib.sha256(body).hexdigest()
    key = f"catalog/{kind}/{sha}.json"
    toolkit.client("s3").put_object(Bucket=toolkit.content_bucket(), Key=key, Body=body)
    typed.put(ContentCatalogptr.model_validate({
        "PK": f"CATALOG#{kind.upper()}", "SK": "SNAPSHOT", "type": "CATALOGPTR", "content_sha256": SHA, "count": len(items), "kind": kind,
        "s3_key": key, "sha256": sha, "src_rev": 1}))


def seed_content() -> None:
    """Concept / technique / skill catalogue snapshots, two problems and the PTAG partitions the difficulty signal reads."""
    _snapshot("concept", [{"aliases": [], "concept_id": uid(f"concept:{s}"), "description": f"about {s}", "name": n,
                           "relations_out": [], "slug": s} for s, n in CONCEPTS.items()])
    _snapshot("technique", [{"aliases": [], "description": f"about {s}", "name": n, "slug": s, "technique_id": uid(f"technique:{s}")}
                            for s, n in TECHNIQUES.items()])
    _snapshot("skill", [{"aliases": [], "name": n, "skill_id": uid(f"skill:{s}"), "slug": s} for s, n in SKILLS.items()])
    for code, (comp, year, band) in CODES.items():
        typed.put(ContentProblem.model_validate({
            "PK": f"PROBLEM#{code}", "SK": "META", "type": "PROBLEM", "GSI1PK": f"PID#{uid(code)}", "GSI1SK": "META",
            "canonical_code": code, "problem_id": uid(code), "problem_number": 1, "year": year, "paper_code": "P", "paper_id": uid("paper"),
            "statement_text": f"Statement of {code}.", "source_url": f"https://example.org/{code}", "difficulty_band": band,
            "competition": {"competition_id": uid(comp), "external_code": comp, "level": "X", "name": comp}, "images": [],
            "content_sha256": SHA, "src_rev": 1, "created_at": NOW, "updated_at": NOW, "visibility": "ACTIVE"}))
        typed.put(ContentPtag.model_validate({
            "PK": f"PROBLEM#{code}", "SK": f"TAG#CONCEPT#{uid('concept:counting')}", "type": "PTAG",
            "GSI1PK": f"CONCEPT#{uid('concept:counting')}", "GSI1SK": f"{year:04d}#000001#{code}", "competition_name": comp,
            "confidence": 0.9, "content_sha256": SHA, "problem_code": code, "problem_id": uid(code), "problem_number": 1,
            "review_status": "REVIEWED", "role": "PRIMARY", "slug": "counting", "source_roles": ["PRIMARY"], "src_rev": 1,
            "tag_kind": "CONCEPT", "year": year, "concept_id": uid("concept:counting")}))


def mcq(n: int = 1, *, concepts: tuple[str, ...] = (), techniques: tuple[str, ...] = (), band: str | None = "easy",
        sources: tuple[str, ...] = (), **over: Any) -> dict:
    """One finalize question as the exam agent sends it (``ImportQuestion.model_dump()``)."""
    return {
        "question_type": "MCQ", "prompt_text": f"What is {n}+{n}?", "prompt_latex": None,
        "options": [{"key": "A", "text": str(2 * n - 1)}, {"key": "B", "text": str(2 * n)}, {"key": "C", "text": str(2 * n + 1)}],
        "correct_answer": {"correct_key": "B"}, "option_explanations": {"A": "no", "B": "yes", "C": "no"},
        "solution_text": f"{n}+{n}={2 * n}", "solution_steps": ["add"], "key_insight": "addition", "difficulty_band": band,
        "revision_log": [{"round": 1, "verdict": "APPROVE", "feedback": "fine"}], "concept_slugs": list(concepts),
        "technique_slugs": list(techniques), "skill_slugs": [], "diagram": None, "pool_question_id": None, "add_to_pool": False,
        "inspiration_sources": [{"canonical_code": c, "note": f"borrowed from {c}"} for c in sources], **over}


def free_text(n: int = 1, **over: Any) -> dict:
    return {**mcq(n), "question_type": "FREE_TEXT", "options": None,
            "correct_answer": {"expected_answer": str(2 * n), "grading_rubric": None}, "option_explanations": {}, **over}


class FakeLLM:
    """Deterministic stand-in for every ``chat.completions.create`` of the quiz logic; counts the calls per schema."""

    def __init__(self, *, fail_on: str | None = None):
        self.calls: list[str] = []
        self.fail_on = fail_on
        self.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=self._create)),
                                      with_options=lambda **_k: self.client)

    def _create(self, *, response_format, messages, **_k):
        name = response_format["json_schema"]["name"]
        self.calls.append(name)
        if name == self.fail_on:
            raise RuntimeError("llm down")
        if name == "quiz_question":
            mcq_q = "MCQ" in messages[0]["content"]
            content = ({"prompt_text": "What is 2+2?", "prompt_latex": None,
                        "options": [{"key": "A", "text": "3"}, {"key": "B", "text": "4"}, {"key": "C", "text": "5"}, {"key": "D", "text": "6"}],
                        "correct_answer_key": "B", "expected_answer": None, "grading_rubric": None,
                        "solution_text": "2+2=4", "key_insight": "arithmetic"} if mcq_q else
                       {"prompt_text": "Prove the sum of two evens is even.", "prompt_latex": None, "options": None,
                        "correct_answer_key": None, "expected_answer": None, "grading_rubric": "write 2a+2b",
                        "solution_text": "2a+2b=2(a+b)", "key_insight": "evens are 2k"})
        elif name == "diagram_plan":
            content = {"needs_diagram": False, "title": "", "elements": []}
        elif name == "grading_result":
            content = {"is_correct": True, "confidence": 0.9, "feedback": "Well reasoned."}
        else:
            raise AssertionError(name)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(content)))])
