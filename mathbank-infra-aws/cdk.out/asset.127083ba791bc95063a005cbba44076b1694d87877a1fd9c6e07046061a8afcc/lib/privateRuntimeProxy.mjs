const ID = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}";
const rule = (method, path, queries = []) => ({ method, re: new RegExp(`^${path}$`), queries });
const attemptRules = [
  rule("GET", "submissions", ["limit", "offset", "problem_ref"]),
  rule("POST", "submissions"),
  rule("GET", `submissions/${ID}`),
  rule("GET", `submissions/${ID}/events`, ["after_sequence"]),
  rule("POST", `submissions/${ID}/assets`, ["filename", "expected_version"]),
  rule("GET", `submissions/${ID}/assets/${ID}/content`),
  rule("GET", `submissions/${ID}/assets/${ID}/pages/(?:[1-9]|10)`),
  rule("DELETE", `submissions/${ID}/assets/${ID}`),
  ...["process", "approve", "analyse", "override"].map((stage) => rule("POST", `submissions/${ID}/${stage}`)),
  rule("PUT", `submissions/${ID}/transcription`),
  rule("PATCH", `submissions/${ID}/transcription/steps/${ID}`),
];
const artifactRules = [
  rule("POST", "preview"), rule("POST", "preview/content", ["frame"]),
  rule("POST", "geometry-preview"), rule("POST", "geometry-preview/content", ["frame"]),
  rule("GET", "embedding-profile"),
  rule("POST", "requests"), rule("GET", `requests/${ID}`),
  rule("POST", `requests/${ID}/generate`),
  rule("GET", `bundles/${ID}`),
  rule("GET", `bundles/${ID}/assets`), rule("GET", `bundles/${ID}/frames`),
  rule("GET", `bundles/${ID}/assets/${ID}/content`),
  rule("GET", `bundles/${ID}/frames/(?:\\d|[1-9]\\d|1[01]\\d|12[0-7])/content`),
  rule("POST", `bundles/${ID}/similar`),
  rule("POST", `bundles/${ID}/index`),
  rule("POST", "search"), rule("POST", "search/semantic"),
];
export const MAX_MEDIA_BYTES = 20 * 1024 * 1024;
export const MEDIA_TYPES = ["image/jpeg", "image/png", "application/pdf", "audio/mpeg", "audio/mp4", "audio/wav", "audio/x-wav", "audio/webm", "video/mp4", "video/webm"];
const privateHeaders = { "Cache-Control": "private, no-store, max-age=0", "X-Content-Type-Options": "nosniff" };
const error = (status, detail) => Response.json({ detail }, { status, headers: privateHeaders });

/** Only credential helpers are injected: callers cannot choose upstream headers or hosts. */
export function createPrivateRuntimeHandler({ domain, getToken, hasAdmin, adminKey, baseUrl, fetcher = fetch }) {
  return async function handle(request, segments = []) {
    const path = segments.join("/");
    const rules = domain === "attempt-media" ? attemptRules : artifactRules;
    const allowed = rules.find((r) => r.method === request.method && r.re.test(path));
    if (!allowed) return error(404, "Unsupported runtime route");
    const admin = await hasAdmin();
    const token = admin ? null : await getToken();
    if (!admin && !token) return error(401, "Sign in to access this workspace");
    if (path.endsWith("/override") && !admin) return error(403, "Instructor session required");
    if (domain === "artifacts" && path.endsWith("/generate") && !admin) return error(403, "Instructor session required for artifact generation");
    if (domain === "artifacts" && path.endsWith("/index") && !admin) return error(403, "Instructor session required for artifact indexing");
    if (admin && !adminKey) return error(503, "Instructor access is not configured");
    const input = new URL(request.url);
    const upstream = new URL(`/v1/${domain}/${path}`, baseUrl);
    for (const [key, value] of input.searchParams) {
      if (!allowed.queries.includes(key)) return error(400, "Unsupported query parameter");
      if (key !== "filename" && key !== "problem_ref" && !/^\d+$/.test(value)) return error(400, "Invalid numeric parameter");
      if (value.length > (key === "filename" || key === "problem_ref" ? 200 : 256) || /[\r\n]/.test(value)) return error(400, "Invalid query value");
      if (!["filename", "problem_ref"].includes(key)) {
        const number = Number(value);
        if (!Number.isSafeInteger(number) || (["limit", "expected_version"].includes(key) && number < 1) || (key === "limit" && number > 100)) return error(400, "Numeric parameter is outside its allowed range");
      }
      upstream.searchParams.set(key, value);
    }
    const headers = admin ? { "X-Admin-Api-Key": adminKey } : { Authorization: `Bearer ${token}` };
    const upload = request.method === "POST" && path.endsWith("/assets");
    const hasBody = ["POST", "PUT", "PATCH"].includes(request.method);
    const max = upload ? MAX_MEDIA_BYTES : 1024 * 1024;
    let body;
    if (hasBody) {
      const type = (request.headers.get("content-type") || "").split(";")[0].toLowerCase();
      if (upload && !MEDIA_TYPES.includes(type)) return error(415, "Unsupported media type");
      if (!upload && type !== "application/json") return error(415, "JSON body required");
      if (Number(request.headers.get("content-length")) > max) return error(413, "File or request is too large");
      const chunks = [];
      let length = 0;
      const reader = request.body?.getReader();
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          length += value.byteLength;
          if (length > max) { await reader.cancel(); return error(413, "File or request is too large"); }
          chunks.push(value);
        }
      }
      body = new Uint8Array(length);
      let offset = 0;
      for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
      if (!upload) {
        try { JSON.parse(new TextDecoder().decode(body)); } catch { return error(400, "Invalid JSON"); }
      }
      if (upload && !length) return error(400, "Choose a non-empty media file");
      headers["Content-Type"] = type;
    }
    // Range passthrough makes authenticated audio/video seeking possible.
    const range = request.headers.get("range");
    if (range && path.endsWith("/content")) {
      if (!/^bytes=\d*-\d*$/.test(range)) return error(400, "Unsupported range");
      headers.Range = range;
    }
    try {
      const result = await fetcher(upstream, { method: request.method, headers, body, cache: "no-store", redirect: "error" });
      const out = new Headers(privateHeaders);
      if (path.endsWith("/content")) out.set("Content-Security-Policy", "default-src 'none'; sandbox");
      for (const name of ["content-type", "content-length", "content-range", "accept-ranges"]) {
        if (result.headers.has(name)) out.set(name, result.headers.get(name));
      }
      return new Response(result.body, { status: result.status, headers: out });
    } catch { return error(502, "The workspace service is unavailable. Your saved work is unchanged."); }
  };
}
