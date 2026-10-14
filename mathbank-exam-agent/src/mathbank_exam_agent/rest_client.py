"""Thin httpx wrapper around mathbank-rest's REST surface — this service's one read/write
path into quiz.*/learner.* data (requirements/64 §3). mathbank-exam-agent never connects
to Postgres/Neo4j directly. Every call here uses the admin-gated /v1/quiz-integration/*
surface (never mathbank-rest's own student-bearer-token endpoints) because this project
resolves student identity itself, via Cognito or an anonymous session, not mathbank-rest's
JWT — see cognito_auth.py / jwt_verify.py.
"""
from __future__ import annotations

import httpx

from mathbank_exam_agent.config import get_settings


class RestError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.status_code, self.code = status_code, code


def _admin_headers() -> dict[str, str]:
    return {"X-Admin-Api-Key": get_settings().admin_api_key}


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    try:
        detail = response.json().get("detail", {})
        code = detail.get("code", "UNKNOWN") if isinstance(detail, dict) else "UNKNOWN"
        message = detail.get("message", str(detail)) if isinstance(detail, dict) else str(detail)
    except Exception:  # noqa: BLE001 -- the upstream body may not be JSON at all
        code, message = "UNKNOWN", response.text[:500]
    raise RestError(response.status_code, code, message)


def _request(method: str, path: str, *, params: dict | None = None, json: dict | None = None,
             timeout: float = 30.0) -> dict | list:
    # mathbank-rest cold-starting (its own Lambda, possibly simultaneously with this
    # one right after a fresh deploy) plus real network latency can exceed 15s —
    # confirmed live: a 15s timeout tripped on the very first post-deploy request.
    # 30s covers that without masking a genuinely hung downstream call.
    base = get_settings().mathbank_rest_base_url.rstrip("/")
    with httpx.Client(timeout=timeout) as client:
        response = client.request(method, f"{base}{path}", params=params, json=json, headers=_admin_headers())
    _raise_for_status(response)
    return response.json()


# --------------------------------------------------------------------------- students / auth

def onboard_student(
    *, cognito_sub: str | None, first_name: str, last_name: str, grade: str | None = None,
    email: str | None = None, phone: str | None = None, is_anonymous: bool = False,
) -> dict:
    return _request("POST", "/v1/quiz-integration/students/onboard", json={
        "cognito_sub": cognito_sub, "first_name": first_name, "last_name": last_name,
        "grade": grade, "email": email, "phone": phone, "is_anonymous": is_anonymous,
    })


def get_student_by_cognito_sub(cognito_sub: str) -> dict | None:
    try:
        return _request("GET", f"/v1/quiz-integration/students/by-cognito-sub/{cognito_sub}")
    except RestError as exc:
        if exc.status_code == 404:
            return None
        raise


def get_student_profile(student_id: str) -> dict:
    return _request("GET", f"/v1/quiz-integration/students/{student_id}")


# --------------------------------------------------------------------------- paper generation / diagnosis

def import_paper(payload: dict) -> dict:
    return _request("POST", "/v1/quiz-integration/papers", json=payload, timeout=30.0)


def start_paper(payload: dict) -> str:
    """Mints a quiz_id immediately, status GENERATING (requirements/64 continued —
    parallel generation + live progress). Returns just the quiz_id string so the caller
    can start posting generation-events and the frontend can start polling them, well
    before any question is drafted."""
    return _request("POST", "/v1/quiz-integration/papers/start", json=payload)["quiz_id"]


def finalize_paper(quiz_id: str, payload: dict) -> dict:
    return _request("POST", f"/v1/quiz-integration/papers/{quiz_id}/finalize", json=payload, timeout=60.0)


def match_pool_questions(
    *, student_id: str, style: str, question_types: list[str], difficulty_band: str | None,
    topic: str | None, concept_slugs: list[str], limit: int = 20,
) -> list[dict]:
    """Cached, critic-approved questions for an almost-identical request, never one this
    student already saw (quiz.question_pool, migration 052)."""
    return _request(
        "POST", "/v1/quiz-integration/question-pool/match",
        json={
            "student_id": student_id, "style": style, "question_types": question_types,
            "difficulty_band": difficulty_band, "topic": topic,
            "concept_slugs": concept_slugs, "limit": limit,
        },
        timeout=15.0,
    )


def post_generation_event(
    quiz_id: str, *, ordinal: int, phase: str, status: str,
    question_ordinal: int | None = None, detail: str = "",
) -> None:
    # Best-effort, never fatal to the actual generation work — a progress-event write
    # failing must not abort an otherwise-successful question draft.
    try:
        _request(
            "POST", f"/v1/quiz-integration/papers/{quiz_id}/generation-events",
            json={
                "ordinal": ordinal, "phase": phase, "status": status,
                "question_ordinal": question_ordinal, "detail": detail,
            },
            timeout=10.0,
        )
    except Exception:  # noqa: BLE001 -- progress visibility is best-effort, not critical-path
        pass


def list_generation_events(quiz_id: str, student_id: str, *, since_ordinal: int = 0) -> list[dict]:
    return _request(
        "GET", f"/v1/quiz-integration/papers/{quiz_id}/generation-events",
        params={"student_id": student_id, "since_ordinal": since_ordinal},
    )


def submit_exam(quiz_id: str, student_id: str) -> dict:
    return _request("POST", f"/v1/quiz-integration/papers/{quiz_id}/submit", params={"student_id": student_id})


def get_diagnosis_input(quiz_id: str, student_id: str) -> dict:
    return _request(
        "GET", f"/v1/quiz-integration/papers/{quiz_id}/diagnosis-input", params={"student_id": student_id},
    )


def write_diagnosis(quiz_id: str, payload: dict) -> dict:
    return _request("POST", f"/v1/quiz-integration/papers/{quiz_id}/diagnosis", json=payload, timeout=30.0)


def get_diagnosis(quiz_id: str, student_id: str) -> dict:
    return _request("GET", f"/v1/quiz-integration/papers/{quiz_id}/diagnosis", params={"student_id": student_id})


# --------------------------------------------------------------------------- exam-taking flow
# (requirements/64, continued — proxied through this service rather than letting
# mathbank-exam-web call mathbank-rest's own /v1/quiz/* student endpoints directly,
# since those are gated by mathbank-rest's own JWT, not the Cognito/anonymous identity
# this service resolves).

def list_my_papers(student_id: str, *, limit: int = 20) -> list[dict]:
    return _request("GET", "/v1/quiz-integration/papers/mine", params={"student_id": student_id, "limit": limit})


def get_paper(quiz_id: str, student_id: str) -> dict:
    return _request("GET", f"/v1/quiz-integration/papers/{quiz_id}", params={"student_id": student_id})


def save_exam_progress(
    quiz_id: str, student_id: str, *, current_question_ordinal: int,
    question_id: str | None = None, selected_key: str | None = None,
    response_text: str | None = None,
) -> dict:
    return _request(
        "PUT", f"/v1/quiz-integration/papers/{quiz_id}/progress",
        json={
            "student_id": student_id,
            "current_question_ordinal": current_question_ordinal,
            "question_id": question_id,
            "selected_key": selected_key,
            "response_text": response_text,
        },
    )


def fail_paper(quiz_id: str, student_id: str, error_message: str) -> dict:
    return _request(
        "POST", f"/v1/quiz-integration/papers/{quiz_id}/fail",
        json={"student_id": student_id, "error_message": error_message},
    )


def respond(
    quiz_id: str, question_id: str, student_id: str, *, selected_key: str | None = None,
    response_text: str | None = None, time_spent_seconds: int | None = None,
) -> dict:
    return _request(
        "POST", f"/v1/quiz-integration/papers/{quiz_id}/questions/{question_id}/respond",
        json={
            "student_id": student_id, "selected_key": selected_key, "response_text": response_text,
            "time_spent_seconds": time_spent_seconds,
        },
        timeout=30.0,
    )


def review(quiz_id: str, student_id: str) -> dict:
    return _request("GET", f"/v1/quiz-integration/papers/{quiz_id}/review", params={"student_id": student_id})


def log_event(
    quiz_id: str, question_id: str, student_id: str, *, event_type: str,
    option_key: str | None = None, client_timestamp_ms: int | None = None,
) -> dict:
    return _request(
        "POST", f"/v1/quiz-integration/papers/{quiz_id}/questions/{question_id}/events",
        json={
            "student_id": student_id, "event_type": event_type, "option_key": option_key,
            "client_timestamp_ms": client_timestamp_ms,
        },
    )


def get_events(quiz_id: str, student_id: str) -> list[dict]:
    return _request("GET", f"/v1/quiz-integration/papers/{quiz_id}/events", params={"student_id": student_id})


# --------------------------------------------------------------------------- difficulty/mastery signals

def get_prerequisite_depth(skill_slug: str, *, max_depth: int = 4) -> dict:
    """Neo4j-graph-backed structural difficulty signal (requirements/64 §5 point 3) —
    reuses mathbank-rest's own existing endpoint, never a direct Neo4j connection from
    this project (its only database boundary is mathbank-rest's REST surface)."""
    base = get_settings().mathbank_rest_base_url.rstrip("/")
    with httpx.Client(timeout=15.0) as client:
        response = client.get(f"{base}/v1/pedagogy/prerequisites/{skill_slug}", params={"max_depth": max_depth})
    if response.status_code == 404:
        return {"depth": None}
    _raise_for_status(response)
    return response.json()


def get_concept_mastery(student_id: str, concept_slug: str) -> float | None:
    """Student-specific personalization signal (requirements/64 §5 point 2) — best
    effort: returns None (not an error) if the student has no recorded mastery for this
    concept yet, which is the normal, expected state for a brand-new topic."""
    data = _request("GET", f"/v1/quiz-integration/students/{student_id}/mastery-summary")
    match = next((c for c in data.get("concepts", []) if c["slug"] == concept_slug), None)
    return float(match["mastery_score"]) if match else None


def get_difficulty_distribution(*, concept_slug: str | None = None, technique_slug: str | None = None) -> dict:
    """Postgres-backed corpus-difficulty signal (requirements/64 §5 point 1) — real
    `core.problem.difficulty_band` counts for a resolved concept/technique, confirmed
    live to carry this project's own real competition-tier labels (e.g. "AIME D3 /
    Entry (Q1-5)"), not a simple easy/medium/hard enum."""
    params = {k: v for k, v in (("concept_slug", concept_slug), ("technique_slug", technique_slug)) if v}
    return _request("GET", "/v1/quiz-integration/difficulty-distribution", params=params)["distribution"]
