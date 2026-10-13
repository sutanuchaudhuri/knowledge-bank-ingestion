// Server-only JSON caller for mathbank-rest, shared by the Socket.IO gateway and Next route handlers.
export function createRest({ baseUrl = process.env.MATHBANK_REST_BASE_URL || "http://127.0.0.1:8000", fetchImpl = fetch,
  timeoutMs = 60_000 } = {}) {
  return async function rest({ method = "GET", path, headers = {}, body }) {
    const res = await fetchImpl(new URL(path, baseUrl), {
      method,
      headers: { ...(body !== undefined ? { "Content-Type": "application/json" } : {}), ...headers },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    });
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = { detail: text.slice(0, 300) }; }
    if (!res.ok) {
      const detail = data?.detail;
      const message = typeof detail === "string" ? detail : detail?.message || detail?.code || `mathbank-rest ${method} ${path.split("?")[0]} failed`;
      throw Object.assign(new Error(message), { status: res.status, code: detail?.code || null });
    }
    return data;
  };
}
