import assert from "node:assert/strict";
import test from "node:test";
import { createTextbookHandlers, resolveTextbookRoute } from "../lib/adminTextbooksProxy.mjs";

const ID = "PRASOLOV-S-1_9-D01";
const r = (segs, s = "") => resolveTextbookRoute(segs, new URLSearchParams(s));

test("allowlisted read-only routes with clamped/validated filters", () => {
  assert.deepEqual(r(["coverage"]), { path: "/v1/admin/textbooks/coverage", query: {} });
  assert.deepEqual(r(["coverage"], "graph=false").query, { graph: "false" });
  assert.deepEqual(r(["problems"], "chapter=6&q=chord&limit=9999&has_diagram=true"),
    { path: "/v1/admin/textbooks/problems", query: { limit: 200, offset: 0, chapter: 6, q: "chord", has_diagram: "true" } });
  assert.equal(r(["problems", "PRASOLOV_PGV1_CH06_P076"]).path, "/v1/admin/textbooks/problems/PRASOLOV_PGV1_CH06_P076");
  assert.deepEqual(r(["learning-items"], "transformation_type=MCQ_FIRST_MOVE").query,
    { limit: 50, offset: 0, transformation_type: "MCQ_FIRST_MOVE" });
  assert.deepEqual(r(["taxonomy"], "node_type=SKILL").query, { limit: 100, offset: 0, node_type: "SKILL" });
  assert.equal(r(["taxonomy", "SKILL.GEO.X"]).path, "/v1/admin/textbooks/taxonomy/SKILL.GEO.X");
  assert.deepEqual(r(["diagrams", ID, "image"]), { path: `/v1/admin/textbooks/diagrams/${ID}/image`, query: {}, raw: true });
  for (const bad of [r(["problems", "../x"]), r(["problems"], "has_diagram=yes"), r(["taxonomy"], "node_type=X"),
    r(["learning-items"], "transformation_type=drop;"), r(["diagrams", "a/b", "image"]), r(["diagrams", "x y", "image"]), r(["admin"]), r([]),
    r(["problems", "A", "B"]), r(["coverage", "x"])]) assert.ok(bad.error);
});

test("admin session required; images stream through; upstream errors keep status", async () => {
  const anon = createTextbookHandlers({ hasSession: async () => false, get: () => assert.fail(), raw: () => assert.fail() });
  assert.equal((await anon.GET(new Request("http://l/x"), ["coverage"])).status, 401);
  const calls = [];
  const ok = createTextbookHandlers({ hasSession: async () => true,
    get: async (p, q) => { calls.push([p, q]); return { ok: 1 }; },
    raw: async () => new Response("PNG", { headers: { "content-type": "image/png" } }) });
  assert.equal((await ok.GET(new Request("http://l/x"), ["coverage"])).status, 200);
  assert.deepEqual(calls[0], ["/v1/admin/textbooks/coverage", {}]);
  const img = await ok.GET(new Request("http://l/x"), ["diagrams", ID, "image"]);
  assert.equal(img.headers.get("content-type"), "image/png");
  assert.equal(img.headers.get("cache-control"), "private, max-age=3600");
  assert.equal((await ok.GET(new Request("http://l/x"), ["nope"])).status, 400);
  const failing = createTextbookHandlers({ hasSession: async () => true, raw: () => {},
    get: async () => { throw Object.assign(new Error("missing"), { status: 404 }); } });
  assert.equal((await failing.GET(new Request("http://l/x"), ["problems", "X"])).status, 404);
});
