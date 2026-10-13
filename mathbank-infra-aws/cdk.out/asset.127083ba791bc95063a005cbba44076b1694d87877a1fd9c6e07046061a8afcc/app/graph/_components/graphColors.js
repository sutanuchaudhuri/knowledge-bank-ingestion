export const NODE_COLORS = {
  Competition: "#2563eb",
  Paper: "#7c3aed",
  Problem: "#059669",
  Solution: "#d97706",
  Concept: "#dc2626",
  Technique: "#0891b2",
  Skill: "#be185d",
};

export const FALLBACK_NODE_COLOR = "#64748b";

export function colorFor(label) {
  return NODE_COLORS[label] || FALLBACK_NODE_COLOR;
}
