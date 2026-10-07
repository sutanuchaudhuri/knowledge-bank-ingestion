"use client";

import { useEffect, useState } from "react";
import { Callout, EmptyState, IconButton, PageHeader, Pager, Pill } from "../_components/ui.jsx";
import MathText from "../_components/MathText.jsx";
import { runtimeJson } from "../../lib/attemptMedia.mjs";
import { svgFrameImage } from "../../lib/artifactFrames.mjs";

const root = "/api/rest/artifacts";
const SUBJECTS = ["GEOMETRY", "ALGEBRA", "COMBINATORICS", "NUMBER_THEORY"];
const title = (text = "") => text.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
const bundleId = (data) => data?.artifact_bundle_id || data?.bundle_id;
const assetId = (data) => data?.artifact_asset_id || data?.asset_id;
const requestId = (data) => data?.artifact_request_id || data?.request_id;
function planTemplate(subject) {
  const equation = { kind: "EQUATION", id: "equation_1", latex: "x+x=2x", reason: "Combine like terms" };
  const templates = {
    GEOMETRY: {
      elements: [{ kind: "POINT", id: "A", x: 100, y: 100, label: "A" }, { kind: "POINT", id: "B", x: 400, y: 300, label: "B" }, { kind: "SEGMENT", id: "AB", start: "A", end: "B" }],
      overlays: [{ id: "focus_AB", caption: "Identify the segment", actions: [{ action: "HIGHLIGHT", targets: ["AB"] }] }],
    },
    ALGEBRA: {
      elements: [equation],
      overlays: [{ id: "combine", caption: "Combine like terms", actions: [{ action: "EMPHASIZE_EQUATION_LINE", targets: ["equation_1"] }] }],
    },
    COMBINATORICS: {
      elements: [{ kind: "NODE", id: "case_1", x: 150, y: 150, label: "Case 1" }, { kind: "NODE", id: "case_2", x: 400, y: 150, label: "Case 2" }],
      overlays: [{ id: "first_case", caption: "Consider the first case", actions: [{ action: "HIGHLIGHT", targets: ["case_1"] }] }],
    },
    NUMBER_THEORY: {
      number_theory_mode: "MODULAR", modulus: 7,
      elements: [{ ...equation, latex: "17\\equiv3\\pmod{7}", reason: "Reduce modulo 7" }],
      overlays: [{ id: "remainder", caption: "Identify the remainder modulo 7", actions: [{ action: "EMPHASIZE_EQUATION_LINE", targets: ["equation_1"] }] }],
    },
  };
  return JSON.stringify(templates[subject], null, 2);
}

function FramePreview({ bundle, frame, compare = false }) {
  const assets = bundle.assets || [];
  const asset = assets.find((a) => assetId(a) === (frame?.artifact_asset_id || frame?.asset_id || frame?.base_asset_id || bundle.base_asset_id))
    || assets.find((a) => a.render_format === "SVG" || a.mime_type === "image/svg+xml") || assets[0];
  const serverFrame = frame?.content_path && Number.isInteger(frame.ordinal) && frame.ordinal >= 0 && frame.ordinal <= 127;
  // Construct the canonical proxy route; never follow arbitrary content_path URLs.
  const url = serverFrame ? `${root}/bundles/${bundleId(bundle)}/frames/${frame.ordinal}/content`
    : asset ? `${root}/bundles/${bundleId(bundle)}/assets/${assetId(asset)}/content` : null;
  const [image, setImage] = useState(null);
  const [latex, setLatex] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false, objectUrl;
    setImage(null); setLatex(""); setError("");
    if (!url) return;
    const controller = new AbortController();
    (async () => {
      const response = await fetch(url, { cache: "no-store", signal: controller.signal });
      if (!response.ok) throw new Error("This artifact asset is unavailable.");
      const type = response.headers.get("content-type") || asset.mime_type;
      if (type?.includes("svg")) {
        const states = (bundle.overlays || bundle.overlay_states || []).filter((o) =>
          frame?.overlay_state_ids?.includes(o.overlay_state_id) || frame?.overlay_ids?.includes(o.overlay_state_id) || frame?.overlay_state_id === o.overlay_state_id);
        const actions = serverFrame ? [] : frame?.actions || frame?.overlays || states.flatMap((o) => o.actions || o.highlight_spec?.actions || []);
        const highlight = getComputedStyle(document.documentElement).getPropertyValue("--mb-primary").trim();
        objectUrl = URL.createObjectURL(svgFrameImage(await response.text(), actions, highlight || "currentColor"));
      } else if (type?.startsWith("image/")) objectUrl = URL.createObjectURL(await response.blob());
      else if (asset.render_format === "LATEX" || type?.startsWith("text/")) setLatex(await response.text());
      else throw new Error("This asset has no supported safe preview.");
      if (!cancelled) setImage(objectUrl || null);
      else if (objectUrl) URL.revokeObjectURL(objectUrl);
    })().catch((e) => { if (!cancelled && e.name !== "AbortError") setError(e.message); });
    return () => { cancelled = true; controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [url, frame, asset, bundle, serverFrame]);
  return <div className="mb-artifact-preview" aria-label={compare ? "Previous visual state" : "Current visual state"}>
    {error ? <Callout tone="warning">{error} The explanation remains available below.</Callout>
      : image ? <img src={image} alt={`${bundle.title} · ${frame?.caption || "Base artifact"}`} />
        : latex ? <MathText>{`$$${latex}$$`}</MathText>
          : url ? <span role="status">Loading visual…</span> : <EmptyState icon="image">No published visual is available.</EmptyState>}
  </div>;
}

export default function ArtifactLibrary({ canGenerate = false }) {
  const [query, setQuery] = useState("");
  const [subject, setSubject] = useState("");
  const [filters, setFilters] = useState({ concept_id: "", theorem_id: "", skill_id: "", difficulty_band: "", asset_type: "" });
  const [items, setItems] = useState([]);
  const [offset, setOffset] = useState(0);
  const [bundle, setBundle] = useState(null);
  const [frameIndex, setFrameIndex] = useState(0);
  const [compare, setCompare] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [searchMode, setSearchMode] = useState("filtered");
  const [boundedResults, setBoundedResults] = useState(null);
  const [supportsOffset, setSupportsOffset] = useState(true);
  const [embeddingProfile, setEmbeddingProfile] = useState(null);
  const [need, setNeed] = useState({ subject: "GEOMETRY", topic: "", title: "", goal_type: "EXPLAIN_CONCEPT" });
  const [plan, setPlan] = useState(planTemplate("GEOMETRY"));
  const [request, setRequest] = useState(null);
  const frames = [...(bundle?.frames || [])].sort((a, b) => (a.ordinal || 0) - (b.ordinal || 0));
  const frame = frames[frameIndex];

  async function run(fn) {
    setError(""); setNotice(""); setBusy(true);
    try { await fn(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function openBundle(id) {
    const path = `${root}/bundles/${encodeURIComponent(id)}`;
    const [data, assetData, manifest] = await Promise.all([
      runtimeJson(path), runtimeJson(`${path}/assets`), runtimeJson(`${path}/frames`),
    ]);
    setBundle({ ...data, ...manifest, assets: assetData.assets || assetData }); setFrameIndex(0);
    const url = new URL(window.location.href); url.searchParams.set("bundle_id", id); window.history.replaceState(null, "", url);
  }
  async function search(next = 0, semantic = false) {
    const profile = semantic ? await requireEmbeddingProfile() : null;
    const payload = { query, ...(semantic ? { generate_embedding: true, model: profile.model, dimensions: profile.dimensions } : {}), ...(subject ? { subject } : {}), ...Object.fromEntries(Object.entries(filters).filter(([, value]) => value)) };
    const path = `${root}/search${semantic ? "/semantic" : ""}`;
    if (next > 0 && boundedResults) {
      setItems(boundedResults.slice(next, next + 26)); setOffset(next); return;
    }
    let result, bounded = !supportsOffset;
    if (!bounded) {
      try { result = await runtimeJson(path, "POST", { ...payload, limit: 26, offset: next }); }
      catch (e) { if (e.status !== 422 || next > 0) throw e; bounded = true; setSupportsOffset(false); }
    }
    if (bounded) result = await runtimeJson(path, "POST", { ...payload, limit: 100 });
    const rows = Array.isArray(result) ? result : result.items || result.bundles || result.results || [];
    setBoundedResults(bounded ? rows : null);
    setItems(bounded ? rows.slice(0, 26) : rows);
    setOffset(next); setSearchMode(semantic ? "semantic" : "filtered");
    if (result.status === "UNAVAILABLE") setNotice("Semantic retrieval is not ready for these filters. Metadata search is still available; no paid indexing was started.");
  }
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("bundle_id")) void run(() => openBundle(params.get("bundle_id")));
    if (params.get("request_id")) void run(async () => setRequest(await runtimeJson(`${root}/requests/${encodeURIComponent(params.get("request_id"))}`)));
    let cancelled = false;
    runtimeJson(`${root}/embedding-profile`).then((data) => { if (!cancelled) setEmbeddingProfile(data); })
      .catch(() => { if (!cancelled) setEmbeddingProfile({ status: "UNAVAILABLE" }); });
    return () => { cancelled = true; };
  }, []);
  async function requireEmbeddingProfile() {
    const profile = await runtimeJson(`${root}/embedding-profile`);
    setEmbeddingProfile(profile);
    if (profile.status !== "AVAILABLE" || !profile.model || !Number.isSafeInteger(profile.dimensions) || profile.dimensions < 1) {
      throw new Error("Semantic retrieval is not configured with a verified embedding model and dimension. Metadata search remains available.");
    }
    return profile;
  }
  async function createRequest() {
    let parsed;
    try { parsed = JSON.parse(plan); } catch { throw new Error("The structured plan must be valid JSON."); }
    const data = await runtimeJson(`${root}/requests`, "POST", { ...parsed, ...need });
    setRequest(data);
    const url = new URL(window.location.href); url.searchParams.set("request_id", requestId(data)); window.history.replaceState(null, "", url);
    setNotice("Request saved. Generation only starts when you explicitly choose Generate.");
  }
  async function findSimilar() {
    const profile = await requireEmbeddingProfile();
    const result = await runtimeJson(`${root}/bundles/${bundleId(bundle)}/similar`, "POST", { limit: 100, model: profile.model, dimensions: profile.dimensions });
    const rows = result.results || result.items || [];
    setBoundedResults(rows); setItems(rows.slice(0, 26)); setOffset(0); setSearchMode("similar");
    if (result.status === "UNAVAILABLE") setNotice("Similar retrieval is not indexed yet. Metadata search is still available; no paid indexing was started.");
  }
  async function indexBundle() {
    if (!window.confirm("Create a semantic search embedding for this artifact? This explicitly uses AI and may incur a charge.")) return;
    const profile = await requireEmbeddingProfile();
    const result = await runtimeJson(`${root}/bundles/${bundleId(bundle)}/index`, "POST", {
      generate_embedding: true, search_text_sha256: bundle.search_text_sha256, model: profile.model, dimensions: profile.dimensions,
    });
    setNotice(result.status === "INDEXED" ? "Artifact indexed for semantic retrieval." : "Indexing requested.");
  }
  function changePage(next) {
    if (searchMode === "similar" && boundedResults) { setItems(boundedResults.slice(next, next + 26)); setOffset(next); }
    else void run(() => search(next, searchMode === "semantic"));
  }
  async function generate() {
    const result = await runtimeJson(`${root}/requests/${requestId(request)}/generate`, "POST", { publish: true });
    const updated = await runtimeJson(`${root}/requests/${requestId(request)}`);
    setRequest(updated);
    const id = bundleId(result.bundle || result) || bundleId(updated);
    if (id) await openBundle(id);
    else setNotice("Generation requested. Refresh the request to check publication.");
  }

  return <div>
    <PageHeader icon="collection" title="Artifact library" subtitle="Find reusable visuals and follow their explanation one frame at a time."
      pills={<Pill icon="shield-check">Validated reusable visuals</Pill>} />
    {error && <Callout tone="danger" role="alert" className="mb-3">{error}</Callout>}
    {notice && <Callout tone="success" role="status" className="mb-3">{notice}</Callout>}
    {busy && <Callout tone="hint" role="status" className="mb-3"><span className="spinner-border spinner-border-sm me-2" aria-hidden="true" />Loading your library…</Callout>}
    <div className="mb-evidence-workspace">
      <section className="card card-body">
        <h2 className="mb-section-title mb-3">Find an artifact</h2>
        <form onSubmit={(e) => { e.preventDefault(); void run(() => search()); }}>
          <label className="form-label w-100">Search library<input aria-label="Search library" maxLength={2000} className="form-control" placeholder="Concept, theorem or topic" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
          <label className="form-label w-100">Subject<select aria-label="Filter artifact subject" className="form-select" value={subject} onChange={(e) => setSubject(e.target.value)}>
            <option value="">All subjects</option>{SUBJECTS.map((s) => <option key={s} value={s}>{title(s)}</option>)}</select></label>
          <details className="mb-3"><summary>More library filters</summary>
            {["concept_id", "theorem_id", "skill_id", "difficulty_band"].map((field) => <label key={field} className="form-label w-100 mt-2">{title(field.replace("_id", ""))}<input maxLength={200} className="form-control" value={filters[field]} onChange={(e) => setFilters({ ...filters, [field]: e.target.value })} /></label>)}
            <label className="form-label w-100">Artifact type<select className="form-select" value={filters.asset_type} onChange={(e) => setFilters({ ...filters, asset_type: e.target.value })}>
              <option value="">All types</option>{["SVG_DIAGRAM", "LATEX_CARD", "FRAME_SEQUENCE", "MANIM_EXPORT_SPEC"].map((v) => <option key={v} value={v}>{title(v)}</option>)}</select></label>
          </details>
          <div className="d-flex flex-wrap gap-2"><button className="btn btn-primary" disabled={busy}>Search metadata</button>
            <button type="button" className="btn btn-ghost" title="Explicitly generate a query embedding when indexed artifacts are available; may incur an AI charge" disabled={busy || !query.trim() || embeddingProfile?.status !== "AVAILABLE"} onClick={() => {
              if (window.confirm("Run semantic search using AI? An embedding may incur a charge; this never runs automatically.")) void run(() => search(0, true));
            }}>Semantic search</button></div>
          {embeddingProfile?.status === "UNAVAILABLE" && <Pill tone="warning" className="mt-2">Semantic model not configured</Pill>}
        </form>
        <div className="mt-3">{items.length ? items.slice(0, 25).map((item) => <button key={bundleId(item)} className={`mb-attempt-list-row${bundleId(bundle) === bundleId(item) ? " selected" : ""}`}
          onClick={() => run(() => openBundle(bundleId(item)))}>
          <span><strong>{item.title}</strong><span className="d-block text-secondary">{item.topic}</span></span><Pill>{title(item.subject)}</Pill>
        </button>) : <EmptyState icon="collection">Search to find a reusable visual.</EmptyState>}</div>
        {boundedResults?.length === 100 && <Pill tone="neutral" className="mt-2">First 100 matches · refine your filters</Pill>}
        <Pager offset={offset} limit={25} count={Math.min(items.length, 25)} hasMore={items.length > 25} loading={busy}
          onPrev={() => changePage(offset - 25)} onNext={() => changePage(offset + 25)} />
      </section>
      <section className="card card-body" aria-label="Artifact detail">
        {bundle ? <>
          <div className="d-flex justify-content-between gap-2 mb-3"><h2 className="mb-section-title">{bundle.title}</h2><Pill tone={bundle.status === "PUBLISHED" ? "success" : "warning"}>{bundle.status}</Pill></div>
          <div className="d-flex gap-2 flex-wrap mb-3"><Pill>{title(bundle.subject)}</Pill><Pill>{bundle.topic}</Pill>{bundle.difficulty_band && <Pill>{bundle.difficulty_band}</Pill>}
            <Pill>Derived instructional visual · not original evidence</Pill></div>
          <FramePreview bundle={bundle} frame={frame} />
          {frame && <Callout tone="insight" className="mt-3" title={`Step ${frame.step_number || frameIndex + 1}`}>{frame.caption || frame.explanation || frame.transcript || "Follow the highlighted focus."}
            {frame.explanation_text && <p className="mb-0 mt-2">{frame.explanation_text}</p>}
            {frame.concept_tag && <Pill className="mt-2">{frame.concept_tag}</Pill>}{frame.hint_tag && <Pill tone="warning" className="mt-2">{frame.hint_tag}</Pill>}
          </Callout>}
          <div className="d-flex align-items-center flex-wrap gap-2 my-3">
            <IconButton icon="chevron-left" label="Previous artifact frame" disabled={!frames.length || frameIndex === 0} onClick={() => setFrameIndex(frameIndex - 1)} />
            <Pill>{frames.length ? `Frame ${frameIndex + 1} / ${frames.length}` : "Base artifact"}</Pill>
            <IconButton icon="chevron-right" label="Next artifact frame" disabled={!frames.length || frameIndex === frames.length - 1} onClick={() => setFrameIndex(frameIndex + 1)} />
            <label className="form-check-label"><input className="form-check-input me-2" type="checkbox" checked={compare} disabled={frameIndex === 0} onChange={(e) => setCompare(e.target.checked)} />Compare previous state</label>
          </div>
          {compare && frameIndex > 0 && <FramePreview bundle={bundle} frame={frames[frameIndex - 1]} compare />}
          {frames.map((f, index) => <button key={f.frame_id || f.ordinal || index} className={`mb-attempt-list-row${frameIndex === index ? " selected" : ""}`} aria-pressed={frameIndex === index} onClick={() => setFrameIndex(index)}>
            <span><Pill>Step {f.step_number || index + 1}</Pill> {f.caption || f.explanation || f.transcript}</span>
          </button>)}
          {(bundle.latex_lines || []).map((line, index) => <div key={line.element_id || index} className="mt-3">
            <button className="btn btn-ghost" onClick={() => {
              const target = frames.findIndex((f) => line.linked_step_id ? f.linked_step_id === line.linked_step_id : f.step_number === line.step_number);
              if (target >= 0) setFrameIndex(target);
            }}>Equation step {line.step_number || index + 1}</button>
            {line.terms?.length ? <div className="d-flex flex-wrap gap-1 align-items-center" aria-label={`Equation ${line.step_number || index + 1}`}>
              {line.terms.map((term) => {
                const actions = (frame?.actions || []).filter((a) => a.targets?.includes(term.id) || a.targets?.includes(line.element_id));
                if (actions.some((a) => a.action === "HIDE") && !actions.some((a) => a.action === "SHOW")) return null;
                const emphasized = actions.some((a) => ["EMPHASIZE_TERM", "EMPHASIZE_EQUATION_LINE", "HIGHLIGHT"].includes(a.action));
                const dimmed = actions.some((a) => a.action === "DIM");
                return <span key={term.id} className={`mb-equation-term${emphasized ? " is-emphasized" : ""}${dimmed ? " is-dimmed" : ""}`}><MathText>{`$${term.latex}$`}</MathText></span>;
              })}
            </div> : <MathText>{`$$${line.latex}$$`}</MathText>}
            <span className="text-secondary">{line.reason}</span>
          </div>)}
          {(frame?.actions || []).filter((a) => a.action === "SHOW_RATIO").map((a, i) => <MathText key={i}>{`$$${a.latex}$$`}</MathText>)}
          {frame?.latex_text && <MathText>{`$$${frame.latex_text}$$`}</MathText>}
          {bundle.summary && <p className="mt-3">{bundle.summary}</p>}
          <details className="mt-3"><summary>Metadata and reuse</summary>
            <dl className="mt-2"><dt>Bundle ID</dt><dd><code>{bundleId(bundle)}</code></dd>
              <dt>Concepts</dt><dd>{(bundle.concept_ids || []).join(", ") || "Not specified"}</dd>
              <dt>Skills</dt><dd>{(bundle.skill_ids || []).join(", ") || "Not specified"}</dd></dl>
            <button className="btn btn-outline-primary" onClick={() => run(async () => { await navigator.clipboard.writeText(window.location.href); setNotice("Reusable library link copied."); })}>Copy reusable link</button>
            <button className="btn btn-ghost ms-2" disabled={busy || embeddingProfile?.status !== "AVAILABLE"} onClick={() => run(findSimilar)}>Find similar artifacts</button>
            {canGenerate && bundle.search_text_sha256 && <button className="btn btn-ghost ms-2" disabled={busy || embeddingProfile?.status !== "AVAILABLE"} onClick={() => run(indexBundle)}>Index artifact for semantic search · uses AI</button>}
          </details>
        </> : <EmptyState icon="image">Choose a result to explore its visual and explanation.</EmptyState>}
      </section>
    </div>
    {canGenerate && <details className="card card-body mt-3"><summary>Request a subject-aware artifact</summary>
      <Callout tone="hint" className="my-3">Save a structured request first. Generation is explicit; no models or indexing run when you browse.</Callout>
      <form onSubmit={(e) => { e.preventDefault(); void run(createRequest); }}>
        <div className="row g-3">
          <label className="form-label col-md-3">Request subject<select aria-label="Request subject" className="form-select" value={need.subject} onChange={(e) => setNeed({ ...need, subject: e.target.value })}>{SUBJECTS.map((s) => <option key={s} value={s}>{title(s)}</option>)}</select></label>
          {["topic", "title", "goal_type"].map((field) => <label key={field} className="form-label col-md-3">{title(field)}<input aria-label={`Artifact ${field.replace(/_/g, " ")}`} className="form-control" required value={need[field]} onChange={(e) => setNeed({ ...need, [field]: e.target.value })} /></label>)}
        </div>
        <label className="form-label w-100 mt-3">Structured plan (JSON)<textarea aria-label="Structured plan (JSON)" className="form-control font-monospace" rows="5" value={plan} onChange={(e) => setPlan(e.target.value)} required /></label>
        <button type="button" className="btn btn-ghost me-2" onClick={() => {
          if (window.confirm("Replace the current plan with a starter for this subject?")) setPlan(planTemplate(need.subject));
        }}>Use {title(need.subject)} starter plan</button>
        <button className="btn btn-outline-primary" disabled={busy}>Save artifact request</button>
      </form>
      {request && <div className="mt-3 d-flex gap-2 flex-wrap align-items-center"><Pill>{request.status || "Request saved"}</Pill>
        {canGenerate ? <button className="btn btn-primary" disabled={busy} onClick={() => run(generate)}>Generate and publish validated artifact</button> : <Pill tone="warning">Generation requires an instructor</Pill>}
        <IconButton icon="arrow-clockwise" label="Refresh artifact request" disabled={busy} onClick={() => run(async () => {
          const updated = await runtimeJson(`${root}/requests/${requestId(request)}`); setRequest(updated); if (bundleId(updated)) await openBundle(bundleId(updated));
        })} /></div>}
    </details>}
  </div>;
}
