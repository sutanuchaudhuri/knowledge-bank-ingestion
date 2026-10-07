import assert from "node:assert/strict";
import test from "node:test";
import { assessedAccuracy, attemptResult } from "../lib/attemptHistory.mjs";

test("ungraded approved attempts await assessment rather than showing incorrect", () => {
  assert.equal(attemptResult(null).label, "Awaiting assessment");
  assert.equal(attemptResult(undefined).tone, "warning");
  assert.equal(attemptResult(false).label, "Not yet");
  assert.equal(attemptResult(true).label, "Correct");
});
test("accuracy excludes ungraded attempts from numerator and denominator", () => {
  assert.equal(assessedAccuracy([{ is_correct: true }, { is_correct: false }, { is_correct: null }]), 50);
  assert.equal(assessedAccuracy([{ is_correct: null }]), null);
  assert.equal(assessedAccuracy([]), null);
});
