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

test("guidance activity hides routine source diagnostics but retains teaching progress", () => {
  const rows = toolEvidence("prepare_problem_guidance", {
    status: "ready", stages: ["private stage detail", "group", "check"], diagram_count: 0,
    context: { problem: { body: "PRIVATE" }, metadata_status: "automatic", skills: [],
      warnings: ["Internal context warning"] },
    warnings: ["Stored reference is unverified"],
    solution_evidence: { status: "available", references_considered: 2,
      sources: [{ verification_status: "UNVERIFIED", body_markdown: "PRIVATE_SOLUTION", answer: "384" }] },
  });
  assert.ok(!rows.some((row) => /stored solution|certification|source diagrams|evidence limitations/.test(row.label)));
  assert.ok(rows.some((row) => row.label.includes("3 teaching stages")));
  assert.doesNotMatch(JSON.stringify(rows), /PRIVATE|384|private stage/);
  const missing = toolEvidence("prepare_problem_guidance", { status: "unavailable",
    solution_evidence: { status: "unavailable", references_considered: 0 } });
  assert.deepEqual(missing, []);
});

test("topic plans and pending feedback expose bounded provenance, never allegations or answers", () => {
  const rows = toolEvidence("pedagogy_agent", { matched: true, plan_steps: ["secret"], practice: [{ answer: "SECRET" }] });
  assert.ok(rows.some((r) => r.label === "1 teaching stages prepared"));
  assert.ok(rows.some((r) => r.label === "1 complete step-supported candidates"));
  assert.doesNotMatch(JSON.stringify(rows), /SECRET|secret/);
  const report = toolEvidence("report_pedagogy_feedback", { feedback_id: "id", status: "PENDING", reason: "private allegation" });
  assert.match(report[0].label, /queued for review.*annotations unchanged/);
  assert.doesNotMatch(JSON.stringify(report), /private allegation/);
});

test("topic lessons and audits show only verified progress counters", () => {
  const rows = toolEvidence("pedagogy_agent", { matched: true, intent: "LEARN_TOPIC",
    current_unit: 0, unit_count: 7, artifact_status: "rendered", markdown_block: "private teaching payload" });
  assert.ok(rows.some((row) => row.label === "Topic lesson · step 1 of 7"));
  assert.ok(rows.some((row) => row.label === "Validated instructional diagram prepared"));
  assert.doesNotMatch(JSON.stringify(rows), /private teaching payload/);
  assert.match(toolEvidence("advance_topic_lesson", { completed_checkpoints: 2 })[0].label, /not a mastery certification/);
  assert.match(toolEvidence("retrieval_audit_agent", { review_status: "PENDING", raw: "secret" })[0].label, /no canonical mutation/);
});

test("lesson progress events contain only learner-safe checkpoint and stage data", () => {
  const progress = {
    topic: "Power of a point",
    stages: [{ index: 0, title: "Circle and chord", acronym: "TH", icon: "book-half", status: "active", seconds: 4 }],
    current_unit: 0, completed: 0, skipped: 0,
    checkpoint: { question: "Pick one", choices: ["A", "B"], input_type: "single-choice", hint_available: true, hint: null },
    feedback: "", feedback_tone: null,
  };
  const rows = toolEvidence("get_topic_lesson", { progress });
  assert.deepEqual(rows, [{ type: "progress", progress }]);
  assert.doesNotMatch(JSON.stringify(rows), /answer|correct|secret/i);
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
