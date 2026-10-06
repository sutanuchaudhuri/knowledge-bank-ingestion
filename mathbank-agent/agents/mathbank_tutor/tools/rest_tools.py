"""Tools that call mathbank-rest (hybrid RAG + corpus queries over Postgres).

Each function is a plain, type-hinted, docstring-documented Python callable —
ADK auto-generates the function-calling schema from this signature, so the
docstring IS the tool description the LLM sees. Keep it accurate.
"""
from __future__ import annotations

import os
from urllib.parse import quote

import httpx

REST_BASE_URL = os.environ.get("MATHBANK_REST_BASE_URL", "http://127.0.0.1:8000")


def _client() -> httpx.Client:
    return httpx.Client(base_url=REST_BASE_URL, timeout=30.0)


def search_problems(
    query: str,
    competition: str = "",
    year_min: int = 0,
    year_max: int = 0,
    recent_first: bool = False,
    limit: int = 10,
) -> dict:
    """Hybrid graph + vector similarity + lexical search over canonical statements.

    Use this for any open-ended question about what problems exist on a topic,
    e.g. "recent questions on combinatorics", "problems about cyclic
    quadrilaterals", "AIME problems on polynomial roots since 2015".
    For textbook geometry topics, enrich the query with related terms (e.g.
    "power of a point secant tangent radical axis") or filter by PRASOLOV_PGV1.

    Args:
        query: The natural-language topic or concept to search for (required).
        competition: Optional exact competition code to filter by, one of
            AMC10, AMC12, AIME, HMMT_FEB, HMMT_NOV, HMMT_INV, SMT, PUMAC,
            CHMMC, CMM, MPG_MAIN, MPG_OLY, PURPLE_MS, PURPLE_HS, ARML,
            ARML_LOCAL, ARML_POWER, or PRASOLOV_PGV1 (Prasolov "Problems in
            Plane Geometry" textbook, chapters 1-30, with step-by-step
            solutions; use it for geometry theory practice such as power of a
            point / radical axis). Leave empty to search all.
        year_min: Optional earliest competition year to include (0 = no limit).
        year_max: Optional latest competition year to include (0 = no limit).
        recent_first: If true, sort matching problems by year descending
            instead of by relevance — use this whenever the user asks for
            "recent"/"latest"/"newest" problems.
        limit: Max number of results (default 10, max 100).

    Returns:
        {"query": str, "results": [{"canonical_code", "statement_text",
        "competition", "year", "paper_code", "rrf_score", "semantic_rank",
        "lexical_rank", "graph_rank", "graph_evidence"}, ...],
        "retrieval": {...}, "warnings": [...]}.
        Disclose warnings; unavailable graph retrieval is not successful graph coverage.
    """
    body: dict = {
        "query": query, "limit": min(limit, 100), "filters": {},
        "retrieval": {"semantic": True, "lexical": True, "graph": True},
    }
    if competition:
        body["filters"]["competition"] = competition
    if year_min:
        body["filters"]["year_min"] = year_min
    if year_max:
        body["filters"]["year_max"] = year_max
    if recent_first:
        body["order_by"] = "year_desc"
    with _client() as client:
        response = client.post("/v1/search/problems", json=body)
        response.raise_for_status()
        return response.json()


def get_problem_by_code(canonical_code: str) -> dict:
    """Fetch full detail for one problem by its canonical code (e.g. 'AIME_2023_I_Q11'),
    including its statement, official answer, tagged concepts/techniques, and
    all known solutions. Use this after search_problems to show a full solution.
    """
    with _client() as client:
        response = client.get(f"/v1/problems/by-code/{canonical_code}")
        if response.status_code == 404:
            return {"error": f"no problem found with canonical_code={canonical_code!r}"}
        response.raise_for_status()
        return response.json()


def get_problem_diagrams(canonical_code: str) -> list[dict]:
    """Get question-specific source diagrams, never whole pages or solution images.

    Call when presenting a retrieved problem, especially if its statement mentions
    a diagram. Paste the returned markdown exactly into the reply. An empty list
    means diagrams are unavailable: disclose this and offer a different problem.
    """
    with _client() as client:
        response = client.get(f"/v1/problems/by-code/{quote(canonical_code, safe='')}/diagrams")
        response.raise_for_status()
        return response.json()


def list_competitions() -> list[dict]:
    """List all competitions/sources tracked in the corpus (AMC, AIME, HMMT, SMT,
    PUMaC, CHMMC, CMM, MPG, ARML, Purple Comet and the PRASOLOV_PGV1 textbook)."""
    with _client() as client:
        response = client.get("/v1/competitions")
        response.raise_for_status()
        return response.json()


def get_corpus_coverage() -> list[dict]:
    """Per-competition ingestion statistics: how many papers/problems are in the
    database and how many have concept/technique tags assigned so far. Use this
    to answer questions like "how much of HMMT do you have" or "is the corpus
    complete".
    """
    with _client() as client:
        response = client.get("/v1/corpus/coverage")
        response.raise_for_status()
        return response.json()


def list_concepts(domain: str = "", limit: int = 50) -> list[dict]:
    """List taxonomy concepts (e.g. 'Vieta's formulas', 'Law of Sines'), optionally
    filtered by a domain substring like 'Algebra' or 'Geometry'.
    """
    with _client() as client:
        params = {"limit": min(limit, 200)}
        if domain:
            params["domain"] = domain
        response = client.get("/v1/concepts", params=params)
        response.raise_for_status()
        return response.json()


def get_problems_for_concept(concept_slug: str, limit: int = 25) -> list[dict]:
    """List problems tagged with a specific concept slug (see list_concepts for slugs)."""
    with _client() as client:
        response = client.get(f"/v1/concepts/{concept_slug}/problems", params={"limit": min(limit, 200)})
        response.raise_for_status()
        return response.json()


def search_concepts(
    query: str,
    node_types: str = "",
    chapter_number: int = 0,
    limit: int = 8,
) -> dict:
    """Concept-level search over the embedded geometry taxonomy (concepts,
    subconcepts, skills and techniques), ranked by vector similarity + lexical
    fusion.

    Use this FIRST whenever the learner names a topic, theorem or method
    ("power of a point", "radical axis", "inversion", "angle chasing") to find
    the canonical taxonomy node, then follow up by slug_kind:
    'concept' -> get_problems_for_concept(slug); 'technique' ->
    get_problems_for_technique(slug); 'skill' -> get_prerequisite_path(slug).
    Prefer example_problem_codes (up to 5) for practice with
    start_step_attempt or get_problem_learning_context. problem_count is the
    number of problems whose published steps exercise the node (0 means no
    practice yet); the slug routes list corpus tags and can be sparser.

    Args:
        query: The topic, theorem or method in natural language (required).
        node_types: Optional comma-separated subset of DOMAIN, CONCEPT,
            SUBCONCEPT, SKILL, TECHNIQUE (e.g. "SUBCONCEPT,TECHNIQUE").
            Leave empty for all.
        chapter_number: Optional textbook chapter filter (0 = any).
        limit: Max nodes to return (default 8, max 50).

    Returns:
        {"query", "results": [{"taxonomy_node_id", "node_type", "name",
        "parent_name", "chapter_number", "section_number", "slug",
        "slug_kind", "problem_count", "example_problem_codes", "rrf_score",
        "semantic_rank", "lexical_rank"}], "retrieval": {...}, "warnings": [...]}.
        Disclose warnings (e.g. lexical-only fallback).
    """
    body: dict = {"query": query, "limit": max(1, min(limit, 50))}
    types = [t.strip().upper() for t in node_types.split(",") if t.strip()]
    if types:
        body["node_types"] = types
    if chapter_number:
        body["chapter_number"] = chapter_number
    with _client() as client:
        response = client.post("/v1/search/concepts", json=body)
        response.raise_for_status()
        return response.json()


def get_problems_for_technique(technique_slug: str, limit: int = 25) -> list[dict]:
    """List problems tagged with a technique, by its slug (e.g. the 'slug' of a
    search_concepts result whose slug_kind is 'technique', such as
    'tech.geo.power_of_a_point')."""
    with _client() as client:
        response = client.get(f"/v1/techniques/{quote(technique_slug, safe='')}/problems",
                              params={"limit": min(limit, 200)})
        response.raise_for_status()
        return response.json()


def decompose_problem(problem_code: str, max_steps: int = 3) -> dict:
    """Break a problem the student is stuck on into small, ordered subproblems
    that build up to the full solution, without revealing the final answer.

    Use this when a student says they're stuck or asks for help step-by-step,
    instead of just giving them the full solution outright. Walk them through
    one subproblem at a time, using check_subproblem_answer to grade each
    response before moving to the next step.

    Args:
        problem_code: The canonical_code of the problem (e.g. 'AIME_1992_Q06').
        max_steps: Max number of subproblems to generate (1-5, default 3).

    Returns:
        {"problem_code", "subproblems": [{"step", "prompt", "targets_skill"}]}
    """
    with _client() as client:
        response = client.post(
            "/v1/tutor/decompose",
            json={"problem_code": problem_code, "max_steps": max_steps},
        )
        if response.status_code == 404:
            return {"error": f"no problem found with canonical_code={problem_code!r}"}
        response.raise_for_status()
        return response.json()


def check_subproblem_answer(subproblem_prompt: str, student_answer: str) -> dict:
    """Grade a student's free-form answer to one subproblem generated by
    decompose_problem. Use the returned feedback to tell the student whether
    they got it right before moving to the next subproblem step.

    Args:
        subproblem_prompt: The exact subproblem prompt text the student was asked.
        student_answer: The student's free-form answer/reasoning.

    Returns:
        {"correct": bool, "feedback": str}
    """
    with _client() as client:
        response = client.post(
            "/v1/tutor/check-subproblem",
            json={"subproblem_prompt": subproblem_prompt, "student_answer": student_answer},
        )
        response.raise_for_status()
        return response.json()


def get_improvement_plan(access_token: str, max_focus_areas: int = 5) -> dict:
    """Fetch the logged-in student's personalized 'what should I improve' plan:
    their weakest concepts/techniques (not yet mastered), each with a few
    recommended practice problems. Use this when a student asks something like
    "what should I work on next" or "what am I weak at".

    Requires the student's own bearer access_token (from a prior login/register
    call) — the agent has no persistent student identity of its own yet, so this
    must be supplied explicitly rather than inferred from the conversation.

    Args:
        access_token: The student's JWT access token.
        max_focus_areas: How many weak concepts/techniques to return (default 5).

    Returns:
        {"student_id", "focus_areas": [{"kind", "slug", "name", "mastery_score",
        "tier", "attempts_count", "recommended_problems"}, ...], "total_struggling_areas"}
        or {"error": "..."} if the token is invalid/expired.
    """
    with _client() as client:
        response = client.get(
            "/v1/learner/mastery/improvement-plan",
            params={"max_focus_areas": max_focus_areas},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code == 401:
            return {"error": "invalid or expired access_token"}
        response.raise_for_status()
        return response.json()


def get_problem_learning_context(problem_code: str) -> dict:
    """Get answer-free statement, reviewed skills/prerequisites and diagnostic choices.

    Call FIRST when a learner is stuck or wants hints. Unenriched means no reviewed
    skill evidence: do not invent it. Never calls full-solution retrieval.
    """
    with _client() as client:
        response = client.get(f"/v1/tutor/learning-context/{quote(problem_code, safe='')}")
        if response.status_code == 404:
            return {"error": f"No problem with code {problem_code!r}"}
        response.raise_for_status()
        return response.json()


def get_prerequisite_path(skill_slug: str, max_depth: int = 4) -> dict:
    """Read reviewed prior skills, bounded to 1-8 levels; not a course or mastery score."""
    with _client() as client:
        response = client.get(
            f"/v1/tutor/prerequisites/{quote(skill_slug, safe='')}",
            params={"max_depth": max_depth},
        )
        if response.status_code == 404:
            return {"error": f"No reviewed skill {skill_slug!r}"}
        response.raise_for_status()
        return response.json()


def get_next_hint(
    problem_code: str, diagnosis: str, student_attempt: str, hint_level: int = 1,
) -> dict:
    """Generate ONE provisional hint after asking for the learner's attempt/diagnosis.

    diagnosis: concept, strategy, execution, calculation, or connection.
    hint_level: 1 directional, 2 conceptual, 3 strategic (never complete solution).
    Only escalate on explicit request after the learner tries the previous hint.
    Generated content is PENDING, not an expert-reviewed hint ladder.
    """
    with _client() as client:
        response = client.post("/v1/tutor/coach", json={
            "problem_code": problem_code, "diagnosis": diagnosis,
            "student_attempt": student_attempt, "hint_level": hint_level,
        }, timeout=60.0)
        response.raise_for_status()
        return response.json()


def find_easier_same_skill_problems(problem_code: str, limit: int = 5) -> dict:
    """Find lower reviewed levels on shared skills, NOT guaranteed easier overall.

    Respect returned evidence and warnings. No results means unavailable, not
    permission to invent analogous problems or infer difficulty from year/contest.
    """
    with _client() as client:
        response = client.get(
            f"/v1/tutor/practice/{quote(problem_code, safe='')}", params={"limit": limit},
        )
        response.raise_for_status()
        return response.json()
