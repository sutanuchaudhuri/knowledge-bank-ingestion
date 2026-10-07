import assert from "node:assert/strict";
import test from "node:test";
import { hasQuestionText, relatedCandidates, relatedProblemRequest, problemDiscussionPrompt, tutorProblemHref, uniqueProblemTags } from "../lib/corpusProblems.mjs";

test("display tags deduplicate taxonomy identities while preserving distinct tags and source records", () => {
  const tags = [
    { slug: "alg-eq", name: "Equations", source: "problem" },
    { slug: "alg-eq", name: "Equations", source: "step" },
    { name: "Sequences" }, { name: "Sequences" },
    { slug: "geo-eq", name: "Equations" },
  ];
  assert.deepEqual(uniqueProblemTags(tags), [tags[0], tags[2], tags[4]]);
  assert.equal(tags.length, 5);
  assert.deepEqual(uniqueProblemTags(), []);
  assert.deepEqual(uniqueProblemTags(null), []);
});

test("related search uses published tags without solutions or paid embedding requests", () => {
  const body = relatedProblemRequest({
    concepts: [{ name: "Cyclic quadrilateral" }, { name: "Cyclic quadrilateral" }],
    techniques: [{ name: "Angle chasing" }], statement_text: "Statement",
    official_answer: "SECRET", solutions: [{ body_markdown: "HIDDEN" }],
  });
  assert.equal(body.query, "Cyclic quadrilateral Angle chasing");
  assert.deepEqual(body.retrieval, { semantic: false, lexical: true, graph: true });
  assert.doesNotMatch(JSON.stringify(body), /SECRET|HIDDEN/);
});

test("untagged problems use bounded question text and empty problems do not search", () => {
  assert.equal(relatedProblemRequest({ statement_text: "a".repeat(3000) }).query.length, 2000);
  assert.equal(relatedProblemRequest({}), null);
  assert.equal(relatedProblemRequest({ statement_text: "[Placeholder] Missing statement" }), null);
  assert.equal(hasQuestionText({ statement_text: "   [Placeholder] Missing statement" }), false);
  assert.equal(hasQuestionText({ statement_text: "Find x." }), true);
});

test("related candidates exclude the current problem, duplicates and missing identities", () => {
  const results = [
    { canonical_code: "CURRENT" }, {}, { canonical_code: "OTHER" }, { canonical_code: "OTHER" },
    ...Array.from({ length: 10 }, (_, index) => ({ canonical_code: `PROBLEM_${index}` })),
  ];
  const related = relatedCandidates(results, "CURRENT");
  assert.equal(related.length, 6);
  assert.equal(related[0].canonical_code, "OTHER");
  assert.equal(new Set(related.map((problem) => problem.canonical_code)).size, 6);
});

test("tutor links and prompts preserve the canonical problem identity", () => {
  assert.equal(tutorProblemHref("PUMAC_2008_A_NT_Q05"), "/?problem=PUMAC_2008_A_NT_Q05");
  assert.match(problemDiscussionPrompt("PUMAC_2008_A_NT_Q05"), /PUMAC_2008_A_NT_Q05/);
  assert.match(problemDiscussionPrompt("PUMAC_2008_A_NT_Q05"), /without revealing the full solution/);
});
