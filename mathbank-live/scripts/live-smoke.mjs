#!/usr/bin/env node
// Two-socket realtime smoke for a RUNNING stack (REST :8000 + live :5174). No paid model calls.
// instructor socket + student socket: widget/message/poll fan-out, student-only refusal of staff ops,
// response → aggregate, and reconnect replay without duplicates. Exit code 0 = pass.
import fs from "node:fs";
import { io } from "socket.io-client";

const BASE = process.env.LIVE_URL || "http://127.0.0.1:5174";
const WEB = process.env.WEB_URL || "http://127.0.0.1:5173";
const env = Object.fromEntries((fs.existsSync(".env") ? fs.readFileSync(".env", "utf8") : "").split(/\r?\n/)
  .filter((l) => /^[A-Z_]+=/.test(l)).map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1).replace(/^["']|["']$/g, "")]));
const STUDENT = { email: process.env.E2E_STUDENT_EMAIL || "e2e.regression.student@example.com",
  password: process.env.E2E_STUDENT_PASSWORD || "E2eRegression123!", first_name: "E2E", last_name: "Regression" };

const cookieOf = (res) => (res.headers.getSetCookie?.() || []).map((c) => c.split(";")[0]).join("; ");
async function call(path, body, cookie = "", base = BASE) {
  const res = await fetch(base + path, { method: body ? "POST" : "GET", headers: { "Content-Type": "application/json", cookie },
    body: body ? JSON.stringify(body) : undefined });
  const data = await res.json().catch(() => ({}));
  return { res, data };
}
const step = (msg) => console.log(`✓ ${msg}`);
const fail = (msg) => { console.error(`✗ ${msg}`); process.exit(1); };
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

function connect(cookie) {
  const socket = io(BASE, { path: "/socket.io", transports: ["websocket"], extraHeaders: { cookie }, reconnection: false });
  const events = [];
  socket.on("live:event", (e) => events.push(e));
  return { socket, events,
    ready: () => new Promise((ok, ko) => { socket.on("connect", ok); socket.on("connect_error", ko); }),
    join: (sid, last = 0) => socket.timeout(15000).emitWithAck("live:join", { session_id: sid, last_sequence: last }),
    op: (sid, op, args = {}) => socket.timeout(30000).emitWithAck("live:op", { session_id: sid, op, args }) };
}
async function until(fn, label, ms = 8000) {
  const end = Date.now() + ms;
  while (Date.now() < end) { if (fn()) return; await wait(100); }
  fail(`timed out waiting for ${label}`);
}

// 1. sign in both roles through the live app's own HTTP routes
const admin = await call("/api/auth/admin-login", { username: env.ADMIN_LOGIN_USERNAME, password: env.ADMIN_LOGIN_PASSWORD });
if (!admin.res.ok) fail(`instructor login ${admin.res.status} (run make sync-live-env)`);
const adminCookie = cookieOf(admin.res);
let login = await call("/api/auth/student-login", { email: STUDENT.email, password: STUDENT.password });
if (!login.res.ok) {
  await call("/api/auth/student-register", STUDENT, "", WEB);
  login = await call("/api/auth/student-login", { email: STUDENT.email, password: STUDENT.password });
}
if (!login.res.ok) fail(`student login ${login.res.status}`);
const studentCookie = cookieOf(login.res);
step("instructor + student signed in via mathbank-live");

// 2. anonymous sockets are refused
const anon = connect("");
try { await anon.ready(); fail("anonymous socket connected"); } catch (e) { if (e.message !== "UNAUTHENTICATED") fail(`anon: ${e.message}`); }
anon.socket.close();
step("anonymous socket refused (UNAUTHENTICATED)");

// 3. create + join
const created = await call("/api/sessions", { title: `Live smoke ${new Date().toISOString()}`, minutes: 20,
  topics: ["Secants and tangents", "Power of a point"] }, adminCookie);
if (created.res.status !== 201 && !created.res.ok) fail(`create session ${created.res.status} ${JSON.stringify(created.data)}`);
const sid = created.data.session_id;
const joined = await call("/api/join", { join_code: created.data.join_code }, studentCookie);
if (!joined.res.ok) fail(`join ${joined.res.status} ${JSON.stringify(joined.data)}`);
step(`session ${sid} created, student joined with code ${created.data.join_code}`);

const ins = connect(adminCookie);
const stu = connect(studentCookie);
await Promise.all([ins.ready(), stu.ready()]);
const [ji, js] = await Promise.all([ins.join(sid), stu.join(sid)]);
if (!ji.ok || ji.role !== "INSTRUCTOR") fail(`instructor join ${JSON.stringify(ji)}`);
if (!js.ok || js.role !== "STUDENT" || !js.participant_id) fail(`student join ${JSON.stringify(js)}`);
if (js.state.participants) fail("student snapshot leaked staff-only participants");
step("both sockets joined; student snapshot has no staff-only fields");

// 4. student cannot drive the session
const refused = await stu.op(sid, "transition", { to: "NEXT" });
if (refused.ok || refused.status !== 403) fail(`student transition not refused: ${JSON.stringify(refused)}`);
step("student staff op refused (403) before reaching REST");

// 5. start + widget + message fan-out
let r = await ins.op(sid, "transition", { to: "START", expected_session_version: ji.state.state_version, client_command_id: `smoke-start-${sid}` });
if (!r.ok) fail(`start ${JSON.stringify(r)}`);
r = await ins.op(sid, "show_widget", { intent: "power of a point" });
if (!r.ok) fail(`show widget ${JSON.stringify(r)}`);
r = await ins.op(sid, "command", { command_type: "INSTRUCTOR_MESSAGE", payload: { text: "Remember $PA \\cdot PB = PT^2$" }, client_command_id: `smoke-msg-${sid}` });
if (!r.ok) fail(`message ${JSON.stringify(r)}`);
await until(() => stu.events.some((e) => e.event_type === "widget.shown"), "student widget.shown");
await until(() => stu.events.some((e) => e.event_type === "instructor.message"), "student instructor.message");
step("widget.shown + instructor.message pushed to the student socket");

// 6. poll → response → aggregate visible to instructor
r = await ins.op(sid, "open_activity", { definition: { activity_type: "LIVE_POLL", prompt: "PA=4, PB=9. PT=?",
  options: [{ id: "A", label: "6" }, { id: "B", label: "13" }], correctness_policy: { correct_option: "A" } }, seconds: 60 });
if (!r.ok) fail(`open poll ${JSON.stringify(r)}`);
await until(() => stu.events.some((e) => e.event_type === "activity.opened"), "student activity.opened");
const st = await stu.op(sid, "state");
const aid = st.data?.activity?.activity_instance_id;
if (!aid) fail("student state has no activity");
r = await stu.op(sid, "respond", { activity_instance_id: aid, option: "A", client_command_id: `smoke-resp-${sid}` });
if (!r.ok) fail(`respond ${JSON.stringify(r)}`);
r = await stu.op(sid, "command", { command_type: "QUESTION_ASK", payload: { text: "Why is it squared?" }, client_command_id: `smoke-q-${sid}` });
if (!r.ok) fail(`question ${JSON.stringify(r)}`);
await until(() => ins.events.some((e) => e.event_type === "student.question_asked" || e.event_type?.startsWith("student.")), "instructor sees student event");
const view = await ins.op(sid, "state");
if (view.data?.activity_aggregate?.response_count !== 1) fail(`aggregate ${JSON.stringify(view.data?.activity_aggregate)}`);
if (stu.events.some((e) => e.audience === "INSTRUCTOR")) fail("instructor-only event reached the student");
step("poll response aggregated for instructor; instructor-only events never reached the student");

// 7. reconnect replay: new socket with last_sequence gets only newer events, no duplicates
const last = Math.max(...stu.events.map((e) => e.sequence));
stu.socket.close();
await ins.op(sid, "reveal_activity", { activity_instance_id: aid });
const again = connect(studentCookie);
await again.ready();
const rj = await again.join(sid, last);
if (!rj.ok) fail(`rejoin ${JSON.stringify(rj)}`);
const seqs = rj.events.map((e) => e.sequence);
if (seqs.some((s) => s <= last)) fail(`replay returned old events ${seqs}`);
if (!rj.events.some((e) => e.event_type === "activity.revealed")) fail(`replay missing activity.revealed ${rj.events.map((e) => e.event_type)}`);
if (rj.state.activity_aggregate?.correct_option !== "A") fail("revealed aggregate not visible to student");
step(`reconnect replayed ${seqs.length} missed event(s) after #${last}, no duplicates; revealed results visible`);

await ins.op(sid, "transition", { to: "COMPLETE", expected_session_version: (await ins.op(sid, "state")).data.state_version });
ins.socket.close(); again.socket.close();
console.log("live smoke: PASS");
process.exit(0);
