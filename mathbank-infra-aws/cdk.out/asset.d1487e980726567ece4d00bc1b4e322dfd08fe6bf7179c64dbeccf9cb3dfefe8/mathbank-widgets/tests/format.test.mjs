import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { deterministicFormat, checkLatex, insertSnippet } from "../src/format.mjs";

const cases = JSON.parse(readFileSync(new URL("../fixtures/format_cases.json", import.meta.url), "utf8"));

test("JS formatter matches the Python fixtures exactly", () => {
  for (const c of cases) {
    if (c.check_only) assert.deepEqual(checkLatex(c.input), c.warnings, `check ${JSON.stringify(c.input)}`);
    else {
      assert.equal(deterministicFormat(c.input), c.formatted, `format ${JSON.stringify(c.input)}`);
      assert.deepEqual(checkLatex(c.formatted), c.warnings);
    }
  }
});

test("insertSnippet wraps outside math and places the caret", () => {
  const r = insertSnippet("x ", 2, 2, "\\sqrt{|}");
  assert.equal(r.value, "x $\\sqrt{}$");
  assert.equal(r.cursor, 2 + 1 + "\\sqrt{".length);
  const inside = insertSnippet("$a$", 2, 2, "\\cdot ");
  assert.equal(inside.value, "$a\\cdot $");
  const sel = insertSnippet("AB", 0, 2, "\\overline{|}");
  assert.equal(sel.value, "$\\overline{AB}$");
});
