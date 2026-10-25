import { useState } from "react";
import type { Edge, Program } from "./contracts";
import { outcomes } from "./contracts";
import { MathText, Pager, Pill } from "./ui";

export const outcomeLabels = {
  ALWAYS: "Completes the activity", SUCCESS: "Answers correctly",
  RETRY: "Needs another attempt", UNCERTAIN: "Needs clarification",
};

export function RuleEditor({ program, edit, disabled, onInspect, sourceKey, topic = "", onPropose }: {
  program: Program; edit: (program: Program) => void; disabled: boolean;
  onInspect: (key: string) => void; sourceKey?: string; topic?: string; onPropose?: () => void;
}) {
  const [page, setPage] = useState(0);
  const [source, setSource] = useState("");
  const [destination, setDestination] = useState("");
  const [outcome, setOutcome] = useState<Edge["outcome"]>("ALWAYS");
  const label = (key: string) => program.nodes.find(node => node.key === key)?.label || key;
  const shown = program.edges.map((edge, index) => ({ edge, index })).filter(({ edge }) =>
    (!sourceKey || edge.from_key === sourceKey) && (!topic || program.nodes.find(node => node.key === edge.from_key)?.topic === topic));
  function update(index: number, patch: Partial<Edge>) {
    edit({ ...program, edges: program.edges.map((edge, i) => i === index ? { ...edge, ...patch } : edge) });
  }
  return <div className="sc-stack">
    <div className="sc-toolbar sc-between"><h3>Instructor routing rules</h3><Pill>{shown.length} rules</Pill></div>
    {!shown.length && <p className="sc-muted">No outgoing rules in this selection.</p>}
    {shown.slice(page * 25, (page + 1) * 25).map(({ edge, index }) => <article className="sc-rule sc-stack" key={index}>
      <div className="sc-toolbar sc-between"><strong><MathText text={label(edge.from_key)} /></strong>
        <Pill>{program.nodes.find(node => node.key === edge.from_key)?.topic || "Workflow"}</Pill></div>
      <p className="sc-explain"><MathText text={`When the student ${outcomeLabels[edge.outcome].toLowerCase()}, go to ${label(edge.to_key)}.`} /></p>
      <div className="sc-muted">Structured rule: <code>{edge.from_key} · {edge.outcome} → {edge.to_key} · priority {edge.priority}</code></div>
      <div className="sc-config">
        <label>Source node<select value={edge.from_key} disabled={disabled} onChange={event => update(index, { from_key: event.target.value })}>
          {!program.nodes.some(node => node.key === edge.from_key) && <option>{edge.from_key}</option>}
          {program.nodes.map(node => <option key={node.key} value={node.key}>{node.label}</option>)}
        </select></label>
        <label>When the student…<select value={edge.outcome} disabled={disabled} onChange={event => update(index, { outcome: event.target.value as Edge["outcome"] })}>
          {outcomes.map(value => <option key={value} value={value}>{outcomeLabels[value]}</option>)}
        </select></label>
        <label>Send student to…<select value={edge.to_key} disabled={disabled} onChange={event => update(index, { to_key: event.target.value })}>
          {!program.nodes.some(node => node.key === edge.to_key) && <option>{edge.to_key}</option>}
          {program.nodes.filter(node => node.key !== edge.from_key).map(node => <option key={node.key} value={node.key}>{node.label}</option>)}
        </select></label>
        <label>Priority<input type="number" min="0" step="1" required disabled={disabled} value={edge.priority} onChange={event => {
          if (event.target.value && event.target.validity.valid) update(index, { priority: Number(event.target.value) });
        }} /></label>
      </div>
      <label>Plain-language explanation (editable)<textarea disabled={disabled} maxLength={2000} value={edge.annotation || ""}
        placeholder="Explain the instructional intent of this branch…" onChange={event => update(index, { annotation: event.target.value })} /></label>
      <span className="sc-muted">Annotation only; typed conditions remain authoritative. Recheck this explanation after changing the rule.</span>
      <div className="sc-toolbar sc-between">
        <button disabled={disabled} onClick={() => onInspect(edge.from_key)}>Test this rule ↗</button>
        <button className="sc-danger" disabled={disabled} onClick={() => {
          edit({ ...program, edges: program.edges.filter((_, i) => i !== index) }); setPage(0);
        }}>Delete rule</button>
      </div>
    </article>)}
    {shown.length > 25 && <Pager page={page} hasMore={(page + 1) * 25 < shown.length} onChange={setPage} disabled={disabled} />}
    <details><summary>Add a typed draft rule</summary>
      <form className="sc-config" onSubmit={event => {
        event.preventDefault();
        const from = sourceKey || source;
        if (!from || !destination || from === destination) return;
        edit({ ...program, edges: [...program.edges, { from_key: from, to_key: destination, outcome, priority: 10, annotation: "" }] });
        setDestination(""); setPage(0);
      }}>
        {!sourceKey && <label>New rule source<select required disabled={disabled} value={source} onChange={event => setSource(event.target.value)}>
          <option value="">Choose source…</option>{program.nodes.map(node => <option key={node.key} value={node.key}>{node.label}</option>)}
        </select></label>}
        <label>New rule outcome<select value={outcome} disabled={disabled} onChange={event => setOutcome(event.target.value as Edge["outcome"])}>
          {outcomes.map(value => <option key={value} value={value}>{outcomeLabels[value]}</option>)}
        </select></label>
        <label>New rule destination<select required disabled={disabled} value={destination} onChange={event => setDestination(event.target.value)}>
          <option value="">Choose destination…</option>{program.nodes.filter(node => node.key !== (sourceKey || source)).map(node => <option key={node.key} value={node.key}>{node.label}</option>)}
        </select></label>
        <button disabled={disabled || !(sourceKey || source) || !destination}>Add draft rule</button>
      </form>
    </details>
    {onPropose && <button disabled={disabled} onClick={onPropose}>＋ Add natural-language rule</button>}
  </div>;
}
