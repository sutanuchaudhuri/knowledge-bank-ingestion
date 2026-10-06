"use client";

import { useEffect, useState } from "react";
import { problemImageUrl } from "../../lib/problemDiagrams.mjs";
import { Callout } from "./ui.jsx";

function Diagram({ image, code }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <Callout tone="warning">Source diagram unavailable for {code}.</Callout>;
  return (
    <figure className="mb-problem-diagram">
      <a href={problemImageUrl(image.problem_image_id)} target="_blank" rel="noreferrer" aria-label={`Open source image for ${code}`}>
        <img src={problemImageUrl(image.problem_image_id)} alt={image.alt || `Diagram ${image.ordinal} for ${code}`}
          loading="lazy" onError={() => setFailed(true)} />
      </a>
      <figcaption className="small text-secondary">
        {image.source === "PDF_PROBLEM_PAGE" ? "Source problem page - may include neighbouring questions" : "Source problem diagram"}
      </figcaption>
    </figure>
  );
}

export default function ProblemDiagrams({ code, images }) {
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
  if (error) return <Callout tone="warning" role="alert">{error}</Callout>;
  const items = images ?? loaded;
  if (!items?.length) return null;
  return <div className="mb-problem-diagrams" data-testid="problem-diagrams">
    {items.map((image) => <Diagram key={image.problem_image_id} image={image} code={code} />)}
  </div>;
}
