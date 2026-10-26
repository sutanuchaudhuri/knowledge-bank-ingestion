import { useState } from "react";
import type { Outcome, Preview, PreviewAnswer } from "./contracts";
import { outcomeLabels } from "./narrative";
import { Empty, Hero, Icon, MathText, Pill } from "./ui";

export function Simulator({ title, preview, canStart, disabled, onRestart, onRefresh, onTransition, onRespond, onAssist, onReveal }: {
  title: string; preview: Preview | null; canStart: boolean; disabled: boolean; onRestart: () => void; onRefresh: () => void;
  onTransition: (outcome: Outcome) => void; onRespond: (answer: PreviewAnswer) => void;
  onAssist: () => void; onReveal: () => void;
}) {
  const [text, setText] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [showHint, setShowHint] = useState(true);
  const [confirmReveal, setConfirmReveal] = useState(false);
  const activityKey = `${preview?.current_node.key}:${preview?.activity?.activity_id}:${preview?.activity?.revision}`;
  const [currentActivity, setCurrentActivity] = useState(activityKey);
  if (currentActivity !== activityKey) {
    setCurrentActivity(activityKey); setText(""); setSelected([]); setConfirmReveal(false);
  }
  const restart = <button type="button" className="sc-light" disabled={disabled || !canStart} onClick={onRestart}>
    <Icon name="arrow-counterclockwise" />{preview ? "Save & restart" : "Save & start preview"}</button>;
  if (!preview) return <div className="sc-canvas-inner sc-narrow">
    <Hero kicker="Student simulation" title="Try the journey as a student" description="A synthetic student. Real progress is never changed." actions={restart} />
    <Empty icon="person-video3">{canStart ? "Start a preview to answer each step as a student would." : "Open a workflow from the sidebar first."}</Empty>
  </div>;
  const activity = preview.activity;
  const choice = activity && ["SINGLE_CHOICE", "MULTI_SELECT", "ASSERTION_REASON"].includes(activity.kind);
  const active = preview.status === "ACTIVE";
  const latest = preview.history.at(-1);
  return <div className="sc-canvas-inner sc-narrow">
    <Hero kicker="Student simulation" title={<MathText text={preview.current_node.label} />}
      description={<><MathText text={title} /> · Synthetic student · No real progress changes</>} actions={restart} />
    <section className="sc-student-box" aria-label="Synthetic simulator">
      <div className="sc-row">
        <Pill tone={active ? "primary" : "success"}>{active ? preview.current_node.type.toLowerCase() : "Complete"}</Pill>
        {preview.max_transitions !== undefined && <span className="sc-tiny">Move {preview.transitions_used ?? 0} of {preview.max_transitions}</span>}
      </div>
      <div className="sc-question"><MathText text={preview.current_node.prompt} /></div>
      {activity?.prompt && <div className="sc-reading" aria-label="Activity question"><MathText text={activity.prompt} /></div>}
      {activity && active ? <form className="sc-form" onSubmit={event => {
        event.preventDefault(); onRespond(choice ? { selected_keys: selected } : { text: text.trim() });
      }}>
        {choice ? <fieldset className="sc-answers"><legend className="sc-visually-hidden">Your answer</legend>
          {activity.options?.map((option, index) => <label key={option.key} className={`sc-option${selected.includes(option.key) ? " sc-active" : ""}`}>
            <input type={activity.kind === "MULTI_SELECT" ? "checkbox" : "radio"} name="preview-answer" value={option.key}
              checked={selected.includes(option.key)} disabled={disabled} onChange={() => setSelected(current =>
                activity.kind === "MULTI_SELECT" ? current.includes(option.key) ? current.filter(key => key !== option.key) : [...current, option.key] : [option.key])} />
            <span className="sc-option-key">{String.fromCharCode(65 + index)}</span><MathText text={option.text} />
          </label>)}
        </fieldset> : <label className="sc-visually-labelled">Your thinking<textarea value={text} disabled={disabled} onChange={event => setText(event.target.value)}
          maxLength={8000} inputMode={activity.kind === "NUMERIC_EXACT" ? "decimal" : undefined}
          placeholder={activity.kind === "NUMERIC_EXACT" ? "Enter a number, e.g. 21, -0.5 or 3/4" : "Think through the question here…"} /></label>}
        <div className="sc-row">
          <button className="sc-primary" disabled={disabled || (choice ? !selected.length : !text.trim())}>{choice ? "Submit answer" : "Submit thinking"}</button>
          <button type="button" className="sc-light" disabled={disabled} onClick={() => { setShowHint(true); onAssist(); }}><Icon name="lightbulb" />Hint</button>
          {preview.help && <button type="button" className="sc-link" onClick={() => setShowHint(value => !value)}>{showHint ? "Hide hint" : "Show hint"}</button>}
        </div>
      </form> : active && <p className="sc-tiny">No question on this step. Use “Test routing” below to continue.</p>}
      {showHint && preview.help && <div className="sc-hint" aria-label="Current hint"><Icon name="lightbulb" /> <strong>Hint {preview.help.level}</strong> · <MathText text={preview.help.text} /></div>}
      {preview.feedback && <div className="sc-result" role="status"><MathText text={preview.feedback} /></div>}
      {activity && active && <div className="sc-reveal">{!confirmReveal
        ? <button type="button" className="sc-link" disabled={disabled} onClick={() => setConfirmReveal(true)}>Reveal explanation…</button>
        : <div className="sc-row"><span className="sc-tiny">Counts as assisted, not independent success.</span>
          <button type="button" className="sc-light" disabled={disabled} onClick={() => { setConfirmReveal(false); onReveal(); }}>Confirm reveal</button>
          <button type="button" className="sc-link" onClick={() => setConfirmReveal(false)}>Cancel</button></div>}</div>}
    </section>
    {latest && <section className="sc-decision" aria-label="Latest routing decision">
      <Icon name="signpost-split" /> <span><strong>{latest.from_key || latest.node_key}</strong>{latest.outcome && <> · {outcomeLabels[latest.outcome]}</>} → <strong>{latest.to_key || preview.current_node.key}</strong>
        <span className="sc-tiny"> · {latest.decision_source}{latest.assisted ? " · assisted" : ""}</span>
        <span className="sc-sub"><MathText text={latest.reason} /></span></span>
    </section>}
    <details className="sc-more"><summary>Test routing</summary><div className="sc-form">
      <p className="sc-tiny">Staff controls, not grading. The server picks the matching rule.</p>
      <div className="sc-row sc-wrap" aria-label="Simulated outcomes">{(["ALWAYS", "SUCCESS", "RETRY", "UNCERTAIN"] as const).map(outcome =>
        <button type="button" key={outcome} className="sc-light" disabled={disabled || !active} onClick={() => onTransition(outcome)}>Simulate {outcome}</button>)}</div>
      <button type="button" className="sc-link" disabled={disabled} onClick={onRefresh}>Reload preview state</button>
    </div></details>
    <details className="sc-more"><summary>Student journey · {preview.history.length}</summary>
      {!preview.history.length ? <p className="sc-tiny">No moves yet.</p> : <ol className="sc-trace" aria-label="Student journey">{preview.history.map((item, index) => <li key={index}>
        <strong>{item.from_key || item.node_key}</strong>{item.outcome && <> · {item.outcome}</>}{item.to_key && <> → {item.to_key}</>}
        {item.assisted && <Pill tone="warning">Assisted</Pill>} <span className="sc-tiny">{item.decision_source}{item.rule_id ? ` · ${item.rule_id}` : ""}</span>
        <div className="sc-sub"><MathText text={item.reason} /></div>
      </li>)}</ol>}
    </details>
  </div>;
}
