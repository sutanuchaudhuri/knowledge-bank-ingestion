"""Exact taxonomy grounding and learner reports; no models or automatic approval."""

from __future__ import annotations

import json
import re
from uuid import UUID

from sqlalchemy import text

from mathbank_rest.db.postgres import engine
from mathbank_rest.db.retrieval_audit import AUDIT_VERSION, POWER, audit_problem, power_structure
from mathbank_rest.practice_selection import load_profile, rank_candidates


def topic_key(value: str) -> str:
    return " ".join(
        word
        for word in re.findall(r"[a-z0-9]+", value.lower())
        if word not in {"a", "an", "the", "of"}
    )


def _content():
    from mathbank_rest import stores

    return stores.get_store("content")


def _learner():
    from mathbank_rest import stores

    return stores.get_store("learner")


def _pg_nodes(conn, node_types: tuple[str, ...]) -> list[dict]:
    rows = conn.execute(
        text(
            "SELECT taxonomy_node_id,name,node_type FROM pedagogy.taxonomy_node "
            "WHERE node_type = ANY(:types) ORDER BY taxonomy_node_id"
        ),
        {"types": list(node_types)},
    ).mappings()
    return [dict(row) for row in rows]


def topic_plan(query: str) -> dict:
    key = topic_key(query)
    store = _content()
    nodes = store.list_taxonomy_nodes(("CONCEPT", "SUBCONCEPT", "SKILL", "TECHNIQUE"))
    exact = [node for node in nodes if key and topic_key(node["name"]) == key]
    if len(exact) != 1:
        return {
            "matched": False,
            "query": query,
            "reason": "No unique exact taxonomy match. Clarify the topic; similarity alone is not applicability.",
            "candidates": [
                {"taxonomy_node_id": n["taxonomy_node_id"], "name": n["name"]}
                for n in nodes
                if key and key in topic_key(n["name"])
            ][:8],
        }
    node = store.get_taxonomy_nodes([exact[0]["taxonomy_node_id"]])[exact[0]["taxonomy_node_id"]]
    steps = [
        "Identify the objects and hypotheses of the named concept.",
        "Choose a problem whose published steps support that concept, then verify its statement and diagram.",
        "Ask for the learner's attempt; give one checkpoint before advancing.",
    ]
    if node["taxonomy_node_id"] == "TECH.GEO.POWER_OF_A_POINT":
        steps[0] = (
            "Identify a circle and a point; distinguish intersecting chords, two secants, or tangent–secant configurations."
        )
        checkpoint = "Which circle and point are involved, and which collinear segment products can you compare?"
    else:
        checkpoint = "Which givens match this concept's hypotheses, and what have you tried?"
    return {
        "matched": True,
        "query": query,
        "node": node,
        "plan_steps": steps,
        "first_checkpoint": checkpoint,
        "provenance": "Published step annotations, not a mathematical correctness certificate.",
        "warnings": [
            "Published/approved annotations may be machine-generated; applicability still needs checking."
        ],
    }


def _pg_candidates(conn, node_id: str, limit: int) -> list[dict]:
    rows = conn.execute(text("""
            SELECT p.canonical_code,n.node_type,
                   CASE WHEN n.node_type='TECHNIQUE' THEN max(st.confidence)
                        ELSE max(pe.taxonomy_confidence) END AS confidence,
                   pe.difficulty_band_source_order AS difficulty,
                   array_remove(array_agg(DISTINCT s.skill_node_id),NULL) AS skill_ids,
                   concat_ws('|',pe.subconcept_node_id,pe.problem_form,
                       array_to_string(array_agg(DISTINCT s.skill_node_id ORDER BY s.skill_node_id),',')) AS structure_key
            FROM pedagogy.taxonomy_node n
            JOIN pedagogy.solution_step s ON s.publication_status='PUBLISHED'
            JOIN core.problem p ON p.problem_id=s.problem_id
            LEFT JOIN pedagogy.problem_enrichment pe ON pe.problem_id=p.problem_id
            LEFT JOIN pedagogy.solution_step_technique st ON st.solution_step_id=s.solution_step_id
                AND st.technique_node_id=n.taxonomy_node_id AND st.review_status='APPROVED'
            WHERE n.taxonomy_node_id=:node AND (
                (n.node_type='SKILL' AND s.skill_node_id=n.taxonomy_node_id)
                OR (n.node_type='SUBCONCEPT' AND s.subconcept_node_id=n.taxonomy_node_id)
                OR (n.node_type='CONCEPT' AND s.concept_node_id=n.taxonomy_node_id)
                OR (n.node_type='TECHNIQUE' AND st.solution_step_id IS NOT NULL))
              AND NOT EXISTS (SELECT 1 FROM knowledge.problem_technique pt
                  WHERE pt.problem_id=p.problem_id AND pt.technique_id=n.technique_id
                    AND pt.review_status IN ('PENDING','REJECTED'))
              AND NOT EXISTS (SELECT 1 FROM knowledge.problem_concept pc
                  WHERE pc.problem_id=p.problem_id AND pc.concept_id=n.concept_id
                    AND pc.review_status IN ('PENDING','REJECTED'))
              AND NOT EXISTS (SELECT 1 FROM learner.pedagogy_feedback negative
                  WHERE negative.problem_id=p.problem_id AND negative.status='RESOLVED'
                    AND negative.retrieval_verdict='IRRELEVANT'
                    AND negative.audit_snapshot->>'requested_node_id'=n.taxonomy_node_id)
            GROUP BY p.canonical_code,n.node_type,pe.difficulty_band_source_order,
                     pe.subconcept_node_id,pe.problem_form
            ORDER BY p.canonical_code LIMIT :limit
        """), {"node": node_id, "limit": limit}).mappings()
    return [dict(row) for row in rows]


def _pg_learner_state(student_id: UUID) -> dict:
    with engine.connect() as conn:
        exposed = list(conn.execute(text("""
            SELECT p.canonical_code FROM learner.solve_attempt a
            JOIN core.problem p USING(problem_id) WHERE a.student_id=:student
            UNION SELECT p.canonical_code FROM learner.attempt a
            JOIN core.problem p USING(problem_id) WHERE a.student_id=:student
        """), {"student": student_id}).scalars())
        gap_skills = list(conn.execute(text("""
            SELECT DISTINCT target_skill_id FROM pedagogy.knowledge_gap
            WHERE student_id=:student AND status IN ('UNRESOLVED','CONFIRMED')
              AND target_skill_id IS NOT NULL
        """), {"student": student_id}).scalars())
    return {"exposed_codes": exposed, "gap_skill_ids": gap_skills}


def topic_candidates(topic: str, *, profile_version: str = "topic-fit-v1", limit: int = 10,
                     target_difficulty: int | None = None, known_skills: list[str] | None = None,
                     exposed_codes: list[str] | None = None, exclude_codes: list[str] | None = None,
                     student_id: UUID | None = None) -> dict:
    profile = load_profile(profile_version)
    plan = topic_plan(topic)
    if not plan["matched"]:
        return plan
    node = plan["node"]
    candidates = _content().list_topic_candidates(node["taxonomy_node_id"], limit=100)
    learner = _learner()
    if getattr(learner, "backend", "postgres") == "dynamodb":
        # the PostgreSQL candidate query excludes reviewed-irrelevant problems in SQL; mb-learner holds them as RETRIEVAL_EXCLUSION
        excluded = set(learner.list_excluded_problem_codes(node["taxonomy_node_id"]))
        candidates = [c for c in candidates if c["canonical_code"] not in excluded]
    exposure = set(exposed_codes or [])
    gap_skills = None
    if student_id:
        state = learner.get_topic_learner_state(student_id)
        exposure.update(state["exposed_codes"])
        gap_skills = list(state["gap_skill_ids"])
    for candidate in candidates:
        candidate["confidence"] = float(candidate["confidence"] or 0)
        candidate["exposure_known"] = student_id is not None
        candidate["gap_skill_ids"] = gap_skills
        skills = candidate["skill_ids"]
        candidate["prerequisite_ids"] = _content().list_taxonomy_prerequisite_ids(skills) if skills else []
    result = rank_candidates(
        candidates, profile=profile, limit=limit, target_difficulty=target_difficulty,
        known_skills=known_skills, exposed_codes=list(exposure) if student_id or exposed_codes is not None else None,
        exclude_codes=exclude_codes,
    )
    return {"matched": True, "node": node, "profile_version": profile_version,
            "minimum_confidence": profile["minimum_confidence"], "candidates": result,
            "candidate_limit": 100, "bounded": True,
            "warnings": ["Structural diversity uses taxonomy/skill signatures, not verified geometric equivalence.",
                         "Unknown fit signals are not estimated. Source completeness is checked before display."]}


def audit_problem_content(store, code: str, topic: str, node: dict | None) -> dict:
    """``retrieval_audit.audit_problem`` over the content store (DynamoDB mode: no SQL). The PENDING/REJECTED tag rows that the
    SQL lists as ``challenged_assertions`` are not in mb-content (the publisher withholds those problems), so that list is empty."""
    problem = store.get_problem_by_code(code)
    if problem is None:
        return {"error": "UNKNOWN_PROBLEM"}
    dag = store.get_solution_dag(code)
    steps = list(dag["steps"])
    support: list[str] = []
    if node:
        node_id, kind = node["taxonomy_node_id"], node.get("node_type")
        technique_steps = {t["solution_step_id"] for t in dag["step_techniques"] if t["technique_node_id"] == node_id}
        by_kind = {"SKILL": "skill_node_id", "CONCEPT": "concept_node_id", "SUBCONCEPT": "subconcept_node_id"}
        support = [s["solution_step_id"] for s in steps
                   if (kind in by_kind and s.get(by_kind[kind]) == node_id)
                   or (kind == "TECHNIQUE" and s["solution_step_id"] in technique_steps)]
    structural = power_structure(problem["statement_text"] or "", steps) if node and node["taxonomy_node_id"] == POWER else None
    return {"version": AUDIT_VERSION, "problem_code": code, "requested_topic": topic,
            "requested_node_id": node["taxonomy_node_id"] if node else None,
            "published_step_count": len(steps), "supporting_step_ids": support[:50],
            "challenged_assertions": [], "structural_validation": structural,
            "suggested_error_kind": "INSUFFICIENT_EVIDENCE" if not support else "RETRIEVAL",
            "review_status": "PENDING", "retrieval_score": None,
            "message": "Correction candidate only. Inspect source evidence before any canonical change."}


def submit_feedback(student_id: UUID, problem_code: str, topic: str, reason: str, *,
                    idempotency_key: str | None = None) -> dict | None:
    node = topic_plan(topic).get("node")
    return _learner().submit_feedback(student_id, problem_code, topic, reason, node=node, idempotency_key=idempotency_key)


def _pg_submit_feedback(student_id: UUID, problem_code: str, topic: str, reason: str, node: dict | None) -> dict | None:
    with engine.begin() as conn:
        audit = audit_problem(conn, problem_code, topic, node)
        if audit.get("error"):
            return None
        row = (
            conn.execute(
                text("""
            INSERT INTO learner.pedagogy_feedback(student_id,problem_id,topic,reason,audit_snapshot)
            SELECT :student_id,problem_id,:topic,:reason,CAST(:audit AS jsonb) FROM core.problem WHERE canonical_code=:code
            ON CONFLICT (student_id,problem_id,topic,reason) DO UPDATE SET topic=EXCLUDED.topic
            RETURNING feedback_id,status,created_at,audit_snapshot AS audit
        """),
                {
                    "student_id": student_id,
                    "code": problem_code,
                    "topic": topic.strip(),
                    "reason": reason.strip(),
                    "audit": json.dumps(audit),
                },
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None


def feedback_queue(limit: int, offset: int, *, status: str | None = None, student_id: UUID | None = None,
                   q: str | None = None) -> dict:
    return _learner().list_feedback_queue(limit, offset, status=status, student_id=student_id, q=q)


def _pg_feedback_queue(limit: int, offset: int, *, status: str | None = None, student_id: UUID | None = None,
                       q: str | None = None) -> dict:
    where, params = [], {"limit": limit, "offset": offset}
    if status:
        where.append("f.status=:status")
        params["status"] = status
    if student_id is not None:
        where.append("f.student_id=:student")
        params["student"] = student_id
    if q:
        where.append("(f.topic ILIKE :q OR f.reason ILIKE :q)")
        params["q"] = f"%{q}%"
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"""
            SELECT f.feedback_id,p.canonical_code,f.topic,f.reason,f.status,f.created_at,
                   f.review_note,f.reviewed_at,f.audit_snapshot AS audit,
                   f.retrieval_verdict,f.error_kind,
                   count(*) OVER (PARTITION BY f.problem_id,f.topic) AS related_report_count
            FROM learner.pedagogy_feedback f JOIN core.problem p USING(problem_id) {clause}
            ORDER BY (f.status='PENDING') DESC,f.created_at DESC LIMIT :limit OFFSET :offset
        """),
            params,
        ).mappings()
        total = conn.execute(
            text(f"SELECT count(*) FROM learner.pedagogy_feedback f {clause}"),
            {k: v for k, v in params.items() if k not in ("limit", "offset")},
        ).scalar_one()
        return {
            "items": [dict(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


def resolve_feedback(feedback_id: UUID, status: str, note: str,
                     retrieval_verdict: str = "UNCLASSIFIED", error_kind: str = "UNCLASSIFIED",
                     actor: str | None = None) -> dict | None:
    """Review a pending report once. ``actor`` is the admin principal (``Actor.id``): stored as the reviewer and audited
    (LRN-F22, LRN-S10); ``None`` records the system actor."""
    return _learner().resolve_feedback(feedback_id, status, note, retrieval_verdict, error_kind, actor)


def _pg_resolve_feedback(feedback_id: UUID, status: str, note: str, retrieval_verdict: str, error_kind: str,
                         actor: str | None) -> dict | None:
    with engine.begin() as conn:
        row = (
            conn.execute(
                text("""
            UPDATE learner.pedagogy_feedback SET status=:status,review_note=:note,reviewed_at=now(),
                retrieval_verdict=:verdict,error_kind=:error_kind
            WHERE feedback_id=:id AND status='PENDING' RETURNING feedback_id,status,review_note,retrieval_verdict,error_kind
        """),
                {"id": feedback_id, "status": status, "note": note.strip(),
                 "verdict": retrieval_verdict, "error_kind": error_kind},
            )
            .mappings()
            .first()
        )
        if row is not None:
            from mathbank_rest.db.pedagogy_admin import ANONYMOUS, audit

            audit(conn, actor or ANONYMOUS, "FEEDBACK_REVIEWED", "FEEDBACK", str(feedback_id),
                  before_state={"status": "PENDING"},
                  after_state={"status": status, "retrieval_verdict": retrieval_verdict, "error_kind": error_kind})
        return dict(row) if row else None


def reviewed_retrieval_examples(limit: int = 100) -> dict:
    return {"examples": _learner().list_retrieval_examples(limit),
            "message": "Reviewed evaluation evidence only; no automatic training or canonical mutation."}


def _pg_retrieval_examples(limit: int) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT f.topic AS query,p.canonical_code,f.retrieval_verdict,f.error_kind,
                   f.review_note AS reason,f.reviewed_at,f.feedback_id AS review_reference
            FROM learner.pedagogy_feedback f JOIN core.problem p USING(problem_id)
            WHERE f.status='RESOLVED' AND f.retrieval_verdict <> 'UNCLASSIFIED'
            ORDER BY f.reviewed_at DESC LIMIT :limit
        """), {"limit": limit}).mappings()
        return [dict(row) for row in rows]
