import assert from "node:assert/strict";
import test from "node:test";
import { createAgentEventMapper, GENERATED_COACHING_NOTICE, readSse } from "../lib/agentStream.mjs";

function streamBytes(text, chunkSize = 1) {
  const bytes = new TextEncoder().encode(text);
  return new ReadableStream({
    start(controller) {
      for (let index = 0; index < bytes.length; index += chunkSize) {
        controller.enqueue(bytes.slice(index, index + chunkSize));
      }
      controller.close();
    },
  });
}

test("parses fragmented UTF-8, CRLF, comments, multiline data and final frames", async () => {
  const events = [];
  for await (const event of readSse(streamBytes(': ping\r\ndata: {"text":\r\ndata: "café"}\r\n\r\ndata: {"done":true}'))) events.push(event);
  assert.deepEqual(events, [{ text: "caf\u00e9" }, { done: true }]);
});

test("ignores the SSE done sentinel", async () => {
  const events = [];
  for await (const event of readSse(streamBytes("data: [DONE]\n\n"))) events.push(event);
  assert.deepEqual(events, []);
});

test("rejects malformed events instead of silently swallowing them", async () => {
  await assert.rejects(async () => {
    for await (const event of readSse(streamBytes("data: not-json\n\n"))) void event;
  }, SyntaxError);
});

test("accumulates deltas without duplicating ADK final text", () => {
  const map = createAgentEventMapper();
  const event = (text, partial) => ({ author: "tutor", partial, content: { parts: [{ text }] } });
  assert.deepEqual(map(event("Hel", true)), [{ type: "answer", text: "Hel" }]);
  assert.deepEqual(map(event("lo", true)), [{ type: "answer", text: "Hello" }]);
  assert.deepEqual(map(event("Hello", false)), [{ type: "answer", text: "Hello" }]);
  assert.deepEqual(map(event("Next", true)), [{ type: "answer", text: "Hello\n\nNext" }]);
  assert.deepEqual(map(event("Next step", false)), [{ type: "answer", text: "Hello\n\nNext step" }]);
});

test("exposes tool activity but never private thoughts or raw tool payloads", () => {
  const map = createAgentEventMapper();
  const updates = map({ author: "tutor", content: { parts: [
    { text: "Private reasoning", thought: true },
    { functionCall: { name: "search_problems", args: { secret: "hidden" } } },
    { functionResponse: { name: "search_problems", response: { raw: "hidden" } } },
    { text: "Public answer" },
  ] } });
  assert.deepEqual(updates, [
    { type: "activity", label: "Calling search_problems", status: "running" },
    { type: "activity", label: "search_problems completed", status: "complete" },
    { type: "answer", text: "Public answer" },
  ]);
  assert.deepEqual(map({ author: "user", content: { parts: [{ text: "Question" }] } }), []);
});

test("reports agent and tool errors explicitly", () => {
  const map = createAgentEventMapper();
  assert.throws(() => map({ errorCode: "FAIL", errorMessage: "Agent unavailable" }), /Agent unavailable/);
  assert.throws(() => map({ error: "Streaming failed" }), /Streaming failed/);
  assert.deepEqual(map({ content: { parts: [{ functionResponse: { name: "search", response: { error: "Unavailable" } } }] } }), [
    { type: "activity", label: "search reported an error", status: "error" },
  ]);
});

test("deduplicates streamed tool calls by ID without hiding separate invocations", () => {
  const map = createAgentEventMapper();
  const call = (id, partial) => ({ partial, content: { parts: [{ functionCall: { id, name: "search" } }] } });
  assert.equal(map(call("one", true)).length, 1);
  assert.deepEqual(map(call("one", true)), []);
  assert.deepEqual(map(call("one", false)), []);
  assert.equal(map(call("two", false)).length, 1);
});

test("labels generated coaching deterministically even when the model omits its status", () => {
  const map = createAgentEventMapper();
  map({ content: { parts: [{ functionResponse: {
    name: "get_next_hint",
    response: { provenance: { review_status: "PENDING" }, hint: "Private raw tool value" },
  } }] } });
  const event = (text, partial) => ({ author: "tutor", partial, content: { parts: [{ text }] } });
  assert.deepEqual(map(event("Try", true)), [
    { type: "answer", text: `${GENERATED_COACHING_NOTICE}\n\nTry` },
  ]);
  assert.deepEqual(map(event("Try counting.", false)), [
    { type: "answer", text: `${GENERATED_COACHING_NOTICE}\n\nTry counting.` },
  ]);
});
