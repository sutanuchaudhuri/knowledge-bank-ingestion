"use client";

import { Callout, EmptyState, IconButton, PageHeader, Pill } from "../../../_components/ui.jsx";

import { useCallback, useEffect, useState } from "react";

const API = "/api/rest/admin/manim-studio";

async function call(path, options) {
  const response = await fetch(`${API}${path}`, { cache: "no-store", ...options });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}

const STATUS_TONE = { DRAFT: "warning", APPROVED: "success", SUPERSEDED: "neutral" };
const when = (ts) => (ts ? new Date(ts).toLocaleString() : "—");

function PromoteForm({ candidate, onPromoted }) {
  const [canonicalCode, setCanonicalCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function promote() {
    if (!canonicalCode.trim()) {
      setError("A canonical code is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await call("/scenes/promote", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ render_job_id: candidate.id, canonical_code: canonicalCode.trim() }),
      });
      onPromoted();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="d-flex gap-2 align-items-center mt-2">
      <input
        className="form-control form-control-sm"
        style={{ maxWidth: 260 }}
        placeholder="Canonical code, e.g. JENSEN_CONVEXITY_V1"
        value={canonicalCode}
        onChange={(e) => setCanonicalCode(e.target.value)}
      />
      <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={promote}>
        {busy ? "Promoting…" : "Promote to catalog"}
      </button>
      {error && <span className="small text-danger">{error}</span>}
    </div>
  );
}

function CandidateCard({ candidate, onPromoted }) {
  const objectCount = candidate.scene_spec_json?.objects?.length ?? 0;
  const timelineCount = candidate.scene_spec_json?.timeline?.length ?? 0;
  return (
    <div className="card shadow-sm border-0 mb-3">
      <div className="card-body">
        <div className="d-flex justify-content-between align-items-start">
          <div>
            <div className="fw-semibold">{candidate.scene_spec_json?.scene_key || "Untitled scene"}</div>
            <div className="small text-secondary">Created {when(candidate.created_at)} · expires {when(candidate.expires_at)}</div>
          </div>
          <Pill tone="info">{candidate.video_duration_ms ? `${(candidate.video_duration_ms / 1000).toFixed(1)}s video` : "DONE"}</Pill>
        </div>
        <div className="small text-secondary mt-1">{objectCount} object(s), {timelineCount} timeline step(s) — review the full rendered video after promoting, from the catalog panel on the right.</div>
        <PromoteForm candidate={candidate} onPromoted={onPromoted} />
      </div>
    </div>
  );
}

function SceneDetail({ scene, onValidated, onApproved }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);

  async function run(action, handler) {
    setBusy(true);
    setMessage(null);
    try {
      const result = await call(`/scenes/${scene.scene_spec_id}/${action}`, { method: "POST" });
      setMessage(result);
      handler();
    } catch (err) {
      setMessage({ status: "ERROR", errors: [err.message] });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card shadow-sm border-0">
      <div className="card-header bg-white d-flex align-items-center gap-2">
        <span className="fw-semibold">{scene.canonical_code}</span>
        <Pill tone={STATUS_TONE[scene.status] || "neutral"}>{scene.status}</Pill>
        <span className="small text-secondary ms-auto">v{scene.version}</span>
      </div>
      <div className="card-body">
        {scene.rendered_video_asset_id && (
          <video className="w-100 rounded mb-3" style={{ maxHeight: 320, background: "#000" }} controls
                 src={`${API}/scenes/${scene.scene_spec_id}/video`} />
        )}
        <div className="small text-secondary mb-2">
          Created by {scene.created_by} on {when(scene.created_at)}
          {scene.approved_by && <> · approved by {scene.approved_by} on {when(scene.approved_at)}</>}
        </div>
        {message && (
          <Callout tone={message.status === "APPROVED" || message.status === "VALID" ? "success" : "warning"} icon="info-circle">
            {message.status}
            {message.errors?.length > 0 && (
              <ul className="mb-0 mt-1">
                {message.errors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            )}
          </Callout>
        )}
        {scene.status === "DRAFT" && (
          <div className="d-flex gap-2 mt-2">
            <button type="button" className="btn btn-sm btn-outline-secondary" disabled={busy}
                    onClick={() => run("validate", onValidated)}>
              Validate
            </button>
            <button type="button" className="btn btn-sm btn-primary" disabled={busy}
                    onClick={() => run("approve", onApproved)}>
              Approve
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ManimStudioPage() {
  const [candidates, setCandidates] = useState(null);
  const [scenes, setScenes] = useState(null);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState(null);

  const reload = useCallback(() => {
    setError(null);
    Promise.all([call("/candidates"), call("/scenes")])
      .then(([c, s]) => {
        setCandidates(c);
        setScenes(s);
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => { reload(); }, [reload]);

  return (
    <div className="app-page">
      <PageHeader
        icon="camera-reels"
        title="Manim video studio"
        subtitle="Review research-agent-generated explainer videos and promote the good ones into the canonical scene catalog."
        pills={[
          <Pill key="candidates" tone="info" icon="hourglass-split">{candidates?.length ?? "…"} pending review</Pill>,
          <Pill key="scenes" tone="neutral" icon="collection">{scenes?.length ?? "…"} in catalog</Pill>,
        ]}
      />

      {error && <Callout tone="danger" icon="exclamation-triangle">{error}</Callout>}

      <div className="row g-4">
        <div className="col-lg-6">
          <h2 className="h6 text-secondary text-uppercase mb-3">Pending promotion</h2>
          {candidates && candidates.length === 0 && (
            <EmptyState icon="inbox">No finished, unpromoted render jobs right now.</EmptyState>
          )}
          {candidates?.map((c) => (
            <CandidateCard key={c.id} candidate={c} onPromoted={reload} />
          ))}
        </div>

        <div className="col-lg-6">
          <h2 className="h6 text-secondary text-uppercase mb-3">Catalog scenes</h2>
          {scenes && scenes.length === 0 && <EmptyState icon="collection">Nothing promoted yet.</EmptyState>}
          <div className="list-group mb-3">
            {scenes?.map((s) => (
              <button
                key={s.scene_spec_id}
                type="button"
                className={`list-group-item list-group-item-action d-flex justify-content-between align-items-center ${selected === s.scene_spec_id ? "active" : ""}`}
                onClick={() => setSelected(s.scene_spec_id)}
              >
                <span>{s.canonical_code} <span className="small text-secondary">v{s.version}</span></span>
                <Pill tone={STATUS_TONE[s.status] || "neutral"}>{s.status}</Pill>
              </button>
            ))}
          </div>
          {selected && scenes && (
            <SceneDetail
              scene={scenes.find((s) => s.scene_spec_id === selected)}
              onValidated={reload}
              onApproved={reload}
            />
          )}
        </div>
      </div>
    </div>
  );
}
