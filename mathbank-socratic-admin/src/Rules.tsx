import { useState } from "react";
import type { ReactNode } from "react";
import type { Program, Strategy } from "./contracts";
import { RuleEditor } from "./RuleEditor";
import { MathText, Pager, Pill } from "./ui";

export function Rules({ program, strategies, domain, edit, disabled, onInspect, coauthor }: {
  program: Program | null; strategies: Strategy[]; domain: string; edit: (program: Program) => void;
  disabled: boolean; onInspect: (key: string) => void; coauthor: ReactNode;
}) {
  const [topic, setTopic] = useState("");
  const [strategyPage, setStrategyPage] = useState(0);
  const [strategyDomain, setStrategyDomain] = useState("");
  const catalog = strategies.filter(item => !strategyDomain || item.domain === strategyDomain);
  const topics = [...new Set(program?.nodes.map(node => node.topic).filter((value): value is string => !!value))];
  return <div className="sc-stack">
    <div className="sc-split">
      <div className="sc-stack">{coauthor || <section className="sc-card"><h2>Create a rule in natural language</h2><p>Open a workflow in Designer first.</p></section>}
        <section className="sc-card sc-stack"><h2>Policy boundaries</h2>
          <p className="sc-muted">Plain-language explanations record instructor intent. Typed guards, priority and REST eligibility select the route.</p>
          {program && <div className="sc-toolbar"><Pill>Fallback: {program.fallback_key}</Pill><Pill>Budget: {program.max_transitions} transitions</Pill></div>}
        </section>
      </div>
      <section className="sc-card sc-stack"><h2>Rules by topic {domain && `· ${domain}`}</h2>
        <label>Filter rules by topic<select value={topic} onChange={event => setTopic(event.target.value)}>
          <option value="">All topics</option>{topics.map(value => <option key={value}>{value}</option>)}
        </select></label>
        {program ? <RuleEditor key={topic} program={program} edit={edit} disabled={disabled} onInspect={onInspect} topic={topic} /> : <p>Open a workflow in Designer to author its rules.</p>}
      </section>
    </div>
    <details className="sc-card"><summary>Strategy registry · {catalog.length} candidates</summary>
      <label>Strategy domain<select value={strategyDomain} onChange={event => { setStrategyDomain(event.target.value); setStrategyPage(0); }}>
        <option value="">All domains</option>{[...new Set(strategies.map(item => item.domain))].sort().map(value => <option key={value}>{value}</option>)}
      </select></label>
      {!catalog.length && <p>No strategies returned for this domain.</p>}
      <div className="sc-strategy-grid">{catalog.slice(strategyPage * 25, (strategyPage + 1) * 25).map(item => <article key={item.code} className="sc-callout">
        <h3><MathText text={item.label} /></h3><Pill>{item.domain}</Pill> <Pill>{item.status}</Pill>
        <p><code>{item.code}</code></p>{item.phases.map((phase, index) => <div key={index}><MathText text={phase} /></div>)}
      </article>)}</div>
      <Pager page={strategyPage} hasMore={(strategyPage + 1) * 25 < catalog.length} onChange={setStrategyPage} />
    </details>
  </div>;
}
