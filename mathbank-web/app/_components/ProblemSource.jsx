"use client";

import { useEffect, useState } from "react";
import { Callout, Icon } from "./ui.jsx";
import { useSourcePane } from "./SourcePane.jsx";

export default function ProblemSource({ code }) {
  const [source, setSource] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const pane = useSourcePane();
  const open = pane?.selected?.code === code;
  const [error, setError] = useState(null);
  useEffect(() => {
    setSource(null);
    setLoaded(false);
    setError(null);
    if (!code) return;
    const controller = new AbortController();
    fetch(`/api/rest/solve/source/${encodeURIComponent(code)}`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Could not load original source (${response.status})`);
        return response.json();
      })
      .then((data) => { if (!controller.signal.aborted) { setSource(data); setLoaded(true); } })
      .catch((err) => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [code]);
  if (error) return <Callout tone="warning" role="alert">{error}</Callout>;
  if (!source) return loaded ? <Callout tone="warning">No original source is registered for this problem.</Callout> : null;
  return <section className="mb-original-source" data-testid="problem-source">
    <button type="button" className="btn btn-sm btn-outline-secondary"
      aria-expanded={open} onClick={() => open ? pane.close() : pane.open({ code, source })}>
      <Icon name="file-earmark-pdf" /> Source
    </button>
    {(source.url || source.embed_url) && <a href={source.url || source.embed_url} target="_blank" rel="noreferrer"
      className="btn btn-sm btn-ghost ms-1" title="Direct original source link"
      onClick={(event) => {
        if (source.kind === "pdf" && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
          event.preventDefault();
          pane.open({ code, source });
        }
      }}>
      <Icon name="box-arrow-up-right" />{source.kind === "pdf" ? "Original PDF" : "Original source"}
    </a>}
  </section>;
}
