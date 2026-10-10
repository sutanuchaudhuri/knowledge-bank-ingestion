"use client";

import { useEffect, useState } from "react";
import { Callout, EmptyState, Pill, SectionTitle } from "../../../../_components/ui.jsx";
import { endpoint, request } from "./shared.js";

const STATUS_TONE = { PUBLISHED: "success", DRAFT: "warning", REVIEWED: "info", APPROVED: "info", SUPERSEDED: "neutral", RETIRED: "neutral" };

function DiffSummary({ diff }) {
  return (
    <div className="mt-3">
      <div className="d-flex flex-wrap gap-2 mb-2">
        <Pill tone={diff.metadata_changed ? "warning" : "success"}>
          {diff.metadata_changed ? "Metadata changed" : "Metadata unchanged"}
        </Pill>
        <Pill tone={diff.states_added.length ? "primary" : "neutral"}>{diff.states_added.length} states added</Pill>
        <Pill tone={diff.states_removed.length ? "danger" : "neutral"}>{diff.states_removed.length} states removed</Pill>
        <Pill tone={diff.states_changed.length ? "info" : "neutral"}>{diff.states_changed.length} states changed</Pill>
        <Pill tone={diff.interaction_changes.length ? "info" : "neutral"}>{diff.interaction_changes.length} states with interaction changes</Pill>
      </div>
      {diff.states_added.length > 0 && <p className="small mb-1"><strong>Added:</strong> {diff.states_added.join(", ")}</p>}
      {diff.states_removed.length > 0 && <p className="small mb-1"><strong>Removed:</strong> {diff.states_removed.join(", ")}</p>}
      {diff.states_changed.map(change => (
        <p key={change.state_key} className="small mb-1">
          <strong>{change.state_key}:</strong> {change.before.title !== change.after.title && `title "${change.before.title}" → "${change.after.title}"`}
          {change.before.ordinal !== change.after.ordinal && ` · ordinal ${change.before.ordinal} → ${change.after.ordinal}`}
        </p>
      ))}
    </div>
  );
}

/** Release history, a two-release diff, and the validate → review → publish wizard
 * (requirements/43 §3.2.6, AMC-6). Promoting an older release to a new draft reuses the
 * same create_release(parent_release_id=...) the workspace shell's "New draft version"
 * action calls, just targeting a specific historical release instead of always the latest. */
export default function VersionsTab({ course, refresh }) {
  const [releaseA, setReleaseA] = useState("");
  const [releaseB, setReleaseB] = useState("");
  const [diff, setDiff] = useState(null);
  const [selectedRelease, setSelectedRelease] = useState(null);
  const [reviewer, setReviewer] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const releases = course.releases || [];

  useEffect(() => {
    if (releases.length >= 2 && !releaseA && !releaseB) {
      setReleaseA(releases[1].release_id);
      setReleaseB(releases[0].release_id);
    }
  }, [releases, releaseA, releaseB]);

  useEffect(() => {
    if (!releaseA || !releaseB || releaseA === releaseB) { setDiff(null); return undefined; }
    const controller = new AbortController();
    request(`${endpoint}/releases/${releaseA}/diff/${releaseB}`, { signal: controller.signal })
      .then(setDiff)
      .catch(err => { if (err.name !== "AbortError") setError(err.message); });
    return () => controller.abort();
  }, [releaseA, releaseB]);

  useEffect(() => {
    const latestDraft = releases.find(r => r.status === "DRAFT" || r.status === "APPROVED");
    if (latestDraft) {
      const controller = new AbortController();
      request(`${endpoint}/releases/${latestDraft.release_id}`, { signal: controller.signal })
        .then(setSelectedRelease)
        .catch(() => {});
      return () => controller.abort();
    }
    return undefined;
  }, [releases]);

  async function promote(releaseId) {
    const actor = window.prompt("Your name (for the audit trail)");
    if (!actor) return;
    setBusy(true);
    setError("");
    try {
      await request(`${endpoint}/${encodeURIComponent(course.canonical_code)}/releases`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ created_by: actor, parent_release_id: releaseId }),
      });
      setNotice("New draft version created from the selected release.");
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function validate() {
    if (!selectedRelease) return;
    setBusy(true);
    setError("");
    try {
      const result = await request(`${endpoint}/releases/${selectedRelease.release_id}/validate`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
      });
      setNotice(result.status === "VALID" ? "Release passed validation." : `Validation failed: ${(result.errors || []).join("; ")}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function review() {
    if (!selectedRelease) return;
    setBusy(true);
    setError("");
    try {
      const result = await request(`${endpoint}/releases/${selectedRelease.release_id}/review`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "APPROVED", reviewer, note: "Reviewed in the admin workspace." }),
      });
      if (result.errors?.length) throw new Error(result.errors.join("; "));
      setNotice("Release approved for publication.");
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function publish() {
    if (!selectedRelease) return;
    setBusy(true);
    setError("");
    try {
      const result = await request(`${endpoint}/releases/${selectedRelease.release_id}/publish`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ publisher: reviewer }),
      });
      if (result.errors?.length) throw new Error(result.errors.join("; "));
      setNotice(`Published v${selectedRelease.version}; graph projection is ${result.projection}.`);
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
        <SectionTitle icon="clock-history">Release history</SectionTitle>
        {!releases.length ? <EmptyState icon="clock-history">No releases yet.</EmptyState> : (
          <ul className="list-group list-group-flush">
            {releases.map(release => (
              <li key={release.release_id} className="list-group-item d-flex justify-content-between align-items-center gap-3">
                <div>
                  <strong>v{release.version}</strong>
                  <span className="small text-secondary ms-2">{release.created_by} · {release.created_at?.slice(0, 10)}</span>
                </div>
                <div className="d-flex gap-2 align-items-center">
                  <Pill tone={STATUS_TONE[release.status] || "neutral"}>{release.status}</Pill>
                  {release.status !== "DRAFT" && (
                    <button type="button" className="btn btn-sm btn-outline-primary" disabled={busy} onClick={() => promote(release.release_id)}>
                      Promote to new draft
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {releases.length >= 2 && (
        <div className="card border-0 shadow-sm p-3 mb-4">
          <SectionTitle icon="file-diff">Compare two releases</SectionTitle>
          <div className="row g-3">
            <div className="col-md-5">
              <label className="form-label" htmlFor="diff-a">Release A</label>
              <select id="diff-a" className="form-select" value={releaseA} onChange={event => setReleaseA(event.target.value)}>
                {releases.map(release => <option key={release.release_id} value={release.release_id}>v{release.version} ({release.status})</option>)}
              </select>
            </div>
            <div className="col-md-5">
              <label className="form-label" htmlFor="diff-b">Release B</label>
              <select id="diff-b" className="form-select" value={releaseB} onChange={event => setReleaseB(event.target.value)}>
                {releases.map(release => <option key={release.release_id} value={release.release_id}>v{release.version} ({release.status})</option>)}
              </select>
            </div>
          </div>
          {diff && <DiffSummary diff={diff} />}
        </div>
      )}

      {selectedRelease && selectedRelease.status !== "PUBLISHED" && (
        <div className="card border-0 shadow-sm p-3">
          <SectionTitle icon="patch-check">Validate → review → publish (v{selectedRelease.version})</SectionTitle>
          <div className="mb-3" style={{ maxWidth: 360 }}>
            <label className="form-label" htmlFor="reviewer-name">Reviewer / publisher name</label>
            <input id="reviewer-name" className="form-control" value={reviewer} onChange={event => setReviewer(event.target.value)} />
          </div>
          {selectedRelease.status === "DRAFT" && (
            <label className="form-check mb-3">
              <input className="form-check-input" type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />
              <span className="form-check-label">I confirm this release is ready for approval.</span>
            </label>
          )}
          <div className="d-flex flex-wrap gap-2">
            {selectedRelease.status === "DRAFT" && <>
              <button type="button" className="btn btn-outline-primary" disabled={busy} onClick={validate}>Validate</button>
              <button type="button" className="btn btn-primary" disabled={busy || !reviewer.trim() || !confirmed} onClick={review}>Approve release</button>
            </>}
            {selectedRelease.status === "APPROVED" && (
              <button type="button" className="btn btn-primary" disabled={busy || !reviewer.trim()} onClick={publish}>Publish</button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
