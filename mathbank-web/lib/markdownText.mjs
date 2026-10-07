// Preserve code verbatim: TeX normalization must never modify program strings.
const CODE = /(^[ \t]*(`{3,}|~{3,})[^\n]*\n[\s\S]*?(?:\n[ \t]*\2[ \t]*(?=\n|$)|(?![\s\S]))|(`+)[^\n]*?\3|\[asy\][\s\S]*?(?:\[\/asy\]|(?![\s\S]))|\]\([^\n]*?\))/gim;

export function normalizeMathDelimiters(text) {
  if (!text) return text;
  return transformProse(String(text));
}

function transformProse(text) {
  let result = "";
  let offset = 0;
  for (const match of text.matchAll(CODE)) {
    result += math(text.slice(offset, match.index)) + match[0];
    offset = match.index + match[0].length;
  }
  return result + math(text.slice(offset));
}

function math(text) {
  return text
    .replace(/\\{1,2}\[([\s\S]*?)\\{1,2}\]/g, (_, expr) => `\n\n$$\n${expr.trim()}\n$$\n\n`)
    .replace(/\\{1,2}\(([\s\S]*?)\\{1,2}\)/g, (_, expr) => `$${expr.trim()}$`);
}

export function prepareMathMarkdown(text) {
  const normalized = normalizeMathDelimiters(text || "");
  let result = "";
  let offset = 0;
  for (const match of normalized.matchAll(CODE)) {
    result += normalized.slice(offset, match.index);
    if (/^\[asy\]/i.test(match[0])) {
      const complete = /\[\/asy\]$/i.test(match[0]);
      const source = match[0].replace(/^\[asy\]/i, "").replace(/\[\/asy\]$/i, "").trim();
      const fence = "`".repeat(Math.max(3, ...(source.match(/`+/g) || []).map((s) => s.length + 1)));
      result += `\n\n${fence}${complete ? "asymptote" : "asymptote-pending"}\n${source}\n${fence}\n\n`;
    } else result += match[0];
    offset = match.index + match[0].length;
  }
  return result + normalized.slice(offset);
}
