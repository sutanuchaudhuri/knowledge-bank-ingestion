import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";
import { prepareProblemPresentation } from "../lib/problemPresentation.mjs";

const require = createRequire(import.meta.url);
const Q31 = "PRASOLOV_PGV1_CH06_P031";
const AIME = String.raw`Let $x_1=97$, and for $n>1$, let $x_n=\frac{n}{x_{n-1}}$. Calculate the product $x_1x_2x_3x_4x_5x_6x_7x_8$.`;

test("the Markdown renderer and imported stylesheet resolve the same KaTeX version", () => {
  const renderer = createRequire(require.resolve("rehype-katex"));
  assert.equal(renderer("katex/package.json").version, require("katex/package.json").version);
});

test("canonical AIME subscripts and fractions are preserved without formatting warnings", () => {
  assert.deepEqual(prepareProblemPresentation(AIME, "AIME_1985_Q01"), {
    markdown: AIME, warnings: [], method: "validated-deterministic-v1",
  });
});

test("repairs only recognized PDF word breaks, preserving genuine hyphens and subtraction", () => {
  const result = prepareProblemPresentation("A quad- rilateral and quadrilat-\neral have a coeﬃcient. A well- known counter-example has $a- b$.", "OTHER");
  assert.equal(result.markdown, "A quadrilateral and quadrilateral have a coefficient. A well- known counter-example has $a- b$.");
  assert.deepEqual(result.warnings, []);
});

test("protects code, link destinations, Asymptote and already-delimited math", () => {
  const original = "``quad- rilateral coeﬃcient`` [source](https://example.org/coeﬃcient) https://example.org/coeﬃcient " +
    "$\\text{quad- rilateral}$\n```text\nquad- rilateral\n```\n[asy]\n// quad- rilateral\n[/asy]";
  const result = prepareProblemPresentation(original, Q31);
  assert.ok(result.markdown.includes("``quad- rilateral coeﬃcient``"));
  assert.ok(result.markdown.includes("](https://example.org/coeﬃcient) https://example.org/coeﬃcient"));
  assert.ok(result.markdown.includes("$\\text{quad- rilateral}$"));
  assert.ok(result.markdown.includes("```text\nquad- rilateral\n```"));
  assert.ok(result.markdown.includes("// quad- rilateral"));
});

test("Q31-specific point and given-coefficient presentation is idempotent and does not infer arbitrary fractions", () => {
  const statement = "For quadrilat- eral A1B1C1D1 points A2, B2, C2 and D2 are similarly defined. Its coeﬃcient is 1\n4 |(cot A + cot C)(cot B + cot D)|.";
  const result = prepareProblemPresentation(statement, Q31);
  assert.ok(result.markdown.includes("$A_{1}B_{1}C_{1}D_{1}$"));
  assert.ok(result.markdown.includes(String.raw`$\frac{1}{4}\left|(\cot A+\cot C)(\cot B+\cot D)\right|$`));
  assert.deepEqual(result.warnings, []);
  assert.deepEqual(prepareProblemPresentation(result.markdown, Q31), result);
  assert.equal(prepareProblemPresentation("A1 and 1 4 |(cot A + cot C)(cot B + cot D)|", "OTHER").markdown,
    "A1 and 1 4 |(cot A + cot C)(cot B + cot D)|");
});

test("invalid source TeX is reported without rewriting mathematical content", () => {
  const statement = String.raw`Try $\notARealCommand{x_1}$.`;
  const result = prepareProblemPresentation(statement, "OTHER");
  assert.equal(result.markdown, statement);
  assert.equal(result.warnings.length, 1);
  assert.match(result.warnings[0], /formatting review/);
});
