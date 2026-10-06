"use client";

import { useEffect, useState } from "react";
import { Bar, SectionTitle, StatCard } from "../../_components/ui.jsx";

const GAP_TONES = { UNRESOLVED: "warning", CONFIRMED: "danger", RESOLVED: "success", REJECTED: "neutral" };
const ENTITY_LABELS = {
  problem: "Problems", solution: "Solutions", solution_step: "Solution steps",
  learning_item: "Transformations", taxonomy_node: "Taxonomy nodes", diagram: "Diagrams",
};

async function getJson(url, signal) {
  const res = await fetch(url, { signal, cache: "no-store" });
  if (!res.ok) throw new Error(`${url} ${res.status}`);
  return res.json();
}

const fmt = (n) => (typeof n === "number" ? n.toLocaleString("en-US") : "—");

/** Analytics row for the admin dashboard; each source loads independently so one failure never blanks the rest. */
export default function AdminOverview({ refreshToken }) {
  const [jobs, setJobs] = useState(null);
  const [coverage, setCoverage] = useState(null);
  const [gaps, setGaps] = useState(null);
  const [convos, setConvos] = useState(null);

  useEffect(() => {
    const ctl = new AbortController();
    const settle = (promise, set) => promise.then(set).catch((e) => { if (e.name !== "AbortError") set({ failed: true }); });
    settle(getJson("/api/rest/admin/pipeline/jobs?limit=1&offset=0", ctl.signal), setJobs);
    settle(getJson("/api/rest/admin/textbooks/coverage", ctl.signal), setCoverage);
    settle(getJson("/api/rest/admin/knowledge-gaps?view=gaps&limit=1", ctl.signal), setGaps);
    settle(getJson("/api/rest/admin/conversations", ctl.signal), setConvos);
    return () => ctl.abort();
  }, [refreshToken]);

  const matrix = coverage?.matrix || [];
  const byEntity = Object.fromEntries(matrix.map((r) => [r.entity, r]));
  const problems = byEntity.problem;
  const problemPct = problems?.source_rows ? (problems.postgres / problems.source_rows) * 100 : null;
  const totals = gaps?.totals || {};
  const gapMax = Math.max(1, ...Object.values(totals).map(Number).filter(Number.isFinite));
  const covered = matrix.filter((r) => ENTITY_LABELS[r.entity]);

  return (
    <section className="mb-4" aria-label="Platform overview" data-testid="admin-overview">
      <div className="row g-3 mb-3">
        <div className="col-6 col-xl-3">
          <StatCard icon="file-earmark-pdf" label="Competition papers" href="#pipeline-jobs"
            value={jobs?.failed ? "—" : fmt(jobs?.total)} hint={jobs?.competitions ? `${jobs.competitions.length} competitions` : "pipeline tracked"} />
        </div>
        <div className="col-6 col-xl-3">
          <StatCard icon="book" tone="info" label="Textbook problems" href="/admin/textbooks"
            value={fmt(problems?.postgres)} progress={problemPct} hint={problems?.source_rows ? `of ${fmt(problems.source_rows)} in source CSVs` : "Prasolov corpus"} />
        </div>
        <div className="col-6 col-xl-3">
          <StatCard icon="exclamation-diamond" tone="warning" label="Open knowledge gaps" href="/admin/knowledge-gaps"
            value={gaps?.failed ? "—" : fmt(Number(totals.UNRESOLVED ?? 0))} hint={`${fmt(Number(totals.RESOLVED ?? 0))} resolved by detours`} />
        </div>
        <div className="col-6 col-xl-3">
          <StatCard icon="people" tone="success" label="Student conversations" href="/admin/conversations"
            value={convos?.failed ? "—" : fmt(convos?.linked?.length)} hint={convos ? `${fmt(convos.unlinked_count)} anonymous sessions` : "linked to students"} />
        </div>
      </div>
      <div className="row g-3">
        <div className="col-12 col-xl-7">
          <div className="card p-3 h-100">
            <SectionTitle icon="bar-chart-steps">Textbook import coverage</SectionTitle>
            {covered.length ? covered.map((r) => (
              <Bar key={r.entity} label={ENTITY_LABELS[r.entity]} value={r.postgres ?? 0}
                max={Math.max(r.source_rows || 0, r.postgres || 0, 1)}
                tone={r.status === "GAP" ? "warning" : r.status === "UNKNOWN" ? "neutral" : "success"} />
            )) : <p className="small text-secondary mb-0">{coverage?.failed ? "Coverage unavailable." : "Loading…"}</p>}
          </div>
        </div>
        <div className="col-12 col-xl-5">
          <div className="card p-3 h-100">
            <SectionTitle icon="activity">Knowledge-gap outcomes</SectionTitle>
            {Object.keys(GAP_TONES).map((s) => (
              <Bar key={s} label={s.toLowerCase()} value={Number(totals[s] ?? 0)} max={gapMax} tone={GAP_TONES[s]} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
