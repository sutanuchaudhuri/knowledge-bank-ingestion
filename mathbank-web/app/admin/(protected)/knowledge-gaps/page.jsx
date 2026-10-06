"use client";

import { IconButton, PageHeader, Pill } from "../../../_components/ui.jsx";

import { useEffect, useState } from "react";

const endpoint = "/api/rest/admin/knowledge-gaps";
const GAP_STATUSES = ["UNRESOLVED", "CONFIRMED", "RESOLVED", "REJECTED"];
const PLAN_STATUSES = ["ACTIVE", "SUSPENDED", "COMPLETED", "EXHAUSTED", "ABORTED", "SUPERSEDED"];
const TONES = {
  UNRESOLVED: "secondary", CONFIRMED: "danger", RESOLVED: "success", REJECTED: "light",
  ACTIVE: "primary", SUSPENDED: "secondary", COMPLETED: "success", EXHAUSTED: "warning", ABORTED: "light", SUPERSEDED: "light",
  PASSED: "success", FAILED: "danger", PRESENTED: "primary", PENDING: "light", SKIPPED: "light",
};

async function load(params, signal) {
  const response = await fetch(`${endpoint}?${new URLSearchParams(params)}`, { signal, cache: "no-store" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}

const when = (ts) => (ts ? new Date(ts).toLocaleString() : "—");
const human = (s) => (s ? String(s).replaceAll("_", " ").toLowerCase() : "—");

function StatusBadge({ status }) {
  return <span className={`badge text-bg-${TONES[status] || "secondary"}${TONES[status] === "light" ? " border" : ""}`}>{status || "—"}</span>;
}

function PlanDetail({ id, onClose }) {
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    const ctl = new AbortController();
    setPlan(null); setError(null);
    load({ view: "plan", id }, ctl.signal).then(setPlan).catch((e) => e.name !== "AbortError" && setError(e.message));
    return () => ctl.abort();
  }, [id]);
  return (
    <div className="card shadow-sm border-0 mb-4">
      <div className="card-header bg-white d-flex align-items-center gap-2">
        <span className="fw-semibold">Recovery plan</span>
        {plan && <StatusBadge status={plan.status} />}
        {plan && <span className="small text-secondary">{plan.target_label} · {human(plan.trigger)}</span>}
        <button type="button" className="btn-close ms-auto" aria-label="Close" onClick={onClose} />
      </div>
      <div className="card-body">
        {error && <div className="alert alert-danger">{error}</div>}
        {!plan && !error && <div className="spinner-border spinner-border-sm" role="status" />}
        {plan && (
          <>
            <div className="row g-3 small mb-3">
              <div className="col-md-3"><div className="text-secondary">Origin</div>{plan.origin?.problem_code} · part {plan.origin?.part_label} step {plan.origin?.step_index_in_part}</div>
              <div className="col-md-3"><div className="text-secondary">Mastery</div>{plan.mastery?.independent_successes}/{plan.mastery?.independent_successes_required} first-try · transfer {plan.mastery?.transfer_passed ? "passed" : "not passed"}</div>
              <div className="col-md-3"><div className="text-secondary">Opened / ended</div>{when(plan.created_at)} → {when(plan.ended_at)}</div>
              <div className="col-md-3"><div className="text-secondary">Outcome</div>{plan.ended_at ? human(plan.status) : "in progress"}{plan.mastery?.met ? " · mastery goal met" : ""}</div>
            </div>
            {plan.parent_target_label && <div className="alert alert-info py-2 small">Building-block branch of “{plan.parent_target_label}”.</div>}
            <div className="table-responsive">
              <table className="table table-sm align-middle small">
                <thead><tr><th>#</th><th>Stage</th><th>Kind</th><th>Type</th><th>Status</th><th>Tries</th><th>First try</th><th>Last response</th><th>Feedback</th><th>Added</th></tr></thead>
                <tbody>
                  {plan.items_teacher.map((i) => (
                    <tr key={i.ordinal}>
                      <td>{i.ordinal}</td><td>{human(i.stage)}</td><td>{human(i.item_kind)}</td>
                      <td>{human(i.transformation_type)}</td><td><StatusBadge status={i.status} /></td><td>{i.tries}</td>
                      <td>{i.independent_success == null ? "—" : i.independent_success ? "✓" : "✗"}</td>
                      <td className="text-truncate" style={{ maxWidth: 260 }} title={JSON.stringify(i.last_response || "")}>
                        {i.last_response ? (i.last_response.response_text ?? (i.last_response.choice_index != null ? `choice ${i.last_response.choice_index + 1}` : i.last_response.acknowledged ? "acknowledged" : "—")) : "—"}
                      </td>
                      <td className="text-truncate" style={{ maxWidth: 260 }} title={i.last_result?.feedback || ""}>{i.last_result?.feedback || i.last_result?.verdict || "—"}</td>
                      <td>{human(i.added_reason)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function KnowledgeGapsPage() {
  const [gapStatus, setGapStatus] = useState("");
  const [student, setStudent] = useState("");
  const [query, setQuery] = useState("");
  const [planStatus, setPlanStatus] = useState("");
  const [gaps, setGaps] = useState(null);
  const [plans, setPlans] = useState(null);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const ctl = new AbortController();
    setError(null);
    load({ view: "gaps", limit: 200, ...(gapStatus ? { status: gapStatus } : {}), ...(query ? { student: query } : {}) }, ctl.signal)
      .then(setGaps).catch((e) => e.name !== "AbortError" && setError(e.message));
    return () => ctl.abort();
  }, [gapStatus, query, tick]);

  useEffect(() => {
    const ctl = new AbortController();
    load({ view: "plans", limit: 200, ...(planStatus ? { status: planStatus } : {}) }, ctl.signal)
      .then(setPlans).catch((e) => e.name !== "AbortError" && setError(e.message));
    return () => ctl.abort();
  }, [planStatus, tick]);

  const totals = gaps?.totals || {};
  return (
    <div>
      <PageHeader icon="exclamation-diamond" tone="warning" title="Knowledge gaps & recovery"
        subtitle="Ranked gap hypotheses from step diagnosis and the recovery detours they triggered."
        pills={<Pill tone="neutral" icon="eye" title="A gap is RESOLVED only by a completed detour and CONFIRMED by an exhausted one; mastery is never written here.">Read-only</Pill>}
        actions={<IconButton icon="arrow-clockwise" label="Refresh" variant="outline-secondary" onClick={() => setTick((t) => t + 1)} />} />
      {error && <div className="alert alert-danger">{error}</div>}

      <div className="row g-3 mb-4">
        {GAP_STATUSES.map((s) => (
          <div className="col-6 col-lg-3" key={s}>
            <button type="button" onClick={() => setGapStatus(gapStatus === s ? "" : s)}
              className={`card w-100 text-start shadow-sm border-0 border-start border-4 border-${TONES[s] === "light" ? "secondary" : TONES[s]}${gapStatus === s ? " bg-light" : ""}`}>
              <div className="card-body py-2">
                <div className="small text-secondary">{s}</div>
                <div className="fs-4 fw-semibold">{totals[s] ?? 0}</div>
              </div>
            </button>
          </div>
        ))}
      </div>

      <div className="row g-4">
        <div className="col-xl-8">
          <div className="card shadow-sm border-0">
            <div className="card-header bg-white d-flex flex-wrap gap-2 align-items-center">
              <span className="fw-semibold">Gap hypotheses</span>
              <select className="form-select form-select-sm w-auto ms-auto" value={gapStatus} onChange={(e) => setGapStatus(e.target.value)} aria-label="Gap status">
                <option value="">All statuses</option>
                {GAP_STATUSES.map((s) => <option key={s}>{s}</option>)}
              </select>
              <form className="d-flex gap-1" onSubmit={(e) => { e.preventDefault(); setQuery(student.trim()); }}>
                <input className="form-control form-control-sm" placeholder="Student e-mail" value={student} onChange={(e) => setStudent(e.target.value)} />
                <button className="btn btn-sm btn-outline-primary" type="submit">Search</button>
              </form>
            </div>
            <div className="table-responsive">
              <table className="table table-hover table-sm align-middle small mb-0">
                <thead className="table-light"><tr>
                  <th>When</th><th>Student</th><th>Problem</th><th>#</th><th>Target</th><th>Where / how</th><th>Conf.</th><th>Status</th><th>Detour</th>
                </tr></thead>
                <tbody>
                  {!gaps && <tr><td colSpan={9} className="text-center py-3"><span className="spinner-border spinner-border-sm" /></td></tr>}
                  {gaps?.gaps?.length === 0 && <tr><td colSpan={9} className="text-center text-secondary py-3">No gaps match.</td></tr>}
                  {gaps?.gaps?.map((g) => (
                    <tr key={g.knowledge_gap_id}>
                      <td className="text-nowrap">{when(g.created_at)}</td>
                      <td>{g.email}</td>
                      <td>{g.problem_code}</td>
                      <td>{g.rank}</td>
                      <td>{g.target_label}{g.ai_reranked && <span className="badge text-bg-light border ms-1">AI-ranked</span>}</td>
                      <td>{human(g.failure_location)} · {human(g.failure_mode)}</td>
                      <td>{g.confidence != null ? Number(g.confidence).toFixed(2) : "—"}</td>
                      <td><StatusBadge status={g.status} />{g.status_reason && <div className="text-secondary">{human(g.status_reason)}</div>}</td>
                      <td>{g.recovery_plan_id
                        ? <button type="button" className="btn btn-link btn-sm p-0" onClick={() => setSelected(g.recovery_plan_id)}><StatusBadge status={g.recovery_status} /></button>
                        : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <div className="col-xl-4">
          <div className="card shadow-sm border-0">
            <div className="card-header bg-white fw-semibold">Most common open gaps</div>
            <ul className="list-group list-group-flush small">
              {(gaps?.top_open_targets || []).length === 0 && <li className="list-group-item text-secondary">None open.</li>}
              {(gaps?.top_open_targets || []).map((t) => (
                <li key={t.target_id || t.target_label} className="list-group-item d-flex justify-content-between">
                  <span>{t.target_label}</span>
                  <span className="text-secondary">{t.open_gaps} gaps · {t.students} students</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <div className="mt-4">
        {selected && <PlanDetail id={selected} onClose={() => setSelected(null)} />}
        <div className="card shadow-sm border-0">
          <div className="card-header bg-white d-flex align-items-center gap-2">
            <span className="fw-semibold">Recovery detours</span>
            <select className="form-select form-select-sm w-auto ms-auto" value={planStatus} onChange={(e) => setPlanStatus(e.target.value)} aria-label="Plan status">
              <option value="">All statuses</option>
              {PLAN_STATUSES.map((s) => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div className="table-responsive">
            <table className="table table-hover table-sm align-middle small mb-0">
              <thead className="table-light"><tr>
                <th>Opened</th><th>Student</th><th>Problem</th><th>Target</th><th>Trigger</th><th>Status</th><th>Items</th><th>Passed / failed</th><th>Adapted</th><th>Ended</th><th />
              </tr></thead>
              <tbody>
                {!plans && <tr><td colSpan={11} className="text-center py-3"><span className="spinner-border spinner-border-sm" /></td></tr>}
                {plans?.length === 0 && <tr><td colSpan={11} className="text-center text-secondary py-3">No detours yet.</td></tr>}
                {(Array.isArray(plans) ? plans : plans?.plans || []).map((p) => (
                  <tr key={p.recovery_plan_id} className={selected === p.recovery_plan_id ? "table-active" : ""}>
                    <td className="text-nowrap">{when(p.created_at)}</td><td>{p.email}</td><td>{p.problem_code}</td>
                    <td>{p.target_label}{p.parent_recovery_plan_id && <span className="badge text-bg-warning ms-1">branch</span>}</td>
                    <td>{human(p.trigger)}</td><td><StatusBadge status={p.status} /></td><td>{p.items}</td>
                    <td>{p.passed} / {p.failed}</td><td>{p.adapted}</td><td className="text-nowrap">{when(p.ended_at)}</td>
                    <td><button type="button" className="btn btn-sm btn-outline-primary" onClick={() => setSelected(p.recovery_plan_id)}>Details</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
