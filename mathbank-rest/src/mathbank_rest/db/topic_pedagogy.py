"""Exact taxonomy grounding and learner reports; no models or automatic approval."""

from __future__ import annotations

import json
import re
from uuid import UUID

from sqlalchemy import text

from mathbank_rest.db.postgres import engine
from mathbank_rest.db.retrieval_audit import audit_problem
from mathbank_rest.db.step_search import _TAXONOMY_DETAILS
from mathbank_rest.practice_selection import load_profile, rank_candidates


def topic_key(value: str) -> str:
    return " ".join(
        word
        for word in re.findall(r"[a-z0-9]+", value.lower())
        if word not in {"a", "an", "the", "of"}
    )


def topic_plan(query: str) -> dict:
    key = topic_key(query)
    with engine.connect() as conn:
        nodes = list(
            conn.execute(
                text(
                    "SELECT taxonomy_node_id,name,node_type FROM pedagogy.taxonomy_node "
                    "WHERE node_type IN ('CONCEPT','SUBCONCEPT','SKILL','TECHNIQUE')"
                )
            ).mappings()
        )
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
        node = dict(
            conn.execute(text(_TAXONOMY_DETAILS), {"ids": [exact[0]["taxonomy_node_id"]]})
            .mappings()
            .one()
        )
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


def topic_candidates(topic: str, *, profile_version: str = "topic-fit-v1", limit: int = 10,
                     target_difficulty: int | None = None, known_skills: list[str] | None = None,
                     exposed_codes: list[str] | None = None, exclude_codes: list[str] | None = None,
                     student_id: UUID | None = None) -> dict:
    profile = load_profile(profile_version)
    plan = topic_plan(topic)
    if not plan["matched"]:
        return plan
    node = plan["node"]
    with engine.connect() as conn:
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
            ORDER BY p.canonical_code LIMIT 100
        """), {"node": node["taxonomy_node_id"]}).mappings()
        candidates = [dict(row) for row in rows]
        exposure = set(exposed_codes or [])
        gap_skills = None
        if student_id:
            exposure.update(conn.execute(text("""
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
        for candidate in candidates:
            candidate["confidence"] = float(candidate["confidence"] or 0)
            candidate["exposure_known"] = student_id is not None
            candidate["gap_skill_ids"] = gap_skills
            skills = candidate["skill_ids"]
            candidate["prerequisite_ids"] = list(conn.execute(text("""
                SELECT DISTINCT from_node_id FROM pedagogy.taxonomy_edge
                WHERE to_node_id=ANY(:skills) AND relationship_type='PREREQUISITE_OF'
            """), {"skills": skills}).scalars()) if skills else []
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


def submit_feedback(student_id: UUID, problem_code: str, topic: str, reason: str) -> dict | None:
    grounding = topic_plan(topic)
    with engine.begin() as conn:
        audit = audit_problem(conn, problem_code, topic, grounding.get("node"))
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


def feedback_queue(limit: int, offset: int) -> dict:
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
            SELECT f.feedback_id,p.canonical_code,f.topic,f.reason,f.status,f.created_at,
                   f.review_note,f.reviewed_at,f.audit_snapshot AS audit,
                   f.retrieval_verdict,f.error_kind,
                   count(*) OVER (PARTITION BY f.problem_id,f.topic) AS related_report_count
            FROM learner.pedagogy_feedback f JOIN core.problem p USING(problem_id)
            ORDER BY (f.status='PENDING') DESC,f.created_at DESC LIMIT :limit OFFSET :offset
        """),
            {"limit": limit, "offset": offset},
        ).mappings()
        total = conn.execute(text("SELECT count(*) FROM learner.pedagogy_feedback")).scalar_one()
        return {
            "items": [dict(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


def resolve_feedback(feedback_id: UUID, status: str, note: str,
                     retrieval_verdict: str = "UNCLASSIFIED", error_kind: str = "UNCLASSIFIED") -> dict | None:
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
        return dict(row) if row else None


def reviewed_retrieval_examples(limit: int = 100) -> dict:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT f.topic AS query,p.canonical_code,f.retrieval_verdict,f.error_kind,
                   f.review_note AS reason,f.reviewed_at,f.feedback_id AS review_reference
            FROM learner.pedagogy_feedback f JOIN core.problem p USING(problem_id)
            WHERE f.status='RESOLVED' AND f.retrieval_verdict <> 'UNCLASSIFIED'
            ORDER BY f.reviewed_at DESC LIMIT :limit
        """), {"limit": limit}).mappings()
        return {"examples": [dict(row) for row in rows],
                "message": "Reviewed evaluation evidence only; no automatic training or canonical mutation."}
