// Shared with app/page.jsx's chat renderer and the Postgres detail panels —
// the agent and the corpus text both use \( \) / \[ \] which remark-math doesn't
// recognize (it wants $ $ / $$ $$).
export function normalizeMathDelimiters(text) {
  if (!text) return text;
  return text
    .replace(/\\\[([\s\S]*?)\\\]/g, (_, expr) => `$$${expr}$$`)
    .replace(/\\\(([\s\S]*?)\\\)/g, (_, expr) => `$${expr}$`);
}
