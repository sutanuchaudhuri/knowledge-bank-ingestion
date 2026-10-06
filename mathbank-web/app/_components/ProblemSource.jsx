"use client";

import { useEffect, useId, useState } from "react";
import { Callout, Icon, Pill } from "./ui.jsx";

export default function ProblemSource({ code }) {
  const [source, setSource] = useState(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState(null);
  const [frameError, setFrameError] = useState(false);
  const id = useId();
  useEffect(() => {
    setSource(null);
    setOpen(false);
    setError(null);
    setFrameError(false);
    if (!code) return;
    const controller = new AbortController();
    fetch(`/api/rest/solve/source/${encodeURIComponent(code)}`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Could not load original source (${response.status})`);
        return response.json();
      })
      .then((data) => { if (!controller.signal.aborted) setSource(data); })
      .catch((err) => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [code]);
  if (error) return <Callout tone="warning" role="alert">{error}</Callout>;
  if (!source) return null;
  return <section className="mb-original-source" data-testid="problem-source">
    <button type="button" className="btn btn-sm btn-outline-secondary"
      aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>
      <Icon name="file-earmark-pdf" /> Source
    </button>
    {open && <div id={id} className="mt-2" data-testid="source-viewer">
      <div className="d-flex flex-wrap align-items-center gap-2 mb-2">
        <Pill icon="file-earmark-text">{source.label}</Pill>
        {(source.url || source.embed_url) && <a href={source.url || source.embed_url} target="_blank" rel="noreferrer"
          className="btn btn-sm btn-ghost">Open original in new tab <Icon name="box-arrow-up-right" /></a>}
      </div>
      <p className="small text-secondary">Full original source, not the isolated diagram. It may include other questions or answers.</p>
      {source.embed_url
        ? <><iframe src={source.embed_url} title={`Original source document for ${code}`}
          className="mb-source-frame" referrerPolicy="no-referrer" onError={() => setFrameError(true)} />
          {frameError && <Callout tone="warning" role="alert">Original document could not be displayed. Open the source in a new tab.</Callout>}
          <p className="small text-secondary mt-2">If the viewer is blank or blocked, open the original in a new tab.</p></>
        : <Callout tone="neutral">This source is a web page, not a PDF. Use the original-source link above.</Callout>}
    </div>}
  </section>;
}
