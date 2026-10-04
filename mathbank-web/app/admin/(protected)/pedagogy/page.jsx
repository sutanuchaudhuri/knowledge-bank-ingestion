"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import MathText from "../../../_components/MathText.jsx";
import ProblemDetail from "../../../db/ProblemDetail.jsx";

const KINDS = [
  ["skill", "Skills"],
  ["skill_concept", "Skill-to-concept links"],
  ["skill_relation", "Skill prerequisites and relations"],
  ["problem_skill", "Problem-to-skill mappings"],
  ["problem_pedagogy", "Difficulty assessments"],
];
const PAGE_SIZE = 25;
const endpoint = "/api/rest/admin/pedagogy";

async function request(body, signal) {
  const response = await fetch(endpoint, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body), signal,
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
  return result;
}

function Badge({ status }) {
  return <span className={`badge text-bg-${status === "REVIEWED" ? "success" : status === "REJECTED" ? "danger" : "warning"}`}>{status}</span>;
}

export default function PedagogyReviewPage() {
  const [kind, setKind] = useState("skill");
  const [status, setStatus] = useState("PENDING");
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [note, setNote] = useState("");
  const [attested, setAttested] = useState(false);
  const [history, setHistory] = useState(null);
  const [historyError, setHistoryError] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const [publishConfirm, setPublishConfirm] = useState(false);
  const [checked, setChecked] = useState([]);
  const [bulkNote, setBulkNote] = useState("");
  const [bulkConfirmed, setBulkConfirmed] = useState(false);
  const [showSolutionEvidence, setShowSolutionEvidence] = useState(false);
  const inFlight = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setSelected(null);
    setError(null);
    setPublishConfirm(false);
    setChecked([]);
    setBulkConfirmed(false);
    fetch(`${endpoint}?kind=${kind}&status=${status}&limit=${PAGE_SIZE}&offset=${offset}`, { signal: controller.signal })
      .then(async response => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.error || `Queue failed (${response.status})`);
        return body;
      })
      .then(setData)
      .catch(err => { if (err.name !== "AbortError") setError(err.message); });
    return () => controller.abort();
  }, [kind, status, offset, reload]);

  useEffect(() => {
    setNote("");
    setAttested(false);
    setHistory(null);
    setHistoryError(null);
    setShowSolutionEvidence(false);
    if (!selected) return undefined;
    const controller = new AbortController();
    request({ action: "history", kind, key: selected.key }, controller.signal)
      .then(result => setHistory(result.events))
      .catch(err => { if (err.name !== "AbortError") setHistoryError(err.message); });
    return () => controller.abort();
  }, [selected, kind]);

  async function review(nextStatus) {
    if (inFlight.current || !selected || note.trim().length < 10 ||
        (nextStatus === "REVIEWED" && !attested)) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await request({
        action: "review", kind, key: selected.key, expected_revision: selected.revision,
        review_status: nextStatus, note: note.trim(),
      });
      setNotice(result.message);
      setReload(value => value + 1);
    } catch (err) {
      setError(err.message);
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  async function publish() {
    if (inFlight.current || !publishConfirm || !data) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await request({
        action: "publish", expected_fingerprint: data.source_fingerprint,
      });
      setNotice(result.message);
      setReload(value => value + 1);
    } catch (err) {
      setError(err.message);
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  async function bulkReview(nextStatus, starter = false) {
    if (inFlight.current || !bulkConfirmed || bulkNote.trim().length < 10 ||
        !data || (!starter && !checked.length)) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const payload = starter ? {
        action: "approve-starter", expected_fingerprint: data.source_fingerprint,
        note: bulkNote.trim(),
      } : {
        action: "bulk-review", review_status: nextStatus, note: bulkNote.trim(),
        items: data.items.filter(item => checked.includes(JSON.stringify(item.key))).map(item => ({
          kind, key: item.key, expected_revision: item.revision,
        })),
      };
      const result = await request(payload);
      setNotice(result.message);
      setBulkNote("");
      setReload(value => value + 1);
    } catch (err) {
      setError(err.message);
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  return (
    <div>
      <header className="d-flex flex-wrap justify-content-between align-items-start gap-3 mb-4">
        <div>
          <span className="badge text-bg-primary mb-2">Human review</span>
          <h1 className="h3 fw-bold">Pedagogical metadata approval</h1>
          <p className="text-secondary mb-0">Inspect evidence, record a decision in Postgres, then explicitly publish to the teaching graph.</p>
        </div>
        <Link href="/admin" className="btn btn-outline-secondary">Ingestion admin</Link>
      </header>
      <div className="alert alert-info">
        Approve skills first, then their mappings and relations. Approval records your review of the displayed assertion, not automatic approval of related rows.
        Generated content and confidence are not expert validation. Publishing preserves each row&apos;s status; it never approves pending rows.
      </div>
      {error && <div role="alert" className="alert alert-danger">{error}</div>}
      {notice && <div role="status" className="alert alert-success">{notice}</div>}
      <section className="card border-0 shadow-sm mb-4">
        <div className="card-body">
          <h2 className="h5">Bulk review</h2>
          <p className="small text-secondary">Select assertions in the queue for one atomic decision, or approve all pending rows in the versioned counting starter manifest.
            The starter action includes skills and dependent links in dependency order, not the 65 legacy concept-hierarchy assertions or other corpus tags.</p>
          {data?.starter_warning && <p role="status" className="text-warning-emphasis">{data.starter_warning}</p>}
          <label htmlFor="bulk-note" className="form-label">Bulk review rationale (10-2,000 characters)</label>
          <textarea id="bulk-note" className="form-control mb-3" rows={2} maxLength={2000} value={bulkNote} disabled={busy}
            onChange={event => setBulkNote(event.target.value)} />
          <label className="form-check mb-3">
            <input className="form-check-input" type="checkbox" checked={bulkConfirmed} disabled={busy}
              onChange={event => setBulkConfirmed(event.target.checked)} />
            <span className="form-check-label">I authorize the displayed bulk scope and have reviewed the evidence appropriate to my decision.</span>
          </label>
          <div className="d-flex flex-wrap gap-2">
            <button className="btn btn-success" onClick={() => bulkReview("REVIEWED")}
              disabled={busy || !checked.length || !bulkConfirmed || bulkNote.trim().length < 10}>Approve selected ({checked.length})</button>
            <button className="btn btn-outline-danger" onClick={() => bulkReview("REJECTED")}
              disabled={busy || !checked.length || !bulkConfirmed || bulkNote.trim().length < 10}>Reject selected ({checked.length})</button>
            <button className="btn btn-outline-primary" onClick={() => bulkReview("REVIEWED", true)}
              disabled={busy || !data?.starter_pending || !bulkConfirmed || bulkNote.trim().length < 10}>
              Approve pending starter set ({data?.starter_pending ?? 0})
            </button>
          </div>
          <p className="small text-secondary mt-2 mb-0">Each affected assertion gets its own immutable before/after audit event. Nothing is published automatically.</p>
        </div>
      </section>
      <section className="card border-0 shadow-sm mb-4">
        <div className="card-body">
          <h2 className="h5">Graph publication</h2>
          {data ? <>
            <p className={data.needs_publish ? "text-warning-emphasis" : "text-success"}>
              {data.needs_publish ? "Postgres metadata needs publication or has no recorded admin publication." : "Postgres matches the last recorded admin publication."}
            </p>
            <p className="small text-secondary">Until publish succeeds, tutoring uses the previous Neo4j snapshot. A rejected assertion can remain active there until you publish. Other server instances may cache graph views for up to five minutes.</p>
            <p className="small">Last recorded publication: {data.last_publication?.published_at || "None"}.
              {" "}Publisher identity is the shared admin credential, not a named individual.</p>
            <label className="form-check mb-3">
              <input className="form-check-input" type="checkbox" checked={publishConfirm} disabled={busy}
                onChange={event => setPublishConfirm(event.target.checked)} />
              <span className="form-check-label">I intend to publish the current Postgres review decisions to Neo4j.</span>
            </label>
            <button className="btn btn-primary" onClick={publish} disabled={!publishConfirm || busy}>
              {busy ? "Working..." : "Publish metadata to graph"}
            </button>
          </> : <p>Load the review queue to check publication status.</p>}
        </div>
      </section>
      <div className="row g-4">
        <section className="col-12 col-xl-5">
          <div className="card border-0 shadow-sm">
            <div className="card-body">
              <h2 className="h5">Review queue</h2>
              <div className="row g-2 mb-3">
                <div className="col-sm-7">
                  <label htmlFor="metadata-kind" className="form-label">Metadata type</label>
                  <select id="metadata-kind" className="form-select" value={kind} disabled={busy}
                    onChange={event => { setKind(event.target.value); setOffset(0); }}>
                    {KINDS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </div>
                <div className="col-sm-5">
                  <label htmlFor="review-status" className="form-label">Review status</label>
                  <select id="review-status" className="form-select" value={status} disabled={busy}
                    onChange={event => { setStatus(event.target.value); setOffset(0); }}>
                    {["PENDING", "REVIEWED", "REJECTED", "ALL"].map(value => <option key={value}>{value}</option>)}
                  </select>
                </div>
              </div>
              <button className="btn btn-sm btn-outline-secondary mb-3" disabled={busy} onClick={() => setReload(value => value + 1)}>Reload queue</button>
              {data && <p className="small text-secondary">
                This type: {data.counts[kind]?.PENDING || 0} pending · {data.counts[kind]?.REVIEWED || 0} reviewed · {data.counts[kind]?.REJECTED || 0} rejected
              </p>}
              {!data && !error && <p role="status">Loading metadata...</p>}
              {data && <label className="form-check mb-3">
                <input className="form-check-input" type="checkbox" disabled={busy || !data.items.length}
                  checked={data.items.length > 0 && checked.length === data.items.length}
                  onChange={event => setChecked(event.target.checked ? data.items.map(item => JSON.stringify(item.key)) : [])} />
                <span className="form-check-label">Select all assertions on this page</span>
              </label>}
              {data?.items.map(item => <div key={JSON.stringify(item.key)} className="d-flex align-items-start gap-2 mb-2">
                <input type="checkbox" className="form-check-input mt-3 flex-shrink-0" aria-label={`Select ${item.title}`} disabled={busy}
                  checked={checked.includes(JSON.stringify(item.key))}
                  onChange={event => setChecked(values => event.target.checked
                    ? [...values, JSON.stringify(item.key)] : values.filter(value => value !== JSON.stringify(item.key)))} />
                <button type="button" disabled={busy}
                className={`w-100 text-start btn ${selected?.revision === item.revision ? "btn-light border-primary" : "btn-light"} border mb-2 p-3`}
                onClick={() => { setSelected(item); setError(null); }}>
                <div className="d-flex flex-wrap justify-content-between gap-2"><strong>{item.title}</strong><Badge status={item.metadata.review_status} /></div>
                <span className="small text-secondary text-break">{item.metadata.source}</span>
              </button></div>)}
              {data && !data.items.length && <p>No assertions match this filter.</p>}
              {data && <div className="d-flex align-items-center justify-content-between mt-3">
                <button className="btn btn-sm btn-outline-primary" disabled={!offset || busy} onClick={() => setOffset(value => Math.max(0, value - PAGE_SIZE))}>Previous</button>
                <span className="small">{data.total ? offset + 1 : 0}-{Math.min(offset + PAGE_SIZE, data.total)} of {data.total}</span>
                <button className="btn btn-sm btn-outline-primary" disabled={offset + PAGE_SIZE >= data.total || busy} onClick={() => setOffset(value => value + PAGE_SIZE)}>Next</button>
              </div>}
            </div>
          </div>
        </section>
        <section className="col-12 col-xl-7">
          <div className="card border-0 shadow-sm">
            <div className="card-body">
              <h2 className="h5">Assertion and evidence</h2>
              {!selected ? <p className="text-secondary">Select an assertion to inspect its objective, source, confidence, dimensions, and problem context.</p> : <>
                <h3 className="h6 fw-bold">{selected.title}</h3>
                <Badge status={selected.metadata.review_status} />
                <div className="border rounded p-3 my-3"><MathText>{selected.context || "No context available."}</MathText></div>
                {selected.objective && <p><strong>Skill objective:</strong> {selected.objective}</p>}
                {selected.problem_code && <div className="mb-3">
                  <button className="btn btn-sm btn-outline-secondary" disabled={busy}
                    onClick={() => setShowSolutionEvidence(value => !value)}>
                    {showSolutionEvidence ? "Hide solution evidence" : "Load official answer and solutions for review"}
                  </button>
                  {showSolutionEvidence && <div className="mt-3"><ProblemDetail code={selected.problem_code} /></div>}
                </div>}
                <dl className="row small">
                  {Object.entries(selected.metadata).map(([field, value]) => <div className="col-12 mb-2" key={field}>
                    <dt>{field}</dt><dd className="text-break mb-0">{value === null ? "Not assessed" : String(value)}</dd>
                  </div>)}
                </dl>
                <label htmlFor="review-note" className="form-label">Review rationale (required, 10-2,000 characters)</label>
                <textarea id="review-note" className="form-control mb-3" rows={3} maxLength={2000}
                  disabled={busy} value={note} onChange={event => setNote(event.target.value)} />
                <label className="form-check mb-3">
                  <input className="form-check-input" type="checkbox" checked={attested} disabled={busy}
                    onChange={event => setAttested(event.target.checked)} />
                  <span className="form-check-label">I reviewed this assertion and its source/context for pedagogical correctness.</span>
                </label>
                <div className="d-flex flex-wrap gap-2">
                  <button className="btn btn-success" onClick={() => review("REVIEWED")}
                    disabled={busy || !attested || note.trim().length < 10 || selected.metadata.review_status === "REVIEWED"}>Approve assertion</button>
                  <button className="btn btn-outline-danger" onClick={() => review("REJECTED")}
                    disabled={busy || note.trim().length < 10 || selected.metadata.review_status === "REJECTED"}>Reject assertion</button>
                  <button className="btn btn-outline-secondary" onClick={() => review("PENDING")}
                    disabled={busy || note.trim().length < 10 || selected.metadata.review_status === "PENDING"}>Return to pending</button>
                </div>
                <p className="small text-secondary mt-3">The decision and before/after snapshots are stored in Postgres. Concurrent changes require reloading; prerequisite and hierarchy cycles are rejected.</p>
                <h3 className="h6 mt-4">Review history</h3>
                {historyError && <p role="alert" className="text-danger">{historyError}</p>}
                {!history && !historyError && <p>Loading history...</p>}
                {history?.length === 0 && <p className="small text-secondary">No recorded admin decisions yet.</p>}
                {history?.map(event => <div key={event.review_event_id} className="border rounded p-3 mb-2 small">
                  <p className="mb-1">{event.before_snapshot.review_status} → {event.after_snapshot.review_status} · {event.reviewed_at}</p>
                  <p className="mb-1 text-break">{event.review_note}</p>
                  <span className="text-secondary">{event.reviewer}</span>
                </div>)}
              </>}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
