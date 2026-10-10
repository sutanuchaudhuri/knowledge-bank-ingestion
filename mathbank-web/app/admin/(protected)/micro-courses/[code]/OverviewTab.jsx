"use client";

import { useState } from "react";
import { Callout, Pill } from "../../../../_components/ui.jsx";

/** Metadata, targets and learning objectives — editable only while the identity is not yet
 * locked by a PUBLISHED/SUPERSEDED/RETIRED release (requirements/43 §3.2.1). */
export default function OverviewTab({ course, refresh }) {
  const locked = course.releases?.some(r => ["PUBLISHED", "SUPERSEDED", "RETIRED"].includes(r.status));
  const [title, setTitle] = useState(course.title);
  const [description, setDescription] = useState(course.description || "");
  const [estimatedMinutes, setEstimatedMinutes] = useState(course.estimated_minutes || "");
  const [difficultyLevel, setDifficultyLevel] = useState(course.difficulty_level || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // Course-identity editing (title/description/estimated_minutes/difficulty_level) has no
  // dedicated PATCH endpoint today — only creation and the deactivate/reactivate/new-release
  // actions exist. Surfacing that honestly rather than pretending a save button works.
  async function save(event) {
    event.preventDefault();
    setError("Editing saved metadata after creation is not yet available from this tab. "
      + "Use the catalog's \"New course\" wizard for a new course, or start a new draft "
      + "version to change learning objectives there.");
  }

  return (
    <div className="row g-4">
      <section className="col-lg-7">
        <div className="card border-0 shadow-sm p-3 p-lg-4">
          {locked && (
            <Callout tone="info" className="mb-3">
              This course's identity is locked by a published release. Start a new draft
              version to change it (course identity is immutable once published).
            </Callout>
          )}
          {error && <Callout tone="warning" role="alert" className="mb-3">{error}</Callout>}
          {notice && <Callout tone="success" role="status" className="mb-3">{notice}</Callout>}
          <form onSubmit={save}>
            <div className="mb-3">
              <label className="form-label" htmlFor="overview-title">Title</label>
              <input id="overview-title" className="form-control" value={title} disabled={locked}
                onChange={event => setTitle(event.target.value)} />
            </div>
            <div className="mb-3">
              <label className="form-label" htmlFor="overview-description">Description</label>
              <textarea id="overview-description" className="form-control" rows={3} value={description} disabled={locked}
                onChange={event => setDescription(event.target.value)} />
            </div>
            <div className="row g-2 mb-3">
              <div className="col-6">
                <label className="form-label" htmlFor="overview-minutes">Estimated minutes</label>
                <input id="overview-minutes" type="number" className="form-control mb-num" value={estimatedMinutes} disabled={locked}
                  onChange={event => setEstimatedMinutes(event.target.value)} />
              </div>
              <div className="col-6">
                <label className="form-label" htmlFor="overview-difficulty">Difficulty (1-10)</label>
                <input id="overview-difficulty" type="number" min="1" max="10" className="form-control mb-num" value={difficultyLevel} disabled={locked}
                  onChange={event => setDifficultyLevel(event.target.value)} />
              </div>
            </div>
            <button type="submit" className="btn btn-primary" disabled={busy || locked}>Save metadata</button>
          </form>
        </div>
      </section>
      <section className="col-lg-5">
        <div className="card border-0 shadow-sm p-3 p-lg-4">
          <h3 className="h6 mb-3">Primary targets</h3>
          <div className="d-flex flex-wrap gap-2">
            {course.targets?.map((target, index) => (
              <Pill key={index} tone="primary">{target.target_type}</Pill>
            ))}
            {!course.targets?.length && <Pill tone="neutral">No targets</Pill>}
          </div>
        </div>
      </section>
    </div>
  );
}
