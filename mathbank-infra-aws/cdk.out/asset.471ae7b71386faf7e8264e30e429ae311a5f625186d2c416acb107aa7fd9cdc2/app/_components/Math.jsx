"use client";

// Slim inline/display LaTeX renderer ($…$, $$…$$) for the live classroom. KaTeX with trust off; plain
// text segments are rendered by React (escaped). Passed to WidgetHost/MathComposer as renderMath.
import katex from "katex";

const PATTERN = /(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)/g;

export function MathText({ text, className }) {
  const parts = String(text ?? "").split(PATTERN);
  return (
    <span className={className}>
      {parts.map((part, i) => {
        const display = part.startsWith("$$") && part.endsWith("$$") && part.length > 4;
        const inline = !display && part.startsWith("$") && part.endsWith("$") && part.length > 2;
        if (!display && !inline) return <span key={i} style={{ whiteSpace: "pre-wrap" }}>{part}</span>;
        const tex = display ? part.slice(2, -2) : part.slice(1, -1);
        const html = katex.renderToString(tex, { throwOnError: false, displayMode: display, trust: false, strict: "ignore" });
        return <span key={i} dangerouslySetInnerHTML={{ __html: html }} />;
      })}
    </span>
  );
}

export const renderMath = (t) => <MathText text={t} />;
