"use client";

import { useRef, useState } from "react";
import { Callout, EmptyState, Icon, Pill, SectionTitle } from "../../../../_components/ui.jsx";
import { endpoint, request } from "./shared.js";

function Field({ label, id, ...props }) {
  return (
    <div className="mb-3">
      <label className="form-label" htmlFor={id}>{label}</label>
      <input id={id} className="form-control" {...props} />
    </div>
  );
}

/** Media/video attachment per state, plus a YouTube-aware upload form. AI-assisted
 * transcription (requirements/43 §3.2.3 step 3-4) is flagged "coming soon" rather than
 * faked — there is no transcription provider wired up yet. */
export default function MediaTab({ release, refresh }) {
  const [assetForm, setAssetForm] = useState({ state_id: release?.states?.[0]?.state_id || "", title: "", presentation_role: "SUPPORT", rights_note: "" });
  const [assetFile, setAssetFile] = useState(null);
  const [assetConfirmed, setAssetConfirmed] = useState(false);
  const [reviewer, setReviewer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const assetInputRef = useRef(null);

  if (!release) return <EmptyState icon="camera-video">Create a draft release first (see the Versions tab).</EmptyState>;
  const editable = release.status === "DRAFT";

  const mediaAssets = release.states.flatMap(state =>
    (state.assets || []).map(asset => ({ ...asset, state_title: state.title, state_key: state.state_key })));

  async function uploadAsset(event) {
    event.preventDefault();
    if (!assetForm.state_id || !assetFile) return;
    if (!reviewer.trim() || !assetConfirmed) {
      setError("Enter the reviewer and confirm the asset review before uploading.");
      return;
    }
    if (assetFile.size > 25 * 1024 * 1024) {
      setError("Choose an asset no larger than 25 MB.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const formData = new FormData();
      formData.set("file", assetFile);
      formData.set("title", assetForm.title || assetFile.name);
      formData.set("presentation_role", assetForm.presentation_role);
      formData.set("rights_note", assetForm.rights_note);
      formData.set("reviewed_by", reviewer.trim());
      formData.set("admin_confirmed", "true");
      await request(`${endpoint}/states/${assetForm.state_id}/assets`, { method: "POST", body: formData });
      setNotice("Asset uploaded to private storage and attached to the draft.");
      setAssetFile(null);
      setAssetConfirmed(false);
      if (assetInputRef.current) assetInputRef.current.value = "";
      setAssetForm(current => ({ ...current, title: "", rights_note: "" }));
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {error && <Callout tone="danger" role="alert" className="mb-3">{error}</Callout>}
      {notice && <Callout tone="success" role="status" className="mb-3">{notice}</Callout>}

      <div className="card border-0 shadow-sm p-3 mb-4">
        <SectionTitle icon="collection-play">Attached media — v{release.version}</SectionTitle>
        {!mediaAssets.length ? <EmptyState icon="camera-video">No media attached yet.</EmptyState> : (
          <ul className="list-group list-group-flush">
            {mediaAssets.map(asset => (
              <li key={asset.asset_id} className="list-group-item d-flex justify-content-between align-items-center gap-3">
                <div>
                  <strong>{asset.title || asset.asset_kind}</strong>
                  <div className="small text-secondary">{asset.state_title} ({asset.state_key}) · {asset.mime_type}</div>
                </div>
                <Pill tone={asset.validation_status === "VALID" ? "success" : "warning"}>{asset.validation_status}</Pill>
              </li>
            ))}
          </ul>
        )}
      </div>

      {editable && (
        <div className="row g-3">
          <div className="col-lg-7">
            <form className="card border-0 shadow-sm p-3" onSubmit={uploadAsset}>
              <SectionTitle icon="upload">Upload private media</SectionTitle>
              <label className="form-label" htmlFor="asset-state">Lesson state</label>
              <select id="asset-state" className="form-select mb-3" value={assetForm.state_id}
                onChange={event => setAssetForm({ ...assetForm, state_id: event.target.value })} required>
                {release.states.map(state => <option key={state.state_id} value={state.state_id}>{state.state_key} · {state.title}</option>)}
              </select>
              <div className="mb-3">
                <label className="form-label" htmlFor="asset-file">Asset file</label>
                <input ref={assetInputRef} id="asset-file" className="form-control" type="file"
                  accept="image/png,image/jpeg,image/webp,application/pdf,text/plain,video/mp4,audio/mpeg,audio/mp4"
                  onChange={event => setAssetFile(event.target.files?.[0] || null)} required />
              </div>
              <Field id="asset-title" label="Display title" value={assetForm.title}
                onChange={event => setAssetForm({ ...assetForm, title: event.target.value })} maxLength={300} />
              <label className="form-label" htmlFor="asset-role">Presentation role</label>
              <select id="asset-role" className="form-select mb-3" value={assetForm.presentation_role}
                onChange={event => setAssetForm({ ...assetForm, presentation_role: event.target.value })}>
                {["PRIMARY", "SUPPORT", "EXAMPLE", "REFERENCE", "OPTIONAL"].map(role => <option key={role}>{role}</option>)}
              </select>
              <Field id="asset-rights" label="Rights / source note" value={assetForm.rights_note}
                onChange={event => setAssetForm({ ...assetForm, rights_note: event.target.value })} maxLength={1000} />
              <Field id="asset-reviewer" label="Asset reviewer" value={reviewer}
                onChange={event => setReviewer(event.target.value)} required maxLength={200} />
              <label className="form-check mb-3">
                <input className="form-check-input" type="checkbox" checked={assetConfirmed} disabled={busy}
                  onChange={event => setAssetConfirmed(event.target.checked)} />
                <span className="form-check-label">I reviewed this asset and confirm it is approved for course use.</span>
              </label>
              <div className="d-flex align-items-center justify-content-between gap-3">
                <Pill tone="neutral">Private · up to 25 MB</Pill>
                <button className="btn btn-primary" type="submit" disabled={busy || !assetFile || !reviewer.trim() || !assetConfirmed}>
                  Upload asset
                </button>
              </div>
            </form>
          </div>
          <div className="col-lg-5">
            <div className="card border-0 shadow-sm p-3 h-100">
              <SectionTitle icon="youtube">YouTube video</SectionTitle>
              <p className="small text-secondary">
                Paste a YouTube URL as a "Reference" presentation-role asset using the form on
                the left — the student reader embeds recognized YouTube links automatically
                (see requirements/42 §3.3).
              </p>
              <Callout tone="hint">
                <Icon name="robot" /> <strong>AI transcription ("Help me transcribe") is not yet
                available.</strong> Transcripts remain manual-authoring only for now; a review
                flow for timestamped segments is designed in requirements/43 §3.2.3 but not
                built.
              </Callout>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
