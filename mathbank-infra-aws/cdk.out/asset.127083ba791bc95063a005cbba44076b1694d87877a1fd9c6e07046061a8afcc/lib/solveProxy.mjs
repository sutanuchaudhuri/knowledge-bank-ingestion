// Student step-runtime proxy (v2 Phase 7): /api/rest/solve/* -> mathbank-rest /v1 step runtime.
// Allowlisted routes only; the student JWT stays in the httpOnly cookie and is attached server-side.
// Mutations must be same-origin and forward the browser's Idempotency-Key.
// Step ids contain "/" (e.g. PRASOLOV_PGV1/STEP-1.1-A-01), so the browser sends them encoded as
// a single segment and they are re-encoded with encodeURIComponent upstream.

const enc = encodeURIComponent;

export function resolveSolveRoute(method, segments, searchParams = new URLSearchParams()) {
  const [head, ...rest] = segments;
  if (method === "GET") {
    if (head === "attempts" && rest.length === 1) return { path: `/v1/attempts/${enc(rest[0])}/runtime`, auth: true };
    if (head === "attempts" && rest.length === 3 && rest[1] === "hints")
      return { path: `/v1/attempts/${enc(rest[0])}/steps/${enc(rest[2])}/hints`, auth: true };
    if (head === "attempts" && rest.length === 2 && rest[1] === "events")
      return { path: "/v1/students/{student}/events", query: { attempt_id: rest[0], limit: 100 }, auth: true, needsStudent: true };
    if (head === "attempts" && rest.length === 2 && rest[1] === "diagnoses")
      return { path: `/v1/attempts/${enc(rest[0])}/diagnoses`, auth: true };
    if (head === "practice" && rest.length === 1)
      return { path: `/v1/solution-steps/${enc(rest[0])}/practice`, query: { limit: searchParams.get("limit") || 5 }, auth: true };
    if (head === "attempts" && rest.length === 2 && rest[1] === "recovery-plans")
      return { path: `/v1/attempts/${enc(rest[0])}/recovery-plans`, auth: true };
    if (head === "recovery-plans" && rest.length === 1) return { path: `/v1/recovery-plans/${enc(rest[0])}`, auth: true };
    if (head === "recovery-plans" && rest.length === 2 && rest[1] === "next")
      return { path: `/v1/recovery-plans/${enc(rest[0])}/next`, auth: true };
    if (head === "diagrams" && rest.length === 1) return { path: `/v1/problems/by-code/${enc(rest[0])}/diagrams` };
    if (head === "source" && rest.length === 1) return { path: `/v1/problems/by-code/${enc(rest[0])}/source` };
    if (head === "source-pdf" && rest.length === 1) return { path: `/v1/problems/by-code/${enc(rest[0])}/source-pdf`, raw: true };
    if (head === "source-highlight" && rest.length === 1) return { path: `/v1/problems/by-code/${enc(rest[0])}/source-highlight`, raw: true, query: { page: searchParams.get("page") || undefined } };
    if (head === "source-marked-pdf" && rest.length === 1) return { path: `/v1/problems/by-code/${enc(rest[0])}/source-marked-pdf`, raw: true };
    if (head === "images" && rest.length === 1) return { path: `/v1/problem-images/${enc(rest[0])}`, raw: true };
    return null;
  }
  if (method === "POST") {
    if (head === "pedagogy-feedback" && rest.length === 0)
      return { path: "/v1/tutor/feedback", auth: true, body: true };
    if (head === "start" && rest.length === 1)
      return { path: `/v1/students/{student}/problems/${enc(rest[0])}/attempts`, auth: true, needsStudent: true, body: false };
    if (head === "attempts" && rest.length === 3 && ["responses", "hint"].includes(rest[1]))
      return { path: `/v1/attempts/${enc(rest[0])}/steps/${enc(rest[2])}/${rest[1]}`, auth: true, body: true };
    if (head === "attempts" && rest.length === 3 && rest[1] === "diagnose")
      return { path: `/v1/attempts/${enc(rest[0])}/steps/${enc(rest[2])}/diagnose`, auth: true, body: false };
    if (head === "attempts" && rest.length === 2 && rest[1] === "submit")
      return { path: `/v1/attempts/${enc(rest[0])}/submit`, auth: true, body: true };
    if (head === "attempts" && rest.length === 2 && rest[1] === "recovery-plans")
      return { path: `/v1/attempts/${enc(rest[0])}/recovery-plans`, auth: true, body: true };
    if (head === "recovery-plans" && rest.length === 3 && rest[1] === "items")
      return { path: `/v1/recovery-plans/${enc(rest[0])}/items/${enc(rest[2])}/responses`, auth: true, body: true };
    if (head === "recovery-plans" && rest.length === 2 && ["resume", "abort"].includes(rest[1]))
      return { path: `/v1/recovery-plans/${enc(rest[0])}/${rest[1]}`, auth: true, body: true };
    return null;
  }
  return null;
}

function errorResponse(err) {
  let detail = err.message;
  try { detail = JSON.parse(err.message); } catch { /* plain text */ }
  return Response.json({ error: detail }, { status: err.status || 502 });
}

export function createSolveHandlers({ getToken, get, post, raw }) {
  let cachedStudent = null;

  async function studentId(token) {
    if (cachedStudent?.token === token) return cachedStudent.id;
    const me = await get("/v1/learner/me", token);
    cachedStudent = { token, id: me.student_id };
    return me.student_id;
  }

  async function handle(request, segments, method) {
    const route = resolveSolveRoute(method, segments, new URL(request.url).searchParams);
    if (!route) return Response.json({ error: "Unknown solve endpoint" }, { status: 404 });
    if (route.raw) {
      const upstream = await raw(route.path, route.query);
      return new Response(upstream.body, { status: upstream.status, headers: {
        "Content-Type": upstream.headers.get("content-type") || "application/octet-stream",
        "Cache-Control": upstream.ok ? upstream.headers.get("cache-control") || "no-cache" : "no-store" } });
    }
    if (method === "POST" && request.headers.get("origin") !== new URL(request.url).origin) {
      return Response.json({ error: "Same-origin requests are required" }, { status: 403 });
    }
    const token = route.auth ? await getToken() : null;
    if (route.auth && !token) return Response.json({ error: "not logged in" }, { status: 401 });
    try {
      let path = route.path;
      if (route.needsStudent) path = path.replace("{student}", enc(await studentId(token)));
      if (method === "GET") return Response.json(await get(path, token, route.query));
      let payload = {};
      if (route.body) {
        try { payload = await request.json(); }
        catch { return Response.json({ error: "Invalid JSON" }, { status: 400 }); }
        if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
          return Response.json({ error: "Expected a JSON object" }, { status: 400 });
        }
      }
      const key = request.headers.get("idempotency-key");
      return Response.json(await post(path, token, payload, key ? { "Idempotency-Key": key.slice(0, 200) } : {}));
    } catch (err) {
      return errorResponse(err);
    }
  }

  return {
    GET: (request, segments) => handle(request, segments, "GET"),
    POST: (request, segments) => handle(request, segments, "POST"),
  };
}
