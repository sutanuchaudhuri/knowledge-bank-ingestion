import assert from "node:assert/strict";
import test from "node:test";
import { createAdminPedagogyHandlers } from "../lib/adminPedagogyProxy.mjs";
import { invalidateGraphCache, withCache } from "../lib/cache.js";

const URL = "http://localhost/api/rest/admin/pedagogy";
const request = (body, origin = "http://localhost") => new Request(URL, {
  method: "POST", headers: { "Content-Type": "application/json", origin },
  body: JSON.stringify(body),
});
const defaults = { hasSession: async () => true, get: async () => ({}),
  post: async () => ({}), invalidate: () => {} };

test("unauthenticated admin proxies never call REST", async () => {
  let calls = 0;
  const handlers = createAdminPedagogyHandlers({ ...defaults, hasSession: async () => false,
    get: async () => calls++, post: async () => calls++ });
  assert.equal((await handlers.GET(new Request(URL))).status, 401);
  assert.equal((await handlers.POST(request({ action: "approve-starter" }))).status, 401);
  assert.equal(calls, 0);
});

test("mutations require same-origin requests and valid actions", async () => {
  let calls = 0;
  const handlers = createAdminPedagogyHandlers({ ...defaults, post: async () => calls++ });
  assert.equal((await handlers.POST(request({ action: "review" }, "https://evil.example"))).status, 403);
  assert.equal((await handlers.POST(request({ action: "review" }, ""))).status, 403);
  assert.equal((await handlers.POST(request({ action: "../learner/attempts" }))).status, 400);
  assert.equal((await handlers.POST(request(null))).status, 400);
  assert.equal(calls, 0);
});

test("forwards allowlisted bulk actions and invalidates graph cache only after publish", async () => {
  const calls = [];
  let invalidations = 0;
  const handlers = createAdminPedagogyHandlers({ ...defaults,
    post: async (path, body) => { calls.push([path, body]); return { updated: 27 }; },
    invalidate: () => invalidations++ });
  for (const action of ["review", "bulk-review", "approve-starter", "history"]) {
    assert.equal((await handlers.POST(request({ action, note: "Operator approval" }))).status, 200);
  }
  assert.equal(invalidations, 0);
  assert.equal((await handlers.POST(request({ action: "publish", expected_fingerprint: "hash" }))).status, 200);
  assert.equal(invalidations, 1);
  assert.deepEqual(calls.at(-1), ["/v1/admin/pedagogy/publish", { expected_fingerprint: "hash" }]);
});

test("preserves stale-review and publication errors without invalidating", async () => {
  let invalidations = 0;
  const handlers = createAdminPedagogyHandlers({ ...defaults,
    post: async () => { const err = new Error("Reload"); err.status = 409; throw err; },
    invalidate: () => invalidations++ });
  const response = await handlers.POST(request({ action: "publish" }));
  assert.equal(response.status, 409);
  assert.equal((await response.json()).error, "Reload");
  assert.equal(invalidations, 0);
});

test("queue only forwards bounded named filters to the authenticated backend", async () => {
  const calls = [];
  const handlers = createAdminPedagogyHandlers({ ...defaults,
    get: async (...args) => { calls.push(args); return { items: [] }; } });
  assert.equal((await handlers.GET(new Request(`${URL}?kind=skill&status=PENDING&limit=25&offset=0`))).status, 200);
  assert.equal((await handlers.GET(new Request(`${URL}?secret=key`))).status, 400);
  assert.deepEqual(calls[0], ["/v1/admin/pedagogy/queue",
    { kind: "skill", status: "PENDING", limit: "25", offset: "0" }]);
});

test("publication invalidation cannot be undone by an old in-flight graph read", async () => {
  let finish;
  const pending = withCache("graph:test-inflight", 60000, () => new Promise(resolve => { finish = resolve; }));
  invalidateGraphCache();
  finish("old");
  assert.equal(await pending, "old");
  assert.equal(await withCache("graph:test-inflight", 60000, async () => "new"), "new");
  invalidateGraphCache();
});
