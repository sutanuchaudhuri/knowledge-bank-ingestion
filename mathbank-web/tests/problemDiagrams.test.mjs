import assert from "node:assert/strict";
import test from "node:test";
import { mentionedProblemCodes, problemImageUrl } from "../lib/problemDiagrams.mjs";

test("attaches source diagrams to canonical codes in tutor text and saved history", () => {
  assert.deepEqual(mentionedProblemCodes("Try **PAPER_SMT_2010_GEOM_Q06** then AIME_2023_I_Q11."), [
    "PAPER_SMT_2010_GEOM_Q06", "AIME_2023_I_Q11",
  ]);
  assert.deepEqual(mentionedProblemCodes("`PRASOLOV_PGV1_CH14_P021` PRASOLOV_PGV1_CH14_P021"), ["PRASOLOV_PGV1_CH14_P021"]);
});

test("does not repeat diagrams that the tutor already embedded", () => {
  assert.deepEqual(mentionedProblemCodes("PAPER_SMT_2010_GEOM_Q06\n![source](/api/rest/solve/images/uuid)"), []);
});

test("does not guess codes from titles or mathematical symbols", () => {
  assert.deepEqual(mentionedProblemCodes("SMT 2010 Geometry Test, Problem 6. OT=25"), []);
  assert.equal(problemImageUrl("a/b"), "/api/rest/solve/images/a%2Fb");
});
