// Shared with app/page.jsx's chat renderer and the Postgres detail panels —
// the agent and the corpus text both use \( \) / \[ \] which remark-math doesn't
// recognize (it wants $ $ / $$ $$).
export { normalizeMathDelimiters } from "./markdownText.mjs";
