import { useState } from "react";
import type { Edge, Program, Strategy, Validation, Workflow, WorkflowNode } from "./contracts";
import { nodeTypes, outcomes } from "./contracts";
import { outcomeLabels, outgoing, ruleSentence, ruleText, typeNames } from "./narrative";
import { Icon, MathText, Pill } from "./ui";

const hasMath = (value: string) => /\\\(|\\\[|\$/.test(value);

export function StepPanel({ program, nodeKey, disabled, edit, onRule, onAddRule, onRemoved }: {
  program: Program; nodeKey: string; disabled: boolean; edit: (program: Program) => void;
  onRule: (index: number) => void; onAddRule: () => void; onRemoved: () => void;
}) {
  const [confirm, setConfirm] = useState(false);
  const node = program.nodes.find(item => item.key === nodeKey);
  if (!node) return <p className="sc-tiny">This step no longer exists in the draft.</p>;
  const update = (patch: Partial<WorkflowNode>) =>
    edit({ ...program, nodes: program.nodes.map(item => item.key === nodeKey ? { ...item, ...patch } : item) });
  const protectedNode = node.key === program.entry || node.key === program.fallback_key;
  return <div className="sc-form">
    <div className="sc-kicker">{typeNames[node.type]} · <code>{node.key}</code></div>
    <label>Step title<input value={node.label} disabled={disabled} maxLength={200} onChange={event => update({ label: event.target.value })} /></label>
    <label>Student-facing question or content<textarea value={node.prompt} disabled={disabled} maxLength={12000}
      onChange={event => update({ prompt: event.target.value })} /></label>
    {hasMath(node.prompt) && <div className="sc-math-preview" aria-label="Rendered content"><MathText text={node.prompt} /></div>}
    <label>Step type<select value={node.type} disabled={disabled} onChange={event => update({ type: event.target.value as WorkflowNode["type"] })}>
      {nodeTypes.map(type => <option key={type} value={type}>{typeNames[type]}</option>)}
    </select></label>
    <h3 className="sc-section-title">Connections</h3>
    {outgoing(program, node.key).map(({ edge, index }) => <button type="button" key={index} className="sc-list-row" disabled={disabled} onClick={() => onRule(index)}>
      <span><MathText text={ruleText(program, edge)} /></span><Icon name="chevron-right" />
    </button>)}
    {!outgoing(program, node.key).length && <p className="sc-tiny">No rules leave this step yet.</p>}
    <button type="button" className="sc-light" disabled={disabled} onClick={onAddRule}><Icon name="plus-lg" />Add branching rule</button>
    <details className="sc-more"><summary>More settings</summary><div className="sc-form">
      <label>Topic<input value={node.topic || ""} disabled={disabled} maxLength={200} onChange={event => update({ topic: event.target.value || undefined })} /></label>
      <label>Learning objective<input value={node.objective || ""} disabled={disabled} maxLength={4000} onChange={event => update({ objective: event.target.value || undefined })} /></label>
      <label>Activity reference<input value={node.activity_ref || ""} disabled={disabled} maxLength={200} placeholder="activity.definition UUID"
        onChange={event => update({ activity_ref: event.target.value || undefined })} /></label>
      <label>Source claim reference<input value={node.source_claim_ref || ""} disabled={disabled} maxLength={200} onChange={event => update({ source_claim_ref: event.target.value || undefined })} /></label>
      <label>Accessible alternative<textarea value={node.accessible_alternative || ""} disabled={disabled} maxLength={12000}
        onChange={event => update({ accessible_alternative: event.target.value || undefined })} /></label>
      <p className="sc-tiny">The server scores the bound activity; answer keys never reach the student view.</p>
      {protectedNode ? <p className="sc-tiny">This is the entry or fallback step; change that in workflow settings before removing it.</p>
        : confirm ? <div className="sc-row"><button type="button" className="sc-danger" disabled={disabled} onClick={() => {
          edit({ ...program, nodes: program.nodes.filter(item => item.key !== node.key), edges: program.edges.filter(edge => edge.from_key !== node.key && edge.to_key !== node.key) });
          onRemoved();
        }}>Remove step and its rules</button><button type="button" className="sc-light" onClick={() => setConfirm(false)}>Cancel</button></div>
        : <button type="button" className="sc-light sc-danger-text" disabled={disabled} onClick={() => setConfirm(true)}><Icon name="trash" />Remove step…</button>}
    </div></details>
  </div>;
}

export function RulePanel({ program, index, disabled, edit, onRemoved }: {
  program: Program; index: number; disabled: boolean; edit: (program: Program) => void; onRemoved: () => void;
}) {
  const edge = program.edges[index];
  if (!edge) return <p className="sc-tiny">This rule no longer exists in the draft.</p>;
  const update = (patch: Partial<Edge>) => edit({ ...program, edges: program.edges.map((item, i) => i === index ? { ...item, ...patch } : item) });
  return <div className="sc-form">
    <div className="sc-kicker">Plain language</div>
    <label>Describe what should happen<textarea value={edge.annotation || ""} disabled={disabled} maxLength={4000}
      placeholder={ruleSentence(program, edge)} onChange={event => update({ annotation: event.target.value })} /></label>
    <div className="sc-hint"><Icon name="info-circle" /> The typed rule below decides the route: <MathText text={ruleSentence(program, edge)} />
      {edge.annotation?.trim() && " Re-read your description after changing it."}</div>
    <h3 className="sc-section-title">Rule</h3>
    <label>From step<select value={edge.from_key} disabled={disabled} onChange={event => update({ from_key: event.target.value })}>
      {program.nodes.map(node => <option key={node.key} value={node.key}>{node.label}</option>)}
    </select></label>
    <label>When the student…<select value={edge.outcome} disabled={disabled} onChange={event => update({ outcome: event.target.value as Edge["outcome"] })}>
      {outcomes.map(value => <option key={value} value={value}>{outcomeLabels[value]}</option>)}
    </select></label>
    <label>Go to<select value={edge.to_key} disabled={disabled} onChange={event => update({ to_key: event.target.value })}>
      {program.nodes.filter(node => node.key !== edge.from_key).map(node => <option key={node.key} value={node.key}>{node.label}</option>)}
    </select></label>
    <label>Priority <span className="sc-tiny">(lower runs first)</span><input type="number" min="0" max="10000" step="1" value={edge.priority} disabled={disabled}
      onChange={event => { if (event.target.value && event.target.validity.valid) update({ priority: Number(event.target.value) }); }} /></label>
    <button type="button" className="sc-light sc-danger-text" disabled={disabled} onClick={() => {
      edit({ ...program, edges: program.edges.filter((_, i) => i !== index) }); onRemoved();
    }}><Icon name="trash" />Remove rule</button>
  </div>;
}

export function NewRulePanel({ program, from, disabled, onAdd }: {
  program: Program; from?: string; disabled: boolean; onAdd: (edge: Edge) => void;
}) {
  const [source, setSource] = useState(from || program.nodes[0]?.key || "");
  const [outcome, setOutcome] = useState<Edge["outcome"]>("SUCCESS");
  const [target, setTarget] = useState("");
  const [annotation, setAnnotation] = useState("");
  const used = new Set(program.edges.filter(edge => edge.from_key === source && edge.outcome === outcome).map(edge => edge.priority));
  let priority = 10; while (used.has(priority)) priority += 10;
  return <form className="sc-form" id="new-rule" onSubmit={event => {
    event.preventDefault();
    if (source && target && source !== target) onAdd({ from_key: source, to_key: target, outcome, priority, annotation: annotation.trim() || undefined });
  }}>
    <label>From step<select value={source} disabled={disabled} onChange={event => setSource(event.target.value)}>
      {program.nodes.map(node => <option key={node.key} value={node.key}>{node.label}</option>)}
    </select></label>
    <label>When the student…<select value={outcome} disabled={disabled} onChange={event => setOutcome(event.target.value as Edge["outcome"])}>
      {outcomes.map(value => <option key={value} value={value}>{outcomeLabels[value]}</option>)}
    </select></label>
    <label>Go to<select value={target} required disabled={disabled} onChange={event => setTarget(event.target.value)}>
      <option value="">Choose a step…</option>
      {program.nodes.filter(node => node.key !== source).map(node => <option key={node.key} value={node.key}>{node.label}</option>)}
    </select></label>
    <label>Explanation (optional)<textarea value={annotation} disabled={disabled} maxLength={4000}
      placeholder="Why this branch helps the student…" onChange={event => setAnnotation(event.target.value)} /></label>
    {target && <div className="sc-hint"><MathText text={ruleSentence(program, { from_key: source, to_key: target, outcome, priority })} /></div>}
  </form>;
}

export function NewStepPanel({ program, onAdd }: { program: Program; onAdd: (node: WorkflowNode) => void }) {
  const [label, setLabel] = useState("New discovery");
  const [type, setType] = useState<WorkflowNode["type"]>("DISCOVERY");
  const base = label.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || "step";
  let key = /^[a-z]/.test(base) ? base : `step-${base}`; let n = 2;
  while (program.nodes.some(node => node.key === key)) key = `${base}-${n++}`;
  return <form className="sc-form" id="new-step" onSubmit={event => {
    event.preventDefault();
    if (label.trim()) onAdd({ key, label: label.trim(), type, prompt: "" });
  }}>
    <label>Step title<input value={label} required maxLength={200} onChange={event => setLabel(event.target.value)} /></label>
    <label>Type<select value={type} onChange={event => setType(event.target.value as WorkflowNode["type"])}>
      {nodeTypes.filter(value => value !== "START").map(value => <option key={value} value={value}>{typeNames[value]}</option>)}
    </select></label>
    <p className="sc-tiny">Key <code>{key}</code> is permanent once saved.</p>
  </form>;
}

export function NewWorkflowPanel({ strategies, initial, onCreate }: {
  strategies: Strategy[]; initial?: Strategy | null; onCreate: (title: string, domain: string, strategy: string) => void;
}) {
  const [title, setTitle] = useState(initial ? initial.label : "");
  const [domain, setDomain] = useState(initial?.domain || "");
  const [strategy, setStrategy] = useState(initial?.code || "");
  const domains = [...new Set(strategies.map(item => item.domain))].sort();
  return <form className="sc-form" id="new-workflow" onSubmit={event => {
    event.preventDefault();
    if (title.trim() && domain) onCreate(title.trim(), domain, strategy);
  }}>
    <label>Workflow title<input value={title} required maxLength={200} onChange={event => setTitle(event.target.value)} /></label>
    <label>Domain<select value={domain} required onChange={event => { setDomain(event.target.value); setStrategy(""); }}>
      <option value="">Choose a domain…</option>{domains.map(value => <option key={value}>{value}</option>)}
    </select></label>
    {domain && <label>Teaching strategy<select value={strategy} onChange={event => setStrategy(event.target.value)}>
      <option value="">Default for {domain}</option>
      {strategies.filter(item => item.domain === domain).map(item => <option key={item.code} value={item.code}>{item.label}</option>)}
    </select></label>}
  </form>;
}

export function SettingsPanel({ workflow, program, strategies, validation, disabled, dirty, edit, onValidate, onSources, onDiscard }: {
  workflow: Workflow; program: Program; strategies: Strategy[]; validation: Validation | null; disabled: boolean; dirty: boolean;
  edit: (program: Program) => void; onValidate: () => void; onSources: () => void; onDiscard: () => void;
}) {
  return <div className="sc-form">
    <label>Teaching strategy<select value={program.strategy_code} disabled={disabled} onChange={event => edit({ ...program, strategy_code: event.target.value })}>
      {!strategies.some(item => item.code === program.strategy_code) && <option value={program.strategy_code}>{program.strategy_code}</option>}
      {strategies.filter(item => item.domain === workflow.domain).map(item => <option key={item.code} value={item.code}>{item.label}</option>)}
    </select></label>
    <label>Entry step<select value={program.entry} disabled={disabled} onChange={event => edit({ ...program, entry: event.target.value })}>
      {program.nodes.map(node => <option key={node.key} value={node.key}>{node.label}</option>)}
    </select></label>
    <label>Fallback step<select value={program.fallback_key} disabled={disabled} onChange={event => edit({ ...program, fallback_key: event.target.value })}>
      {program.nodes.map(node => <option key={node.key} value={node.key}>{node.label}</option>)}
    </select></label>
    <label>Maximum moves per session<input type="number" min="1" max="500" step="1" value={program.max_transitions} disabled={disabled}
      onChange={event => { if (event.target.value && event.target.validity.valid) edit({ ...program, max_transitions: Number(event.target.value) }); }} /></label>
    <h3 className="sc-section-title">Source</h3>
    <dl className="sc-facts">
      <dt>Problem</dt><dd>{program.source.problem_code || "Not linked"}</dd>
      <dt>Solution revision</dt><dd>{program.source.solution_id ? `r${program.source.solution_revision}` : "Not linked"}</dd>
      <dt>Released route</dt><dd>{program.source.route_release_id ? "Linked" : "None"}</dd>
    </dl>
    <button type="button" className="sc-light" disabled={disabled} onClick={onSources}><Icon name="database" />Choose source…</button>
    <h3 className="sc-section-title">Check</h3>
    <button type="button" className="sc-light" disabled={disabled} onClick={onValidate}><Icon name="check2-square" />Save & validate structure</button>
    {validation && <div className={`sc-hint${validation.valid ? "" : " sc-warn"}`} role="status">
      <strong>{validation.valid ? "Structure is valid." : "Needs changes:"}</strong>
      {validation.findings.length > 0 && <ul>{validation.findings.map((finding, i) => <li key={i}><MathText text={finding} /></li>)}</ul>}
      <span className="sc-tiny">Structure only — not mathematical review or publication.</span>
    </div>}
    {dirty && <button type="button" className="sc-light sc-danger-text" disabled={disabled} onClick={onDiscard}><Icon name="arrow-counterclockwise" />Discard unsaved edits</button>}
    <details className="sc-more"><summary>Draft identity</summary><code className="sc-tiny">{workflow.workflow_id}<br />revision {workflow.revision} · {workflow.content_hash}</code>
      <p className="sc-tiny"><Pill tone="warning">Prototype</Pill> Drafts only; publishing is not available.</p></details>
  </div>;
}

