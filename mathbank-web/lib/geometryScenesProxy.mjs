import { SCENE_ID, RUN_ID, DEBUG_OWNER, sceneVersion } from "./geometryScenes.mjs";

const privateHeaders = {
  "Cache-Control": "private, no-store, max-age=0",
  "X-Content-Type-Options": "nosniff",
  "Content-Security-Policy": "default-src 'none'; sandbox",
};
const error = (status, detail) => Response.json({ detail }, { status, headers: privateHeaders });
const MAX_BODY = 64 * 1024;
const text = (value, max) => typeof value === "string" && value.trim().length > 0 && value.length <= max;

export function publicInterpretError(body) {
  const detail = body?.detail;
  const safe = { message: "The geometry scene could not be loaded." };
  if (!detail || Array.isArray(detail) || typeof detail !== "object") return safe;
  if (typeof detail.code === "string" && /^[A-Z][A-Z0-9_]{0,79}$/.test(detail.code)) safe.code = detail.code;
  if (text(detail.message, 1000) && !/[\u0000-\u001f\u007f<>]/.test(detail.message)) safe.message = detail.message;
  if (typeof detail.run_id === "string" && RUN_ID.test(detail.run_id)) safe.run_id = detail.run_id;
  return safe;
}

export function validInterpretRequest(body) {
  const keys = ["problem_text", "goal", "scene_id", "expected_version", "context", "required_entities", "forbidden_entities", "seed",
    "current_math_step", "problem_id", "solution_step_id", "solve_attempt_id"];
  if (!body || Array.isArray(body) || typeof body !== "object" || Object.keys(body).some((key) => !keys.includes(key))
    || !text(body.problem_text, 20000) || !text(body.goal, 2000)) return false;
  if (body.scene_id !== undefined && (typeof body.scene_id !== "string" || !SCENE_ID.test(body.scene_id))) return false;
  if ((body.scene_id === undefined) !== (body.expected_version === undefined)
    || (body.expected_version !== undefined && !sceneVersion(body.expected_version))) return false;
  if (body.seed !== undefined && (!Number.isSafeInteger(body.seed) || body.seed < 0 || body.seed > 2147483647)) return false;
  if (body.current_math_step !== undefined && (typeof body.current_math_step !== "string" || body.current_math_step.length > 200)) return false;
  for (const key of ["problem_id", "solution_step_id", "solve_attempt_id"]) {
    if (body[key] !== undefined && (!text(body[key], 200) || /[\u0000-\u001f\u007f]/.test(body[key]))) return false;
  }
  if (body.context !== undefined && (!Array.isArray(body.context) || body.context.length > 128
    || JSON.stringify(body.context).length > 32768 || body.context.some((value) => !value
      || Array.isArray(value) || typeof value !== "object"
      || Object.keys(value).some((key) => !["type", "fact"].includes(key))
      || !text(value.type, 80) || !text(value.fact, 4000)))) return false;
  for (const key of ["required_entities", "forbidden_entities"]) {
    if (body[key] !== undefined && (!Array.isArray(body[key]) || body[key].length > 128
      || body[key].some((value) => typeof value !== "string" || !SCENE_ID.test(value)))) return false;
  }
  if (body.required_entities?.some((entity) => body.forbidden_entities?.includes(entity))) return false;
  return true;
}

export function validRunReview(body) {
  return !!body && !Array.isArray(body) && typeof body === "object"
    && Object.keys(body).every((key) => ["decision", "note"].includes(key))
    && ["ACCEPTED", "REJECTED", "NEEDS_REVISION"].includes(body.decision)
    && (body.note === undefined || (typeof body.note === "string" && body.note.length <= 4000));
}

function allowedRoute(method, segments) {
  if (method === "POST" && segments.length === 1 && segments[0] === "interpret") return { interpret: true };
  if (segments[0] === "debug" && segments[1] === "runs") {
    if (method === "GET" && (segments.length === 2 || (segments.length === 3 && RUN_ID.test(segments[2])))) return { staff: true };
    if (method === "POST" && segments.length === 4 && RUN_ID.test(segments[2]) && segments[3] === "review") return { staff: true, review: true };
    return null;
  }
  if (method !== "GET") return null;
  if (!SCENE_ID.test(segments[0] || "") || ["debug", "runs", "interpret"].includes(segments[0])) return null;
  if (segments.length === 1 || (segments.length === 2 && segments[1] === "frames")) return {};
  if (segments[1] !== "versions" || !/^(0|[1-9]\d*)$/.test(segments[2] || "")
    || !sceneVersion(Number(segments[2]))) return null;
  if (segments.length === 3) return {};
  if (segments.length === 4 && segments[3] === "render") return { image: true };
  return null;
}

/** A dedicated allowlist: no arbitrary paths, query tokens, upstream URLs or scene mutations. */
export function createGeometryScenesHandler({ getToken, hasAdmin, adminKey, baseUrl, fetcher = fetch }) {
  return async function handle(request, segments = []) {
    const route = allowedRoute(request.method, segments);
    if (!route) return error(404, "Unsupported geometry scene route");
    const input = new URL(request.url);
    const admin = await hasAdmin();
    if (route.staff && !admin) return error(403, "Staff session required");
    let owner;
    if (route.staff) {
      const entries = [...input.searchParams];
      if (entries.length !== 1 || entries[0][0] !== "owner" || !DEBUG_OWNER.test(entries[0][1])) return error(400, "A valid diagnostics owner is required");
      owner = entries[0][1];
    } else if (input.search) return error(400, "Query parameters are not supported");
    const token = admin ? null : await getToken();
    if (!admin && !token) return error(401, "Sign in to view geometry scenes");
    if (admin && !adminKey) return error(503, "Staff access is not configured");
    const headers = admin ? { "X-Admin-Api-Key": adminKey } : { Authorization: `Bearer ${token}` };
    let body;
    if (route.interpret || route.review) {
      if (request.headers.get("origin") && request.headers.get("origin") !== input.origin) return error(403, "Same-origin request required");
      if (request.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") return error(415, "JSON body required");
      if (Number(request.headers.get("content-length")) > MAX_BODY) return error(413, "Request is too large");
      const reader = request.body?.getReader();
      const chunks = [];
      let length = 0;
      if (reader) {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          length += value.byteLength;
          if (length > MAX_BODY) { await reader.cancel(); return error(413, "Request is too large"); }
          chunks.push(value);
        }
      }
      try {
        const bytes = new Uint8Array(length);
        let offset = 0;
        for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
        const parsed = JSON.parse(new TextDecoder().decode(bytes));
        if (!(route.review ? validRunReview(parsed) : validInterpretRequest(parsed))) return error(400, route.review ? "Invalid run review" : "Invalid geometry interpretation request");
        body = JSON.stringify(parsed);
      } catch { return error(400, "Invalid JSON"); }
      headers["Content-Type"] = "application/json";
    }
    try {
      const upstream = new URL(`/v1/geometry-scenes/${segments.join("/")}`, baseUrl);
      if (owner) upstream.searchParams.set("owner", owner);
      const response = await fetcher(upstream, {
        method: request.method, headers, body, cache: "no-store", redirect: "error", signal: request.signal,
      });
      const mime = response.headers.get("content-type")?.split(";")[0].trim().toLowerCase();
      if (!response.ok) {
        if (route.interpret && mime === "application/json") {
          let publicBody;
          try { publicBody = await response.json(); } catch {}
          return error(response.status, publicInterpretError(publicBody));
        }
        return error(response.status, "The geometry scene could not be loaded.");
      }
      if (route.image) {
        if (!["image/svg+xml", "image/png"].includes(mime)) return error(502, "Unexpected diagram response");
        return new Response(response.body, { headers: { ...privateHeaders, "Content-Type": mime } });
      }
      if (mime !== "application/json") return error(502, "Unexpected geometry scene response");
      return Response.json(await response.json(), { status: response.status, headers: privateHeaders });
    } catch { return error(502, "The geometry scene service is unavailable."); }
  };
}
