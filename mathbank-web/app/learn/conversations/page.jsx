"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Transcript from "../../_components/Transcript.jsx";

async function load(url) {
  const response = await fetch(url, { cache: "no-store" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(body.error || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return body;
}

const when = (ts) => (ts ? new Date(ts).toLocaleString() : "—");

export default function ConversationsPage() {
  const [sessions, setSessions] = useState(null);
  const [selected, setSelected] = useState(null);
  const [transcript, setTranscript] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    load("/api/rest/learner/conversations").then(setSessions).catch((err) => setError(err));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setTranscript(null);
    load(`/api/rest/learner/conversations/${encodeURIComponent(selected)}`).then(setTranscript).catch((err) => setError(err));
  }, [selected]);

  if (error?.status === 401) {
    return <div className="alert alert-info">Please <Link href="/login">sign in</Link> to see your saved tutor conversations.</div>;
  }
  return (
    <div className="container-fluid px-0">
      <div className="d-flex align-items-center justify-content-between mb-3">
        <div>
          <h1 className="h3 fw-bold mb-1">My tutor conversations</h1>
          <p className="text-secondary mb-0">Every chat you have with the MathBank tutor while signed in is saved here.</p>
        </div>
        <Link href="/" className="btn btn-primary">New conversation</Link>
      </div>
      {error && <div role="alert" className="alert alert-danger">{error.message}</div>}
      <div className="row g-4">
        <div className="col-12 col-lg-4">
          <div className="list-group shadow-sm" data-testid="conversation-list">
            {sessions === null && <div className="list-group-item text-secondary">Loading…</div>}
            {sessions?.length === 0 && <div className="list-group-item text-secondary">No saved conversations yet.</div>}
            {sessions?.map((s) => (
              <button key={s.agent_session_id} type="button"
                className={`list-group-item list-group-item-action${selected === s.agent_session_id ? " active" : ""}`}
                onClick={() => setSelected(s.agent_session_id)}>
                <div className="fw-semibold text-truncate">{s.preview || "(no messages yet)"}</div>
                <div className="small opacity-75">{when(s.session_updated_at || s.last_seen_at)} · {s.event_count} messages · {s.surface.replaceAll("_", " ").toLowerCase()}</div>
              </button>
            ))}
          </div>
        </div>
        <div className="col-12 col-lg-8">
          <section className="card border-0 shadow-sm">
            <div className="card-body">
              {!selected && <p className="text-secondary mb-0">Choose a conversation to read it again.</p>}
              {selected && !transcript && <p className="text-secondary mb-0">Loading conversation…</p>}
              <Transcript transcript={transcript} />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
