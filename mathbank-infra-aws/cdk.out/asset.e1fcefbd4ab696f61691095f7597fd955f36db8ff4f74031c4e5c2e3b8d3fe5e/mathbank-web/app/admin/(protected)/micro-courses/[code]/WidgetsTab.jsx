"use client";

import { useEffect, useState } from "react";
import { Callout, EmptyState, Pill, SectionTitle } from "../../../../_components/ui.jsx";
import { endpoint, request } from "./shared.js";

const STATUS_TONE = { PUBLISHED: "success", DRAFT: "warning", REVIEWED: "info", DEPRECATED: "neutral" };

/** Read-only, browsable interaction-template/control/icon/animation catalog
 * (requirements/43 §3.2.5, AMC-8). No live-preview rendering yet (would need bundled demo
 * configs per template family); status alone already tells an author what is attachable. */
export default function WidgetsTab() {
  const [library, setLibrary] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    request(`${endpoint}/templates`, { signal: controller.signal })
      .then(setLibrary)
      .catch(err => { if (err.name !== "AbortError") setError(err.message); });
    return () => controller.abort();
  }, []);

  if (error) return <Callout tone="danger" role="alert">{error}</Callout>;
  if (!library) return <p role="status" className="text-secondary">Loading widget library…</p>;

  const byTemplate = new Map();
  for (const version of library.templates) {
    if (!byTemplate.has(version.template_key)) byTemplate.set(version.template_key, []);
    byTemplate.get(version.template_key).push(version);
  }

  return (
    <div>
      <div className="card border-0 shadow-sm p-3 mb-4">
        <SectionTitle icon="puzzle">Interaction templates ({byTemplate.size})</SectionTitle>
        <div className="row g-3">
          {[...byTemplate.entries()].map(([templateKey, versions]) => (
            <div key={templateKey} className="col-md-6 col-xl-4">
              <div className="card border-0 shadow-sm p-3 h-100">
                <strong className="d-block mb-1">{templateKey}</strong>
                <span className="small text-secondary d-block mb-2">{versions[0].interaction_family}</span>
                <div className="d-flex flex-wrap gap-1">
                  {versions.map(version => (
                    <Pill key={version.interaction_template_version_id} tone={STATUS_TONE[version.version_status] || "neutral"}>
                      v{version.version} · {version.version_status}
                    </Pill>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="row g-3">
        <div className="col-md-4">
          <div className="card border-0 shadow-sm p-3 h-100">
            <SectionTitle icon="sliders">Controls ({library.controls.length})</SectionTitle>
            <div className="d-flex flex-wrap gap-1">
              {library.controls.map(control => <Pill key={control.control_key} tone="neutral">{control.control_key}</Pill>)}
            </div>
          </div>
        </div>
        <div className="col-md-4">
          <div className="card border-0 shadow-sm p-3 h-100">
            <SectionTitle icon="emoji-smile">Icons ({library.icons.length})</SectionTitle>
            <div className="d-flex flex-wrap gap-1">
              {library.icons.map(icon => <Pill key={icon.token_key} tone="neutral" title={icon.accessible_label}>{icon.token_key}</Pill>)}
            </div>
          </div>
        </div>
        <div className="col-md-4">
          <div className="card border-0 shadow-sm p-3 h-100">
            <SectionTitle icon="stars">Animations ({library.animations.length})</SectionTitle>
            <div className="d-flex flex-wrap gap-1">
              {library.animations.map(animation => <Pill key={animation.animation_key} tone="neutral">{animation.animation_key}</Pill>)}
            </div>
          </div>
        </div>
      </div>
      {!byTemplate.size && <EmptyState icon="puzzle">No interaction templates seeded yet.</EmptyState>}
    </div>
  );
}
