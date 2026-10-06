"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Transcript from "../../_components/Transcript.jsx";
import { Callout, EmptyState, Icon, PageHeader } from "../../_components/ui.jsx";

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
    return <Callout tone="neutral" icon="lock">Please <Link href="/login">sign in</Link> to see your saved tutor conversations.</Callout>;
  }
  return (
    <>
      <PageHeader icon="chat-left-text" title="My tutor conversations"
        subtitle="Every chat you have with the tutor while signed in is saved here."
        actions={<Link href="/" className="btn btn-primary btn-sm"><Icon name="plus-lg" className="me-1" />New conversation</Link>} />
      {error && <Callout tone="danger" role="alert" className="mb-3">{error.message}</Callout>}
      <div className="app-master-detail">
        <div>
          <div className="list-group" data-testid="conversation-list">
            {sessions === null && <div className="list-group-item text-secondary"><span className="spinner-border spinner-border-sm me-2" />Loading…</div>}
            {sessions?.length === 0 && <div className="list-group-item"><EmptyState icon="chat-square-dots">No saved conversations yet.</EmptyState></div>}
            {sessions?.map((s) => (
              <button key={s.agent_session_id} type="button"
                className={`list-group-item list-group-item-action${selected === s.agent_session_id ? " active" : ""}`}
                onClick={() => setSelected(s.agent_session_id)}>
                <div className="fw-semibold text-truncate">{s.preview || "(no messages yet)"}</div>
                <div className="d-flex flex-wrap gap-2 mt-1 small opacity-75">
                  <span><Icon name="clock" className="me-1" />{when(s.session_updated_at || s.last_seen_at)}</span>
                  <span><Icon name="chat" className="me-1" />{s.event_count}</span>
                  <span><Icon name="window" className="me-1" />{s.surface.replaceAll("_", " ").toLowerCase()}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
        <div>
          <section className="card">
            <div className="card-body">
              {!selected && <EmptyState icon="arrow-left-circle">Pick a conversation to read it again.</EmptyState>}
              {selected && !transcript && <p className="text-secondary mb-0"><span className="spinner-border spinner-border-sm me-2" />Loading conversation…</p>}
              <Transcript transcript={transcript} />
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
