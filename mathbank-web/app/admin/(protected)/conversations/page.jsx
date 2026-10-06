"use client";

import { PageHeader, Pill } from "../../../_components/ui.jsx";

import { useEffect, useState } from "react";
import Transcript from "../../../_components/Transcript.jsx";

const endpoint = "/api/rest/admin/conversations";

async function load(params) {
  const response = await fetch(`${endpoint}?${new URLSearchParams(params)}`, { cache: "no-store" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}

const when = (ts) => (ts ? new Date(ts).toLocaleString() : "—");

export default function AdminConversationsPage() {
  const [student, setStudent] = useState("");
  const [query, setQuery] = useState("");
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [transcript, setTranscript] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setData(null);
    load(query ? { student: query } : {}).then(setData).catch((err) => setError(err.message));
  }, [query]);

  useEffect(() => {
    if (!selected) return;
    setTranscript(null);
    load({ id: selected }).then(setTranscript).catch((err) => setError(err.message));
  }, [selected]);

  return (
    <div>
      <PageHeader icon="people" tone="success" title="Student tutor conversations"
        subtitle="Rebuilt from agent sessions linked to students, including the agent's thinking and tool calls."
        pills={data && <><Pill tone="success" icon="link-45deg">{data.linked.length} linked</Pill><Pill tone="neutral" icon="incognito" title="Anonymous agent sessions are not attributable to a student">{data.unlinked_count} anonymous</Pill></>} />
      {error && <div role="alert" className="alert alert-danger">{error}</div>}
      <form className="d-flex gap-2 mb-3" onSubmit={(e) => { e.preventDefault(); setQuery(student.trim()); }}>
        <input className="form-control" style={{ maxWidth: 420 }} placeholder="Filter by student e-mail or id"
          value={student} onChange={(e) => setStudent(e.target.value)} aria-label="Student filter" />
        <button className="btn btn-primary">Filter</button>
      </form>
      <div className="row g-4">
        <div className="col-12 col-xl-5">
          <div className="table-responsive shadow-sm rounded-3 bg-white">
            <table className="table table-hover align-middle mb-0" data-testid="admin-conversations">
              <thead className="table-light"><tr><th>Student</th><th>Started</th><th>Msgs</th><th>Surface</th></tr></thead>
              <tbody>
                {data === null && <tr><td colSpan={4} className="text-secondary">Loading…</td></tr>}
                {data?.linked.length === 0 && <tr><td colSpan={4} className="text-secondary">No linked conversations.</td></tr>}
                {data?.linked.map((s) => (
                  <tr key={s.agent_session_id} role="button" className={selected === s.agent_session_id ? "table-primary" : ""}
                    onClick={() => setSelected(s.agent_session_id)}>
                    <td><div className="fw-semibold">{s.email}</div><div className="small text-secondary text-truncate" style={{ maxWidth: 260 }}>{s.preview}</div></td>
                    <td className="small">{when(s.created_at)}</td>
                    <td>{s.event_count}</td>
                    <td><span className="badge text-bg-light border">{s.surface}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="col-12 col-xl-7">
          <section className="card border-0 shadow-sm">
            <div className="card-body">
              {!selected && <p className="text-secondary mb-0">Select a conversation.</p>}
              {transcript && (
                <p className="small text-secondary">Session <code>{transcript.agent_session_id}</code> · {transcript.email} · agent user <code>{transcript.agent_user_id}</code></p>
              )}
              {selected && !transcript && <p className="text-secondary mb-0">Loading…</p>}
              <Transcript transcript={transcript} />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
