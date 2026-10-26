import { useState } from "react";
import type { Edge, Job, Program } from "./contracts";
import { edgeDescription, outcomes, priorEdges } from "./contracts";
import { nodeLabel, outcomeLabels, ruleSentence } from "./narrative";
import { Icon, MathText, Pill } from "./ui";

export function Coauthor({ program, instruction, setInstruction, job, baseHash, stale, disabled, polling, onRequest, onAccept, onReject, onResume }: {
  program: Program; instruction: string; setInstruction: (value: string) => void;
  job?: Job; baseHash?: string; stale: boolean; disabled: boolean; polling: boolean;
  onRequest: () => void; onAccept: (candidate?: Edge) => void; onReject: () => void; onResume: () => void;
}) {
  const [candidate, setCandidate] = useState<Edge | null>(null);
  const result = job?.result;
  const edge = candidate || result;
  const inProgress = job && ["QUEUED", "RUNNING"].includes(job.status);
  return <div className="sc-form" aria-label="AI rule proposal">
    <div className="sc-kicker">Natural-language authoring</div>
    <p className="sc-desc">Describe a rule in plain English. You review the proposal before anything changes.</p>
    <label>Rule instruction<textarea value={instruction} disabled={disabled} maxLength={2000} onChange={event => setInstruction(event.target.value)}
      placeholder="If a student answers the quiz incorrectly, send them to the Bijections mini-lesson." /></label>
    <div className="sc-row">
      <button type="button" className="sc-primary" disabled={disabled || !instruction.trim() || !!inProgress} onClick={onRequest}><Icon name="stars" />Propose rule</button>
      <button type="button" className="sc-light" disabled={disabled} onClick={() => {
        const from = program.nodes.find(node => node.type === "QUIZ") || program.nodes[0];
        const to = program.nodes.find(node => node.key !== from?.key && ["REMEDIATION", "LESSON", "TOPIC"].includes(node.type));
        setInstruction(from && to ? `If the student answers ${from.label} incorrectly, send them to ${to.label}.` : "After completing the current activity, continue to the next approved discovery.");
      }}>Example</button>
    </div>
    {job && <div className="sc-student-box sc-form">
      <div className="sc-row"><Pill>{job.status}</Pill>{inProgress && <span className="sc-tiny" role="status">{polling ? "Waiting for the proposal…" : "Paused."}</span>}</div>
      {job.error && <p role="alert"><MathText text={job.error} /></p>}
      {inProgress && !polling && <button type="button" className="sc-light" disabled={disabled} onClick={onResume}>Check status</button>}
      {job.status === "SUCCEEDED" && !result && <p role="alert">The job finished without a proposed rule.</p>}
      {job.status === "SUCCEEDED" && result && edge && <>
        <strong>Proposed rule</strong>
        <p><MathText text={ruleSentence(program, edge)} /></p>
        <p className="sc-tiny"><MathText text={result.explanation} /></p>
        <details className="sc-more" aria-label="Proposed edge comparison"><summary>Compare and adjust</summary><div className="sc-form">
          <div className="sc-tiny">Current matching rules: {priorEdges(program, edge).length ? priorEdges(program, edge).map((prior, index) => <code key={index}>{edgeDescription(prior)} </code>) : "none"}</div>
          <div className="sc-tiny">Proposed: <code>{edgeDescription(edge)}</code></div>
          <label>Proposed source<select disabled={disabled || stale} value={edge.from_key} onChange={event => setCandidate({ ...edge, from_key: event.target.value })}>
            {program.nodes.map(node => <option key={node.key} value={node.key}>{nodeLabel(program, node.key)}</option>)}
          </select></label>
          <label>Proposed outcome<select disabled={disabled || stale} value={edge.outcome} onChange={event => setCandidate({ ...edge, outcome: event.target.value as Edge["outcome"] })}>
            {outcomes.map(value => <option key={value} value={value}>{outcomeLabels[value]}</option>)}
          </select></label>
          <label>Proposed destination<select disabled={disabled || stale} value={edge.to_key} onChange={event => setCandidate({ ...edge, to_key: event.target.value })}>
            {program.nodes.filter(node => node.key !== edge.from_key).map(node => <option key={node.key} value={node.key}>{nodeLabel(program, node.key)}</option>)}
          </select></label>
          <label>Proposed priority<input type="number" min="0" step="1" value={edge.priority} disabled={disabled || stale} onChange={event => {
            if (event.target.value && event.target.validity.valid) setCandidate({ ...edge, priority: Number(event.target.value) });
          }} /></label>
          <code className="sc-tiny">{result.model_id} · base {baseHash?.slice(0, 12)}</code>
        </div></details>
        {stale && <p className="sc-hint sc-warn">The draft changed since this proposal. Dismiss it and ask again.</p>}
        <div className="sc-row">
          <button type="button" className="sc-primary" disabled={disabled || stale || edge.from_key === edge.to_key}
            onClick={() => onAccept(candidate ? { from_key: candidate.from_key, to_key: candidate.to_key, outcome: candidate.outcome, priority: candidate.priority } : undefined)}>Accept into draft</button>
          <button type="button" className="sc-light" disabled={disabled} onClick={onReject}>Dismiss</button>
        </div>
      </>}
      {!(job.status === "SUCCEEDED" && result) && <button type="button" className="sc-light" disabled={disabled} onClick={onReject}>Dismiss</button>}
    </div>}
  </div>;
}
