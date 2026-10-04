// Server-side only HTTP client for mathbank-rest (app/api/rest/* route handlers) —
// never imported from a "use client" component. The browser only ever calls our
// own /api/rest/* routes, never mathbank-rest directly.
const REST_BASE_URL = process.env.MATHBANK_REST_BASE_URL || "http://127.0.0.1:8000";

function buildUrl(path, searchParams) {
  const url = new URL(path, REST_BASE_URL);
  if (searchParams) {
    for (const [key, value] of Object.entries(searchParams)) {
      if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, value);
    }
  }
  return url;
}

async function parseJsonSafely(res) {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

export async function restGet(path, searchParams) {
  const res = await fetch(buildUrl(path, searchParams), { cache: "no-store" });
  const body = await parseJsonSafely(res);
  if (!res.ok) {
    const err = new Error(body?.detail || `mathbank-rest GET ${path} failed: ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return body;
}

export async function restPost(path, payload) {
  const res = await fetch(buildUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  const body = await parseJsonSafely(res);
  if (!res.ok) {
    const err = new Error(body?.detail || `mathbank-rest POST ${path} failed: ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return body;
}

/**
 * Fetches `limit+1` rows from a list endpoint and trims to `limit`, so the UI can
 * offer prev/next pagination via a `hasMore` flag without a backend count query.
 */
export async function restGetPage(path, searchParams, limit, offset) {
  const rows = await restGet(path, { ...searchParams, limit: limit + 1, offset });
  return { items: rows.slice(0, limit), hasMore: rows.length > limit };
}
