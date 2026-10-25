import { useState } from "react";
import type { Outcome, Preview, PreviewAnswer } from "./contracts";
import { MathText, Pill } from "./ui";

export function Simulator({ preview, disabled, onRestart, onRefresh, onTransition, onRespond, onAssist, onReveal }: {
  preview: Preview | null; disabled: boolean; onRestart: () => void; onRefresh: () => void;
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
  const activity = preview?.activity;
  const choice = activity && ["SINGLE_CHOICE", "MULTI_SELECT", "ASSERTION_REASON"].includes(activity.kind);
  const active = preview?.status === "ACTIVE";
  const latest = preview?.history.at(-1);
  return <div className="sc-stack">
    <section className="sc-card sc-preview sc-stack" aria-label="Synthetic simulator">
      <div className="sc-toolbar sc-between"><div><h2>Student Simulator</h2><p className="sc-muted">Preview identity · Synthetic session · No mastery write</p></div><Pill tone="success">Student view · Synthetic</Pill></div>
      <div className="sc-toolbar sc-between"><Pill>{preview?.current_node.type || "Preview ready"}</Pill>
        <button disabled={disabled} onClick={onRestart}>{preview ? "Save draft & restart preview" : "Save draft & start preview"}</button></div>
      {!preview ? <p className="sc-callout">Start the saved draft to try its current activity, request hints and see which rule activates.</p> : <>
        <div className="sc-toolbar"><Pill tone={active ? "primary" : "success"}>{preview.status}</Pill><Pill>State {preview.state_version}</Pill></div>
        <h3 className="sc-student-title"><MathText text={preview.current_node.label} /></h3>
        <p className="sc-muted">Current node: {preview.current_node.key} · {preview.current_node.type}</p>
        <div className="sc-callout sc-reading"><MathText text={preview.current_node.prompt} /></div>
        {activity ? <form className="sc-stack" onSubmit={event => {
          event.preventDefault(); onRespond(choice ? { selected_keys: selected } : { text: text.trim() });
        }}>
          {choice ? <fieldset className="sc-answers"><legend>Your answer</legend>
            {activity.options?.map((option, index) => <label key={option.key} className={`sc-answer${selected.includes(option.key) ? " sc-answer-selected" : ""}`}>
              <input type={activity.kind === "MULTI_SELECT" ? "checkbox" : "radio"} name="preview-answer" value={option.key}
                checked={selected.includes(option.key)} disabled={disabled || !active} onChange={() => setSelected(current =>
                  activity.kind === "MULTI_SELECT" ? current.includes(option.key) ? current.filter(key => key !== option.key) : [...current, option.key] : [option.key])} />
              <span>{String.fromCharCode(65 + index)}.</span><MathText text={option.text} />
            </label>)}
          </fieldset> : <label>Your thinking<textarea value={text} disabled={disabled || !active} onChange={event => setText(event.target.value)}
            maxLength={8000} placeholder="Describe an observation or justification…" /></label>}
          <div className="sc-toolbar">
            <button className="sc-primary" disabled={disabled || !active || (choice ? !selected.length : !text.trim())}>
              {choice ? "Submit answer" : "Submit thinking"}
            </button>
            <button type="button" disabled={disabled || !active} onClick={() => { setShowHint(true); onAssist(); }}>Request hint</button>
            {preview.help && <button type="button" onClick={() => setShowHint(value => !value)}>{showHint ? "Hide hint" : "Show hint"}</button>}
          </div>
        </form> : <p className="sc-muted">No response activity is bound to this node. Use the explicit routing test below; no grade is inferred.</p>}
        {showHint && preview.help && <div className="sc-callout" aria-label="Current hint"><Pill>Hint H{preview.help.level} · Assisted</Pill><MathText text={preview.help.text} /></div>}
        {preview.feedback && <div className="sc-feedback" role="status"><MathText text={preview.feedback} /></div>}
        {activity && active && <details><summary>Explicit reveal · assisted path</summary>
          <p className="sc-muted">Reveal only the authorized current explanation. This is not independent success.</p>
          {!confirmReveal ? <button disabled={disabled} onClick={() => setConfirmReveal(true)}>Reveal current explanation…</button> :
            <div className="sc-toolbar"><button disabled={disabled} onClick={() => { setConfirmReveal(false); onReveal(); }}>Confirm assisted reveal</button><button onClick={() => setConfirmReveal(false)}>Cancel</button></div>}
        </details>}
        <details className="sc-routing-test"><summary>Test routing with a simulated outcome</summary>
          <p className="sc-muted">Staff test controls, not student grading. REST chooses the eligible edge and owns the state.</p>
          <div className="sc-toolbar" aria-label="Simulated outcomes">{(["ALWAYS", "SUCCESS", "RETRY", "UNCERTAIN"] as const).map(outcome =>
            <button key={outcome} disabled={disabled || !active} onClick={() => onTransition(outcome)}>Simulate {outcome}</button>)}</div>
        </details>
        <section className="sc-stack" aria-label="Student journey"><h3>Student journey</h3>
          {!preview.history.length ? <p className="sc-muted">Submit an answer to see which instructor rule activates.</p> :
            <ol className="sc-trace">{preview.history.map((item, index) => <li className="sc-path" key={index}>
              <strong>{item.from_key || item.node_key}</strong> {item.outcome && <>— {item.outcome}</>} {item.to_key && <>→ {item.to_key}</>}
              <div><Pill>{item.decision_source}</Pill> {item.rule_id && <code>{item.rule_id}</code>}</div>
              <MathText text={item.reason} />
            </li>)}</ol>}
        </section>
        <button disabled={disabled} onClick={onRefresh}>Reload preview state</button>
      </>}
    </section>
    <section className="sc-card sc-stack" aria-label="Latest routing decision"><h2>Latest routing decision</h2>
      {latest ? <div className="sc-debug"><dl className="sc-reference">
        <dt>From</dt><dd>{latest.from_key || latest.node_key}</dd><dt>Outcome</dt><dd>{latest.outcome || "Recorded by server"}</dd>
        <dt>To</dt><dd>{latest.to_key || preview?.current_node.key}</dd><dt>Decision</dt><dd>{latest.decision_source}</dd>
        <dt>Reason</dt><dd><MathText text={latest.reason} /></dd>
      </dl></div> : <p className="sc-debug">No submission yet. The matching edge will highlight after the server returns a routing decision.</p>}
    </section>
  </div>;
}
