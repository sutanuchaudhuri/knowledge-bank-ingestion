import { useState } from "react";
import type { KeyboardEvent } from "react";
import type { Preview, Program } from "./contracts";
import { describeProgram, nodeSubtitle, outgoing, ruleText, typeIcons } from "./narrative";
import { Hero, Icon, MathText, Pager, Pill, Segmented } from "./ui";

export type Representation = "flow" | "text" | "json";

export function Designer({ title, program, representation, setRepresentation, selected, preview, disabled, onStep, onRule, onAddStep }: {
  title: string; program: Program; representation: Representation; setRepresentation: (value: Representation) => void;
  selected: string; preview: Preview | null; disabled: boolean;
  onStep: (key: string) => void; onRule: (index: number) => void; onAddStep: () => void;
}) {
  return <div className="sc-canvas-inner">
    <Hero kicker="Designer" title={<MathText text={title} />}
      description="Choose a step to edit it. Switch views to read the flow as plain language or JSON."
      actions={<button type="button" className="sc-light" disabled={disabled} onClick={onAddStep}><Icon name="plus-lg" />Add step</button>} />
    <Segmented label="Flow representation" value={representation} onChange={setRepresentation} options={[
      { value: "flow", label: "Flow", icon: "diagram-3" },
      { value: "text", label: "Natural language", icon: "text-paragraph" },
      { value: "json", label: "JSON", icon: "braces" },
    ]} />
    {representation === "flow" && <FlowList program={program} selected={selected} preview={preview} disabled={disabled} onStep={onStep} onRule={onRule} />}
    {representation === "text" && <Narrative program={program} onStep={onStep} />}
    {representation === "json" && <JsonView program={program} />}
  </div>;
}

function FlowList({ program, selected, preview, disabled, onStep, onRule }: {
  program: Program; selected: string; preview: Preview | null; disabled: boolean;
  onStep: (key: string) => void; onRule: (index: number) => void;
}) {
  const [page, setPage] = useState(0);
  const nodes = program.nodes.slice(page * 25, (page + 1) * 25);
  const latest = preview?.history.at(-1);
  function move(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const target = event.key === "ArrowDown" ? index + 1 : event.key === "ArrowUp" ? index - 1
      : event.key === "Home" ? 0 : event.key === "End" ? nodes.length - 1 : -1;
    if (target < 0 || target >= nodes.length) return;
    event.preventDefault();
    onStep(nodes[target].key);
    event.currentTarget.closest(".sc-flow")?.querySelectorAll<HTMLButtonElement>(".sc-node")[target]?.focus();
  }
  return <>
    <div className="sc-flow" role="group" aria-label="Workflow steps">
      {nodes.map((node, index) => {
        const rules = outgoing(program, node.key);
        const here = preview?.current_node.key === node.key;
        return <div key={node.key} className="sc-flow-item">
          {index > 0 && <div className="sc-arrow" aria-hidden="true"><Icon name="arrow-down" /></div>}
          <button type="button" className={`sc-node${selected === node.key ? " sc-active" : ""}${here ? " sc-here" : ""}`}
            aria-pressed={selected === node.key} disabled={disabled} onKeyDown={event => move(event, index)} onClick={() => onStep(node.key)}>
            <span className="sc-glyph"><Icon name={typeIcons[node.type] || "circle"} /></span>
            <span className="sc-node-text"><span className="sc-name"><MathText text={node.label} /></span>
              <span className="sc-sub"><MathText text={nodeSubtitle(node)} /></span></span>
            {here && <Pill tone="success">Student here</Pill>}
            <span className="sc-edit">Edit <Icon name="chevron-right" /></span>
          </button>
          {rules.length > 0 && <div className="sc-branch">
            {rules.map(({ edge, index: ruleIndex }) => {
              const hit = latest?.from_key === edge.from_key && latest.to_key === edge.to_key && latest.outcome === edge.outcome;
              return <button type="button" key={ruleIndex} className={hit ? "sc-live" : ""} disabled={disabled} onClick={() => onRule(ruleIndex)}>
                <Icon name={hit ? "check2" : "arrow-return-right"} /><MathText text={ruleText(program, edge)} />
              </button>;
            })}
          </div>}
        </div>;
      })}
    </div>
    <Pager page={page} hasMore={(page + 1) * 25 < program.nodes.length} onChange={setPage} disabled={disabled} />
  </>;
}

function Narrative({ program, onStep }: { program: Program; onStep: (key: string) => void }) {
  const story = describeProgram(program);
  return <article className="sc-narrative" aria-label="Natural-language flow">
    <p className="sc-lead">{story.summary}</p>
    {story.steps.map(step => <section key={step.key}>
      <h2><button type="button" className="sc-link" onClick={() => onStep(step.key)}><MathText text={step.heading} /></button></h2>
      <p className="sc-reading"><MathText text={step.body} /></p>
      <ul>{step.rules.map((rule, index) => <li key={index}><MathText text={rule} /></li>)}</ul>
    </section>)}
  </article>;
}

function JsonView({ program }: { program: Program }) {
  const [copied, setCopied] = useState(false);
  const json = JSON.stringify(program, null, 2);
  return <section className="sc-json" aria-label="JSON flow">
    <div className="sc-row sc-space"><span className="sc-tiny">Typed program · <code>{program.schema_version}</code> · read-only; edit through steps and rules</span>
      <button type="button" className="sc-light" onClick={() => {
        void navigator.clipboard?.writeText(json).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); });
      }}><Icon name={copied ? "check2" : "clipboard"} />{copied ? "Copied" : "Copy JSON"}</button></div>
    <pre tabIndex={0}><code>{json}</code></pre>
  </section>;
}
