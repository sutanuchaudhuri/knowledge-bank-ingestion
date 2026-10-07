"use client";

import { useEffect, useState } from "react";
import { Callout, IconButton, Pill } from "./ui.jsx";

export default function GeometryArtifact({ plan, renderMath }) {
  const [image, setImage] = useState(null);
  const [error, setError] = useState(null);
  const [frame, setFrame] = useState(0);
  const payload = JSON.stringify(plan);
  const frames = plan.frames || [];
  const activeFrame = frame < frames.length ? frame : 0;
  const overlay = plan.overlays?.find((item) => item.id === frames[activeFrame]?.overlay_id);
  useEffect(() => setFrame(0), [payload]);
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl;
    setImage(null);
    setError(null);
    const endpoint = plan.subject === "GEOMETRY" ? "geometry-preview" : "preview";
    const frameQuery = frames.length ? `?frame=${activeFrame}` : "";
    fetch(`/api/rest/artifacts/${endpoint}/content${frameQuery}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: payload, signal: controller.signal, cache: "no-store",
    }).then(async (response) => {
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail?.message || body.detail?.code || body.detail || `Diagram unavailable (${response.status})`);
      }
      if (!response.headers.get("content-type")?.startsWith("image/svg+xml")) throw new Error("Unexpected diagram response.");
      const blob = await response.blob();
      if (controller.signal.aborted) return;
      objectUrl = URL.createObjectURL(blob);
      setImage(objectUrl);
    }).catch((err) => { if (err.name !== "AbortError") setError(err.message); });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [payload, plan.subject, activeFrame, frames.length]);
  return (
    <figure className="mb-generated-diagram">
      <Pill tone="info" icon="image">Generated illustration · not the source figure</Pill>
      {error ? <Callout tone="danger" role="alert">{error}</Callout>
        : image ? <img src={image} alt={plan.title || "Generated geometry diagram"} className="mb-source-image" />
          : <div role="status" className="text-secondary small my-3">Drawing the geometry diagram…</div>}
      {frames.length > 0 && <div className="d-flex align-items-center gap-2 flex-wrap my-2" aria-label="Diagram frames">
        <IconButton icon="chevron-left" label="Previous diagram frame" disabled={activeFrame === 0}
          onClick={() => setFrame(activeFrame - 1)} />
        <span className="small flex-grow-1" aria-live="polite">{activeFrame + 1} / {frames.length} · {overlay?.caption}</span>
        <IconButton icon="chevron-right" label="Next diagram frame" disabled={activeFrame === frames.length - 1}
          onClick={() => setFrame(activeFrame + 1)} />
      </div>}
      {image && renderMath && plan.elements.filter((element) => element.kind === "EQUATION").map((element) => (
        <div key={element.id} className="my-2">{renderMath(`$$${element.latex}$$`)}{element.reason && <div className="small text-secondary">{element.reason}</div>}</div>
      ))}
      <figcaption className="small text-secondary">{plan.summary || "Illustrative sketch; not a proof or an original publisher diagram."}</figcaption>
    </figure>
  );
}
