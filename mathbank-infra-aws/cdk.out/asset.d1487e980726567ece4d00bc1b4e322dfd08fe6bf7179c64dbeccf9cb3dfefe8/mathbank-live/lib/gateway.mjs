// Pure realtime-gateway logic for mathbank-live (requirements 28). No sockets, no network: the Socket.IO
// wiring in server.mjs injects `rest` (an HTTP JSON caller) and `emitTo` (room fan-out), so every rule
// here — actor resolution, room naming, audience routing, the operation allowlist, replay and dedupe — is
// unit-testable. mathbank-rest stays the single source of truth: the gateway never mutates state itself,
// it forwards commands and relays the append-only live.session_event log.
import crypto from "node:crypto";

export { mergeEvents } from "./events.mjs";

export const STUDENT_COOKIE = "mb_student_token";
export const ADMIN_COOKIE = "mb_admin_session";
const ID = /^[A-Za-z0-9:_.-]{1,120}$/;

export function parseCookies(header = "") {
  const out = {};
  for (const part of String(header).split(";")) {
    const i = part.indexOf("=");
    if (i < 0) continue;
    const k = part.slice(0, i).trim();
    if (k && !(k in out)) out[k] = decodeURIComponent(part.slice(i + 1).trim());
  }
  return out;
}

export function signAdminMarker(username, secret) {
  const payload = `admin:${username}`;
  return `${payload}:${crypto.createHmac("sha256", secret).update(payload).digest("hex")}`;
}

/** Same HMAC marker format as mathbank-web (lib/session.js) so a local admin login works in both apps. */
export function verifyAdminMarker(value, secret) {
  if (!value || !secret) return null;
  const parts = String(value).split(":");
  if (parts.length !== 3 || parts[0] !== "admin") return null;
  const expected = crypto.createHmac("sha256", secret).update(`admin:${parts[1]}`).digest("hex");
  const a = Buffer.from(parts[2]);
  const b = Buffer.from(expected);
  return a.length === b.length && crypto.timingSafeEqual(a, b) ? parts[1] : null;
}

/** Resolve the socket/HTTP caller from cookies. Students are verified by mathbank-rest on first use. */
export function resolveActor(cookieHeader, env = process.env) {
  const cookies = parseCookies(cookieHeader);
  const admin = verifyAdminMarker(cookies[ADMIN_COOKIE], env.ADMIN_SESSION_SECRET);
  if (admin) return { role: "INSTRUCTOR", name: admin };
  if (cookies[STUDENT_COOKIE]) return { role: "STUDENT", token: cookies[STUDENT_COOKIE] };
  return null;
}

export function authHeaders(actor, env = process.env) {
  if (actor?.role === "INSTRUCTOR") {
    return { "X-Admin-Api-Key": env.MATHBANK_ADMIN_API_KEY || "", "X-Actor-Id": actor.name || "admin" };
  }
  if (actor?.role === "STUDENT") return { Authorization: `Bearer ${actor.token}` };
  return {};
}

export function systemActor(env = process.env) {
  return { role: "INSTRUCTOR", name: env.LIVE_GATEWAY_ACTOR || "live-gateway" };
}

/** Rooms are namespaced by session so per-student rooms never leak across sessions. */
export const roomName = (sid, room) => `${sid}|${room}`;

export function roomsForEvent(sid, event) {
  const instructors = roomName(sid, `instructor:${sid}`);
  switch (event.audience) {
    case "STUDENT": return event.audience_id ? [roomName(sid, `student:${event.audience_id}`), instructors] : [instructors];
    case "GROUP": return event.audience_id ? [roomName(sid, `group:${event.audience_id}`), instructors] : [instructors];
    case "INSTRUCTOR": return [instructors];
    default: return [roomName(sid, `session:${sid}`)];
  }
}

const enc = (v) => encodeURIComponent(String(v));
const need = (args, key) => {
  const v = args?.[key];
  if (v === undefined || v === null || !ID.test(String(v))) throw Object.assign(new Error(`invalid ${key}`), { status: 400 });
  return enc(v);
};
const pick = (args, keys) => Object.fromEntries(keys.filter((k) => args?.[k] !== undefined).map((k) => [k, args[k]]));
const VERSIONED = ["client_command_id", "expected_session_version"];

/**
 * Allowlisted operations the browser may ask the gateway to forward. `staff` ops are refused for
 * students before any REST call (REST re-checks). `asSystem` ops call REST with the admin key on the
 * participant's behalf, with the participant id taken from the verified join — never from the client.
 */
export const OPERATIONS = {
  state: { method: "GET", path: (sid) => `/v1/live/sessions/${sid}/state` },
  command: { method: "POST", path: (sid) => `/v1/live/sessions/${sid}/commands`,
    body: (a) => pick(a, ["command_type", "payload", "correlation_id", ...VERSIONED]) },
  respond: { method: "POST", path: (sid, a) => `/v1/live/sessions/${sid}/activities/${need(a, "activity_instance_id")}/responses`,
    body: (a) => pick(a, ["option", "text", "confidence", "client_command_id"]) },
  transition: { staff: true, method: "POST", path: (sid) => `/v1/live/sessions/${sid}/transition`,
    body: (a) => pick(a, ["to", "topic_index", "scene_index", ...VERSIONED]) },
  pause: { staff: true, method: "POST", path: (sid) => `/v1/live/sessions/${sid}/pause`, body: (a) => pick(a, VERSIONED) },
  resume: { staff: true, method: "POST", path: (sid) => `/v1/live/sessions/${sid}/resume`, body: (a) => pick(a, VERSIONED) },
  open_activity: { staff: true, method: "POST", path: (sid) => `/v1/live/sessions/${sid}/activities`,
    body: (a) => pick(a, ["activity_id", "definition", "seconds", "anonymous", ...VERSIONED]) },
  close_activity: { staff: true, method: "POST", path: (sid, a) => `/v1/live/sessions/${sid}/activities/${need(a, "activity_instance_id")}/close`,
    body: (a) => pick(a, VERSIONED) },
  reveal_activity: { staff: true, method: "POST", path: (sid, a) => `/v1/live/sessions/${sid}/activities/${need(a, "activity_instance_id")}/reveal`,
    body: (a) => pick(a, VERSIONED) },
  show_widget: { staff: true, method: "POST", path: (sid) => `/v1/live/sessions/${sid}/widgets`,
    body: (a) => pick(a, ["widget_spec_id", "spec", "intent", "context", "widget_instance_id", ...VERSIONED]) },
  hide_widget: { staff: true, method: "DELETE", path: (sid, a) => `/v1/live/sessions/${sid}/widgets/${need(a, "widget_instance_id")}` },
  override: { staff: true, method: "POST", path: (sid) => `/v1/instructor/live/${sid}/overrides`,
    body: (a) => pick(a, ["action", "scope", "scope_id", ...VERSIONED]) },
  instructor_nl: { staff: true, method: "POST", path: (sid) => `/v1/instructor/live/${sid}/commands`,
    body: (a) => pick(a, ["message", "auto_apply", "expected_session_version"]) },
  decide: { staff: true, method: "POST", path: (sid, a) => `/v1/instructor/live/${sid}/recommendations/${need(a, "recommendation_id")}`,
    body: (a) => pick(a, ["decision", "expected_session_version"]) },
  // Paid model call (OpenAI) on the REST side; rate-limited per participant in the gateway.
  ask_tutor: { asSystem: true, paid: true, method: "POST", path: (sid) => `/v1/tutor/sessions/${sid}/messages`,
    body: (a, ctx) => ({ message: String(a?.message || "").slice(0, 4000), participant_id: ctx.participantId || null,
      ...(a?.client_command_id ? { client_command_id: a.client_command_id } : {}) }) },
};

export function buildRequest(op, sid, args, actor, ctx = {}, env = process.env) {
  const spec = OPERATIONS[op];
  if (!spec) throw Object.assign(new Error(`unknown operation ${op}`), { status: 400 });
  if (!ID.test(String(sid))) throw Object.assign(new Error("invalid session id"), { status: 400 });
  if (spec.staff && actor?.role !== "INSTRUCTOR") throw Object.assign(new Error("instructor only"), { status: 403 });
  const caller = spec.asSystem ? systemActor(env) : actor;
  return { method: spec.method, path: spec.path(enc(sid), args || {}), headers: authHeaders(caller, env),
    body: spec.body ? spec.body(args || {}, ctx) : undefined, paid: Boolean(spec.paid) };
}

/** Fetch every event after `after` that `actor` may see (REST filters visibility), following pagination. */
export async function replay(rest, sid, after, actor, { env = process.env, pageLimit = 500, maxPages = 20 } = {}) {
  const events = [];
  let cursor = Math.max(0, Number(after) || 0);
  for (let page = 0; page < maxPages; page += 1) {
    const out = await rest({ method: "GET", path: `/v1/live/sessions/${enc(sid)}/events?after_sequence=${cursor}&limit=${pageLimit}`,
      headers: authHeaders(actor, env) });
    const batch = out.events || [];
    events.push(...batch);
    const next = Number(out.next_after ?? (batch.at(-1)?.sequence ?? cursor));
    if (batch.length < pageLimit || next <= cursor) break;
    cursor = next;
  }
  return events;
}

/**
 * Per-session event pumps. One pump per session with at least one connected socket polls REST for new
 * events (staff view) and fans them out by audience. Polling REST keeps the gateway stateless and
 * horizontally replaceable; a missed broadcast is always recoverable via replay(last_sequence).
 */
export function createGateway({ rest, emitTo, pollMs = 700, env = process.env, log = () => {},
  setTimer = setInterval, clearTimer = clearInterval } = {}) {
  const sessions = new Map();

  async function pump(sid) {
    const s = sessions.get(sid);
    if (!s || s.busy) { if (s) s.again = true; return 0; }
    s.busy = true;
    let delivered = 0;
    try {
      do {
        s.again = false;
        const events = await replay(rest, sid, s.last, systemActor(env), { env });
        for (const e of events) {
          if (e.sequence <= s.last) continue;
          emitTo(roomsForEvent(sid, e), "live:event", e);
          s.last = e.sequence;
          delivered += 1;
        }
      } while (s.again);
      s.errors = 0;
    } catch (err) {
      s.errors = (s.errors || 0) + 1;
      if (s.errors === 1 || s.errors % 20 === 0) log(`pump ${sid}: ${err.message}`);
    } finally {
      s.busy = false;
    }
    return delivered;
  }

  return {
    sessions,
    pump,
    /** Start (or join) the pump; `lastSequence` is the REST head at join time so history is not re-broadcast. */
    attach(sid, socketId, lastSequence = 0) {
      let s = sessions.get(sid);
      if (!s) {
        s = { last: Number(lastSequence) || 0, sockets: new Set(), busy: false, again: false, errors: 0 };
        s.timer = setTimer(() => { pump(sid); }, pollMs);
        sessions.set(sid, s);
      }
      s.sockets.add(socketId);
      return s;
    },
    detach(sid, socketId) {
      const s = sessions.get(sid);
      if (!s) return;
      s.sockets.delete(socketId);
      if (s.sockets.size === 0) {
        clearTimer(s.timer);
        sessions.delete(sid);
      }
    },
    nudge(sid) { return pump(sid); },
    close() { for (const [sid, s] of sessions) { clearTimer(s.timer); sessions.delete(sid); } },
  };
}

/** Very small fixed-window limiter for paid/expensive socket ops. */
export function createOpLimiter({ limit = 6, windowMs = 60_000, now = () => Date.now() } = {}) {
  const hits = new Map();
  return (key) => {
    const t = now();
    const e = hits.get(key);
    if (!e || t - e.start > windowMs) { hits.set(key, { start: t, n: 1 }); return true; }
    e.n += 1;
    return e.n <= limit;
  };
}

export function originAllowed(origin, host, extra = "") {
  if (!origin) return true; // non-browser clients (tests, curl) still need valid cookies
  try {
    const o = new URL(origin);
    if (o.host === host) return true;
    return String(extra).split(",").map((s) => s.trim()).filter(Boolean).includes(o.origin);
  } catch {
    return false;
  }
}
