// Server-side proxy to mathbank-agent's session-creation endpoint.
// Runs on the Next.js server, so the browser never talks to :8001 directly
// (no CORS exposure needed on the agent side).
const AGENT_BASE_URL = process.env.MATHBANK_AGENT_BASE_URL || "http://127.0.0.1:8001";
const APP_NAME = "mathbank_tutor";

export async function POST(request) {
  const { userId, sessionId } = await request.json();

  const res = await fetch(
    `${AGENT_BASE_URL}/apps/${APP_NAME}/users/${encodeURIComponent(userId)}/sessions/${encodeURIComponent(sessionId)}`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }
  );

  // 409 = session already exists (e.g. React StrictMode's double-invoked dev
  // effect, or a page reload reusing a persisted sessionId) — idempotent, not an error.
  if (res.status === 409) {
    return Response.json({ id: sessionId, appName: APP_NAME, userId, alreadyExists: true });
  }
  if (!res.ok) {
    return Response.json({ error: `agent session create failed: ${res.status}` }, { status: res.status });
  }
  return Response.json(await res.json());
}
