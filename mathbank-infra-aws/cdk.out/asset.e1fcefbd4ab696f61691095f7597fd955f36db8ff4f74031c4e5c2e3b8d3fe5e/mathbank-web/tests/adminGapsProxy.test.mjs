import assert from "node:assert/strict";
import test from "node:test";
import { createAdminGapHandlers, resolveAdminGapRoute } from "../lib/adminGapsProxy.mjs";

const ID = "0b0e5d1c-7a35-4e8f-9d0c-111111111111";
const q = (s) => resolveAdminGapRoute(new URLSearchParams(s));

test("allowlisted read-only views with validated filters", () => {
  assert.deepEqual(q(""), { path: "/v1/admin/knowledge-gaps", query: { limit: 100 } });
  assert.deepEqual(q("view=gaps&status=CONFIRMED&student=ann&limit=9999"),
    { path: "/v1/admin/knowledge-gaps", query: { limit: 500, status: "CONFIRMED", student: "ann" } });
  assert.deepEqual(q(`view=plans&status=EXHAUSTED&student_id=${ID}&limit=0`),
    { path: "/v1/admin/recovery-plans", query: { limit: 1, status: "EXHAUSTED", student_id: ID } });
  assert.equal(q(`view=plan&id=${ID}`).path, `/v1/admin/recovery-plans/${ID}`);
  assert.ok(q("view=gaps&status=DROP").error);
  assert.ok(q("view=plans&status=RESOLVED").error);
  assert.ok(q("view=plans&student_id=x").error);
  assert.ok(q("view=plan&id=../../x").error);
  assert.ok(q("view=students").error);
});

test("requires an admin session; bad views are 400; upstream errors keep their status", async () => {
  const calls = [];
  const ok = createAdminGapHandlers({ hasSession: async () => true, get: async (p, qq) => { calls.push([p, qq]); return { totals: {} }; } });
  assert.equal((await ok.GET(new Request("http://localhost/x?view=gaps"))).status, 200);
  assert.deepEqual(calls[0], ["/v1/admin/knowledge-gaps", { limit: 100 }]);
  assert.equal((await ok.GET(new Request("http://localhost/x?view=nope"))).status, 400);
  const anon = createAdminGapHandlers({ hasSession: async () => false, get: async () => assert.fail("must not call upstream") });
  assert.equal((await anon.GET(new Request("http://localhost/x"))).status, 401);
  const failing = createAdminGapHandlers({ hasSession: async () => true,
    get: async () => { throw Object.assign(new Error("missing"), { status: 404 }); } });
  assert.equal((await failing.GET(new Request(`http://localhost/x?view=plan&id=${ID}`))).status, 404);
  assert.equal(createAdminGapHandlers({ hasSession: async () => true, get: async () => ({}) }).POST, undefined);
});
