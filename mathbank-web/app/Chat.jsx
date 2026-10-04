"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { createSession, newSessionId, streamMessage } from "./agentClient.js";
import { normalizeMathDelimiters } from "../lib/markdown.js";

const USER_ID = "anonymous";

export default function Chat() {
  const sessionRef = useRef(null);
  const streamRef = useRef(null);
  const bottomRef = useRef(null);
  const [ready, setReady] = useState(false);
  const [messages, setMessages] = useState([
    { role: "assistant", text: "Ask me about any competition math topic, e.g. \"What are the recent questions on combinatorics?\"" },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [activity, setActivity] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    if (!sessionRef.current) {
      const id = newSessionId();
      sessionRef.current = { id, request: createSession(USER_ID, id) };
    }
    sessionRef.current.request
      .then(() => { if (!cancelled) setReady(true); })
      .catch((err) => { if (!cancelled) setError(`Could not reach the agent: ${err.message}`); });
    return () => { cancelled = true; streamRef.current?.abort(); };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: sending ? "instant" : "smooth", block: "nearest" });
  }, [messages, sending]);

  async function handleSend(event) {
    event.preventDefault();
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
      await streamMessage(USER_ID, sessionRef.current.id, text, (update) => {
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

  return (
    <div className="row g-4">
      <div className="col-12 col-xl-9">
        <section className="card border-0 shadow-sm" aria-label="Tutor conversation">
          <div className="card-header bg-white d-flex justify-content-between align-items-center py-3">
            <span className="fw-semibold">Your math workspace</span>
            <span className={`badge ${ready ? "text-bg-success" : "text-bg-secondary"}`}>
              {sending ? "Streaming" : ready ? "Agent connected" : "Connecting"}
            </span>
          </div>
          <div className="card-body overflow-auto" style={{ minHeight: "45vh", maxHeight: "65vh" }} aria-live="polite" aria-busy={sending}>
            {messages.map((message, index) => (
              <div key={index} className={`d-flex mb-3 ${message.role === "user" ? "justify-content-end" : ""}`}>
                <div className={`rounded-4 p-3 ${message.role === "user" ? "bg-primary text-white" : "bg-body-tertiary"}`} style={{ maxWidth: "95%", minWidth: 0 }}>
                  <div className="small fw-bold mb-2">{message.role === "user" ? "You" : "MathBank Tutor"}</div>
                  {message.role === "user" ? (
                    <div style={{ whiteSpace: "pre-wrap" }}>{message.text}</div>
                  ) : message.text ? (
                    <div className="markdown-body">
                      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
                        {normalizeMathDelimiters(message.text)}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <span className="text-secondary small">{sending ? "Working on your question..." : "No answer received."}</span>
                  )}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
          <div className="card-footer bg-white p-3">
            {error && <div role="alert" className="alert alert-danger">{error}</div>}
            <form onSubmit={handleSend} className="d-flex gap-2">
              <label htmlFor="chat-input" className="visually-hidden">Your question</label>
              <input id="chat-input" className="form-control form-control-lg" value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder={ready ? "Ask a question…" : "Connecting to the agent…"} disabled={!ready || sending} />
              {sending ? (
                <button type="button" className="btn btn-outline-danger" onClick={() => streamRef.current?.abort()}>Stop</button>
              ) : (
                <button className="btn btn-primary px-4" disabled={!ready || !input.trim()}>Send</button>
              )}
            </form>
          </div>
        </section>
      </div>
      <aside className="col-12 col-xl-3">
        <section className="card border-0 shadow-sm">
          <div className="card-header bg-white py-3 fw-semibold">Agent activity</div>
          <div className="card-body">
            <p className="small text-secondary">Live tool calls and progress updates. Private model reasoning is not displayed.</p>
            <ol className="list-group list-group-flush" aria-live="polite">
              {activity.map((item, index) => (
                <li key={index} className="list-group-item px-0 d-flex gap-2 align-items-start">
                  <span className={`badge ${item.status === "error" ? "text-bg-danger" : item.status === "complete" ? "text-bg-success" : "text-bg-secondary"}`}>{index + 1}</span>
                  <span className="small">{item.label}</span>
                </li>
              ))}
            </ol>
            {!activity.length && <p className="small text-secondary mb-0">Ask a question to see the agent at work.</p>}
          </div>
        </section>
      </aside>
    </div>
  );
}
