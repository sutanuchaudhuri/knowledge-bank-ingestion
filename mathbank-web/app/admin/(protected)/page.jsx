"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { panel, table, th, td, input, button, primaryButton } from "../../db/dbStyles.js";

const STATUS_COLOUR = {
  PENDING: "#92400e",
  DOWNLOADED: "#1d4ed8",
  PARSED: "#1d4ed8",
  INGESTED: "#15803d",
  FAILED: "#b91c1c",
};

function StatusBadge({ label }) {
  return (
    <span style={{ color: STATUS_COLOUR[label] || "#555", fontWeight: 600, fontSize: 12 }}>{label}</span>
  );
}

function CompetitionForm({ onCreated }) {
  const [form, setForm] = useState({ external_code: "", name: "", organization: "", country: "", level: "" });
  const [status, setStatus] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setStatus("saving");
    try {
      const res = await fetch("/api/rest/admin/competitions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || `status ${res.status}`);
      setStatus("done");
      setForm({ external_code: "", name: "", organization: "", country: "", level: "" });
      onCreated?.(body);
    } catch (err) {
      setStatus(`error: ${err.message}`);
    }
  }

  return (
    <form onSubmit={submit} style={{ ...panel, display: "grid", gap: 8 }}>
      <h3 style={{ marginTop: 0, fontSize: 15 }}>Add competition</h3>
      <input style={input} placeholder="External code (e.g. SMT)" required
        value={form.external_code} onChange={(e) => setForm({ ...form, external_code: e.target.value.toUpperCase() })} />
      <input style={input} placeholder="Name (e.g. Stanford Math Tournament)" required
        value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
      <input style={input} placeholder="Organization (optional)"
        value={form.organization} onChange={(e) => setForm({ ...form, organization: e.target.value })} />
      <input style={input} placeholder="Country (optional)"
        value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} />
      <input style={input} placeholder="Level (optional, e.g. HIGH_SCHOOL)"
        value={form.level} onChange={(e) => setForm({ ...form, level: e.target.value })} />
      <button type="submit" style={primaryButton}>Create competition</button>
      {status === "done" && <p style={{ color: "#15803d", fontSize: 13 }}>Created.</p>}
      {status?.startsWith("error") && <p style={{ color: "#b91c1c", fontSize: 13 }}>{status}</p>}
    </form>
  );
}

function PaperForm({ onRegistered }) {
  const [form, setForm] = useState({
    paper_external_code: "",
    competition_external_code: "",
    year: new Date().getFullYear(),
    problem_url: "",
    solution_url: "",
    source_kind: "PDF",
  });
  const [status, setStatus] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setStatus("saving");
    try {
      const res = await fetch("/api/rest/admin/papers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, year: Number(form.year), solution_url: form.solution_url || null }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || `status ${res.status}`);
      setStatus("done");
      onRegistered?.(body);
    } catch (err) {
      setStatus(`error: ${err.message}`);
    }
  }

  return (
    <form onSubmit={submit} style={{ ...panel, display: "grid", gap: 8 }}>
      <h3 style={{ marginTop: 0, fontSize: 15 }}>Register a paper (page URL)</h3>
      <p style={{ fontSize: 12, color: "#666", margin: 0 }}>
        Creates a PENDING row in pipeline.pdf_source immediately — the actual
        download/parse/ingest work runs separately (<code>make pdf-fetch</code> →
        <code> pdf-reconcile</code> → <code>pdf-ingest</code> in mathbank-db).
      </p>
      <input style={input} placeholder="Paper code (e.g. PAPER_SMT_2027_TEAM)" required
        value={form.paper_external_code}
        onChange={(e) => setForm({ ...form, paper_external_code: e.target.value.toUpperCase() })} />
      <input style={input} placeholder="Competition external code (e.g. SMT)" required
        value={form.competition_external_code}
        onChange={(e) => setForm({ ...form, competition_external_code: e.target.value.toUpperCase() })} />
      <input style={input} type="number" placeholder="Year" required
        value={form.year} onChange={(e) => setForm({ ...form, year: e.target.value })} />
      <label style={{ fontSize: 13 }}>
        Source kind:{" "}
        <select value={form.source_kind} onChange={(e) => setForm({ ...form, source_kind: e.target.value })}>
          <option value="PDF">PDF (Docling parser)</option>
          <option value="HTML">HTML (single page per paper)</option>
        </select>
      </label>
      <input style={input} placeholder="Problem page/PDF URL" required
        value={form.problem_url} onChange={(e) => setForm({ ...form, problem_url: e.target.value })} />
      <input style={input} placeholder="Solution page/PDF URL (optional)"
        value={form.solution_url} onChange={(e) => setForm({ ...form, solution_url: e.target.value })} />
      <button type="submit" style={primaryButton}>Register paper (creates PENDING row)</button>
      {status === "done" && <p style={{ color: "#15803d", fontSize: 13 }}>Registered — now PENDING.</p>}
      {status?.startsWith("error") && <p style={{ color: "#b91c1c", fontSize: 13 }}>{status}</p>}
    </form>
  );
}

function PipelineRuns({ refreshToken }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("/api/rest/admin/pipeline/runs")
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`status ${res.status}`))))
      .then(setData)
      .catch((err) => setError(err.message));
  }, [refreshToken]);

  if (error) return <p style={{ color: "#b91c1c", fontSize: 13 }}>Could not load pipeline runs: {error}</p>;
  if (!data) return <p style={{ fontSize: 13 }}>Loading…</p>;

  return (
    <div style={panel}>
      <h3 style={{ marginTop: 0, fontSize: 15 }}>Every stage logged (pipeline.run + pipeline.graph_projection)</h3>
      <table style={table}>
        <thead>
          <tr><th style={th}>Run type</th><th style={th}>Status</th><th style={th}>Started</th><th style={th}>Completed</th><th style={{ ...th, textAlign: "right" }}>Items</th></tr>
        </thead>
        <tbody>
          {data.runs?.map((r) => (
            <tr key={r.run_id}>
              <td style={td}>{r.run_type}</td>
              <td style={td}><StatusBadge label={r.status} /></td>
              <td style={td}>{(r.started_at || "").slice(0, 19)}</td>
              <td style={td}>{(r.completed_at || "—").slice(0, 19)}</td>
              <td style={{ ...td, textAlign: "right" }}>{r.completed_items}/{r.expected_items ?? "?"} ({r.failed_items} failed)</td>
            </tr>
          ))}
          {data.graph_projections?.map((g) => (
            <tr key={g.projection_run_id}>
              <td style={td}>GRAPH_PROJECTION ({g.graph_name})</td>
              <td style={td}><StatusBadge label={g.status === "COMPLETED" ? "INGESTED" : g.status === "FAILED" ? "FAILED" : "PENDING"} /></td>
              <td style={td}>{(g.started_at || "").slice(0, 19)}</td>
              <td style={td}>{(g.completed_at || "—").slice(0, 19)}</td>
              <td style={{ ...td, textAlign: "right" }}>{g.nodes_upserted} nodes / {g.edges_upserted} edges</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PapersDashboard({ refreshToken, onRetried }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const [competitionFilter, setCompetitionFilter] = useState("");

  useEffect(() => {
    fetch(`/api/rest/admin/papers${competitionFilter ? `?competition=${encodeURIComponent(competitionFilter)}` : ""}`)
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`status ${res.status}`))))
      .then((data) => setItems(data.items))
      .catch((err) => setError(err.message));
  }, [refreshToken, competitionFilter]);

  async function retry(paperCode) {
    await fetch(`/api/rest/admin/papers/${encodeURIComponent(paperCode)}/retry`, { method: "POST" });
    onRetried?.();
  }

  if (error) return <p style={{ color: "#b91c1c", fontSize: 13 }}>Could not load papers: {error}</p>;

  return (
    <div style={panel}>
      <h3 style={{ marginTop: 0, fontSize: 15 }}>Paper pipeline status (pipeline.pdf_source)</h3>
      <input style={{ ...input, marginBottom: 8 }} placeholder="Filter by competition external_code"
        value={competitionFilter} onChange={(e) => setCompetitionFilter(e.target.value.toUpperCase())} />
      {!items ? (
        <p style={{ fontSize: 13 }}>Loading…</p>
      ) : items.length === 0 ? (
        <p style={{ fontSize: 13, color: "#666" }}>No papers tracked yet.</p>
      ) : (
        <table style={table}>
          <thead>
            <tr>
              <th style={th}>Paper</th><th style={th}>Competition</th><th style={th}>Kind</th>
              <th style={th}>Download</th><th style={th}>Parse</th><th style={th}>Ingest</th>
              <th style={th}>Questions</th><th style={th}>Error</th><th style={th} />
            </tr>
          </thead>
          <tbody>
            {items.map((p) => {
              const hasFailure = [p.download_status, p.parse_status, p.ingest_status].includes("FAILED");
              return (
                <tr key={p.pdf_source_id}>
                  <td style={td}>{p.paper_external_code}</td>
                  <td style={td}>{p.competition_external_code}</td>
                  <td style={td}>{p.source_kind}</td>
                  <td style={td}><StatusBadge label={p.download_status} /></td>
                  <td style={td}><StatusBadge label={p.parse_status} /></td>
                  <td style={td}><StatusBadge label={p.ingest_status} /></td>
                  <td style={td}>{p.questions_ingested}/{p.questions_found}</td>
                  <td style={{ ...td, color: "#b91c1c", fontSize: 11 }}>{p.last_error || ""}</td>
                  <td style={td}>
                    {hasFailure && (
                      <button style={button} onClick={() => retry(p.paper_external_code)}>Retry</button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function AdminPage() {
  const [refreshToken, setRefreshToken] = useState(0);
  const bump = () => setRefreshToken((n) => n + 1);

  async function logout() {
    await fetch("/api/auth/admin-logout", { method: "POST" });
    window.location.href = "/admin/login";
  }

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: 16, fontFamily: "system-ui, sans-serif" }}>
      <p style={{ marginTop: 0 }}>
        <Link href="/" style={{ fontSize: 13, color: "#2563eb" }}>&larr; Back to chat</Link>
        {" · "}
        <Link href="/db" style={{ fontSize: 13, color: "#2563eb" }}>Corpus browser</Link>
        {" · "}
        <button onClick={logout} style={{ fontSize: 13, color: "#2563eb", background: "none", border: "none", cursor: "pointer", padding: 0, textDecoration: "underline" }}>
          Log out
        </button>
      </p>
      <h1 style={{ fontSize: 20 }}>Corpus ingestion admin</h1>
      <p style={{ color: "#666", fontSize: 13 }}>
        Add a competition and its paper URLs — rows are tracked as PENDING in{" "}
        <code>pipeline.pdf_source</code> immediately; the download/parse/ingest/embed/graph
        stages are separate commands (see requirements/11_SYSTEM_DIAGRAMS_TESTING_AND_METRICS.md).
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
        <CompetitionForm onCreated={bump} />
        <PaperForm onRegistered={bump} />
      </div>
      <div style={{ display: "grid", gap: 16 }}>
        <PapersDashboard refreshToken={refreshToken} onRetried={bump} />
        <PipelineRuns refreshToken={refreshToken} />
      </div>
    </div>
  );
}
