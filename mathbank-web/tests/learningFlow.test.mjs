import assert from "node:assert/strict";
import test from "node:test";
import { DIAGNOSES, hintRequestState } from "../lib/learningFlow.mjs";
import { nodeMetadata, edgeMetadata } from "../lib/graphMetadata.mjs";

test("offers five distinct diagnostic categories, not mastery scores", () => {
  assert.deepEqual(DIAGNOSES.map((item) => item.id), ["concept", "strategy", "execution", "calculation", "connection"]);
  assert(DIAGNOSES.every((item) => item.question && item.label));
});

test("requires an attempt and stops after three requested hints", () => {
  assert.equal(hintRequestState(" ", "", 0).allowed, false);
  assert.deepEqual(hintRequestState("I tried counting", "", 0), { allowed: true, nextLevel: 1 });
  assert.equal(hintRequestState("I tried counting", "I tried counting", 1).allowed, false);
  assert.deepEqual(hintRequestState("I tried the complement", "I tried counting", 1), { allowed: true, nextLevel: 2 });
  assert.deepEqual(hintRequestState("A new attempt", "An earlier attempt", 2), { allowed: true, nextLevel: 3 });
  assert.equal(hintRequestState("Another attempt", "An earlier attempt", 3).allowed, false);
});

test("graph metadata exposes provenance and dimensions, never answers or solution bodies", () => {
  const properties = {
    objective: "Identify objects and boxes", review_status: "REVIEWED",
    confidence: 0.9, conceptual_depth: { toNumber: () => 3 },
    official_answer: "hidden", body_markdown: "hidden", password: "hidden",
  };
  assert.deepEqual(nodeMetadata(properties), {
    objective: "Identify objects and boxes", confidence: 0.9,
    review_status: "REVIEWED", conceptual_depth: 3,
  });
  assert.deepEqual(edgeMetadata({ source: "review-rubric-v1", required_level: { toNumber: () => 2 }, confidence: 0.8, secret: "hidden" }),
    { required_level: 2, confidence: 0.8, source: "review-rubric-v1" });
});
