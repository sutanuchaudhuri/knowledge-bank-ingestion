import { useState } from "react";
import type { Program } from "./contracts";
import { nodeLabel, ruleText } from "./narrative";
import { Empty, Hero, Icon, MathText, Pager, Pill } from "./ui";

export function RulesView({ program, disabled, onRule, onDescribe }: {
  program: Program | null; disabled: boolean; onRule: (index: number) => void; onDescribe: () => void;
}) {
  const [topic, setTopic] = useState("");
  const [page, setPage] = useState(0);
  if (!program) return <div className="sc-canvas-inner"><Hero kicker="Policy library" title="Rules by topic" />
    <Empty icon="diagram-3">Open a workflow from the sidebar to see its rules.</Empty></div>;
  const topicOf = (key: string) => program.nodes.find(node => node.key === key)?.topic || "";
  const topics = [...new Set(program.nodes.map(node => node.topic).filter((value): value is string => !!value))];
  const rules = program.edges.map((edge, index) => ({ edge, index })).filter(({ edge }) => !topic || topicOf(edge.from_key) === topic);
  return <div className="sc-canvas-inner">
    <Hero kicker="Policy library" title="Rules by topic" description="Readable policies first. Technical conditions appear when a rule is opened."
      actions={<><Pill>Fallback · {nodeLabel(program, program.fallback_key)}</Pill><Pill>Max {program.max_transitions} moves</Pill></>} />
    {topics.length > 0 && <div className="sc-chips" role="group" aria-label="Filter rules by topic">
      {["", ...topics].map(value => <button type="button" key={value || "all"} aria-pressed={topic === value}
        className={`sc-chip${topic === value ? " sc-active" : ""}`} onClick={() => { setTopic(value); setPage(0); }}>{value || "All topics"}</button>)}
    </div>}
    {!rules.length ? <Empty icon="signpost-split">No rules for this topic.</Empty> : rules.slice(page * 25, (page + 1) * 25).map(({ edge, index }) =>
      <button type="button" key={index} className="sc-list-row" disabled={disabled} onClick={() => onRule(index)}>
        <span><strong><MathText text={nodeLabel(program, edge.from_key)} /></strong><span className="sc-sub"><MathText text={ruleText(program, edge)} /></span></span>
        <span className="sc-edit">Edit <Icon name="chevron-right" /></span>
      </button>)}
    <Pager page={page} hasMore={(page + 1) * 25 < rules.length} onChange={setPage} />
    <button type="button" className="sc-light" disabled={disabled} onClick={onDescribe}><Icon name="plus-lg" />Describe a new rule in English</button>
  </div>;
}
