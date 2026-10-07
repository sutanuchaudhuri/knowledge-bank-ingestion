import test from "node:test";
import assert from "node:assert/strict";
import { geometryArtifactSource, splitTutorProblem } from "../lib/tutorProblem.mjs";

test("problem and source are separated from coaching without losing math", () => {
  const parsed = splitTutorProblem("Try this.\n\n**Problem:**\nA convex quadrilateral $ABCD$ has equal inradii. Prove it is a rectangle.\n\n**Source:** Prasolov\n\nAsk for a hint.");
  assert.equal(parsed.intro, "Try this.");
  assert.match(parsed.statement, /\$ABCD\$/);
  assert.equal(parsed.source, "Prasolov");
  assert.equal(parsed.outro, "Ask for a hint.");
});
test("plain tutoring prose and incomplete streaming sections are unchanged", () => {
  assert.equal(splitTutorProblem("Discuss the source of this problem."), null);
  assert.equal(splitTutorProblem("**Problem:**\nAn incomplete statement"), null);
});
test("geometry blocks are declarative only, bounded and streaming-safe", () => {
  const node = (value) => ({ children: [{ tagName: "code", properties: { className: ["language-geometry-artifact"] }, children: [{ value }] }] });
  assert.equal(geometryArtifactSource(node("{")).pending, true);
  assert.ok(geometryArtifactSource(node('{"subject":"GEOMETRY","elements":[]}')).plan);
  assert.ok(geometryArtifactSource(node('{"svg":"<script/>"}')).error);
  const algebra = node('{"subject":"ALGEBRA","elements":[]}');
  algebra.children[0].properties.className = ["language-artifact-preview"];
  assert.ok(geometryArtifactSource(algebra).plan);
  assert.equal(geometryArtifactSource({ children: [] }), null);
});
