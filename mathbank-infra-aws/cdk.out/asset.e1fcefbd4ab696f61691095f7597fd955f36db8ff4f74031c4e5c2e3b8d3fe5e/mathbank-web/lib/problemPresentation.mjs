import katex from "katex";
import { prepareMathMarkdown } from "./markdownText.mjs";

const WORDS = new Set(["quadrilateral", "quadrilaterals", "triangle", "triangles", "circumcenter", "circumcenters", "coefficient", "similarity", "perpendicular", "construction"]);
const PROTECTED = /(^[ \t]*(`{3,}|~{3,})[^\n]*\n[\s\S]*?(?:\n[ \t]*\2[ \t]*(?=\n|$)|(?![\s\S]))|(`+)[\s\S]*?\3|\]\((?:\\.|[^)])*\)|https?:\/\/[^\s<>)]+|\$\$[\s\S]*?\$\$|(?<!\\)\$(?:\\.|[^$])*?(?<!\\)\$)/gm;

function prose(text, code) {
  let result = text.replace(/([A-Za-z]+)-\s+([A-Za-z]+)/g, (whole, left, right) =>
    WORDS.has((left + right).toLowerCase()) ? left + right : whole);
  result = result.replace(/ﬃ/g, "ffi").replace(/ﬁ/g, "fi").replace(/ﬂ/g, "fl");
  if (code === "PRASOLOV_PGV1_CH06_P031") {
    result = result.replace(/\b(?:[ABCD][12])+\b/g, (name) => `$${name.replace(/([ABCD])([12])/g, "$1_{$2}")}$`);
    // A source-specific transcription repair, never a generic "1 4" -> fraction guess.
    result = result.replace(/1\s+4\s*\|\s*\(cot A \+ cot C\)\(cot B \+ cot D\)\s*\|/g,
      String.raw`$\frac{1}{4}\left|(\cot A+\cot C)(\cot B+\cot D)\right|$`);
  }
  return result;
}

export function prepareProblemPresentation(statement, code) {
  const source = prepareMathMarkdown(statement || "");
  let markdown = "", offset = 0;
  for (const match of source.matchAll(PROTECTED)) {
    markdown += prose(source.slice(offset, match.index), code) + match[0];
    offset = match.index + match[0].length;
  }
  markdown += prose(source.slice(offset), code);
  const warnings = [];
  for (const match of markdown.matchAll(PROTECTED)) {
    if (!match[0].startsWith("$")) continue;
    const display = match[0].startsWith("$$");
    const math = match[0].slice(display ? 2 : 1, display ? -2 : -1);
    try {
      katex.renderToString(math, { displayMode: display, throwOnError: true, trust: false, strict: "error" });
    } catch (error) {
      if (!(error instanceof katex.ParseError)) throw error;
      warnings.push("A source math expression needs formatting review; consult the original source.");
    }
  }
  return { markdown, warnings: [...new Set(warnings)], method: "validated-deterministic-v1" };
}
