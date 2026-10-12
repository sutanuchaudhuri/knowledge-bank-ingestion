import assert from "node:assert/strict";
import test from "node:test";
import {
  createAdminConversationHandlers, createLearnerConversationHandlers,
  resolveAdminConversationRoute, resolveLearnerConversationRoute,
} from "../lib/conversationsProxy.mjs";

test("learner routes are allowlisted and session ids validated", () => {
  assert.deepEqual(resolveLearnerConversationRoute([]), { path: "/v1/learner/agent-sessions", query: { limit: 50 } });
  assert.equal(resolveLearnerConversationRoute(["web-1-abc"]).path, "/v1/learner/agent-sessions/web-1-abc/transcript");
  assert.equal(resolveLearnerConversationRoute(["../admin"]), null);
  assert.equal(resolveLearnerConversationRoute(["a", "b"]), null);
});

test("admin routes: list with student filter or one transcript", () => {
  assert.deepEqual(resolveAdminConversationRoute(new URLSearchParams("student=a@b.c")),
    { path: "/v1/admin/agent-sessions", query: { limit: 100, student: "a@b.c" } });
  assert.equal(resolveAdminConversationRoute(new URLSearchParams("id=web-1")).path, "/v1/admin/agent-sessions/web-1/transcript");
  assert.ok(resolveAdminConversationRoute(new URLSearchParams("id=a b")).error);
});

test("learner handler requires the student cookie and forwards the token", async () => {
  const seen = [];
  const h = createLearnerConversationHandlers({ getToken: async () => null, get: async () => ({}) });
  assert.equal((await h.GET(new Request("http://x/"), [])).status, 401);
  const ok = createLearnerConversationHandlers({ getToken: async () => "tok", get: async (p, t) => { seen.push([p, t]); return []; } });
  assert.equal((await ok.GET(new Request("http://x/"), [])).status, 200);
  assert.deepEqual(seen, [["/v1/learner/agent-sessions", "tok"]]);
  assert.equal((await ok.GET(new Request("http://x/"), ["a", "b"])).status, 404);
});

test("admin handler requires an admin session and maps upstream errors", async () => {
  const no = createAdminConversationHandlers({ hasSession: async () => false, get: async () => ({}) });
  assert.equal((await no.GET(new Request("http://x/api?id=s"))).status, 401);
  const err = Object.assign(new Error("missing"), { status: 404 });
  const yes = createAdminConversationHandlers({ hasSession: async () => true, get: async () => { throw err; } });
  assert.equal((await yes.GET(new Request("http://x/api?id=s"))).status, 404);
  assert.equal((await yes.GET(new Request("http://x/api?id=bad%20id"))).status, 400);
});
