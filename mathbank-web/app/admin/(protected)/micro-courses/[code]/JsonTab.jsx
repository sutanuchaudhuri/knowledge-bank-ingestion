"use client";

import { useEffect, useState } from "react";
import { Callout, EmptyState, SectionTitle } from "../../../../_components/ui.jsx";
import { endpoint, request } from "./shared.js";

function JsonPane({ title, data, error }) {
  const [copied, setCopied] = useState(false);
  if (error) return <Callout tone="warning">{error}</Callout>;
  const text = JSON.stringify(data, null, 2);
  return (
    <div className="card border-0 shadow-sm p-3 h-100">
      <SectionTitle
        icon="braces"
        actions={
          <button type="button" className="btn btn-sm btn-outline-secondary"
            onClick={() => { navigator.clipboard?.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
            {copied ? "Copied" : "Copy"}
          </button>
        }
      >
        {title}
      </SectionTitle>
      <pre className="small bg-body-tertiary p-2 rounded" style={{ maxHeight: 560, overflow: "auto" }}>{text}</pre>
    </div>
  );
}

/** Two read-only JSON panes: the full admin shape (course + latest release) and the
 * public student-facing shape (GET /published, the same payload the reader consumes).
 * Requested by the user so admins can confirm exactly what gets served. */
export default function JsonTab({ course, release }) {
  const [published, setPublished] = useState(null);
  const [publishedError, setPublishedError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    request(`/api/rest/micro-courses/${encodeURIComponent(course.canonical_code)}`, { signal: controller.signal })
      .then(setPublished)
      .catch(err => {
        if (err.name === "AbortError") return;
        setPublishedError(err.status === 404 ? "Not published yet — no public JSON to show." : err.message);
      });
    return () => controller.abort();
  }, [course.canonical_code]);

  if (!release) return <EmptyState icon="braces">No release yet.</EmptyState>;

  return (
    <div className="row g-3">
      <div className="col-lg-6"><JsonPane title={`Admin — v${release.version} (${release.status})`} data={{ course, release }} /></div>
      <div className="col-lg-6"><JsonPane title="Public (student-facing)" data={published} error={publishedError} /></div>
    </div>
  );
}
