import assert from "node:assert/strict";
import test from "node:test";
import { DECISION_NOTES, currentRecoveryItem, inRecovery, masterySummary, probeLabel, recoveryOutcome, recoveryPayload, recoveryStageProgress, ACTION_BADGES, canDiagnose, feedbackTone, gapStatusLabel, hasStepSolution, hintSummary, isConflict, likelihoodTone, nextHintLevel, probeHref, progressPercent, stepLabel, timelineStatus } from "../lib/solveFlow.mjs";

test("timeline follows the spec-14 legend", () => {
  assert.equal(timelineStatus({ state: "SUCCESS_INDEPENDENT" }).icon, "✓");
  assert.equal(timelineStatus({ state: "SUCCESS_WITH_HELP" }).tone, "warning");
  assert.equal(timelineStatus({ state: "PRESENTED", is_current: true }).icon, "●");
  assert.equal(timelineStatus({ state: "RETRY_PRESENTED", is_current: true }).icon, "!");
  assert.equal(timelineStatus({ state: "LOCKED" }).icon, "○");
});

test("hint ladder escalates to a reveal and stops", () => {
  assert.equal(nextHintLevel(0).level, 1);
  assert.equal(nextHintLevel(4).label, "Reveal");
  assert.equal(nextHintLevel(5), null);
  assert.match(hintSummary(0), /independent/);
  assert.equal(hintSummary(2), "You used 2 hints on this step.");
});

test("labels, progress, feedback tone, conflicts and eligibility", () => {
  assert.equal(stepLabel({ part_label: "MAIN", step_index_in_part: 2 }), "Solution · step 2");
  assert.equal(stepLabel({ part_label: "B", step_index_in_part: 1 }), "Part B · step 1");
  assert.equal(progressPercent({ total_steps: 3, completed_steps: 1 }), 33);
  assert.equal(progressPercent({ total_steps: 0 }), 0);
  assert.equal(feedbackTone({ result: "SUCCESS" }), "success");
  assert.equal(feedbackTone({ result: "FAILED", verdict: "PARTIALLY_CORRECT" }), "warning");
  assert.ok(isConflict(409, { error: { code: "STATE_VERSION_CONFLICT" } }));
  assert.ok(!isConflict(409, { error: { code: "INVALID_TRANSITION" } }));
  assert.ok(hasStepSolution("PRASOLOV_PGV1_CH01_P001") && !hasStepSolution("HMMT_2020_FEB_ALG_1"));
});

test("diagnosis helpers gate on effort and never link learning items as problems", () => {
  assert.equal(canDiagnose(null), false);
  assert.equal(canDiagnose({ attempt_count: 0, help_level_used: 0 }), false);
  assert.equal(canDiagnose({ attempt_count: 1, help_level_used: 0 }), true);
  assert.equal(canDiagnose({ attempt_count: 0, help_level_used: 2 }), true);
  assert.equal(likelihoodTone("likely"), "danger");
  assert.equal(likelihoodTone("worth checking"), "secondary");
  assert.equal(gapStatusLabel("REJECTED"), "Ruled out");
  assert.equal(probeHref({ kind: "PRACTICE_STEP", problem_code: "PRASOLOV_PGV1_CH01_P001" }), "/learn/solve/PRASOLOV_PGV1_CH01_P001");
  assert.equal(probeHref({ kind: "LEARNING_ITEM", learning_item_id: "x" }), null);
  assert.ok(ACTION_BADGES.RECOVERY_DETOUR && ACTION_BADGES.DIAGNOSTIC_PROBE && ACTION_BADGES.RETRY_WITH_HINT);
});

test("recovery detour helpers", () => {
  const runtime = { attempt: { current_mode: "RECOVERY" }, recovery: { recovery_plan_id: "p" } };
  assert.equal(inRecovery(runtime), true);
  assert.equal(inRecovery({ attempt: { current_mode: "SOLVING" }, recovery: null }), false);
  const plan = { status: "ACTIVE", current_item_ordinal: 3, items: [
    { ordinal: 1, stage: "FOUNDATION", status: "PASSED", item_kind: "THEORY" },
    { ordinal: 2, stage: "RECOGNITION", status: "FAILED", item_kind: "LEARNING_ITEM" },
    { ordinal: 3, stage: "ISOLATED_EXECUTION", status: "PRESENTED", item_kind: "LEARNING_ITEM", content: { form: "SUBPROBLEM" } },
    { ordinal: 4, stage: "TRANSFER", status: "PENDING", item_kind: "LEARNING_ITEM" },
    { ordinal: 5, stage: "RETURN_TO_STEP", status: "PENDING", item_kind: "RETURN" },
  ] };
  assert.equal(currentRecoveryItem(plan).ordinal, 3);
  assert.deepEqual(recoveryStageProgress(plan).map((s) => s.state), ["done", "failed", "current", "todo", "todo"]);
  assert.deepEqual(recoveryPayload(plan.items[0]), { acknowledged: true });
  assert.equal(recoveryPayload(plan.items[2], { text: "  " }), null);
  assert.deepEqual(recoveryPayload(plan.items[2], { text: "AB = 2" }), { response_text: "AB = 2" });
  const mcq = { item_kind: "LEARNING_ITEM", content: { form: "MCQ" } };
  assert.equal(recoveryPayload(mcq, {}), null);
  assert.deepEqual(recoveryPayload(mcq, { choiceIndex: 0 }), { choice_index: 0 });
  assert.match(masterySummary({ independent_successes: 1, independent_successes_required: 2, transfer_required: true, transfer_passed: false }), /1 of 2.*to go/);
  assert.match(masterySummary({ independent_successes: 3, independent_successes_required: 2, transfer_required: true, transfer_passed: true }), /goal met \(3 ✓\).*passed/);
  assert.equal(recoveryOutcome(plan), null);
  assert.equal(recoveryOutcome({ status: "COMPLETED" }).tone, "success");
  assert.equal(recoveryOutcome({ status: "EXHAUSTED" }).tone, "warning");
  for (const d of ["RETRY", "CONFIRM", "ALTERNATE", "BRANCH"]) assert.ok(DECISION_NOTES[d]);
  assert.deepEqual(probeLabel({ kind: "LEARNING_ITEM", transformation_type: "MCQ_FIRST_MOVE", problem_code: "P2" }),
    { title: "Pick the first move", detail: "from P2" });
  assert.equal(probeLabel({ kind: "PRACTICE_STEP", problem_code: "P3", step_type: "CALCULATION" }).title, "P3");
});
