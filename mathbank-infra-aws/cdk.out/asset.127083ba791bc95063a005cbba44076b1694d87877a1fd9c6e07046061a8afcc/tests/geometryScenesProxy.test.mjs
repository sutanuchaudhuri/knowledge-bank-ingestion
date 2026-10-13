import assert from "node:assert/strict";
import test from "node:test";
import { createGeometryScenesHandler, validInterpretRequest, publicInterpretError } from "../lib/geometryScenesProxy.mjs";

function setup(overrides = {}) {
  const calls = [];
  const handler = createGeometryScenesHandler({
    getToken: async () => "server-jwt", hasAdmin: async () => false, adminKey: "server-key", baseUrl: "http://rest.test",
    fetcher: async (url, options) => { calls.push({ url, options }); return Response.json({ ok: true }); },
    ...overrides,
  });
  const send = (method, path, body, headers = {}) => handler(new Request(`http://web.test/api/rest/geometry-scenes/${path}`, {
    method, headers: { ...(body === undefined ? {} : { "content-type": "application/json" }), ...headers },
    ...(body === undefined ? {} : { body: typeof body === "string" ? body : JSON.stringify(body) }),
  }), path.split("?")[0].split("/"));
  return { calls, send };
}

test("all accepted reads use server JWT, never browser credentials, tokens or cache", async () => {
  const { calls, send } = setup();
  for (const path of ["triangle", "triangle/frames", "triangle/versions/0", "triangle/versions/2"]) {
    const response = await send("GET", path, undefined, { Authorization: "untrusted", "X-Admin-Api-Key": "untrusted" });
    assert.equal(response.status, 200);
    assert.match(response.headers.get("cache-control"), /private, no-store/);
    assert.equal(response.headers.get("x-content-type-options"), "nosniff");
    const call = calls.at(-1);
    assert.equal(call.url.href, `http://rest.test/v1/geometry-scenes/${path}`);
    assert.deepEqual(call.options.headers, { Authorization: "Bearer server-jwt" });
    assert.equal(call.options.cache, "no-store");
    assert.equal(call.options.redirect, "error");
  }
});

test("anonymous reads and student run diagnostics are rejected before upstream", async () => {
  const anonymous = setup({ getToken: async () => null });
  assert.equal((await anonymous.send("GET", "triangle/frames")).status, 401);
  assert.equal(anonymous.calls.length, 0);
  const student = setup();
  assert.equal((await student.send("GET", "debug/runs/run_123?owner=admin")).status, 403);
  assert.equal((await student.send("GET", "debug/runs?owner=admin")).status, 403);
  assert.equal((await student.send("POST", "debug/runs/run_123/review?owner=admin", { decision: "ACCEPTED" })).status, 403);
  assert.equal(student.calls.length, 0);
  const staff = setup({ hasAdmin: async () => true });
  assert.equal((await staff.send("GET", "debug/runs/run_123?owner=admin")).status, 200);
  assert.deepEqual(staff.calls[0].options.headers, { "X-Admin-Api-Key": "server-key" });
  assert.equal(staff.calls[0].url.href, "http://rest.test/v1/geometry-scenes/debug/runs/run_123?owner=admin");
  assert.equal((await setup({ hasAdmin: async () => true, adminKey: "" }).send("GET", "debug/runs/run_123?owner=admin")).status, 503);
});

test("debug owner query is mandatory, bounded and allowlisted only on staff routes", async () => {
  const { send, calls } = setup({ hasAdmin: async () => true });
  const owner = "11111111-1111-4111-8111-111111111111";
  assert.equal((await send("GET", `debug/runs?owner=${owner}`)).status, 200);
  assert.equal(calls[0].url.searchParams.get("owner"), owner);
  for (const query of ["", "?owner=", "?owner=../other", "?owner=admin&owner=admin",
    "?owner=admin&token=secret", "?owner=admin&limit=5", "?owner=" + "x".repeat(201)]) {
    assert.equal((await send("GET", "debug/runs/run_123" + query)).status, 400, query);
  }
  assert.equal((await send("GET", "triangle?owner=admin")).status, 400);
  assert.equal((await send("GET", "runs/run_123?owner=admin")).status, 404);
  assert.equal(calls.length, 1);
});

test("both production receipt prefixes retain staff-only diagnostics and owner restrictions", async () => {
  const owner = "11111111-1111-4111-8111-111111111111";
  for (const prefix of ["run", "failed"]) {
    const id = `${prefix}_0123456789abcdef0123456789abcdef`;
    const path = `debug/runs/${id}`;
    const staff = setup({ hasAdmin: async () => true });
    assert.equal((await staff.send("GET", `${path}?owner=${owner}`)).status, 200);
    assert.equal(staff.calls[0].url.href, `http://rest.test/v1/geometry-scenes/${path}?owner=${owner}`);
    assert.deepEqual(staff.calls[0].options.headers, { "X-Admin-Api-Key": "server-key" });
    assert.equal((await staff.send("GET", `${path}?owner=admin`)).status, 200);
    assert.equal((await staff.send("GET", path)).status, 400);
    assert.equal((await staff.send("GET", `${path}?owner=admin&token=secret`)).status, 400);
    const student = setup();
    assert.equal((await student.send("GET", `${path}?owner=${owner}`)).status, 403);
    assert.equal(student.calls.length, 0);
    const anonymous = setup({ getToken: async () => null });
    assert.equal((await anonymous.send("GET", `${path}?owner=admin`)).status, 403);
    assert.equal(anonymous.calls.length, 0);
  }
});

test("interpret failures preserve only public error fields and both run receipt prefixes", async () => {
  for (const prefix of ["run", "failed"]) {
    const run_id = `${prefix}_0123456789abcdef0123456789abcdef`;
    const detail = { code: "INVALID_GEOMETRY_PLAN", message: "Geometry validation failed.", run_id,
      provider_body: "private provider response", evidence: { prompt: "private evidence" }, api_key: "private credential" };
    const { send } = setup({ fetcher: async () => Response.json({
      detail, provider_response: "private top-level response",
    }, { status: 422 }) });
    const response = await send("POST", "interpret", { problem_text: "Triangle ABC", goal: "Draw the altitude" });
    assert.equal(response.status, 422);
    assert.match(response.headers.get("cache-control"), /private, no-store/);
    assert.deepEqual(await response.json(), { detail: {
      code: detail.code, message: detail.message, run_id,
    } });
  }
});

test("interpret error sanitization rejects unsafe field types, markup and identifier values", async () => {
  const fallback = { message: "The geometry scene could not be loaded." };
  for (const detail of [null, "private provider body", [], { code: {}, message: {}, run_id: {} },
    { code: "provider secret", message: "<script>private</script>", run_id: "../other" },
    { code: "X".repeat(81), message: "x".repeat(1001), run_id: "x".repeat(129) },
    { message: "private\nbody", run_id: "run_a?token=secret" }]) {
    assert.deepEqual(publicInterpretError({ detail }), fallback);
  }
  const payload = { problem_text: "Triangle ABC", goal: "Draw the altitude" };
  for (const [contentType, body] of [["text/html", "<h1>private provider response</h1>"], ["application/json", "{malformed"]]) {
    const { send } = setup({ fetcher: async () => new Response(body, { status: 503, headers: { "content-type": contentType } }) });
    const response = await send("POST", "interpret", payload);
    assert.equal(response.status, 503);
    assert.doesNotMatch(await response.text(), /private provider|malformed/);
  }
});

test("staff reviews accept only backend decisions and bounded notes with same-origin JSON", async () => {
  const { send, calls } = setup({ hasAdmin: async () => true });
  const path = "debug/runs/run_123/review?owner=admin";
  for (const decision of ["ACCEPTED", "REJECTED", "NEEDS_REVISION"]) {
    assert.equal((await send("POST", path, { decision, note: "Reviewed privately" })).status, 200);
  }
  assert.equal(calls[0].url.pathname, "/v1/geometry-scenes/debug/runs/run_123/review");
  for (const body of [{}, { decision: "OTHER" }, { decision: "ACCEPTED", owner: "other" },
    { decision: "ACCEPTED", note: "x".repeat(4001) }, { decision: "ACCEPTED", note: {} }]) {
    assert.equal((await send("POST", path, body)).status, 400);
  }
  assert.equal((await send("POST", path, { decision: "ACCEPTED" }, { origin: "http://evil.test" })).status, 403);
  assert.equal(calls.length, 3);
});

test("route allowlist blocks traversal, arbitrary methods, endpoints, queries and unsafe versions", async () => {
  const { calls, send } = setup();
  for (const [method, path] of [
    ["GET", "triangle/../admin"], ["GET", "triangle%2Fother"], ["GET", "triangle/versions/01"],
    ["GET", "triangle/versions/-1"], ["GET", "triangle/versions/9007199254740992"],
    ["POST", "triangle/deltas"], ["POST", "triangle/versions/1/validate"],
    ["PUT", "triangle"], ["DELETE", "triangle"], ["GET", "runs"], ["GET", "runs/run_123"], ["GET", "interpret"],
    ["GET", "triangle/versions/1/render/extra"],
  ]) assert.equal((await send(method, path)).status, 404, `${method} ${path}`);
  assert.equal((await send("GET", "triangle?token=secret")).status, 400);
  assert.equal(calls.length, 0);
});

test("render MIME checks reject HTML/JSON, sandbox SVG, and preserve binary PNG", async () => {
  for (const mime of ["text/html", "application/json", "image/jpeg"]) {
    const { send } = setup({ fetcher: async () => new Response("not an image", { headers: { "content-type": mime } }) });
    assert.equal((await send("GET", "triangle/versions/0/render")).status, 502);
  }
  for (const mime of ["image/svg+xml", "image/png"]) {
    const { send } = setup({ fetcher: async () => new Response(new Uint8Array([1, 2, 3]), { headers: { "content-type": mime } }) });
    const response = await send("GET", "triangle/versions/0/render");
    assert.equal(response.headers.get("content-type"), mime);
    assert.match(response.headers.get("content-security-policy"), /sandbox/);
    assert.deepEqual([...new Uint8Array(await response.arrayBuffer())], [1, 2, 3]);
  }
  const badJSON = setup({ fetcher: async () => new Response("{}", { headers: { "content-type": "text/html" } }) });
  assert.equal((await badJSON.send("GET", "triangle")).status, 502);
});

test("interpret sends only bounded production input without constructing geometry or paid calls in tests", async () => {
  const { send, calls } = setup();
  const body = { problem_text: "Triangle ABC", goal: "Draw the altitude", scene_id: "triangle",
    expected_version: 0, context: [{ type: "given", fact: "AB is perpendicular to AC." }],
    required_entities: ["A"], forbidden_entities: ["O"], seed: 17, current_math_step: "step_2",
    problem_id: "problem_1", solution_step_id: "solution_step_2", solve_attempt_id: "11111111-1111-4111-8111-111111111111" };
  assert.equal((await send("POST", "interpret", body)).status, 200);
  assert.deepEqual(JSON.parse(calls[0].options.body), body);
  assert.equal(calls[0].url.pathname, "/v1/geometry-scenes/interpret");
  for (const invalid of [{ ...body, svg: "<svg/>" }, { ...body, scene_id: "../x" }, { ...body, seed: 1.5 },
    { ...body, context: [null] }, { ...body, context: ["Current step"] }, { ...body, context: [{ type: "given" }] },
    { ...body, context: [{ type: "given", fact: "A fact", svg: "<svg/>" }] },
    { ...body, expected_version: -1 }, { goal: "Draw" }, { ...body, goal: "" }]) {
    assert.equal((await send("POST", "interpret", invalid)).status, 400);
  }
  assert.equal((await send("POST", "interpret", "{")).status, 400);
  assert.equal((await send("POST", "interpret", body, { "content-type": "text/plain" })).status, 415);
  assert.equal((await send("POST", "interpret", body, { origin: "http://evil.test" })).status, 403);
  assert.equal((await send("POST", "interpret", "x".repeat(65537))).status, 413);
  assert.equal(calls.length, 1);
});

test("interpret contract enforces text bounds, typed context, seed, links and version pair", () => {
  const valid = { problem_text: "x".repeat(20000), goal: "x".repeat(2000),
    context: [{ type: "given", fact: "A fact" }], seed: 2147483647, current_math_step: "",
    problem_id: "x".repeat(200), solution_step_id: "step", solve_attempt_id: "attempt" };
  assert.equal(validInterpretRequest(valid), true);
  for (const changes of [{ problem_text: "x".repeat(20001) }, { goal: "x".repeat(2001) },
    { context: [{ type: "", fact: "Fact" }] }, { context: [{ type: "given", fact: 5 }] },
    { context: Array.from({ length: 9 }, () => ({ type: "given", fact: "x".repeat(4000) })) },
    { seed: -1 }, { seed: 2147483648 }, { scene_id: "triangle" }, { expected_version: 0 },
    { current_math_step: "x".repeat(201) }, { problem_id: "x".repeat(201) }, { solution_step_id: {} },
    { solve_attempt_id: "attempt\nsecret" }, { required_entities: ["../A"] },
    { required_entities: ["A"], forbidden_entities: ["A"] }]) {
    assert.equal(validInterpretRequest({ ...valid, ...changes }), false, JSON.stringify(changes).slice(0, 100));
  }
});

test("upstream failures are private controlled errors, never provider details", async () => {
  const broken = setup({ fetcher: async () => { throw new Error("private secret"); } });
  const response = await broken.send("GET", "triangle");
  assert.equal(response.status, 502);
  assert.doesNotMatch(await response.text(), /private secret/);
  const denied = setup({ fetcher: async () => Response.json({ detail: "private owner" }, { status: 403 }) });
  const forbidden = await denied.send("GET", "triangle/versions/0/render");
  assert.equal(forbidden.status, 403);
  assert.doesNotMatch(await forbidden.text(), /private owner/);
});
