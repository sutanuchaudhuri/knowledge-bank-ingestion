// mathbank-live — separately deployable realtime classroom (requirements 28).
// One Node process: Next.js (pages + route handlers) and a Socket.IO gateway on the same HTTP server.
// The gateway is stateless: REST (/v1/live/*) owns all state; sockets only relay the event log and
// forward allowlisted commands. Custom server ⇒ do not use `output: "standalone"`.
import { createServer } from "node:http";
import { parse } from "node:url";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import nextEnv from "@next/env";
import next from "next";
import { Server } from "socket.io";
import { createGateway, buildRequest, createOpLimiter, originAllowed, replay, resolveActor, roomName } from "./lib/gateway.mjs";
import { createRest } from "./lib/rest.mjs";
import { createAttemptReplay } from "./lib/attemptEvents.mjs";

const dir = dirname(fileURLToPath(import.meta.url));
const dev = process.env.NODE_ENV !== "production";
nextEnv.loadEnvConfig(dir, dev);
const port = Number(process.env.LIVE_PORT || process.env.PORT || 5174);
const hostname = process.env.LIVE_HOST || "0.0.0.0";

const app = next({ dev, dir, hostname: "localhost", port });
await app.prepare();
const handle = app.getRequestHandler();
const nextUpgrade = typeof app.getUpgradeHandler === "function" ? app.getUpgradeHandler() : null;

const server = createServer((req, res) => handle(req, res, parse(req.url, true)));
const io = new Server(server, {
  path: "/socket.io",
  serveClient: false,
  destroyUpgrade: false, // let Next's HMR upgrade (dev) through untouched
  allowRequest: (req, cb) => cb(null, originAllowed(req.headers.origin, req.headers.host, process.env.LIVE_ALLOWED_ORIGINS)),
});
if (nextUpgrade) {
  server.on("upgrade", (req, socket, head) => {
    if (!req.url?.startsWith("/socket.io")) nextUpgrade(req, socket, head);
  });
}

const rest = createRest();
const gateway = createGateway({
  rest,
  emitTo: (rooms, event, data) => io.to(rooms).emit(event, data),
  log: (msg) => console.warn(`[live] ${msg}`),
});
const paidLimiter = createOpLimiter({ limit: 6 });

io.use((socket, nextFn) => {
  const actor = resolveActor(socket.handshake.headers.cookie);
  if (!actor) return nextFn(new Error("UNAUTHENTICATED"));
  socket.data.actor = actor;
  socket.data.joined = new Map(); // sid -> { participantId, rooms }
  return nextFn();
});

const fail = (ack, err) => typeof ack === "function" && ack({ ok: false, status: err.status || 500, error: err.message, code: err.code || null });

io.on("connection", (socket) => {
  const { actor } = socket.data;
  const attempts = createAttemptReplay({ rest, actor, emit: (event, data) => socket.emit(event, data),
    onError: () => socket.emit("attempt.progress.error", { code: "REPLAY_UNAVAILABLE" }) });
  socket.on("attempt:watch", async (msg, ack) => {
    try {
      const events = await attempts.watch(String(msg?.submission_id || ""), msg?.after_sequence ?? 0);
      if (typeof ack === "function") ack({ ok: true, events });
    } catch (error) { fail(ack, error); }
  });
  socket.on("attempt:unwatch", (msg) => attempts.unwatch(String(msg?.submission_id || "")));

  socket.on("live:join", async (msg, ack) => {
    try {
      const sid = String(msg?.session_id || "");
      const stateReq = buildRequest("state", sid, {}, actor); // validates sid
      // REST decides membership and rooms (403 NOT_A_PARTICIPANT for students who have not joined).
      const info = await rest({ method: "GET", path: `/v1/realtime/sessions/${encodeURIComponent(sid)}`, headers: stateReq.headers });
      const rooms = info.rooms.map((r) => roomName(sid, r));
      const participantId = info.rooms.find((r) => r.startsWith("student:"))?.slice("student:".length) || null;
      await socket.join(rooms);
      socket.data.joined.set(sid, { participantId, rooms });
      gateway.attach(sid, socket.id, info.last_sequence);
      const missed = await replay(rest, sid, msg?.last_sequence || 0, actor);
      const state = await rest(stateReq);
      if (typeof ack === "function") ack({ ok: true, role: actor.role, participant_id: participantId, state, events: missed });
    } catch (err) {
      fail(ack, err);
    }
  });

  socket.on("live:op", async (msg, ack) => {
    try {
      const sid = String(msg?.session_id || "");
      const joined = socket.data.joined.get(sid);
      if (!joined) throw Object.assign(new Error("join the session first"), { status: 403 });
      const req = buildRequest(String(msg?.op || ""), sid, msg?.args || {}, actor, { participantId: joined.participantId });
      if (req.paid && !paidLimiter(`${sid}|${joined.participantId || actor.name}`)) {
        throw Object.assign(new Error("Too many tutor requests — wait a minute."), { status: 429 });
      }
      const data = await rest(req);
      if (typeof ack === "function") ack({ ok: true, data });
      gateway.nudge(sid);
    } catch (err) {
      fail(ack, err);
    }
  });

  socket.on("disconnect", () => {
    attempts.close();
    for (const sid of socket.data.joined.keys()) gateway.detach(sid, socket.id);
  });
});

server.listen(port, hostname, () => {
  console.log(`mathbank-live ready on http://localhost:${port} (${dev ? "dev" : "production"}; socket.io at /socket.io)`);
});

const shutdown = () => { gateway.close(); io.close(); server.close(() => process.exit(0)); setTimeout(() => process.exit(0), 3000).unref(); };
process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
