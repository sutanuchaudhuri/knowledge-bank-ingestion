// Agentic widget blocks in tutor markdown (requirements 27/29): the agent's propose_widget tool returns a
// validated spec, which the agent embeds as a fenced ```widget JSON block. The browser renders it only
// when it parses and names a whitelisted widget_type; everything else stays plain text.

export const WIDGET_TYPES = new Set([
  "GEOMETRY_DIAGRAM", "GEOMETRY_OVERLAY", "COORDINATE_GRAPH", "KNOWLEDGE_GRAPH", "REASONING_DAG", "NUMBER_LINE",
  "TABLE", "FORMULA_CARD", "TIMELINE", "BAR_CHART", "POLL_RESULT", "STEP_PROGRESS", "COMPARISON",
]);
export const MAX_WIDGET_BLOCK = 20_000;

/** Returns { spec } for a renderable block, { pending: true } for an incomplete/streaming one, or null. */
export function parseWidgetBlock(source) {
  const text = String(source || "").trim();
  if (!text || text.length > MAX_WIDGET_BLOCK) return null;
  let value;
  try { value = JSON.parse(text); } catch { return { pending: true }; }
  const spec = value && typeof value === "object" && value.spec && typeof value.spec === "object" ? value.spec : value;
  if (!spec || typeof spec !== "object" || Array.isArray(spec) || !WIDGET_TYPES.has(spec.widget_type)) return null;
  if (spec.config != null && (typeof spec.config !== "object" || Array.isArray(spec.config))) return null;
  return { spec };
}

/** hast <pre><code class="language-widget">…</code></pre> -> raw text, else null. */
export function widgetSourceFromPre(node) {
  const code = node?.children?.find((c) => c.type === "element" && c.tagName === "code");
  const cls = code?.properties?.className;
  if (!code || !(Array.isArray(cls) ? cls : [cls]).includes("language-widget")) return null;
  return (code.children || []).map((c) => c.value || "").join("");
}
