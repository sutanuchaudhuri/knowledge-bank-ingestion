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

export async function restGet(path, searchParams, options = {}) {
  const res = await fetch(buildUrl(path, searchParams), { cache: "no-store", ...options });
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

// Admin endpoints (/v1/admin/*) need the shared X-Admin-Api-Key header,
// attached here server-side — the browser never sees MATHBANK_ADMIN_API_KEY.
function adminHeaders() {
  return { "Content-Type": "application/json", "X-Admin-Api-Key": process.env.MATHBANK_ADMIN_API_KEY || "" };
}

export async function restAdminGet(path, searchParams) {
  const res = await fetch(buildUrl(path, searchParams), { headers: adminHeaders(), cache: "no-store" });
  const body = await parseJsonSafely(res);
  if (!res.ok) {
    const err = new Error(body?.detail ? JSON.stringify(body.detail) : `mathbank-rest GET ${path} failed: ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return body;
}

export async function restAdminImage(path) {
  const response = await fetch(buildUrl(path), { headers: adminHeaders(), cache: "no-store" });
  if (!response.ok) {
    const error = new Error("Draft image could not be loaded");
    error.status = response.status;
    throw error;
  }
  return response;
}

export async function restAdminPost(path, payload) {
  return restAdminSend("POST", path, payload);
}

export async function restAdminSend(method, path, payload) {
  const res = await fetch(buildUrl(path), {
    method,
    headers: adminHeaders(),
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  const body = await parseJsonSafely(res);
  if (!res.ok) {
    const err = new Error(body?.detail ? JSON.stringify(body.detail) : `mathbank-rest ${method} ${path} failed: ${res.status}`);
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

// Learner endpoints (/v1/learner/*) need the student's own bearer token —
// read from the httpOnly session cookie server-side (see lib/session.js),
// never sent to/read by the browser directly.
function bearerHeaders(token) {
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

export async function restAuthGet(path, token, searchParams) {
  const res = await fetch(buildUrl(path, searchParams), { headers: bearerHeaders(token), cache: "no-store" });
  const body = await parseJsonSafely(res);
  if (!res.ok) {
    const err = new Error(body?.detail ? JSON.stringify(body.detail) : `mathbank-rest GET ${path} failed: ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return body;
}

export async function restAuthPost(path, token, payload, extraHeaders = {}) {
  const res = await fetch(buildUrl(path), {
    method: "POST",
    headers: { ...bearerHeaders(token), ...extraHeaders },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  const body = await parseJsonSafely(res);
  if (!res.ok) {
    const err = new Error(body?.detail ? JSON.stringify(body.detail) : `mathbank-rest POST ${path} failed: ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return body;
}

// Binary passthrough (problem diagrams): returns the upstream Response untouched.
export async function restRaw(path, searchParams) {
  return fetch(buildUrl(path, searchParams), { cache: "no-store" });
}

// Admin binary passthrough (all textbook diagrams, including solution-hidden ones).
export async function restAdminRaw(path) {
  return fetch(buildUrl(path), { headers: { "X-Admin-Api-Key": process.env.MATHBANK_ADMIN_API_KEY || "" }, cache: "no-store" });
}
