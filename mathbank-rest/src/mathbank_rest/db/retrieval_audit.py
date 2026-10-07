"""Read-only audit evidence; allegations never become canonical decisions."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

AUDIT_VERSION = "topic-audit-v1"
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))
from power_geometry_evidence import POWER, power_structure


def audit_problem(conn, code: str, topic: str, node: dict | None) -> dict:
    problem = conn.execute(text("SELECT problem_id,statement_text FROM core.problem WHERE canonical_code=:code"),
                           {"code": code}).mappings().first()
    if problem is None:
        return {"error": "UNKNOWN_PROBLEM"}
    steps = list(conn.execute(text("""
        SELECT solution_step_id,step_text FROM pedagogy.solution_step
        WHERE problem_id=:id AND publication_status='PUBLISHED' ORDER BY global_step_index
    """), {"id": problem["problem_id"]}).mappings())
    support = []
    assertions = []
    if node:
        support = list(conn.execute(text("""
            SELECT s.solution_step_id FROM pedagogy.solution_step s
            JOIN pedagogy.taxonomy_node n ON n.taxonomy_node_id=:node
            WHERE s.problem_id=:id AND s.publication_status='PUBLISHED'
              AND ((n.node_type='SKILL' AND s.skill_node_id=n.taxonomy_node_id)
               OR (n.node_type='CONCEPT' AND s.concept_node_id=n.taxonomy_node_id)
               OR (n.node_type='SUBCONCEPT' AND s.subconcept_node_id=n.taxonomy_node_id)
               OR (n.node_type='TECHNIQUE' AND EXISTS (
                   SELECT 1 FROM pedagogy.solution_step_technique st
                   WHERE st.solution_step_id=s.solution_step_id
                     AND st.technique_node_id=n.taxonomy_node_id AND st.review_status='APPROVED')))
        """), {"id": problem["problem_id"], "node": node["taxonomy_node_id"]}).scalars())
        assertions = [dict(row) for row in conn.execute(text("""
            SELECT t.slug,pt.role,pt.review_status,pt.approval_method,pt.confidence,pt.assertion_source
            FROM knowledge.problem_technique pt JOIN knowledge.technique t USING(technique_id)
            JOIN pedagogy.taxonomy_node n ON n.technique_id=t.technique_id
            WHERE pt.problem_id=:id AND n.taxonomy_node_id=:node
        """), {"id": problem["problem_id"], "node": node["taxonomy_node_id"]}).mappings()]
    for assertion in assertions:
        assertion["confidence"] = float(assertion["confidence"]) if assertion["confidence"] is not None else None
    structural = power_structure(problem["statement_text"] or "", steps) if node and node["taxonomy_node_id"] == POWER else None
    return {"version": AUDIT_VERSION, "problem_code": code, "requested_topic": topic,
            "requested_node_id": node["taxonomy_node_id"] if node else None,
            "published_step_count": len(steps), "supporting_step_ids": support[:50],
            "challenged_assertions": assertions, "structural_validation": structural,
            "suggested_error_kind": "METADATA" if assertions and not support else "INSUFFICIENT_EVIDENCE" if not support else "RETRIEVAL",
            "review_status": "PENDING", "retrieval_score": None,
            "message": "Correction candidate only. Inspect source evidence before any canonical change."}
