// Admin import / reconciliation / DAG review proxy (runtime_extension/15, requirements/26).
// /api/rest/admin/imports/<path...> -> /v1/admin/imports/<path...> on mathbank-rest. Allowlisted paths only;
// mutations need an admin session AND a same-origin request. The admin key is attached server-side.

const UUID_RE = /^[0-9a-fA-F-]{36}$/;
const CODE_RE = /^[A-Za-z0-9_.-]{1,100}$/;
const STEP_RE = /^[A-Za-z0-9_.:#\-/]{1,200}$/;
const BOOK_RE = /^[A-Z0-9_]{1,64}$/;

function intIn(params, key, min, max, fallback) {
  const raw = params.get(key);
  if (raw === null || raw === "") return fallback;
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) ? Math.min(Math.max(n, min), max) : fallback;
}

function pick(params, key, allowed) {
  const v = params.get(key);
  if (!v) return { value: undefined };
  return allowed.includes(v) ? { value: v } : { error: `Invalid ${key}` };
}

function compact(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== undefined));
}

const page = params => ({ limit: intIn(params, "limit", 1, 500, 50), offset: intIn(params, "offset", 0, 1_000_000, 0) });
const BASE = "/v1/admin/imports";

// GET routes -> { path, query } | { error }
export function resolveImportRead(segments = [], params = new URLSearchParams()) {
  const [head, id, tail, ...rest] = segments;
  if (rest.length) return { error: "Unknown path" };
  const book = params.get("book");
  if (book && !BOOK_RE.test(book)) return { error: "Invalid book" };
  if (head === "packages" && !id) return { path: `${BASE}/packages`, query: compact({ book: book || undefined }) };
  if (head === "packages" && id) {
    if (!UUID_RE.test(id)) return { error: "Invalid package id" };
    if (!tail) return { path: `${BASE}/packages/${id}`, query: {} };
    const entity = params.get("entity_type");
    if (entity && !/^[a-z_]{1,40}$/.test(entity)) return { error: "Invalid entity_type" };
    if (tail === "issues") {
      const kind = pick(params, "kind", ["ALL", "REJECTED", "WARNINGS"]);
      if (kind.error) return kind;
      return { path: `${BASE}/packages/${id}/issues`, query: compact({ ...page(params), entity_type: entity || undefined, kind: kind.value }) };
    }
    if (tail === "conflicts") {
      const rs = pick(params, "resolution_status", ["OPEN", "AUTO_RESOLVED", "RESOLVED", "IGNORED"]);
      if (rs.error) return rs;
      return { path: `${BASE}/packages/${id}/conflicts`, query: compact({ ...page(params), entity_type: entity || undefined, resolution_status: rs.value }) };
    }
    return { error: "Unknown path" };
  }
  if (head === "reconciliation" && !id) {
    return { path: `${BASE}/reconciliation`, query: compact({ book: book || undefined, graph: params.get("graph") === "false" ? "false" : undefined }) };
  }
  if (head === "projection-requests" && !id) {
    const st = pick(params, "status", ["PENDING", "DONE", "CANCELLED"]);
    if (st.error) return st;
    return { path: `${BASE}/projection-requests`, query: compact({ status: st.value, limit: intIn(params, "limit", 1, 500, 100) }) };
  }
  if (head === "problems" && id && tail === "dag") {
    if (!CODE_RE.test(id)) return { error: "Invalid problem code" };
    return { path: `${BASE}/problems/${encodeURIComponent(id)}/dag`, query: {} };
  }
  if (head === "actions" && !id) {
    const tt = pick(params, "target_type", ["IMPORT_CONFLICT", "SOLUTION_STEP", "STEP_DEPENDENCY", "SOLUTION_DAG", "LEARNING_ITEM", "PROJECTION_REQUEST"]);
    if (tt.error) return tt;
    return { path: `${BASE}/actions`, query: compact({ target_type: tt.value, limit: intIn(params, "limit", 1, 500, 100) }) };
  }
  return { error: "Unknown path" };
}

// Body is { action, ...payload }; returns { method, path, payload } | { error }.
export function resolveImportWrite(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) return { error: "Expected a JSON object" };
  const { action, id, code, step_id: stepId, ...payload } = body;
  switch (action) {
    case "decide-conflict":
      if (!Number.isInteger(id) || id < 1) return { error: "Invalid conflict id" };
      return { method: "POST", path: `${BASE}/conflicts/${id}/decision`, payload };
    case "request-projection":
      return { method: "POST", path: `${BASE}/projection-requests`, payload };
    case "review-learning-item":
      if (typeof id !== "string" || !UUID_RE.test(id)) return { error: "Invalid learning item id" };
      return { method: "POST", path: `${BASE}/learning-items/${id}/review`, payload };
    case "edit-step":
      if (typeof stepId !== "string" || !STEP_RE.test(stepId)) return { error: "Invalid step id" };
      return { method: "PATCH", path: `${BASE}/steps/${encodeURIComponent(stepId)}`, payload };
    case "upsert-dependency":
      return { method: "PUT", path: `${BASE}/dependencies`, payload };
    case "reject-dependency":
      return { method: "POST", path: `${BASE}/dependencies/reject`, payload };
    case "review-dag":
      if (typeof code !== "string" || !CODE_RE.test(code)) return { error: "Invalid problem code" };
      return { method: "POST", path: `${BASE}/problems/${encodeURIComponent(code)}/dag/review`, payload };
    default:
      return { error: "Unknown admin import action" };
  }
}

export function createImportHandlers({ hasSession, get, send }) {
  const fail = err => Response.json({ error: err.message }, { status: err.status || 502 });
  return {
    async GET(request, segments) {
      if (!await hasSession()) return Response.json({ error: "Admin login required" }, { status: 401 });
      const route = resolveImportRead(segments || [], new URL(request.url).searchParams);
      if (route.error) return Response.json({ error: route.error }, { status: 400 });
      try { return Response.json(await get(route.path, route.query)); } catch (err) { return fail(err); }
    },
    async POST(request) {
      if (!await hasSession()) return Response.json({ error: "Admin login required" }, { status: 401 });
      if (request.headers.get("origin") !== new URL(request.url).origin) {
        return Response.json({ error: "Same-origin admin requests are required" }, { status: 403 });
      }
      let body;
      try { body = await request.json(); } catch { return Response.json({ error: "Invalid JSON" }, { status: 400 }); }
      const route = resolveImportWrite(body);
      if (route.error) return Response.json({ error: route.error }, { status: 400 });
      try { return Response.json(await send(route.method, route.path, route.payload)); } catch (err) { return fail(err); }
    },
  };
}
