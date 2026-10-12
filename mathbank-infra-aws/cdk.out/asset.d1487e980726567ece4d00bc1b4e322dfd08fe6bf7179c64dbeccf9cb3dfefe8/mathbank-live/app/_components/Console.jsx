"use client";

// Instructor console: pacing (start/back/next/complete, pause), board widgets by intent, live polls with
// reveal, messages, takeover of the AI tutor, participants with confusion flags, and recommendations.
import { useState } from "react";
import { MathComposer, WidgetHost } from "mathbank-widgets";
import { optionKey, optionLabel, pollSpec } from "../../lib/events.mjs";
import Header from "./Header.jsx";
import { MathText, renderMath } from "./Math.jsx";
import useLive from "./useLive.js";

const uid = () => (globalThis.crypto?.randomUUID?.() || `c-${Date.now()}-${Math.random().toString(16).slice(2)}`);
const INTENTS = ["power of a point", "intersecting chords", "triangle angle sum", "formula: PA·PB = PT²"];
const LETTERS = ["A", "B", "C", "D", "E", "F"];

function PollCreator({ op, onError }) {
  const [prompt, setPrompt] = useState("If $PA = 4$ and $PB = 9$, what is the tangent length $PT$?");
  const [options, setOptions] = useState("6\n13\n36\n5");
  const [correct, setCorrect] = useState("A");
  async function open(e) {
    e.preventDefault();
    const list = options.split("\n").map((s) => s.trim()).filter(Boolean).slice(0, 6)
      .map((label, i) => ({ id: LETTERS[i], label }));
    const res = await op("open_activity", { definition: { activity_type: "LIVE_POLL", prompt, options: list,
      correctness_policy: { correct_option: correct } }, seconds: 120, client_command_id: uid() });
    if (!res.ok) onError(res.error);
  }
  return (
    <form onSubmit={open} data-testid="poll-creator">
      <label className="form-label small" htmlFor="poll-prompt">Question</label>
      <input id="poll-prompt" className="form-control form-control-sm mb-2" value={prompt} onChange={(e) => setPrompt(e.target.value)} />
      <label className="form-label small" htmlFor="poll-options">Options (one per line → A, B, C…)</label>
      <textarea id="poll-options" className="form-control form-control-sm mb-2" rows={3} value={options} onChange={(e) => setOptions(e.target.value)} />
      <div className="d-flex gap-2 align-items-center">
        <label className="small" htmlFor="poll-correct">Correct</label>
        <select id="poll-correct" className="form-select form-select-sm" style={{ width: 80 }} value={correct} onChange={(e) => setCorrect(e.target.value)}>
          {LETTERS.slice(0, Math.max(1, options.split("\n").filter((s) => s.trim()).length)).map((l) => <option key={l}>{l}</option>)}
        </select>
        <button className="btn btn-sm btn-primary ms-auto">Open poll</button>
      </div>
    </form>
  );
}

export default function Console({ sid }) {
  const { status, state, events, error, op, refresh } = useLive(sid);
  const [err, setErr] = useState(null);
  const [msg, setMsg] = useState("");
  const [intent, setIntent] = useState("");
  const run = async (name, args = {}) => {
    setErr(null);
    const res = await op(name, { client_command_id: uid(), ...args });
    if (!res.ok) setErr(res.error); else refresh();
    return res;
  };
  const versioned = (to) => run("transition", { to, expected_session_version: state?.state_version });

  if (error && !state) return <div className="alert alert-warning">{error}</div>;
  const a = state?.activity;
  const agg = state?.activity_aggregate;
  const takeover = state?.control_mode === "INSTRUCTOR_ACTIVE";
  const statusText = state?.status;

  return (
    <div className="row g-4">
      <div className="col-12">
        <Header state={state} status={status} extra={state && (
          <span className="small">Join code <code className="join-code fs-5" data-testid="join-code">{state.join_code}</code></span>)} />
        {err && <div className="alert alert-danger py-2 small" role="alert">{err}</div>}
      </div>

      <div className="col-12 col-xl-4">
        <div className="card shadow-sm mb-3">
          <div className="card-header bg-white fw-semibold">Pacing</div>
          <div className="card-body d-flex flex-wrap gap-2">
            {(statusText === "CREATED" || statusText === "SCHEDULED") && <button className="btn btn-success btn-sm" onClick={() => versioned("START")}>Start</button>}
            <button className="btn btn-outline-secondary btn-sm" onClick={() => versioned("BACK")}>◀ Back</button>
            <button className="btn btn-outline-primary btn-sm" onClick={() => versioned("NEXT")}>Next ▶</button>
            {statusText === "PAUSED"
              ? <button className="btn btn-outline-success btn-sm" onClick={() => run("resume", { expected_session_version: state?.state_version })}>Resume</button>
              : <button className="btn btn-outline-warning btn-sm" onClick={() => run("pause", { expected_session_version: state?.state_version })}>Pause</button>}
            <button className="btn btn-outline-danger btn-sm ms-auto" onClick={() => versioned("COMPLETE")}>Complete</button>
          </div>
          <ol className="list-group list-group-flush list-group-numbered small">
            {(state?.topics || []).map((t, i) => (
              <li key={t.topic_id || i} className={`list-group-item ${i === state.current_topic_index ? "active" : ""}`}>{t.title}</li>
            ))}
          </ol>
        </div>

        <div className="card shadow-sm mb-3">
          <div className="card-header bg-white fw-semibold d-flex">AI tutor
            <span className={`badge ms-auto ${takeover ? "text-bg-warning" : "text-bg-success"}`}>{takeover ? "Instructor leading" : "AI may respond"}</span>
          </div>
          <div className="card-body d-flex gap-2">
            {takeover
              ? <button className="btn btn-sm btn-outline-success" onClick={() => run("override", { action: "RELEASE", scope: "SESSION" })}>Release to AI</button>
              : <button className="btn btn-sm btn-outline-warning" onClick={() => run("override", { action: "TAKEOVER", scope: "SESSION" })}>Take over</button>}
          </div>
        </div>

        <div className="card shadow-sm">
          <div className="card-header bg-white fw-semibold">Participants ({(state?.participants || []).length})</div>
          <ul className="list-group list-group-flush small" data-testid="participants">
            {(state?.participants || []).map((p) => (
              <li key={p.participant_id} className="list-group-item d-flex">{p.display_name}{p.confused && <span className="ms-auto">😕 confused</span>}</li>
            ))}
          </ul>
        </div>
      </div>

      <div className="col-12 col-xl-4">
        <div className="card shadow-sm mb-3">
          <div className="card-header bg-white fw-semibold">Board</div>
          <div className="card-body">
            <div className="d-flex flex-wrap gap-1 mb-2">
              {INTENTS.map((i) => <button key={i} type="button" className="btn btn-sm btn-outline-secondary" onClick={() => run("show_widget", { intent: i })}>{i}</button>)}
            </div>
            <form className="input-group input-group-sm mb-3" onSubmit={(e) => { e.preventDefault(); if (intent.trim()) run("show_widget", { intent }).then(() => setIntent("")); }}>
              <input className="form-control" placeholder="Describe a widget…" value={intent} onChange={(e) => setIntent(e.target.value)} aria-label="Widget intent" />
              <button className="btn btn-outline-primary">Show</button>
            </form>
            {(state?.widgets || []).map((w) => (
              <div key={w.widget_instance_id} className="mb-3 position-relative">
                <button className="btn btn-sm btn-light border position-absolute top-0 end-0 m-1" style={{ zIndex: 2 }}
                  onClick={() => run("hide_widget", { widget_instance_id: w.widget_instance_id })} aria-label="Hide widget">✕</button>
                <WidgetHost spec={w.spec} renderMath={renderMath} />
              </div>
            ))}
          </div>
        </div>

        <div className="card shadow-sm">
          <div className="card-header bg-white fw-semibold">Poll</div>
          <div className="card-body">
            {!a || a.status === "REVEALED" ? <PollCreator op={op} onError={setErr} /> : null}
            {a && (
              <div className="mt-3" data-testid="poll-status">
                <div className="small mb-1"><MathText text={a.prompt} /> <span className="badge text-bg-light border">{a.status}</span></div>
                <div className="small text-secondary mb-2">{(a.options || []).map((o) => `${optionKey(o)}: ${optionLabel(o)}`).join(" · ")}</div>
                {agg && <WidgetHost spec={pollSpec(a, agg, a.status === "REVEALED")} renderMath={renderMath} />}
                <div className="d-flex gap-2 mt-2">
                  {a.status === "OPEN" && <button className="btn btn-sm btn-outline-secondary" onClick={() => run("close_activity", { activity_instance_id: a.activity_instance_id })}>Close</button>}
                  {a.status !== "REVEALED" && <button className="btn btn-sm btn-outline-primary" onClick={() => run("reveal_activity", { activity_instance_id: a.activity_instance_id })}>Reveal</button>}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="col-12 col-xl-4">
        <div className="card shadow-sm mb-3">
          <div className="card-header bg-white fw-semibold">Message the class</div>
          <div className="card-body">
            <MathComposer value={msg} onChange={setMsg} renderMath={renderMath} rows={2} submitLabel="Send to class" testId="instructor-composer"
              ariaLabel="Message to class" placeholder="e.g. Remember: PA·PB = PT^2"
              onSubmit={async () => { if (msg.trim()) { const r = await run("command", { command_type: "INSTRUCTOR_MESSAGE", payload: { text: msg.trim() } }); if (r.ok) setMsg(""); } }} />
          </div>
        </div>

        {(state?.recommendations || []).filter((r) => r.status === "PROPOSED").length > 0 && (
          <div className="card shadow-sm mb-3 border-info">
            <div className="card-header bg-info-subtle fw-semibold">Recommendations</div>
            <ul className="list-group list-group-flush small">
              {state.recommendations.filter((r) => r.status === "PROPOSED").map((r) => (
                <li key={r.recommendation_id} className="list-group-item">
                  <div><strong>{r.action?.type || r.action?.action || "Suggestion"}</strong> <span className="text-secondary">({r.source})</span></div>
                  {r.rationale && <div className="text-secondary">{r.rationale}</div>}
                  <div className="d-flex gap-2 mt-1">
                    <button className="btn btn-sm btn-outline-success" onClick={() => run("decide", { recommendation_id: r.recommendation_id, decision: "ACCEPT", expected_session_version: state?.state_version })}>Accept</button>
                    <button className="btn btn-sm btn-outline-secondary" onClick={() => run("decide", { recommendation_id: r.recommendation_id, decision: "REJECT" })}>Dismiss</button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="card shadow-sm">
          <div className="card-header bg-white fw-semibold">Live events</div>
          <ul className="list-group list-group-flush small live-feed" data-testid="event-log">
            {[...events].reverse().slice(0, 80).map((e) => (
              <li key={e.sequence} className="list-group-item py-1">
                <span className="text-secondary me-2">#{e.sequence}</span><code>{e.event_type}</code>
                {e.payload?.text && <div><MathText text={e.payload.text} /></div>}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
