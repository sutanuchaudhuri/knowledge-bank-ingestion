"use client";

import { useEffect, useState } from "react";
import { Callout, Icon } from "./ui.jsx";

export default function AsymptoteDiagram({ source }) {
  const [image, setImage] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    const controller = new AbortController();
    let url;
    setImage(null);
    setError(null);
    fetch("/api/diagrams/asymptote", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source }), signal: controller.signal,
    }).then(async (response) => {
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.error || `Diagram rendering failed (${response.status}).`);
      }
      if (!response.headers.get("content-type")?.startsWith("image/png")) {
        throw new Error("Diagram renderer returned an unexpected format.");
      }
      const blob = await response.blob();
      if (controller.signal.aborted) return;
      url = URL.createObjectURL(blob);
      setImage(url);
    }).catch((failure) => {
      if (!controller.signal.aborted) setError(failure.message);
    });
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url); };
  }, [source]);
  return <figure className="mb-generated-diagram" data-testid="asymptote-diagram">
    {error ? <Callout tone="warning" role="alert">{error}</Callout>
      : image ? <img className="mb-source-image" src={image} alt="Diagram rendered from the problem's Asymptote source"
        onError={() => setError("The rendered diagram could not be displayed.")} />
        : <div role="status" className="text-secondary">Rendering the source diagram...</div>}
    <figcaption className="small text-secondary">Rendered from embedded source code; not a proof or scale measurement.</figcaption>
    <details className="mb-diagram-code"><summary><Icon name="code-slash" /> Diagram source (Asymptote)</summary>
      <pre><code className="language-asymptote">{source}</code></pre>
    </details>
  </figure>;
}
