import { InlineMath, BlockMath } from "react-katex";
import "katex/dist/katex.min.css";

// Splits on \( ... \), \[ ... \], $$ ... $$ and $ ... $ delimiters and renders each
// math span with KaTeX, leaving everything else as plain text. The generator isn't
// perfectly consistent about which convention it uses from one question to the next
// (observed both \(...\) and $...$ in real generated papers), so both are supported
// rather than assuming one. Falls back to the raw text if KaTeX can't parse a span
// (never crashes the page over one malformed expression). Block forms are tried
// before their inline counterparts so `$$...$$` isn't mis-split as two `$...$` runs.
const SPLIT_RE = /(\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)/g;

function renderPart(part, key) {
  const tryRender = (Component, expr) => {
    try {
      return <Component key={key} math={expr} />;
    } catch {
      return <span key={key}>{part}</span>;
    }
  };
  if (part.startsWith("\\[") && part.endsWith("\\]")) return tryRender(BlockMath, part.slice(2, -2));
  if (part.startsWith("\\(") && part.endsWith("\\)")) return tryRender(InlineMath, part.slice(2, -2));
  if (part.startsWith("$$") && part.endsWith("$$")) return tryRender(BlockMath, part.slice(2, -2));
  if (part.startsWith("$") && part.endsWith("$")) return tryRender(InlineMath, part.slice(1, -1));
  return <span key={key} style={{ whiteSpace: "pre-wrap" }}>{part}</span>;
}

export function MathText({ text }) {
  if (!text) return null;
  const parts = text.split(SPLIT_RE);
  return <>{parts.map((part, i) => renderPart(part, i))}</>;
}
