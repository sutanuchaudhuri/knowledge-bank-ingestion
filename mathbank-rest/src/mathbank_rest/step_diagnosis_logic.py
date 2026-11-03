"""Pure step-diagnosis logic shared by the PostgreSQL (``step_diagnosis``) and DynamoDB (``stores.learner.diagnosis``) backends.

No SQL, no I/O except the optional OpenAI re-rank call: scoring, the recommended action, the evidence fingerprint, the gap status
machine, the learner view and the re-rank validation. ``step_diagnosis`` re-exports every name, so existing imports keep working.

Rules (spec): persist every hypothesis, never overwrite one (only its status moves UNRESOLVED -> CONFIRMED/REJECTED,
CONFIRMED -> RESOLVED, each with a learner.event), never set mastery from a diagnosis, and never show canonical step text in probes.
"""
from __future__ import annotations

import hashlib
import json
import os

DIAGNOSER_VERSION = "rules-v1"
TRIGGERS = ("AUTO", "STUDENT_REQUEST", "TUTOR")
ACTIONS = ("RETRY_WITH_HINT", "DIAGNOSTIC_PROBE", "RECOVERY_DETOUR")
ACTION_LABELS = {
    "RETRY_WITH_HINT": "Have another go — a hint should be enough.",
    "DIAGNOSTIC_PROBE": "Try a short check on the skills below to pin down what is missing.",
    "RECOVERY_DETOUR": "Take a short detour to strengthen the first skill below, then come back to this step.",
}
LOCATION_LABELS = {
    "SKILL": "the skill this step uses", "TECHNIQUE": "the technique this step uses",
    "REPRESENTATION": "reading the figure or notation", "PREREQUISITE": "an earlier step this one builds on",
    "SUBCONCEPT": "the topic area", "CONCEPT": "a background concept",
}
OPEN_STATUSES = ("UNRESOLVED", "CONFIRMED")
MAX_HYPOTHESES = 5
RECOVERY_THRESHOLD = 0.6
AUTO_MIN_FAILED_TRIES = 2
AUTO_MIN_HELP = 3
CONCEPTUAL_MODES = {"NOT_RECOGNIZED", "MISUNDERSTOOD", "THEOREM_NOT_RECALLED", "WRONG_THEOREM_SELECTED",
                    "PROOF_CONNECTION_MISSING"}
LOCAL_LOCATIONS = {"SKILL", "TECHNIQUE", "REPRESENTATION"}


def _clamp(x: float) -> float:
    return round(min(0.95, max(0.05, x)), 3)


def likelihood_label(confidence: float) -> str:
    return "likely" if confidence >= RECOVERY_THRESHOLD else "possible" if confidence >= 0.35 else "worth checking"


def should_auto_diagnose(result: str, attempt_count: int, help_level: int) -> bool:
    """Auto-diagnose a FAILED step once the student has tried twice or needed strategic help."""
    return result == "FAILED" and (attempt_count >= AUTO_MIN_FAILED_TRIES or help_level >= AUTO_MIN_HELP)


def score_hypotheses(ctx: dict) -> list[dict]:
    """Rank gap hypotheses from a diagnosis context (see ``load_context``); deterministic, no I/O."""
    step, cur = ctx["step"], ctx["current"]
    grader_mode = cur.get("failure_mode") or "NONE"
    grader_loc = cur.get("failure_location") or "NONE"
    tries, help_ = int(cur.get("attempt_count") or 0), int(cur.get("help_level") or 0)
    hist = ctx.get("skill_history") or {}
    out: list[dict] = []

    # 1. local skill (diagnose the local failure first)
    c, ev = 0.45, []
    if tries > 1:
        c += 0.1 * min(tries - 1, 3); ev.append(f"failed_tries={tries}")
    if help_:
        c += 0.05 * min(help_, 4); ev.append(f"help_level={help_}")
    if hist.get("failed", 0):
        c += 0.1; ev.append(f"failed_same_skill_elsewhere={hist['failed']}")
    if hist.get("independent", 0) >= 2:
        c -= 0.15; ev.append(f"independent_same_skill_elsewhere={hist['independent']}")
    mode = grader_mode if grader_mode != "NONE" else "CANNOT_EXECUTE"
    if mode == "CARELESS":
        c -= 0.2; ev.append("grader_says_careless")
    if grader_loc == "PREREQUISITE":
        c -= 0.1; ev.append("grader_points_to_prerequisite")
    if grader_mode != "NONE":
        ev.append(f"grader_failure_mode={grader_mode}")
    label = step.get("skill_label")
    techniques = ctx.get("step_techniques") or []
    if techniques:
        ev.append("step_techniques=" + ",".join(t["technique_node_id"] for t in techniques))
        if grader_loc == "TECHNIQUE":
            label = techniques[0].get("name") or label
    out.append({"failure_location": grader_loc if grader_loc in LOCAL_LOCATIONS else "SKILL",
                "failure_mode": mode, "target_skill_id": step.get("skill_id"),
                "target_skill_node_id": step.get("skill_uuid"),
                "target_subconcept_id": step.get("subconcept_id"), "target_concept_id": step.get("concept_id"),
                "target_label": label, "source_step_id": None,
                "confidence": _clamp(c), "evidence": {"signals": ev}})

    # 2. skills of the steps this one DEPENDS_ON
    seen = {step.get("skill_id")}
    prereq_mode = grader_mode if grader_mode in CONCEPTUAL_MODES else "NOT_RECOGNIZED"
    for p in ctx.get("predecessors") or []:
        if not p.get("skill_id") or p["skill_id"] in seen:
            continue
        seen.add(p["skill_id"])
        c, ev = 0.25, [f"step_depends_on={p['step_id']}"]
        p_help = int(p.get("help_level") or 0)
        if p.get("state") == "FAILED" or p_help >= 5:
            c += 0.3; ev.append("prerequisite_step_failed_or_revealed")
        elif p_help >= 3:
            c += 0.2; ev.append(f"prerequisite_help_level={p_help}")
        elif p_help >= 1:
            c += 0.1; ev.append(f"prerequisite_help_level={p_help}")
        elif p.get("independent"):
            c -= 0.15; ev.append("prerequisite_step_solved_independently")
        ph = p.get("history") or {}
        if ph.get("failed", 0):
            c += 0.1; ev.append(f"failed_prerequisite_skill_elsewhere={ph['failed']}")
        if ph.get("independent", 0) >= 2:
            c -= 0.1; ev.append(f"independent_prerequisite_skill_elsewhere={ph['independent']}")
        if grader_loc == "PREREQUISITE":
            c += 0.1; ev.append("grader_points_to_prerequisite")
        out.append({"failure_location": "PREREQUISITE", "failure_mode": prereq_mode,
                    "target_skill_id": p["skill_id"], "target_skill_node_id": p.get("skill_uuid"),
                    "target_subconcept_id": p.get("subconcept_id"), "target_concept_id": p.get("concept_id"),
                    "target_label": p.get("skill_label"), "source_step_id": p["step_id"],
                    "confidence": _clamp(c), "evidence": {"signals": ev}})

    # 3. subconcept, when several different skills in it are failing in this attempt
    n = int(ctx.get("subconcept_failures") or 0)
    if n and step.get("subconcept_id"):
        out.append({"failure_location": "SUBCONCEPT", "failure_mode": "MISUNDERSTOOD", "target_skill_id": None,
                    "target_skill_node_id": None, "target_subconcept_id": step["subconcept_id"],
                    "target_concept_id": step.get("concept_id"), "target_label": step.get("subconcept_label"),
                    "source_step_id": None, "confidence": _clamp(0.3 + 0.15 * min(n, 3)),
                    "evidence": {"signals": [f"other_failed_skills_in_subconcept={n}"]}})

    # 4. concept prerequisites (sparse for Prasolov)
    for cp in (ctx.get("concept_prereqs") or [])[:2]:
        out.append({"failure_location": "CONCEPT", "failure_mode": "MISUNDERSTOOD", "target_skill_id": None,
                    "target_skill_node_id": None, "target_subconcept_id": None,
                    "target_concept_id": cp.get("concept_id"), "target_label": cp.get("label"),
                    "source_step_id": None, "confidence": _clamp(0.2 + (0.1 if grader_loc == "CONCEPT" else 0)),
                    "evidence": {"signals": ["concept_prerequisite_of_step_concept"]}})

    out.sort(key=lambda h: (-h["confidence"], h["failure_location"] != "SKILL"))
    for i, h in enumerate(out[:MAX_HYPOTHESES], start=1):
        h["rank"] = i
    return out[:MAX_HYPOTHESES]


def recommend_action(hypotheses: list[dict], ctx: dict) -> str:
    if not hypotheses:
        return "DIAGNOSTIC_PROBE"
    top = hypotheses[0]
    hist = ctx.get("skill_history") or {}
    if (ctx.get("current") or {}).get("failure_mode") == "CARELESS" or top["failure_mode"] == "CARELESS" or (
            top["failure_location"] in LOCAL_LOCATIONS and hist.get("independent", 0) >= 2
            and not hist.get("failed", 0)):
        return "RETRY_WITH_HINT"
    return "RECOVERY_DETOUR" if top["confidence"] >= RECOVERY_THRESHOLD else "DIAGNOSTIC_PROBE"


def evidence_fingerprint(ctx: dict) -> str:
    cur = ctx["current"]
    basis = {"tries": cur.get("attempt_count"), "help": cur.get("help_level"),
             "mode": cur.get("failure_mode"), "loc": cur.get("failure_location"),
             "preds": sorted((p["step_id"], p.get("state"), p.get("help_level")) for p in ctx.get("predecessors") or []),
             "subfail": ctx.get("subconcept_failures")}
    return hashlib.sha256(json.dumps(basis, sort_keys=True, default=str).encode()).hexdigest()[:32]


def gap_transition(status: str, result: str, independent: bool) -> str | None:
    """New status for an open hypothesis after a later outcome on the same skill (None = unchanged)."""
    if result == "FAILED":
        return "CONFIRMED" if status == "UNRESOLVED" else None
    if result == "SUCCESS" and independent:
        return {"UNRESOLVED": "REJECTED", "CONFIRMED": "RESOLVED"}.get(status)
    return None  # success with help or skipped: not enough evidence either way


def evidence_of(ctx: dict) -> dict:
    """The ``evidence`` document persisted with a diagnosis."""
    return {"current": ctx["current"], "skill_history": ctx["skill_history"],
            "predecessor_steps": [p["step_id"] for p in ctx["predecessors"]],
            "subconcept_failures": ctx["subconcept_failures"]}


def gap_matches_step(gap: dict, skill_id: str | None, subconcept_id: str | None) -> bool:
    """An open hypothesis is about the evaluated step when it targets the step's skill (or, for a subconcept hypothesis, its subconcept)."""
    if gap.get("target_skill_id") is not None:
        return gap["target_skill_id"] == skill_id
    return gap.get("failure_location") == "SUBCONCEPT" and gap.get("target_subconcept_id") == subconcept_id


# ---------------------------------------------------------------- learner view and optional AI re-rank

def apply_rerank(hypotheses: list[dict], ai_rerank: dict | None) -> list[dict]:
    """Hypotheses in the AI order when a valid permutation is stored; otherwise the rules order."""
    order = (ai_rerank or {}).get("order") or []
    by_id = {h.get("knowledge_gap_id"): h for h in hypotheses}
    if not order or None in by_id or sorted(order) != sorted(by_id):
        return list(hypotheses)
    return [by_id[g] for g in order]


def student_view(d: dict | None) -> dict | None:
    """What the learner sees: focus areas and a next move — no failure-mode labels, raw scores or evidence."""
    if d is None:
        return None
    rules_top = d["hypotheses"][0]["target_label"] if d["hypotheses"] else None
    hyps = apply_rerank(d["hypotheses"], d.get("ai_rerank"))
    return {
        "gap_diagnosis_id": d["gap_diagnosis_id"], "solution_step_id": d["solution_step_id"],
        "trigger": d["trigger"], "created_at": d["created_at"],
        "recommended_action": d["recommended_action"],
        "recommended_action_label": ACTION_LABELS[d["recommended_action"]],
        "ranked_by": "AI" if d.get("ai_rerank") else "RULES",
        "hypotheses": [{"rank": i + 1, "knowledge_gap_id": h.get("knowledge_gap_id"), "focus": h["failure_location"],
                        "focus_label": LOCATION_LABELS.get(h["failure_location"], h["failure_location"]),
                        "target_label": h["target_label"], "likelihood": likelihood_label(h["confidence"]),
                        "status": h["status"], "source_step_id": h["source_step_id"]} for i, h in enumerate(hyps)],
        "probes": d["probes"], "probe_target_label": rules_top,
    }


# The rules diagnoser is the floor: the model may only *reorder* the persisted hypotheses. It never adds, removes or relabels
# them, never changes confidence, status or the recommended action, and an invalid answer is discarded. Runs after the diagnosis
# commits, outside the attempt lock; one cached result per diagnosis. Off unless DIAGNOSIS_LLM_RERANK is truthy.

RERANK_MODEL = os.getenv("DIAGNOSIS_RERANK_MODEL", os.getenv("STEP_TUTOR_MODEL", "gpt-4.1-mini"))


def rerank_enabled() -> bool:
    return os.getenv("DIAGNOSIS_LLM_RERANK", "").strip().lower() in ("1", "true", "yes", "on")


def validate_rerank(answer: dict, hypotheses: list[dict]) -> list[str] | None:
    ids = [h["knowledge_gap_id"] for h in hypotheses]
    order = answer.get("order") if isinstance(answer, dict) else None
    if not isinstance(order, list) or len(order) != len(ids) or sorted(map(str, order)) != sorted(ids):
        return None
    return [str(g) for g in order]


def rerank_context_of(d: dict, step: dict | None) -> dict:
    """The model input for a stored diagnosis ``d`` and the step row (``step_type``, ``skill_name``) it is about."""
    step = step or {}
    current = (d.get("evidence") or {}).get("current") or {}
    return {"step_type": step.get("step_type"), "skill_name": step.get("skill_name"),
            "attempts": current.get("attempt_count"), "hints_used": current.get("help_level"),
            "last_verdict": current.get("verdict"), "last_failure_mode": current.get("failure_mode"),
            "last_failure_location": current.get("failure_location"),
            "hypotheses": [{"id": h["knowledge_gap_id"], "location": h["failure_location"],
                            "failure_mode": h["failure_mode"], "target": h["target_label"],
                            "rules_confidence": h["confidence"], "evidence": h["evidence"]}
                           for h in d["hypotheses"]]}


_RERANK_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["order", "rationale"],
                  "properties": {"order": {"type": "array", "items": {"type": "string"}},
                                 "rationale": {"type": "string"}}}


def openai_reranker(context: dict) -> dict:
    from mathbank_rest.step_tutor import _client

    response = _client().chat.completions.create(
        model=RERANK_MODEL, temperature=0,
        response_format={"type": "json_schema",
                         "json_schema": {"name": "gap_rerank", "strict": True, "schema": _RERANK_SCHEMA}},
        messages=[{"role": "system", "content": (
            "You review a rules-based diagnosis of why a student is stuck on one step of a geometry solution. "
            "Reorder the given hypothesis ids from most to least likely using the evidence. Return every id "
            "exactly once; do not invent ids. rationale: one sentence for the teacher.")},
            {"role": "user", "content": json.dumps(context, default=str)}])
    answer = json.loads(response.choices[0].message.content or "{}")
    answer["model"] = RERANK_MODEL
    return answer


def stored_rerank(answer: dict, order: list[str], hypotheses: list[dict]) -> dict:
    """The ``ai_rerank`` document persisted for a validated answer."""
    rules_order = [h["knowledge_gap_id"] for h in hypotheses]
    return {"order": order, "rationale": str(answer.get("rationale", ""))[:500], "model": answer.get("model", "injected"),
            "rules_order": rules_order, "changed": order != rules_order}
