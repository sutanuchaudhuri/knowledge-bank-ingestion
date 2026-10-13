const BASE = "/v1/admin/corpus";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const CODE = /^[A-Za-z0-9_.-]{1,200}$/;

export function corpusRoute(method, path = []) {
  const [head, id, tail] = path;
  if (path.length > 3) return null;
  if (method === "GET") {
    if (["problems", "drafts"].includes(head) && !id) return `${BASE}/${head}`;
    if (head === "problems" && CODE.test(id || "") && !tail) return `${BASE}/problems/${encodeURIComponent(id)}`;
    if (head === "drafts" && UUID.test(id || "") && tail === "image") return `${BASE}/drafts/${id}/image`;
  }
  if (method === "POST") {
    if (["drafts", "images", "generate"].includes(head) && !id) return `${BASE}/${head}`;
    if (head === "drafts" && UUID.test(id || "") && tail === "review") return `${BASE}/drafts/${id}/review`;
  }
  if (method === "PUT" && head === "drafts" && UUID.test(id || "") && !tail) return `${BASE}/drafts/${id}`;
  return null;
}

export function createCorpusHandlers({ hasSession, get, send, image }) {
  return async (request, segments) => {
    if (!await hasSession()) return Response.json({ error: "Admin login required" }, { status: 401 });
    const method = request.method;
    if (method !== "GET" && request.headers.get("origin") !== new URL(request.url).origin) {
      return Response.json({ error: "Same-origin admin requests required" }, { status: 403 });
    }
    const path = corpusRoute(method, segments);
    if (!path) return Response.json({ error: "Unknown corpus route" }, { status: 400 });
    try {
      if (path.endsWith("/image")) return await image(path);
      if (method === "GET") {
        const allowed = segments[0] === "drafts" ? ["state", "limit", "offset"]
          : ["competition", "year", "paper", "number", "q", "missing_only", "limit", "offset"];
        const query = Object.fromEntries([...new URL(request.url).searchParams].filter(([key]) => allowed.includes(key)));
        return Response.json(await get(path, query));
      }
      if (Number(request.headers.get("content-length")) > 7_100_000) {
        return Response.json({ error: "Upload exceeds 5 MB" }, { status: 413 });
      }
      let payload;
      try { payload = await request.json(); } catch { return Response.json({ error: "Invalid JSON" }, { status: 400 }); }
      return Response.json(await send(method, path, payload));
    } catch (error) {
      return Response.json({ error: error.message }, { status: error.status || 502 });
    }
  };
}
