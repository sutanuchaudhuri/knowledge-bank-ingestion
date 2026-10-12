import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { createTutoringRoutesHandlers } from "../lib/tutoringRoutesProxy.mjs";
import { nodeMetadata } from "../lib/graphMetadata.mjs";
// graphConfig is plain JS in a package without type=module; import its source as ESM.
const config = await import(`data:text/javascript;base64,${readFileSync(new URL("../lib/graphConfig.js", import.meta.url)).toString("base64")}`);
const id = "11111111-1111-4111-8111-111111111111";

test("route graph relationships have correct endpoints and safe labels", () => {
  assert.equal(config.RELATIONSHIPS["step-produces"].to, "Claim");
  assert.equal(config.RELATIONSHIPS["misconception-remediation"].from, "Misconception");
  assert.equal(config.labelOf("RouteStep", { step_index: 3 }), "Checkpoint 3");
  assert.deepEqual(nodeMetadata({ route_release_id: id, step_index: 1, full_explanation: "SECRET", expected_answer: "SECRET" }),
    { route_release_id: id, step_index: 1 });
});
test("route admin proxy denies anonymous, cross-origin and path injection", async () => {
  let forwarded = false;
  const deps = { hasSession: async () => true, post: async () => { forwarded = true; }, get: async () => {}, invalidate() {} };
  const h = createTutoringRoutesHandlers(deps);
  assert.equal((await h.POST(new Request("http://localhost/api/routes", { method: "POST", headers: { origin: "http://evil.test" }, body: "{}" }))).status, 403);
  assert.equal((await h.GET(new Request("http://localhost/api/routes?release=../../secrets"))).status, 400);
  const anonymous = createTutoringRoutesHandlers({ ...deps, hasSession: async () => false });
  assert.equal((await anonymous.GET(new Request("http://localhost/api/routes"))).status, 401);
  assert.equal(forwarded, false);
});
test("review is forwarded server-side without implicitly publishing", async () => {
  const calls = [];
  const h = createTutoringRoutesHandlers({ hasSession: async () => true, get: async () => ({}),
    post: async (path, body) => { calls.push({ path, body }); return { status: "REVIEWED" }; }, invalidate() {} });
  const response = await h.POST(new Request("http://localhost/api/routes", { method: "POST",
    headers: { origin: "http://localhost", "Content-Type": "application/json" },
    body: JSON.stringify({ action: "review", release: id, expected_hash: "a".repeat(64),
      reviewer: "Reviewer", mathematical_review_confirmed: true }) }));
  assert.equal(response.status, 200);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, `/v1/admin/tutoring-routes/${id}/review`);
});
