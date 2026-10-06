"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const post = async (url, body) => {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
};

function JoinCard() {
  const [code, setCode] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  async function join(e) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const out = await post("/api/join", { join_code: code });
      window.location.href = `/s/${out.session_id}`;
    } catch (ex) { setErr(ex.message); setBusy(false); }
  }
  return (
    <form className="card shadow-sm" onSubmit={join}>
      <div className="card-body">
        <h2 className="h5">Join a live class</h2>
        <div className="input-group input-group-lg">
          <input className="form-control join-code text-uppercase" aria-label="Join code" placeholder="CODE" value={code}
            onChange={(e) => setCode(e.target.value)} maxLength={12} autoFocus />
          <button className="btn btn-primary" disabled={busy || code.trim().length < 4}>Join</button>
        </div>
        {err && <div className="text-danger small mt-2">{err}</div>}
      </div>
    </form>
  );
}

function InstructorHome() {
  const [sessions, setSessions] = useState([]);
  const [title, setTitle] = useState("Power of a point");
  const [topics, setTopics] = useState("Warm-up: secants and tangents\nPower of a point theorem\nPractice problem");
  const [minutes, setMinutes] = useState(30);
  const [err, setErr] = useState(null);
  useEffect(() => {
    fetch("/api/sessions", { cache: "no-store" }).then((r) => r.json()).then((d) => setSessions(d.sessions || [])).catch(() => {});
  }, []);
  async function create(e) {
    e.preventDefault();
    try {
      const s = await post("/api/sessions", { title, minutes, topics: topics.split("\n") });
      window.location.href = `/i/${s.session_id}`;
    } catch (ex) { setErr(ex.message); }
  }
  return (
    <div className="row g-4">
      <div className="col-12 col-lg-6">
        <form className="card shadow-sm" onSubmit={create}>
          <div className="card-body">
            <h2 className="h5">Start a live session</h2>
            <label className="form-label small" htmlFor="title">Title</label>
            <input id="title" className="form-control mb-2" value={title} onChange={(e) => setTitle(e.target.value)} />
            <label className="form-label small" htmlFor="topics">Topics (one per line)</label>
            <textarea id="topics" className="form-control mb-2" rows={4} value={topics} onChange={(e) => setTopics(e.target.value)} />
            <label className="form-label small" htmlFor="minutes">Minutes</label>
            <input id="minutes" type="number" min={5} max={240} className="form-control mb-3" style={{ maxWidth: 120 }}
              value={minutes} onChange={(e) => setMinutes(e.target.value)} />
            <button className="btn btn-primary">Create session</button>
            {err && <div className="text-danger small mt-2">{err}</div>}
          </div>
        </form>
      </div>
      <div className="col-12 col-lg-6">
        <div className="card shadow-sm">
          <div className="card-header bg-white fw-semibold">Recent sessions</div>
          <ul className="list-group list-group-flush">
            {sessions.length === 0 && <li className="list-group-item text-secondary small">No sessions yet.</li>}
            {sessions.map((s) => (
              <li key={s.session_id} className="list-group-item d-flex justify-content-between align-items-center">
                <span><Link href={`/i/${s.session_id}`}>{s.title}</Link> <span className="badge text-bg-light border">{s.status}</span></span>
                <code className="join-code">{s.join_code}</code>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

export default function Home({ role, name }) {
  return (
    <div className="mx-auto" style={{ maxWidth: 1100 }}>
      <h1 className="h3 mb-1">Live classroom</h1>
      <p className="text-secondary">Realtime sessions over Socket.IO — widgets, polls, tutor and instructor messages appear instantly.</p>
      {role === "INSTRUCTOR" && <><p className="small">Signed in as instructor <strong>{name}</strong>.</p><InstructorHome /></>}
      {role === "STUDENT" && <div style={{ maxWidth: 520 }}><JoinCard /></div>}
      {!role && <div className="alert alert-info">Please <Link href="/login">sign in</Link> as a student (to join with a code) or as an instructor (to run a session).</div>}
    </div>
  );
}
