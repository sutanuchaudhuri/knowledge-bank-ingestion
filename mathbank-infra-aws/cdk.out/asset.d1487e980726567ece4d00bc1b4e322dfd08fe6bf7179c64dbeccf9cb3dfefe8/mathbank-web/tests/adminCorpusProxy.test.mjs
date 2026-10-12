import { test } from "node:test";
import assert from "node:assert/strict";
import { corpusRoute, createCorpusHandlers } from "../lib/adminCorpusProxy.mjs";

const id = "11111111-1111-4111-8111-111111111111";
test("corpus proxy allowlists paths and methods", () => {
  assert.equal(corpusRoute("GET", ["problems"]), "/v1/admin/corpus/problems");
  assert.equal(corpusRoute("POST", ["drafts", id, "review"]), `/v1/admin/corpus/drafts/${id}/review`);
  assert.equal(corpusRoute("GET", ["drafts", id, "image"]), `/v1/admin/corpus/drafts/${id}/image`);
  assert.equal(corpusRoute("PUT", ["drafts", id]), `/v1/admin/corpus/drafts/${id}`);
  for (const [method, path] of [["DELETE", ["drafts", id]], ["GET", ["../secrets"]],
    ["POST", ["drafts", "invalid", "review"]], ["GET", ["problems", "../escape"]]]) {
    assert.equal(corpusRoute(method, path), null);
  }
});
test("session and same-origin authorization precede corpus mutations", async () => {
  let sends = 0;
  const dependencies = { get: async () => ({}), image: async () => new Response(),
    send: async () => { sends++; return {}; } };
  const request = () => new Request("http://localhost/api/rest/admin/corpus/drafts",
    { method: "POST", headers: { origin: "https://foreign.example" }, body: "{}" });
  assert.equal((await createCorpusHandlers({ ...dependencies, hasSession: async () => false })(request(), ["drafts"])).status, 401);
  assert.equal((await createCorpusHandlers({ ...dependencies, hasSession: async () => true })(request(), ["drafts"])).status, 403);
  assert.equal(sends, 0);
});
test("corpus proxy forwards only supported filters and preserves failures", async () => {
  let query;
  const handle = createCorpusHandlers({ hasSession: async () => true,
    get: async (_, params) => { query = params; return { items: [] }; } });
  const result = await handle(new Request("http://localhost/api/rest/admin/corpus/problems?competition=AMC10&admin_key=bad"), ["problems"]);
  assert.equal(result.status, 200);
  assert.deepEqual(query, { competition: "AMC10" });
  const fail = createCorpusHandlers({ hasSession: async () => true,
    send: async () => { const error = new Error("Source changed"); error.status = 409; throw error; } });
  const response = await fail(new Request("http://localhost/api/rest/admin/corpus/drafts", {
    method: "POST", headers: { origin: "http://localhost" }, body: "{}",
  }), ["drafts"]);
  assert.equal(response.status, 409);
  assert.deepEqual(await response.json(), { error: "Source changed" });
});
