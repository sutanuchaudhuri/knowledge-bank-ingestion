"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import Link from "next/link";
import { GRAPH_DEFAULT_LIMIT, GRAPH_LIMIT_OPTIONS, RELATIONSHIPS } from "../../../lib/graphConfig.js";
import { colorFor } from "../_components/graphColors.js";
import styles from "../graph.module.css";

// force-graph renders to <canvas>; must stay client-only (no SSR).
const ForceGraphCanvas = dynamic(() => import("../_components/ForceGraphCanvas.jsx"), { ssr: false });

const ZOOM_STEP = 1.5;
const ANIM_MS = 300;
const FIT_PADDING = 40;
const DIM_COLOR = "rgba(148, 163, 184, 0.25)";

const endpointId = (end) => (typeof end === "object" && end !== null ? end.id : end);

export default function GraphRelationshipPage() {
  const { rel } = useParams();
  const config = Object.hasOwn(RELATIONSHIPS, rel) ? RELATIONSHIPS[rel] : null;
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [limit, setLimit] = useState(GRAPH_DEFAULT_LIMIT);
  const [reloadKey, setReloadKey] = useState(0);
  const [reviewedOnly, setReviewedOnly] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [paused, setPaused] = useState(false);
  const [size, setSize] = useState({ width: 0, height: 0 });

  const graphRef = useRef(null);
  const wrapRef = useRef(null);
  const fittedRef = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError(null);
    setSelectedId(null);
    setPaused(false);
    fittedRef.current = false;
    fetch(`/api/graph/relationship/${rel}?limit=${limit}&reviewed=${reviewedOnly}`, { signal: controller.signal })
      .then((res) =>
        res.ok ? res.json() : res.json().then((body) => Promise.reject(new Error(body.error || `status ${res.status}`)))
      )
      .then(setData)
      .catch((err) => { if (err.name !== "AbortError") setError(err.message); });
    return () => controller.abort();
  }, [rel, limit, reloadKey, reviewedOnly]);

  // Size the canvas to its container so the graph fills the full-width workspace.
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return undefined;
    const update = () => {
      const { width, height } = el.getBoundingClientRect();
      setSize((prev) =>
        prev.width === Math.floor(width) && prev.height === Math.floor(height)
          ? prev
          : { width: Math.floor(width), height: Math.floor(height) }
      );
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const graphData = useMemo(() => ({ nodes: data?.nodes ?? [], links: data?.links ?? [] }), [data]);

  const nodesById = useMemo(() => new Map(graphData.nodes.map((n) => [n.id, n])), [graphData]);

  const adjacency = useMemo(() => {
    const map = new Map();
    for (const link of graphData.links) {
      const s = endpointId(link.source);
      const t = endpointId(link.target);
      if (!map.has(s)) map.set(s, { out: new Set(), in: new Set() });
      if (!map.has(t)) map.set(t, { out: new Set(), in: new Set() });
      map.get(s).out.add(t);
      map.get(t).in.add(s);
    }
    return map;
  }, [graphData]);

  const legend = useMemo(() => {
    const counts = new Map();
    for (const n of graphData.nodes) counts.set(n.label, (counts.get(n.label) || 0) + 1);
    return [...counts.entries()];
  }, [graphData]);

  const selected = selectedId ? nodesById.get(selectedId) : null;
  const selectedAdj = selectedId ? adjacency.get(selectedId) : null;
  const highlightIds = useMemo(() => {
    if (!selectedId) return null;
    const ids = new Set([selectedId]);
    selectedAdj?.out.forEach((id) => ids.add(id));
    selectedAdj?.in.forEach((id) => ids.add(id));
    return ids;
  }, [selectedId, selectedAdj]);

  const fit = useCallback(() => graphRef.current?.zoomToFit(ANIM_MS, FIT_PADDING), []);
  const zoomBy = useCallback((factor) => {
    const g = graphRef.current;
    if (g) g.zoom(g.zoom() * factor, ANIM_MS);
  }, []);
  const togglePause = useCallback(() => {
    const g = graphRef.current;
    if (!g) return;
    if (paused) g.resumeAnimation();
    else g.pauseAnimation();
    setPaused(!paused);
  }, [paused]);
  const resetView = useCallback(() => {
    const g = graphRef.current;
    setSelectedId(null);
    if (!g) return;
    if (paused) {
      g.resumeAnimation();
      setPaused(false);
    }
    fittedRef.current = false;
    g.d3ReheatSimulation();
    g.zoomToFit(ANIM_MS, FIT_PADDING);
  }, [paused]);

  const focusNode = useCallback((id) => {
    setSelectedId(id);
    const node = nodesById.get(id);
    const g = graphRef.current;
    if (g && node && Number.isFinite(node.x)) g.centerAt(node.x, node.y, ANIM_MS);
  }, [nodesById]);

  const onEngineStop = useCallback(() => {
    if (!fittedRef.current) {
      fittedRef.current = true;
      graphRef.current?.zoomToFit(ANIM_MS, FIT_PADDING);
    }
  }, []);

  const loading = !data && !error;
  const isEmpty = data && graphData.nodes.length === 0;
  const sampled = data?.links.length ?? 0;
  const total = data?.totalRelationships;
  const coverage = total ? Math.round((sampled / total) * 1000) / 10 : null;

  const renderNeighbors = (title, ids) => (
    <div className="mb-3">
      <div className="fw-semibold small mb-1">{title} ({ids.size})</div>
      {ids.size === 0 ? (
        <div className="text-body-secondary small">None in this sample.</div>
      ) : (
        <div>
          {[...ids].slice(0, 200).map((id) => {
            const n = nodesById.get(id);
            return (
              <button key={id} type="button" className={styles.neighborBtn} onClick={() => focusNode(id)}>
                <span className={styles.swatch} style={{ background: colorFor(n?.label) }} />
                <span className="text-truncate">{n?.name ?? id}</span>
              </button>
            );
          })}
          {ids.size > 200 && <div className="text-body-secondary small">…and {ids.size - 200} more</div>}
        </div>
      )}
    </div>
  );

  return (
    <div>
      <div className={styles.toolbar}>
        <h2 className="h5 mb-0 me-auto">{config?.title ?? rel}</h2>
        <label className="d-flex align-items-center gap-2 small mb-0" htmlFor="graph-limit">
          Relationship limit
          <select
            id="graph-limit"
            className="form-select form-select-sm w-auto"
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
          >
            {GRAPH_LIMIT_OPTIONS.map((value) => <option key={value} value={value}>{value.toLocaleString()}</option>)}
          </select>
        </label>
      </div>

      {config?.pedagogical && (
        <div className="alert alert-light border small d-flex flex-wrap justify-content-between gap-2">
          <span>Teaching graph: approved metadata includes automatic estimates, not necessarily human review. Missing relationships are an enrichment gap, not inferred prerequisites.</span>
          <label className="form-check">
            <input type="checkbox" className="form-check-input" checked={reviewedOnly} onChange={(event) => setReviewedOnly(event.target.checked)} />
            Approved only
          </label>
          {!reviewedOnly && <strong className="text-warning-emphasis">Inventory view includes unreviewed assertions; do not treat them as teaching facts.</strong>}
        </div>
      )}

      {error && (
        <div className="alert alert-danger d-flex align-items-center justify-content-between gap-2" role="alert">
          <span>Could not load view: {error}</span>
          <button type="button" className="btn btn-sm btn-outline-danger" onClick={() => setReloadKey((k) => k + 1)}>
            Retry
          </button>
        </div>
      )}

      {data && (
        <div className={styles.metrics}>
          <div className={styles.metric}>
            <div className={styles.metricLabel}>Nodes in sample</div>
            <div className={styles.metricValue}>{graphData.nodes.length.toLocaleString()}</div>
          </div>
          <div className={styles.metric}>
            <div className={styles.metricLabel}>Relationships in sample</div>
            <div className={styles.metricValue}>{sampled.toLocaleString()}</div>
          </div>
          <div className={styles.metric}>
            <div className={styles.metricLabel}>Total {config?.type ?? ""} relationships</div>
            <div className={styles.metricValue}>{typeof total === "number" ? total.toLocaleString() : "—"}</div>
          </div>
          <div className={styles.metric}>
            <div className={styles.metricLabel}>Coverage</div>
            <div className={styles.metricValue}>
              {coverage === null ? "—" : `${coverage}%`}
              {data.truncated && <span className="badge text-bg-warning ms-2 align-middle" style={{ fontSize: "0.7rem" }}>sampled</span>}
            </div>
          </div>
        </div>
      )}

      <div className={`${styles.workspace} ${selected ? "" : styles.workspaceNoPanel}`}>
        <div ref={wrapRef} className={styles.canvasWrap}>
          {loading && (
            <div className={styles.canvasOverlay} role="status">
              <span className="spinner-border text-primary" aria-hidden="true" />
              <span>Loading graph…</span>
            </div>
          )}
          {isEmpty && (
            <div className={styles.canvasOverlay}>
              <strong>No relationships found</strong>
              <span className="small">This view has no {config?.type ?? rel} relationships in the corpus yet.</span>
            </div>
          )}
          {data && !isEmpty && (
            <>
              <div className={styles.controls} role="toolbar" aria-label="Graph controls">
                <button type="button" className={styles.controlBtn} onClick={() => zoomBy(ZOOM_STEP)} title="Zoom in" aria-label="Zoom in">+</button>
                <button type="button" className={styles.controlBtn} onClick={() => zoomBy(1 / ZOOM_STEP)} title="Zoom out" aria-label="Zoom out">−</button>
                <button type="button" className={styles.controlBtn} onClick={fit} title="Fit graph to view">Fit</button>
                <button type="button" className={styles.controlBtn} onClick={togglePause} title={paused ? "Resume animation" : "Pause animation"}>
                  {paused ? "Resume" : "Pause"}
                </button>
                <button type="button" className={styles.controlBtn} onClick={resetView} title="Clear selection and re-run layout">Reset</button>
              </div>
              <div className={styles.legend} aria-label="Node legend">
                {legend.map(([label, count]) => (
                  <span key={label} className={styles.legendItem}>
                    <span className={styles.swatch} style={{ background: colorFor(label) }} />
                    {label} <span style={{ color: "#64748b" }}>({count.toLocaleString()})</span>
                  </span>
                ))}
              </div>
              {size.width > 0 && size.height > 0 && (
                <ForceGraphCanvas
                  graphRef={graphRef}
                  graphData={graphData}
                  width={size.width}
                  height={size.height}
                  nodeLabel={(n) => `${n.label}: ${n.name}${n.properties?.approval_method === "automatic" || n.properties?.pedagogy_approval_method === "automatic" ? " (automatically approved)" : n.properties?.review_status ? ` (${n.properties.review_status})` : ""}`}
                  nodeColor={(n) => (highlightIds && !highlightIds.has(n.id) ? DIM_COLOR : colorFor(n.label))}
                  nodeVal={(n) => (n.id === selectedId ? 4 : 1)}
                  nodeRelSize={4}
                  linkColor={(l) =>
                    highlightIds
                      ? endpointId(l.source) === selectedId || endpointId(l.target) === selectedId
                        ? "#475569"
                        : "rgba(203, 213, 225, 0.25)"
                      : "#cbd5e1"
                  }
                  linkWidth={(l) =>
                    selectedId && (endpointId(l.source) === selectedId || endpointId(l.target) === selectedId) ? 1.5 : 0.5
                  }
                  linkDirectionalArrowLength={selectedId ? 3 : 0}
                  linkDirectionalArrowRelPos={1}
                  cooldownTicks={200}
                  onEngineStop={onEngineStop}
                  onNodeClick={(n) => setSelectedId(n.id)}
                  onBackgroundClick={() => setSelectedId(null)}
                />
              )}
            </>
          )}
        </div>

        {selected && (
          <aside className={styles.panel} aria-label="Node details">
            <div className="d-flex align-items-start justify-content-between gap-2 mb-2">
              <div>
                <span className="badge rounded-pill" style={{ background: colorFor(selected.label), color: "#fff" }}>
                  {selected.label}
                </span>
                <h3 className="h6 mt-2 mb-1" style={{ wordBreak: "break-word" }}>{selected.name}</h3>
              </div>
              <button type="button" className={styles.controlBtn} aria-label="Close details" onClick={() => setSelectedId(null)}>
                ×
              </button>
            </div>
            <div className="small text-body-secondary mb-1">Canonical ID</div>
            <div className={`${styles.mono} mb-3`}>{selected.id}</div>
            {selected.label === "Problem" && selected.properties?.canonical_code && (
              <Link className="btn btn-sm btn-outline-primary mb-3" href={`/learn?problem=${encodeURIComponent(selected.properties.canonical_code)}`}>Practice with hints</Link>
            )}
            <h4 className="h6">Metadata</h4>
            {Object.keys(selected.properties || {}).length ? (
              <dl className="small">
                {Object.entries(selected.properties).map(([key, value]) => (
                  <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd style={{ overflowWrap: "anywhere" }}>{String(value)}</dd></div>
                ))}
              </dl>
            ) : <p className="small text-secondary">No additional metadata recorded.</p>}
            <div className="small mb-3">
              Degree in sample: <strong>{(selectedAdj?.out.size ?? 0) + (selectedAdj?.in.size ?? 0)}</strong>
            </div>
            {renderNeighbors(`Outgoing → ${config?.to ?? ""}`, selectedAdj?.out ?? new Set())}
            {renderNeighbors(`Incoming ← ${config?.from ?? ""}`, selectedAdj?.in ?? new Set())}
            <h4 className="h6">Relationship evidence</h4>
            {graphData.links.filter((link) => endpointId(link.source) === selectedId || endpointId(link.target) === selectedId).slice(0, 30).map((link, index) => (
              <div className="border rounded-3 p-2 small mb-2" key={index}>
                <strong>{link.type || config?.type}</strong>
                <div>{nodesById.get(endpointId(link.source))?.name} → {nodesById.get(endpointId(link.target))?.name}</div>
                {Object.entries(link.properties || {}).map(([key, value]) => <div key={key}>{key.replaceAll("_", " ")}: {String(value)}</div>)}
                {!Object.keys(link.properties || {}).length && <span className="text-secondary">Provenance not recorded.</span>}
              </div>
            ))}
            <p className="small text-secondary">Showing up to 30 incident relationships.</p>
            <div className="small text-body-secondary">Neighbors are limited to the loaded sample.</div>
          </aside>
        )}
      </div>
    </div>
  );
}
