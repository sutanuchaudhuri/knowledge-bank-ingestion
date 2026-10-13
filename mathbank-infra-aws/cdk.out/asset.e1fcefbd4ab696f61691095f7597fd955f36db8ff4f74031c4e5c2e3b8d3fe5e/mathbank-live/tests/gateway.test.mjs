import assert from "node:assert/strict";
import test from "node:test";
import {
  authHeaders, buildRequest, createGateway, createOpLimiter, mergeEvents, originAllowed, parseCookies, replay,
  resolveActor, roomName, roomsForEvent, signAdminMarker, verifyAdminMarker,
} from "../lib/gateway.mjs";
import { lastSequence, needsRefresh, pollSpec } from "../lib/events.mjs";

const env = { ADMIN_SESSION_SECRET: "s3cret", MATHBANK_ADMIN_API_KEY: "admin-key", LIVE_GATEWAY_ACTOR: "gw" };
const SID = "11111111-2222-3333-4444-555555555555";

test("cookies resolve instructor (signed) before student, reject forged markers", () => {
  const marker = signAdminMarker("alice", env.ADMIN_SESSION_SECRET);
  assert.equal(verifyAdminMarker(marker, env.ADMIN_SESSION_SECRET), "alice");
  assert.equal(verifyAdminMarker(marker, "other"), null);
  assert.equal(verifyAdminMarker("admin:alice:deadbeef", env.ADMIN_SESSION_SECRET), null);
  assert.deepEqual(parseCookies("a=1; b=x%20y"), { a: "1", b: "x y" });
  assert.deepEqual(resolveActor(`mb_student_token=tok; mb_admin_session=${encodeURIComponent(marker)}`, env), { role: "INSTRUCTOR", name: "alice" });
  assert.deepEqual(resolveActor("mb_student_token=tok", env), { role: "STUDENT", token: "tok" });
  assert.equal(resolveActor("mb_admin_session=admin:x:y", env), null);
  assert.equal(resolveActor("", env), null);
});

test("auth headers per role", () => {
  assert.deepEqual(authHeaders({ role: "INSTRUCTOR", name: "alice" }, env), { "X-Admin-Api-Key": "admin-key", "X-Actor-Id": "alice" });
  assert.equal(authHeaders({ role: "STUDENT", token: "tok" }, env).Authorization, "Bearer tok");
  assert.deepEqual(authHeaders(null, env), {});
});

test("rooms are session-namespaced and audience-routed", () => {
  const ins = roomName(SID, `instructor:${SID}`);
  assert.deepEqual(roomsForEvent(SID, { audience: "SESSION" }), [roomName(SID, `session:${SID}`)]);
  assert.deepEqual(roomsForEvent(SID, { audience: "STUDENT", audience_id: "p1" }), [roomName(SID, "student:p1"), ins]);
  assert.deepEqual(roomsForEvent(SID, { audience: "GROUP", audience_id: "g1" }), [roomName(SID, "group:g1"), ins]);
  assert.deepEqual(roomsForEvent(SID, { audience: "INSTRUCTOR" }), [ins]);
  assert.deepEqual(roomsForEvent(SID, { audience: "STUDENT" }), [ins]);
});

test("operation allowlist: students refused staff ops, ids validated, unknown ops rejected", () => {
  const student = { role: "STUDENT", token: "tok" };
  const instructor = { role: "INSTRUCTOR", name: "alice" };
  assert.throws(() => buildRequest("transition", SID, { to: "NEXT" }, student, {}, env), (e) => e.status === 403);
  assert.throws(() => buildRequest("drop_tables", SID, {}, instructor, {}, env), (e) => e.status === 400);
  assert.throws(() => buildRequest("state", "../etc", {}, instructor, {}, env), (e) => e.status === 400);
  assert.throws(() => buildRequest("respond", SID, { activity_instance_id: "a/../b" }, student, {}, env), (e) => e.status === 400);
  const r = buildRequest("transition", SID, { to: "NEXT", expected_session_version: 3, junk: 1 }, instructor, {}, env);
  assert.equal(r.method, "POST");
  assert.equal(r.path, `/v1/live/sessions/${SID}/transition`);
  assert.deepEqual(r.body, { to: "NEXT", expected_session_version: 3 });
  const h = buildRequest("hide_widget", SID, { widget_instance_id: "w1" }, instructor, {}, env);
  assert.equal(h.method, "DELETE");
  const s = buildRequest("respond", SID, { activity_instance_id: "a1", option: "A" }, student, {}, env);
  assert.equal(s.headers.Authorization, "Bearer tok");
});

test("ask_tutor runs as system with the server-verified participant id, never the client's", () => {
  const r = buildRequest("ask_tutor", SID, { message: "hi", participant_id: "spoofed" }, { role: "STUDENT", token: "tok" },
    { participantId: "p-real" }, env);
  assert.equal(r.paid, true);
  assert.equal(r.headers["X-Admin-Api-Key"], "admin-key");
  assert.equal(r.headers["X-Actor-Id"], "gw");
  assert.equal(r.body.participant_id, "p-real");
  assert.equal(r.path, `/v1/tutor/sessions/${SID}/messages`);
});

test("replay follows next_after pagination", async () => {
  const calls = [];
  const rest = async ({ path }) => {
    calls.push(path);
    const after = Number(new URL(path, "http://x").searchParams.get("after_sequence"));
    const events = Array.from({ length: after < 4 ? 2 : 1 }, (_, i) => ({ sequence: after + i + 1 }));
    return { events, next_after: events.at(-1).sequence };
  };
  const out = await replay(rest, SID, 0, { role: "INSTRUCTOR", name: "a" }, { env, pageLimit: 2 });
  assert.deepEqual(out.map((e) => e.sequence), [1, 2, 3, 4, 5]);
  assert.equal(calls.length, 3);
});

test("pump fans out new events once, by audience, and detaching the last socket stops the timer", async () => {
  let log = [{ sequence: 5, audience: "SESSION" }];
  const rest = async ({ path }) => {
    const after = Number(new URL(path, "http://x").searchParams.get("after_sequence"));
    return { events: log.filter((e) => e.sequence > after), next_after: null };
  };
  const emitted = [];
  const timers = new Set();
  const gw = createGateway({ rest, env, emitTo: (rooms, ev, e) => emitted.push([rooms, e.sequence]),
    setTimer: () => { const t = {}; timers.add(t); return t; }, clearTimer: (t) => timers.delete(t) });
  gw.attach(SID, "sock1", 5);
  gw.attach(SID, "sock2", 5);
  assert.equal(timers.size, 1);
  assert.equal(await gw.pump(SID), 0);
  log = [...log, { sequence: 6, audience: "STUDENT", audience_id: "p1" }, { sequence: 7, audience: "INSTRUCTOR" }];
  assert.equal(await gw.nudge(SID), 2);
  assert.equal(await gw.nudge(SID), 0);
  assert.deepEqual(emitted, [[[roomName(SID, "student:p1"), roomName(SID, `instructor:${SID}`)], 6], [[roomName(SID, `instructor:${SID}`)], 7]]);
  gw.detach(SID, "sock1");
  assert.equal(timers.size, 1);
  gw.detach(SID, "sock2");
  assert.equal(timers.size, 0);
  assert.equal(gw.sessions.size, 0);
});

test("pump survives REST errors", async () => {
  const errors = [];
  const gw = createGateway({ rest: async () => { throw new Error("down"); }, env, emitTo: () => {}, log: (m) => errors.push(m),
    setTimer: () => 1, clearTimer: () => {} });
  gw.attach(SID, "s", 0);
  assert.equal(await gw.pump(SID), 0);
  assert.equal(errors.length, 1);
});

test("mergeEvents dedupes by sequence, sorts and caps", () => {
  const m = mergeEvents([{ sequence: 2 }, { sequence: 1 }], [{ sequence: 2, x: 1 }, { sequence: 3 }]);
  assert.deepEqual(m.map((e) => e.sequence), [1, 2, 3]);
  assert.equal(lastSequence(m), 3);
  assert.equal(mergeEvents([], Array.from({ length: 10 }, (_, i) => ({ sequence: i + 1 })), 4).length, 4);
});

test("limiter, origin check, refresh rule and poll spec", () => {
  let t = 0;
  const allow = createOpLimiter({ limit: 2, windowMs: 1000, now: () => t });
  assert.equal(allow("k"), true); assert.equal(allow("k"), true); assert.equal(allow("k"), false);
  t = 2000; assert.equal(allow("k"), true);
  assert.equal(originAllowed("http://localhost:5174", "localhost:5174"), true);
  assert.equal(originAllowed("http://evil.test", "localhost:5174"), false);
  assert.equal(originAllowed("http://localhost:5173", "localhost:5174", "http://localhost:5173"), true);
  assert.equal(originAllowed(undefined, "h"), true);
  assert.equal(needsRefresh({ event_type: "tutor.message" }), false);
  assert.equal(needsRefresh({ event_type: "widget.shown" }), true);
  const spec = pollSpec({ prompt: "Q", options: [{ id: "A", label: "6" }] },
    { option_counts: { A: 3 }, option_percentages: { A: 100 }, response_count: 3, correct_option: "A" }, true);
  assert.equal(spec.widget_type, "POLL_RESULT");
  assert.equal(spec.config.counts.A, 3);
  assert.equal(spec.config.reveal, true);
});
