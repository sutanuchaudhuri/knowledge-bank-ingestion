import assert from "node:assert/strict";
import test from "node:test";
import { createPrivateRuntimeHandler, MAX_MEDIA_BYTES } from "../lib/privateRuntimeProxy.mjs";
import { currentAssessment, intervalLabel, runtimeErrorMessage, transcriptionPayload } from "../lib/attemptMedia.mjs";

const id = "11111111-1111-4111-8111-111111111111";
const asset = "22222222-2222-4222-8222-222222222222";
function setup(overrides = {}) {
  const calls = [];
  const handle = createPrivateRuntimeHandler({
    domain: "attempt-media", getToken: async () => "student-token", hasAdmin: async () => false,
    adminKey: "admin-key", baseUrl: "http://local.test",
    fetcher: async (url, options) => { calls.push({ url, options }); return Response.json({ saved: true }); },
    ...overrides,
  });
  const send = (method, path, body, headers = {}) => handle(new Request(`http://browser.test/api/${path}`, {
    method, headers: { ...(body !== undefined ? { "content-type": "application/json" } : {}), ...headers },
    ...(body !== undefined ? { body: typeof body === "string" ? body : JSON.stringify(body) } : {}),
  }), path.split("?")[0].split("/"));
  return { calls, send };
}
test("student authentication never forwards browser credentials or an admin key", async () => {
  const { calls, send } = setup();
  const res = await send("GET", `submissions/${id}`, undefined, { Authorization: "Bearer injected", "X-Admin-Api-Key": "injected" });
  assert.equal(res.status, 200);
  assert.deepEqual(calls[0].options.headers, { Authorization: "Bearer student-token" });
  assert.equal(calls[0].options.cache, "no-store");
  assert.equal(calls[0].options.redirect, "error");
  assert.match(res.headers.get("cache-control"), /private, no-store/);
});
test("anonymous and unauthorized override requests stop before upstream", async () => {
  const anonymous = setup({ getToken: async () => null });
  assert.equal((await anonymous.send("GET", "submissions")).status, 401);
  assert.equal(anonymous.calls.length, 0);
  const student = setup();
  assert.equal((await student.send("POST", `submissions/${id}/override`, {})).status, 403);
  assert.equal(student.calls.length, 0);
});
test("only a verified admin session attaches the configured key", async () => {
  const { send, calls } = setup({ hasAdmin: async () => true });
  assert.equal((await send("POST", `submissions/${id}/override`, { expected_version: 1 })).status, 200);
  assert.equal(calls[0].options.headers["X-Admin-Api-Key"], "admin-key");
  assert.equal(calls[0].options.headers.Authorization, undefined);
});
test("allowlist rejects arbitrary paths, methods, IDs and queries", async () => {
  const { send, calls } = setup();
  for (const [method, path] of [["GET", "submissions/../admin"], ["GET", "submissions/no-id"], ["PUT", "submissions"], ["DELETE", `submissions/${id}`], ["POST", `submissions/${id}/generate`]]) {
    assert.equal((await send(method, path)).status, 404);
  }
  assert.equal((await send("GET", "submissions?owner_id=other")).status, 400);
  assert.equal((await send("GET", "submissions?offset=-1")).status, 400);
  assert.equal(calls.length, 0);
});
test("raw uploads preserve MIME and version, reject executable content and oversized bodies", async () => {
  const { send, calls } = setup();
  const path = `submissions/${id}/assets?filename=work.png&expected_version=3`;
  assert.equal((await send("POST", path, "image-bytes", { "content-type": "image/png" })).status, 200);
  assert.equal(calls[0].options.headers["Content-Type"], "image/png");
  assert.equal(calls[0].url.searchParams.get("expected_version"), "3");
  assert.equal((await send("POST", path, "<svg/>", { "content-type": "image/svg+xml" })).status, 415);
  assert.equal((await send("POST", path, "x", { "content-type": "image/png", "content-length": String(MAX_MEDIA_BYTES + 1) })).status, 413);
});
test("binary errors, MIME and ranges are preserved without caching", async () => {
  const { send, calls } = setup({ fetcher: async (url, options) => {
    calls.push({ url, options });
    return new Response(new Uint8Array([1, 2, 3]), { status: 206, headers: { "Content-Type": "audio/mpeg", "Content-Range": "bytes 0-2/10", "Accept-Ranges": "bytes" } });
  } });
  const res = await send("GET", `submissions/${id}/assets/${asset}/content`, undefined, { Range: "bytes=0-2" });
  assert.equal(res.status, 206);
  assert.equal(res.headers.get("content-type"), "audio/mpeg");
  assert.equal(calls[0].options.headers.Range, "bytes=0-2");
  assert.deepEqual([...new Uint8Array(await res.arrayBuffer())], [1, 2, 3]);
  const upstreamError = setup({ fetcher: async () => Response.json({ detail: "not owner" }, { status: 403 }) });
  assert.equal((await upstreamError.send("GET", `submissions/${id}`)).status, 403);
});
test("invalid JSON and service failures produce controlled responses", async () => {
  assert.equal((await setup().send("POST", "submissions", "{")).status, 400);
  const broken = setup({ fetcher: async () => { throw new Error("private provider secret"); } });
  const response = await broken.send("GET", "submissions");
  assert.equal(response.status, 502);
  assert.doesNotMatch(await response.text(), /secret/);
});
test("artifact allowlist includes explicit semantic invocation and private binary assets", async () => {
  const { send } = setup({ domain: "artifacts" });
  assert.equal((await send("GET", "embedding-profile")).status, 200);
  assert.equal((await send("POST", "search/semantic", { query: "circles" })).status, 200);
  assert.equal((await send("GET", `bundles/${id}/assets/${asset}/content`)).status, 200);
  assert.equal((await send("GET", `bundles/${id}/frames/127/content`)).status, 200);
  assert.equal((await send("GET", `bundles/${id}/frames/128/content`)).status, 404);
  assert.equal((await send("POST", `bundles/${id}/similar`, { limit: 100 })).status, 200);
  assert.equal((await send("POST", `bundles/${id}/index`, { generate_embedding: true })).status, 403);
  const staff = setup({ domain: "artifacts", hasAdmin: async () => true });
  assert.equal((await staff.send("POST", `bundles/${id}/index`, { generate_embedding: true, search_text_sha256: "hash" })).status, 200);
  assert.equal((await send("POST", `bundles/${id}/generate`, {})).status, 404);
});
test("full replacement retains source provenance and normalizes one-based ordering", () => {
  const payload = transcriptionPayload(4, [{ ordinal: 8, plain_text: "incorrect math", evidence_ids: [asset], source_plain_text: "machine" }], [{ region_id: asset, media_asset_id: id, page_number: 2, x_norm: .1, y_norm: .2, width_norm: .3, height_norm: .1, region_type: "EQUATION" }]);
  assert.equal(payload.expected_version, 4);
  assert.equal(payload.steps[0].ordinal, 1);
  assert.equal(payload.steps[0].plain_text, "incorrect math");
  assert.equal(payload.steps[0].source_plain_text, undefined);
  assert.equal(payload.regions[0].page_number, 2);
});
test("dirty or unapproved versions never display stale assessment", () => {
  const snapshot = { transcription_version: 2, approved_version: 1, approvals: [{ transcription_version: 2, approved_version: 1 }], assessments: [{ step_id: id, transcription_version: 1 }, { step_id: id, transcription_version: 2, approved_version: 1, correctness: "UNCERTAIN" }] };
  assert.equal(currentAssessment(snapshot, id).correctness, "UNCERTAIN");
  assert.equal(currentAssessment(snapshot, id, true), null);
  assert.equal(currentAssessment({ ...snapshot, transcription_version: 3 }, id), null);
  assert.equal(intervalLabel({ start_ms: 7400, end_ms: 12900 }), "00:07.4–00:12.9");
});
test("provider failures explain manual review and retained approval without blaming learners", () => {
  assert.match(runtimeErrorMessage("TRANSCRIPTION_UNAVAILABLE"), /enter the transcription manually/);
  assert.match(runtimeErrorMessage("ANALYSIS_UNAVAILABLE"), /approved attempt is still saved/);
  assert.equal(MAX_MEDIA_BYTES, 20 * 1024 * 1024);
});
