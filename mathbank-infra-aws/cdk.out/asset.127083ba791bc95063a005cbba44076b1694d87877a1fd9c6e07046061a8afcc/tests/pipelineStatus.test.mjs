import test from "node:test";
import assert from "node:assert/strict";
import { PIPELINE_STAGES, formatPipelineTime, pipelineBadgeClass } from "../lib/pipelineStatus.mjs";

test("vectors and generated/published pedagogy are independent stages", () => {
  assert.equal(PIPELINE_STAGES.length, 9);
  for (const name of ["vectors", "graph", "pedagogy", "pedagogy_graph"]) {
    assert.ok(PIPELINE_STAGES.some(([key]) => key === name));
  }
});
test("timestamps are deterministic UTC and absent timestamps are not invented", () => {
  assert.equal(formatPipelineTime(null), "Not recorded");
  assert.equal(formatPipelineTime("2026-10-05T10:40:00Z"), "2026-10-05 10:40:00 UTC");
});
test("unknown and stalled are not successful badges", () => {
  assert.equal(pipelineBadgeClass("UNKNOWN"), "text-bg-secondary");
  assert.equal(pipelineBadgeClass("STALLED"), "text-bg-warning");
});
