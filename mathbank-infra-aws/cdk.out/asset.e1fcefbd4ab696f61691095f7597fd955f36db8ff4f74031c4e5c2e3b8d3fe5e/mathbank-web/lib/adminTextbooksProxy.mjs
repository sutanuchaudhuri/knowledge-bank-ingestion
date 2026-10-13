// Admin textbook corpus browser proxy (requirements/24): read-only, admin session required.
// /api/rest/admin/textbooks/<path...> -> /v1/admin/textbooks/<path...> on mathbank-rest (allowlisted).

const CODE_RE = /^[A-Za-z0-9_.-]{1,100}$/;
const NODE_TYPES = ["DOMAIN", "CONCEPT", "SUBCONCEPT", "SKILL", "TECHNIQUE"];
const BOOL = ["true", "false"];

function intIn(params, key, min, max, fallback) {
  const raw = params.get(key);
  if (raw === null || raw === "") return fallback;
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) ? Math.min(Math.max(n, min), max) : fallback;
}

function text(params, key, max = 200) {
  const v = (params.get(key) || "").trim().slice(0, max);
  return v || undefined;
}

function compact(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== undefined));
}

function page(params, maxLimit = 200, defLimit = 50) {
  return { limit: intIn(params, "limit", 1, maxLimit, defLimit), offset: intIn(params, "offset", 0, 1_000_000, 0) };
}

// Returns { path, query, raw? } or { error } for an allowlisted read.
export function resolveTextbookRoute(segments = [], params = new URLSearchParams()) {
  const [head, id, tail, ...rest] = segments;
  if (rest.length) return { error: "Unknown path" };
  const base = "/v1/admin/textbooks";
  if (head === "coverage" && !id) {
    return { path: `${base}/coverage`, query: params.get("graph") === "false" ? { graph: "false" } : {} };
  }
  if (head === "problems" && !id) {
    const hd = params.get("has_diagram"), hs = params.get("has_solution");
    if ((hd && !BOOL.includes(hd)) || (hs && !BOOL.includes(hs))) return { error: "has_* must be true or false" };
    return { path: `${base}/problems`, query: compact({
      ...page(params), chapter: intIn(params, "chapter", 1, 99, undefined), q: text(params, "q"),
      node: text(params, "node"), has_diagram: hd || undefined, has_solution: hs || undefined }) };
  }
  if (head === "problems" && id && !tail) {
    if (!CODE_RE.test(id)) return { error: "Invalid problem code" };
    return { path: `${base}/problems/${encodeURIComponent(id)}`, query: {} };
  }
  if (head === "learning-items" && !id) {
    const tt = text(params, "transformation_type", 64);
    if (tt && !/^[A-Z_]+$/.test(tt)) return { error: "Invalid transformation_type" };
    return { path: `${base}/learning-items`, query: compact({
      ...page(params), transformation_type: tt, chapter: intIn(params, "chapter", 1, 99, undefined), q: text(params, "q") }) };
  }
  if (head === "taxonomy" && !id) {
    const nt = params.get("node_type");
    if (nt && !NODE_TYPES.includes(nt)) return { error: "Unknown node_type" };
    return { path: `${base}/taxonomy`, query: compact({ ...page(params, 500, 100), node_type: nt || undefined, q: text(params, "q") }) };
  }
  if (head === "taxonomy" && id && !tail) {
    if (!CODE_RE.test(id)) return { error: "Invalid node id" };
    return { path: `${base}/taxonomy/${encodeURIComponent(id)}`, query: {} };
  }
  if (head === "diagrams" && id && tail === "image") {
    if (!CODE_RE.test(id)) return { error: "Invalid diagram id" };
    return { path: `${base}/diagrams/${encodeURIComponent(id)}/image`, query: {}, raw: true };
  }
  return { error: "Unknown path" };
}

export function createTextbookHandlers({ hasSession, get, raw }) {
  return {
    async GET(request, segments) {
      if (!await hasSession()) return Response.json({ error: "Admin login required" }, { status: 401 });
      const route = resolveTextbookRoute(segments || [], new URL(request.url).searchParams);
      if (route.error) return Response.json({ error: route.error }, { status: 400 });
      try {
        if (route.raw) {
          const upstream = await raw(route.path);
          return new Response(upstream.body, { status: upstream.status, headers: {
            "Content-Type": upstream.headers.get("content-type") || "application/octet-stream",
            "Cache-Control": "private, max-age=3600" } });
        }
        return Response.json(await get(route.path, route.query));
      } catch (err) {
        return Response.json({ error: err.message }, { status: err.status || 502 });
      }
    },
  };
}
