// Pure helpers for the step-by-step solve workspace (v2 Phase 7, runtime_extension/14).

export const HINT_LADDER = [
  { level: 1, label: "Nudge", detail: "A guiding question" },
  { level: 2, label: "Concept", detail: "Reminder of the idea to use" },
  { level: 3, label: "Strategy", detail: "How to approach this step" },
  { level: 4, label: "Near-explicit", detail: "Almost the whole step" },
  { level: 5, label: "Reveal", detail: "Show the reference step" },
];

// spec 14: ✓ independent, ✓ with help, ● current, ! needs recovery/retry, ○ locked
export function timelineStatus(entry) {
  if (entry.state === "SUCCESS_INDEPENDENT") return { icon: "✓", tone: "success", label: "Solved independently" };
  if (entry.state === "SUCCESS_WITH_HELP") return { icon: "✓", tone: "warning", label: "Solved with help" };
  if (entry.state === "SKIPPED") return { icon: "↷", tone: "secondary", label: "Skipped" };
  if (entry.state === "FAILED" || entry.state === "RETRY_PRESENTED")
    return { icon: "!", tone: "danger", label: entry.is_current ? "Try again" : "Needs another look" };
  if (entry.is_current) return { icon: "●", tone: "primary", label: "Current step" };
  if (entry.state === "LOCKED") return { icon: "○", tone: "light", label: "Locked" };
  return { icon: "●", tone: "primary", label: "In progress" };
}

export function humanize(code) {
  return (code || "").toLowerCase().replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export function hintSummary(used) {
  if (!used) return "No hints used on this step — success now counts as independent.";
  return `You used ${used} hint${used === 1 ? "" : "s"} on this step.`;
}

export function nextHintLevel(used) {
  return used >= 5 ? null : HINT_LADDER[used];
}

export function progressPercent(progress) {
  if (!progress?.total_steps) return 0;
  return Math.round((100 * progress.completed_steps) / progress.total_steps);
}

export function feedbackTone(evaluation) {
  if (!evaluation) return null;
  if (evaluation.result === "SUCCESS") return "success";
  return evaluation.verdict === "PARTIALLY_CORRECT" ? "warning" : "danger";
}

export function isConflict(status, body) {
  return status === 409 && body?.error?.code === "STATE_VERSION_CONFLICT";
}

// "Part A · step 2", or "Main solution · step 2"
export function stepLabel(entry) {
  const part = entry.part_label === "MAIN" || !entry.part_label ? "Solution" : `Part ${entry.part_label}`;
  return entry.step_index_in_part ? `${part} · step ${entry.step_index_in_part}` : part;
}

// Only the imported textbook corpus (Prasolov) has a published step DAG today; the workspace still
// handles a 409 "no published solution steps" gracefully for anything else.
export function hasStepSolution(code) {
  return typeof code === "string" && code.startsWith("PRASOLOV_");
}

// Phase 9 gap diagnosis: only after the student has actually tried or asked for help on the step.
export function canDiagnose(step) {
  return Boolean(step) && ((step.attempt_count || 0) > 0 || (step.help_level_used || 0) > 0);
}

export function likelihoodTone(likelihood) {
  return { likely: "danger", possible: "warning" }[likelihood] || "secondary";
}

export const ACTION_BADGES = {
  RECOVERY_DETOUR: { tone: "danger", label: "Short detour suggested" },
  DIAGNOSTIC_PROBE: { tone: "warning", label: "Quick check suggested" },
  RETRY_WITH_HINT: { tone: "success", label: "Try again" },
};

export function gapStatusLabel(status) {
  return { CONFIRMED: "Confirmed", REJECTED: "Ruled out", RESOLVED: "Fixed", UNRESOLVED: "Open" }[status] || status;
}

export function probeHref(probe) {
  return probe?.kind === "PRACTICE_STEP" && probe.problem_code ? `/learn/solve/${encodeURIComponent(probe.problem_code)}` : null;
}

// Learning-item probes are short checks drawn from other problems; practice-step probes link to a problem.
export function probeLabel(probe) {
  if (probe?.kind === "LEARNING_ITEM") {
    const what = RECOVERY_TYPE_LABELS[probe.transformation_type] || humanize(probe.transformation_type);
    return { title: what, detail: probe.problem_code ? `from ${probe.problem_code}` : humanize(probe.transformed_form) };
  }
  return { title: probe?.problem_code || "Practice step", detail: humanize(probe?.step_type) };
}

// ---------------------------------------------------------------- Phase 10 recovery detour

export const RECOVERY_STAGES = [
  { stage: "FOUNDATION", label: "Worked example" },
  { stage: "RECOGNITION", label: "Recognise" },
  { stage: "ISOLATED_EXECUTION", label: "Use it once" },
  { stage: "GUIDED_APPLICATION", label: "In context" },
  { stage: "TRANSFER", label: "Somewhere new" },
  { stage: "RETURN_TO_STEP", label: "Back to problem" },
];

export const RECOVERY_TYPE_LABELS = {
  MCQ_METHOD_RECOGNITION: "Which method fits?", MCQ_LOCAL_GOAL: "What is the local goal?",
  MCQ_FIRST_MOVE: "Pick the first move", MCQ_INTERMEDIATE_SKILL: "Pick the intermediate result",
  MCQ_STEP_SEQUENCE: "Order the reasoning", SUBPROBLEM_FIRST_MOVE: "Make the first move",
  SUBPROBLEM_NEXT_INTERMEDIATE: "Reach the next result",
};

export function inRecovery(runtime) {
  return runtime?.attempt?.current_mode === "RECOVERY" && Boolean(runtime?.recovery?.recovery_plan_id);
}

export function currentRecoveryItem(plan) {
  return plan?.items?.find((i) => i.ordinal === plan.current_item_ordinal) || null;
}

// One pill per stage present in the plan: done / current / todo / failed.
export function recoveryStageProgress(plan) {
  const items = plan?.items || [];
  const current = currentRecoveryItem(plan);
  return RECOVERY_STAGES.filter((s) => items.some((i) => i.stage === s.stage)).map((s) => {
    const mine = items.filter((i) => i.stage === s.stage);
    let state = "todo";
    if (current?.stage === s.stage && plan.status === "ACTIVE") state = "current";
    else if (mine.every((i) => ["PASSED", "FAILED", "SKIPPED"].includes(i.status)))
      state = mine.some((i) => i.status === "PASSED") ? "done" : "failed";
    return { ...s, state, count: mine.length };
  });
}

export function recoveryPayload(item, { choiceIndex, text } = {}) {
  if (!item) return null;
  if (item.item_kind === "THEORY") return { acknowledged: true };
  if (item.content?.form === "MCQ") return Number.isInteger(choiceIndex) ? { choice_index: choiceIndex } : null;
  return text && text.trim() ? { response_text: text } : null;
}

export function masterySummary(mastery) {
  if (!mastery) return "";
  const transfer = mastery.transfer_required ? (mastery.transfer_passed ? " · new-context check passed" : " · new-context check to go") : "";
  const have = mastery.independent_successes, need = mastery.independent_successes_required;
  const first = have >= need ? `first-try goal met (${have} ✓)` : `${have} of ${need} first-try successes`;
  return `${first}${transfer}`;
}

export function recoveryOutcome(plan) {
  if (plan?.status === "COMPLETED") return { tone: "success", title: "Skill strengthened",
    text: "You met the practice goal. Head back and use it on the step where you were stuck." };
  if (plan?.status === "EXHAUSTED") return { tone: "warning", title: "Practice finished",
    text: "This skill still needs work — the tutor will keep an eye on it. Go back and give the step another try with hints." };
  return null;
}

export const DECISION_NOTES = {
  RETRY: "Not quite — have another go at this one.",
  CONFIRM: "Got it with a second try. One more similar question to make sure it sticks.",
  ALTERNATE: "Let's try a different question on the same idea.",
  BRANCH: "Let's strengthen a building block first.",
};
