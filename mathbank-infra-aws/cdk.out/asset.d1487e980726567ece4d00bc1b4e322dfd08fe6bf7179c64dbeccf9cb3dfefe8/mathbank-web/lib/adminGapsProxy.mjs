// Admin knowledge-gap & recovery-plan proxy (v2 Phases 9-10): read-only, admin session required.
// /api/rest/admin/knowledge-gaps?view=gaps|plans|plan -> mathbank-rest internal admin endpoints.

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const GAP_STATUSES = ["UNRESOLVED", "CONFIRMED", "REJECTED", "RESOLVED"];
const PLAN_STATUSES = ["ACTIVE", "SUSPENDED", "COMPLETED", "EXHAUSTED", "ABORTED", "SUPERSEDED"];

function limitOf(params) {
  const n = Number.parseInt(params.get("limit") || "100", 10);
  return Number.isFinite(n) ? Math.min(Math.max(n, 1), 500) : 100;
}

// Returns { path, query } or { error } for an allowlisted read.
export function resolveAdminGapRoute(params) {
  const view = params.get("view") || "gaps";
  const status = params.get("status") || null;
  if (view === "gaps") {
    if (status && !GAP_STATUSES.includes(status)) return { error: "Unknown gap status" };
    const student = (params.get("student") || "").trim().slice(0, 200);
    return { path: "/v1/admin/knowledge-gaps",
      query: { limit: limitOf(params), ...(status ? { status } : {}), ...(student ? { student } : {}) } };
  }
  if (view === "plans") {
    if (status && !PLAN_STATUSES.includes(status)) return { error: "Unknown plan status" };
    const studentId = params.get("student_id");
    if (studentId && !UUID_RE.test(studentId)) return { error: "student_id must be a uuid" };
    return { path: "/v1/admin/recovery-plans",
      query: { limit: limitOf(params), ...(status ? { status } : {}), ...(studentId ? { student_id: studentId } : {}) } };
  }
  if (view === "plan") {
    const id = params.get("id");
    if (!id || !UUID_RE.test(id)) return { error: "id must be a uuid" };
    return { path: `/v1/admin/recovery-plans/${id}`, query: {} };
  }
  return { error: "Unknown view" };
}

export function createAdminGapHandlers({ hasSession, get }) {
  return {
    async GET(request) {
      if (!await hasSession()) return Response.json({ error: "Admin login required" }, { status: 401 });
      const route = resolveAdminGapRoute(new URL(request.url).searchParams);
      if (route.error) return Response.json({ error: route.error }, { status: 400 });
      try {
        return Response.json(await get(route.path, route.query));
      } catch (err) {
        return Response.json({ error: err.message }, { status: err.status || 502 });
      }
    },
  };
}
