import assert from "node:assert/strict";
import test from "node:test";
import { POST } from "../app/api/agent/run/route.js";
import { GENERATED_COACHING_NOTICE, readSse } from "../lib/agentStream.mjs";

function request(body) {
  return new Request("http://localhost/api/agent/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

const input = { userId: "test", sessionId: "test-session", text: "Hello" };

test("streams normalized answers incrementally, filters thoughts and completes", async (t) => {
  let upstream;
  let signal;
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert(url.endsWith("/run_sse"));
    assert.equal(JSON.parse(options.body).streaming, true);
    signal = options.signal;
    return new Response(new ReadableStream({ start(controller) { upstream = controller; } }));
  });
  const response = await POST(request({ ...input, stream: true }));
  assert.equal(response.headers.get("content-type"), "text/event-stream");
  const events = readSse(response.body);
  assert.equal((await events.next()).value.type, "activity");
  const send = (event) => upstream.enqueue(new TextEncoder().encode(`data: ${JSON.stringify(event)}\n\n`));
  send({ author: "tutor", partial: true, content: { parts: [{ text: "Private", thought: true }, { text: "Hi" }] } });
  assert.deepEqual((await events.next()).value, { type: "answer", text: "Hi" });
  send({ author: "tutor", content: { parts: [{ text: "Hi there" }] } });
  assert.deepEqual((await events.next()).value, { type: "answer", text: "Hi there" });
  upstream.close();
  assert.deepEqual((await events.next()).value, { type: "done" });
  assert.equal((await events.next()).done, true);
  assert.equal(signal.aborted, false);
});

test("surfaces empty streams and upstream errors", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(""));
  const response = await POST(request({ ...input, stream: true }));
  const events = [];
  for await (const event of readSse(response.body)) events.push(event);
  assert.deepEqual(events.at(-1), { type: "error", message: "Agent finished without an answer" });
});

test("cancelling the browser stream aborts the upstream request", async (t) => {
  let signal;
  t.mock.method(globalThis, "fetch", async (_url, options) => {
    signal = options.signal;
    return new Response(new ReadableStream({
      start(controller) { signal.addEventListener("abort", () => controller.error(new DOMException("Stopped", "AbortError"))); },
    }));
  });
  const response = await POST(request({ ...input, stream: true }));
  const reader = response.body.getReader();
  await reader.read();
  await reader.cancel();
  assert.equal(signal.aborted, true);
});

test("preserves non-streaming response and rejects invalid input", async (t) => {
  assert.equal((await POST(request({ text: "" }))).status, 400);
  assert.equal((await POST(request(null))).status, 400);
  assert.equal((await POST(request({ ...input, stream: "true" }))).status, 400);
  assert.equal((await POST(new Request("http://localhost/api/agent/run", { method: "POST", body: "not JSON" }))).status, 400);
  t.mock.method(globalThis, "fetch", async (url) => {
    assert(url.endsWith("/run"));
    return Response.json([{ author: "tutor", content: { parts: [{ text: "Hidden", thought: true }, { text: "Answer" }] } }]);
  });
  const response = await POST(request(input));
  assert.deepEqual(await response.json(), { reply: "Answer" });
});

test("returns explicit errors for upstream HTTP and connection failures", async (t) => {
  const mock = t.mock.method(globalThis, "fetch", async () => new Response("unavailable", { status: 503 }));
  let response = await POST(request(input));
  assert.equal(response.status, 503);
  assert.match((await response.json()).error, /503/);
  mock.mock.mockImplementation(async () => { throw new Error("Connection refused"); });
  response = await POST(request({ ...input, stream: true }));
  assert.equal(response.status, 502);
  assert.match((await response.json()).error, /Connection refused/);
});

test("non-streaming generated hints have the same deterministic review notice", async (t) => {
  t.mock.method(globalThis, "fetch", async () => Response.json([
    { content: { parts: [{ functionResponse: {
      name: "get_next_hint", response: { provenance: { review_status: "PENDING" } },
    } }] } },
    { author: "tutor", content: { parts: [{ text: "Try counting." }] } },
  ]));
  const response = await POST(request(input));
  assert.deepEqual(await response.json(), { reply: `${GENERATED_COACHING_NOTICE}\n\nTry counting.` });
});
