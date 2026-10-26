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
export type Role = "admin" | "student";
export type Capability = "author" | "review_mathematics" | "review_pedagogy" | "publish" | "manage_users" | "preview";
export interface Session {
  actor: string | { username?: string; name?: string; actor_id?: string; capabilities?: Capability[] };
  csrf_token: string; auth_mode?: "cognito" | "local"; role?: Role; roles?: Role[];
}
export interface UserSummary {
  username: string; email: string | null; email_verified: boolean; name: string | null;
  status: string; enabled: boolean; created_at: string | null; updated_at: string | null; groups: string[];
}
export interface AccessEvent { action: string; actor_type: string; actor_id: string | null; occurred_at: string; detail: Record<string, unknown> }
export interface UserDetail extends UserSummary {
  mfa: string[];
  access: { last_sign_in_at: string | null; sign_ins_30d: number; failed_sign_ins_30d: number; role_switches_30d: number; admin_actions_30d: number; audit_enabled: boolean };
  events: AccessEvent[];
}
export interface UserPage { users: UserSummary[]; next_token: string | null; manageable_groups: string[]; role_matrix: Record<string, string[]> }
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

export const roleLabels: Record<Role, string> = { admin: "Admin", student: "Student" };
export function can(session: Session | null, capability: Capability): boolean {
  if (!session) return false;
  const actor = session.actor;
  // Older sessions without capabilities are author sessions (pre-roles contract).
  if (typeof actor === "string" || !actor.capabilities) return capability === "author" || capability === "preview";
  return actor.capabilities.includes(capability);
}
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
