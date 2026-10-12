"use client";

// Socket.IO client hook: join → snapshot + replay, then live events with sequence dedupe. On reconnect it
// re-joins with the last seen sequence so nothing is lost or duplicated (requirements 28 §reconnect).
import { useCallback, useEffect, useRef, useState } from "react";
import { io } from "socket.io-client";
import { lastSequence, mergeEvents, needsRefresh } from "../../lib/events.mjs";

export default function useLive(sid) {
  const [status, setStatus] = useState("connecting");
  const [state, setState] = useState(null);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);
  const [participantId, setParticipantId] = useState(null);
  const socketRef = useRef(null);
  const lastRef = useRef(0);
  const timer = useRef(null);

  const add = useCallback((list) => {
    setEvents((prev) => {
      const merged = mergeEvents(prev, list);
      lastRef.current = Math.max(lastRef.current, lastSequence(merged));
      return merged;
    });
  }, []);

  const op = useCallback((name, args = {}) => new Promise((resolve) => {
    const socket = socketRef.current;
    if (!socket?.connected) return resolve({ ok: false, error: "not connected" });
    socket.timeout(90_000).emit("live:op", { session_id: sid, op: name, args }, (err, res) => resolve(err ? { ok: false, error: "timed out" } : res));
  }), [sid]);

  const refresh = useCallback(() => {
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      const res = await op("state");
      if (res.ok) setState(res.data);
    }, 200);
  }, [op]);

  useEffect(() => {
    const socket = io({ path: "/socket.io", transports: ["websocket", "polling"] });
    socketRef.current = socket;
    const join = () => {
      setStatus("joining");
      socket.emit("live:join", { session_id: sid, last_sequence: lastRef.current }, (res) => {
        if (!res?.ok) { setStatus("error"); setError(res?.error || "could not join"); return; }
        setError(null);
        setStatus("live");
        setState(res.state);
        setParticipantId(res.participant_id);
        add(res.events);
      });
    };
    socket.on("connect", join);
    socket.on("disconnect", () => setStatus("reconnecting"));
    socket.on("connect_error", (e) => { setStatus("error"); setError(e.message === "UNAUTHENTICATED" ? "Please sign in first." : e.message); });
    socket.on("live:event", (e) => { add([e]); if (needsRefresh(e)) refresh(); });
    return () => { clearTimeout(timer.current); socket.close(); };
  }, [sid, add, refresh]);

  return { status, state, events, error, op, refresh, participantId };
}
