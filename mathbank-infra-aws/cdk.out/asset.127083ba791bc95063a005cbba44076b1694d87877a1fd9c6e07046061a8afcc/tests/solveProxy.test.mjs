import assert from "node:assert/strict";
import test from "node:test";
import { createSolveHandlers, resolveSolveRoute } from "../lib/solveProxy.mjs";

const STEP = "PRASOLOV_PGV1/STEP-1.1-A-01";

test("maps allowlisted routes and keeps slash step ids as one encoded segment", () => {
  assert.equal(resolveSolveRoute("POST", ["attempts", "a1", "responses", STEP]).path,
    "/v1/attempts/a1/steps/PRASOLOV_PGV1%2FSTEP-1.1-A-01/responses");
  assert.equal(resolveSolveRoute("GET", ["attempts", "a1"]).path, "/v1/attempts/a1/runtime");
  assert.equal(resolveSolveRoute("GET", ["practice", STEP]).path, "/v1/solution-steps/PRASOLOV_PGV1%2FSTEP-1.1-A-01/practice");
  assert.equal(resolveSolveRoute("GET", ["images", "../../etc"]).path, "/v1/problem-images/..%2F..%2Fetc");
  assert.equal(resolveSolveRoute("POST", ["attempts", "a1", "outcome", STEP]), null, "students cannot self-grade");
  assert.equal(resolveSolveRoute("DELETE", ["attempts", "a1"]), null);
  assert.equal(resolveSolveRoute("GET", ["admin"]), null);
});

test("diagnosis routes are allowlisted for the student; admin gap views are not", () => {
  const d = resolveSolveRoute("POST", ["attempts", "a1", "diagnose", STEP]);
  assert.equal(d.path, "/v1/attempts/a1/steps/PRASOLOV_PGV1%2FSTEP-1.1-A-01/diagnose");
  assert.equal(d.auth, true);
  assert.equal(resolveSolveRoute("GET", ["attempts", "a1", "diagnoses"]).path, "/v1/attempts/a1/diagnoses");
  assert.equal(resolveSolveRoute("GET", ["admin", "students", "s", "knowledge-gaps"]), null);
});

function handlers(overrides = {}) {
  const calls = [];
  const h = createSolveHandlers({
    getToken: async () => "jwt",
    get: async (path, token, query) => { calls.push(["GET", path, token, query]); return path === "/v1/learner/me" ? { student_id: "s-1" } : { ok: true }; },
    post: async (path, token, payload, headers) => { calls.push(["POST", path, token, payload, headers]); return { ok: true }; },
    raw: async () => new Response("png", { headers: { "content-type": "image/png" } }),
    ...overrides,
  });
  return { h, calls };
}

const post = (body, headers = {}) => new Request("http://localhost/api/rest/solve/x", {
  method: "POST", body: JSON.stringify(body), headers: { origin: "http://localhost", ...headers } });

test("start resolves the student from the token and forwards the idempotency key", async () => {
  const { h, calls } = handlers();
  const res = await h.POST(post({}, { "Idempotency-Key": "k1" }), ["start", "PRASOLOV_PGV1_CH01_P001"]);
  assert.equal(res.status, 200);
  assert.deepEqual(calls.at(-1), ["POST", "/v1/students/s-1/problems/PRASOLOV_PGV1_CH01_P001/attempts", "jwt", {}, { "Idempotency-Key": "k1" }]);
});

test("mutations require login and same origin; conflicts keep their status and code", async () => {
  assert.equal((await handlers({ getToken: async () => null }).h.POST(post({ state_version: 1 }), ["attempts", "a", "hint", STEP])).status, 401);
  const cross = new Request("http://localhost/x", { method: "POST", body: "{}", headers: { origin: "http://evil" } });
  assert.equal((await handlers().h.POST(cross, ["attempts", "a", "hint", STEP])).status, 403);
  const conflict = Object.assign(new Error(JSON.stringify({ code: "STATE_VERSION_CONFLICT" })), { status: 409 });
  const { h } = handlers({ post: async () => { throw conflict; } });
  const res = await h.POST(post({ state_version: 1 }), ["attempts", "a", "responses", STEP]);
  assert.equal(res.status, 409);
  assert.equal((await res.json()).error.code, "STATE_VERSION_CONFLICT");
});

test("diagrams are public and images stream through", async () => {
  const { h, calls } = handlers({ getToken: async () => null });
  assert.equal((await h.GET(new Request("http://localhost/x"), ["diagrams", "CODE"])).status, 200);
  assert.deepEqual(calls.at(-1).slice(0, 3), ["GET", "/v1/problems/by-code/CODE/diagrams", null]);
  const img = await h.GET(new Request("http://localhost/x"), ["images", "id-1"]);
  assert.equal(img.headers.get("content-type"), "image/png");
});

test("original document routes are public and stream PDFs, not arbitrary URLs", async () => {
  const { h, calls } = handlers({ getToken: async () => null,
    raw: async () => new Response("%PDF-fixture", { headers: { "content-type": "application/pdf" } }) });
  await h.GET(new Request("http://localhost/x"), ["source", "PAPER_SMT_2010_GEOM_Q06"]);
  assert.equal(calls.at(-1)[1], "/v1/problems/by-code/PAPER_SMT_2010_GEOM_Q06/source");
  const pdf = await h.GET(new Request("http://localhost/x"), ["source-pdf", "PAPER_SMT_2010_GEOM_Q06"]);
  assert.equal(pdf.headers.get("content-type"), "application/pdf");
  assert.equal(resolveSolveRoute("GET", ["source-pdf", "code", "solution"]), null);
  assert.equal(resolveSolveRoute("GET", ["source-highlight", "CODE"]).path, "/v1/problems/by-code/CODE/source-highlight");
  assert.equal(resolveSolveRoute("GET", ["source-marked-pdf", "CODE"]).path, "/v1/problems/by-code/CODE/source-marked-pdf");
  assert.equal(resolveSolveRoute("GET", ["source-marked-pdf", "CODE"]).raw, true);
  assert.equal(resolveSolveRoute("GET", ["source-highlight", "CODE", "other"]), null);
  assert.equal(resolveSolveRoute("GET", ["source-highlight", "CODE"], new URLSearchParams("page=2")).query.page, "2");
});

test("recovery detour routes are allowlisted for the student; admin plan views are not", () => {
  assert.equal(resolveSolveRoute("GET", ["recovery-plans", "p1"]).path, "/v1/recovery-plans/p1");
  assert.equal(resolveSolveRoute("GET", ["recovery-plans", "p1", "next"]).path, "/v1/recovery-plans/p1/next");
  assert.equal(resolveSolveRoute("GET", ["attempts", "a1", "recovery-plans"]).path, "/v1/attempts/a1/recovery-plans");
  const create = resolveSolveRoute("POST", ["attempts", "a1", "recovery-plans"]);
  assert.equal(create.path, "/v1/attempts/a1/recovery-plans");
  assert.equal(create.body, true);
  assert.equal(resolveSolveRoute("POST", ["recovery-plans", "p1", "items", "i/1"]).path, "/v1/recovery-plans/p1/items/i%2F1/responses");
  assert.equal(resolveSolveRoute("POST", ["recovery-plans", "p1", "resume"]).path, "/v1/recovery-plans/p1/resume");
  assert.equal(resolveSolveRoute("POST", ["recovery-plans", "p1", "abort"]).path, "/v1/recovery-plans/p1/abort");
  assert.equal(resolveSolveRoute("POST", ["recovery-plans", "p1", "delete"]), null);
  assert.equal(resolveSolveRoute("GET", ["admin", "recovery-plans"]), null);
});
test("feedback proxy is an authenticated allowlisted student mutation", () => {
  assert.deepEqual(resolveSolveRoute("POST", ["pedagogy-feedback"]), { path: "/v1/tutor/feedback", auth: true, body: true });
  assert.equal(resolveSolveRoute("GET", ["pedagogy-feedback"]), null);
  assert.equal(resolveSolveRoute("POST", ["pedagogy-feedback", "other"]), null);
});
