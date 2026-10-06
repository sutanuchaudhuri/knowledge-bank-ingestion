// Agent conversation transcripts proxy (requirements/22_AGENT_SESSION_TRANSCRIPTS.md). Read-only.
//   /api/rest/learner/conversations           -> GET /v1/learner/agent-sessions            (student cookie)
//   /api/rest/learner/conversations/{id}      -> GET /v1/learner/agent-sessions/{id}/transcript
//   /api/rest/admin/conversations?student=     -> GET /v1/admin/agent-sessions              (admin session)
//   /api/rest/admin/conversations?id={id}      -> GET /v1/admin/agent-sessions/{id}/transcript
import { SESSION_ID_PATTERN } from "./agentIdentity.mjs";

const enc = encodeURIComponent;

export function resolveLearnerConversationRoute(segments = []) {
  if (segments.length === 0) return { path: "/v1/learner/agent-sessions", query: { limit: 50 } };
  if (segments.length === 1 && SESSION_ID_PATTERN.test(segments[0]))
    return { path: `/v1/learner/agent-sessions/${enc(segments[0])}/transcript` };
  return null;
}

export function resolveAdminConversationRoute(params) {
  const id = params.get("id");
  if (id !== null) {
    if (!SESSION_ID_PATTERN.test(id)) return { error: "id is not a valid session id" };
    return { path: `/v1/admin/agent-sessions/${enc(id)}/transcript`, query: {} };
  }
  const student = (params.get("student") || "").trim().slice(0, 200);
  return { path: "/v1/admin/agent-sessions", query: { limit: 100, ...(student ? { student } : {}) } };
}

function fail(err) {
  return Response.json({ error: err.message }, { status: err.status || 502 });
}

export function createLearnerConversationHandlers({ getToken, get }) {
  return {
    async GET(_request, segments) {
      const route = resolveLearnerConversationRoute(segments);
      if (!route) return Response.json({ error: "Unknown conversation endpoint" }, { status: 404 });
      const token = await getToken();
      if (!token) return Response.json({ error: "not logged in" }, { status: 401 });
      try { return Response.json(await get(route.path, token, route.query)); } catch (err) { return fail(err); }
    },
  };
}

export function createAdminConversationHandlers({ hasSession, get }) {
  return {
    async GET(request) {
      if (!await hasSession()) return Response.json({ error: "Admin login required" }, { status: 401 });
      const route = resolveAdminConversationRoute(new URL(request.url).searchParams);
      if (route.error) return Response.json({ error: route.error }, { status: 400 });
      try { return Response.json(await get(route.path, route.query)); } catch (err) { return fail(err); }
    },
  };
}
