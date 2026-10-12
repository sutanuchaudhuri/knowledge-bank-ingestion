import test from "node:test";
import assert from "node:assert/strict";
import { ActiveResponseClock, idleQuestionMessage, publicResponseWindow } from "../lib/tutorResponseWindow.mjs";
import { createAgentEventMapper } from "../lib/agentStream.mjs";

const window = { id: "1bdcbb22-98cf-413e-8b59-870557292dee", seconds: 30, action: "hint", question: "What is x?" };

test("response clock counts active time only and fires exactly once", () => {
  const clock = new ActiveResponseClock(30, 0);
  clock.update(0, false);
  assert.equal(clock.update(10000, false).seconds, 20);
  clock.update(12000, true);
  assert.equal(clock.update(72000, true).seconds, 18);
  clock.update(72000, false);
  assert.equal(clock.update(89999, false).expired, false);
  assert.equal(clock.update(90000, false).expired, true);
  assert.equal(clock.update(99000, false).expired, false);
});

test("clock never expires while paused, even with zero remaining", () => {
  const clock = new ActiveResponseClock(15, 0);
  clock.update(0, false);
  assert.equal(clock.update(15000, true).expired, false);
  assert.equal(clock.update(90000, true).expired, false);
  assert.equal(clock.update(90000, false).expired, true);
});

test("only bounded pacing metadata is projected from ADK state deltas", () => {
  const mapper = createAgentEventMapper();
  assert.deepEqual(mapper({ actions: { stateDelta: {
    "private:token": "SECRET", "tutor:response_window": { ...window, internal: "SECRET" },
  } } }), [{ type: "response-window", window }]);
  assert.deepEqual(mapper({ actions: { stateDelta: { "tutor:response_window": null } } }),
    [{ type: "response-window", window: null }]);
  assert.throws(() => publicResponseWindow({ ...window, seconds: 1 }), /invalid response window/);
  assert.throws(() => publicResponseWindow({ ...window, action: "grade" }), /invalid response window/);
  assert.equal(idleQuestionMessage(window), `[Tutor idle:${window.id}:hint]`);
});
