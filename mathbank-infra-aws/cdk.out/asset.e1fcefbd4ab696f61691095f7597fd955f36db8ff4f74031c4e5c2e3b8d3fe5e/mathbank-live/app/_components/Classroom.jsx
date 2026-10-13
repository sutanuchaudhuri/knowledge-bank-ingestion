"use client";

// Student view: stage widgets, the open activity, tutor/instructor messages, and a slim math composer
// (symbols, quick/AI format, voice input) to ask the AI tutor or the instructor.
import { useMemo, useState } from "react";
import { MathComposer, SpeakButton, WidgetHost } from "mathbank-widgets";
import { MESSAGE_TYPES, optionKey, optionLabel, pollSpec } from "../../lib/events.mjs";
import Header from "./Header.jsx";
import { MathText, renderMath } from "./Math.jsx";
import useLive from "./useLive.js";

const uid = () => (globalThis.crypto?.randomUUID?.() || `c-${Date.now()}-${Math.random().toString(16).slice(2)}`);

function Activity({ state, op }) {
  const a = state?.activity;
  const [sent, setSent] = useState(null);
  const [err, setErr] = useState(null);
  if (!a) return null;
  const revealed = a.status === "REVEALED" && state.activity_aggregate;
  async function answer(option) {
    setErr(null);
    const res = await op("respond", { activity_instance_id: a.activity_instance_id, option, client_command_id: uid() });
    if (res.ok) setSent(option); else setErr(res.error);
  }
  return (
    <div className="card shadow-sm mb-3 border-primary" data-testid="live-activity">
      <div className="card-header bg-primary-subtle fw-semibold">Quick check</div>
      <div className="card-body">
        <div className="mb-2"><MathText text={a.prompt} /></div>
        {a.status === "OPEN" && (
          <div className="d-flex flex-wrap gap-2">
            {(a.options || []).map((o) => (
              <button key={optionKey(o)} type="button" onClick={() => answer(optionKey(o))}
                className={`btn ${sent === optionKey(o) ? "btn-primary" : "btn-outline-primary"}`}>
                <MathText text={optionLabel(o)} />
              </button>
            ))}
          </div>
        )}
        {sent && a.status === "OPEN" && <div className="small text-success mt-2" data-testid="answer-sent">Answer sent — you can change it until the poll closes.</div>}
        {a.status === "CLOSED" && <div className="small text-secondary">The poll is closed. Results will appear when revealed.</div>}
        {err && <div className="small text-danger mt-2">{err}</div>}
        {revealed && <div className="mt-3"><WidgetHost spec={pollSpec(a, state.activity_aggregate, true)} renderMath={renderMath} /></div>}
      </div>
    </div>
  );
}

function Message({ e }) {
  const tutor = e.event_type === "tutor.message";
  return (
    <div className={`mb-2 p-2 rounded ${tutor ? "bg-white border" : "bg-warning-subtle"}`} data-testid="live-message">
      <div className="small text-secondary d-flex align-items-center gap-2">
        {tutor ? "AI tutor" : "Instructor"}{e.audience === "STUDENT" ? " · to you" : ""}
        <span className="ms-auto"><SpeakButton text={e.payload?.text || ""} /></span>
      </div>
      <MathText text={e.payload?.text} />
      {e.payload?.widget_suggestion && <div className="mt-2"><WidgetHost spec={e.payload.widget_suggestion} renderMath={renderMath} /></div>}
    </div>
  );
}

export default function Classroom({ sid }) {
  const { status, state, events, error, op } = useLive(sid);
  const [text, setText] = useState("");
  const [mine, setMine] = useState([]);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null);
  const [confused, setConfused] = useState(false);
  const feed = useMemo(() => {
    const msgs = events.filter((e) => MESSAGE_TYPES.has(e.event_type)).map((e) => ({ key: `e${e.sequence}`, at: e.timestamp, e }));
    return [...msgs, ...mine].sort((a, b) => String(a.at).localeCompare(String(b.at)));
  }, [events, mine]);

  async function send(target) {
    const q = text.trim();
    if (!q || busy) return;
    setBusy(true); setNote(null);
    setMine((m) => [...m, { key: uid(), at: new Date().toISOString(), mine: q, target }]);
    setText("");
    const res = target === "tutor"
      ? await op("ask_tutor", { message: q, client_command_id: uid() })
      : await op("command", { command_type: "QUESTION_ASK", payload: { text: q }, client_command_id: uid() });
    if (!res.ok) setNote(res.status === 409 ? "The instructor is leading right now — your question was not sent to the AI tutor. Try “Ask instructor”." : res.error);
    else if (target === "tutor" && res.data && res.data.delivered === false) setNote("The AI tutor is paused for this class.");
    setBusy(false);
  }

  async function toggleConfused() {
    const res = await op("command", { command_type: "MARK_CONFUSED", payload: { confused: !confused }, client_command_id: uid() });
    if (res.ok) setConfused(!confused);
  }

  if (error && !state) {
    return <div className="alert alert-warning">{error} {error.includes("sign in") && <a href="/login">Sign in</a>}</div>;
  }
  return (
    <div className="row g-4">
      <div className="col-12">
        <Header state={state} status={status} extra={
          <button type="button" className={`btn btn-sm ${confused ? "btn-warning" : "btn-outline-warning"}`} onClick={toggleConfused}
            aria-pressed={confused}>{confused ? "😕 Marked confused" : "I'm confused"}</button>} />
      </div>
      <div className="col-12 col-lg-7">
        <Activity key={state?.activity?.activity_instance_id || "none"} state={state} op={op} />
        <div data-testid="live-stage">
          {(state?.widgets || []).length === 0 && <div className="stage-empty p-5 text-center">Waiting for the instructor to put something on the board…</div>}
          {(state?.widgets || []).map((w) => (
            <div key={w.widget_instance_id} className="mb-3"><WidgetHost spec={w.spec} renderMath={renderMath} /></div>
          ))}
        </div>
      </div>
      <div className="col-12 col-lg-5">
        <div className="card shadow-sm">
          <div className="card-header bg-white fw-semibold">Messages</div>
          <div className="card-body live-feed" data-testid="live-feed">
            {feed.length === 0 && <div className="text-secondary small">Messages from the tutor and instructor appear here.</div>}
            {feed.map((m) => m.e ? <Message key={m.key} e={m.e} /> : (
              <div key={m.key} className="mb-2 p-2 rounded bg-primary-subtle text-end">
                <div className="small text-secondary">You → {m.target === "tutor" ? "AI tutor" : "instructor"}</div>
                <MathText text={m.mine} />
              </div>
            ))}
          </div>
          <div className="card-footer bg-white">
            <MathComposer value={text} onChange={setText} renderMath={renderMath} rows={2} showSubmit={false}
              ariaLabel="Your question" testId="live-composer" placeholder="Ask a question — type math like PA*PB = PT^2"
              disabled={status !== "live"} onSubmit={() => send("tutor")} />
            <div className="d-flex gap-2 mt-2">
              <button type="button" className="btn btn-primary btn-sm" disabled={busy || !text.trim() || status !== "live"} onClick={() => send("tutor")}>Ask AI tutor</button>
              <button type="button" className="btn btn-outline-secondary btn-sm" disabled={busy || !text.trim() || status !== "live"} onClick={() => send("instructor")}>Ask instructor</button>
            </div>
            {note && <div className="small text-warning-emphasis mt-2">{note}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
