"use client";

import { useEffect, useState } from "react";
import { pinnedSceneVersions, sceneFrameCaption } from "../../lib/geometryScenes.mjs";
import { Callout, IconButton, Pill } from "./ui.jsx";

/** @param {{scene: import("../../lib/geometryScenes.mjs").GeometrySceneReference}} props */
export default function GeometryScene({ scene }) {
  const { scene_id: id, version: pinned } = scene;
  // The key in MathText resets state when a streamed reference changes.
  const [version, setVersion] = useState(pinned);
  const [versions, setVersions] = useState([pinned]);
  const [frame, setFrame] = useState(null);
  const [error, setError] = useState(null);
  const [navigationError, setNavigationError] = useState(false);
  const base = `/api/rest/geometry-scenes/${id}`;
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${base}/frames`, { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") throw new Error();
        const list = pinnedSceneVersions(await response.json(), pinned);
        if (!controller.signal.aborted) setVersions(list);
      }).catch(() => { if (!controller.signal.aborted) setNavigationError(true); });
    return () => controller.abort();
  }, [base, pinned]);
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl;
    setFrame(null);
    setError(null);
    const path = `${base}/versions/${version}`;
    Promise.all([
      fetch(path, { cache: "no-store", signal: controller.signal }).then(async (response) => {
        if (!response.ok || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") throw new Error("The diagram caption is unavailable.");
        return sceneFrameCaption(await response.json(), id, version);
      }),
      fetch(`${path}/render`, { cache: "no-store", signal: controller.signal }).then(async (response) => {
        if (!response.ok) throw new Error("The geometry diagram is unavailable.");
        if (!["image/svg+xml", "image/png"].includes(response.headers.get("content-type")?.split(";")[0].trim().toLowerCase())) throw new Error("Unexpected diagram response.");
        return response.blob();
      }),
    ]).then(([caption, blob]) => {
      if (controller.signal.aborted) return;
      objectUrl = URL.createObjectURL(blob);
      setFrame({ image: objectUrl, caption, version });
    }).catch((err) => { if (!controller.signal.aborted) setError(err.message); });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [base, id, version]);
  const index = versions.indexOf(version);
  const visible = frame?.version === version ? frame : null;
  return (
    <figure className="mb-generated-diagram" data-testid="geometry-scene">
      <Pill tone="info" icon="image">Geometry illustration · not a proof</Pill>
      {error ? <Callout tone="danger" role="alert">{error}</Callout>
        : visible ? <img src={visible.image} alt={visible.caption || "Geometry diagram"} className="mb-source-image" />
          : <div role="status" className="text-secondary small my-3">Loading the geometry diagram…</div>}
      <nav className="d-flex align-items-center gap-2 flex-wrap my-2" aria-label="Geometry scene frames">
        <IconButton icon="chevron-left" label="Previous geometry frame" disabled={index <= 0}
          onClick={() => setVersion(versions[index - 1])} />
        <span className="small mb-num">Frame {index + 1} / {versions.length}</span>
        <IconButton icon="chevron-right" label="Next geometry frame" disabled={index < 0 || index >= versions.length - 1}
          onClick={() => setVersion(versions[index + 1])} />
      </nav>
      {navigationError && <div role="status" className="small text-secondary">Earlier frames are unavailable.</div>}
      <figcaption className="small text-secondary" aria-live="polite">{visible?.caption}</figcaption>
    </figure>
  );
}
