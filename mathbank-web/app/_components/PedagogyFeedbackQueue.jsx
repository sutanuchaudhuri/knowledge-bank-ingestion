"use client";

import { useEffect, useState } from "react";
import { Callout, Pager, Pill, SectionTitle } from "./ui.jsx";
import ProblemDetail from "../db/ProblemDetail.jsx";

const endpoint = "/api/rest/admin/pedagogy";

export default function PedagogyFeedbackQueue() {
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [note, setNote] = useState("");
  const [decision, setDecision] = useState("RESOLVED");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);
  const [verdict, setVerdict] = useState("UNCLASSIFIED");
  const [errorKind, setErrorKind] = useState("UNCLASSIFIED");
  useEffect(() => {
    const controller = new AbortController();
    setError(null);
    setData(null);
    fetch(`${endpoint}?view=feedback&limit=10&offset=${offset}`, { signal: controller.signal })
      .then(async (r) => { const body = await r.json(); if (!r.ok) throw new Error(body.error || "Feedback queue unavailable"); return body; })
      .then(setData).catch((err) => { if (err.name !== "AbortError") setError(err.message); });
    return () => controller.abort();
  }, [offset, reload]);
  async function review(event) {
    event.preventDefault();
    setBusy(true); setError(null);
    try {
      const r = await fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "feedback-review", feedback_id: selected.feedback_id, status: decision, note: note.trim(),
          retrieval_verdict: verdict, error_kind: errorKind }) });
      const body = await r.json();
      if (!r.ok) throw new Error(body.error || "Review failed");
      setSelected(null); setNote(""); setReload((n) => n + 1);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <section className="card p-3 mb-3" aria-label="Learner relevance reports">
    <SectionTitle icon="chat-left-text">Learner relevance reports</SectionTitle>
    <p className="small text-secondary">Reports are allegations, not approved annotations. Correct the mapping below and publish separately before resolving.</p>
    {error && <Callout tone="danger" role="alert">{error}</Callout>}
    {!data && !error && <span role="status">Loading reports…</span>}
    {data && <><div className="table-responsive"><table className="table table-hover align-middle">
      <thead><tr><th>Problem</th><th>Topic</th><th>Report</th><th>Status</th></tr></thead>
      <tbody>{data.items.map((item) => <tr key={item.feedback_id} className={selected?.feedback_id === item.feedback_id ? "table-active" : ""}>
        <td><button type="button" className="btn btn-link p-0" disabled={busy} aria-pressed={selected?.feedback_id === item.feedback_id}
          onClick={() => { setSelected(item); setNote(""); setShowEvidence(false); setVerdict("UNCLASSIFIED"); setErrorKind("UNCLASSIFIED"); }}>{item.canonical_code}</button></td>
        <td>{item.topic}</td><td>{item.reason}</td><td><Pill tone={item.status === "PENDING" ? "warning" : "neutral"}>{item.status}</Pill></td>
      </tr>)}</tbody>
    </table></div>{!data.items.length && <p className="text-secondary">No learner reports.</p>}
      <Pager offset={offset} limit={10} count={data.items.length} hasMore={offset + 10 < data.total} loading={busy}
        onPrev={() => { setSelected(null); setOffset((n) => Math.max(0, n - 10)); }}
        onNext={() => { setSelected(null); setOffset((n) => n + 10); }} />
    </>}
    {selected && <div className="mb-3">
      <Callout tone="hint"><strong>{selected.canonical_code} · {selected.topic}</strong>
        <p className="mb-0">{selected.reason}</p>
        {selected.review_note && <p className="mb-0"><strong>Review evidence:</strong> {selected.review_note}</p>}
      </Callout>
      {selected.audit?.version && <details className="mb-2">
        <summary>Correction candidate evidence · {selected.related_report_count || 1} reports</summary>
        <p className="small mb-1">{selected.audit.published_step_count} published steps · {selected.audit.supporting_step_ids?.length || 0} requested-topic links</p>
        <p className="small mb-1">Structural audit: {selected.audit.structural_validation?.status || "Not applicable"} · suggested issue: {selected.audit.suggested_error_kind}</p>
        <Callout tone="warning">Heuristic evidence only. Inspect the source and actual solution; missing signatures are not an automatic rejection.</Callout>
        <pre className="small text-wrap">{JSON.stringify(selected.audit, null, 2)}</pre>
      </details>}
      <button type="button" className="btn btn-outline-secondary btn-sm" onClick={() => setShowEvidence((value) => !value)}>
        {showEvidence ? "Hide source evidence" : "Load original problem and solution evidence"}
      </button>
      {showEvidence && <div className="mt-3"><ProblemDetail code={selected.canonical_code} /></div>}
    </div>}
    {selected?.status === "PENDING" && <form onSubmit={review} className="d-grid gap-2">
      <label>Report decision<select className="form-select" value={decision} onChange={(e) => setDecision(e.target.value)}>
        <option value="RESOLVED">Resolved after review/correction</option><option value="DISMISSED">Dismissed with evidence</option>
      </select></label>
      <label>Review evidence<textarea className="form-control" value={note} minLength={10} maxLength={2000} required onChange={(e) => setNote(e.target.value)} /></label>
      <div className="row g-2">
        <label className="col-md-6">Retrieval relevance<select className="form-select" value={verdict} onChange={(e) => setVerdict(e.target.value)}>
          <option value="UNCLASSIFIED">Not classified</option><option value="IRRELEVANT">Reviewed negative example</option><option value="RELEVANT">Reviewed positive example</option>
        </select></label>
        <label className="col-md-6">Issue type<select className="form-select" value={errorKind} onChange={(e) => setErrorKind(e.target.value)}>
          <option value="UNCLASSIFIED">Not classified</option><option value="METADATA">Annotation mismatch</option><option value="RETRIEVAL">Retrieval mismatch</option><option value="INSUFFICIENT_EVIDENCE">Insufficient evidence</option>
        </select></label>
      </div>
      <button className="btn btn-primary justify-self-start" disabled={busy || note.trim().length < 10}>Save report decision</button>
    </form>}
  </section>;
}
