"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { createSession, newSessionId, sendMessage } from "./agentClient.js";
import { normalizeMathDelimiters } from "../lib/markdown.js";

const USER_ID = "anonymous"; // replaced by a real student id once profiles exist

export default function Page() {
  const [sessionId] = useState(newSessionId);
  const [ready, setReady] = useState(false);
  const [messages, setMessages] = useState([
    { role: "assistant", text: "Ask me about any competition math topic, e.g. \"What are the recent questions on combinatorics?\"" },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    createSession(USER_ID, sessionId)
      .then(() => setReady(true))
      .catch((err) => setMessages((m) => [...m, { role: "assistant", text: `Could not reach the agent: ${err.message}` }]));
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    const text = input.trim();
    if (!text || !ready || sending) return;
    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setSending(true);
    try {
      const reply = await sendMessage(USER_ID, sessionId, text);
      setMessages((m) => [...m, { role: "assistant", text: reply }]);
    } catch (err) {
      setMessages((m) => [...m, { role: "assistant", text: `Error: ${err.message}` }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: 16, fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ fontSize: 20 }}>MathBank Tutor</h1>
      <p style={{ color: "#666", fontSize: 13 }}>
        Anonymous session · hybrid RAG over mathbank-rest + Postgres ·{" "}
        <a href="/db" style={{ color: "#2563eb" }}>browse the corpus</a>
        {" · "}
        <a href="/graph" style={{ color: "#2563eb" }}>view the graph</a>
      </p>

      <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12, minHeight: 360, marginBottom: 12 }}>
        {messages.map((m, i) => (
          <div key={i} style={{ margin: "8px 0", textAlign: m.role === "user" ? "right" : "left" }}>
            <div
              style={{
                display: "inline-block",
                padding: "8px 12px",
                borderRadius: 10,
                background: m.role === "user" ? "#2563eb" : "#f1f5f9",
                color: m.role === "user" ? "white" : "#111",
                maxWidth: "85%",
                textAlign: "left",
              }}
            >
              {m.role === "user" ? (
                <span style={{ whiteSpace: "pre-wrap" }}>{m.text}</span>
              ) : (
                <div className="markdown-body">
                  <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
                    {normalizeMathDelimiters(m.text)}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder={ready ? "Ask a question…" : "Connecting to the agent…"}
          disabled={!ready || sending}
          style={{ flex: 1, padding: 10, borderRadius: 8, border: "1px solid #ccc" }}
        />
        <button onClick={handleSend} disabled={!ready || sending} style={{ padding: "10px 16px", borderRadius: 8 }}>
          {sending ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
}
