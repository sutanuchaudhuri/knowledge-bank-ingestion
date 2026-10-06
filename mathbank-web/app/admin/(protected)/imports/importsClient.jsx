"use client";

// Shared client helpers for /api/rest/admin/imports (admin import / reconciliation / DAG review).
import { useCallback, useEffect, useState } from "react";

export const IMPORTS_API = "/api/rest/admin/imports";
export const num = (n) => (n === null || n === undefined ? "—" : Number(n).toLocaleString());
export const human = (s) => (s ? String(s).replaceAll("_", " ").toLowerCase() : "—");
export const when = (t) => (t ? new Date(t).toISOString().replace("T", " ").slice(0, 16) + " UTC" : "—");

export async function importsGet(path, params = {}, signal) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v !== undefined && v !== null));
  const response = await fetch(`${IMPORTS_API}/${path}${qs.size ? `?${qs}` : ""}`, { signal, cache: "no-store" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}

export async function importsAction(action, payload) {
  const response = await fetch(IMPORTS_API, {
    method: "POST", headers: { "Content-Type": "application/json" }, cache: "no-store",
    body: JSON.stringify({ action, ...payload }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}

export function useImports(path, params) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);
  const key = JSON.stringify([path, params, tick]);
  useEffect(() => {
    if (!path) return undefined;
    const ctl = new AbortController();
    setState((s) => ({ ...s, loading: true, error: null }));
    importsGet(path, params, ctl.signal)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((e) => e.name !== "AbortError" && setState({ data: null, error: e.message, loading: false }));
    return () => ctl.abort();
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { ...state, reload };
}

export function Status({ loading, error }) {
  if (error) return <div className="alert alert-danger small">{error}</div>;
  if (loading) return <div className="spinner-border spinner-border-sm text-primary" role="status" aria-label="Loading" />;
  return null;
}

const ITEM_TONE = { APPROVED: "success", REJECTED: "danger", NEEDS_REVISION: "warning", PENDING_REVIEW: "secondary" };

// Human learning-item review (runtime_extension/15 §6): approval_method becomes 'human' and is never
// overwritten by re-import; rejection hides the item from students and prunes it from the graph.
export function ItemReview({ item }) {
  const [state, setState] = useState({ status: item.review_status, method: item.approval_method });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const decide = async (decision) => {
    setBusy(true); setError(null);
    try {
      const r = await importsAction("review-learning-item", { id: item.learning_item_id, decision });
      setState({ status: r.review_status, method: r.approval_method });
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  return (
    <span className="d-inline-flex align-items-center gap-1" data-testid="item-review">
      <span className={`badge text-bg-${ITEM_TONE[state.status] || "secondary"}`}>{state.status}</span>
      {state.method && <span className="text-secondary">{state.method}</span>}
      <button type="button" className="btn btn-sm btn-outline-success py-0" disabled={busy || state.status === "APPROVED"}
        onClick={() => decide("APPROVE")}>Approve</button>
      <button type="button" className="btn btn-sm btn-outline-danger py-0" disabled={busy || state.status === "REJECTED"}
        onClick={() => decide("REJECT")}>Reject</button>
      {error && <span className="text-danger">{error}</span>}
    </span>
  );
}

const DEP_TONE = { NEXT: "secondary", DEPENDS_ON: "primary", ALTERNATIVE_TO: "warning", BRANCHES_TO: "info",
  JOINS_AT: "info", JUSTIFIES: "success", DERIVES_FROM: "primary", USES_RESULT_FROM: "primary" };

// Semantic DAG review (runtime_extension/15 §7): skill/checkpoint edits, dependency type change/reject, approve.
export function DagReview({ code }) {
  const { data, error, loading, reload } = useImports(code ? `problems/${encodeURIComponent(code)}/dag` : null, {});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [draft, setDraft] = useState({ from_step_id: "", to_step_id: "", relationship_type: "DEPENDS_ON" });

  const run = async (action, payload, ok) => {
    setBusy(true); setMessage(null);
    try { await importsAction(action, payload); setMessage({ tone: "success", text: ok }); reload(); }
    catch (e) { setMessage({ tone: "danger", text: e.message }); }
    finally { setBusy(false); }
  };

  if (!data) return <Status loading={loading} error={error} />;
  const label = Object.fromEntries(data.steps.map((s) => [s.solution_step_id, `#${s.global_step_index}`]));
  const live = data.dependencies.filter((d) => d.review_status !== "REJECTED");
  return (
    <div data-testid="dag-review">
      <div className="d-flex flex-wrap align-items-center gap-2 mb-3">
        <span className="small text-secondary">DAG review:</span>
        <span className={`badge text-bg-${data.review?.status === "APPROVED" ? "success" : data.review ? "warning" : "secondary"}`}
          data-testid="dag-review-status">{data.review?.status || "NOT REVIEWED"}</span>
        {data.review && <span className="small text-secondary">{when(data.review.reviewed_at)}</span>}
        <button type="button" className="btn btn-sm btn-success ms-auto" disabled={busy}
          onClick={() => run("review-dag", { code, status: "APPROVED" }, "DAG approved")}>Approve DAG</button>
        <button type="button" className="btn btn-sm btn-outline-warning" disabled={busy}
          onClick={() => run("review-dag", { code, status: "NEEDS_REVISION" }, "Marked needs revision")}>Needs revision</button>
      </div>
      {message && <div className={`alert alert-${message.tone} small py-2`} role="status">{message.text}</div>}

      <h3 className="h6">Steps</h3>
      <div className="table-responsive mb-3">
        <table className="table table-sm align-middle small">
          <thead><tr><th>#</th><th>Step</th><th>Skill</th><th>Checkpoint</th></tr></thead>
          <tbody>
            {data.steps.map((s) => (
              <tr key={s.solution_step_id}>
                <td className="text-nowrap">{s.global_step_index}{s.admin_edited_at && <span className="badge text-bg-info ms-1" title="Admin edited; re-import will not overwrite">edited</span>}</td>
                <td style={{ maxWidth: 520 }}><div className="text-truncate" title={s.step_text}>{s.step_text}</div>
                  <code className="small text-secondary">{s.solution_step_id}</code></td>
                <td className="small">{s.skill_name || "—"}<div className="text-secondary">{s.skill_node_id}</div></td>
                <td>
                  <div className="form-check form-switch m-0">
                    <input className="form-check-input" type="checkbox" role="switch" checked={!!s.is_checkpoint} disabled={busy}
                      aria-label={`Checkpoint ${s.global_step_index}`}
                      onChange={(e) => run("edit-step", { step_id: s.solution_step_id, is_checkpoint: e.target.checked }, "Step updated")} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className="h6">Dependencies <span className="text-secondary small">({live.length} active, {data.dependencies.length - live.length} rejected)</span></h3>
      <div className="table-responsive mb-3">
        <table className="table table-sm align-middle small" data-testid="dag-dependencies">
          <thead><tr><th>From</th><th>Type</th><th>To</th><th>Status</th><th>Change type</th><th /></tr></thead>
          <tbody>
            {data.dependencies.map((d) => (
              <tr key={`${d.from_step_id}|${d.to_step_id}|${d.relationship_type}`} className={d.review_status === "REJECTED" ? "text-decoration-line-through text-secondary" : ""}>
                <td>{label[d.from_step_id] || d.from_step_id}</td>
                <td><span className={`badge text-bg-${DEP_TONE[d.relationship_type] || "secondary"}`}>{d.relationship_type}</span></td>
                <td>{label[d.to_step_id] || d.to_step_id}</td>
                <td>{human(d.review_status)} · {d.approval_method}</td>
                <td>
                  {d.review_status !== "REJECTED" && (
                    <select className="form-select form-select-sm" value={d.relationship_type} disabled={busy}
                      aria-label="Change dependency type"
                      onChange={(e) => run("upsert-dependency", { from_step_id: d.from_step_id, to_step_id: d.to_step_id,
                        relationship_type: e.target.value, previous_type: d.relationship_type }, "Dependency type changed")}>
                      {data.dependency_types.map((t) => <option key={t}>{t}</option>)}
                    </select>
                  )}
                </td>
                <td>{d.review_status !== "REJECTED" && (
                  <button type="button" className="btn btn-sm btn-outline-danger" disabled={busy}
                    onClick={() => run("reject-dependency", { from_step_id: d.from_step_id, to_step_id: d.to_step_id,
                      relationship_type: d.relationship_type }, "Dependency rejected")}>Reject</button>)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <form className="row g-2 align-items-end mb-3" onSubmit={(e) => { e.preventDefault();
        run("upsert-dependency", draft, "Dependency added"); }}>
        <div className="col-sm-4"><label className="form-label small mb-0">From step</label>
          <select className="form-select form-select-sm" required value={draft.from_step_id}
            onChange={(e) => setDraft({ ...draft, from_step_id: e.target.value })}>
            <option value="">choose…</option>
            {data.steps.map((s) => <option key={s.solution_step_id} value={s.solution_step_id}>#{s.global_step_index}</option>)}
          </select></div>
        <div className="col-sm-3"><label className="form-label small mb-0">Type</label>
          <select className="form-select form-select-sm" value={draft.relationship_type}
            onChange={(e) => setDraft({ ...draft, relationship_type: e.target.value })}>
            {data.dependency_types.map((t) => <option key={t}>{t}</option>)}
          </select></div>
        <div className="col-sm-3"><label className="form-label small mb-0">To step</label>
          <select className="form-select form-select-sm" required value={draft.to_step_id}
            onChange={(e) => setDraft({ ...draft, to_step_id: e.target.value })}>
            <option value="">choose…</option>
            {data.steps.map((s) => <option key={s.solution_step_id} value={s.solution_step_id}>#{s.global_step_index}</option>)}
          </select></div>
        <div className="col-sm-2"><button className="btn btn-sm btn-primary w-100" disabled={busy}>Add edge</button></div>
      </form>
      <p className="small text-secondary mb-2">Changes are audited, emit <code>SOLUTION_STEP_CHANGED</code> and queue a graph/embedding
        re-projection. Hard prerequisites use only non-rejected <code>DEPENDS_ON</code>; cycles are refused.</p>

      {data.actions.length > 0 && (
        <details className="small"><summary>Recent admin actions ({data.actions.length})</summary>
          <ul className="list-unstyled mt-2 mb-0">
            {data.actions.map((a) => <li key={a.action_id}><code>{a.action}</code> {a.target_type} · {when(a.created_at)}{a.note ? ` — ${a.note}` : ""}</li>)}
          </ul>
        </details>
      )}
    </div>
  );
}
