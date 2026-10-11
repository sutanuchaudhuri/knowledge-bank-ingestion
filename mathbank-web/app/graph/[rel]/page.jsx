"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Callout, IconButton, Pill } from "../../_components/ui.jsx";
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
const LABEL_PILL_TONE = { Problem: "primary", Concept: "info", Skill: "success", Technique: "warning" };

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
  const [mounted, setMounted] = useState(false);

  const graphRef = useRef(null);
  const wrapRef = useRef(null);
  const fittedRef = useRef(false);

  useEffect(() => {
    setMounted(true);
  }, []);

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

  // BUG-4 fix (requirements/50): node size previously ignored real connectivity, so a true
  // hub (e.g. a concept with thousands of edges) rendered identically to a leaf node with
  // one edge — no visual cue to real importance within the current sample. Derived from the
  // same adjacency map already built above; capped and sqrt-scaled so one outlier hub does
  // not visually swamp the rest of the sample.
  const maxDegree = useMemo(() => {
    let max = 1;
    for (const entry of adjacency.values()) max = Math.max(max, entry.out.size + entry.in.size);
    return max;
  }, [adjacency]);
  const degreeVal = useCallback(
    (id) => {
      const entry = adjacency.get(id);
      const degree = entry ? entry.out.size + entry.in.size : 1;
      return 1 + 3 * Math.sqrt(degree / maxDegree);
    },
    [adjacency, maxDegree],
  );

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
  // NGQ-4 (requirements/50 DGAP-1/DGAP-2): a handful of relationship types are near-empty
  // in the underlying corpus (e.g. only 1-2 rows against tens of thousands of candidate
  // nodes) — not a sampling artifact, a real content gap. Surface that honestly instead of
  // rendering what looks like an unexplained, possibly-broken near-blank canvas. The curated
  // taxonomy views (concept/skill hierarchy etc.) are all in the hundreds-to-thousands, so a
  // low absolute threshold safely only catches the genuinely near-empty cases.
  const isSparse = typeof total === "number" && total > 0 && total < 10;

  const formatNumber = useCallback((value) => {
    const num = Number(value);
    if (!Number.isFinite(num)) return "—";
    return mounted ? num.toLocaleString() : String(num);
  }, [mounted]);

  const formatPercent = useCallback((value) => {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    return mounted
      ? `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 })}%`
      : `${value}%`;
  }, [mounted]);

  const renderNeighbors = (title, ids) => (
    <div className="mb-3">
      <div className="fw-semibold small mb-1">{title} ({formatNumber(ids.size)})</div>
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
          {ids.size > 200 && <div className="text-body-secondary small">…and {formatNumber(ids.size - 200)} more</div>}
        </div>
      )}
    </div>
  );

  return (
    <div>
      <div className="d-flex flex-wrap align-items-start justify-content-between gap-2 mb-3">
        <div>
          <h2 className="h5 mb-1">{config?.title ?? rel}</h2>
          <p className="text-secondary small mb-0">Inspect one relationship slice while keeping the graph simulation and evidence intact.</p>
        </div>
        <div className="d-flex flex-wrap gap-2">
          <Pill tone="info" icon="diagram-3">{config?.type ?? rel}</Pill>
          {config?.pedagogical && (
            <Pill tone={reviewedOnly ? "success" : "warning"} icon={reviewedOnly ? "check-circle" : "exclamation-diamond"}>
              {reviewedOnly ? "Approved only" : "Inventory view"}
            </Pill>
          )}
        </div>
      </div>

      <div className={styles.toolbar}>
        <div className="small text-body-secondary me-auto">Adjust the sampled relationship count without changing the underlying graph logic.</div>
        <label className="d-flex align-items-center gap-2 small mb-0" htmlFor="graph-limit">
          Relationship limit
          <select
            id="graph-limit"
            className="form-select form-select-sm w-auto"
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
          >
            {GRAPH_LIMIT_OPTIONS.map((value) => <option key={value} value={value}>{formatNumber(value)}</option>)}
          </select>
        </label>
      </div>

      {config?.pedagogical && (
        <Callout tone={reviewedOnly ? "hint" : "warning"} title="Teaching graph context" className="mb-3">
          <div className="d-flex flex-wrap align-items-start justify-content-between gap-2 small">
            <div className="flex-grow-1">
              Approved metadata includes automatic estimates, not necessarily human review. Missing relationships are an enrichment gap, not inferred prerequisites.
              {!reviewedOnly && <div className="fw-semibold mt-2 text-warning-emphasis">Inventory view includes unreviewed assertions; do not treat them as teaching facts.</div>}
            </div>
            <label className="form-check mb-0">
              <input type="checkbox" className="form-check-input" checked={reviewedOnly} onChange={(event) => setReviewedOnly(event.target.checked)} />
              Approved only
            </label>
          </div>
        </Callout>
      )}

      {error && (
        <Callout tone="danger" role="alert" title="Could not load view" className="mb-3">
          <div className="d-flex flex-wrap align-items-center justify-content-between gap-2">
            <span>Could not load view: {error}</span>
            <button type="button" className="btn btn-sm btn-primary" onClick={() => setReloadKey((k) => k + 1)}>
              Retry
            </button>
          </div>
        </Callout>
      )}

      {data && isSparse && (
        <Callout tone="warning" role="status" title="Sparsely populated" className="mb-3">
          Only {formatNumber(total)} {config?.type ?? ""} relationship{total === 1 ? "" : "s"} exist{total === 1 ? "s" : ""} in the corpus — this is a real content gap, not a sampling or rendering issue.
        </Callout>
      )}

      {data && (
        <div className={styles.metrics}>
          <div className={styles.metric}>
            <div className={styles.metricLabel}>Nodes in sample</div>
            <div className={`${styles.metricValue} mb-num`}>{formatNumber(graphData.nodes.length)}</div>
          </div>
          <div className={styles.metric}>
            <div className={styles.metricLabel}>Relationships in sample</div>
            <div className={`${styles.metricValue} mb-num`}>{formatNumber(sampled)}</div>
          </div>
          <div className={styles.metric}>
            <div className={styles.metricLabel}>Total {config?.type ?? ""} relationships</div>
            <div className={`${styles.metricValue} mb-num`}>{typeof total === "number" ? formatNumber(total) : "—"}</div>
          </div>
          <div className={styles.metric}>
            <div className={styles.metricLabel}>Coverage</div>
            <div className={styles.metricValue}>
              <span className="mb-num">{formatPercent(coverage)}</span>
              {data.truncated && <Pill tone="warning" className="ms-2">sampled</Pill>}
            </div>
          </div>
        </div>
      )}

      <div className={`${styles.workspace} ${selected ? "" : styles.workspaceNoPanel}`}>
        <div ref={wrapRef} className={styles.canvasWrap}>
          {loading && (
            <div className={styles.canvasOverlay} role="status">
              <Callout tone="insight" title="Loading graph">
                <div className="d-flex align-items-center gap-2">
                  <span className="spinner-border spinner-border-sm text-primary" aria-hidden="true" />
                  <span>Fetching the latest relationship sample.</span>
                </div>
              </Callout>
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
                <button type="button" className="btn btn-sm btn-primary" onClick={fit} title="Fit graph to view">
                  Fit
                </button>
                <IconButton icon="plus-lg" label="Zoom in" variant="outline-secondary" size="sm" onClick={() => zoomBy(ZOOM_STEP)} />
                <IconButton icon="dash-lg" label="Zoom out" variant="outline-secondary" size="sm" onClick={() => zoomBy(1 / ZOOM_STEP)} />
                <IconButton
                  icon={paused ? "play-fill" : "pause-fill"}
                  label={paused ? "Resume animation" : "Pause animation"}
                  variant="outline-secondary"
                  size="sm"
                  onClick={togglePause}
                />
                <IconButton icon="arrow-counterclockwise" label="Clear selection and re-run layout" variant="outline-secondary" size="sm" onClick={resetView} />
              </div>
              <div className={styles.legend} aria-label="Node legend">
                {legend.map(([label, count]) => (
                  <span key={label} className={styles.legendItem}>
                    <span className={styles.swatch} style={{ background: colorFor(label) }} />
                    {label} <span className="text-body-secondary mb-num">({formatNumber(count)})</span>
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
                  nodeVal={(n) => (n.id === selectedId ? degreeVal(n.id) + 3 : degreeVal(n.id))}
                  nodeRelSize={4}
                  linkColor={(l) =>
                    highlightIds
                      ? endpointId(l.source) === selectedId || endpointId(l.target) === selectedId
                        ? "#475569"
                        : "rgba(203, 213, 225, 0.25)"
                      : "#94a3b8"
                  }
                  linkWidth={(l) =>
                    selectedId && (endpointId(l.source) === selectedId || endpointId(l.target) === selectedId) ? 1.5 : 0.8
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
                <Pill tone={LABEL_PILL_TONE[selected.label] || "neutral"}>{selected.label}</Pill>
                <h3 className="h6 mt-2 mb-1 text-break">{selected.name}</h3>
              </div>
              <IconButton icon="x-lg" label="Close details" variant="outline-secondary" size="sm" onClick={() => setSelectedId(null)} />
            </div>
            <div className="small text-body-secondary mb-1">Canonical ID</div>
            <div className={`${styles.mono} mb-3`}>{selected.id}</div>
            {selected.label === "Problem" && selected.properties?.canonical_code && (
              <Link className="btn btn-sm btn-primary mb-3" href={`/learn?problem=${encodeURIComponent(selected.properties.canonical_code)}`}>Practice with hints</Link>
            )}
            <h4 className="h6">Metadata</h4>
            {Object.keys(selected.properties || {}).length ? (
              <dl className="small">
                {Object.entries(selected.properties).map(([key, value]) => (
                  <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd className="text-break">{String(value)}</dd></div>
                ))}
              </dl>
            ) : <p className="small text-secondary">No additional metadata recorded.</p>}
            <div className="small mb-3">
              Degree in sample: <strong className="mb-num">{formatNumber((selectedAdj?.out.size ?? 0) + (selectedAdj?.in.size ?? 0))}</strong>
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
