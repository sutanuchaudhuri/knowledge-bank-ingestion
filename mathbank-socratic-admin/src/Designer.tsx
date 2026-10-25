import { useState } from "react";
import type { KeyboardEvent } from "react";
import { nodeTypes } from "./contracts";
import type { Program, WorkflowNode, Preview, Strategy, PreviewAnswer } from "./contracts";
import { RuleEditor, outcomeLabels } from "./RuleEditor";
import { Simulator } from "./Simulator";
import { MathText, Pager, Pill } from "./ui";

export function Designer({ program, strategies, selected, setSelected, preview, disabled, edit, onSimulate, onTransition, onRefreshPreview, onSources, onPropose, onRespond, onAssist, onReveal }: {
  program: Program; strategies: Strategy[]; selected: string; setSelected: (key: string) => void;
  preview: Preview | null; disabled: boolean; edit: (program: Program) => void;
  onSimulate: () => void; onTransition: (outcome: "ALWAYS" | "SUCCESS" | "RETRY" | "UNCERTAIN") => void;
  onRefreshPreview: () => void; onSources: () => void;
  onPropose: () => void; onRespond: (answer: PreviewAnswer) => void; onAssist: () => void; onReveal: () => void;
}) {
  const [page, setPage] = useState(0);
  const [newKey, setNewKey] = useState("");
  const [deletePending, setDeletePending] = useState<string | null>(null);
  const node = program.nodes.find(item => item.key === selected);
  const pageNodes = program.nodes.slice(page * 25, (page + 1) * 25);
  const latest = preview?.history.at(-1);
  const label = (key: string) => program.nodes.find(item => item.key === key)?.label || key;
  function updateNode(patch: Partial<WorkflowNode>) {
    edit({ ...program, nodes: program.nodes.map(item => item.key === selected ? { ...item, ...patch } : item) });
  }
  function move(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const target = event.key === "ArrowDown" ? index + 1 : event.key === "ArrowUp" ? index - 1 : event.key === "Home" ? 0 : event.key === "End" ? pageNodes.length - 1 : -1;
    if (target < 0 || target >= pageNodes.length) return;
    event.preventDefault();
    setSelected(pageNodes[target].key);
    event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>(".sc-node")[target]?.focus();
  }
  return <div className="sc-stack">
    <div className="sc-toolbar sc-between"><p className="sc-muted">Inspect a node on the left; try its approved activity on the right.</p><button onClick={onSources} disabled={disabled}>Choose source references</button></div>
    <details className="sc-card">
      <summary>Draft configuration · Source, strategy and routing limits</summary>
      <div className="sc-stack">
      <h2>Draft configuration</h2>
      <div className="sc-config">
        <label>Strategy<select value={program.strategy_code} disabled={disabled} onChange={event => edit({ ...program, strategy_code: event.target.value })}>
          <option value="" disabled>Select a strategy…</option>
          {!strategies.some(item => item.code === program.strategy_code) && program.strategy_code && <option value={program.strategy_code}>{program.strategy_code} · unavailable in catalog</option>}
          {strategies.map(item => <option key={item.code} value={item.code}>{item.domain} · {item.label}</option>)}
        </select></label>
        <label>Entry node<select value={program.entry} disabled={disabled} onChange={event => edit({ ...program, entry: event.target.value })}>
          {!program.nodes.some(item => item.key === program.entry) && <option value={program.entry}>{program.entry} · unresolved</option>}
          {program.nodes.map(item => <option key={item.key} value={item.key}>{item.key}</option>)}
        </select></label>
        <label>Fallback node<select value={program.fallback_key} disabled={disabled} onChange={event => edit({ ...program, fallback_key: event.target.value })}>
          {!program.nodes.some(item => item.key === program.fallback_key) && <option value={program.fallback_key}>{program.fallback_key} · unresolved</option>}
          {program.nodes.map(item => <option key={item.key} value={item.key}>{item.key}</option>)}
        </select></label>
        <label>Transition budget<input type="number" min="1" max="100" step="1" required value={program.max_transitions} disabled={disabled} onChange={event => {
          if (event.target.value && event.target.validity.valid) edit({ ...program, max_transitions: Number(event.target.value) });
        }} /></label>
      </div>
      <dl className="sc-reference">
        <dt>Source problem</dt><dd>{program.source.problem_code || "Not linked"}</dd>
        <dt>Reference solution</dt><dd>{program.source.solution_id || "Not linked"}</dd>
        <dt>Released route</dt><dd>{program.source.route_release_id || "Not linked"}</dd>
      </dl>
      </div>
    </details>
    <div className="sc-designer-grid">
      <div className="sc-stack">
      <section className="sc-card sc-stack" aria-label="Workflow map">
        <div><h2>Workflow map</h2><p className="sc-muted">Arrow keys / Home / End inspect nodes. Selection never moves the synthetic session.</p></div>
        <div className="sc-graph sc-flow" role="group" aria-label="Keyboard workflow nodes">
          {pageNodes.map((item, index) => <button key={item.key} className={`sc-node${preview?.current_node.key === item.key ? " sc-current" : ""}`}
            aria-pressed={selected === item.key} disabled={disabled} onKeyDown={event => move(event, index)} onClick={() => setSelected(item.key)}>
            <span className="sc-muted">{item.type} · {item.topic || item.key}</span><strong><MathText text={item.label} /></strong>
            {selected === item.key && <span>Inspecting</span>}
            {preview?.current_node.key === item.key && <span>▶ Synthetic position</span>}
            <span className="sc-branches">{program.edges.filter(edge => edge.from_key === item.key).map((edge, edgeIndex) =>
              <span className={latest?.from_key === edge.from_key && latest.to_key === edge.to_key && latest.outcome === edge.outcome ? "sc-branch-hit" : ""} key={edgeIndex}>
                {latest?.from_key === edge.from_key && latest.to_key === edge.to_key && latest.outcome === edge.outcome ? "✓ Selected: " : ""}
                {outcomeLabels[edge.outcome]} → <MathText text={label(edge.to_key)} /> · {edge.priority}
              </span>)}</span>
          </button>)}
        </div>
        <p className="sc-muted">Blue = inspecting · Green = synthetic position · ✓ = last server-selected branch.</p>
        <Pager page={page} hasMore={(page + 1) * 25 < program.nodes.length} disabled={disabled} onChange={setPage} />
        <form className="sc-stack" onSubmit={event => {
          event.preventDefault();
          const key = newKey.trim();
          if (!/^[a-z][a-z0-9_-]*$/.test(key) || program.nodes.some(item => item.key === key)) return;
          edit({ ...program, nodes: [...program.nodes, { key, label: key, type: "DISCOVERY", prompt: "" }] });
          setSelected(key); setPage(Math.floor(program.nodes.length / 25)); setNewKey("");
        }}>
          <label>New immutable node key<input disabled={disabled} pattern="[a-z][a-z0-9_-]*" required value={newKey} onChange={event => setNewKey(event.target.value)} /></label>
          {program.nodes.some(item => item.key === newKey.trim()) && <p role="status">This key already exists.</p>}
          <button disabled={disabled || !newKey.trim() || program.nodes.some(item => item.key === newKey.trim())}>Add discovery node</button>
        </form>
      </section>
      <section className="sc-card sc-stack" aria-label="Selected node inspector">
        <h2>Node inspector</h2>
        {!node ? <p>Select a node to edit its draft prompt.</p> : <>
          <Pill>Inspecting {node.key}</Pill>
          <label>Node label<input value={node.label} disabled={disabled} onChange={event => updateNode({ label: event.target.value })} /></label>
          <label>Node type<select value={node.type} disabled={disabled} onChange={event => updateNode({ type: event.target.value as WorkflowNode["type"] })}>
            {nodeTypes.map(type => <option key={type}>{type}</option>)}
          </select></label>
          <label>Current-step prompt<textarea value={node.prompt} disabled={disabled} onChange={event => updateNode({ prompt: event.target.value })} /></label>
          <div className="sc-reading"><MathText text={node.prompt} /></div>
          <div className="sc-config">
            <label>Topic<input value={node.topic || ""} disabled={disabled} onChange={event => updateNode({ topic: event.target.value })} /></label>
            <label>Objective<input value={node.objective || ""} disabled={disabled} onChange={event => updateNode({ objective: event.target.value })} /></label>
          </div>
          <details><summary>Source, assessment and accessibility</summary><div className="sc-stack">
            <label>Reviewed source claim reference<input value={node.source_claim_ref || ""} disabled={disabled} onChange={event => updateNode({ source_claim_ref: event.target.value })} /></label>
            <label>Approved activity reference<input value={node.activity_ref || ""} disabled={disabled} onChange={event => updateNode({ activity_ref: event.target.value })} /></label>
            <label>Accessible alternative<textarea value={node.accessible_alternative || ""} disabled={disabled} onChange={event => updateNode({ accessible_alternative: event.target.value })} /></label>
            <p className="sc-muted">REST must resolve approved immutable references. Answer keys and private rubrics never enter the student payload.</p>
          </div></details>
          <nav className="sc-toolbar" aria-label="Inspector step navigation">
            <button disabled={disabled || program.nodes.findIndex(item => item.key === selected) < 1} onClick={() => {
              const index = program.nodes.findIndex(item => item.key === selected) - 1;
              setSelected(program.nodes[index].key); setPage(Math.floor(index / 25));
            }}>Previous step</button>
            <button disabled={disabled || program.nodes.findIndex(item => item.key === selected) >= program.nodes.length - 1} onClick={() => {
              const index = program.nodes.findIndex(item => item.key === selected) + 1;
              setSelected(program.nodes[index].key); setPage(Math.floor(index / 25));
            }}>Next step</button>
          </nav>
          <RuleEditor key={node.key} sourceKey={node.key} program={program} edit={edit} disabled={disabled} onInspect={setSelected} onPropose={onPropose} />
          {node.key === program.entry || node.key === program.fallback_key ? <p className="sc-muted">Change entry/fallback references before removing this node.</p> :
            deletePending === node.key ? <div className="sc-callout">
              Remove this node and all incident edges from the draft?
              <div className="sc-toolbar"><button disabled={disabled} className="sc-danger" onClick={() => {
                edit({ ...program, nodes: program.nodes.filter(item => item.key !== node.key), edges: program.edges.filter(edge => edge.from_key !== node.key && edge.to_key !== node.key) });
                setSelected(""); setDeletePending(null);
              }}>Confirm removal</button><button onClick={() => setDeletePending(null)}>Cancel</button></div>
            </div> : <button className="sc-danger" disabled={disabled} onClick={() => setDeletePending(node.key)}>Remove node…</button>}
        </>}
      </section>
      </div>
      <Simulator key={preview?.preview_id || "none"} preview={preview} disabled={disabled} onRestart={onSimulate} onRefresh={onRefreshPreview}
        onTransition={onTransition} onRespond={onRespond} onAssist={onAssist} onReveal={onReveal} />
    </div>
  </div>;
}
