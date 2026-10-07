import assert from "node:assert/strict";
import test from "node:test";
import { normalizeMathDelimiters, prepareMathMarkdown } from "../lib/markdownText.mjs";

test("renders prose TeX delimiters without modifying JavaScript or Asymptote strings", () => {
  const code = '```js\nconst text = String.raw`\\(h\\)`;\nconst other = "\\(z\\)";\n```\n`\\(x\\)`';
  assert.equal(normalizeMathDelimiters(`Find \\(h^2\\).\n${code}`), `Find $h^2$.\n${code}`);
  assert.match(prepareMathMarkdown("Then \\[x=2\\] done"), /\$\$\nx=2\n\$\$/);
});
test("legacy Asymptote source becomes a diagram block outside the math statement", () => {
  assert.equal(prepareMathMarkdown("Find \\(h\\). [asy] draw((0,0)--(1,1)); [/asy]"),
    "Find $h$. \n\n```asymptote\ndraw((0,0)--(1,1));\n```\n\n");
  assert.match(prepareMathMarkdown("[asy] label(\"\\(x\\)\"); [/asy]"), /label\("\\\(x\\\)"\)/);
  assert.match(prepareMathMarkdown("[asy] draw((0,0)"), /```asymptote-pending/);
  assert.equal(prepareMathMarkdown("```text\n[asy] example [/asy]\n```"), "```text\n[asy] example [/asy]\n```");
});
test("stored double-escaped math and whitespace normalize without leftover backslashes", () => {
  const statement = String.raw`Problem: In the diagram below, let \\( OT = 25 \\) and \\( AM = MB = 30 \\). Find \\( MD \\).`;
  assert.equal(prepareMathMarkdown(statement), "Problem: In the diagram below, let $OT = 25$ and $AM = MB = 30$. Find $MD$.");
  assert.equal(prepareMathMarkdown(String.raw`Let \( OT = 25 \).`), "Let $OT = 25$.");
  const code = String.raw`const text = "\\( OT = 25 \\)";`;
  assert.equal(prepareMathMarkdown("```js\n" + code + "\n```"), "```js\n" + code + "\n```");
  assert.equal(prepareMathMarkdown(String.raw`[Find \\( MD \\)](#mb-tone-goal)`), "[Find $MD$](#mb-tone-goal)");
  assert.equal(prepareMathMarkdown(String.raw`[Find \(MD\)](https://example.test/\(original\))`),
    String.raw`[Find $MD$](https://example.test/\(original\))`);
});
