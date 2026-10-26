export const outcomes = ["ALWAYS", "SUCCESS", "RETRY", "UNCERTAIN"] as const;
export type Outcome = typeof outcomes[number];
export const nodeTypes = ["START", "DISCOVERY", "QUIZ", "LESSON", "TOPIC", "INTERACTION", "HINT", "FEEDBACK", "AI_DECISION", "DETERMINISTIC_GATE", "PREREQUISITE_PROBE", "REMEDIATION", "BRANCH", "RETURN", "TRANSFER", "REFLECT", "COMPLETE", "HUMAN_REVIEW"] as const;
export type NodeType = typeof nodeTypes[number];
export interface WorkflowNode {
  key: string; label: string; type: NodeType; prompt: string;
  topic?: string; objective?: string; source_claim_ref?: string; activity_ref?: string;
  accessible_alternative?: string;
}
export interface Edge { from_key: string; to_key: string; outcome: Outcome; priority: number; annotation?: string }
export interface Source { problem_code: string | null; solution_id: string | null; solution_revision?: number | null; route_release_id: string | null }
export interface Program {
  schema_version: "socratic.prototype.v1";
  strategy_code: string;
  source: Source;
  entry: string;
  nodes: WorkflowNode[];
  edges: Edge[];
  fallback_key: string;
  max_transitions: number;
}
export interface WorkflowSummary {
  workflow_id: string; title: string; domain: string; content_hash: string; revision: number; updated_at?: string;
}
export interface Workflow extends WorkflowSummary { program: Program; prototype_only: true }
export interface Strategy { code: string; domain: string; label: string; status: "DRAFT"; phases: string[] }
export interface Resource {
  canonical_code: string; problem_id: string; statement_text: string;
  solutions: { solution_id: string; revision: number; verification_status: string }[];
  routes: { route_release_id: string; solution_id?: string; status: string; approach_name: string }[];
}
export interface Session { actor: string | { username?: string; name?: string; actor_id?: string }; csrf_token: string; auth_mode?: "cognito" | "local" }
export interface Job {
  job_id: string; status: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED"; error: string | null;
  result: (Edge & { explanation: string; model_id: string }) | null;
}
export interface Preview {
  preview_id: string; workflow_id: string; state_version: number;
  workflow_revision?: number; content_hash?: string; transitions_used?: number; max_transitions?: number;
  current_node: WorkflowNode; status: "ACTIVE" | "COMPLETE"; synthetic: true;
  activity?: {
    activity_id: string; revision: string;
    kind: "SINGLE_CHOICE" | "MULTI_SELECT" | "ASSERTION_REASON" | "FREE_FORM_REASONING" | "NUMERIC_EXACT";
    prompt?: string;
    options?: { key: string; text: string }[];
  } | null;
  feedback?: string | null;
  help?: { level: number; text: string; assisted: boolean } | null;
  history: {
    node_key: string; decision_source: string; reason: string;
    from_key?: string; to_key?: string; outcome?: Outcome; rule_id?: string; assisted?: boolean;
  }[];
}
export type PreviewAnswer = { selected_keys: string[] } | { text: string };
export interface Validation { valid: boolean; findings: string[] }

export function actorName(actor: Session["actor"]): string {
  return typeof actor === "string" ? actor : actor.name || actor.username || actor.actor_id || "Administrator";
}
export function isDirty(workflow: Workflow | null, program: Program | null): boolean {
  return !!workflow && !!program && JSON.stringify(workflow.program) !== JSON.stringify(program);
}
export function edgeDescription(edge: Edge): string {
  return `${edge.from_key} — ${edge.outcome} → ${edge.to_key} · priority ${edge.priority}`;
}
export function priorEdges(program: Program, proposed: Edge): Edge[] {
  return program.edges.filter(edge => edge.from_key === proposed.from_key && edge.outcome === proposed.outcome);
}
