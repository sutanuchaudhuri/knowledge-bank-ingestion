// Server-side proxy to mathbank-agent's session-creation endpoint.
// Runs on the Next.js server, so the browser never talks to :8001 directly
// (no CORS exposure needed on the agent side).
// The ADK user id is derived here (student_id from the httpOnly cookie, else "anonymous"); any
// client-supplied userId is ignored. Student sessions are linked in mathbank-rest so the
// conversation can be rebuilt later (requirements/22_AGENT_SESSION_TRANSCRIPTS.md).
import { restAuthGet, restAuthPost } from "../../../../lib/restClient.js";
import { getStudentToken } from "../../../../lib/session.js";
import { createAgentIdentity, linkPayload, SESSION_ID_PATTERN } from "../../../../lib/agentIdentity.mjs";

const AGENT_BASE_URL = process.env.MATHBANK_AGENT_BASE_URL || "http://127.0.0.1:8001";
const APP_NAME = "mathbank_tutor";
const identity = createAgentIdentity({ getToken: getStudentToken, get: restAuthGet });

export async function POST(request) {
  if (request.headers.get("origin") && request.headers.get("origin") !== new URL(request.url).origin) {
    return Response.json({ error: "Same-origin requests are required" }, { status: 403 });
  }
  let body;
  try { body = await request.json(); } catch { return Response.json({ error: "Invalid JSON" }, { status: 400 }); }
  const sessionId = body?.sessionId;
  if (typeof sessionId !== "string" || !SESSION_ID_PATTERN.test(sessionId)) {
    return Response.json({ error: "sessionId is required" }, { status: 400 });
  }
  const { userId, token, studentId } = await identity.resolve();

  let res;
  try {
    res = await fetch(
      `${AGENT_BASE_URL}/apps/${APP_NAME}/users/${encodeURIComponent(userId)}/sessions/${encodeURIComponent(sessionId)}`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }
    );
  } catch (err) {
    return Response.json({ error: `Could not reach agent: ${err.message}` }, { status: 502 });
  }

  // 409 = session already exists (e.g. React StrictMode's double-invoked dev
  // effect, or a page reload reusing a persisted sessionId) — idempotent, not an error.
  let session;
  if (res.status === 409) session = { id: sessionId, appName: APP_NAME, alreadyExists: true };
  else if (!res.ok) return Response.json({ error: `agent session create failed: ${res.status}` }, { status: res.status });
  else session = await res.json();

  let linked = false;
  if (studentId) {
    try {
      await restAuthPost("/v1/learner/agent-sessions", token, linkPayload(sessionId, body));
      linked = true;
    } catch {
      linked = false; // the chat still works; the conversation is just not listed until relinked
    }
  }
  return Response.json({ id: session.id || sessionId, appName: APP_NAME, alreadyExists: !!session.alreadyExists,
    signedIn: !!studentId, linked });
}
