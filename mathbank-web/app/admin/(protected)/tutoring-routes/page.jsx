"use client";

import { useEffect, useState } from "react";
import { Callout, EmptyState, PageHeader, Pill } from "../../../_components/ui.jsx";
import MathText from "../../../_components/MathText.jsx";

const endpoint = "/api/rest/admin/tutoring-routes";
async function request(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `Route request failed (${response.status})`);
  return body;
}

export default function TeachingRoutes() {
  const [queue, setQueue] = useState(null);
  const [detail, setDetail] = useState(null);
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [reviewer, setReviewer] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [publishConfirmed, setPublishConfirmed] = useState(false);
  const [editor, setEditor] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    request(`${endpoint}?limit=25&offset=${offset}`, { signal: controller.signal }).then(setQueue)
      .catch(err => { if (err.name !== "AbortError") setError(err.message); });
    return () => controller.abort();
  }, [offset, refresh]);
  useEffect(() => {
    setDetail(null); setConfirmed(false); setPublishConfirmed(false);
    if (!selected) return undefined;
    const controller = new AbortController();
    request(`${endpoint}?release=${selected}`, { signal: controller.signal })
      .then(data => { setDetail(data); setEditor(JSON.stringify(data.program, null, 2)); })
      .catch(err => { if (err.name !== "AbortError") setError(err.message); });
    return () => controller.abort();
  }, [selected, refresh]);
  async function mutate(action) {
    setBusy(true); setError(""); setNotice("");
    try {
      const payload = action === "edit" ? { program: JSON.parse(editor), expected_hash: detail.release.content_hash }
        : action === "review" ? { reviewer, expected_hash: detail.release.content_hash, mathematical_review_confirmed: confirmed } : {};
      const result = await request(endpoint, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, release: selected, ...payload }) });
      setNotice(action === "refresh-graph" ? `Graph refreshed: ${result.published_releases} published routes; ${result.nodes} metadata nodes.`
        : action === "publish" ? "Published. Refresh the graph separately to verify projection."
          : action === "review" ? "Reviewed; not yet published." : "Draft saved; review is still required.");
      setRefresh(value => value + 1);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <>
    <PageHeader icon="list-check" title="Teaching routes" subtitle="Review source-grounded drafts before students can use them."
      pills={<Pill tone="warning">No automatic publication</Pill>}
      actions={<button className="btn btn-outline-primary" disabled={busy} onClick={() => mutate("refresh-graph")}>Refresh graph</button>} />
    {error && <Callout tone="danger" role="alert">{error}</Callout>}
    {notice && <Callout tone="success" role="status">{notice}</Callout>}
    <div className="row g-4">
      <section className="col-lg-4">
        <div className="list-group" aria-label="Teaching route releases">
          {queue?.releases.map(row => <button key={row.route_release_id}
            className={`list-group-item list-group-item-action ${selected === row.route_release_id ? "active" : ""}`}
            disabled={busy} onClick={() => setSelected(row.route_release_id)}>
            <strong className="d-block">{row.canonical_code}</strong>
            <span>{row.approach_name}</span>
            <div className="mt-2"><Pill tone={row.status === "PUBLISHED" ? "success" : "warning"}>{row.status}</Pill>
              <span className="small ms-2">{row.steps} checkpoints · v{row.release_version}</span></div>
          </button>)}
        </div>
        {queue?.total === 0 && <EmptyState>No compiled routes yet.</EmptyState>}
        <div className="d-flex gap-2 align-items-center mt-3">
          <button className="btn btn-ghost" disabled={busy || offset === 0} onClick={() => setOffset(value => value - 25)}>Previous</button>
          <span className="small mb-num">{queue ? `${Math.min(offset + 1, queue.total)}–${Math.min(offset + 25, queue.total)} / ${queue.total}` : "Loading…"}</span>
          <button className="btn btn-ghost" disabled={busy || !queue || offset + 25 >= queue.total} onClick={() => setOffset(value => value + 25)}>Next</button>
        </div>
      </section>
      <section className="col-lg-8">
        {!detail ? <EmptyState>Select a release to inspect its source and checkpoints.</EmptyState> : <>
          <Callout tone="warning">Structural validation is not proof verification. Inspect every mathematical step, hint and diagnostic before attesting.</Callout>
          <details className="card p-3 mb-3"><summary>Canonical statement and stored solution · {detail.source.verification_status}</summary>
            <MathText className="mt-3">{detail.source.statement_text}</MathText><hr /><MathText>{detail.source.solution}</MathText>
          </details>
          {detail.program.steps.map((step, index) => <details key={index} className="card p-3 mb-3" open={index === 0}>
            <summary>Checkpoint {index + 1} · {step.instruction.goal_text}</summary>
            <div className="mt-3"><MathText>{step.instruction.student_prompt}</MathText>
              <Callout tone="insight" title="Current-step explanation"><MathText>{step.instruction.full_explanation}</MathText></Callout>
              <ol>{step.hints.map((hint, level) => <li key={level}><MathText>{hint}</MathText></li>)}</ol>
              <details><summary>All instructional fields, requirements and source excerpt</summary><pre className="text-wrap small">{JSON.stringify(step, null, 2)}</pre></details>
            </div>
          </details>)}
          <details className="card p-3 mb-3"><summary>Claims, misconceptions, theory and diagnostics</summary>
            <pre className="text-wrap small">{JSON.stringify(detail.program.assets, null, 2)}</pre></details>
          {detail.release.status === "DRAFT" && <>
            <details className="card p-3 mb-3"><summary>Edit complete draft program</summary>
              <label htmlFor="route-json" className="form-label mt-3">Program JSON</label>
              <textarea id="route-json" className="form-control font-monospace" rows={18} value={editor} onChange={event => setEditor(event.target.value)} disabled={busy} />
              <button className="btn btn-outline-primary mt-3" disabled={busy} onClick={() => mutate("edit")}>Save draft</button>
            </details>
            <label className="form-label" htmlFor="route-reviewer">Reviewer name</label>
            <input id="route-reviewer" className="form-control mb-3" value={reviewer} disabled={busy} onChange={event => setReviewer(event.target.value)} />
            <label className="form-check mb-3"><input className="form-check-input" type="checkbox" checked={confirmed}
              onChange={event => setConfirmed(event.target.checked)} disabled={busy} />
              <span className="form-check-label">I reviewed the mathematics, source fidelity and spoiler boundaries.</span></label>
            <button className="btn btn-primary" disabled={busy || !confirmed || reviewer.trim().length < 3} onClick={() => mutate("review")}>Mark reviewed</button>
          </>}
          {detail.release.status === "REVIEWED" && <>
            <label className="form-check mb-3"><input className="form-check-input" type="checkbox" checked={publishConfirmed}
              onChange={event => setPublishConfirmed(event.target.checked)} disabled={busy} />
              <span className="form-check-label">Make this reviewed route available to new student sessions.</span></label>
            <button className="btn btn-primary" disabled={busy || !publishConfirmed} onClick={() => mutate("publish")}>Publish reviewed route</button>
          </>}
        </>}
      </section>
    </div>
  </>;
}
