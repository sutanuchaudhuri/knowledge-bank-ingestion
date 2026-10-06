import assert from "node:assert/strict";
import test from "node:test";
import { createImportHandlers, resolveImportRead, resolveImportWrite } from "../lib/adminImportsProxy.mjs";

const PKG = "11111111-2222-3333-4444-555555555555";
const URL_BASE = "http://localhost/api/rest/admin/imports";
const post = (body, origin = "http://localhost") => new Request(URL_BASE, {
  method: "POST", headers: { "Content-Type": "application/json", origin }, body: JSON.stringify(body) });

test("reads are allowlisted and validated", () => {
  assert.deepEqual(resolveImportRead(["packages"], new URLSearchParams("book=PRASOLOV_PGV1")),
    { path: "/v1/admin/imports/packages", query: { book: "PRASOLOV_PGV1" } });
  assert.equal(resolveImportRead(["packages", PKG, "conflicts"], new URLSearchParams("resolution_status=OPEN&limit=9999")).query.limit, 500);
  assert.ok(resolveImportRead(["packages", "nope"]).error);
  assert.ok(resolveImportRead(["packages", PKG, "issues"], new URLSearchParams("kind=DROP")).error);
  assert.ok(resolveImportRead(["reconciliation"], new URLSearchParams("book=x;drop")).error);
  assert.equal(resolveImportRead(["problems", "PRASOLOV_PGV1_CH14_P021", "dag"]).path,
    "/v1/admin/imports/problems/PRASOLOV_PGV1_CH14_P021/dag");
  assert.ok(resolveImportRead(["cypher"]).error);
  assert.ok(resolveImportRead([]).error);
});

test("writes map to the right REST method and path", () => {
  assert.deepEqual(resolveImportWrite({ action: "edit-step", step_id: "PRASOLOV_PGV1/STEP-1.37-A-01#2", is_checkpoint: true }),
    { method: "PATCH", path: "/v1/admin/imports/steps/PRASOLOV_PGV1%2FSTEP-1.37-A-01%232", payload: { is_checkpoint: true } });
  assert.equal(resolveImportWrite({ action: "upsert-dependency", from_step_id: "a" }).method, "PUT");
  assert.equal(resolveImportWrite({ action: "decide-conflict", id: 7, decision: "KEEP_EXISTING" }).path,
    "/v1/admin/imports/conflicts/7/decision");
  assert.ok(resolveImportWrite({ action: "decide-conflict", id: "7; drop" }).error);
  assert.ok(resolveImportWrite({ action: "review-learning-item", id: "x" }).error);
  assert.ok(resolveImportWrite({ action: "run-cypher" }).error);
  assert.ok(resolveImportWrite([]).error);
});

test("handlers enforce session, same-origin and pass REST errors through", async () => {
  let calls = 0;
  const denied = createImportHandlers({ hasSession: async () => false, get: async () => calls++, send: async () => calls++ });
  assert.equal((await denied.GET(new Request(`${URL_BASE}/packages`), ["packages"])).status, 401);
  assert.equal((await denied.POST(post({ action: "upsert-dependency" }))).status, 401);
  assert.equal(calls, 0);

  const sent = [];
  const ok = createImportHandlers({ hasSession: async () => true, get: async (p, q) => ({ p, q }),
    send: async (m, p, b) => { sent.push([m, p, b]); if (b.relationship_type === "DEPENDS_ON") { const e = new Error("cycle"); e.status = 409; throw e; } return { ok: true }; } });
  assert.equal((await ok.POST(post({ action: "upsert-dependency" }, "http://evil.example"))).status, 403);
  assert.equal(sent.length, 0);
  const r = await ok.POST(post({ action: "upsert-dependency", from_step_id: "a", to_step_id: "b", relationship_type: "DEPENDS_ON" }));
  assert.equal(r.status, 409);
  assert.deepEqual(sent[0][0], "PUT");
  const g = await ok.GET(new Request(`${URL_BASE}/reconciliation?graph=false`), ["reconciliation"]);
  assert.deepEqual(await g.json(), { p: "/v1/admin/imports/reconciliation", q: { graph: "false" } });
});
