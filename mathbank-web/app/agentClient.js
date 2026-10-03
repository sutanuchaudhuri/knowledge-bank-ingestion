// Client for THIS app's own API routes (app/api/agent/*), which proxy to
// mathbank-agent server-side — the browser never calls :8001 directly.

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
