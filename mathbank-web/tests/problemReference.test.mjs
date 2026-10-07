import assert from "node:assert/strict";
import test from "node:test";
import { parseProblemReference, resolveProblemReference } from "../lib/problemReference.mjs";

test("accepts canonical codes and readable contest references, with arbitrary text as search", () => {
  assert.deepEqual(parseProblemReference("aime_1985_q01"), { code: "AIME_1985_Q01" });
  assert.deepEqual(parseProblemReference("amc 10 2011 problem1"), {
    competition: "AMC10", year: 2011, number: 1, paper: null,
  });
  assert.equal(parseProblemReference("AMC 10A 2011 Q1").paper, "A");
  assert.equal(parseProblemReference("AIME 2011 II problem 1").paper, "II");
  assert.equal(parseProblemReference("AMC 8 2011 problem 1").competition, "AMC8");
  assert.deepEqual(parseProblemReference("amc 10 201 problem1"), { query: "amc 10 201 problem1" });
  assert.deepEqual(parseProblemReference("geometry with intersecting circles"), { query: "geometry with intersecting circles" });
  assert.throws(() => parseProblemReference(" "), /Enter a topic/);
  assert.throws(() => parseProblemReference("AIME 2011 problem 16"), /problem number/);
  assert.throws(() => parseProblemReference("AMC 10I 2011 problem 1"), /A\/B/);
  assert.throws(() => parseProblemReference("AMC 10A 2011 B problem 1"), /one paper/);
});

test("resolves exact corpus records, returns ambiguity and excludes answer fields", async () => {
  const rows = ["A", "B"].map((paper) => ({
    canonical_code: `AMC10_2011${paper}_Q01`, problem_number: 1,
    paper_code: paper, year: 2011, competition: "AMC 10", official_answer: "SECRET",
  }));
  const calls = [];
  const fetchPage = async (url) => { calls.push(url); return { items: rows, hasMore: false }; };
  const candidates = await resolveProblemReference("amc 10 2011 problem1", { fetchPage });
  assert.equal(candidates.candidates.length, 2);
  assert.doesNotMatch(JSON.stringify(candidates), /SECRET|official_answer/);
  assert.match(calls[0], /competition=AMC10&year_min=2011&year_max=2011/);
  const exact = await resolveProblemReference("AMC 10B 2011 problem 1", { fetchPage });
  assert.deepEqual(exact.candidates.map((item) => item.canonical_code), ["AMC10_2011B_Q01"]);
});

test("canonical codes bypass list lookup; pagination and abort signal are preserved", async () => {
  const controller = new AbortController();
  assert.deepEqual(await resolveProblemReference("AIME_1985_Q01", {
    fetchPage: () => { throw new Error("No lookup expected"); },
  }), { kind: "exact", candidates: [{ canonical_code: "AIME_1985_Q01" }], warnings: [] });
  const calls = [];
  const candidates = await resolveProblemReference("AIME 2011 II problem 1", {
    signal: controller.signal,
    fetchPage: async (url, options) => {
      assert.equal(options.signal, controller.signal);
      calls.push(url);
      return calls.length === 1 ? { items: [], hasMore: true } : { items: [
        { canonical_code: "AIME_2011_II_Q01", paper_code: "II", problem_number: 1 },
      ], hasMore: false };
    },
  });
  assert.equal(candidates.candidates[0].canonical_code, "AIME_2011_II_Q01");
  assert.match(calls[1], /offset=100/);
});

test("free text uses existing graph/text search, retains warnings and excludes private answer fields", async () => {
  let request;
  const result = await resolveProblemReference("a recurrence where neighboring terms cancel", {
    fetchPage: async (url, options) => {
      request = { url, options };
      return { results: [{ canonical_code: "AIME_1985_Q01", competition: "AIME", year: 1985,
        official_answer: "SECRET", solutions: ["SECRET_BODY"] }], warnings: ["Graph unavailable"] };
    },
  });
  assert.equal(result.kind, "search");
  assert.equal(result.candidates.length, 1);
  assert.equal(request.url, "/api/rest/search");
  assert.deepEqual(JSON.parse(request.options.body), {
    query: "a recurrence where neighboring terms cancel", limit: 10,
    retrieval: { semantic: false, lexical: true, graph: true },
  });
  assert.deepEqual(result.warnings, ["Graph unavailable"]);
  assert.doesNotMatch(JSON.stringify(result), /SECRET|official_answer|solutions/);
  const empty = await resolveProblemReference("circles", { fetchPage: async () => ({ results: [] }) });
  assert.deepEqual(empty, { kind: "search", candidates: [], warnings: [] });
  await assert.rejects(resolveProblemReference("circles", { fetchPage: async () => ({ results: [{}] }) }), /invalid data/);
  await assert.rejects(resolveProblemReference("circles", { fetchPage: async () => ({ results: [], warnings: {} }) }), /invalid data/);
});

test("already-cancelled searches never make a request", async () => {
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(resolveProblemReference("circles", {
    signal: controller.signal, fetchPage: () => { assert.fail("An aborted lookup must not fetch"); },
  }), { name: "AbortError" });
});

test("missing, unavailable, malformed and over-limit lookups are explicit", async () => {
  const query = "AMC 10 2011 problem 1";
  await assert.rejects(resolveProblemReference(query, { fetchPage: async () => ({ items: [], hasMore: false }) }), /No matching problem/);
  await assert.rejects(resolveProblemReference(query, { fetchPage: async () => { throw new Error("Offline"); } }), /Offline/);
  await assert.rejects(resolveProblemReference(query, { fetchPage: async () => ({}) }), /invalid data/);
  await assert.rejects(resolveProblemReference(query, { fetchPage: async () => ({ items: [], hasMore: true }) }), /search limit/);
});
