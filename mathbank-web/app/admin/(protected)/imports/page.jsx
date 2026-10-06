"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { DagReview, Status, human, importsAction, num, useImports, when } from "./importsClient.jsx";

const BOOK = "PRASOLOV_PGV1";
const TABS = [["packages", "Packages"], ["reconciliation", "Graph & embeddings"], ["queue", "Projection queue"],
  ["dag", "DAG review"], ["audit", "Audit trail"]];
const SEVERITY = { ERROR: "danger", WARNING: "warning", INFO: "secondary" };

function Pager({ total, limit, offset, onChange }) {
  if (!total || total <= limit) return null;
  return (
    <div className="d-flex align-items-center gap-2 small">
      <span className="text-secondary">{num(offset + 1)}–{num(Math.min(offset + limit, total))} of {num(total)}</span>
      <button type="button" className="btn btn-sm btn-outline-secondary" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>‹ Prev</button>
      <button type="button" className="btn btn-sm btn-outline-secondary" disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>Next ›</button>
    </div>
  );
}

function Packages({ onOpen }) {
  const { data, error, loading } = useImports("packages", { book: BOOK });
  if (!data) return <Status loading={loading} error={error} />;
  return (
    <div className="table-responsive" data-testid="import-packages">
      <table className="table table-hover align-middle">
        <thead><tr><th>Package</th><th>Version</th><th>Status</th><th>Postgres</th><th>Reconciled</th>
          <th className="text-end">Rejected rows</th><th className="text-end">Open conflicts</th><th>Pending projection</th><th /></tr></thead>
        <tbody>
          {data.map((p) => (
            <tr key={p.content_package_id}>
              <td><div className="fw-semibold">{p.package_name}</div><div className="small text-secondary">{p.book_code} · {p.files} files · imported {when(p.imported_at)}</div></td>
              <td>{p.package_version}</td>
              <td><span className="badge text-bg-primary">{p.status}</span>{p.status_detail && <div className="small text-secondary">{p.status_detail}</div>}</td>
              <td>{p.postgres ? "✅" : "—"}</td>
              <td>{p.reconciled ? "✅" : p.reconciled === false ? "⚠️" : "—"}</td>
              <td className="text-end">{num(p.rejected_rows)}</td>
              <td className="text-end">{num(p.open_conflicts)} <span className="text-secondary small">/ {num(p.conflicts)}</span></td>
              <td className="small">{p.pending_projection.length ? p.pending_projection.join(", ") : "—"}</td>
              <td><button type="button" className="btn btn-sm btn-outline-primary" onClick={() => onOpen(p.content_package_id)}>Open</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Issues({ packageId }) {
  const [kind, setKind] = useState("REJECTED");
  const [offset, setOffset] = useState(0);
  const { data, error, loading } = useImports(`packages/${packageId}/issues`, { kind, limit: 25, offset });
  return (
    <>
      <div className="d-flex gap-2 align-items-center mb-2">
        <select className="form-select form-select-sm w-auto" value={kind} aria-label="Issue kind" onChange={(e) => { setKind(e.target.value); setOffset(0); }}>
          <option value="REJECTED">Rejected rows</option><option value="WARNINGS">Imported with warnings</option><option value="ALL">All</option>
        </select>
        {data && <Pager total={data.total} limit={25} offset={offset} onChange={setOffset} />}
      </div>
      {!data ? <Status loading={loading} error={error} /> : (
        <div className="table-responsive"><table className="table table-sm small align-middle" data-testid="import-issues">
          <thead><tr><th>Entity</th><th>Row</th><th>External id</th><th>Status</th><th>Errors / warnings</th></tr></thead>
          <tbody>{data.items.map((r) => (
            <tr key={r.staging_row_id}><td>{r.entity_type}</td><td className="text-nowrap">{r.source_file}:{r.source_row_number}</td>
              <td><code>{r.external_id}</code></td>
              <td><span className={`badge text-bg-${r.validation_status === "REJECTED" ? "danger" : "warning"}`}>{r.validation_status}</span></td>
              <td><code className="small">{JSON.stringify([...(r.validation_errors || []), ...(r.validation_warnings || [])]).slice(0, 300)}</code></td></tr>
          ))}</tbody></table>
          {data.items.length === 0 && <p className="text-secondary small">No issues of this kind.</p>}
        </div>
      )}
    </>
  );
}

function Conflicts({ packageId }) {
  const [status, setStatus] = useState("OPEN");
  const [offset, setOffset] = useState(0);
  const [msg, setMsg] = useState(null);
  const { data, error, loading, reload } = useImports(`packages/${packageId}/conflicts`, { resolution_status: status, limit: 25, offset });
  const decide = async (id, decision) => {
    setMsg(null);
    try { await importsAction("decide-conflict", { id, decision }); setMsg({ tone: "success", text: `Conflict ${id}: ${human(decision)}` }); reload(); }
    catch (e) { setMsg({ tone: "danger", text: e.message }); }
  };
  return (
    <>
      <div className="d-flex gap-2 align-items-center mb-2">
        <select className="form-select form-select-sm w-auto" value={status} aria-label="Conflict status" onChange={(e) => { setStatus(e.target.value); setOffset(0); }}>
          {["OPEN", "RESOLVED", "AUTO_RESOLVED", "IGNORED"].map((s) => <option key={s}>{s}</option>)}
        </select>
        {data && <Pager total={data.total} limit={25} offset={offset} onChange={setOffset} />}
      </div>
      {msg && <div className={`alert alert-${msg.tone} small py-2`}>{msg.text}</div>}
      <p className="small text-secondary">Decisions are recorded and audited; accept-incoming / merge-manually take effect on the next package re-import or a DAG edit.</p>
      {!data ? <Status loading={loading} error={error} /> : (
        <div className="table-responsive"><table className="table table-sm small align-middle" data-testid="import-conflicts">
          <thead><tr><th>Severity</th><th>Type</th><th>Entity</th><th>External id</th><th>Detail</th><th>Decision</th></tr></thead>
          <tbody>{data.items.map((c) => (
            <tr key={c.conflict_id}>
              <td><span className={`badge text-bg-${SEVERITY[c.severity] || "secondary"}`}>{c.severity}</span></td>
              <td>{human(c.conflict_type)}</td><td>{c.entity_type}</td><td><code>{c.external_id}</code></td>
              <td><code className="small">{JSON.stringify(c.detail).slice(0, 200)}</code></td>
              <td className="text-nowrap">{c.decision ? <span className="badge text-bg-info">{c.decision}</span> : (
                <div className="btn-group btn-group-sm">
                  <button type="button" className="btn btn-outline-secondary" onClick={() => decide(c.conflict_id, "KEEP_EXISTING")}>Keep</button>
                  <button type="button" className="btn btn-outline-primary" onClick={() => decide(c.conflict_id, "ACCEPT_INCOMING")}>Accept</button>
                  <button type="button" className="btn btn-outline-warning" onClick={() => decide(c.conflict_id, "MERGE_MANUALLY")}>Merge</button>
                </div>)}</td>
            </tr>
          ))}</tbody></table>
          {data.items.length === 0 && <p className="text-secondary small">No conflicts with this status.</p>}
        </div>
      )}
    </>
  );
}

function PackageDetail({ packageId, onClose }) {
  const [tab, setTab] = useState("reconciliation");
  const { data, error, loading } = useImports(`packages/${packageId}`, {});
  if (!data) return <Status loading={loading} error={error} />;
  return (
    <div className="card shadow-sm border-0 mt-3" data-testid="package-detail">
      <div className="card-header bg-body d-flex align-items-center">
        <strong>{data.package_name}</strong><span className="badge text-bg-primary ms-2">{data.status}</span>
        <button type="button" className="btn-close ms-auto" aria-label="Close" onClick={onClose} />
      </div>
      <div className="card-body">
        <ul className="nav nav-pills mb-3">
          {[["reconciliation", "Reconciliation"], ["issues", "Validation issues"], ["conflicts", "Conflicts"], ["files", "Files & history"]].map(([k, l]) => (
            <li className="nav-item" key={k}><button type="button" className={`nav-link ${tab === k ? "active" : ""}`} onClick={() => setTab(k)}>{l}</button></li>
          ))}
        </ul>
        {tab === "reconciliation" && (
          <div className="table-responsive"><table className="table table-sm small align-middle">
            <thead><tr><th>Entity</th><th className="text-end">Source</th><th className="text-end">Valid</th><th className="text-end">Imported</th>
              <th className="text-end">Created</th><th className="text-end">Updated</th><th className="text-end">Rejected</th><th className="text-end">Conflicts</th><th className="text-end">In DB</th><th>Reconciled</th></tr></thead>
            <tbody>{data.reconciliation.map((r) => (
              <tr key={r.entity_type}><td>{r.entity_type}</td><td className="text-end">{num(r.source_count)}</td><td className="text-end">{num(r.valid_count)}</td>
                <td className="text-end">{num(r.imported_count)}</td><td className="text-end">{num(r.created_count)}</td><td className="text-end">{num(r.updated_count)}</td>
                <td className="text-end">{num(r.rejected_count)}</td><td className="text-end">{num(r.conflict_count)}</td><td className="text-end">{num(r.present_in_db)}</td>
                <td>{r.reconciled ? "✅" : "⚠️"}</td></tr>
            ))}</tbody></table>
            <h3 className="h6 mt-3">Conflict summary</h3>
            <table className="table table-sm small"><tbody>{data.conflict_summary.map((c, i) => (
              <tr key={i}><td>{c.entity_type}</td><td>{human(c.conflict_type)}</td><td><span className={`badge text-bg-${SEVERITY[c.severity] || "secondary"}`}>{c.severity}</span></td><td>{c.resolution_status}</td><td className="text-end">{num(c.count)}</td></tr>
            ))}</tbody></table>
          </div>
        )}
        {tab === "issues" && <Issues packageId={packageId} />}
        {tab === "conflicts" && <Conflicts packageId={packageId} />}
        {tab === "files" && (
          <div className="row g-3">
            <div className="col-lg-7"><table className="table table-sm small"><thead><tr><th>File</th><th>Role</th><th className="text-end">Rows</th><th>sha256</th></tr></thead>
              <tbody>{data.files.map((f) => <tr key={f.relative_path}><td>{f.relative_path}</td><td>{f.file_role}</td><td className="text-end">{num(f.row_count)}</td><td><code>{String(f.sha256 || "").slice(0, 12)}</code></td></tr>)}</tbody></table></div>
            <div className="col-lg-5"><ul className="list-group list-group-flush small">{data.status_history.map((h, i) => (
              <li className="list-group-item" key={i}>{when(h.created_at)} · {h.from_status || "∅"} → <strong>{h.to_status}</strong> {h.scope && <span className="text-secondary">({h.scope})</span>}</li>
            ))}</ul></div>
          </div>
        )}
      </div>
    </div>
  );
}

function Reconciliation() {
  const [graph, setGraph] = useState(true);
  const [msg, setMsg] = useState(null);
  const { data, error, loading, reload } = useImports("reconciliation", { book: BOOK, graph: graph ? undefined : "false" });
  const reproject = async (target) => {
    setMsg(null);
    try { const r = await importsAction("request-projection", { target, scope_type: "BOOK", scope_id: BOOK });
      setMsg({ tone: "success", text: `${target} ${r.created ? "queued" : "already queued"} (${r.projection_request_id.slice(0, 8)})` }); reload(); }
    catch (e) { setMsg({ tone: "danger", text: e.message }); }
  };
  return (
    <div data-testid="import-reconciliation">
      <div className="form-check form-switch mb-3">
        <input className="form-check-input" type="checkbox" id="rec-graph" checked={graph} onChange={(e) => setGraph(e.target.checked)} />
        <label className="form-check-label small" htmlFor="rec-graph">Count Neo4j (slower)</label>
      </div>
      {msg && <div className={`alert alert-${msg.tone} small py-2`}>{msg.text}</div>}
      {!data ? <Status loading={loading} error={error} /> : (
        <div className="row g-4">
          <div className="col-xl-6">
            <div className="d-flex align-items-center mb-2"><h3 className="h6 mb-0">Graph</h3>
              <button type="button" className="btn btn-sm btn-outline-primary ms-auto" onClick={() => reproject("GRAPH_TEXTBOOK_STEPS")}>Reproject missing</button></div>
            {!data.graph_ok && <div className="alert alert-warning small py-2">Graph not counted{data.graph_error ? `: ${data.graph_error}` : ""}</div>}
            <table className="table table-sm small"><thead><tr><th>Entity</th><th className="text-end">Expected</th><th className="text-end">Actual</th><th className="text-end">Missing</th><th className="text-end">Extra / stale</th></tr></thead>
              <tbody>{data.graph.map((r) => <tr key={r.entity} className={r.missing ? "table-warning" : ""}><td>{human(r.entity)}</td><td className="text-end">{num(r.expected)}</td><td className="text-end">{num(r.actual)}</td><td className="text-end">{num(r.missing)}</td><td className="text-end">{num(r.extra_or_stale)}</td></tr>)}</tbody></table>
          </div>
          <div className="col-xl-6">
            <div className="d-flex align-items-center mb-2"><h3 className="h6 mb-0">Embeddings</h3>
              <button type="button" className="btn btn-sm btn-outline-warning ms-auto" title="Paid OpenAI embeddings — queued for an operator" onClick={() => reproject("STEP_EMBEDDINGS")}>Queue re-embedding (paid)</button></div>
            <table className="table table-sm small"><thead><tr><th>Entity</th><th className="text-end">Expected</th><th className="text-end">Completed</th><th className="text-end">Missing</th></tr></thead>
              <tbody>{data.embeddings.map((r) => <tr key={r.entity} className={r.missing ? "table-warning" : ""}><td>{human(r.entity)}</td><td className="text-end">{num(r.expected)}</td><td className="text-end">{num(r.completed)}</td><td className="text-end">{num(r.missing)}</td></tr>)}</tbody></table>
            <dl className="row small mb-0">
              <dt className="col-5">Active model</dt><dd className="col-7">{data.active_embedding ? `${data.active_embedding.provider} ${data.active_embedding.model_name} (${data.active_embedding.dimensions}d) · ${num(data.active_embedding.active_embeddings)} vectors` : "—"}</dd>
              <dt className="col-5">Metadata profiles</dt><dd className="col-7">{data.metadata_profile_version.map((p) => `${p.name} v${p.version} (${num(p.representations)})`).join(", ") || "—"}</dd>
              <dt className="col-5">Embedding jobs</dt><dd className="col-7">{Object.entries(data.embedding_jobs).map(([k, v]) => `${k} ${num(v)}`).join(" · ") || "—"}</dd>
              <dt className="col-5">Failed jobs</dt><dd className="col-7">{num(data.failed_embedding_jobs)}</dd>
            </dl>
          </div>
        </div>
      )}
    </div>
  );
}

function Queue() {
  const [status, setStatus] = useState("PENDING");
  const { data, error, loading } = useImports("projection-requests", { status: status || undefined });
  return (
    <>
      <div className="d-flex gap-2 align-items-center mb-2">
        <select className="form-select form-select-sm w-auto" value={status} aria-label="Request status" onChange={(e) => setStatus(e.target.value)}>
          <option value="PENDING">Pending</option><option value="DONE">Done</option><option value="CANCELLED">Cancelled</option><option value="">All</option>
        </select>
        <span className="small text-secondary">Drain: <code>make -C mathbank-db projection-queue-run-remote</code> (free graph) · <code>projection-queue-run-paid-remote</code> (paid embeddings)</span>
      </div>
      {!data ? <Status loading={loading} error={error} /> : (
        <table className="table table-sm small" data-testid="projection-queue"><thead><tr><th>Target</th><th>Scope</th><th>Reason</th><th>Status</th><th>Requested</th><th>Completed</th></tr></thead>
          <tbody>{data.map((r) => <tr key={r.projection_request_id}><td>{r.target}</td><td>{r.scope_type} {r.scope_id}</td><td>{r.reason}</td><td>{r.status}</td>
            <td>{when(r.requested_at)} {r.requested_by && <span className="text-secondary">by {r.requested_by}</span>}</td><td>{when(r.completed_at)} {r.completed_by && <span className="text-secondary">{r.completed_by}</span>}</td></tr>)}
            {data.length === 0 && <tr><td colSpan={6} className="text-secondary">No requests.</td></tr>}</tbody></table>
      )}
    </>
  );
}

function DagTab() {
  const [input, setInput] = useState("");
  const [code, setCode] = useState("");
  return (
    <>
      <form className="d-flex gap-2 mb-3" onSubmit={(e) => { e.preventDefault(); setCode(input.trim()); }}>
        <input className="form-control form-control-sm w-auto" style={{ minWidth: 320 }} placeholder="Problem code, e.g. PRASOLOV_PGV1_CH03_P001"
          value={input} onChange={(e) => setInput(e.target.value)} aria-label="Problem code" />
        <button className="btn btn-sm btn-primary">Load DAG</button>
        {code && <Link className="btn btn-sm btn-outline-secondary" href={`/admin/textbooks/problems/${encodeURIComponent(code)}`}>Open problem</Link>}
      </form>
      {code ? <DagReview code={code} /> : <p className="small text-secondary">Enter a problem code (or open a problem from the textbook corpus) to review its solution-step DAG.</p>}
    </>
  );
}

function Audit() {
  const [type, setType] = useState("");
  const { data, error, loading } = useImports("actions", { target_type: type || undefined });
  return (
    <>
      <select className="form-select form-select-sm w-auto mb-2" value={type} aria-label="Target type" onChange={(e) => setType(e.target.value)}>
        <option value="">All targets</option>
        {["IMPORT_CONFLICT", "SOLUTION_STEP", "STEP_DEPENDENCY", "SOLUTION_DAG", "LEARNING_ITEM", "PROJECTION_REQUEST"].map((t) => <option key={t}>{t}</option>)}
      </select>
      {!data ? <Status loading={loading} error={error} /> : (
        <table className="table table-sm small" data-testid="admin-actions"><thead><tr><th>When</th><th>Target</th><th>Action</th><th>Actor</th><th>Note</th></tr></thead>
          <tbody>{data.map((a) => <tr key={a.action_id}><td className="text-nowrap">{when(a.created_at)}</td><td>{a.target_type}<div className="text-secondary"><code>{a.target_id}</code></div></td>
            <td><code>{a.action}</code></td><td>{a.actor}</td><td>{a.note}</td></tr>)}
            {data.length === 0 && <tr><td colSpan={5} className="text-secondary">No admin decisions yet.</td></tr>}</tbody></table>
      )}
    </>
  );
}

export default function ImportDashboard() {
  const [tab, setTab] = useState("packages");
  const [pkg, setPkg] = useState(null);
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    if (TABS.some(([k]) => k === p.get("tab"))) setTab(p.get("tab"));
  }, []);
  const choose = (k) => { setTab(k); window.history.replaceState(null, "", `?tab=${k}`); };
  return (
    <div className="container-fluid py-4 px-lg-5">
      <p className="small mb-2"><Link href="/admin">← Admin</Link> · <Link href="/admin/textbooks">Textbook corpus</Link></p>
      <h1 className="h3 mb-0">Imports &amp; reconciliation</h1>
      <div className="text-secondary small mb-3">Prasolov geometry packages: validation issues, conflicts, Postgres ↔ graph ↔ pgvector reconciliation, projection queue and semantic DAG review. Every decision is audited.</div>
      <ul className="nav nav-tabs mb-4" role="tablist">
        {TABS.map(([k, label]) => (
          <li className="nav-item" key={k} role="presentation">
            <button type="button" role="tab" aria-selected={tab === k} className={`nav-link ${tab === k ? "active" : ""}`} onClick={() => choose(k)}>{label}</button>
          </li>
        ))}
      </ul>
      {tab === "packages" && <><Packages onOpen={setPkg} />{pkg && <PackageDetail key={pkg} packageId={pkg} onClose={() => setPkg(null)} />}</>}
      {tab === "reconciliation" && <Reconciliation />}
      {tab === "queue" && <Queue />}
      {tab === "dag" && <DagTab />}
      {tab === "audit" && <Audit />}
    </div>
  );
}
