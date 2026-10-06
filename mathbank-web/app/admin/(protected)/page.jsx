"use client";

import { useEffect, useState } from "react";
import AdminOverview from "./AdminOverview.jsx";
import PipelineJobs from "./PipelineJobs.jsx";
import { Icon, IconButton, PageHeader, Pager, Pill } from "../../_components/ui.jsx";
import { panel, table, th, td, input, button, primaryButton } from "../../db/dbStyles.js";

const STATUS_COLOUR = {
  PENDING: "#92400e",
  DOWNLOADED: "#1d4ed8",
  PARSED: "#1d4ed8",
  INGESTED: "#15803d",
  FAILED: "#b91c1c",
  COMPLETED: "#15803d",
  IN_PROGRESS: "#1d4ed8",
};

function StatusBadge({ label }) {
  return (
    <span className="badge rounded-pill bg-light border" style={{ color: STATUS_COLOUR[label] || "#555" }}>{label}</span>
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
    <form onSubmit={submit} className={`${panel} gap-3`}>
      <h3 className="h5 fw-bold">Add competition</h3>
      <input className={input} aria-label="External code" placeholder="External code (e.g. SMT)" required
        value={form.external_code} onChange={(e) => setForm({ ...form, external_code: e.target.value.toUpperCase() })} />
      <input className={input} aria-label="Competition name" placeholder="Name (e.g. Stanford Math Tournament)" required
        value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
      <input className={input} aria-label="Organization" placeholder="Organization (optional)"
        value={form.organization} onChange={(e) => setForm({ ...form, organization: e.target.value })} />
      <input className={input} aria-label="Country" placeholder="Country (optional)"
        value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} />
      <input className={input} aria-label="Level" placeholder="Level (optional, e.g. HIGH_SCHOOL)"
        value={form.level} onChange={(e) => setForm({ ...form, level: e.target.value })} />
      <button type="submit" className={primaryButton}>Create competition</button>
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
    <form onSubmit={submit} className={`${panel} gap-3`}>
      <h3 className="h5 fw-bold">Register a paper (page URL)</h3>
      <p style={{ fontSize: 12, color: "#666", margin: 0 }}>
        Creates a PENDING row in pipeline.pdf_source immediately — the actual
        download/parse/ingest work runs separately (<code>make pdf-fetch</code> →
        <code> pdf-reconcile</code> → <code>pdf-ingest</code> in mathbank-db).
      </p>
      <input className={input} aria-label="Paper code" placeholder="Paper code (e.g. PAPER_SMT_2027_TEAM)" required
        value={form.paper_external_code}
        onChange={(e) => setForm({ ...form, paper_external_code: e.target.value.toUpperCase() })} />
      <input className={input} aria-label="Competition external code" placeholder="Competition external code (e.g. SMT)" required
        value={form.competition_external_code}
        onChange={(e) => setForm({ ...form, competition_external_code: e.target.value.toUpperCase() })} />
      <input className={input} aria-label="Year" type="number" placeholder="Year" required
        value={form.year} onChange={(e) => setForm({ ...form, year: e.target.value })} />
      <label className="form-label mb-0">
        Source kind:{" "}
        <select className="form-select" value={form.source_kind} onChange={(e) => setForm({ ...form, source_kind: e.target.value })}>
          <option value="PDF">PDF (Docling parser)</option>
          <option value="HTML">HTML (single page per paper)</option>
        </select>
      </label>
      <input className={input} aria-label="Problem page or PDF URL" placeholder="Problem page/PDF URL" required
        value={form.problem_url} onChange={(e) => setForm({ ...form, problem_url: e.target.value })} />
      <input className={input} aria-label="Solution page or PDF URL" placeholder="Solution page/PDF URL (optional)"
        value={form.solution_url} onChange={(e) => setForm({ ...form, solution_url: e.target.value })} />
      <button type="submit" className={primaryButton}>Register paper (creates PENDING row)</button>
      {status === "done" && <p style={{ color: "#15803d", fontSize: 13 }}>Registered — now PENDING.</p>}
      {status?.startsWith("error") && <p style={{ color: "#b91c1c", fontSize: 13 }}>{status}</p>}
    </form>
  );
}

function PipelineRuns({ refreshToken }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/rest/admin/pipeline/runs", { signal: controller.signal })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`status ${res.status}`))))
      .then((result) => { setData(result); setError(null); })
      .catch((err) => { if (err.name !== "AbortError") setError(err.message); });
    return () => controller.abort();
  }, [refreshToken]);

  if (error) return <p style={{ color: "#b91c1c", fontSize: 13 }}>Could not load pipeline runs: {error}</p>;
  if (!data) return <p style={{ fontSize: 13 }}>Loading…</p>;

  return (
    <div>
      <div className="table-responsive"><table className={table}>
        <thead>
          <tr><th style={th}>Run type</th><th style={th}>Status</th><th style={th}>Started</th><th style={th}>Completed</th><th style={{ ...th, textAlign: "right" }}>Items</th><th style={th}>Run / logs</th></tr>
        </thead>
        <tbody>
          {data.runs?.map((r) => (
            <tr key={r.run_id}>
              <td style={td}>{r.run_type}</td>
              <td style={td}><StatusBadge label={r.status} /></td>
              <td style={td}>{(r.started_at || "").slice(0, 19)}</td>
              <td style={td}>{(r.completed_at || "—").slice(0, 19)}</td>
              <td style={{ ...td, textAlign: "right" }}>{r.completed_items}/{r.expected_items ?? "?"} ({r.failed_items} failed)</td>
              <td style={td}>
                <code className="small">{r.run_id}</code>
                {r.metadata?.log_dir && <div className="small text-break">{r.metadata.log_dir}</div>}
                {r.heartbeat_at && <div className="small text-secondary">Heartbeat: {r.heartbeat_at.slice(0, 19)}</div>}
              </td>
            </tr>
          ))}
          {data.graph_projections?.map((g) => (
            <tr key={g.projection_run_id}>
              <td style={td}>GRAPH_PROJECTION ({g.graph_name})</td>
              <td style={td}><StatusBadge label={g.status === "COMPLETED" ? "INGESTED" : g.status === "FAILED" ? "FAILED" : "PENDING"} /></td>
              <td style={td}>{(g.started_at || "").slice(0, 19)}</td>
              <td style={td}>{(g.completed_at || "—").slice(0, 19)}</td>
              <td style={{ ...td, textAlign: "right" }}>{g.nodes_upserted} nodes / {g.edges_upserted} edges</td>
              <td style={td}><code className="small">{g.projection_run_id}</code></td>
            </tr>
          ))}
        </tbody>
      </table></div>
    </div>
  );
}

function PapersDashboard({ refreshToken, onRetried }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const [competitionFilter, setCompetitionFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const pageSize = 50;

  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/rest/admin/papers?limit=${pageSize}&offset=${offset}${competitionFilter ? `&competition=${encodeURIComponent(competitionFilter)}` : ""}`, { signal: controller.signal })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`status ${res.status}`))))
      .then((data) => { setItems(data.items); setError(null); })
      .catch((err) => { if (err.name !== "AbortError") setError(err.message); });
    return () => controller.abort();
  }, [refreshToken, competitionFilter, offset]);

  async function retry(paperCode) {
    await fetch(`/api/rest/admin/papers/${encodeURIComponent(paperCode)}/retry`, { method: "POST" });
    onRetried?.();
  }

  if (error) return <p style={{ color: "#b91c1c", fontSize: 13 }}>Could not load papers: {error}</p>;

  return (
    <div>
      <input className={`${input} mb-3`} aria-label="Filter by competition external code" placeholder="Filter by competition external_code"
        value={competitionFilter} onChange={(e) => { setCompetitionFilter(e.target.value.toUpperCase()); setOffset(0); }} />
      <Pager offset={offset} limit={pageSize} count={items?.length || 0} hasMore={Boolean(items && items.length >= pageSize)}
        onPrev={() => setOffset((n) => Math.max(0, n - pageSize))} onNext={() => setOffset((n) => n + pageSize)} />
      {!items ? (
        <p style={{ fontSize: 13 }}>Loading…</p>
      ) : items.length === 0 ? (
        <p style={{ fontSize: 13, color: "#666" }}>No papers tracked yet.</p>
      ) : (
        <div className="table-responsive"><table className={table}>
          <thead>
            <tr>
              <th style={th}>Paper</th><th style={th}>Competition</th><th style={th}>Kind</th>
              <th style={th}>Download</th><th style={th}>Parse</th><th style={th}>Ingest</th>
              <th style={th}>Classify</th><th style={th}>Graph</th><th style={th}>Batch stage</th>
              <th style={th}>Questions</th><th style={th}>Error</th><th style={th} />
            </tr>
          </thead>
          <tbody>
            {items.map((p) => {
              const hasFailure = [p.download_status, p.parse_status, p.ingest_status].includes("FAILED");
              const metrics = p.batch_metrics || {};
              return (
                <tr key={p.pdf_source_id}>
                  <td style={td}>{p.paper_external_code}</td>
                  <td style={td}>{p.competition_external_code}</td>
                  <td style={td}>{p.source_kind}</td>
                  <td style={td}><StatusBadge label={p.download_status} /></td>
                  <td style={td}><StatusBadge label={p.parse_status} /></td>
                  <td style={td}><StatusBadge label={p.ingest_status} /></td>
                  <td style={td}><StatusBadge label={metrics.classification_status || (metrics.graph_verified ? "COMPLETED" : p.batch_run_id ? "PENDING" : "NOT_TRACKED")} /></td>
                  <td style={td}><StatusBadge label={metrics.graph_status || (metrics.graph_verified ? "COMPLETED" : p.batch_run_id ? "PENDING" : "NOT_TRACKED")} /></td>
                  <td style={td}>
                    {metrics.stage || "Not started"}
                    {p.batch_run_id && <div className="small text-secondary">{p.batch_run_id}</div>}
                    {metrics.parse_warnings?.length > 0 && <details className="small text-warning-emphasis">
                      <summary>Extraction warnings</summary>
                      <ul>{metrics.parse_warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
                    </details>}
                  </td>
                  <td style={td}>{p.questions_ingested}/{p.questions_found}</td>
                  <td style={{ ...td, color: "#b91c1c", fontSize: 11 }}>{p.batch_error || p.last_error || ""}</td>
                  <td style={td}>
                    {hasFailure && (
                      <button className={button} onClick={() => retry(p.paper_external_code)}>Retry</button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table></div>
      )}
    </div>
  );
}

export default function AdminPage() {
  const [refreshToken, setRefreshToken] = useState(0);
  const bump = () => setRefreshToken((n) => n + 1);
  useEffect(() => {
    const timer = setInterval(() => setRefreshToken((n) => n + 1), 15000);
    return () => clearInterval(timer);
  }, []);

  return (
    <>
      <PageHeader icon="speedometer2" tone="warning" title="Corpus ingestion admin"
        subtitle="Pipeline health, textbook coverage and learner signals at a glance."
        pills={<Pill tone="neutral" icon="arrow-repeat" title="Generated metadata is automatically approved with provenance; human corrections are protected. Every pipeline layer is verified separately.">Auto-refresh 15s</Pill>}
        actions={<IconButton icon="arrow-clockwise" label="Refresh pipeline status" variant="outline-secondary" onClick={bump} />} />
      <AdminOverview refreshToken={refreshToken} />
      <div className="d-grid gap-4">
        <div id="pipeline-jobs"><PipelineJobs refreshToken={refreshToken} /></div>
        <details className="card p-3">
          <summary className="mb-section-title"><Icon name="plus-circle" />Register a competition or paper</summary>
          <p className="small text-secondary mt-3">
            Rows are tracked as PENDING in <code>pipeline.pdf_source</code> immediately; download, parse, ingest, embed and graph
            run as separate stages (requirements/11).
          </p>
          <div className="app-admin-forms">
            <CompetitionForm onCreated={bump} />
            <PaperForm onRegistered={bump} />
          </div>
        </details>
        <details className="card p-3">
          <summary className="mb-section-title"><Icon name="arrow-counterclockwise" />Paper sources &amp; retries</summary>
          <div className="mt-3"><PapersDashboard refreshToken={refreshToken} onRetried={bump} /></div>
        </details>
        <details className="card p-3">
          <summary className="mb-section-title"><Icon name="journal-text" />Stage log</summary>
          <div className="mt-3"><PipelineRuns refreshToken={refreshToken} /></div>
        </details>
      </div>
    </>
  );
}
