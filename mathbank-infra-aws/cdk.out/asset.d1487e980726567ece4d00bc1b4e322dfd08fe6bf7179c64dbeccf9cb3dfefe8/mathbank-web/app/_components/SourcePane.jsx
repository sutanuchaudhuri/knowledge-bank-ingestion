"use client";

import { createContext, useContext, useState } from "react";
import { Callout, IconButton, Pill } from "./ui.jsx";
import { SourceImage } from "./ProblemDiagrams.jsx";

const SourceContext = createContext(null);
export const useSourcePane = () => useContext(SourceContext);

export default function SourcePane({ children }) {
  const [selected, setSelected] = useState(null);
  const [frameError, setFrameError] = useState(false);
  const [selectedPage, setSelectedPage] = useState(null);
  const open = (value) => { setFrameError(false); setSelectedPage(null); setSelected(value); };
  const source = selected?.source;
  const page = selectedPage || source?.location?.page;
  const pages = source?.location?.pages || [];
  const pdfUrl = source?.highlight_pdf_url || source?.embed_url;
  const documentUrl = pdfUrl ? `${pdfUrl}${page ? `#page=${page}` : ""}` : null;
  return <SourceContext.Provider value={{ selected, open, close: () => setSelected(null) }}>
    {children}
    {selected && <aside className="mb-source-pane" aria-label="Original source split pane" data-testid="source-viewer">
      <header className="d-flex align-items-center justify-content-between gap-2">
        <div><strong>{selected.code}</strong><div className="d-flex gap-2 mt-1">
          <Pill icon="file-earmark-text">{source.label}</Pill>
          {page && <Pill>Page {page}</Pill>}
        </div></div>
        <IconButton icon="x-lg" label="Close source pane" onClick={() => setSelected(null)} />
      </header>
      <div className="mb-source-pane-body">
        {pages.length > 1 && <div className="d-flex flex-wrap gap-2 mb-2" aria-label="Problem source pages">
          {pages.map((region) => <button key={region.page} type="button"
            className={`btn btn-sm ${page === region.page ? "btn-primary" : "btn-outline-secondary"}`}
            onClick={() => { setFrameError(false); setSelectedPage(region.page); }}>
            {region.page === source.location.page ? "Problem" : "Diagram"} · Page {region.page}
          </button>)}
        </div>}
        {(source.url || source.embed_url) && <a href={source.url || source.embed_url} target="_blank" rel="noreferrer"
          className="btn btn-sm btn-outline-primary mb-2">Open original in new tab</a>}
        <p className="small text-secondary">Full original source; other problems or answers may be present.</p>
        {source.highlight_url && <section aria-label="Highlighted problem location">
          <SourceImage key={page} src={`${source.highlight_url}${page ? `?page=${page}` : ""}`} alt={`Highlighted location of ${selected.code} in the original PDF`}
            className="mb-source-image" />
          <p className="small text-secondary">Highlighted from verified source text or figure coordinates.</p>
        </section>}
        {documentUrl ? <>
          {!page && <Callout tone="warning">The problem location is not verified. No highlight is guessed.</Callout>}
          <iframe key={documentUrl} src={documentUrl} title={`Original source document for ${selected.code}`}
            className="mb-source-frame" referrerPolicy="no-referrer" onError={() => setFrameError(true)} />
          {frameError && <Callout tone="warning" role="alert">Original document could not be displayed. Open the source in a new tab.</Callout>}
        </> : <Callout tone="neutral">No PDF is registered for this problem. Open the original source page using the link above.</Callout>}
      </div>
    </aside>}
  </SourceContext.Provider>;
}
