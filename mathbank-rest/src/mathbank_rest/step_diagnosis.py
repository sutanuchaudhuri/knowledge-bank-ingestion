"""Step-level gap diagnosis (v2 Phase 9) — runtime_extension/10 and 13_ATTEMPT_DIAGNOSIS.

When a student is stuck on a solution step, rank *several* knowledge-gap hypotheses: the local
skill the step exercises first ("ratio manipulation", not "similarity"), then the skills of the
steps it DEPENDS_ON (the step DAG is the prerequisite source: Prasolov skills have no
skill-level PREREQUISITE_OF edges), then the subconcept and concept prerequisites. Scoring is
deterministic and free (no model call), so it can run inside the outcome transaction.

Rules (spec): persist every hypothesis, never overwrite one (only its status moves
UNRESOLVED → CONFIRMED/REJECTED, CONFIRMED → RESOLVED, each with a learner.event), never set
mastery from a diagnosis, and never show canonical step text in probes.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from mathbank_rest import step_runtime
from mathbank_rest.step_diagnosis_logic import (  # noqa: F401  (pure logic, shared with the DynamoDB backend; re-exported)
    ACTION_LABELS,
    ACTIONS,
    AUTO_MIN_FAILED_TRIES,
    AUTO_MIN_HELP,
    CONCEPTUAL_MODES,
    DIAGNOSER_VERSION,
    LOCAL_LOCATIONS,
    LOCATION_LABELS,
    MAX_HYPOTHESES,
    OPEN_STATUSES,
    RECOVERY_THRESHOLD,
    RERANK_MODEL,
    TRIGGERS,
    apply_rerank,
    evidence_fingerprint,
    evidence_of,
    gap_matches_step,
    gap_transition,
    likelihood_label,
    openai_reranker,
    recommend_action,
    rerank_context_of,
    rerank_enabled,
    score_hypotheses,
    should_auto_diagnose,
    stored_rerank,
    student_view,
    validate_rerank,
)
from mathbank_rest.step_runtime import (
    CROSS_REFERENCE_STUB_RE,
    NotFound,
    _event,
    _lock_attempt,
    _outbox,
)

# ---------------------------------------------------------------- context loading

def _skill_history(conn: Connection, student_id: str, skill_id: str, attempt_id: str, step_id: str) -> dict:
    row = conn.execute(text(
        "SELECT count(*) FILTER (WHERE st.state = 'SUCCESS_INDEPENDENT') AS independent, "
        "       count(*) FILTER (WHERE st.state = 'SUCCESS_WITH_HELP') AS with_help, "
        "       count(*) FILTER (WHERE st.state IN ('FAILED', 'RETRY_PRESENTED')) AS failed "
        "  FROM learner.attempt_step_state st "
        "  JOIN learner.solve_attempt a USING (solve_attempt_id) "
        "  JOIN pedagogy.solution_step s ON s.solution_step_id = st.solution_step_id "
        " WHERE a.student_id = CAST(:stu AS uuid) AND s.skill_node_id = :sk "
        "   AND NOT (st.solve_attempt_id = CAST(:a AS uuid) AND st.solution_step_id = :s)"),
        {"stu": student_id, "sk": skill_id, "a": attempt_id, "s": step_id}).mappings().one()
    return {k: int(v) for k, v in row.items()}


_STEP_SQL = (
    "SELECT s.solution_step_id, s.problem_id, s.step_type, s.skill_node_id AS skill_id, "
    "       coalesce(s.skill_name, sk.name) AS skill_label, sk.skill_id AS skill_uuid, "
    "       s.subconcept_node_id AS subconcept_id, sc.name AS subconcept_label, "
    "       s.concept_node_id AS concept_id, cn.name AS concept_label, cn.concept_id AS concept_uuid "
    "  FROM pedagogy.solution_step s "
    "  LEFT JOIN pedagogy.taxonomy_node sk ON sk.taxonomy_node_id = s.skill_node_id "
    "  LEFT JOIN pedagogy.taxonomy_node sc ON sc.taxonomy_node_id = s.subconcept_node_id "
    "  LEFT JOIN pedagogy.taxonomy_node cn ON cn.taxonomy_node_id = s.concept_node_id ")


def load_context(conn: Connection, attempt: dict, step_id: str) -> dict:
    attempt_id, student_id = str(attempt["solve_attempt_id"]), str(attempt["student_id"])
    row = conn.execute(text(_STEP_SQL + "WHERE s.solution_step_id = :s"), {"s": step_id}).mappings().first()
    if row is None or str(row["problem_id"]) != str(attempt["problem_id"]):
        raise NotFound("step is not part of this attempt")
    step = {k: (str(v) if isinstance(v, UUID) else v) for k, v in row.items()}
    states = step_runtime._states(conn, attempt_id)
    st = states.get(step_id)
    if st is None:
        raise step_runtime.InvalidTransition("step has not been presented yet")
    ev = st.get("last_evaluation") or {}
    current = {"state": st["state"], "attempt_count": st.get("attempt_count", 0),
               "help_level": st.get("help_level_used", 0), "failure_mode": ev.get("failure_mode"),
               "failure_location": ev.get("failure_location"), "verdict": ev.get("verdict")}
    preds = []
    for p in conn.execute(text(
            _STEP_SQL + "JOIN pedagogy.solution_step_dependency d ON d.from_step_id = s.solution_step_id "
            "WHERE d.to_step_id = :s AND d.relationship_type = 'DEPENDS_ON' AND d.review_status <> 'REJECTED' "
            "ORDER BY s.global_step_index DESC"), {"s": step_id}).mappings():
        ps = states.get(p["solution_step_id"], {})
        preds.append({"step_id": p["solution_step_id"], "skill_id": p["skill_id"], "skill_label": p["skill_label"],
                      "skill_uuid": str(p["skill_uuid"]) if p["skill_uuid"] else None,
                      "subconcept_id": p["subconcept_id"], "concept_id": p["concept_id"],
                      "state": ps.get("state"), "help_level": ps.get("help_level_used", 0),
                      "independent": bool(ps.get("independent_success")),
                      "history": _skill_history(conn, student_id, p["skill_id"], attempt_id, p["solution_step_id"])
                      if p["skill_id"] else {}})
    sub_fail = 0
    if step["subconcept_id"]:
        sub_fail = conn.execute(text(
            "SELECT count(DISTINCT s.skill_node_id) FROM learner.attempt_step_state st "
            "JOIN pedagogy.solution_step s USING (solution_step_id) "
            "WHERE st.solve_attempt_id = CAST(:a AS uuid) AND st.state IN ('FAILED', 'RETRY_PRESENTED') "
            "  AND s.subconcept_node_id = :sc AND s.skill_node_id IS DISTINCT FROM :sk "
            "  AND s.solution_step_id <> :s"),
            {"a": attempt_id, "sc": step["subconcept_id"], "sk": step["skill_id"], "s": step_id}).scalar_one()
    concept_prereqs = []
    if step.get("concept_uuid"):
        concept_prereqs = [{"concept_id": r["slug"] or str(r["concept_id"]), "label": r["name"]} for r in conn.execute(text(
            "SELECT c.concept_id, c.slug, c.name FROM knowledge.concept_relation r "
            "JOIN knowledge.concept c ON c.concept_id = r.from_concept_id "
            "WHERE r.to_concept_id = CAST(:c AS uuid) AND r.relation_type = 'PREREQUISITE_OF' "
            "  AND coalesce(r.review_status, '') <> 'REJECTED' ORDER BY r.strength DESC NULLS LAST LIMIT 2"),
            {"c": step["concept_uuid"]}).mappings()]
    # Derived step techniques (migration 017); empty for steps without tags and for non-textbook corpora.
    techniques = [dict(r) for r in conn.execute(text(
        "SELECT t.technique_node_id, n.name, t.confidence::float AS confidence "
        "  FROM pedagogy.solution_step_technique t JOIN pedagogy.taxonomy_node n "
        "    ON n.taxonomy_node_id = t.technique_node_id "
        " WHERE t.solution_step_id = :s AND t.review_status = 'APPROVED' "
        " ORDER BY t.confidence DESC, t.technique_node_id"), {"s": step_id}).mappings()]
    return {"step": step, "current": current, "predecessors": preds, "subconcept_failures": int(sub_fail),
            "concept_prereqs": concept_prereqs, "step_techniques": techniques,
            "skill_history": _skill_history(conn, student_id, step["skill_id"], attempt_id, step_id)
            if step["skill_id"] else {}}


def find_probes(conn: Connection, student_id: str, problem_id: str, skill_id: str | None,
                skill_uuid: str | None, limit: int = 3) -> list[dict]:
    """Short checks for a skill: approved non-proof learning items first, then same-skill steps from other
    problems the student has not seen. Codes and metadata only — never step text."""
    if not skill_id:
        return []
    # Items generated from the problem being solved are excluded: they quote its own solution steps.
    probes = [dict(r) | {"kind": "LEARNING_ITEM"} for r in conn.execute(text(
        "SELECT li.learning_item_id::text AS learning_item_id, li.transformation_type, li.transformed_form, "
        "       p.canonical_code AS problem_code "
        "  FROM pedagogy.learning_item li LEFT JOIN core.problem p ON p.problem_id = li.source_problem_id "
        " WHERE li.review_status = 'APPROVED' AND li.student_visible AND li.no_proof "
        "   AND li.source_problem_id IS DISTINCT FROM CAST(:p AS uuid) "
        "   AND length(coalesce(li.answer_or_solution_seed, li.correct_answer, '')) >= 25 "
        "   AND coalesce(li.answer_or_solution_seed, '') !~* :stub AND coalesce(li.correct_answer, '') !~* :stub "
        "   AND (li.target_skill_node_id = :sk OR (li.target_skill_node_id IS NULL AND li.target_subconcept_node_id = "
        "        (SELECT subconcept_node_id FROM pedagogy.solution_step WHERE skill_node_id = :sk "
        "          AND subconcept_node_id IS NOT NULL LIMIT 1))) "
        " ORDER BY (li.target_skill_node_id IS NULL), "
        "          array_position(ARRAY['MCQ_METHOD_RECOGNITION','MCQ_FIRST_MOVE','MCQ_INTERMEDIATE_SKILL',"
        "                               'SUBPROBLEM_FIRST_MOVE'], li.transformation_type) NULLS LAST, "
        "          md5(:stu || li.learning_item_id::text) LIMIT :n"),
        {"sk": skill_id, "p": problem_id, "stu": student_id, "n": limit,
         "stub": CROSS_REFERENCE_STUB_RE}).mappings()]
    if len(probes) < limit:
        probes += [dict(r) | {"kind": "PRACTICE_STEP"} for r in conn.execute(text(
            "SELECT s.solution_step_id, p.canonical_code AS problem_code, s.global_step_index, s.step_type, "
            "       s.skill_name, s.is_checkpoint "
            "  FROM pedagogy.solution_step s JOIN core.problem p ON p.problem_id = s.problem_id "
            " WHERE s.skill_node_id = :sk AND s.problem_id <> CAST(:p AS uuid) "
            "   AND s.publication_status = 'PUBLISHED' "
            "   AND NOT EXISTS (SELECT 1 FROM learner.attempt_step_state st "
            "                    JOIN learner.solve_attempt a USING (solve_attempt_id) "
            "                   WHERE a.student_id = CAST(:stu AS uuid) AND st.solution_step_id = s.solution_step_id) "
            " ORDER BY s.is_checkpoint DESC, s.global_step_index, s.solution_step_id LIMIT :n"),
            {"sk": skill_id, "p": problem_id, "stu": student_id, "n": limit - len(probes)}).mappings()]
    return probes


# ---------------------------------------------------------------- persistence

def _diagnosis_row(conn: Connection, diagnosis_id: str) -> dict:
    d = dict(conn.execute(text(
        "SELECT gap_diagnosis_id::text, student_id::text, solve_attempt_id::text, solution_step_id, trigger, "
        "       recommended_action, evidence, probes, diagnoser_version, ai_rerank, created_at "
        "  FROM pedagogy.gap_diagnosis WHERE gap_diagnosis_id = CAST(:d AS uuid)"), {"d": diagnosis_id}).mappings().one())
    d["hypotheses"] = [dict(r) for r in conn.execute(text(
        "SELECT knowledge_gap_id::text, rank, failure_location, failure_mode, target_concept_id, "
        "       target_subconcept_id, target_skill_id, target_skill_node_id::text, target_label, source_step_id, "
        "       confidence::float AS confidence, evidence, status, status_reason, created_at, status_changed_at, "
        "       resolved_at FROM pedagogy.knowledge_gap WHERE gap_diagnosis_id = CAST(:d AS uuid) ORDER BY rank"),
        {"d": diagnosis_id}).mappings()]
    return d


def diagnose_locked(conn: Connection, attempt: dict, step_id: str, trigger: str, actor: str) -> dict:
    """Score and persist a diagnosis for an already-locked attempt; identical evidence returns the existing one."""
    if trigger not in TRIGGERS:
        raise ValueError(trigger)
    ctx = load_context(conn, attempt, step_id)
    attempt_id, student_id = str(attempt["solve_attempt_id"]), str(attempt["student_id"])
    fp = evidence_fingerprint(ctx)
    existing = conn.execute(text(
        "SELECT gap_diagnosis_id::text FROM pedagogy.gap_diagnosis WHERE solve_attempt_id = CAST(:a AS uuid) "
        "AND solution_step_id = :s AND evidence_fingerprint = :f"), {"a": attempt_id, "s": step_id, "f": fp}).scalar()
    if existing:
        return {**_diagnosis_row(conn, existing), "reused": True}
    hyps = score_hypotheses(ctx)
    action = recommend_action(hyps, ctx)
    probes = []
    if action != "RETRY_WITH_HINT" and hyps:
        probes = find_probes(conn, student_id, str(attempt["problem_id"]), hyps[0]["target_skill_id"],
                             hyps[0]["target_skill_node_id"])
    diagnosis_id = conn.execute(text(
        "INSERT INTO pedagogy.gap_diagnosis (student_id, solve_attempt_id, solution_step_id, trigger, "
        "  recommended_action, evidence_fingerprint, evidence, probes, diagnoser_version) "
        "VALUES (:stu, :a, :s, :t, :act, :f, CAST(:ev AS jsonb), CAST(:pr AS jsonb), :v) "
        "RETURNING gap_diagnosis_id::text"),
        {"stu": student_id, "a": attempt_id, "s": step_id, "t": trigger, "act": action, "f": fp,
         "ev": json.dumps(evidence_of(ctx), default=str),
         "pr": json.dumps(probes, default=str), "v": DIAGNOSER_VERSION}).scalar_one()
    for h in hyps:
        gap_id = conn.execute(text(
            "INSERT INTO pedagogy.knowledge_gap (gap_diagnosis_id, student_id, solve_attempt_id, solution_step_id, "
            "  rank, failure_location, failure_mode, target_concept_id, target_subconcept_id, target_skill_id, "
            "  target_skill_node_id, target_label, source_step_id, confidence, evidence) "
            "VALUES (CAST(:d AS uuid), :stu, :a, :s, :r, :loc, :mode, :c, :sc, :sk, CAST(:sku AS uuid), :lbl, :src, "
            "  :conf, CAST(:ev AS jsonb)) RETURNING knowledge_gap_id::text"),
            {"d": diagnosis_id, "stu": student_id, "a": attempt_id, "s": step_id, "r": h["rank"],
             "loc": h["failure_location"], "mode": h["failure_mode"], "c": h["target_concept_id"],
             "sc": h["target_subconcept_id"], "sk": h["target_skill_id"], "sku": h["target_skill_node_id"],
             "lbl": h["target_label"], "src": h["source_step_id"], "conf": h["confidence"],
             "ev": json.dumps(h["evidence"])}).scalar_one()
        _event(conn, student_id, attempt_id, "GAP_HYPOTHESIS_CREATED", actor, step_id=step_id,
               payload={"knowledge_gap_id": gap_id, "gap_diagnosis_id": diagnosis_id, "rank": h["rank"],
                        "failure_location": h["failure_location"], "target_skill_id": h["target_skill_id"],
                        "confidence": h["confidence"]})
        _outbox(conn, "KNOWLEDGE_GAP_CREATED", "knowledge_gap", gap_id,
                {"student_id": str(student_id), "solve_attempt_id": str(attempt_id), "solution_step_id": step_id,
                 "target_skill_id": h["target_skill_id"], "rank": h["rank"]})
    _event(conn, student_id, attempt_id, "GAP_DIAGNOSED", actor, step_id=step_id,
           payload={"gap_diagnosis_id": diagnosis_id, "trigger": trigger, "recommended_action": action,
                    "hypotheses": len(hyps)})
    _outbox(conn, "GAP_DIAGNOSED", "solve_attempt", attempt_id,
            {"student_id": student_id, "solution_step_id": step_id, "gap_diagnosis_id": diagnosis_id,
             "recommended_action": action})
    return {**_diagnosis_row(conn, diagnosis_id), "reused": False}


def diagnose_step(conn: Connection, student_id: UUID | None, attempt_id: UUID | str, step_id: str,
                  trigger: str = "STUDENT_REQUEST") -> dict:
    """Entry point for the REST route: ownership-checked, serialized on the attempt row lock.
    Does not change runtime mode or ``state_version`` (Phase 10 consumes RECOVERY_DETOUR)."""
    attempt = _lock_attempt(conn, attempt_id, student_id)
    actor = "STUDENT" if trigger == "STUDENT_REQUEST" else "TUTOR"
    return diagnose_locked(conn, attempt, step_id, trigger, actor)


def update_gap_statuses(conn: Connection, attempt: dict, step_id: str, result: str, independent: bool,
                        actor: str) -> list[dict]:
    """Move this student's open hypotheses about the evaluated step's skill (or, for subconcept-level
    hypotheses, its subconcept) given a new outcome. Rows are updated in place only in their status."""
    student_id, attempt_id = str(attempt["student_id"]), str(attempt["solve_attempt_id"])
    step = conn.execute(text(
        "SELECT skill_node_id, subconcept_node_id FROM pedagogy.solution_step WHERE solution_step_id = :s"),
        {"s": step_id}).mappings().first()
    if step is None:
        return []
    rows = conn.execute(text(
        "SELECT knowledge_gap_id::text, status FROM pedagogy.knowledge_gap "
        " WHERE student_id = CAST(:stu AS uuid) AND status IN ('UNRESOLVED', 'CONFIRMED') "
        "   AND ((target_skill_id IS NOT NULL AND target_skill_id = :sk) "
        "     OR (target_skill_id IS NULL AND failure_location = 'SUBCONCEPT' AND target_subconcept_id = :sc)) "
        " FOR UPDATE"), {"stu": student_id, "sk": step["skill_node_id"], "sc": step["subconcept_node_id"]}).mappings()
    changed = []
    for r in list(rows):
        new = gap_transition(r["status"], result, independent)
        if new is None:
            continue
        reason = f"{result}{'_INDEPENDENT' if independent else ''} on {step_id}"
        conn.execute(text(
            "UPDATE pedagogy.knowledge_gap SET status = :st, status_reason = :why, status_changed_at = now(), "
            "  resolved_at = CASE WHEN :st IN ('REJECTED', 'RESOLVED') THEN now() END "
            "WHERE knowledge_gap_id = CAST(:g AS uuid)"), {"st": new, "why": reason, "g": r["knowledge_gap_id"]})
        _event(conn, student_id, attempt_id, f"GAP_HYPOTHESIS_{new}", actor, step_id=step_id,
               payload={"knowledge_gap_id": r["knowledge_gap_id"], "from": r["status"], "to": new, "reason": reason})
        changed.append({"knowledge_gap_id": r["knowledge_gap_id"], "from": r["status"], "to": new})
    return changed


# ---------------------------------------------------------------- reads

def latest_for_step(conn: Connection, attempt_id: str, step_id: str) -> dict | None:
    d = conn.execute(text(
        "SELECT gap_diagnosis_id::text FROM pedagogy.gap_diagnosis WHERE solve_attempt_id = CAST(:a AS uuid) "
        "AND solution_step_id = :s ORDER BY created_at DESC LIMIT 1"), {"a": attempt_id, "s": step_id}).scalar()
    return _diagnosis_row(conn, d) if d else None


def list_diagnoses(conn: Connection, student_id: UUID | None, attempt_id: UUID | str) -> list[dict]:
    owner = conn.execute(text("SELECT student_id::text FROM learner.solve_attempt WHERE solve_attempt_id = CAST(:a AS uuid)"),
                         {"a": str(attempt_id)}).scalar()
    if owner is None or (student_id is not None and owner != str(student_id)):
        raise NotFound("attempt not found")
    ids = conn.execute(text(
        "SELECT gap_diagnosis_id::text FROM pedagogy.gap_diagnosis WHERE solve_attempt_id = CAST(:a AS uuid) "
        "ORDER BY created_at DESC"), {"a": str(attempt_id)}).scalars().all()
    return [_diagnosis_row(conn, d) for d in ids]


def list_student_gaps(conn: Connection, student_id: UUID, status: str | None = None, limit: int = 100) -> list[dict]:
    """Admin view: full hypothesis rows (failure mode, confidence, evidence) for one student."""
    return [dict(r) for r in conn.execute(text(
        "SELECT knowledge_gap_id::text, gap_diagnosis_id::text, solve_attempt_id::text, solution_step_id, rank, "
        "       failure_location, failure_mode, target_concept_id, target_subconcept_id, target_skill_id, "
        "       target_label, source_step_id, confidence::float AS confidence, evidence, status, status_reason, "
        "       created_at, status_changed_at, resolved_at "
        "  FROM pedagogy.knowledge_gap WHERE student_id = CAST(:s AS uuid) "
        "   AND (CAST(:st AS text) IS NULL OR status = :st) ORDER BY created_at DESC, rank LIMIT :n"),
        {"s": str(student_id), "st": status, "n": min(max(limit, 1), 500)}).mappings()]


# ---------------------------------------------------------------- optional AI re-rank (Phase 9 extension)
# The pure parts (validation, the model call, the stored document) live in ``step_diagnosis_logic``; this is the SQL side.

def rerank_context(conn: Connection, d: dict) -> dict:
    step = conn.execute(text(
        "SELECT step_type, skill_name FROM pedagogy.solution_step WHERE solution_step_id = :s"),
        {"s": d["solution_step_id"]}).mappings().first() or {}
    return rerank_context_of(d, step)


def rerank_diagnosis(engine, diagnosis_id: str, reranker: Callable[[dict], dict] | None = None,
                     force: bool = False) -> dict | None:
    """Best effort: returns the stored ``ai_rerank`` or None (disabled, <2 hypotheses, model/validation error)."""
    if not (force or rerank_enabled()):
        return None
    with engine.connect() as conn:
        d = _diagnosis_row(conn, diagnosis_id)
        if d.get("ai_rerank"):
            return d["ai_rerank"]
        if len(d["hypotheses"]) < 2:
            return None
        context = rerank_context(conn, d)
    try:
        answer = (reranker or openai_reranker)(context)
    except Exception:  # noqa: BLE001 — the rules order stands
        return None
    order = validate_rerank(answer, d["hypotheses"])
    if order is None:
        return None
    stored = stored_rerank(answer, order, d["hypotheses"])
    with engine.begin() as conn:
        conn.execute(text("UPDATE pedagogy.gap_diagnosis SET ai_rerank = CAST(:r AS jsonb) "
                          "WHERE gap_diagnosis_id = CAST(:d AS uuid) AND ai_rerank IS NULL"),
                     {"r": json.dumps(stored), "d": diagnosis_id})
        return conn.execute(text("SELECT ai_rerank FROM pedagogy.gap_diagnosis WHERE gap_diagnosis_id = CAST(:d AS uuid)"),
                            {"d": diagnosis_id}).scalar()


def admin_gap_overview(conn: Connection, *, status: str | None = None, student: str | None = None,
                       limit: int = 100) -> dict:
    """Teacher overview across students: status totals, most common open skills, and recent hypotheses.
    ``student`` filters by e-mail substring or exact student uuid."""
    flt = ("(CAST(:st AS text) IS NULL OR g.status = :st) AND (CAST(:who AS text) IS NULL "
           " OR sp.email ILIKE '%' || :who || '%' OR g.student_id::text = :who)")
    params = {"st": status, "who": (student or "").strip() or None, "n": min(max(limit, 1), 500)}
    base = "FROM pedagogy.knowledge_gap g JOIN learner.student_profile sp USING (student_id) WHERE "
    totals = {r[0]: r[1] for r in conn.execute(text(
        "SELECT g.status, count(*) " + base + flt.replace("(CAST(:st AS text) IS NULL OR g.status = :st) AND ", "")
        + " GROUP BY g.status"), params)}
    top = [dict(r) for r in conn.execute(text(
        "SELECT coalesce(g.target_skill_id, g.target_subconcept_id) AS target_id, max(g.target_label) AS target_label, "
        "       count(*) AS open_gaps, count(DISTINCT g.student_id) AS students " + base
        + "g.status IN ('UNRESOLVED', 'CONFIRMED') AND (CAST(:who AS text) IS NULL "
          " OR sp.email ILIKE '%' || :who || '%' OR g.student_id::text = :who) "
          "GROUP BY 1 ORDER BY open_gaps DESC, students DESC LIMIT 10"), params).mappings()]
    rows = [dict(r) for r in conn.execute(text(
        "SELECT g.knowledge_gap_id::text, g.gap_diagnosis_id::text, g.student_id::text, sp.email, "
        "       g.solve_attempt_id::text, p.canonical_code AS problem_code, g.solution_step_id, g.rank, "
        "       g.failure_location, g.failure_mode, g.target_skill_id, g.target_label, g.source_step_id, "
        "       g.confidence::float AS confidence, g.status, g.status_reason, g.created_at, g.status_changed_at, "
        "       d.trigger, d.recommended_action, d.ai_rerank IS NOT NULL AS ai_reranked, "
        "       (SELECT rp.recovery_plan_id::text FROM pedagogy.recovery_plan rp "
        "         WHERE rp.knowledge_gap_id = g.knowledge_gap_id ORDER BY rp.created_at DESC LIMIT 1) AS recovery_plan_id, "
        "       (SELECT rp.status FROM pedagogy.recovery_plan rp "
        "         WHERE rp.knowledge_gap_id = g.knowledge_gap_id ORDER BY rp.created_at DESC LIMIT 1) AS recovery_status "
        "  FROM pedagogy.knowledge_gap g JOIN learner.student_profile sp USING (student_id) "
        "  JOIN pedagogy.gap_diagnosis d USING (gap_diagnosis_id) "
        "  JOIN learner.solve_attempt a ON a.solve_attempt_id = g.solve_attempt_id "
        "  JOIN core.problem p ON p.problem_id = a.problem_id "
        " WHERE " + flt + " ORDER BY g.created_at DESC, g.rank LIMIT :n"), params).mappings()]
    return {"totals": totals, "top_open_targets": top, "gaps": rows}
