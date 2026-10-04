// Client for THIS app's own API routes (app/api/agent/*), which proxy to
// mathbank-agent server-side — the browser never calls :8001 directly.
import { readSse } from "../lib/agentStream.mjs";

export function newSessionId() {
  return `web-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export async function createSession(userId, sessionId) {
  const res = await fetch("/api/agent/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ userId, sessionId }),
  });
  if (!res.ok) throw new Error(`createSession failed: ${res.status}`);
  return res.json();
}

/** Sends one user message, returns the agent's final reply text. */
export async function sendMessage(userId, sessionId, text) {
  const res = await fetch("/api/agent/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ userId, sessionId, text }),
  });
  if (!res.ok) throw new Error(`run failed: ${res.status}`);
  const { reply } = await res.json();
  return reply;
}

export async function streamMessage(userId, sessionId, text, onEvent, signal) {
  const res = await fetch("/api/agent/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ userId, sessionId, text, stream: true }),
    signal,
  });
  if (!res.ok) {
    const body = await res.json();
    throw new Error(body.error || `Agent request failed: ${res.status}`);
  }
  if (!res.body) throw new Error("Agent returned no stream");
  let done = false;
  for await (const event of readSse(res.body)) {
    if (event.type === "error") throw new Error(event.message);
    if (event.type === "done") done = true;
    onEvent(event);
  }
  if (!done) throw new Error("Agent stream ended unexpectedly. Please try again.");
}
