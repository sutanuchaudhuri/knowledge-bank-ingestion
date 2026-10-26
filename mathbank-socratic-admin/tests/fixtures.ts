import type { Preview, Workflow } from "../src/contracts";
export const workflow: Workflow = {
  workflow_id: "workflow-1", title: "Discovery draft", domain: "Counting",
  revision: 1, content_hash: "hash-1", prototype_only: true,
  program: {
    schema_version: "socratic.prototype.v1", strategy_code: "COUNTING",
    source: { problem_code: null, solution_id: null, route_release_id: null },
    entry: "start", fallback_key: "remediate", max_transitions: 20,
    nodes: [
      { key: "start", type: "START", label: "Explore", prompt: "Explore \\(x+1\\)." },
      { key: "remediate", type: "REMEDIATION", label: "Revisit", prompt: "Try a smaller example." },
      { key: "complete", type: "COMPLETE", label: "Finish", prompt: "Synthetic journey ended." },
    ],
    edges: [{ from_key: "start", to_key: "remediate", outcome: "RETRY", priority: 0 }],
  },
};
export const preview: Preview = {
  preview_id: "preview-1", workflow_id: "workflow-1", state_version: 0, status: "ACTIVE", synthetic: true,
  current_node: workflow.program.nodes[0], history: [],
};
export const assessmentPreview: Preview = {
  ...preview,
  current_node: { key: "start", type: "QUIZ", label: "Stars and Bars · Assertion–Reason",
    prompt: "Assertion: The number of nonnegative solutions of \\(x+y+z=5\\) is 21. Reason: Each solution corresponds uniquely to five stars and two separators." },
  activity: {
    activity_id: "approved-ar", revision: "1", kind: "ASSERTION_REASON",
    prompt: "Judge the assertion and the reason separately.",
    options: [
      { key: "AR1", text: "Both true; reason explains assertion" },
      { key: "AR2", text: "Both true; reason does not explain assertion" },
      { key: "AR3", text: "Assertion true; reason false" },
      { key: "AR4", text: "Assertion false; reason true" },
      { key: "AR5", text: "Both false" },
    ],
  },
};
