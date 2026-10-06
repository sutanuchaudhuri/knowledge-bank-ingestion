"use client";

import { useEffect, useState } from "react";
import { problemImageUrl } from "../../lib/problemDiagrams.mjs";
import { Callout } from "./ui.jsx";
import ProblemSource from "./ProblemSource.jsx";

export function SourceImage({ src, alt, ...props }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <Callout tone="warning" role="alert">Source diagram unavailable: {alt || "problem image"}.</Callout>;
  return <img {...props} src={src} alt={alt || "Source problem diagram"}
    loading="lazy" onError={() => setFailed(true)} />;
}

function Diagram({ image, code, alt }) {
  const url = problemImageUrl(image.problem_image_id, image.version);
  return (
    <figure className="mb-problem-diagram">
      <a href={url} target="_blank" rel="noreferrer" aria-label={`Open source image for ${code}`}>
        <SourceImage key={url} src={url} alt={alt || image.alt || `Diagram ${image.ordinal} for ${code}`} />
      </a>
      <figcaption className="small text-secondary">
        Source problem diagram
      </figcaption>
    </figure>
  );
}

export default function ProblemDiagrams({ code, images, showSource = true, imageAlt }) {
  const [loaded, setLoaded] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    setLoaded(null);
    setError(null);
    if (images !== undefined || !code) return;
    const controller = new AbortController();
    fetch(`/api/rest/solve/diagrams/${encodeURIComponent(code)}`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Could not load source diagrams (${response.status})`);
        return response.json();
      })
      .then((data) => { if (!controller.signal.aborted) setLoaded(data); })
      .catch((err) => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [code, images]);
  const items = images ?? loaded;
  return <>
    {showSource && <ProblemSource code={code} />}
    {error && <Callout tone="warning" role="alert">{error}</Callout>}
    {items?.length > 0 && <div className="mb-problem-diagrams" data-testid="problem-diagrams">
      {items.map((image) => <Diagram key={image.problem_image_id} image={image} code={code} alt={imageAlt?.(image)} />)}
    </div>}
  </>;
}
