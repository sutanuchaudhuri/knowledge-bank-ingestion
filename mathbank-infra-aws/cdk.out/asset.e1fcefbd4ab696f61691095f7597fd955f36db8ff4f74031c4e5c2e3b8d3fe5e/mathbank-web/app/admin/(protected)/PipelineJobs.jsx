"use client";

import { useEffect, useState } from "react";
import { Pager } from "../../_components/ui.jsx";
import { PIPELINE_STAGES, formatPipelineTime, pipelineBadgeClass } from "../../../lib/pipelineStatus.mjs";

function Badge({ status }) {
  return <span className={`badge rounded-pill ${pipelineBadgeClass(status)}`}>{status}</span>;
}

export default function PipelineJobs({ refreshToken }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [competition, setCompetition] = useState("");
  const [paper, setPaper] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 10;

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (competition) params.set("competition", competition);
    if (paper) params.set("paper", paper);
    fetch(`/api/rest/admin/pipeline/jobs?${params}`, { signal: controller.signal })
      .then(async (res) => {
        const body = await res.json();
        if (!res.ok) throw new Error(body.error || `status ${res.status}`);
        return body;
      })
      .then((body) => { setData(body); setError(null); })
      .catch((err) => { if (err.name !== "AbortError") setError(err.message); });
    return () => controller.abort();
  }, [refreshToken, competition, paper, offset]);

  return (
    <section className="card border-0 shadow-sm">
      <div className="card-body">
        <h2 className="mb-section-title mb-2"><i className="bi bi-diagram-3" aria-hidden="true" />End-to-end paper jobs</h2>
        <p className="text-secondary small">
          All registered sources and canonical papers. Batch completion does not certify vectors or pedagogy.
          Counts are live inventory, not cumulative write operations. Times are UTC; missing history stays unrecorded.
        </p>
        <div className="row g-3 mb-3">
          <div className="col-md-5">
            <label className="form-label" htmlFor="job-competition">Competition</label>
            <select id="job-competition" className="form-select" value={competition}
              onChange={(e) => { setCompetition(e.target.value); setOffset(0); setData(null); }}>
              <option value="">All competitions</option>
              {data?.competitions?.map((c) => <option key={c.competition_external_code} value={c.competition_external_code}>
                {c.competition_external_code} ({c.papers} papers)
              </option>)}
              {!data && competition && <option value={competition}>{competition}</option>}
            </select>
          </div>
          <div className="col-md-7">
            <label className="form-label" htmlFor="job-paper">Paper code contains</label>
            <input id="job-paper" className="form-control" value={paper}
              onChange={(e) => { setPaper(e.target.value); setOffset(0); setData(null); }} />
          </div>
        </div>
        {error && <div className="alert alert-danger" role="alert">Job observation failed: {error}. Displayed data, if any, is stale.</div>}
        {data?.warnings?.map((warning) => <div className="alert alert-warning" role="alert" key={warning}>{warning}</div>)}
        {!data ? <p role="status">Loading job coverage...</p> : <>
          <div className="d-flex flex-wrap gap-3 align-items-center mb-3">
            <span className="small text-secondary">Observed: {formatPipelineTime(data.observed_at)}</span>
            <span className="small">{data.total} papers in selected scope</span>
            <div className="ms-auto"><Pager offset={offset} limit={limit} count={data.items.length} hasMore={offset + limit < data.total}
              onPrev={() => { setOffset(Math.max(0, offset - limit)); setData(null); }}
              onNext={() => { setOffset(offset + limit); setData(null); }} /></div>
          </div>
          <div className="table-responsive">
            <table className="table table-hover align-middle small">
              <thead><tr><th>Competition / paper</th><th>Overall</th>
                {PIPELINE_STAGES.map(([key, label]) => <th key={key}>{label}</th>)}
                <th>Inventory / evidence</th></tr></thead>
              <tbody>{data.items.map((item) => <tr key={item.paper_external_code}>
                <td style={{ minWidth: 210 }}>
                  <strong>{item.competition_external_code}</strong> {item.year || ""}
                  <div className="text-break">{item.paper_external_code}</div>
                  <details className="mt-2"><summary>Job / timestamps</summary>
                    <div>Source: {item.source_kind || "Untracked legacy source"}</div>
                    <div>Run: {item.run_id || "No paper-batch job recorded"}</div>
                    <div>Attempt: {item.attempt_count ?? "Not recorded"}</div>
                    <div>Started: {formatPipelineTime(item.started_at)}</div>
                    <div>Finished: {formatPipelineTime(item.completed_at)}</div>
                    <div>Heartbeat: {formatPipelineTime(item.heartbeat_at)}</div>
                    <div>Source updated: {formatPipelineTime(item.updated_at)}</div>
                    {Object.entries(item.batch_metrics || {}).filter(([key]) => key.endsWith("_log"))
                      .map(([key, value]) => <div className="text-break" key={key}>{key}: {value}</div>)}
                    {item.jobs?.map((job) => <div className="border-top mt-2 pt-2" key={`${job.run_id}:${job.item_type}`}>
                      <strong>{job.item_type}: {job.status}</strong>
                      <div>Started: {formatPipelineTime(job.started_at)}</div>
                      <div>Finished: {formatPipelineTime(job.completed_at)}</div>
                      {job.metrics?.log && <div className="text-break">{job.metrics.log}</div>}
                      {job.last_error && <div className="text-danger">{job.last_error}</div>}
                    </div>)}
                  </details>
                  {item.errors?.length > 0 && <details className="text-danger mt-2"><summary>Errors ({item.errors.length})</summary>
                    <ul>{item.errors.map((message, index) => <li key={`${item.paper_external_code}:${index}`}>{message}</li>)}</ul>
                  </details>}
                </td>
                <td><Badge status={item.overall_status} /></td>
                {PIPELINE_STAGES.map(([key]) => {
                  const stage = item.stages[key];
                  return <td key={key} style={{ minWidth: 120 }}>
                    <Badge status={stage.status} />
                    {stage.expected != null && <div>{stage.completed}/{stage.expected}</div>}
                    <div className="text-secondary" style={{ fontSize: 11 }}>{formatPipelineTime(stage.recorded_at)}</div>
                    {stage.started_at && <div className="small text-secondary">Start: {formatPipelineTime(stage.started_at)}</div>}
                    {stage.error && <div className="text-danger">{stage.error}</div>}
                  </td>;
                })}
                <td style={{ minWidth: 230 }}>
                  <div>{item.metrics.problems} problems / {item.metrics.solutions} solutions</div>
                  <div>{item.metrics.images} images</div>
                  <div>{item.metrics.embedded_chunks}/{item.metrics.chunks} chunks embedded</div>
                  <div>{item.metrics.graph_corpus_edges ?? "Unknown"} corpus graph edges</div>
                  <div>{item.metrics.graph_skill_edges ?? "Unknown"} reviewed graph skill edges</div>
                  <details className="mt-1"><summary>All metrics</summary>
                    <dl>{Object.entries(item.metrics).map(([key, value]) => <div key={key}>
                      <dt className="fw-normal">{key.replaceAll("_", " ")}</dt><dd>{value ?? "Unknown"}</dd>
                    </div>)}</dl>
                  </details>
                </td>
              </tr>)}</tbody>
            </table>
          </div>
          {data.items.length === 0 && <p>No papers match this scope.</p>}
        </>}
      </div>
    </section>
  );
}
