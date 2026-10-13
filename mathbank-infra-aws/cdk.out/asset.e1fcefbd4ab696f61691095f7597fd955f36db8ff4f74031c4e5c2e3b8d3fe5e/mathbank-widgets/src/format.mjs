// Deterministic student math formatter — a line-for-line mirror of
// mathbank-rest/src/mathbank_rest/math_format.py (deterministic_format + check_latex).
// Parity is enforced by fixtures/format_cases.json, which both the Python and node suites check.
// It never solves or corrects mathematics; it only adds LaTeX delimiters/commands.

export const MAX_CHARS = 4000;

const UNSAFE = /\\(href|url|includegraphics|htmlClass|htmlId|htmlStyle|htmlData|input|include|def|newcommand|renewcommand|write|immediate|catcode)\b|<\s*\/?\s*script|javascript\s*:/i;

const strip = (g) => (g.startsWith("(") && g.endsWith(")") ? g.slice(1, -1) : g);

const WORD_SYMBOLS = [
  [/\bangle\s+([A-Z]{3}|[A-Z])\b/g, "\\angle $1"],
  [/\btriangle\s+([A-Z]{3})\b/g, "\\triangle $1"],
  [/\barc\s+([A-Z]{2,3})\b/g, "\\overset{\\frown}{$1}"],
  [/\bsqrt\s*\(([^()]+)\)/g, "\\sqrt{$1}"],
  [/\bsqrt\s*([A-Za-z0-9]+)/g, "\\sqrt{$1}"],
  [/\bpi\b/g, "\\pi"],
  [/\btheta\b/g, "\\theta"], [/\balpha\b/g, "\\alpha"], [/\bbeta\b/g, "\\beta"],
  [/\bgamma\b/g, "\\gamma"], [/\binfinity\b|\binf\b/g, "\\infty"],
  [/\bperp\b|⊥/g, "\\perp "], [/\bparallel\b|∥/g, "\\parallel "],
  [/\bcong\b|≅/g, "\\cong "], [/\bsim\b|∼/g, "\\sim "],
];
const OPERATORS = [
  [/<=|≤/g, "\\le "], [/>=|≥/g, "\\ge "], [/!=|≠/g, "\\ne "], [/~=/g, "\\cong "],
  [/\|\|/g, "\\parallel "], [/(?<=\w)\s*\*\s*(?=\w)/g, " \\cdot "], [/·|×/g, " \\cdot "],
  [/°|\bdeg\b|\bdegrees\b/g, "^\\circ"], [/√\s*\(([^()]+)\)/g, "\\sqrt{$1}"], [/√\s*(\w+)/g, "\\sqrt{$1}"],
  [/π/g, "\\pi"], [/θ/g, "\\theta"], [/∠\s*/g, "\\angle "], [/△\s*/g, "\\triangle "],
  [/\b(\w+|\([^()]+\))\s*\/\s*(\w+|\([^()]+\))/g, (_m, a, b) => `\\frac{${strip(a)}}{${strip(b)}}`],
  [/\^\s*\(([^()]+)\)/g, "^{$1}"], [/\^(\d{2,})/g, "^{$1}"], [/_(\d{2,}|[a-z]{2,})/g, "_{$1}"],
];
const MATHY = /[=<>+\-*/^_|°√π∠△·×≤≥≠≅∼∥⊥]|^\(?[A-Z]{1,4}\)?[.,;:]?$|^\d+(\.\d+)?[.,;:]?$|^(angle|triangle|sqrt|pi|theta|alpha|beta|perp|parallel|cong|sim|deg|degrees)\b|\\[a-z]+/;
const CONNECTOR = /^(and|or|so|then|since|because|hence|thus|therefore|where|is|are|by|of|if|we|the|a|an|to|in|on|at|with|that|this|it|let|get|gives|from|for)$/i;
const MATH_SIGNAL = /[=<>+\-*/^_|°√π∠△·×≤≥≠≅∼∥⊥]|angle|triangle|sqrt|\bpi\b|perp|parallel|cong|\bsim\b|\b[A-Z]{2,4}\b|\d/;

function latexify(run) {
  let out = run;
  for (const [pattern, repl] of [...WORD_SYMBOLS, ...OPERATORS]) out = out.replace(pattern, repl);
  out = out.replace(/\s+\^\\circ/g, "^\\circ");
  return out.replace(/\s{2,}/g, " ").trim();
}

function segmentLine(line) {
  const tokens = line.split(" ");
  const flags = tokens.map((tok, i) => {
    const word = tok.trim();
    let mathy = Boolean(word) && MATHY.test(word) && !CONNECTOR.test(word);
    if (["angle", "triangle", "arc"].includes(word.toLowerCase()) && i + 1 < tokens.length && /^[A-Z]{1,3}\b/.test(tokens[i + 1])) {
      mathy = true;
    }
    // A lone capital "A"/"I" starting a sentence is English, not a point name.
    if ((word === "A" || word === "I") && (i === 0 || tokens[i - 1].endsWith(".")) &&
        !(i + 1 < tokens.length && MATHY.test(tokens[i + 1]) && "=<>+-*/^".includes(tokens[i + 1].slice(0, 1)))) {
      mathy = false;
    }
    return mathy;
  });
  const pieces = [];
  let run = [];
  const flush = () => {
    if (!run.length) return;
    let body = run.join(" ");
    let trail = "";
    while (body && ".,;:".includes(body.at(-1))) {
      trail = body.at(-1) + trail;
      body = body.slice(0, -1);
    }
    pieces.push((MATH_SIGNAL.test(body) ? `$${latexify(body)}$` : body) + trail);
    run = [];
  };
  tokens.forEach((tok, i) => {
    if (flags[i]) run.push(tok);
    else { flush(); pieces.push(tok); }
  });
  flush();
  return pieces.join(" ");
}

/** Wrap math runs in $…$ and convert typed notation to LaTeX. Already-delimited text is only normalised. */
export function deterministicFormat(text) {
  const src = (text || "").slice(0, MAX_CHARS);
  if (!src.trim()) return src;
  if (/\$|\\\(|\\\[/.test(src)) {
    return src.replaceAll("\\(", "$").replaceAll("\\)", "$").replaceAll("\\[", "$$$$").replaceAll("\\]", "$$$$");
  }
  return src.split("\n").map(segmentLine).join("\n");
}

/** Light structural checks: disallowed commands, unbalanced braces, unbalanced $ delimiters. */
export function checkLatex(text) {
  const src = text || "";
  const problems = [];
  if (UNSAFE.test(src)) problems.push("contains a disallowed command");
  let depth = 0;
  for (const ch of src.replace(/\\[{}]/g, "")) {
    depth += ch === "{" ? 1 : ch === "}" ? -1 : 0;
    if (depth < 0) break;
  }
  if (depth !== 0) problems.push("unbalanced braces");
  if ((src.replaceAll("$$", "").match(/(?<!\\)\$/g) || []).length % 2) problems.push("unbalanced $ delimiters");
  return problems;
}

/** Composer toolbar: label shown, LaTeX inserted (cursor placed at "|" when present). */
export const SYMBOL_GROUPS = [
  { name: "Geometry", items: [
    ["∠", "\\angle "], ["△", "\\triangle "], ["⊥", "\\perp "], ["∥", "\\parallel "], ["≅", "\\cong "],
    ["∼", "\\sim "], ["°", "^\\circ"], ["⌒", "\\overset{\\frown}{|}"], ["‾AB", "\\overline{|}"] ] },
  { name: "Algebra", items: [
    ["a/b", "\\frac{|}{}"], ["√", "\\sqrt{|}"], ["x²", "^{2}"], ["xⁿ", "^{|}"], ["xₙ", "_{|}"],
    ["·", " \\cdot "], ["≤", " \\le "], ["≥", " \\ge "], ["≠", " \\ne "], ["±", " \\pm "] ] },
  { name: "Greek", items: [["π", "\\pi "], ["θ", "\\theta "], ["α", "\\alpha "], ["β", "\\beta "], ["γ", "\\gamma "]] },
  { name: "Logic", items: [["⇒", " \\Rightarrow "], ["⇔", " \\iff "], ["∴", " \\therefore "], ["∈", " \\in "]] },
];

/**
 * Insert a snippet into `value` at the selection. Plain-math snippets are wrapped in $…$ when the
 * cursor is not already inside math. Returns { value, cursor }.
 */
export function insertSnippet(value, start, end, snippet) {
  const before = value.slice(0, start);
  const after = value.slice(end);
  const insideMath = ((before.replaceAll("$$", "").match(/(?<!\\)\$/g) || []).length % 2) === 1;
  const selected = value.slice(start, end);
  let body = snippet.includes("|") ? snippet.replace("|", selected) : snippet + selected;
  let caret = snippet.includes("|") ? snippet.indexOf("|") + selected.length : body.length;
  if (!insideMath) {
    body = `$${body}$`;
    caret += 1;
  }
  return { value: before + body + after, cursor: before.length + caret };
}
