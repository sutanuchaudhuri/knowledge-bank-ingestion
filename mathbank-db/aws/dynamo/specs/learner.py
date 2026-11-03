"""C1 Learner runtime → `mb-learner-<env>` (design: 70_DYNAMODB_AND_S3_VECTORS_ADOPTION_PLAN.md §13 C1).

Every learner-owned item lives under PK = STUDENT#<student_id>. Global partitions: uniqueness sentinels
(UNIQUE#…), owner pointers (<KIND>#<id>/OWNER), COHORT#CONCEPT and RETRIEVAL_EXCLUSION#<node>.
Folded 1:1 tables: tutor.runtime_state → SOLVE, tutor.micro_course_runtime → ENROLL,
pedagogy.recovery_plan_item → PLAN.items[]. Their own mappings only verify the fold (row count +
parent present) and emit nothing.
"""
from __future__ import annotations

import hashlib

from ..spec import Mapping, Table, iso, s, ttl_after

T = "learner"

# DynamoDB caps INCLUDE at 20 non-key attributes (incl. `type`). Dropped vs design §3: email_lc, started_at,
# last_updated_at (already encoded in GSI2SK: `<email_lc>#<sid>`, `<started_at>#<aid>`,
# `<last_updated_at>#<aid>#<step>`) and cognito_sub (A5 admin directory needs a GetItem PROFILE to show it).
GSI2_INCLUDE = (
    "student_id", "email", "first_name", "last_name", "display_name", "status", "created_at", "is_anonymous",
    "search_blob", "problem_id", "attempt_number", "current_mode", "solve_attempt_id", "solution_step_id",
    "state", "help_level_used", "attempt_count", "independent_success",
)

TABLES = [
    Table(
        T,
        gsis=("GSI1", "GSI2"),
        stream=True,
        ttl=True,
        # GSI1 ALL (design). GSI2 INCLUDE per design §3; never password_hash, last_response_text or
        # last_evaluation (`type` is added by provision).
        include_gsis=(("GSI2", GSI2_INCLUDE),),
        description="C1 learner runtime: profiles, outcomes/mastery, solve runtime, diagnoses, "
                    "recovery plans, micro-course/route runtime, feedback, agent links, daily activity",
    )
]

IDEM_TTL_DAYS = 7
OUTCOME_SOURCES = {"web", "agent_chat", "import", "step_runtime", "multimodal_approved", "quiz"}
PROFILE_STATUSES = {"ACTIVE", "DISABLED", "ERASING"}
MISCONCEPTION_CONFIRMATION_THRESHOLD = 0.80          # interaction_runtime.CONFIRMATION_THRESHOLD
MASTERY_FORMULA_VERSION = 1                          # mastery.py: HL 45 d, difficulty weight, hint penalty

# Engine S3 offload policy (one mechanism): each listed attribute > MB_OFFLOAD_THRESHOLD (16 KiB) goes to
# s3://mathbank-data-<env>-<account>/offload/learner/students/<sid>/… and is replaced by <attr>_ref.
# None of these attributes is a key or GSI2-projected. PLAN.items[] stays inline (it is the CAS-updated
# runtime list; nested last_response/last_result are covered by the engine's 350 KB safety net).
OFFLOAD = {
    (T, "OUTCOME"): ("submitted_answer",),                                   # student answer text
    (T, "STEPSTATE"): ("last_response_text", "last_evaluation", "evidence"),  # response + grader output/evidence
    (T, "EVENT"): ("payload",),                                              # carries responses/evaluations
    (T, "IDEM"): ("response",),                                              # replayed API response bodies
    (T, "SOLVE"): ("metadata",),
    (T, "DIAG"): ("evidence", "probes", "ai_rerank"),                        # diagnoser/model output + evidence
    (T, "GAP"): ("evidence",),
    (T, "PLAN"): ("mastery_policy", "outcome"),
    (T, "ENROLL"): ("last_responses",),                                      # latest learner responses per item
    (T, "MCEVENT"): ("payload",),                                            # quiz/activity responses
    (T, "IXEVENT"): ("before_state", "action_payload", "after_state"),       # interaction payloads
    (T, "FEEDBACK"): ("audit_snapshot", "review_note"),                      # feedback text + retrieval audit
    (T, "AGENTLINK"): ("context",),                                          # ADK session context
}

# mastery.normalized_difficulty keyword table (kept identical so MEVID weights match the PG formula)
_DIFFICULTY_KEYWORDS = [("entry", 0.15), ("easy", 0.2), ("early", 0.25), ("medium", 0.5), ("mid", 0.5),
                        ("late", 0.75), ("hard", 0.85), ("difficult", 0.85), ("challenge", 0.95)]


def _ts(col: str) -> str:
    """SQL: timestamptz → ISO-8601 UTC µs 'Z' text (same format as the engine), for json_agg payloads."""
    return f"""to_char({col} AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')"""


def _difficulty_weight(band: str | None) -> float:
    norm = 0.5
    if band:
        low = band.lower()
        for kw, val in _DIFFICULTY_KEYWORDS:
            if kw in low:
                norm = val
                break
    return 1.0 + 0.5 * norm


def _stu(sid) -> str:
    return f"STUDENT#{sid}"


# ======================================================================== PROFILE + sentinels

def _profile(r: dict):
    sid = r["student_id"]
    email_lc = r["email"].strip().lower()
    pw = r["password_hash"]
    if not pw.startswith("$2"):
        pw = "!COGNITO"                       # non-bcrypt (random hex of Cognito rows) → literal marker
    status = r["status"] if r["status"] in PROFILE_STATUSES else "DISABLED"
    blob = " ".join(x.strip().lower() for x in (email_lc, r["first_name"], r["last_name"], r["display_name"])
                    if x and x.strip())
    yield {
        "PK": _stu(sid), "SK": "PROFILE", "type": "PROFILE",
        "GSI2PK": "STUDENT_DIR", "GSI2SK": f"{email_lc}#{sid}",
        "student_id": sid, "email": r["email"], "email_lc": email_lc, "password_hash": pw,
        "first_name": r["first_name"], "last_name": r["last_name"], "display_name": r["display_name"],
        "status": status, "token_version": 0, "cognito_sub": r["cognito_sub"], "grade": r["grade"],
        "phone": r["phone"], "is_anonymous": r["is_anonymous"], "created_at": r["created_at"],
        "last_login_at": r["last_login_at"], "search_blob": blob, "version": 1,
    }
    yield {"PK": f"UNIQUE#email#{email_lc}", "SK": "UNIQUE", "type": "UNIQUE_EMAIL", "student_id": sid}
    if r["cognito_sub"]:
        yield {"PK": f"UNIQUE#cognito_sub#{r['cognito_sub']}", "SK": "UNIQUE", "type": "UNIQUE_COGNITO_SUB",
               "student_id": sid}


# ======================================================================== OUTCOME + MEVID

def _mevid(sid, kind: str, tag_id, at, src_kind: str, src_id, is_correct, hint_count, band, problem_id=None,
           extra: dict | None = None) -> dict:
    return {
        "PK": _stu(sid), "SK": f"MEVID#{kind}#{tag_id}#{iso(at)}#{src_kind}#{src_id}", "type": "MEVID",
        "student_id": sid, "tag_kind": kind, "tag_id": tag_id, "is_correct": is_correct,
        "hint_count": hint_count, "difficulty_band": band, "difficulty_weight": _difficulty_weight(band),
        "attempted_at": at, "src_kind": src_kind, "src_id": src_id, "problem_id": problem_id, **(extra or {}),
    }


def _attempt(r: dict):
    sid, aid = r["student_id"], r["attempt_id"]
    src = r["source"]
    yield {
        "PK": _stu(sid), "SK": f"OUTCOME#{iso(r['attempted_at'])}#{aid}", "type": "OUTCOME",
        "student_id": sid, "attempt_id": aid, "problem_id": r["problem_id"], "is_correct": r["is_correct"],
        "submitted_answer": r["submitted_answer"], "time_spent_seconds": r["time_spent_seconds"],
        "hint_count": r["hint_count"], "attempted_at": r["attempted_at"],
        "source": src if src in OUTCOME_SOURCES else "import",
        "legacy_source": None if src in OUTCOME_SOURCES else src,
        "solve_attempt_id": r["solve_attempt_id"],
    }
    if r["is_correct"] is None:
        return
    for kind, ids in (("C", r["concept_ids"]), ("T", r["technique_ids"])):
        for tag in ids or ():
            yield _mevid(sid, kind, tag, r["attempted_at"], "OUT", aid, r["is_correct"], r["hint_count"],
                         r["difficulty_band"], r["problem_id"])


def _quiz_response(r: dict):
    if r["is_correct"] is None:
        return
    for kind, ids in (("C", r["concept_ids"]), ("T", r["technique_ids"])):
        for tag in ids or ():
            yield _mevid(r["student_id"], kind, tag, r["submitted_at"], "QZ", r["response_id"], r["is_correct"],
                         0, r["difficulty_band"], None,
                         {"quiz_id": r["quiz_id"], "question_id": r["question_id"]})


def _mevid_dedupe_check(r: dict):
    """One row per graded-attempt evidence row dropped because knowledge.problem_concept/problem_technique
    holds the same (problem, tag) twice (role 'PRIMARY' vs 'primary'). PG mastery counts these twice; the
    MEVID fan-out counts each tag once. Emits no items: the manifest's source_rows is the parity gap."""
    return ()


def _problem_cursor(r: dict):
    yield {
        "PK": _stu(r["student_id"]), "SK": f"PROBLEM#{r['problem_id']}", "type": "PROBLEM",
        "student_id": r["student_id"], "problem_id": r["problem_id"], "attempt_seq": r["attempt_seq"],
        "open_solve_attempt_id": r["open_solve_attempt_id"], "first_attempted_at": r["first_attempted_at"],
        "outcome_count": r["outcome_count"],
    }


# ======================================================================== MASTERY + COHORT

def _mastery(kind: str, col: str):
    def fn(r: dict):
        sid, tag = r["student_id"], r[col]
        yield {
            "PK": _stu(sid), "SK": f"MASTERY#{kind}#{tag}", "type": "MASTERY", "student_id": sid,
            "tag_kind": kind, "tag_id": tag, col: tag, "mastery_score": r["mastery_score"],
            "attempts_count": r["attempts_count"], "correct_count": r["correct_count"],
            "last_attempt_at": r["last_attempt_at"], "updated_at": r["updated_at"],
            "formula_version": MASTERY_FORMULA_VERSION, "version": 1,
        }
    return fn


def _cohort(r: dict):
    yield {"PK": "COHORT#CONCEPT", "SK": str(r["concept_id"]), "type": "COHORT", "concept_id": r["concept_id"],
           "sum_score": r["sum_score"], "n_students": r["n_students"], "updated_at": r["updated_at"]}


# ======================================================================== SOLVE (+ runtime_state) / STEPSTATE / EVENT

def _shard(aid) -> int:
    return int(hashlib.sha256(str(aid).encode()).hexdigest(), 16) % 4


def _solve(r: dict):
    sid, aid = r["student_id"], r["solve_attempt_id"]
    status = r["status"]
    mode = "ABANDONED" if status == "ABANDONED" else r["current_mode"]
    if mode == "DIAGNOSING":                  # removed from the enum (TUT-S04)
        mode = "SOLVING"
    open_ = status == "IN_PROGRESS"
    yield {
        "PK": _stu(sid), "SK": f"SOLVE#{aid}", "type": "SOLVE",
        "GSI1PK": f"OPEN_SOLVE#{_shard(aid)}" if open_ else None,
        "GSI1SK": f"{iso(r['last_activity_at'])}#{aid}" if open_ else None,
        "GSI2PK": f"STUDENT#{sid}#SOLVES", "GSI2SK": f"{iso(r['started_at'])}#{aid}",
        "student_id": sid, "solve_attempt_id": aid, "problem_id": r["problem_id"],
        "attempt_number": r["attempt_number"], "status": status, "current_mode": mode,
        "current_solution_part_id": r["current_solution_part_id"],
        "current_solution_step_id": r["current_solution_step_id"] or r["current_step_id"],
        "current_recovery_plan_id": r["current_recovery_plan_id"], "recovery_plan_id": r["recovery_plan_id"],
        "plan_ids": r["plan_ids"] or [], "outcome_attempt_id": r["outcome_attempt_id"],
        "hint_requested_count": r["hint_requested_count"], "last_activity_at": r["last_activity_at"],
        "started_at": r["started_at"], "submitted_at": r["submitted_at"], "completed_at": r["completed_at"],
        "updated_at": r["runtime_updated_at"], "metadata": r["metadata"],
        "version": r["state_version"] if r["state_version"] is not None else 1,
    }
    yield {"PK": f"SOLVE#{aid}", "SK": "OWNER", "type": "SOLVE_OWNER", "student_id": sid,
           "problem_id": r["problem_id"]}


def _runtime_state_fold(r: dict):
    if r["parent_student_id"] is None or r["parent_student_id"] != r["student_id"] \
            or r["parent_problem_id"] != r["current_problem_id"]:
        raise ValueError(f"tutor.runtime_state {r['solve_attempt_id']}: no matching learner.solve_attempt")
    return ()


def _stepstate(r: dict):
    sid, aid, step = r["student_id"], r["solve_attempt_id"], r["solution_step_id"]
    item = {
        "PK": _stu(sid), "SK": f"SOLVE#{aid}#STEP#{step}", "type": "STEPSTATE",
        "GSI2PK": f"STUDENT#{sid}#SKILL#{r['skill_node_id']}" if r["skill_node_id"] else None,
        "GSI2SK": f"{iso(r['last_updated_at'])}#{aid}#{step}" if r["skill_node_id"] else None,
        "student_id": sid, "solve_attempt_id": aid, "problem_id": r["problem_id"], "solution_step_id": step,
        "state": r["state"], "first_seen_at": r["first_seen_at"], "first_attempted_at": r["first_attempted_at"],
        "last_updated_at": r["last_updated_at"], "independent_success": r["independent_success"],
        "help_level_used": r["help_level_used"], "attempt_count": r["attempt_count"],
        "last_response_text": r["last_response_text"], "last_evaluation": r["last_evaluation"],
        "evidence": r["evidence"], "skill_node_id": r["skill_node_id"],
        "subconcept_node_id": r["subconcept_node_id"], "returned_to_step_count": r["returned_to_step_count"],
        "returned_to_problem_count": r["returned_to_problem_count"], "version": 1,
    }
    return [item]


def _event(r: dict):
    sid, eid, aid = r["student_id"], r["event_id"], r["solve_attempt_id"]
    sk = f"EVT#{iso(r['event_time'])}#{eid}"
    yield {
        "PK": _stu(sid), "SK": sk, "type": "EVENT",
        "GSI1PK": f"SOLVE#{aid}" if aid else None, "GSI1SK": sk if aid else None,
        "student_id": sid, "event_id": eid, "solve_attempt_id": aid, "event_type": r["event_type"],
        "event_time": r["event_time"], "actor_type": r["actor_type"], "solution_step_id": r["solution_step_id"],
        "payload": r["payload"], "idempotency_key": r["idempotency_key"],
    }


def _idem(r: dict):
    sid, key = r["student_id"], r["idempotency_key"]
    item = {
        "PK": _stu(sid), "SK": f"IDEM#{key}", "type": "IDEM", "student_id": sid, "idempotency_key": key,
        "operation": r["operation"], "request_hash": r["request_hash"], "response": r["response"],
        "created_at": r["created_at"], "ttl": ttl_after(r["created_at"], IDEM_TTL_DAYS),
    }
    return [item]


# ======================================================================== DIAG / GAP / PLAN

def _diag(r: dict):
    sid, did, aid = r["student_id"], r["gap_diagnosis_id"], r["solve_attempt_id"]
    sk = f"SOLVE#{aid}#DIAG#{iso(r['created_at'])}#{did}"
    yield {
        "PK": _stu(sid), "SK": sk, "type": "DIAG", "student_id": sid, "gap_diagnosis_id": did,
        "solve_attempt_id": aid, "solution_step_id": r["solution_step_id"], "trigger": r["trigger"],
        "recommended_action": r["recommended_action"], "evidence_fingerprint": r["evidence_fingerprint"],
        "evidence": r["evidence"], "probes": r["probes"], "diagnoser_version": r["diagnoser_version"],
        "created_at": r["created_at"], "ai_rerank": r["ai_rerank"],
    }
    yield {"PK": _stu(sid), "SK": f"UNIQUE#diag_fp#{aid}#{r['solution_step_id']}#{r['evidence_fingerprint']}",
           "type": "UNIQUE_DIAG_FP", "student_id": sid, "gap_diagnosis_id": did, "diag_sk": sk}


def _gap(r: dict):
    sid, gid = r["student_id"], r["knowledge_gap_id"]
    yield {
        "PK": _stu(sid), "SK": f"GAP#{gid}", "type": "GAP",
        "GSI1PK": f"GAPSTATUS#{r['status']}", "GSI1SK": f"{iso(r['created_at'])}#{gid}",
        "student_id": sid, "knowledge_gap_id": gid, "gap_diagnosis_id": r["gap_diagnosis_id"],
        "solve_attempt_id": r["solve_attempt_id"], "solution_step_id": r["solution_step_id"], "rank": r["rank"],
        "failure_location": r["failure_location"], "failure_mode": r["failure_mode"],
        "target_concept_id": r["target_concept_id"], "target_subconcept_id": r["target_subconcept_id"],
        "target_skill_id": r["target_skill_id"], "target_skill_node_id": r["target_skill_node_id"],
        "target_label": r["target_label"], "source_step_id": r["source_step_id"], "confidence": r["confidence"],
        "evidence": r["evidence"], "status": r["status"], "status_reason": r["status_reason"],
        "created_at": r["created_at"], "status_changed_at": r["status_changed_at"],
        "resolved_at": r["resolved_at"], "latest_plan_id": r["latest_plan_id"],
        "latest_plan_status": r["latest_plan_status"], "version": 1,
    }


def _plan(r: dict):
    sid, pid = r["student_id"], r["recovery_plan_id"]
    items = r["items"] or []
    item = {
        "PK": _stu(sid), "SK": f"PLAN#{pid}", "type": "PLAN",
        "GSI1PK": f"PLANSTATUS#{r['status']}", "GSI1SK": f"{iso(r['created_at'])}#{pid}",
        "student_id": sid, "recovery_plan_id": pid, "solve_attempt_id": r["solve_attempt_id"],
        "origin_problem_id": r["origin_problem_id"], "origin_step_id": r["origin_step_id"],
        "gap_diagnosis_id": r["gap_diagnosis_id"], "knowledge_gap_id": r["knowledge_gap_id"],
        "parent_recovery_plan_id": r["parent_recovery_plan_id"], "trigger": r["trigger"],
        "target_skill_id": r["target_skill_id"], "target_subconcept_id": r["target_subconcept_id"],
        "target_label": r["target_label"], "status": r["status"],
        "current_item_ordinal": r["current_item_ordinal"], "mastery_policy": r["mastery_policy"],
        "outcome": r["outcome"], "planner_version": r["planner_version"], "created_at": r["created_at"],
        "updated_at": r["updated_at"], "ended_at": r["ended_at"], "items": items, "version": 1,
    }
    yield item
    yield {"PK": f"PLAN#{pid}", "SK": "OWNER", "type": "PLAN_OWNER", "student_id": sid}


def _plan_item_fold(r: dict):
    if r["plan_exists"] is not True:
        raise ValueError(f"recovery_plan_item {r['recovery_plan_item_id']}: plan missing")
    return ()


# ======================================================================== ENROLL / MCEVENT / IXEVENT / MISC

def _enroll(r: dict):
    sid, eid = r["student_id"], r["enrollment_id"]
    yield {
        "PK": _stu(sid), "SK": f"ENROLL#{eid}", "type": "ENROLL",
        "GSI1PK": f"MC_RELEASE#{r['release_id']}",
        "GSI1SK": f"{r['status']}#{iso(r['started_at'])}#{eid}",
        "student_id": sid, "enrollment_id": eid, "micro_course_id": r["micro_course_id"],
        "canonical_code": r["canonical_code"], "release_id": r["release_id"], "status": r["status"],
        "current_state_id": r["current_state_id"], "last_responses": r["last_responses"] or {},
        "started_at": r["started_at"], "completed_at": r["completed_at"], "updated_at": r["runtime_updated_at"],
        "version": r["state_version"] if r["state_version"] is not None else 1,
    }
    yield {"PK": f"ENROLL#{eid}", "SK": "OWNER", "type": "ENROLL_OWNER", "student_id": sid}
    if r["holds_open_sentinel"]:
        yield {"PK": _stu(sid), "SK": f"UNIQUE#open_enroll#{r['micro_course_id']}", "type": "UNIQUE_OPEN_ENROLL",
               "student_id": sid, "enrollment_id": eid}


def _course_runtime_fold(r: dict):
    if r["parent_exists"] is not True:
        raise ValueError(f"tutor.micro_course_runtime {r['enrollment_id']}: enrollment missing")
    return ()


def _mcevent(r: dict):
    sid, eid, evid = r["student_id"], r["enrollment_id"], r["event_id"]
    yield {
        "PK": _stu(sid), "SK": f"ENROLL#{eid}#EVT#{iso(r['created_at'])}#{evid}", "type": "MCEVENT",
        "GSI1PK": f"MC_RELEASE#{r['release_id']}#EVT", "GSI1SK": f"{iso(r['created_at'])}#{evid}",
        "student_id": sid, "enrollment_id": eid, "event_id": evid, "release_id": r["release_id"],
        "state_id": r["state_id"], "event_type": r["event_type"],
        "actor_type": "ADMIN" if r["event_type"] == "RESET" else "STUDENT",
        "payload": r["payload"], "created_at": r["created_at"],
    }


def _ixevent(r: dict):
    sid, ix = r["student_id"], r["interaction_event_id"]
    eid = r["enrollment_id"] or "NONE"
    item = {
        "PK": _stu(sid),
        "SK": f"ENROLL#{eid}#IX#{r['interaction_instance_id']}#{iso(r['created_at'])}#{ix}",
        "type": "IXEVENT", "student_id": sid, "interaction_event_id": ix, "enrollment_id": r["enrollment_id"],
        "course_state_id": r["course_state_id"], "interaction_instance_id": r["interaction_instance_id"],
        "event_type": r["event_type"], "semantic_action": r["semantic_action"], "control_key": r["control_key"],
        "object_id": r["object_id"], "before_state": r["before_state"], "action_payload": r["action_payload"],
        "after_state": r["after_state"], "evaluation_outcome": r["evaluation_outcome"],
        "error_signature": r["error_signature"], "created_at": r["created_at"],
    }
    return [item]


def _misc_evidence(r: dict):
    sid = r["student_id"]
    yield {
        "PK": _stu(sid), "SK": f"MISC#{r['misconception_id']}#{iso(r['created_at'])}#{r['evidence_id']}",
        "type": "MISCEVID", "student_id": sid, "evidence_id": r["evidence_id"],
        "misconception_id": r["misconception_id"], "interaction_event_id": r["interaction_event_id"],
        "evidence_type": r["evidence_type"], "evidence_weight": r["evidence_weight"],
        "confidence_before": r["confidence_before"], "confidence_after": r["confidence_after"],
        "created_at": r["created_at"],
    }


def _misc_state(r: dict):
    sid, conf = r["student_id"], r["confidence_after"]
    yield {
        "PK": _stu(sid), "SK": f"MISCSTATE#{r['misconception_id']}", "type": "MISCSTATE", "student_id": sid,
        "misconception_id": r["misconception_id"], "confidence": conf,
        "confirmed": conf is not None and float(conf) >= MISCONCEPTION_CONFIRMATION_THRESHOLD,
        "last_evidence_id": r["evidence_id"], "updated_at": r["created_at"], "version": 1,
    }


# ======================================================================== ROUTE / FEEDBACK / AGENTLINK / DAILY

def _route(r: dict):
    sid, rid = r["student_id"], r["route_attempt_id"]
    if not r["has_instruction"]:
        status, finished_at = "FINISHED", r["updated_at"]
    elif r["open_rank"] == 1:
        status, finished_at = "IN_PROGRESS", None
    else:
        status, finished_at = "ABANDONED", None
    yield {
        "PK": _stu(sid), "SK": f"ROUTE#{rid}", "type": "ROUTE", "student_id": sid, "route_attempt_id": rid,
        "route_release_id": r["route_release_id"], "problem_code": r["problem_code"],
        "current_step": r["current_step"], "tutor_explained_steps": list(r["tutor_explained_steps"] or []),
        "status": status, "finished_at": finished_at, "created_at": r["created_at"],
        "updated_at": r["updated_at"], "version": r["version"],
    }
    if status == "IN_PROGRESS":
        yield {"PK": _stu(sid), "SK": f"UNIQUE#open_route#{r['route_release_id']}", "type": "UNIQUE_OPEN_ROUTE",
               "student_id": sid, "route_attempt_id": rid}


def _feedback(r: dict):
    sid, fid = r["student_id"], r["feedback_id"]
    h = hashlib.sha256(f"{r['topic']}|{r['reason']}".encode()).hexdigest()
    item = {
        "PK": _stu(sid), "SK": f"FEEDBACK#{fid}", "type": "FEEDBACK",
        "GSI1PK": f"FEEDBACK#{r['status']}", "GSI1SK": f"{iso(r['created_at'])}#{fid}",
        "student_id": sid, "feedback_id": fid, "problem_id": r["problem_id"], "topic": r["topic"],
        "reason": r["reason"], "status": r["status"], "review_note": r["review_note"],
        "created_at": r["created_at"], "reviewed_at": r["reviewed_at"], "feedback_type": r["feedback_type"],
        "audit_snapshot": r["audit_snapshot"], "retrieval_verdict": r["retrieval_verdict"],
        "error_kind": r["error_kind"], "requested_node_id": r["requested_node_id"], "reviewed_by": None,
        "version": 1,
    }
    return [item,
            {"PK": _stu(sid), "SK": f"UNIQUE#feedback#{r['problem_id']}#{h}", "type": "UNIQUE_FEEDBACK",
             "student_id": sid, "feedback_id": fid},
            {"PK": f"FEEDBACK#{fid}", "SK": "OWNER", "type": "FEEDBACK_OWNER", "student_id": sid}]


def _retrieval_exclusion(r: dict):
    yield {"PK": f"RETRIEVAL_EXCLUSION#{r['requested_node_id']}", "SK": f"PROBLEM#{r['problem_id']}",
           "type": "RETRIEVAL_EXCLUSION", "requested_node_id": r["requested_node_id"],
           "problem_id": r["problem_id"], "feedback_ids": [s(x) for x in r["feedback_ids"]],
           "updated_at": r["updated_at"]}


def _agent_link(r: dict):
    sid, app, sess = r["student_id"], r["agent_app_name"], r["agent_session_id"]
    yield {
        "PK": _stu(sid), "SK": f"AGENT#{app}#{sess}", "type": "AGENTLINK",
        "GSI1PK": "AGENTLINKS", "GSI1SK": f"{iso(r['created_at'])}#{r['agent_session_link_id']}",
        "student_id": sid, "link_id": r["agent_session_link_id"], "agent_app_name": app,
        "agent_session_id": sess, "agent_user_id": r["agent_user_id"], "surface": r["surface"],
        "context": r["context"], "created_at": r["created_at"], "last_seen_at": r["last_seen_at"],
    }
    yield {"PK": f"UNIQUE#agent_session#{app}#{sess}", "SK": "UNIQUE", "type": "UNIQUE_AGENT_SESSION",
           "student_id": sid}


DAILY_COUNTERS = ("attempts_started", "attempts_completed", "attempts_abandoned", "steps_evaluated",
                  "steps_succeeded", "gaps_diagnosed", "knowledge_gaps_created", "recovery_plans_created",
                  "recovery_plans_completed")


def _daily(r: dict):
    sid = r["student_id"]
    yield {"PK": _stu(sid), "SK": f"DAILY#{r['activity_date'].isoformat()}", "type": "DAILY", "student_id": sid,
           "activity_date": r["activity_date"], **{c: r[c] for c in DAILY_COUNTERS},
           "updated_at": r["updated_at"], "version": 1}


# ======================================================================== SQL

SQL_PROFILE = """
SELECT student_id, email, password_hash, display_name, status, created_at, last_login_at, first_name,
       last_name, cognito_sub, grade, phone, is_anonymous
FROM learner.student_profile ORDER BY student_id"""

SQL_ATTEMPT = """
SELECT a.attempt_id, a.student_id, a.problem_id, a.is_correct, a.submitted_answer, a.time_spent_seconds,
       a.hint_count, a.attempted_at, a.source, p.difficulty_band,
       (SELECT sa.solve_attempt_id FROM learner.solve_attempt sa WHERE sa.outcome_attempt_id = a.attempt_id
         ORDER BY sa.solve_attempt_id LIMIT 1) AS solve_attempt_id,
       (SELECT array_agg(DISTINCT pc.concept_id ORDER BY pc.concept_id) FROM knowledge.problem_concept pc
         WHERE pc.problem_id = a.problem_id AND pc.review_status = 'REVIEWED') AS concept_ids,
       (SELECT array_agg(DISTINCT pt.technique_id ORDER BY pt.technique_id) FROM knowledge.problem_technique pt
         WHERE pt.problem_id = a.problem_id AND pt.review_status = 'REVIEWED') AS technique_ids
FROM learner.attempt a LEFT JOIN core.problem p ON p.problem_id = a.problem_id
ORDER BY a.student_id, a.attempted_at, a.attempt_id"""

SQL_QUIZ_RESPONSE = """
SELECT r.response_id, r.student_id, r.quiz_id, r.question_id, r.is_correct, r.submitted_at, qp.difficulty_band,
       (SELECT array_agg(DISTINCT qc.concept_id ORDER BY qc.concept_id) FROM quiz.question_concept qc
         WHERE qc.question_id = r.question_id) AS concept_ids,
       (SELECT array_agg(DISTINCT qt.technique_id ORDER BY qt.technique_id) FROM quiz.question_technique qt
         WHERE qt.question_id = r.question_id) AS technique_ids
FROM quiz.response r JOIN quiz.paper qp ON qp.quiz_id = r.quiz_id
ORDER BY r.student_id, r.submitted_at, r.response_id"""

SQL_MEVID_DEDUPE_CHECK = """
SELECT x.kind, x.attempt_id, x.student_id, x.tag_id, x.n, g AS copy_no
FROM (SELECT 'C' AS kind, a.attempt_id, a.student_id, pc.concept_id AS tag_id, count(*) AS n
        FROM learner.attempt a
        JOIN knowledge.problem_concept pc ON pc.problem_id = a.problem_id AND pc.review_status = 'REVIEWED'
       WHERE a.is_correct IS NOT NULL GROUP BY 1, 2, 3, 4
      UNION ALL
      SELECT 'T', a.attempt_id, a.student_id, pt.technique_id, count(*)
        FROM learner.attempt a
        JOIN knowledge.problem_technique pt ON pt.problem_id = a.problem_id AND pt.review_status = 'REVIEWED'
       WHERE a.is_correct IS NOT NULL GROUP BY 1, 2, 3, 4) x
CROSS JOIN LATERAL generate_series(2, x.n) AS g
ORDER BY x.kind, x.student_id, x.tag_id, x.attempt_id, g"""

SQL_PROBLEM_CURSOR = """
WITH k AS (SELECT student_id, problem_id FROM learner.attempt
           UNION SELECT student_id, problem_id FROM learner.solve_attempt)
SELECT k.student_id, k.problem_id,
       (SELECT max(sa.attempt_number) FROM learner.solve_attempt sa
         WHERE sa.student_id = k.student_id AND sa.problem_id = k.problem_id) AS attempt_seq,
       (SELECT sa.solve_attempt_id FROM learner.solve_attempt sa
         WHERE sa.student_id = k.student_id AND sa.problem_id = k.problem_id AND sa.status = 'IN_PROGRESS'
         ORDER BY sa.started_at DESC, sa.solve_attempt_id DESC LIMIT 1) AS open_solve_attempt_id,
       LEAST((SELECT min(a.attempted_at) FROM learner.attempt a
               WHERE a.student_id = k.student_id AND a.problem_id = k.problem_id),
             (SELECT min(sa.started_at) FROM learner.solve_attempt sa
               WHERE sa.student_id = k.student_id AND sa.problem_id = k.problem_id)) AS first_attempted_at,
       (SELECT count(*) FROM learner.attempt a
         WHERE a.student_id = k.student_id AND a.problem_id = k.problem_id) AS outcome_count
FROM k ORDER BY k.student_id, k.problem_id"""

SQL_CONCEPT_MASTERY = """
SELECT student_id, concept_id, mastery_score, attempts_count, correct_count, last_attempt_at, updated_at
FROM learner.concept_mastery ORDER BY student_id, concept_id"""

SQL_TECHNIQUE_MASTERY = """
SELECT student_id, technique_id, mastery_score, attempts_count, correct_count, last_attempt_at, updated_at
FROM learner.technique_mastery ORDER BY student_id, technique_id"""

SQL_COHORT = """
SELECT concept_id, sum(mastery_score) AS sum_score, count(*) AS n_students, max(updated_at) AS updated_at
FROM learner.concept_mastery GROUP BY concept_id ORDER BY concept_id"""

SQL_SOLVE = """
SELECT s.solve_attempt_id, s.student_id, s.problem_id, s.attempt_number, s.status, s.started_at,
       s.submitted_at, s.completed_at, s.current_solution_part_id, s.current_solution_step_id,
       s.recovery_plan_id, s.outcome_attempt_id, s.metadata,
       r.current_mode, r.current_step_id, r.current_recovery_plan_id, r.state_version,
       r.updated_at AS runtime_updated_at,
       (SELECT count(*) FROM learner.event e
         WHERE e.solve_attempt_id = s.solve_attempt_id AND e.event_type = 'HINT_REQUESTED') AS hint_requested_count,
       COALESCE((SELECT max(e.event_time) FROM learner.event e WHERE e.solve_attempt_id = s.solve_attempt_id),
                s.started_at) AS last_activity_at,
       (SELECT array_agg(p.recovery_plan_id ORDER BY p.created_at, p.recovery_plan_id)
          FROM pedagogy.recovery_plan p WHERE p.solve_attempt_id = s.solve_attempt_id) AS plan_ids
FROM learner.solve_attempt s LEFT JOIN tutor.runtime_state r ON r.solve_attempt_id = s.solve_attempt_id
ORDER BY s.student_id, s.solve_attempt_id"""

SQL_RUNTIME_STATE = """
SELECT r.solve_attempt_id, r.student_id, r.current_problem_id,
       s.student_id AS parent_student_id, s.problem_id AS parent_problem_id
FROM tutor.runtime_state r LEFT JOIN learner.solve_attempt s ON s.solve_attempt_id = r.solve_attempt_id
ORDER BY r.solve_attempt_id"""

SQL_STEPSTATE = """
SELECT st.solve_attempt_id, st.solution_step_id, st.state, st.first_seen_at, st.first_attempted_at,
       st.last_updated_at, st.independent_success, st.help_level_used, st.attempt_count,
       st.last_response_text, st.last_evaluation, st.evidence,
       sa.student_id, sa.problem_id, ps.skill_node_id, ps.subconcept_node_id,
       (SELECT count(*) FROM learner.event e WHERE e.solve_attempt_id = st.solve_attempt_id
          AND e.solution_step_id = st.solution_step_id
          AND e.event_type = 'RETURNED_TO_ORIGINAL_STEP') AS returned_to_step_count,
       (SELECT count(*) FROM learner.event e WHERE e.solve_attempt_id = st.solve_attempt_id
          AND e.solution_step_id = st.solution_step_id
          AND e.event_type = 'RETURNED_TO_ORIGINAL_PROBLEM') AS returned_to_problem_count
FROM learner.attempt_step_state st
JOIN learner.solve_attempt sa ON sa.solve_attempt_id = st.solve_attempt_id
LEFT JOIN LATERAL (SELECT x.skill_node_id, x.subconcept_node_id FROM pedagogy.solution_step x
                   WHERE x.solution_step_id = st.solution_step_id
                   ORDER BY x.solution_step_id LIMIT 1) ps ON true
ORDER BY sa.student_id, st.solve_attempt_id, st.solution_step_id"""

SQL_EVENT = """
SELECT event_id, student_id, solve_attempt_id, event_type, event_time, actor_type, solution_step_id, payload,
       idempotency_key
FROM learner.event ORDER BY student_id, event_time, event_id"""

SQL_IDEM = """
SELECT student_id, idempotency_key, operation, request_hash, response, created_at
FROM learner.idempotency_record ORDER BY student_id, idempotency_key"""

SQL_DIAG = """
SELECT gap_diagnosis_id, student_id, solve_attempt_id, solution_step_id, trigger, recommended_action,
       evidence_fingerprint, evidence, probes, diagnoser_version, created_at, ai_rerank
FROM pedagogy.gap_diagnosis ORDER BY student_id, created_at, gap_diagnosis_id"""

SQL_GAP = """
SELECT g.knowledge_gap_id, g.gap_diagnosis_id, g.student_id, g.solve_attempt_id, g.solution_step_id, g.rank,
       g.failure_location, g.failure_mode, g.target_concept_id, g.target_subconcept_id, g.target_skill_id,
       g.target_skill_node_id, g.target_label, g.source_step_id, g.confidence, g.evidence, g.status,
       g.status_reason, g.created_at, g.status_changed_at, g.resolved_at,
       lp.recovery_plan_id AS latest_plan_id, lp.status AS latest_plan_status
FROM pedagogy.knowledge_gap g
LEFT JOIN LATERAL (SELECT p.recovery_plan_id, p.status FROM pedagogy.recovery_plan p
                   WHERE p.knowledge_gap_id = g.knowledge_gap_id
                   ORDER BY p.created_at DESC, p.recovery_plan_id DESC LIMIT 1) lp ON true
ORDER BY g.student_id, g.knowledge_gap_id"""

SQL_PLAN = f"""
SELECT p.recovery_plan_id, p.student_id, p.solve_attempt_id, p.origin_problem_id, p.origin_step_id,
       p.gap_diagnosis_id, p.knowledge_gap_id, p.parent_recovery_plan_id, p.trigger, p.target_skill_id,
       p.target_subconcept_id, p.target_label, p.status, p.current_item_ordinal, p.mastery_policy, p.outcome,
       p.planner_version, p.created_at, p.updated_at, p.ended_at,
       (SELECT json_agg(json_build_object(
                 'recovery_plan_item_id', i.recovery_plan_item_id, 'ordinal', i.ordinal, 'stage', i.stage,
                 'item_kind', i.item_kind, 'learning_item_id', i.learning_item_id,
                 'worked_step_id', i.worked_step_id, 'is_transfer', i.is_transfer, 'required', i.required,
                 'status', i.status, 'tries', i.tries, 'independent_success', i.independent_success,
                 'last_response', i.last_response, 'last_result', i.last_result,
                 'added_reason', i.added_reason, 'presented_at', {_ts('i.presented_at')},
                 'completed_at', {_ts('i.completed_at')}) ORDER BY i.ordinal, i.recovery_plan_item_id)
          FROM pedagogy.recovery_plan_item i WHERE i.recovery_plan_id = p.recovery_plan_id) AS items
FROM pedagogy.recovery_plan p ORDER BY p.student_id, p.recovery_plan_id"""

SQL_PLAN_ITEM = """
SELECT i.recovery_plan_item_id, (p.recovery_plan_id IS NOT NULL) AS plan_exists
FROM pedagogy.recovery_plan_item i LEFT JOIN pedagogy.recovery_plan p ON p.recovery_plan_id = i.recovery_plan_id
ORDER BY i.recovery_plan_item_id"""

SQL_ENROLL = f"""
SELECT e.enrollment_id, e.student_id, e.micro_course_id, e.release_id, e.status, e.started_at, e.completed_at,
       mc.canonical_code, rt.current_state_id, rt.state_version, rt.updated_at AS runtime_updated_at,
       (e.status = 'IN_PROGRESS' AND row_number() OVER (
            PARTITION BY e.student_id, e.micro_course_id, (e.status = 'IN_PROGRESS')
            ORDER BY e.started_at DESC, e.enrollment_id DESC) = 1) AS holds_open_sentinel,
       (SELECT jsonb_object_agg(x.item_id, jsonb_build_object(
                 'kind', x.event_type, 'event_id', x.event_id, 'state_id', x.state_id,
                 'created_at', {_ts('x.created_at')}, 'payload', x.payload))
          FROM (SELECT DISTINCT ON (COALESCE(ev.payload->>'learning_item_id', ev.payload->>'activity_id'))
                       COALESCE(ev.payload->>'learning_item_id', ev.payload->>'activity_id') AS item_id,
                       ev.event_type, ev.event_id, ev.state_id, ev.created_at, ev.payload
                FROM learner.micro_course_state_event ev
                WHERE ev.enrollment_id = e.enrollment_id
                  AND ev.event_type IN ('QUIZ_RESPONSE', 'ACTIVITY_RESPONSE')
                  AND COALESCE(ev.payload->>'learning_item_id', ev.payload->>'activity_id') IS NOT NULL
                ORDER BY COALESCE(ev.payload->>'learning_item_id', ev.payload->>'activity_id'),
                         ev.created_at DESC, ev.event_id DESC) x) AS last_responses
FROM learner.micro_course_enrollment e
LEFT JOIN tutor.micro_course_runtime rt ON rt.enrollment_id = e.enrollment_id
LEFT JOIN pedagogy.micro_course mc ON mc.micro_course_id = e.micro_course_id
ORDER BY e.student_id, e.enrollment_id"""

SQL_COURSE_RUNTIME = """
SELECT r.enrollment_id, (e.enrollment_id IS NOT NULL) AS parent_exists
FROM tutor.micro_course_runtime r LEFT JOIN learner.micro_course_enrollment e ON e.enrollment_id = r.enrollment_id
ORDER BY r.enrollment_id"""

SQL_MCEVENT = """
SELECT ev.event_id, ev.enrollment_id, ev.state_id, ev.event_type, ev.payload, ev.created_at,
       e.student_id, e.release_id
FROM learner.micro_course_state_event ev
JOIN learner.micro_course_enrollment e ON e.enrollment_id = ev.enrollment_id
ORDER BY e.student_id, ev.enrollment_id, ev.created_at, ev.event_id"""

SQL_IXEVENT = """
SELECT interaction_event_id, student_id, enrollment_id, course_state_id, interaction_instance_id, event_type,
       semantic_action, control_key, object_id, before_state, action_payload, after_state, evaluation_outcome,
       error_signature, created_at
FROM learner.interaction_event ORDER BY student_id, created_at, interaction_event_id"""

SQL_MISC_EVIDENCE = """
SELECT evidence_id, student_id, interaction_event_id, misconception_id, evidence_type, evidence_weight,
       confidence_before, confidence_after, created_at
FROM learner.misconception_evidence ORDER BY student_id, misconception_id, created_at, evidence_id"""

SQL_MISC_STATE = """
SELECT DISTINCT ON (student_id, misconception_id)
       student_id, misconception_id, evidence_id, confidence_after, created_at
FROM learner.misconception_evidence
ORDER BY student_id, misconception_id, created_at DESC, evidence_id DESC"""

SQL_ROUTE = """
SELECT ra.route_attempt_id, ra.student_id, ra.route_release_id, ra.current_step, ra.version,
       ra.tutor_explained_steps, ra.created_at, ra.updated_at, cp.canonical_code AS problem_code,
       EXISTS (SELECT 1 FROM pedagogy.solution_step_instruction si
                WHERE si.route_release_id = ra.route_release_id AND si.step_index = ra.current_step) AS has_instruction,
       row_number() OVER (
           PARTITION BY ra.student_id, ra.route_release_id,
                        EXISTS (SELECT 1 FROM pedagogy.solution_step_instruction si
                                 WHERE si.route_release_id = ra.route_release_id AND si.step_index = ra.current_step)
           ORDER BY ra.created_at DESC, ra.route_attempt_id DESC) AS open_rank
FROM learner.route_attempt ra
LEFT JOIN pedagogy.solution_route_release rr ON rr.route_release_id = ra.route_release_id
LEFT JOIN core.problem cp ON cp.problem_id = rr.problem_id
ORDER BY ra.student_id, ra.route_attempt_id"""

SQL_FEEDBACK = """
SELECT feedback_id, student_id, problem_id, topic, reason, status, review_note, created_at, reviewed_at,
       feedback_type, audit_snapshot, retrieval_verdict, error_kind,
       audit_snapshot->>'requested_node_id' AS requested_node_id
FROM learner.pedagogy_feedback ORDER BY student_id, feedback_id"""

SQL_RETRIEVAL_EXCLUSION = """
SELECT audit_snapshot->>'requested_node_id' AS requested_node_id, problem_id,
       array_agg(feedback_id ORDER BY feedback_id) AS feedback_ids,
       max(COALESCE(reviewed_at, created_at)) AS updated_at
FROM learner.pedagogy_feedback
WHERE status = 'RESOLVED' AND retrieval_verdict = 'IRRELEVANT'
  AND audit_snapshot->>'requested_node_id' IS NOT NULL
GROUP BY 1, 2 ORDER BY 1, 2"""

SQL_AGENT_LINK = """
SELECT agent_session_link_id, agent_app_name, agent_user_id, agent_session_id, student_id, surface, context,
       created_at, last_seen_at
FROM learner.agent_session_link ORDER BY student_id, agent_app_name, agent_session_id"""

SQL_DAILY = """
SELECT student_id, activity_date, attempts_started, attempts_completed, attempts_abandoned, steps_evaluated,
       steps_succeeded, gaps_diagnosed, knowledge_gaps_created, recovery_plans_created, recovery_plans_completed,
       updated_at
FROM analytics.learner_daily_activity ORDER BY student_id, activity_date"""


def _m(name: str, sql: str, fn, expected: str | None = "", note: str = "") -> Mapping:
    return Mapping(name, table=T, sql=sql, transform=fn,
                   expected_source=name if expected == "" else expected, note=note)


MAPPINGS = [
    _m("learner.student_profile", SQL_PROFILE, _profile, note="PROFILE + UNIQUE#email + UNIQUE#cognito_sub"),
    _m("learner.attempt", SQL_ATTEMPT, _attempt, note="OUTCOME + MEVID (OUT) per REVIEWED tag when graded"),
    _m("learner.mevid_from_quiz_response", SQL_QUIZ_RESPONSE, _quiz_response, expected="quiz.response",
       note="MEVID src_kind=QZ (quiz.response stays owned by C2)"),
    _m("learner.mevid_dedupe_check", SQL_MEVID_DEDUPE_CHECK, _mevid_dedupe_check, expected=None,
       note="check only, no items: graded-attempt evidence rows dropped by tag dedupe (PRIMARY vs primary "
            "duplicate problem_concept/problem_technique rows). Dev 2026-11-02: 28 rows (16 concept over 13 "
            "attempts / 16 student-concepts; 12 technique over 9 attempts / 9 student-techniques). PG mastery "
            "counts these twice, so MEVID-recomputed scores may differ from stored PG scores for those tags. "
            "quiz.question_concept/technique have no duplicates."),
    _m("learner.problem_cursor", SQL_PROBLEM_CURSOR, _problem_cursor, expected=None,
       note="PROBLEM cursors over attempt ∪ solve_attempt"),
    _m("learner.concept_mastery", SQL_CONCEPT_MASTERY, _mastery("C", "concept_id")),
    _m("learner.technique_mastery", SQL_TECHNIQUE_MASTERY, _mastery("T", "technique_id")),
    _m("learner.cohort_concept", SQL_COHORT, _cohort, expected=None,
       note="COHORT#CONCEPT backfill (stream consumer starts at LATEST)"),
    _m("learner.solve_attempt", SQL_SOLVE, _solve, note="SOLVE (+ folded tutor.runtime_state) + SOLVE#/OWNER"),
    _m("tutor.runtime_state", SQL_RUNTIME_STATE, _runtime_state_fold, note="folded into SOLVE; verify only"),
    _m("learner.attempt_step_state", SQL_STEPSTATE, _stepstate),
    _m("learner.event", SQL_EVENT, _event),
    _m("learner.idempotency_record", SQL_IDEM, _idem, note="IDEM with ttl = created_at + 7 d"),
    _m("pedagogy.gap_diagnosis", SQL_DIAG, _diag, note="DIAG + UNIQUE#diag_fp"),
    _m("pedagogy.knowledge_gap", SQL_GAP, _gap),
    _m("pedagogy.recovery_plan", SQL_PLAN, _plan, note="PLAN with embedded items[] + PLAN#/OWNER"),
    _m("pedagogy.recovery_plan_item", SQL_PLAN_ITEM, _plan_item_fold, note="embedded in PLAN.items; verify only"),
    _m("learner.micro_course_enrollment", SQL_ENROLL, _enroll,
       note="ENROLL (+ folded tutor.micro_course_runtime, last_responses) + OWNER + UNIQUE#open_enroll"),
    _m("tutor.micro_course_runtime", SQL_COURSE_RUNTIME, _course_runtime_fold, note="folded into ENROLL; verify only"),
    _m("learner.micro_course_state_event", SQL_MCEVENT, _mcevent),
    _m("learner.interaction_event", SQL_IXEVENT, _ixevent),
    _m("learner.misconception_evidence", SQL_MISC_EVIDENCE, _misc_evidence),
    _m("learner.misconception_state", SQL_MISC_STATE, _misc_state, expected=None,
       note="MISCSTATE from the latest evidence row per (student, misconception)"),
    _m("learner.route_attempt", SQL_ROUTE, _route, note="ROUTE + UNIQUE#open_route"),
    _m("learner.pedagogy_feedback", SQL_FEEDBACK, _feedback, note="FEEDBACK + UNIQUE#feedback + FEEDBACK#/OWNER"),
    _m("learner.retrieval_exclusion", SQL_RETRIEVAL_EXCLUSION, _retrieval_exclusion, expected=None),
    _m("learner.agent_session_link", SQL_AGENT_LINK, _agent_link, note="AGENTLINK + UNIQUE#agent_session"),
    _m("analytics.learner_daily_activity", SQL_DAILY, _daily),
]
