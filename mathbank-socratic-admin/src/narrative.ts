// Plain-language rendering of a workflow program; the typed program stays authoritative.
import type { Edge, NodeType, Program } from "./contracts";

export const outcomeLabels: Record<Edge["outcome"], string> = {
  ALWAYS: "Completes the activity", SUCCESS: "Answers correctly",
  RETRY: "Needs another attempt", UNCERTAIN: "Needs clarification",
};
const outcomeClauses: Record<Edge["outcome"], string> = {
  ALWAYS: "After this step", SUCCESS: "When the student answers correctly",
  RETRY: "If the student needs another attempt", UNCERTAIN: "If the answer is uncertain",
};
export const typeNames: Record<NodeType, string> = {
  START: "Start", DISCOVERY: "Discovery", QUIZ: "Quiz", LESSON: "Lesson", TOPIC: "Topic",
  INTERACTION: "Interaction", HINT: "Hint", FEEDBACK: "Feedback", AI_DECISION: "AI decision",
  DETERMINISTIC_GATE: "Gate", PREREQUISITE_PROBE: "Prerequisite probe", REMEDIATION: "Remediation",
  BRANCH: "Branch", RETURN: "Return", TRANSFER: "Transfer", REFLECT: "Reflection",
  COMPLETE: "Complete", HUMAN_REVIEW: "Human review",
};
export const typeIcons: Partial<Record<NodeType, string>> = {
  START: "flag", DISCOVERY: "compass", QUIZ: "ui-checks", LESSON: "journal-text", TOPIC: "bookmark",
  INTERACTION: "puzzle", HINT: "lightbulb", FEEDBACK: "chat-square-text", AI_DECISION: "magic",
  DETERMINISTIC_GATE: "signpost", PREREQUISITE_PROBE: "search", REMEDIATION: "sign-turn-right",
  BRANCH: "diagram-2", RETURN: "arrow-return-left", TRANSFER: "rocket-takeoff", REFLECT: "chat-quote",
  COMPLETE: "check2-circle", HUMAN_REVIEW: "person-check",
};

/** Short card subtitle without repeating the title. */
export function nodeSubtitle(node: { label: string; type: NodeType; topic?: string; activity_ref?: string; prompt: string }): string {
  const parts = [node.label === typeNames[node.type] ? "" : typeNames[node.type], node.topic || "", node.activity_ref ? "Activity bound" : ""].filter(Boolean);
  if (parts.length) return parts.join(" · ");
  const prompt = node.prompt.replace(/\s+/g, " ").trim();
  return prompt.length > 90 ? `${prompt.slice(0, 90)}…` : prompt;
}

export function nodeLabel(program: Program, key: string): string {
  return program.nodes.find(node => node.key === key)?.label || key;
}

/** Generated sentence for a typed rule; independent of the editable annotation. */
export function ruleSentence(program: Program, edge: Edge): string {
  return `${outcomeClauses[edge.outcome]}, go to ${nodeLabel(program, edge.to_key)}.`;
}

/** The instructor's annotation when written, otherwise the generated sentence. */
export function ruleText(program: Program, edge: Edge): string {
  return edge.annotation?.trim() || ruleSentence(program, edge);
}

export function outgoing(program: Program, key: string): { edge: Edge; index: number }[] {
  return program.edges.map((edge, index) => ({ edge, index }))
    .filter(({ edge }) => edge.from_key === key)
    .sort((a, b) => a.edge.priority - b.edge.priority);
}

/** Whole-flow narrative for the "Natural language" representation. */
export function describeProgram(program: Program): { summary: string; steps: { key: string; heading: string; body: string; rules: string[] }[] } {
  const steps = program.nodes.map((node, index) => {
    const rules = outgoing(program, node.key).map(({ edge }) => {
      const generated = ruleSentence(program, edge);
      const note = edge.annotation?.trim();
      return note && note !== generated ? `${generated} (${note})` : generated;
    });
    if (!rules.length && node.type !== "COMPLETE") rules.push(`No rule leaves this step; the journey falls back to ${nodeLabel(program, program.fallback_key)}.`);
    return {
      key: node.key,
      heading: `${index + 1}. ${node.label}${node.label === typeNames[node.type] ? "" : ` — ${typeNames[node.type]}`}${node.topic ? ` · ${node.topic}` : ""}`,
      body: node.prompt || "No student-facing content yet.",
      rules,
    };
  });
  const source = program.source.problem_code ? ` It is grounded in source problem ${program.source.problem_code}.` : "";
  return {
    summary: `The journey starts at ${nodeLabel(program, program.entry)} and has ${program.nodes.length} steps and ${program.edges.length} rules. ` +
      `If no rule applies, students go to ${nodeLabel(program, program.fallback_key)}; at most ${program.max_transitions} moves are allowed.${source}`,
    steps,
  };
}
