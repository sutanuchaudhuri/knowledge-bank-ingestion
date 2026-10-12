"use client";

import { fmtSeconds } from "../../lib/events.mjs";

const TONE = { live: "success", joining: "secondary", connecting: "secondary", reconnecting: "warning", error: "danger" };

export default function Header({ state, status, extra }) {
  const t = state?.time;
  return (
    <div className="d-flex flex-wrap align-items-center gap-2 mb-3">
      <h1 className="h4 mb-0 me-2">{state?.title || "Live session"}</h1>
      <span className={`badge text-bg-${TONE[status] || "secondary"}`} data-testid="connection-status">{status}</span>
      {state && <span className="badge text-bg-light border">{state.status}</span>}
      {state?.topic && <span className="text-secondary small">Topic {state.current_topic_index + 1}/{state.topics.length}: <strong>{state.topic.title}</strong></span>}
      {t && <span className={`badge ms-auto text-bg-${t.status === "ON_TRACK" ? "light border" : t.status === "BEHIND" ? "warning" : "danger"}`}
        title="Remaining course time">⏱ {fmtSeconds(t.remaining_seconds)}</span>}
      {extra}
    </div>
  );
}
