"""Synthetic, staff-owned previews of a pinned Socratic draft revision (ledger step 03).

One preview row holds the authoritative position and CAS `state_version`; every accepted
command appends an immutable event in the same transaction, with the exact DTO it returned
so an identical retry replays it (SOC-IR-05/06). Responses are scored by the shared
`activity_scoring` module against a private snapshot pinned at start. Nothing here writes
learner, mastery, course or activity rows, and no model or AWS call is made.
"""
from __future__ import annotations

import math
from fractions import Fraction
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest import activity_scoring as scoring
from mathbank_rest.socratic_auth import StaffActor, fail
from mathbank_rest.socratic_contracts import (
    Node,
    Preview,
    PreviewCommand,
    Program,
    Respond,
    Simulate,
    Transition,
    WrittenResponse,
    canonical_json,
    content_digest,
)
from mathbank_rest.socratic_service import database_error, dependency_snapshot, revision_row

# Control/terminal nodes cannot be an explicitly requested preview start.
NON_STARTABLE = {"COMPLETE", "HUMAN_REVIEW", "RETURN", "AI_DECISION", "DETERMINISTIC_GATE", "BRANCH"}
FEEDBACK = {
    "CORRECT": "Correct. The next step follows the instructor's SUCCESS rule.",
    "CORRECT_AFTER_REVEAL": "Matches the revealed explanation. Recorded as assisted, not independent success.",
    "INCORRECT": "Not yet. One response is tentative evidence; try again or request a hint.",
    "UNCERTAIN": "Recorded for review. Written reasoning is not auto-scored, so no correctness is inferred.",
}


class BindingError(ValueError):
    """A node's activity reference cannot be bound for deterministic preview."""


def _engine():
    # Resolved at call time so tests that rebind socratic_service.engine cover this module too.
    from mathbank_rest import socratic_service

    return socratic_service.engine


def _activity_uuid(ref: str) -> UUID:
    try:
        return UUID(ref.removeprefix("activity:"))
    except ValueError:
        raise BindingError("activity_ref must be an activity.definition UUID") from None


def bind_activity(conn, node: Node, problem_id: str | None) -> dict:
    """Load and validate one bound activity; return its private scoring snapshot."""
    activity_id = _activity_uuid(node.activity_ref or "")
    row = conn.execute(text("""
        SELECT activity_id::text,activity_type,prompt,options,correctness_policy,status,
               source_problem_id::text
        FROM activity.definition WHERE activity_id=:id
    """), {"id": activity_id}).mappings().first()
    if not row or row["status"] != "ACTIVE":
        raise BindingError("activity is missing or inactive")
    if row["source_problem_id"] and row["source_problem_id"] != problem_id:
        raise BindingError("activity belongs to a different source problem")
    policy = row["correctness_policy"] or {}
    try:
        kind = scoring.runtime_kind(row["activity_type"], row["options"], policy)
    except scoring.UnsupportedActivity as exc:
        raise BindingError(str(exc)) from None
    hints = policy.get("hints", [])
    if not isinstance(hints, list) or len(hints) > 5 or any(not isinstance(h, str) or not h.strip() for h in hints):
        raise BindingError("hints must be at most five non-empty strings")
    snapshot = {key: row[key] for key in ("activity_id", "activity_type", "prompt", "options")}
    snapshot |= {"policy": policy, "kind": kind}
    # The private snapshot hash is the pinned revision: activity.definition rows are mutable.
    snapshot["revision"] = content_digest(snapshot)
    return snapshot


def activity_findings(conn, program: Program, problem_id: str | None) -> list[str]:
    findings = []
    for node in program.nodes:
        if node.activity_ref:
            try:
                bind_activity(conn, node, problem_id)
            except BindingError as exc:
                findings.append(f"Node {node.key}: {exc}.")
    return findings


def _snapshot_all(conn, program: Program, problem_id: str | None) -> dict:
    snapshot = {}
    for node in program.nodes:
        if node.activity_ref:
            try:
                snapshot[node.key] = bind_activity(conn, node, problem_id)
            except BindingError as exc:
                raise fail(422, "SOCRATIC_ACTIVITY_UNSUPPORTED", f"Node {node.key}: {exc}.") from None
    return snapshot


def _node(program: Program, key: str) -> Node:
    return next(node for node in program.nodes if node.key == key)


def route(program: Program, current: str, outcome: str, transitions_used: int) -> dict:
    """Deterministic edge selection: exact outcome first, then ALWAYS; lowest priority wins.

    Every move that changes node counts against `max_transitions`; once exhausted, the preview
    ends at the fallback node instead of following any rule.
    """
    edges = [e for e in program.edges if e.from_key == current and e.outcome == outcome]
    if not edges and outcome != "ALWAYS":
        edges = [e for e in program.edges if e.from_key == current and e.outcome == "ALWAYS"]
    if not edges and outcome == "RETRY":
        return {"to_key": current, "rule_id": None, "decision_source": "STAY_ON_NODE", "counts": False,
                "reason": "No RETRY rule from this node; the learner stays on the current activity."}
    if not edges and current == program.fallback_key:
        return {"to_key": current, "rule_id": None, "decision_source": "NO_ELIGIBLE_RULE", "counts": False,
                "complete": True, "reason": f"No {outcome} or ALWAYS rule from the fallback; preview ends."}
    if transitions_used + 1 > program.max_transitions:
        return {"to_key": program.fallback_key, "rule_id": None, "decision_source": "BUDGET_EXHAUSTED",
                "counts": False, "complete": True,
                "reason": f"Transition budget of {program.max_transitions} exhausted; routed to fallback."}
    if not edges:
        return {"to_key": program.fallback_key, "rule_id": None, "decision_source": "FALLBACK", "counts": True,
                "reason": f"No {outcome} or ALWAYS rule from {current}; routed to fallback {program.fallback_key}."}
    edge = min(edges, key=lambda e: e.priority)
    rule_id = f"{edge.from_key}:{edge.outcome}:{edge.priority}"
    reason = f"Rule {edge.outcome} (priority {edge.priority}) → {edge.to_key}."
    if edge.annotation:
        reason += f" Instructor note: {edge.annotation}"
    return {"to_key": edge.to_key, "rule_id": rule_id, "decision_source": "INSTRUCTOR_RULE",
            "counts": True, "reason": reason}


def _public_activity(snapshot: dict) -> dict:
    kind = snapshot["kind"]
    activity = {"activity_id": snapshot["activity_id"], "revision": snapshot["revision"], "kind": kind,
                "prompt": snapshot["prompt"]}
    if kind == "ASSERTION_REASON":
        activity["options"] = [{"key": case, "text": option}
                               for case, option in zip(scoring.AR_CASES, snapshot["options"], strict=True)]
    elif kind in ("SINGLE_CHOICE", "MULTI_SELECT"):
        activity["options"] = [{"key": str(index), "text": option} for index, option in enumerate(snapshot["options"])]
    return activity


def _history(conn, preview_id: UUID) -> list[dict]:
    rows = conn.execute(text("""
        SELECT node_key,decision_source,reason,from_key,to_key,outcome,rule_id,assisted
        FROM orchestration.socratic_preview_event
        WHERE preview_id=:id AND action<>'START' ORDER BY state_version
    """), {"id": preview_id}).mappings()
    return [dict(row) for row in rows]


def _dto(state: dict, program: Program, history: list[dict]) -> dict:
    node = _node(program, state["current_node_key"])
    snapshot = state["activity_snapshot"].get(node.key)
    result = {
        "preview_id": state["preview_id"], "workflow_id": state["workflow_id"],
        "workflow_revision": state["workflow_revision"], "content_hash": state["content_hash"],
        "state_version": state["state_version"], "current_node": node.model_dump(mode="json", exclude_none=True),
        "status": state["status"], "synthetic": True, "feedback": state["feedback"], "history": history,
        "transitions_used": state["transitions_used"], "max_transitions": program.max_transitions,
    }
    if snapshot and state["status"] == "ACTIVE":
        result["activity"] = _public_activity(snapshot)
        if state["hint_level"]:
            result["help"] = {"level": state["hint_level"],
                              "text": snapshot["policy"]["hints"][state["hint_level"] - 1], "assisted": True}
    return Preview.model_validate(result).model_dump(mode="json", exclude_none=True)


def _program(conn, actor: StaffActor, workflow_id: UUID, revision: int) -> Program:
    return Program.model_validate(revision_row(conn, workflow_id, actor, revision)["program"])


def start_preview(workflow_id: UUID, body: Simulate, actor: StaffActor) -> dict:
    try:
        with _engine().begin() as conn:
            row = revision_row(conn, workflow_id, actor)
            if row["content_hash"] != body.expected_hash:
                raise fail(409, "SOCRATIC_DRAFT_STALE", "Draft changed; save and restart the preview.")
            program = Program.model_validate(row["program"])
            if dependency_snapshot(conn, program, row["domain"]) != row["dependencies"]:
                raise fail(409, "SOCRATIC_SOURCE_STALE", "Source dependencies changed; save a new explicit revision.")
            start = body.start_node_key or program.entry
            reachable = {program.entry}
            for _ in program.nodes:
                reachable |= {edge.to_key for edge in program.edges if edge.from_key in reachable}
            if start not in reachable or (start != program.entry and _node(program, start).type in NON_STARTABLE):
                raise fail(422, "SOCRATIC_START_INVALID", "Start from the entry or a reachable activity node.")
            snapshot = _snapshot_all(conn, program, row["dependencies"]["source"].get("problem_id"))
            state = {
                "preview_id": uuid4(), "workflow_id": workflow_id, "workflow_revision": row["revision"],
                "content_hash": row["content_hash"], "activity_snapshot": snapshot, "state_version": 1,
                "current_node_key": start, "status": "COMPLETE" if _node(program, start).type == "COMPLETE" else "ACTIVE",
                "transitions_used": 0, "hint_level": 0, "revealed": False, "feedback": None,
            }
            conn.execute(text("""
                INSERT INTO orchestration.socratic_preview
                (preview_id,owner_id,workflow_id,workflow_revision,content_hash,activity_snapshot,state_version,
                 current_node_key,status)
                VALUES (:preview_id,:owner,:workflow_id,:workflow_revision,:content_hash,
                        CAST(:snapshot AS jsonb),1,:current_node_key,:status)
            """), state | {"owner": actor.actor_id, "snapshot": canonical_json(snapshot)})
            result = _dto(state, program, [])
            _append(conn, state, "START", None, content_digest(body.model_dump(mode="json")), result,
                    {"node_key": start, "decision_source": "PREVIEW_START",
                     "reason": "Synthetic preview started" + (" from the requested resource." if body.start_node_key else ".")})
            return result
    except SQLAlchemyError:
        raise database_error() from None


def _append(conn, state: dict, action: str, key: str | None, request_hash: str, result: dict, event: dict,
            response: dict | None = None, evidence: dict | None = None) -> None:
    conn.execute(text("""
        INSERT INTO orchestration.socratic_preview_event
        (preview_id,state_version,action,idempotency_key,request_hash,node_key,from_key,to_key,outcome,rule_id,
         decision_source,reason,assisted,response,evidence,result)
        VALUES (:preview_id,:state_version,:action,:key,:request_hash,:node_key,:from_key,:to_key,:outcome,:rule_id,
                :decision_source,:reason,:assisted,CAST(:response AS jsonb),CAST(:evidence AS jsonb),
                CAST(:result AS jsonb))
    """), {"preview_id": state["preview_id"], "state_version": state["state_version"], "action": action,
           "key": key, "request_hash": request_hash, "from_key": None, "to_key": None, "outcome": None,
           "rule_id": None, "assisted": False, **event,
           "response": canonical_json(response) if response is not None else None,
           "evidence": canonical_json(evidence or {}), "result": canonical_json(result)})


def get_preview(preview_id: UUID, actor: StaffActor) -> dict:
    try:
        with _engine().connect() as conn:
            state = _load(conn, preview_id, actor)
            program = _program(conn, actor, state["workflow_id"], state["workflow_revision"])
            return _dto(state, program, _history(conn, preview_id))
    except SQLAlchemyError:
        raise database_error() from None


def _load(conn, preview_id: UUID, actor: StaffActor, *, lock: bool = False) -> dict:
    row = conn.execute(text(f"""
        SELECT preview_id,workflow_id,workflow_revision,content_hash,activity_snapshot,state_version,
               current_node_key,status,transitions_used,hint_level,revealed,feedback
        FROM orchestration.socratic_preview WHERE preview_id=:id AND owner_id=:owner
        {"FOR UPDATE" if lock else ""}
    """), {"id": preview_id, "owner": actor.actor_id}).mappings().first()
    if not row:
        raise fail(404, "SOCRATIC_PREVIEW_NOT_FOUND", "Preview not found.")
    return dict(row)


def _command(preview_id: UUID, action: str, body: PreviewCommand, actor: StaffActor, apply) -> dict:
    request_hash = content_digest({"action": action,
                                   "body": body.model_dump(mode="json", exclude={"idempotency_key"})})
    try:
        with _engine().begin() as conn:
            state = _load(conn, preview_id, actor, lock=True)
            prior = conn.execute(text("""
                SELECT request_hash,result FROM orchestration.socratic_preview_event
                WHERE preview_id=:id AND idempotency_key=:key
            """), {"id": preview_id, "key": body.idempotency_key}).mappings().first()
            if prior:
                if prior["request_hash"] != request_hash:
                    raise fail(409, "SOCRATIC_IDEMPOTENCY_CONFLICT", "This idempotency key was used with different input.")
                return prior["result"]
            if body.expected_version != state["state_version"]:
                raise fail(409, "SOCRATIC_PREVIEW_STALE", "Preview advanced; reload its current state.")
            current = conn.execute(text("""
                SELECT content_hash FROM orchestration.socratic_workflow WHERE workflow_id=:id AND owner_id=:owner
            """), {"id": state["workflow_id"], "owner": actor.actor_id}).scalar()
            if current != state["content_hash"]:
                raise fail(409, "SOCRATIC_PREVIEW_DRAFT_CHANGED", "The draft was saved since this preview started; restart it.")
            if state["status"] != "ACTIVE":
                raise fail(409, "SOCRATIC_PREVIEW_COMPLETE", "This preview has ended; start a new one.")
            program = _program(conn, actor, state["workflow_id"], state["workflow_revision"])
            event, response, evidence = apply(state, program)
            state["state_version"] += 1
            conn.execute(text("""
                UPDATE orchestration.socratic_preview SET state_version=:state_version,
                    current_node_key=:current_node_key,status=:status,transitions_used=:transitions_used,
                    hint_level=:hint_level,revealed=:revealed,feedback=:feedback,updated_at=clock_timestamp()
                WHERE preview_id=:preview_id
            """), state)
            history = _history(conn, preview_id) + [{
                key: event.get(key) for key in
                ("node_key", "decision_source", "reason", "from_key", "to_key", "outcome", "rule_id")
            } | {"assisted": event.get("assisted", False)}]
            result = _dto(state, program, history)
            _append(conn, state, action, body.idempotency_key, request_hash, result, event, response, evidence)
            return result
    except SQLAlchemyError:
        raise database_error() from None


def _move(state: dict, program: Program, outcome: str) -> dict:
    current = state["current_node_key"]
    decision = route(program, current, outcome, state["transitions_used"])
    destination = decision["to_key"]
    if decision["counts"]:
        state["transitions_used"] += 1
    if destination != current:
        state.update(current_node_key=destination, hint_level=0, revealed=False)
    if decision.get("complete") or _node(program, destination).type == "COMPLETE":
        state["status"] = "COMPLETE"
    return {"node_key": destination, "from_key": current, "to_key": destination, "outcome": outcome,
            "rule_id": decision["rule_id"], "decision_source": decision["decision_source"],
            "reason": decision["reason"]}


def transition(preview_id: UUID, body: Transition, actor: StaffActor) -> dict:
    def apply(state, program):
        event = _move(state, program, body.outcome)
        event["reason"] = "Staff-simulated outcome, not a grade. " + event["reason"]
        event["decision_source"] = "STAFF_SIMULATION:" + event["decision_source"]
        state["feedback"] = None
        return event, None, None
    return _command(preview_id, "TRANSITION", body, actor, apply)


def _current_activity(state: dict) -> dict:
    snapshot = state["activity_snapshot"].get(state["current_node_key"])
    if not snapshot:
        raise fail(409, "SOCRATIC_NO_ACTIVITY", "No response activity is bound to the current node.")
    return snapshot


def _scorer_response(snapshot: dict, response) -> dict:
    kind = snapshot["kind"]
    if kind in ("SINGLE_CHOICE", "MULTI_SELECT", "ASSERTION_REASON"):
        if isinstance(response, WrittenResponse):
            raise fail(422, "SOCRATIC_RESPONSE_INVALID", "Select one of the listed options.")
        keys = list(scoring.AR_CASES) if kind == "ASSERTION_REASON" else [str(i) for i in range(len(snapshot["options"]))]
        if any(key not in keys for key in response.selected_keys):
            raise fail(422, "SOCRATIC_RESPONSE_INVALID", "Select only the listed options.")
        return {"selected_indices": [keys.index(key) for key in response.selected_keys]}
    if not isinstance(response, WrittenResponse):
        raise fail(422, "SOCRATIC_RESPONSE_INVALID", "A written response is required.")
    if kind == "NUMERIC_EXACT":
        try:
            value = float(Fraction(response.text.strip()))
        except (ValueError, ZeroDivisionError, OverflowError):
            raise fail(422, "SOCRATIC_RESPONSE_INVALID", "Enter a number, such as 21, -0.5 or 3/4.") from None
        if not math.isfinite(value):
            raise fail(422, "SOCRATIC_RESPONSE_INVALID", "Enter a finite number.")
        return {"value": value}
    return {"text": response.text}


def respond(preview_id: UUID, body: Respond, actor: StaffActor) -> dict:
    def apply(state, program):
        snapshot = _current_activity(state)
        if (body.current_node_key != state["current_node_key"] or body.activity_id != snapshot["activity_id"]
                or body.activity_revision != snapshot["revision"]):
            raise fail(409, "SOCRATIC_PREVIEW_STALE", "This screen is out of date; reload the preview.")
        try:
            evaluation = scoring.evaluate(snapshot["activity_type"], snapshot["options"], snapshot["policy"],
                                          _scorer_response(snapshot, body.response))
        except ValueError as exc:
            raise fail(422, "SOCRATIC_RESPONSE_INVALID", str(exc)) from None
        assisted = state["hint_level"] > 0 or state["revealed"]
        if evaluation.verdict == "CORRECT":
            outcome, feedback = ("UNCERTAIN", "CORRECT_AFTER_REVEAL") if state["revealed"] else ("SUCCESS", "CORRECT")
        elif evaluation.verdict == "INCORRECT":
            outcome, feedback = "RETRY", "INCORRECT"
        else:
            outcome, feedback = "UNCERTAIN", "UNCERTAIN"
        evidence = {"verdict": evaluation.verdict, "hint_level": state["hint_level"],
                    "revealed": state["revealed"], **evaluation.evidence}
        event = _move(state, program, outcome)
        event["decision_source"] = "DETERMINISTIC_EVALUATION:" + event["decision_source"]
        event["assisted"] = assisted
        state["feedback"] = FEEDBACK[feedback]
        return event, body.response.model_dump(mode="json"), evidence
    return _command(preview_id, "RESPOND", body, actor, apply)


def assist(preview_id: UUID, body: PreviewCommand, actor: StaffActor) -> dict:
    def apply(state, program):
        hints = _current_activity(state)["policy"].get("hints", [])
        if state["hint_level"] >= len(hints):
            raise fail(409, "SOCRATIC_NO_MORE_HINTS",
                       "No further approved hint for this activity." if hints else "This activity has no approved hints.")
        state["hint_level"] += 1
        node = state["current_node_key"]
        return {"node_key": node, "decision_source": "ASSISTANCE", "assisted": True,
                "reason": f"Hint H{state['hint_level']} disclosed; later success is recorded as assisted."}, None, None
    return _command(preview_id, "ASSIST", body, actor, apply)


def reveal(preview_id: UUID, body: PreviewCommand, actor: StaffActor) -> dict:
    def apply(state, program):
        explanation = _current_activity(state)["policy"].get("explanation")
        if state["revealed"]:
            raise fail(409, "SOCRATIC_ALREADY_REVEALED", "The explanation is already revealed.")
        if not isinstance(explanation, str) or not explanation.strip():
            raise fail(409, "SOCRATIC_NO_REVEAL_AVAILABLE", "This activity has no approved explanation.")
        state["revealed"] = True
        state["feedback"] = "Assisted reveal: " + explanation
        return {"node_key": state["current_node_key"], "decision_source": "ASSISTED_REVEAL", "assisted": True,
                "reason": "Explanation explicitly revealed; this is not independent success."}, None, None
    return _command(preview_id, "REVEAL", body, actor, apply)
