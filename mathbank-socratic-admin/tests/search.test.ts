import { describe, expect, it } from "vitest";
import { describeProgram, ruleSentence, ruleText } from "../src/narrative";
import { matches, normalize, searchWorkspace } from "../src/search";
import { workflow } from "./fixtures";
import { prototypeWorkflow } from "./prototype";

const strategies = [
  { code: "COMB_BIJECTION", domain: "Combinatorics", label: "Build a bijection", status: "DRAFT" as const, phases: ["Discover", "Justify"] },
  { code: "ALG_PATTERN", domain: "Algebra", label: "Explore patterns", status: "DRAFT" as const, phases: ["Discover"] },
];
const summaries = [
  { ...prototypeWorkflow, program: undefined },
  { ...workflow, program: undefined, title: "Vieta relations", domain: "Algebra" },
].map(({ program: _, prototype_only: __, ...summary }) => summary);

describe("search module", () => {
  it("normalizes accents, dashes and TeX punctuation and requires every term", () => {
    expect(normalize("Inclusion–Exclusion \\(x_1\\)")).toBe("inclusion-exclusion (x 1 )");
    expect(matches("stars discovery", "Stars and Bars · Discovery journey")).toBe(true);
    expect(matches("stars algebra", "Stars and Bars · Discovery journey")).toBe(false);
    expect(matches("", "anything")).toBe(true);
  });
  it("groups drafts by domain and filters by title or domain", () => {
    const all = searchWorkspace("", { workflows: summaries, strategies, program: null });
    expect(all.domains.map(group => group.domain)).toEqual(["Algebra", "Combinatorics"]);
    expect(all.steps).toEqual([]);
    const algebra = searchWorkspace("algebra", { workflows: summaries, strategies, program: null });
    expect(algebra.domains).toHaveLength(1);
    expect(algebra.domains[0].workflows[0].title).toBe("Vieta relations");
    expect(algebra.strategies.map(item => item.code)).toEqual(["ALG_PATTERN"]);
  });
  it("finds steps of the open workflow by label, prompt, topic and rule annotation", () => {
    const hits = searchWorkspace("bijection", { workflows: summaries, strategies, program: prototypeWorkflow.program });
    expect(hits.steps.map(step => step.key)).toEqual(expect.arrayContaining(["lesson", "quiz"]));
    expect(hits.strategies.map(item => item.code)).toEqual(["COMB_BIJECTION"]);
    expect(hits.total).toBe(hits.steps.length + hits.strategies.length + hits.domains.reduce((n, g) => n + g.workflows.length, 0));
    expect(searchWorkspace("zzz", { workflows: summaries, strategies, program: prototypeWorkflow.program }).total).toBe(0);
  });
});

describe("natural-language narrative", () => {
  const program = prototypeWorkflow.program;
  it("generates rule sentences and prefers instructor annotations for display", () => {
    const retry = program.edges.find(edge => edge.outcome === "RETRY")!;
    expect(ruleSentence(program, retry)).toBe("If the student needs another attempt, go to Bijections mini-lesson.");
    expect(ruleText(program, retry)).toBe(retry.annotation);
    expect(ruleText(program, { ...retry, annotation: "  " })).toBe(ruleSentence(program, retry));
  });
  it("describes every step, its rules, the fallback and the move budget", () => {
    const story = describeProgram(program);
    expect(story.summary).toContain("starts at Begin discovery");
    expect(story.summary).toContain(`at most ${program.max_transitions} moves`);
    expect(story.steps).toHaveLength(program.nodes.length);
    expect(story.steps[2].heading).toBe("3. Stars and Bars · Assertion–Reason — Quiz · Stars and Bars");
    const orphan = story.steps.find(step => step.key === "pie")!;
    expect(orphan.rules[0]).toContain("falls back to Bijections mini-lesson");
    expect(story.steps.find(step => step.key === "done")!.rules).toEqual([]);
  });
});
