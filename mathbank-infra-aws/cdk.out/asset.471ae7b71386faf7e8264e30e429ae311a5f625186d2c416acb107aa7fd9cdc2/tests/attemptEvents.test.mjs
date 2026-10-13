import assert from "node:assert/strict";
import test from "node:test";
import { createAttemptReplay } from "../lib/attemptEvents.mjs";
const sid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";

test("private replay is owner-checked, sequenced and does not repeat delivered events", async () => {
  const emitted = [];
  const requests = [];
  const replay = createAttemptReplay({ actor: { role: "STUDENT", token: "synthetic" },
    emit: (...args) => emitted.push(args),
    rest: async (req) => { requests.push(req); return { events: req.path.endsWith("=0")
      ? [{ event_type: "attempt.transcription.ready", sequence: 1 }] : [] }; } });
  try {
    await replay.watch(sid);
    await replay.tick();
    assert.equal(emitted.length, 1);
    assert.match(requests[1].path, /after_sequence=1$/);
    assert.equal(requests[0].headers.Authorization, "Bearer synthetic");
    await assert.rejects(() => replay.watch("../bad"), /Invalid submission_id/);
  } finally { replay.close(); }
});
test("denied ownership never emits private work", async () => {
  const emitted = [];
  const replay = createAttemptReplay({ actor: { role: "STUDENT", token: "synthetic" },
    emit: (...args) => emitted.push(args),
    rest: async () => { throw Object.assign(new Error("not found"), { status: 404 }); } });
  try { await assert.rejects(() => replay.watch(sid), /not found/); assert.equal(emitted.length, 0); }
  finally { replay.close(); }
});
