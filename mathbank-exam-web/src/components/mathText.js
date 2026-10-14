const CONTROL_COMMANDS = [
  ["\b" + "egin", "\\begin"],
  ["\f" + "rac", "\\frac"],
  ["\r" + "ight", "\\right"],
  ["\t" + "ext", "\\text"],
];

export function normalizeMathText(value) {
  if (!value) return value;
  let normalized = value;
  for (const [malformed, command] of CONTROL_COMMANDS) {
    normalized = normalized.split(malformed).join(command);
  }
  normalized = normalized
    .replace(/\\{2,}\(/g, "\\(")
    .replace(/\\{2,}\)/g, "\\)")
    .replace(/\\{2,}\[/g, "\\[")
    .replace(/\\{2,}\]/g, "\\]")
    .replace(/\\n/g, "\n");
  return normalized;
}
