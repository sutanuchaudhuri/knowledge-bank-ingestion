"""Recovery plans (Phase 10) and the optional diagnosis re-rank.

Offline tests cover plan building, adaptation, the mastery policy, grading, redaction and route guards.
Live tests (MATHBANK_LIVE_STEP_RUNTIME_TEST=1) run inside one transaction that always rolls back.
"""
from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from mathbank_rest import step_diagnosis as dx
from mathbank_rest import step_recovery as rc
from mathbank_rest import step_runtime as rt
from mathbank_rest.main import app

client = TestClient(app)


def _cand(i, t, src="P1", skill=True):
    return {"learning_item_id": f"li-{i}", "transformation_type": t, "transformed_form": "MCQ" if t.startswith("MCQ") else "SUBPROBLEM",
            "source_problem_id": src, "skill_match": skill}


# ---------------------------------------------------------------- planning

def test_build_plan_orders_stages_and_ends_with_return():
    cands = [_cand(1, "MCQ_METHOD_RECOGNITION", "P1"), _cand(2, "MCQ_INTERMEDIATE_SKILL", "P1"),
             _cand(3, "SUBPROBLEM_NEXT_INTERMEDIATE", "P2"), _cand(4, "SUBPROBLEM_FIRST_MOVE", "P3")]
    plan = rc.build_plan(cands, "STEP-W")
    assert [p["stage"] for p in plan] == ["FOUNDATION", "RECOGNITION", "ISOLATED_EXECUTION", "GUIDED_APPLICATION",
                                          "TRANSFER", "RETURN_TO_STEP"]
    assert [p["ordinal"] for p in plan] == [1, 2, 3, 4, 5, 6]
    assert plan[0]["item_kind"] == "THEORY" and plan[0]["required"] is False
    transfer = plan[4]
    assert transfer["is_transfer"] and transfer["learning_item_id"] == "li-4"
    assert transfer["source_problem_id"] not in {p.get("source_problem_id") for p in plan[1:4]}
    assert len({p["learning_item_id"] for p in plan if p["learning_item_id"]}) == 4  # no repeats


def test_build_plan_prefers_skill_matches_and_skips_missing_stages():
    cands = [_cand(1, "MCQ_LOCAL_GOAL", skill=False), _cand(2, "MCQ_FIRST_MOVE", "P9")]
    plan = rc.build_plan(cands, None, include_return=False)
    assert plan[0]["learning_item_id"] == "li-2"  # skill-level MCQ_FIRST_MOVE beats subconcept-only LOCAL_GOAL
    assert all(p["stage"] != "RETURN_TO_STEP" for p in plan)
    assert rc.build_plan([], None, include_return=False) == []


@pytest.mark.parametrize("stage,result,tries,expected", [
    ("FOUNDATION", "SUCCESS", 1, "ADVANCE"),
    ("RECOGNITION", "SUCCESS", 1, "ADVANCE"),
    ("ISOLATED_EXECUTION", "SUCCESS", 2, "CONFIRM"),
    ("ISOLATED_EXECUTION", "FAILED", 1, "RETRY"),
    ("ISOLATED_EXECUTION", "FAILED", 2, "ALTERNATE"),
    ("RECOGNITION", "FAILED", 2, "BRANCH"),
])
def test_adapt(stage, result, tries, expected):
    assert rc.adapt(stage, result, tries) == expected


def _item(status, ind=None, transfer=False, tries=1, kind="LEARNING_ITEM"):
    return {"item_kind": kind, "status": status, "independent_success": ind, "is_transfer": transfer, "tries": tries}


def test_mastery_policy_needs_two_independent_passes_and_a_transfer():
    policy = rc.DEFAULT_POLICY
    assert not rc.mastery_status([_item("PASSED", True), _item("PASSED", True)], policy)["met"]
    assert not rc.mastery_status([_item("PASSED", True), _item("PASSED", False, transfer=True, tries=2)],
                                 policy)["met"]  # one independent pass only
    assert rc.mastery_status([_item("PASSED", True), _item("PASSED", True, transfer=True)], policy)["met"]
    # worked examples never count toward mastery
    assert not rc.mastery_status([_item("PASSED", True, kind="THEORY"), _item("PASSED", True, transfer=True)],
                                 policy)["met"]


def test_grade_mcq_by_index():
    assert rc.grade_mcq(["a", "b"], "b", 1)["result"] == "SUCCESS"
    assert rc.grade_mcq(["a", "b"], "b", 0)["result"] == "FAILED"
    assert rc.grade_mcq(["a", "b"], "b", 5)["result"] == "FAILED"
    assert rc.grade_mcq(["a", "b"], "b", None)["result"] == "FAILED"


def test_grade_item_subproblem_uses_evaluator_with_seed_as_reference():
    seen = {}

    def fake(ctx):
        seen["ctx"] = ctx
        return {"verdict": "CORRECT", "confidence": 0.95, "feedback": "Nice.", "model": "fake"}

    ctx = {"item": {"item_kind": "LEARNING_ITEM"}, "plan": {"target_label": "Similar triangles"},
           "learning_item": {"transformed_form": "SUBPROBLEM", "statement_text": "Problem text", "solution_part_label": "a",
                             "question_text": "Find the first move.", "answer_or_solution_seed": "Draw PQ."}}
    g = rc.grade_item(ctx, {"response_text": "draw a parallel"}, fake)
    assert g["result"] == "SUCCESS" and seen["ctx"].canonical_step == "Draw PQ."
    assert seen["ctx"].previous_steps == ["Find the first move."]
    with pytest.raises(rt.InvalidTransition):
        rc.grade_item(ctx, {"response_text": "  "}, fake)
    assert rc.grade_item({"item": {"item_kind": "THEORY"}}, {})["result"] == "SUCCESS"


# ---------------------------------------------------------------- optional AI re-rank

HYPS = [{"knowledge_gap_id": "g1", "rank": 1, "failure_location": "SKILL", "failure_mode": "CANNOT_EXECUTE",
         "target_label": "A", "confidence": 0.7, "status": "UNRESOLVED", "evidence": {}, "source_step_id": None},
        {"knowledge_gap_id": "g2", "rank": 2, "failure_location": "PREREQUISITE", "failure_mode": "NOT_RECOGNIZED",
         "target_label": "B", "confidence": 0.5, "status": "UNRESOLVED", "evidence": {}, "source_step_id": "S0"}]


def test_rerank_only_accepts_a_permutation():
    assert dx.validate_rerank({"order": ["g2", "g1"]}, HYPS) == ["g2", "g1"]
    assert dx.validate_rerank({"order": ["g2"]}, HYPS) is None
    assert dx.validate_rerank({"order": ["g2", "g3"]}, HYPS) is None
    assert dx.validate_rerank({"order": ["g1", "g1"]}, HYPS) is None
    assert dx.validate_rerank("nope", HYPS) is None


def test_student_view_uses_ai_order_but_keeps_rules_action_and_probe_target():
    d = {"gap_diagnosis_id": "d", "solution_step_id": "s", "trigger": "AUTO", "created_at": None,
         "recommended_action": "RECOVERY_DETOUR", "probes": [], "hypotheses": HYPS,
         "ai_rerank": {"order": ["g2", "g1"], "rationale": "teacher note"}}
    view = dx.student_view(d)
    assert [h["target_label"] for h in view["hypotheses"]] == ["B", "A"]
    assert [h["rank"] for h in view["hypotheses"]] == [1, 2]
    assert view["ranked_by"] == "AI" and view["recommended_action"] == "RECOVERY_DETOUR"
    assert view["probe_target_label"] == "A"
    assert "teacher note" not in json.dumps(view)
    assert dx.student_view({**d, "ai_rerank": {"order": ["bogus"]}})["hypotheses"][0]["target_label"] == "A"


def test_rerank_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DIAGNOSIS_LLM_RERANK", raising=False)
    assert dx.rerank_enabled() is False
    assert dx.rerank_diagnosis(object(), "d", lambda c: {"order": []}) is None


# ---------------------------------------------------------------- route guards

def _auth(student_id):
    from mathbank_rest import security

    return {"Authorization": f"Bearer {security.create_access_token(student_id)}"}


def test_recovery_routes_require_auth_and_admin_key():
    a, p, i = uuid4(), uuid4(), uuid4()
    assert client.post(f"/v1/attempts/{a}/recovery-plans", json={"state_version": 1}).status_code == 401
    assert client.get(f"/v1/attempts/{a}/recovery-plans").status_code == 401
    assert client.get(f"/v1/recovery-plans/{p}").status_code == 401
    assert client.post(f"/v1/recovery-plans/{p}/items/{i}/responses", json={"state_version": 1}).status_code == 401
    assert client.post(f"/v1/recovery-plans/{p}/resume", json={"state_version": 1}).status_code == 401
    assert client.get("/v1/admin/recovery-plans", headers=_auth(uuid4())).status_code == 401
    assert client.get("/v1/admin/knowledge-gaps", headers=_auth(uuid4())).status_code == 401


def test_item_response_is_graded_outside_the_transaction_then_applied(monkeypatch):
    calls = []

    def prepare(conn, student, plan, item, response, version, key):
        calls.append("prepare")
        return {"item": {"item_kind": "THEORY"}}

    def apply(conn, student, plan, item, response, grade, version, key):
        calls.append(("apply", grade["verdict"], response))
        return {"decision": "ADVANCE", "state_version": version + 1}

    from contextlib import nullcontext

    from mathbank_rest.routers import step_runtime as router_mod

    class FakeEngine:
        def begin(self):
            return nullcontext(None)

    monkeypatch.setattr(router_mod, "engine", FakeEngine())
    monkeypatch.setattr(rc, "prepare_item_response", prepare)
    monkeypatch.setattr(rc, "apply_item_response", apply)
    r = client.post(f"/v1/recovery-plans/{uuid4()}/items/{uuid4()}/responses",
                    json={"state_version": 3, "acknowledged": True}, headers=_auth(uuid4()))
    assert r.status_code == 200, r.text
    assert calls == ["prepare", ("apply", "ACKNOWLEDGED", {"acknowledged": True})]


# ---------------------------------------------------------------- live golden flows (rolled back)

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


def _student(conn):
    return conn.execute(text(
        "INSERT INTO learner.student_profile (email, password_hash, first_name, last_name, display_name) "
        "VALUES (:e, 'x', 'Live', 'Test', 'Live Test') RETURNING student_id"),
        {"e": f"live-{uuid4()}@example.com"}).scalar_one()


def _problem_with_practice(conn):
    """A published problem whose first step's skill has approved MCQ practice from other problems."""
    return conn.execute(text(
        "SELECT s.problem_id::text FROM pedagogy.solution_step s "
        " WHERE s.publication_status = 'PUBLISHED' AND s.global_step_index = 1 "
        "   AND (SELECT count(*) FROM pedagogy.learning_item li WHERE li.target_skill_node_id = s.skill_node_id "
        "        AND li.review_status = 'APPROVED' AND li.student_visible AND li.transformed_form = 'MCQ' "
        "        AND li.source_problem_id <> s.problem_id) >= 8 "
        " ORDER BY s.problem_id LIMIT 1")).scalar_one()


def _answer_mcq(conn, student, plan, item, correct):
    li = conn.execute(text("SELECT choices, correct_answer FROM pedagogy.learning_item li "
                           "JOIN pedagogy.recovery_plan_item ri USING (learning_item_id) "
                           "WHERE ri.recovery_plan_item_id = CAST(:i AS uuid)"),
                      {"i": item["recovery_plan_item_id"]}).one()
    idx = li.choices.index(li.correct_answer)
    return {"choice_index": idx if correct else (idx + 1) % len(li.choices)}


def _respond(conn, student, plan_id, item, version, correct=True):
    if item["item_kind"] == "THEORY":
        response = {"acknowledged": True}
    elif item["content"]["form"] == "MCQ":
        response = _answer_mcq(conn, student, plan_id, item, correct)
    else:
        response = {"response_text": "my attempt"}
    ctx = rc.prepare_item_response(conn, student, plan_id, item["recovery_plan_item_id"], response, version, None)

    def fake(sctx):
        return {"verdict": "CORRECT" if correct else "INCORRECT", "confidence": 0.95, "feedback": "ok", "model": "fake"}

    grade = rc.grade_item(ctx, response, fake)
    return rc.apply_item_response(conn, student, plan_id, item["recovery_plan_item_id"], response, grade, version)


def _current(view):
    return next(i for i in view["items"] if i["ordinal"] == view["current_item_ordinal"])


@live
def test_live_recovery_completes_and_returns_to_exact_step(live_conn):
    conn = live_conn
    student = _student(conn)
    started = rt.start_attempt(conn, student, _problem_with_practice(conn))
    attempt_id = started["solve_attempt_id"]
    runtime = rt.get_runtime(conn, attempt_id, student)
    origin, version = runtime["current_step"]["solution_step_id"], runtime["attempt"]["state_version"]

    created = rc.create_plan(conn, student, attempt_id, version)
    plan = created["recovery_plan"]
    version = created["state_version"]
    assert plan["status"] == "ACTIVE" and plan["origin"]["solution_step_id"] == origin
    assert plan["items"][-1]["stage"] == "RETURN_TO_STEP"
    origin_problem = conn.execute(text("SELECT problem_id::text FROM learner.solve_attempt "
                                       "WHERE solve_attempt_id = CAST(:a AS uuid)"), {"a": attempt_id}).scalar_one()
    used_sources = conn.execute(text(
        "SELECT li.source_problem_id::text FROM pedagogy.recovery_plan_item ri JOIN pedagogy.learning_item li "
        "USING (learning_item_id) WHERE ri.recovery_plan_id = CAST(:r AS uuid)"),
        {"r": plan["recovery_plan_id"]}).scalars().all()
    assert used_sources and origin_problem not in used_sources  # never the problem being solved
    # the step runtime is blocked while detoured, and the answer is hidden until finished
    with pytest.raises(rt.InvalidTransition):
        rt.request_hint(conn, student, attempt_id, origin, version)
    rt_view = rt.get_runtime(conn, attempt_id, student)
    assert rt_view["recovery"]["recovery_plan_id"] == plan["recovery_plan_id"]
    assert rt_view["attempt"]["current_mode"] == "RECOVERY"
    assert all("answer" not in (i.get("content") or {}) for i in plan["items"] if i["status"] == "PRESENTED")
    # resuming the same detour returns it instead of creating another
    assert rc.create_plan(conn, student, attempt_id, version)["resumed"] is True
    with pytest.raises(rt.InvalidTransition):
        rc.leave_recovery(conn, student, plan["recovery_plan_id"], version)  # must finish or abort

    for _ in range(20):
        if plan["status"] != "ACTIVE":
            break
        out = _respond(conn, student, plan["recovery_plan_id"], _current(plan), version, correct=True)
        plan, version = out["recovery_plan"], out["state_version"]
    assert plan["status"] == "COMPLETED" and plan["mastery"]["met"] and plan["can_return"]
    finished = [i for i in plan["items"] if i["status"] == "PASSED" and i["item_kind"] == "LEARNING_ITEM"]
    assert finished and all("answer" in i["content"] for i in finished)

    back = rc.leave_recovery(conn, student, plan["recovery_plan_id"], version)
    assert back["returned_to_step_id"] == origin
    runtime = rt.get_runtime(conn, attempt_id, student)
    assert runtime["current_step"]["solution_step_id"] == origin and runtime["recovery"] is None
    assert runtime["attempt"]["current_mode"] == "SOLVING"
    state = conn.execute(text("SELECT state FROM learner.attempt_step_state WHERE solve_attempt_id = CAST(:a AS uuid) "
                              "AND solution_step_id = :s"), {"a": attempt_id, "s": origin}).scalar_one()
    assert state == "PRESENTED"
    types = [e["event_type"] for e in rt.list_events(conn, student, attempt_id=attempt_id, limit=500)]
    assert {"RECOVERY_PLAN_CREATED", "RECOVERY_ITEM_PRESENTED", "RECOVERY_ITEM_SUBMITTED", "RECOVERY_ITEM_EVALUATED",
            "RECOVERY_PLAN_COMPLETED", "RETURNED_TO_ORIGINAL_STEP"} <= set(types)
    # recovery never writes mastery
    assert conn.execute(text("SELECT count(*) FROM learner.concept_mastery WHERE student_id = :s"),
                        {"s": student}).scalar_one() == 0
    # the step runtime works again
    rt.request_hint(conn, student, attempt_id, origin, runtime["attempt"]["state_version"])


@live
def test_live_recovery_adapts_on_failure_and_abort_returns(live_conn):
    conn = live_conn
    student = _student(conn)
    attempt_id = rt.start_attempt(conn, student, _problem_with_practice(conn))["solve_attempt_id"]
    runtime = rt.get_runtime(conn, attempt_id, student)
    origin = runtime["current_step"]["solution_step_id"]
    created = rc.create_plan(conn, student, attempt_id, runtime["attempt"]["state_version"])
    plan, version = created["recovery_plan"], created["state_version"]
    if _current(plan)["item_kind"] == "THEORY":
        out = _respond(conn, student, plan["recovery_plan_id"], _current(plan), version)
        plan, version = out["recovery_plan"], out["state_version"]
    item = _current(plan)
    before = len(plan["items"])
    first = _respond(conn, student, plan["recovery_plan_id"], item, version, correct=False)
    assert first["decision"] == "RETRY" and first["recovery_plan"]["current_item_ordinal"] == item["ordinal"]
    assert "answer" not in (_current(first["recovery_plan"])["content"] or {})
    with pytest.raises(rt.StateVersionConflict):  # stale version
        _respond(conn, student, plan["recovery_plan_id"], item, version, correct=True)
    second = _respond(conn, student, plan["recovery_plan_id"], item, first["state_version"], correct=False)
    assert second["decision"] in ("ALTERNATE", "BRANCH")
    active = second["recovery_plan"]
    if second.get("transition") != "BRANCHED":
        assert len(active["items"]) == before + 1
        assert any(i["added_reason"] == "ALTERNATE_AFTER_FAILURE" for i in active["items"])
    failed = next(i for i in conn.execute(text(
        "SELECT status FROM pedagogy.recovery_plan_item WHERE recovery_plan_item_id = CAST(:i AS uuid)"),
        {"i": item["recovery_plan_item_id"]}).scalars())
    assert failed == "FAILED"
    back = rc.leave_recovery(conn, student, active["recovery_plan_id"], second["state_version"], abort=True)
    assert back["returned_to_step_id"] == origin and back["plan_status"] == "ABORTED"
    open_items = conn.execute(text(
        "SELECT count(*) FROM pedagogy.recovery_plan_item ri JOIN pedagogy.recovery_plan rp USING (recovery_plan_id) "
        "WHERE rp.solve_attempt_id = CAST(:a AS uuid) AND ri.status IN ('PENDING', 'PRESENTED')"),
        {"a": attempt_id}).scalar_one()
    assert open_items == 0
    assert rt.get_runtime(conn, attempt_id, student)["attempt"]["current_mode"] == "SOLVING"
    assert rc.admin_plans(conn, student_id=student)[0]["status"] == "ABORTED"
    overview = dx.admin_gap_overview(conn, student=str(student))
    assert overview["gaps"] == [] and isinstance(overview["totals"], dict)


@live
def test_live_diagnosis_detour_with_learning_item_probes_and_gap_outcome(live_conn):
    conn = live_conn
    student = _student(conn)
    target, pred, problem = conn.execute(text(
        "SELECT b.solution_step_id, a.solution_step_id, b.problem_id::text "
        "  FROM pedagogy.solution_step_dependency d "
        "  JOIN pedagogy.solution_step a ON a.solution_step_id = d.from_step_id "
        "  JOIN pedagogy.solution_step b ON b.solution_step_id = d.to_step_id "
        " WHERE d.relationship_type = 'DEPENDS_ON' AND d.review_status <> 'REJECTED' "
        "   AND a.skill_node_id <> b.skill_node_id AND b.publication_status = 'PUBLISHED' "
        "   AND a.problem_id = b.problem_id "
        "   AND EXISTS (SELECT 1 FROM pedagogy.learning_item li WHERE li.target_skill_node_id = b.skill_node_id "
        "               AND li.review_status = 'APPROVED' AND li.source_problem_id <> b.problem_id) "
        " ORDER BY b.solution_step_id LIMIT 1")).one()
    attempt_id = rt.start_attempt(conn, student, problem)["solve_attempt_id"]
    runtime = rt.get_runtime(conn, attempt_id, student)
    current, version = runtime["current_step"]["solution_step_id"], runtime["attempt"]["state_version"]
    while current != target:
        out = rt.record_step_outcome(conn, attempt_id, current, "SUCCESS", version)
        current, version = out["current_step_id"], out["state_version"]
    for _ in range(2):
        v = rt.submit_step_response(conn, student, attempt_id, target, "a wrong idea", version)["state_version"]
        out = rt.record_step_outcome(conn, attempt_id, target, "FAILED", v,
                                     evaluation={"failure_mode": "CANNOT_EXECUTE", "failure_location": "SKILL"})
        version = out["state_version"]
    d = out["diagnosis"]
    assert d and d["probe_target_label"] and all(h.get("knowledge_gap_id") for h in d["hypotheses"])
    li_probes = [p for p in d["probes"] if p["kind"] == "LEARNING_ITEM"]
    assert li_probes, "approved learning items should come first as probes"
    assert d["probes"][0]["kind"] == "LEARNING_ITEM"
    assert all(p.get("problem_code") != runtime["attempt"]["problem_code"] for p in li_probes)

    with pytest.raises(rt.InvalidTransition):
        rc.create_plan(conn, student, attempt_id, version, trigger="DIAGNOSIS")  # needs the diagnosis id
    with pytest.raises(rt.NotFound):
        rc.create_plan(conn, uuid4(), attempt_id, version)  # another student's attempt
    created = rc.create_plan(conn, student, attempt_id, version, trigger="DIAGNOSIS",
                             gap_diagnosis_id=d["gap_diagnosis_id"], idempotency_key="k-create")
    again = rc.create_plan(conn, student, attempt_id, version, trigger="DIAGNOSIS",
                           gap_diagnosis_id=d["gap_diagnosis_id"], idempotency_key="k-create")
    assert again["recovery_plan"]["recovery_plan_id"] == created["recovery_plan"]["recovery_plan_id"]
    root_id = created["recovery_plan"]["recovery_plan_id"]
    state = conn.execute(text("SELECT state FROM learner.attempt_step_state WHERE solve_attempt_id = CAST(:a AS uuid) "
                              "AND solution_step_id = :s"), {"a": attempt_id, "s": target}).scalar_one()
    assert state == "DETOURED"
    with pytest.raises(rt.InvalidTransition):
        rt.submit_step_response(conn, student, attempt_id, target, "x", created["state_version"])

    plan, version, failed_once = created["recovery_plan"], created["state_version"], False
    for _ in range(30):
        if plan["status"] != "ACTIVE":
            break
        item = _current(plan)
        wrong = not failed_once and item["item_kind"] == "LEARNING_ITEM"
        out = _respond(conn, student, plan["recovery_plan_id"], item, version, correct=not wrong)
        if wrong:  # fail the first practice item twice: alternate item or prerequisite branch
            out = _respond(conn, student, plan["recovery_plan_id"], item, out["state_version"], correct=False)
            assert out["decision"] in ("ALTERNATE", "BRANCH")
            failed_once = True
        plan, version = out["recovery_plan"], out["state_version"]
    assert plan["recovery_plan_id"] == root_id and plan["status"] in ("COMPLETED", "EXHAUSTED")
    gap = conn.execute(text("SELECT kg.status FROM pedagogy.recovery_plan rp JOIN pedagogy.knowledge_gap kg "
                            "USING (knowledge_gap_id) WHERE rp.recovery_plan_id = CAST(:r AS uuid)"),
                       {"r": root_id}).scalar_one()
    assert gap == ("RESOLVED" if plan["status"] == "COMPLETED" else "CONFIRMED")
    back = rc.leave_recovery(conn, student, root_id, version, idempotency_key="k-back")
    assert back["returned_to_step_id"] == target
    replay = rc.leave_recovery(conn, student, root_id, version, idempotency_key="k-back")
    assert replay.pop("replayed") is True and replay == {k: v for k, v in back.items() if k != "replayed"}
    assert rt.get_runtime(conn, attempt_id, student)["current_step"]["state"] == "RETRY_PRESENTED"
    teacher = rc.admin_plan_detail(conn, root_id)
    assert teacher["knowledge_gap_id"] and any(i["last_result"] for i in teacher["items_teacher"])
    overview = dx.admin_gap_overview(conn, student=str(student))
    assert overview["gaps"] and overview["totals"]


@live
def test_live_cross_reference_stubs_are_never_recovery_material(live_conn):
    """Text like "similar to heading a)" is not self-contained: excluded from items, examples and probes."""
    stub_skill = live_conn.execute(text(
        "SELECT target_skill_node_id FROM pedagogy.learning_item "
        " WHERE review_status = 'APPROVED' AND student_visible AND no_proof AND target_skill_node_id IS NOT NULL "
        "   AND answer_or_solution_seed ~* :re GROUP BY 1 ORDER BY count(*) DESC LIMIT 1"),
        {"re": rt.CROSS_REFERENCE_STUB_RE}).scalar()
    assert stub_skill, "corpus has no stub-seeded items to check"
    student = str(_student(live_conn))
    origin = "00000000-0000-0000-0000-000000000000"
    ids = [c["learning_item_id"] for c in rc._candidates(live_conn, student, origin, stub_skill, None)]
    assert ids
    leaked = live_conn.execute(text(
        "SELECT count(*) FROM pedagogy.learning_item WHERE learning_item_id::text = ANY(CAST(:ids AS text[])) "
        "   AND (coalesce(answer_or_solution_seed, '') ~* :re OR coalesce(correct_answer, '') ~* :re)"),
        {"ids": ids, "re": rt.CROSS_REFERENCE_STUB_RE}).scalar()
    assert leaked == 0
    example = rc._worked_example(live_conn, student, origin, stub_skill)
    if example:
        assert not live_conn.execute(text("SELECT step_text ~* :re FROM pedagogy.solution_step WHERE solution_step_id = :s"),
                                     {"re": rt.CROSS_REFERENCE_STUB_RE, "s": example}).scalar()
    probes = dx.find_probes(live_conn, student, origin, stub_skill, None, limit=10)
    probe_items = [p["learning_item_id"] for p in probes if p["kind"] == "LEARNING_ITEM"]
    if probe_items:
        assert live_conn.execute(text(
            "SELECT count(*) FROM pedagogy.learning_item WHERE learning_item_id::text = ANY(CAST(:ids AS text[])) "
            "   AND coalesce(answer_or_solution_seed, '') ~* :re"), {"ids": probe_items, "re": rt.CROSS_REFERENCE_STUB_RE}).scalar() == 0


def test_provenance_descriptions_are_hidden_from_students():
    from mathbank_rest.step_recovery import _student_description

    assert _student_description("Skill inferred from ordered solution steps.") is None
    assert _student_description(None) is None
    assert _student_description("Use equal tangents from an external point.") == (
        "Use equal tangents from an external point.")
