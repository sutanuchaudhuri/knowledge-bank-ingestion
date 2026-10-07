// Private per-socket replay: never joins or publishes student evidence into classroom rooms.
import { authHeaders } from "./gateway.mjs";

export function createAttemptReplay({ rest, emit, actor, intervalMs = 1000, onError = () => {} }) {
  const watched = new Map();
  let active = true;
  let polling = false;
  const id = (value) => {
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(value))) {
      throw Object.assign(new Error("Invalid submission_id"), { status: 400 });
    }
    return value;
  };
  async function watch(submissionId, after = 0) {
    id(submissionId);
    if (!Number.isSafeInteger(after) || after < 0) throw Object.assign(new Error("Invalid event sequence"), { status: 400 });
    if (watched.size >= 10 && !watched.has(submissionId)) throw Object.assign(new Error("Too many watched submissions"), { status: 429 });
    // REST verifies JWT identity/ownership before any private event is replayed.
    const data = await rest({ path: `/v1/attempt-media/submissions/${submissionId}/events?after_sequence=${after}`,
      headers: authHeaders(actor) });
    if (!active) return [];
    const events = data.events || [];
    watched.set(submissionId, Math.max(after, ...events.map((e) => e.sequence)));
    for (const event of events) emit(event.event_type, event);
    return events;
  }
  async function tick() {
    if (!active || polling) return;
    polling = true;
    try {
      for (const [sid, sequence] of watched) {
        try { await watch(sid, sequence); }
        catch (error) { watched.delete(sid); onError(error); }
      }
    } finally { polling = false; }
  }
  const timer = setInterval(tick, intervalMs);
  timer.unref?.();
  return { watch, unwatch: (sid) => watched.delete(sid), tick,
    close() { active = false; clearInterval(timer); watched.clear(); } };
}
