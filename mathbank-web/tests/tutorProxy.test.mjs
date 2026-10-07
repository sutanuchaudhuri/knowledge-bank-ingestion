import assert from "node:assert/strict";
import test from "node:test";
import { GET, POST } from "../app/api/tutor/[...path]/route.js";

const context = (path) => ({ params: Promise.resolve({ path }) });

test("proxies only allowed anonymous tutor read routes and bounded query names", async (t) => {
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url.pathname, "/v1/tutor/prerequisites/counting");
    assert.equal(url.searchParams.get("max_depth"), "3");
    assert.equal(url.searchParams.has("password"), false);
    assert.equal(options.headers, undefined);
    return Response.json({ prerequisites: [] });
  });
  const response = await GET(new Request("http://localhost/api/tutor/prerequisites/counting?max_depth=3&password=ignored"), context(["prerequisites", "counting"]));
  assert.equal(response.status, 200);
  assert.equal((await GET(new Request("http://localhost"), context(["admin", "papers"]))).status, 404);
  assert.equal((await GET(new Request("http://localhost"), context(["learning-context"]))).status, 404);
});

test("coach payload is sent to the tutor, never learner attempt endpoints", async (t) => {
  const payload = { problem_code: "TEST", diagnosis: "strategy", student_attempt: "I tried a count", hint_level: 1 };
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url.pathname, "/v1/tutor/coach");
    assert.deepEqual(JSON.parse(options.body), payload);
    assert.equal(options.method, "POST");
    assert.equal(options.headers.Authorization, undefined);
    return Response.json({ hint_level: 1, hint: "A small step" });
  });

  const response = await POST(new Request("http://localhost", { method: "POST", body: JSON.stringify(payload) }), context(["coach"]));
  assert.equal(response.status, 200);
});

test("workspace proxy checks presentation without modifying the canonical statement", async (t) => {
  const statement = "A quad- rilateral.";
  t.mock.method(globalThis, "fetch", async () => Response.json({
    problem: { canonical_code: "TEST", statement_text: statement }, pedagogy_session: null,
  }));
  const response = await GET(new Request("http://localhost"), context(["workspace", "TEST"]));
  const body = await response.json();
  assert.equal(body.problem.statement_text, statement);
  assert.equal(body.problem.display_statement, "A quadrilateral.");
  assert.deepEqual(body.format_warnings, []);
});

test("preserves upstream failures and rejects malformed JSON/unknown endpoints", async (t) => {
  t.mock.method(globalThis, "fetch", async () => Response.json({ detail: "Unknown problem" }, { status: 404 }));
  let response = await GET(new Request("http://localhost"), context(["learning-context", "MISSING"]));
  assert.equal(response.status, 404);
  assert.deepEqual(await response.json(), { error: "Unknown problem" });
  response = await POST(new Request("http://localhost", { method: "POST", body: "bad JSON" }), context(["coach"]));
  assert.equal(response.status, 400);
  response = await POST(new Request("http://localhost", { method: "POST", body: "{}" }), context(["learner", "attempts"]));
  assert.equal(response.status, 404);
});
