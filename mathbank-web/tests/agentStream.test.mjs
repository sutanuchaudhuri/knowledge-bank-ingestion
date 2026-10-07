import assert from "node:assert/strict";
import test from "node:test";
import { createAgentEventMapper, GENERATED_COACHING_NOTICE, readSse, toolEvidence } from "../lib/agentStream.mjs";

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
    { type: "activity", label: "Searching graph, vector and text evidence", status: "running" },
    { type: "activity", label: "search_problems completed", status: "complete" },
    { type: "answer", text: "Public answer" },
  ]);
  assert.deepEqual(map({ author: "user", content: { parts: [{ text: "Question" }] } }), []);
});

test("activity uses actual retrieval status, not imagined graph evidence or raw payloads", () => {
  const rows = toolEvidence("search_practice_problems", {
    retrieval: { graph: "unavailable", semantic: true, lexical: true, graph_candidates: 0 },
    results: [{ statement_text: "HIDDEN", answer: "SECRET" }], skipped_incomplete: 2,
    warnings: ["postgres://private:credential@example.test"],
  });
  assert.ok(rows.some((row) => row.label === "Graph unavailable · degraded retrieval"));
  assert.ok(rows.some((row) => row.label === "Vector search enabled"));
  assert.ok(rows.some((row) => row.label === "2 incomplete candidates excluded"));
  assert.doesNotMatch(JSON.stringify(rows), /HIDDEN|SECRET|credential/);
  assert.deepEqual(toolEvidence("search_problems", { raw: "unknown" }), []);
  assert.deepEqual(toolEvidence("search_problems", { error: "failure", results: [] }), []);
  const map = createAgentEventMapper();
  const event = { content: { parts: [{ functionResponse: { id: "one", name: "search_problems",
    response: { retrieval: { graph: "queried", graph_candidates: 3 } } } }] } };
  assert.ok(map(event).some((row) => row.label === "Graph queried · 3 candidates"));
  assert.deepEqual(map(event), []);
});

test("coaching activity distinguishes machine approval and pending hints from human review", () => {
  const rows = toolEvidence("get_problem_learning_context", {
    problem: { answer: "SECRET" }, metadata_status: "automatic", skills: [{}, {}],
    prerequisites: [], concepts: [{}], techniques: [], warnings: ["raw private details"],
  });
  assert.ok(rows.some((row) => row.label === "2 graph-linked skills · machine-approved, not human verified"));
  assert.doesNotMatch(JSON.stringify(rows), /SECRET|raw private/);
  assert.equal(toolEvidence("get_next_hint", { provenance: { review_status: "PENDING" } })[0].status, "stopped");
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
