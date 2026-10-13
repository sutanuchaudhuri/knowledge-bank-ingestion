"use client";

import { useState } from "react";
import { Callout, IconButton, Pill } from "./ui.jsx";
import { buildCircumcenterConstruction, constructionViewport } from "../../lib/circumcenterConstruction.mjs";

const label = (id) => id.replace(/1/g, "₁").replace(/2/g, "₂");

export default function ConstructionPreview({ intent, code }) {
  const [index, setIndex] = useState(0);
  let construction, viewport;
  try {
    construction = buildCircumcenterConstruction(intent, code);
    viewport = constructionViewport(construction, construction.frames[Math.min(index, construction.frames.length - 1)]);
  } catch (error) {
    return <Callout tone="warning" role="alert">{error.message} No generic diagram will be substituted.</Callout>;
  }
  const frame = construction.frames[Math.min(index, construction.frames.length - 1)];
  const polygon = (vertices) => vertices.map((id) => viewport.point(id).join(",")).join(" ");
  const line = (from, to) => {
    const a = viewport.point(from), b = viewport.point(to);
    return { x1: a[0], y1: a[1], x2: b[0], y2: b[1] };
  };
  return <figure className="mb-generated-diagram">
    <div className="d-flex flex-wrap gap-1 mb-2">
      <Pill tone="info" icon="image">Step-aligned construction</Pill>
      <Pill>Illustrative coordinates</Pill><Pill>Not source</Pill>
    </div>
    <svg viewBox="0 0 480 340" className="mb-source-image" role="img" aria-label="Progressive circumcenter construction">
      <title>{frame.caption}</title>
      <polygon data-element-id={`quadrilateral_${frame.parents.join("")}`} points={polygon(frame.parents)} fill="none" stroke="var(--mb-muted)" strokeWidth="2">
        <title>{frame.level === 1 ? "Original quadrilateral: canonical statement" : "First-level circumcenter quadrilateral: canonical construction"}</title>
      </polygon>
      {!frame.allSecond && frame.triangles.map((id, i) => <polygon key={id} data-element-id={`triangle_${construction.definitions[id].triangle.join("")}`}
        points={polygon(construction.definitions[id].triangle)} fill={i % 2 ? "var(--mb-primary-soft)" : "var(--mb-info-soft)"}
        stroke={i % 2 ? "var(--mb-primary)" : "var(--mb-info)"} strokeWidth="2" opacity=".6">
        <title>{`Triangle ${construction.definitions[id].triangle.map(label).join("")}: defines ${label(id)} in the canonical statement`}</title>
      </polygon>)}
      {frame.circles.map((id) => {
        const p = viewport.point(id);
        return <circle key={id} data-element-id={`circumcircle_${id}`} cx={p[0]} cy={p[1]} r={viewport.radius(id)} fill="none" stroke="var(--mb-info)" strokeWidth="2" strokeDasharray="5 4">
          <title>{`Circumcircle of ${construction.definitions[id].triangle.map(label).join("")}: computed from its three defining vertices`}</title>
        </circle>;
      })}
      {frame.radii.flatMap((id) => construction.definitions[id].triangle.map((v) =>
        <line key={`${id}${v}`} data-element-id={`radius_${id}${v}`} {...line(id, v)} stroke="var(--mb-info)" strokeWidth="2" strokeDasharray="4 4">
          <title>{`${label(id)}${label(v)}: radius of the defining circumcircle; current visual focus`}</title>
        </line>))}
      {frame.shared && <line data-element-id="segment_CD" {...line("C", "D")} stroke="var(--mb-success)" strokeWidth="4">
        <title>CD: shared side of BCD and CDA; current visual focus</title>
      </line>}
      {frame.centers.length === 4 && <polygon data-element-id={`quadrilateral_${frame.centers.join("")}`} points={polygon(frame.centers)} fill="none" stroke="var(--mb-primary)" strokeWidth="3" />}
      {frame.visible.map((id, i) => {
        const p = viewport.point(id), derived = Boolean(construction.definitions[id]);
        return <g key={id} data-element-id={id}>
          <title>{derived ? `${label(id)}: circumcenter of ${construction.definitions[id].triangle.map(label).join(", ")}` : `${id}: original vertex`}</title>
          <circle cx={p[0]} cy={p[1]} r="4" fill={derived ? "var(--mb-primary)" : "var(--mb-text)"} />
          {(!frame.allSecond || !id.endsWith("2")) && <text x={p[0] + (i % 2 ? 10 : -10)} y={p[1] + (i % 2 ? 18 : -10)} textAnchor={i % 2 ? "start" : "end"} fill="var(--mb-text)">{label(id)}</text>}
        </g>;
      })}
    </svg>
    {frame.allSecond && <SecondLevelZoom construction={construction} frame={frame} />}
    <div className="d-flex gap-2 align-items-center">
      <IconButton label="Previous construction frame" icon="chevron-left" disabled={!index} onClick={() => setIndex(index - 1)} />
      <figcaption className="small flex-grow-1" aria-live="polite">{index + 1}/{construction.frames.length} · {frame.caption}</figcaption>
      <IconButton label="Next construction frame" icon="chevron-right" disabled={index >= construction.frames.length - 1} onClick={() => setIndex(index + 1)} />
    </div>
    <details className="small mt-2"><summary>Element definitions</summary>
      <ul>{frame.centers.map((id) => <li key={id}>{label(id)}: circumcenter of triangle {construction.definitions[id].triangle.map(label).join("")} · canonical statement</li>)}</ul>
      <p className="text-secondary mb-0">Coordinates are computed from a nondegenerate example, not recovered from a source figure. Each center is checked for equal distance to its three defining vertices. Highlighting follows the current tutor goal.</p>
    </details>
  </figure>;
}

function SecondLevelZoom({ construction, frame }) {
  const viewport = constructionViewport(construction, { ...frame, visible: frame.centers, circles: [] });
  return <div className="border rounded p-2 mt-2 mb-2">
    <Pill tone="info">Second level · magnified independently</Pill>
    <svg viewBox="0 0 480 340" className="mb-source-image" role="img" aria-label="Magnified second-level circumcenters">
      <polygon points={frame.centers.map((id) => viewport.point(id).join(",")).join(" ")} fill="var(--mb-primary-soft)" stroke="var(--mb-primary)" strokeWidth="3" />
      {frame.centers.map((id, index) => {
        const p = viewport.point(id);
        return <g key={id} data-zoom-element-id={id}>
          <circle cx={p[0]} cy={p[1]} r="4" fill="var(--mb-primary)" />
          <text x={p[0] + (index % 2 ? 10 : -10)} y={p[1] + (index % 2 ? 18 : -10)} textAnchor={index % 2 ? "start" : "end"} fill="var(--mb-text)">{label(id)}</text>
        </g>;
      })}
    </svg>
    <p className="small text-secondary mb-0">This panel uses a different zoom. Do not read a scale factor from these pictures.</p>
  </div>;
}
