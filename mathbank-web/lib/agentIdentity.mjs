// Server-side agent identity (requirements/22_AGENT_SESSION_TRANSCRIPTS.md).
// The ADK user id is never taken from the browser: a logged-in student chats as their student_id,
// everyone else as "anonymous". Student sessions are then linked in mathbank-rest
// (learner.agent_session_link) so the whole conversation can be rebuilt later.

export const ANONYMOUS_USER = "anonymous";
export const SESSION_ID_PATTERN = /^[A-Za-z0-9._:-]{1,200}$/;
const SURFACES = new Set(["HOME_CHAT", "SOLVE_WORKSPACE", "OTHER"]);

export function createAgentIdentity({ getToken, get }) {
  const cache = new Map();

  async function resolve() {
    let token = null;
    try { token = await getToken(); } catch { token = null; }
    if (!token) return { userId: ANONYMOUS_USER, token: null, studentId: null };
    if (cache.has(token)) return { userId: cache.get(token), token, studentId: cache.get(token) };
    try {
      const me = await get("/v1/learner/me", token);
      if (!me?.student_id) throw new Error("no student id");
      if (cache.size > 500) cache.clear();
      cache.set(token, me.student_id);
      return { userId: me.student_id, token, studentId: me.student_id };
    } catch {
      // Expired/invalid cookie: chat still works, but anonymously and unlinked.
      return { userId: ANONYMOUS_USER, token: null, studentId: null };
    }
  }

  return { resolve };
}

export function linkPayload(sessionId, body = {}) {
  const surface = SURFACES.has(body.surface) ? body.surface : "HOME_CHAT";
  const context = {};
  const raw = body.context && typeof body.context === "object" && !Array.isArray(body.context) ? body.context : {};
  for (const key of ["problem_code", "solve_attempt_id", "page"]) {
    if (typeof raw[key] === "string" && raw[key].length <= 200) context[key] = raw[key];
  }
  return { agent_session_id: sessionId, surface, context };
}
