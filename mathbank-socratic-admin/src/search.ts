// Workspace search: pure, framework-free, unit-tested. The sidebar renders its results.
import type { Program, Strategy, WorkflowNode, WorkflowSummary } from "./contracts";

export interface StepHit { key: string; label: string; type: WorkflowNode["type"]; match: string }
export interface DomainGroup { domain: string; workflows: WorkflowSummary[] }
export interface SearchResults {
  query: string;
  domains: DomainGroup[];
  steps: StepHit[];
  strategies: Strategy[];
  total: number;
}

export function normalize(value: string): string {
  return value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/[\\{}$^_]/g, " ")
    .replace(/[–—]/g, "-").toLowerCase().replace(/\s+/g, " ").trim();
}

export function terms(query: string): string[] {
  return normalize(query).split(" ").filter(Boolean);
}

/** Every term must appear somewhere in the combined fields (order-insensitive AND match). */
export function matches(query: string, ...fields: (string | null | undefined)[]): boolean {
  const wanted = terms(query);
  if (!wanted.length) return true;
  const haystack = normalize(fields.filter(Boolean).join(" "));
  return wanted.every(term => haystack.includes(term));
}

function snippet(text: string, query: string, width = 60): string {
  const plain = text.replace(/\s+/g, " ").trim();
  const first = terms(query)[0];
  const at = first ? normalize(plain).indexOf(first) : -1;
  if (at < 0 || plain.length <= width) return plain.slice(0, width) + (plain.length > width ? "…" : "");
  const start = Math.max(0, at - 20);
  return (start ? "…" : "") + plain.slice(start, start + width) + (start + width < plain.length ? "…" : "");
}

export function searchWorkspace(query: string, data: {
  workflows: WorkflowSummary[]; strategies: Strategy[]; program: Program | null;
}): SearchResults {
  const domainNames = [...new Set([...data.strategies.map(item => item.domain), ...data.workflows.map(item => item.domain)])]
    .sort((a, b) => a.localeCompare(b));
  const domains = domainNames.map(domain => ({
    domain,
    workflows: data.workflows.filter(item => item.domain === domain && matches(query, item.title, item.domain)),
  })).filter(group => group.workflows.length);
  const steps: StepHit[] = [];
  if (data.program && terms(query).length) {
    for (const node of data.program.nodes) {
      const rules = data.program.edges.filter(edge => edge.from_key === node.key).map(edge => edge.annotation || "");
      if (matches(query, node.label, node.prompt, node.topic, node.type, node.objective, ...rules)) {
        const field = [node.label, node.topic, node.prompt, ...rules].find(value => value && matches(query.split(" ")[0] || "", value)) || node.prompt;
        steps.push({ key: node.key, label: node.label, type: node.type, match: snippet(field || "", query) });
      }
    }
  }
  const strategies = terms(query).length
    ? data.strategies.filter(item => matches(query, item.label, item.code, item.domain, ...item.phases)) : [];
  const total = domains.reduce((sum, group) => sum + group.workflows.length, 0) + steps.length + strategies.length;
  return { query, domains, steps, strategies, total };
}
