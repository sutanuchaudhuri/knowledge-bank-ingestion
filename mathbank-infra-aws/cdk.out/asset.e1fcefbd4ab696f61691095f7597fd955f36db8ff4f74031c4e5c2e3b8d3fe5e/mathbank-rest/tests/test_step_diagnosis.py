"""Gap diagnosis (v2 Phase 9): pure scoring, route guards, and an opt-in live golden flow.

Live tests (MATHBANK_LIVE_STEP_RUNTIME_TEST=1) run inside one transaction that always rolls back.
"""
from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from mathbank_rest import security
from mathbank_rest import step_diagnosis as dx
from mathbank_rest import step_runtime as rt
from mathbank_rest.main import app

client = TestClient(app)


def _ctx(**over):
    ctx = {
        "step": {"skill_id": "SKILL.A", "skill_label": "Ratio manipulation", "skill_uuid": None,
                 "subconcept_id": "GEO.C01.S01", "subconcept_label": "Parallel lines", "concept_id": "GEO.C01"},
        "current": {"attempt_count": 2, "help_level": 0, "failure_mode": "ALGEBRA_BREAKDOWN",
                    "failure_location": "SKILL", "state": "FAILED"},
        "skill_history": {"independent": 0, "with_help": 0, "failed": 0},
        "predecessors": [{"step_id": "P/1", "skill_id": "SKILL.B", "skill_label": "Similar triangles",
                          "state": "SUCCESS_WITH_HELP", "help_level": 3, "independent": False, "history": {}}],
        "subconcept_failures": 0, "concept_prereqs": [],
    }
    for k, v in over.items():
        ctx[k] = {**ctx[k], **v} if isinstance(v, dict) and isinstance(ctx.get(k), dict) else v
    return ctx


# ---------------------------------------------------------------- pure scoring

def test_local_skill_is_ranked_first_with_prerequisite_second():
    hyps = dx.score_hypotheses(_ctx())
    assert [h["rank"] for h in hyps] == [1, 2]
    assert hyps[0]["failure_location"] == "SKILL" and hyps[0]["target_skill_id"] == "SKILL.A"
    assert hyps[0]["failure_mode"] == "ALGEBRA_BREAKDOWN"
    assert hyps[1]["failure_location"] == "PREREQUISITE" and hyps[1]["source_step_id"] == "P/1"
    assert all(0.05 <= h["confidence"] <= 0.95 for h in hyps)


def test_step_technique_labels_technique_failures_and_is_evidence():
    tech = [{"technique_node_id": "TECH.GEO.POWER_OF_A_POINT", "name": "Power of a point", "confidence": 0.9}]
    hyps = dx.score_hypotheses(_ctx(step_techniques=tech, current={"failure_location": "TECHNIQUE"}))
    assert hyps[0]["failure_location"] == "TECHNIQUE" and hyps[0]["target_label"] == "Power of a point"
    assert hyps[0]["target_skill_id"] == "SKILL.A"
    assert "step_techniques=TECH.GEO.POWER_OF_A_POINT" in hyps[0]["evidence"]["signals"]
    # A skill failure keeps the skill label; untagged steps are unchanged.
    assert dx.score_hypotheses(_ctx(step_techniques=tech))[0]["target_label"] == "Ratio manipulation"
    assert dx.score_hypotheses(_ctx())[0]["target_label"] == "Ratio manipulation"


def test_revealed_prerequisite_and_grader_pointer_can_outrank_local_skill():
    ctx = _ctx(current={"attempt_count": 1, "failure_location": "PREREQUISITE", "failure_mode": "THEOREM_NOT_RECALLED"},
               predecessors=[{"step_id": "P/1", "skill_id": "SKILL.B", "skill_label": "Similar triangles",
                              "state": "SUCCESS_WITH_HELP", "help_level": 5, "independent": False,
                              "history": {"failed": 1}}])
    hyps = dx.score_hypotheses(ctx)
    assert hyps[0]["failure_location"] == "PREREQUISITE"
    assert hyps[0]["failure_mode"] == "THEOREM_NOT_RECALLED"
    assert dx.recommend_action(hyps, ctx) == "RECOVERY_DETOUR"


def test_same_skill_prerequisites_are_not_duplicated_and_subconcept_added():
    ctx = _ctx(predecessors=[{"step_id": "P/1", "skill_id": "SKILL.A", "help_level": 0}],
               subconcept_failures=2, concept_prereqs=[{"concept_id": "c", "label": "Ratios"}])
    locs = [h["failure_location"] for h in dx.score_hypotheses(ctx)]
    assert locs.count("PREREQUISITE") == 0 and "SUBCONCEPT" in locs and "CONCEPT" in locs


def test_careless_or_strong_history_recommends_retry():
    careless = _ctx(current={"failure_mode": "CARELESS"})
    assert dx.recommend_action(dx.score_hypotheses(careless), careless) == "RETRY_WITH_HINT"
    strong = _ctx(skill_history={"independent": 3, "failed": 0}, predecessors=[])
    assert dx.recommend_action(dx.score_hypotheses(strong), strong) == "RETRY_WITH_HINT"


def test_uncertain_evidence_recommends_probe():
    ctx = _ctx(current={"attempt_count": 1, "failure_mode": "NONE", "failure_location": "NONE"},
               predecessors=[])
    hyps = dx.score_hypotheses(ctx)
    assert hyps[0]["confidence"] < dx.RECOVERY_THRESHOLD
    assert dx.recommend_action(hyps, ctx) == "DIAGNOSTIC_PROBE"


@pytest.mark.parametrize(("status", "result", "independent", "expected"), [
    ("UNRESOLVED", "FAILED", False, "CONFIRMED"),
    ("CONFIRMED", "FAILED", False, None),
    ("UNRESOLVED", "SUCCESS", True, "REJECTED"),
    ("CONFIRMED", "SUCCESS", True, "RESOLVED"),
    ("UNRESOLVED", "SUCCESS", False, None),
    ("CONFIRMED", "SKIPPED", None, None),
])
def test_gap_transition(status, result, independent, expected):
    assert dx.gap_transition(status, result, independent) == expected


def test_auto_trigger_threshold_and_fingerprint():
    assert not dx.should_auto_diagnose("FAILED", 1, 0)
    assert dx.should_auto_diagnose("FAILED", 2, 0) and dx.should_auto_diagnose("FAILED", 1, 3)
    assert not dx.should_auto_diagnose("SUCCESS", 5, 5)
    assert dx.evidence_fingerprint(_ctx()) == dx.evidence_fingerprint(_ctx(current={"state": "RETRY_PRESENTED"}))
    assert dx.evidence_fingerprint(_ctx()) != dx.evidence_fingerprint(_ctx(current={"attempt_count": 3}))


def test_student_view_hides_modes_scores_and_evidence():
    d = {"gap_diagnosis_id": "d", "solution_step_id": "s", "trigger": "AUTO", "created_at": None,
         "recommended_action": "RECOVERY_DETOUR", "probes": [],
         "hypotheses": [{"rank": 1, "failure_location": "SKILL", "failure_mode": "ALGEBRA_BREAKDOWN",
                         "target_label": "Ratio manipulation", "confidence": 0.72, "status": "UNRESOLVED",
                         "evidence": {"signals": ["x"]}, "source_step_id": None}]}
    view = dx.student_view(d)
    payload = json.dumps(view)
    assert "ALGEBRA_BREAKDOWN" not in payload and "0.72" not in payload and "signals" not in payload
    assert view["hypotheses"][0]["likelihood"] == "likely"


# ---------------------------------------------------------------- route guards

def _auth(student_id):
    return {"Authorization": f"Bearer {security.create_access_token(student_id)}"}


def test_diagnosis_routes_require_auth_and_admin_key():
    a = uuid4()
    assert client.post(f"/v1/attempts/{a}/steps/PRASOLOV_PGV1/STEP-1.1-A-01/diagnose").status_code == 401
    assert client.get(f"/v1/attempts/{a}/diagnoses").status_code == 401
    assert client.get(f"/v1/admin/attempts/{a}/diagnoses", headers=_auth(uuid4())).status_code == 401
    assert client.get(f"/v1/admin/students/{uuid4()}/knowledge-gaps").status_code == 401


def test_diagnose_route_accepts_slash_step_ids(monkeypatch):
    seen = {}

    def fake(conn, student, attempt, step, trigger):
        seen.update(step=step, trigger=trigger)
        return {"gap_diagnosis_id": "d", "solution_step_id": step, "trigger": trigger, "created_at": None,
                "recommended_action": "DIAGNOSTIC_PROBE", "probes": [], "hypotheses": [], "reused": False}

    monkeypatch.setattr(dx, "diagnose_step", fake)
    r = client.post(f"/v1/attempts/{uuid4()}/steps/PRASOLOV_PGV1/STEP-1.1-A-01/diagnose", headers=_auth(uuid4()))
    assert r.status_code == 200, r.text
    assert seen == {"step": "PRASOLOV_PGV1/STEP-1.1-A-01", "trigger": "STUDENT_REQUEST"}
    assert r.json()["recommended_action_label"]


# ---------------------------------------------------------------- live golden flow (rolled back)

live = pytest.mark.skipif(os.getenv("MATHBANK_LIVE_STEP_RUNTIME_TEST") != "1", reason="Live Postgres opt-in")


@pytest.fixture
def live_conn():
    from mathbank_rest.db.postgres import engine

    with engine.connect() as conn:
        tx = conn.begin()
        try:
            yield conn
        finally:
            tx.rollback()


@live
def test_live_diagnosis_golden_flow(live_conn):
    conn = live_conn
    student = conn.execute(text(
        "INSERT INTO learner.student_profile (email, password_hash, first_name, last_name, display_name) "
        "VALUES (:e, 'x', 'Live', 'Test', 'Live Test') RETURNING student_id"),
        {"e": f"live-{uuid4()}@example.com"}).scalar_one()
    # a step whose DEPENDS_ON predecessor exercises a different skill, in one published problem
    target, pred, problem = conn.execute(text(
        "SELECT b.solution_step_id, a.solution_step_id, b.problem_id::text "
        "  FROM pedagogy.solution_step_dependency d "
        "  JOIN pedagogy.solution_step a ON a.solution_step_id = d.from_step_id "
        "  JOIN pedagogy.solution_step b ON b.solution_step_id = d.to_step_id "
        " WHERE d.relationship_type = 'DEPENDS_ON' AND d.review_status <> 'REJECTED' "
        "   AND a.skill_node_id <> b.skill_node_id AND b.publication_status = 'PUBLISHED' "
        "   AND a.problem_id = b.problem_id ORDER BY b.solution_step_id LIMIT 1")).one()
    started = rt.start_attempt(conn, student, problem)
    attempt_id = started["solve_attempt_id"]
    runtime = rt.get_runtime(conn, attempt_id, student)
    current, version = runtime["current_step"]["solution_step_id"], runtime["attempt"]["state_version"]
    while current != target:  # walk to the target; the predecessor needs strategic help
        if current == pred:
            for _ in range(3):
                version = rt.request_hint(conn, student, attempt_id, current, version)["state_version"]
        out = rt.record_step_outcome(conn, attempt_id, current, "SUCCESS", version)
        current, version = out["current_step_id"], out["state_version"]
        assert current is not None

    def fail_once():
        v = rt.submit_step_response(conn, student, attempt_id, target, "a wrong idea", version)["state_version"]
        return rt.record_step_outcome(conn, attempt_id, target, "FAILED", v,
                                      evaluation={"failure_mode": "CANNOT_EXECUTE", "failure_location": "SKILL"})

    first = fail_once()
    version = first["state_version"]
    assert first["diagnosis"] is None  # one failed try is below the auto threshold
    second = fail_once()
    version = second["state_version"]
    d = second["diagnosis"]
    assert d and d["trigger"] == "AUTO" and len(d["hypotheses"]) >= 2
    assert d["hypotheses"][0]["focus"] in ("SKILL", "PREREQUISITE")
    assert any(h["focus"] == "PREREQUISITE" and h["source_step_id"] == pred for h in d["hypotheses"])
    payload = json.dumps(d, default=str)
    step_text = conn.execute(text("SELECT step_text FROM pedagogy.solution_step WHERE solution_step_id = :s"),
                             {"s": target}).scalar_one()
    assert step_text not in payload and "failure_mode" not in payload
    for p in d["probes"]:
        assert "step_text" not in p
    # runtime exposes it; identical evidence re-uses the same diagnosis
    assert rt.get_runtime(conn, attempt_id, student)["current_step"]["diagnosis"]["gap_diagnosis_id"] == \
        d["gap_diagnosis_id"]
    again = dx.diagnose_step(conn, student, attempt_id, target)
    assert again["reused"] is True and again["gap_diagnosis_id"] == d["gap_diagnosis_id"]
    with pytest.raises(rt.NotFound):
        dx.diagnose_step(conn, uuid4(), attempt_id, target)

    # a third failure confirms the open local-skill hypothesis, then independent success resolves it
    third = fail_once()
    version = third["state_version"]
    assert any(c["to"] == "CONFIRMED" for c in third["gap_status_changes"])
    v = rt.submit_step_response(conn, student, attempt_id, target, "the right idea", version)["state_version"]
    win = rt.record_step_outcome(conn, attempt_id, target, "SUCCESS", v)
    assert {"RESOLVED", "REJECTED"} & {c["to"] for c in win["gap_status_changes"]}

    rows = dx.list_student_gaps(conn, student)
    created = conn.execute(text(
        "SELECT count(*) FROM learner.event WHERE solve_attempt_id = CAST(:a AS uuid) "
        "AND event_type = 'GAP_HYPOTHESIS_CREATED'"), {"a": attempt_id}).scalar_one()
    assert len(rows) == created  # every hypothesis persisted, none deleted
    types = {e["event_type"] for e in rt.list_events(conn, student, attempt_id=attempt_id, limit=500)}
    assert {"GAP_DIAGNOSED", "GAP_HYPOTHESIS_CREATED", "GAP_HYPOTHESIS_CONFIRMED"} <= types
    assert types & {"GAP_HYPOTHESIS_RESOLVED", "GAP_HYPOTHESIS_REJECTED"}
    # a diagnosis never writes mastery
    assert conn.execute(text("SELECT count(*) FROM learner.concept_mastery WHERE student_id = :s"),
                        {"s": student}).scalar_one() == 0
