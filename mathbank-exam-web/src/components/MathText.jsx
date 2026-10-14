import { InlineMath, BlockMath } from "react-katex";
import "katex/dist/katex.min.css";
import { normalizeMathText } from "./mathText.js";

// Splits on \( ... \), \[ ... \], $$ ... $$ and $ ... $ delimiters and renders each
// math span with KaTeX, leaving everything else as plain text. The generator isn't
// perfectly consistent about which convention it uses from one question to the next
// (observed both \(...\) and $...$ in real generated papers), so both are supported
// rather than assuming one. Falls back to the raw text if KaTeX can't parse a span
// (never crashes the page over one malformed expression). Block forms are tried
// before their inline counterparts so `$$...$$` isn't mis-split as two `$...$` runs.
const SPLIT_RE = /(\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)/g;

function renderPart(part, key) {
  const tryRender = (Component, expr, display = false) => {
    try {
      const math = <Component math={expr} throwOnError={false} />;
      return display
        ? <div key={key} className="mb-math-display">{math}</div>
        : <span key={key} className="mb-math-inline">{math}</span>;
    } catch {
      return <span key={key}>{part}</span>;
    }
  };
  if (part.startsWith("\\[") && part.endsWith("\\]")) return tryRender(BlockMath, part.slice(2, -2), true);
  if (part.startsWith("\\(") && part.endsWith("\\)")) return tryRender(InlineMath, part.slice(2, -2));
  if (part.startsWith("$$") && part.endsWith("$$")) return tryRender(BlockMath, part.slice(2, -2), true);
  if (part.startsWith("$") && part.endsWith("$")) {
    const expression = part.slice(1, -1);
    const separatedChoices = (expression.match(/\\qquad/g) || []).length >= 2;
    return separatedChoices
      ? tryRender(BlockMath, expression, true)
      : tryRender(InlineMath, expression);
  }
  return <span key={key} style={{ whiteSpace: "pre-wrap" }}>{part}</span>;
}

export function MathText({ text }) {
  if (!text) return null;
  const parts = normalizeMathText(text).split(SPLIT_RE);
  return <>{parts.map((part, i) => renderPart(part, i))}</>;
}
