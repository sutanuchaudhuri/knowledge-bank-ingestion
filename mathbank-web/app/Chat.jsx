"use client";

import { useEffect, useRef, useState } from "react";
import { createSession, newSessionId, streamMessage } from "./agentClient.js";
import { MathComposer, SpeakButton } from "mathbank-widgets";
import Link from "next/link";
import MathText from "./_components/MathText.jsx";
import TutorAnswer from "./_components/TutorAnswer.jsx";
import { Avatar, Callout, EmptyState, Icon, Pill, SectionTitle } from "./_components/ui.jsx";

const SUGGESTIONS = [
  ["bullseye", "Explain the power of a point"],
  ["search", "Recent combinatorics questions"],
  ["triangle", "A hard geometry problem to try"],
];

const ACTIVITY_LOOK = {
  complete: { tone: "success", icon: "check-lg" },
  error: { tone: "danger", icon: "x-lg" },
  stopped: { tone: "warning", icon: "pause-fill" },
  running: { tone: "primary", icon: "gear" },
};

export default function Chat() {
  const sessionRef = useRef(null);
  const streamRef = useRef(null);
  const bottomRef = useRef(null);
  const [ready, setReady] = useState(false);
  const [saved, setSaved] = useState(null);
  const [messages, setMessages] = useState([
    { role: "assistant", text: "Hi! Ask me about any competition math topic, or pick a starter below." },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [activity, setActivity] = useState([]);
  const [error, setError] = useState(null);
  const [studentName, setStudentName] = useState("");

  useEffect(() => {
    let cancelled = false;
    if (!sessionRef.current) {
      const id = newSessionId();
      sessionRef.current = { id, request: createSession(id) };
    }
    sessionRef.current.request
      .then((session) => { if (!cancelled) { setReady(true); setSaved(session); } })
      .catch((err) => { if (!cancelled) setError(`Could not reach the agent: ${err.message}`); });
    return () => { cancelled = true; streamRef.current?.abort(); };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/rest/learner/me", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((me) => { if (!cancelled && me?.first_name) setStudentName(`${me.first_name} ${me.last_name || ""}`.trim()); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: sending ? "instant" : "smooth", block: "nearest" });
  }, [messages, sending]);

  async function handleSend(event) {
    event?.preventDefault();
    const text = input.trim();
    if (!text || !ready || streamRef.current) return;
    const controller = new AbortController();
    streamRef.current = controller;
    const answerIndex = messages.length + 1;
    setMessages((m) => [...m, { role: "user", text }, { role: "assistant", text: "" }]);
    setInput("");
    setError(null);
    setActivity([]);
    setSending(true);
    try {
      await streamMessage(sessionRef.current.id, text, (update) => {
        if (update.type === "answer") {
          setMessages((items) => items.map((item, index) => index === answerIndex ? { ...item, text: update.text } : item));
        } else if (update.type === "activity") {
          setActivity((items) => [...items, update]);
        } else if (update.type === "done") {
          setActivity((items) => [...items, { label: "Response complete", status: "complete" }]);
        }
      }, controller.signal);
    } catch (err) {
      if (err.name === "AbortError") {
        setActivity((items) => [...items, { label: "Response stopped", status: "stopped" }]);
      } else {
        setError(err.message);
        setActivity((items) => [...items, { label: "Response failed", status: "error" }]);
      }
    } finally {
      streamRef.current = null;
      setSending(false);
    }
  }

  const greeting = messages.length === 1;
  const status = sending ? { tone: "info", icon: "broadcast", text: "Streaming" }
    : ready ? { tone: "success", icon: "circle-fill", text: "Agent connected" }
      : { tone: "neutral", icon: "hourglass-split", text: "Connecting" };

  return (
    <div className="row g-4">
      <div className="col-12 col-xl-9">
        <section className="card mb-chat" aria-label="Tutor conversation">
          <div className="d-flex justify-content-end gap-2 px-3 pt-2">
            <Link className="btn btn-ghost btn-sm" href="/learn/attempt-media"><Icon name="file-earmark-richtext" />Upload my written attempt</Link>
            <Link className="btn btn-ghost btn-sm" href="/artifacts"><Icon name="collection" />Artifact library</Link>
          </div>
          <div className="mb-chat-scroll" aria-live="polite" aria-busy={sending}>
            {messages.map((message, index) => {
              const mine = message.role === "user";
              const streaming = sending && index === messages.length - 1;
              return (
                <div key={index} className={`mb-msg ${mine ? "mb-msg-user" : "mb-msg-assistant"}`}>
                  {mine ? <Avatar name={studentName || "You"} size={32} /> : <Avatar name="MathBank Tutor" icon="stars" size={32} />}
                  <div className="min-w-0">
                    <div className={`mb-msg-meta ${mine ? "justify-content-end" : ""}`}>
                      <span className="fw-semibold">{mine ? "You" : "MathBank Tutor"}</span>
                      {!mine && message.text && !streaming && <SpeakButton text={message.text} label="Listen to this answer" />}
                    </div>
                    <div className="mb-bubble">
                      {mine ? (
                        /\$|\\\(|\\\[/.test(message.text) ? <MathText>{message.text}</MathText>
                          : <div style={{ whiteSpace: "pre-wrap" }}>{message.text}</div>
                      ) : message.text ? (
                        <TutorAnswer>{message.text}</TutorAnswer>
                      ) : sending ? (
                        <span className="mb-typing" role="status" aria-label="Working on your question"><span /><span /><span /></span>
                      ) : (
                        <span className="text-secondary small">No answer received.</span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
            {greeting && (
              <div className="mb-suggestions ps-5" aria-label="Suggested questions">
                {SUGGESTIONS.map(([icon, text]) => (
                  <button key={text} type="button" className="mb-tab" onClick={() => setInput(text)} disabled={!ready}>
                    <Icon name={icon} />{text}
                  </button>
                ))}
              </div>
            )}
            <div ref={bottomRef} />
          </div>
          <div className="mb-chat-foot">
            {error && <Callout tone="danger" role="alert" className="mb-2">{error}</Callout>}
            <form onSubmit={handleSend}>
              <label htmlFor="chat-input" className="visually-hidden">Your question</label>
              <MathComposer id="chat-input" ariaLabel="Your question" testId="chat-composer" rows={1}
                value={input} onChange={setInput} onSubmit={() => handleSend()} showSubmit={false}
                renderMath={(t) => <MathText>{t}</MathText>}
                placeholder={ready ? "Ask anything about competition math…" : "Connecting to the agent…"}
                disabled={!ready || sending}>
                {sending ? (
                  <button type="button" className="mbw-send is-danger" onClick={() => streamRef.current?.abort()}><Icon name="stop-fill" />Stop</button>
                ) : (
                  <button className="mbw-send" disabled={!ready || !input.trim()}><Icon name="send-fill" />Send</button>
                )}
              </MathComposer>
            </form>
            <div className="d-flex flex-wrap align-items-center gap-2 mt-2 small text-secondary">
              <Pill tone={status.tone} icon={status.icon}>{status.text}</Pill>
              {saved && (
                <span data-testid="chat-saved-state">
                  {saved.linked
                    ? <><Icon name="cloud-check" className="me-1" />Auto-saved to <Link href="/learn/conversations">your conversations</Link></>
                    : <><Icon name="incognito" className="me-1" />Anonymous · <Link href="/login">sign in</Link> to keep history</>}
                </span>
              )}
            </div>
          </div>
        </section>
      </div>
      <aside className="col-12 col-xl-3">
        <section className="card p-3 mb-sticky" aria-label="Agent activity">
          <SectionTitle icon="activity">Agent activity</SectionTitle>
          {activity.length ? (
            <ol className="mb-activity" aria-live="polite">
              {activity.map((item, index) => {
                const look = ACTIVITY_LOOK[item.status] || ACTIVITY_LOOK.running;
                return (
                  <li key={index}>
                    <span className={`mb-activity-dot mb-tone-${look.tone}`}><Icon name={look.icon} /></span>
                    <span className="min-w-0 text-break pt-1">{item.label}</span>
                  </li>
                );
              })}
            </ol>
          ) : (
            <EmptyState icon="cpu">Tool calls appear here while the tutor works.</EmptyState>
          )}
        </section>
      </aside>
    </div>
  );
}
