import { useState } from "react";
import type { Edge, Job, Program } from "./contracts";
import { edgeDescription, outcomes, priorEdges } from "./contracts";
import { outcomeLabels } from "./RuleEditor";
import { MathText, Pill } from "./ui";

export function Coauthor({ program, instruction, setInstruction, job, baseHash, stale, disabled, polling, onRequest, onAccept, onReject, onResume }: {
  program: Program; instruction: string; setInstruction: (value: string) => void;
  job?: Job; baseHash?: string; stale: boolean; disabled: boolean; polling: boolean;
  onRequest: () => void; onAccept: (candidate?: Edge) => void; onReject: () => void; onResume: () => void;
}) {
  const [candidate, setCandidate] = useState<Edge | null>(null);
  const result = job?.result;
  const edge = candidate || result;
  const inProgress = job && ["QUEUED", "RUNNING"].includes(job.status);
  const label = (key: string) => program.nodes.find(node => node.key === key)?.label || key;
  return <section className="sc-card sc-stack" aria-label="AI rule proposal">
    <div className="sc-toolbar sc-between"><h2>✦ Create a rule in natural language</h2><Pill tone="warning">Review before apply</Pill></div>
    <p className="sc-muted">Describe the instructor's intent. The agent returns a typed proposal, not a direct edit; review the source, condition and destination.</p>
    <label>Rule instruction<textarea value={instruction} disabled={disabled} maxLength={2000} onChange={event => setInstruction(event.target.value)}
      placeholder="If the student gets the Assertion–Reason quiz wrong, send them to the Bijections mini-lesson." /></label>
    <div className="sc-toolbar">
      <button className="sc-primary" disabled={disabled || !instruction.trim() || !!inProgress} onClick={onRequest}>Save draft & request proposal</button>
      <button disabled={disabled} onClick={() => {
        const from = program.nodes.find(node => node.type === "QUIZ") || program.nodes[0];
        const to = program.nodes.find(node => node.key !== from?.key && ["REMEDIATION", "LESSON", "TOPIC"].includes(node.type));
        setInstruction(from && to ? `If the student answers ${from.label} incorrectly, send them to ${to.label}.` : "After completing the current activity, continue to the next approved discovery.");
      }}>Example</button>
    </div>
    {job && <div className="sc-drawer sc-stack">
      <div className="sc-toolbar"><Pill>{job.status}</Pill><code>{job.job_id}</code></div>
      {job.error && <p role="alert"><MathText text={job.error} /></p>}
      {inProgress && <div className="sc-toolbar"><span role="status">{polling ? "Waiting for server proposal (bounded polling)…" : "Polling paused. Check status to resume."}</span>
        <button disabled={disabled || polling} onClick={onResume}>Check status / resume polling</button></div>}
      {job.status === "SUCCEEDED" && !result && <p role="alert">The completed job has no proposed edge. It cannot be accepted.</p>}
      {job.status === "SUCCEEDED" && result && edge && <>
        <div className="sc-diff" aria-label="Proposed edge comparison">
          <div><h3>Before · saved matching edges</h3>{priorEdges(program, edge).length ? priorEdges(program, edge).map((prior, index) => <p key={index}><code>{edgeDescription(prior)}</code></p>) : <p>No matching source/outcome edge.</p>}</div>
          <div><h3>Proposed candidate</h3><code>{edgeDescription(edge)}</code></div>
        </div>
        <p><MathText text={result.explanation} /></p>
        <div className="sc-config">
          <label>Proposed source<select disabled={disabled || stale} value={edge.from_key} onChange={event => setCandidate({ ...edge, from_key: event.target.value })}>
            {program.nodes.map(node => <option key={node.key} value={node.key}>{label(node.key)}</option>)}
          </select></label>
          <label>Proposed outcome<select disabled={disabled || stale} value={edge.outcome} onChange={event => setCandidate({ ...edge, outcome: event.target.value as Edge["outcome"] })}>
            {outcomes.map(value => <option key={value} value={value}>{outcomeLabels[value]}</option>)}
          </select></label>
          <label>Proposed destination<select disabled={disabled || stale} value={edge.to_key} onChange={event => setCandidate({ ...edge, to_key: event.target.value })}>
            {program.nodes.filter(node => node.key !== edge.from_key).map(node => <option key={node.key} value={node.key}>{label(node.key)}</option>)}
          </select></label>
          <label>Proposed priority<input type="number" min="0" step="1" value={edge.priority} disabled={disabled || stale} onChange={event => {
            if (event.target.value && event.target.validity.valid) setCandidate({ ...edge, priority: Number(event.target.value) });
          }} /></label>
        </div>
        <p className="sc-warning">Not applied yet. Natural-language interpretation can misunderstand your instruction. REST must revalidate even an edited candidate.</p>
        <details><summary>Proposal provenance and base</summary><code>{result.model_id}<br />{baseHash}</code><p className="sc-muted">No automatic publish, mathematical approval or provider fallback.</p></details>
        {stale && <p className="sc-warning">The draft no longer matches this proposal. Reject it and request a new proposal for the saved draft.</p>}
        <button className="sc-primary" disabled={disabled || stale || edge.from_key === edge.to_key}
          onClick={() => onAccept(candidate ? { from_key: candidate.from_key, to_key: candidate.to_key, outcome: candidate.outcome, priority: candidate.priority } : undefined)}>Accept proposed edge into draft</button>
      </>}
      <button disabled={disabled} onClick={onReject}>Reject / dismiss proposal</button>
    </div>}
  </section>;
}
