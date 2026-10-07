"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Callout, EmptyState, IconButton, PageHeader, Pager, Pill } from "./ui.jsx";
import MathText from "./MathText.jsx";
import { currentAssessment, intervalLabel, isApprovedCurrent, orderedSteps, runtimeErrorMessage, runtimeJson, STEP_TYPES, transcriptionPayload } from "../../lib/attemptMedia.mjs";
import { MAX_MEDIA_BYTES, MEDIA_TYPES } from "../../lib/privateRuntimeProxy.mjs";

const root = "/api/rest/attempt-media/submissions";
const mime = (asset) => asset?.content_type || asset?.mime_type || "";
const assetId = (asset) => asset?.media_asset_id || asset?.asset_id;
const emptyStep = () => ({ ordinal: 1, plain_text: "", latex_text: "", step_type: "OBSERVATION", confidence: 1, evidence_ids: [] });

export default function AttemptMediaWorkspace({ instructor = false }) {
  const [submission, setSubmission] = useState(null);
  const [steps, setSteps] = useState([]);
  const [regions, setRegions] = useState([]);
  const [selected, setSelected] = useState(0);
  const [activeAsset, setActiveAsset] = useState(null);
  const [page, setPage] = useState(1);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [problem, setProblem] = useState("");
  const [listing, setListing] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [access, setAccess] = useState(instructor ? "ready" : "loading");
  const [listStatus, setListStatus] = useState("loading");
  const [listError, setListError] = useState("");
  const [retry, setRetry] = useState(0);
  const [override, setOverride] = useState({ correctness: "UNCERTAIN", why: "", next_action: "", alignment_type: "VALID_ALTERNATE_STEP" });
  const [regionEdit, setRegionEdit] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [drawing, setDrawing] = useState(false);
  const drawStart = useRef(null);
  const [localPreview, setLocalPreview] = useState(null);
  const [evidenceFocus, setEvidenceFocus] = useState(null);
  const player = useRef(null);
  const intervalEnd = useRef(null);
  const previewUrl = useRef(null);
  const current = steps[selected];
  const version = submission?.transcription_version;
  const base = submission ? `${root}/${submission.submission_id}` : null;
  const availableAssets = (submission?.assets || []).filter((a) => !a.purged_at);
  const asset = localPreview ? null : availableAssets.find((a) => assetId(a) === activeAsset) || availableAssets[0];
  const pages = asset?.page_count || 1;
  const originalUrl = asset ? `${base}/assets/${assetId(asset)}/content` : localPreview?.url;
  const sourceType = asset ? mime(asset) : localPreview?.type;
  const linked = current?.evidence_ids || [];
  const highlighted = evidenceFocus || linked;
  const companionEvidence = [...new Map(regions.filter((r) => linked.includes(r.region_id) && r.x_norm != null && r.media_asset_id !== assetId(asset))
    .map((r) => [`${r.media_asset_id}:${r.page_number || 1}`, r])).values()];
  const assessment = current && submission ? currentAssessment(submission, current.step_id, dirty) : null;
  const approved = isApprovedCurrent(submission) && !dirty;

  function hydrate(data) {
    setSubmission(data); setSteps(orderedSteps(data.steps)); setRegions(data.regions || []);
    setDirty(false); setSelected(0); setEvidenceFocus(null);
    setActiveAsset((previous) => data.assets?.some((a) => assetId(a) === previous && !a.purged_at) ? previous : assetId(data.assets?.find((a) => !a.purged_at)));
  }
  async function load(id) { hydrate(await runtimeJson(`${root}/${encodeURIComponent(id)}`)); }
  async function run(fn) {
    setBusy(true); setError(""); setNotice("");
    try { await fn(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setProblem(params.get("problem_ref") || "");
    if (params.get("submission_id")) void run(() => load(params.get("submission_id")));
    return () => { if (previewUrl.current) URL.revokeObjectURL(previewUrl.current); };
  }, []);
  useEffect(() => {
    if (instructor) return;
    let cancelled = false;
    setAccess("loading");
    runtimeJson("/api/rest/learner/me").then((data) => {
      if (!cancelled) setAccess(data?.student_id ? "ready" : "signed-out");
    }).catch((e) => {
      if (!cancelled) {
        setAccess(e.status === 401 || e.status === 403 ? "signed-out" : "error");
        if (e.status !== 401 && e.status !== 403) setError("Student sign-in could not be verified. Try again when the service is available.");
      }
    });
    return () => { cancelled = true; };
  }, [instructor, retry]);
  useEffect(() => {
    let cancelled = false;
    setListStatus("loading"); setListError("");
    runtimeJson(`${root}?limit=25&offset=${offset}`).then((data) => {
      if (!cancelled) {
        const rows = Array.isArray(data) ? data : data?.items || data?.submissions;
        if (!Array.isArray(rows)) throw new Error("Saved submissions could not be loaded. Try again when the service is available.");
        setListing(rows); setHasMore(data.has_more ?? rows.length > 25);
        setListStatus("ready");
      }
    }).catch((e) => {
      if (!cancelled) {
        setListStatus(e.status === 401 || e.status === 403 ? "signed-out" : "error");
        setListError(e.status === 401 || e.status === 403 ? "Sign in is required to view your private submissions." : `Saved submissions are unavailable. ${e.message}`);
        if (e.status === 401 || e.status === 403) setAccess("signed-out");
      }
    });
    return () => { cancelled = true; };
  }, [offset, submission?.submission_id, retry]);

  function persistId(id) {
    const url = new URL(window.location.href);
    url.searchParams.set("submission_id", id);
    window.history.replaceState(null, "", url);
  }
  async function create() {
    if (access !== "ready" || listStatus !== "ready") return;
    const data = await runtimeJson(root, "POST", { problem_ref: problem });
    persistId(data.submission_id); await load(data.submission_id);
  }
  async function upload(file) {
    if (!file) return;
    if (!MEDIA_TYPES.includes(file.type)) { setError("Choose a JPEG, PNG, PDF, or supported short audio/video file."); return; }
    if (file.size > MAX_MEDIA_BYTES) { setError("Choose a file under 20 MB."); return; }
    if (availableAssets.filter((a) => !a.role || a.role === "ORIGINAL").length >= 10) { setError("A submission can hold up to 10 original assets."); return; }
    if (previewUrl.current) URL.revokeObjectURL(previewUrl.current);
    previewUrl.current = URL.createObjectURL(file);
    setLocalPreview({ url: previewUrl.current, type: file.type });
    setActiveAsset(null);
    await run(async () => {
      const response = await fetch(`${base}/assets?filename=${encodeURIComponent(file.name)}&expected_version=${version}`, {
        method: "POST", headers: { "Content-Type": file.type }, body: file, cache: "no-store",
      });
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(runtimeErrorMessage(data?.detail?.code) || (typeof data?.detail === "string" ? data.detail : "Upload failed. Your original file is unchanged."));
      }
      const uploaded = await response.json();
      await load(submission.submission_id); setActiveAsset(assetId(uploaded)); setLocalPreview(null);
      setNotice("Original saved privately. Processing only starts when you choose Transcribe media.");
    });
  }
  function changeSteps(next) { setSteps(next.map((s, i) => ({ ...s, ordinal: i + 1 }))); setDirty(true); }
  function patchStep(patch) { changeSteps(steps.map((s, i) => i === selected ? { ...s, ...patch } : s)); }
  function move(delta) {
    const to = selected + delta;
    if (to < 0 || to >= steps.length) return;
    const next = [...steps]; [next[selected], next[to]] = [next[to], next[selected]];
    changeSteps(next); setSelected(to);
  }
  function merge() {
    const nextStep = steps[selected + 1];
    if (!nextStep) return;
    const next = [...steps];
    next.splice(selected, 2, { ...current,
      plain_text: [current.plain_text, nextStep.plain_text].filter(Boolean).join("\n"),
      latex_text: [current.latex_text, nextStep.latex_text].filter(Boolean).join("\n"),
      confidence: Math.min(current.confidence ?? 1, nextStep.confidence ?? 1),
      evidence_ids: [...new Set([...linked, ...(nextStep.evidence_ids || [])])],
    });
    changeSteps(next);
  }
  function split() {
    const splitText = (text = "") => {
      const at = text.indexOf("\n");
      return at >= 0 ? [text.slice(0, at), text.slice(at + 1)] : [text, ""];
    };
    const [plain, restPlain] = splitText(current.plain_text);
    const [latex, restLatex] = splitText(current.latex_text);
    const next = [...steps]; next.splice(selected, 1, { ...current, plain_text: plain, latex_text: latex },
      { ...emptyStep(), plain_text: restPlain, latex_text: restLatex, evidence_ids: [...linked] });
    changeSteps(next);
  }
  function selectStep(index) {
    setSelected(index); setEvidenceFocus(null);
    const evidence = regions.filter((r) => steps[index]?.evidence_ids?.includes(r.region_id));
    const spatial = evidence.find((r) => r.x_norm != null);
    const temporal = evidence.find((r) => r.start_ms != null);
    const chosen = temporal || spatial;
    if (chosen) { setActiveAsset(chosen.media_asset_id); setPage(chosen.page_number || 1); }
    if (temporal) {
      intervalEnd.current = temporal.end_ms / 1000;
      // Wait for a different selected media element to mount before seeking.
      setTimeout(() => {
        if (player.current) {
          player.current.currentTime = temporal.start_ms / 1000;
          player.current.play().catch(() => {});
        }
      }, 0);
    }
  }
  function selectRegion(region) {
    const index = steps.findIndex((s) => s.evidence_ids?.includes(region.region_id));
    if (index >= 0) setSelected(index);
    setEvidenceFocus(null); setRegionEdit({ ...region });
  }
  function newRegion() {
    if (!asset) return;
    setRegionEdit({
      region_id: crypto.randomUUID(), media_asset_id: assetId(asset), region_type: sourceType?.startsWith("audio/") || sourceType?.startsWith("video/") ? "SPEECH" : "MATH_LINE", reading_order: regions.length + 1, confidence: 1,
      ...(sourceType?.startsWith("audio/") || sourceType?.startsWith("video/")
        ? { start_ms: Math.round((player.current?.currentTime || 0) * 1000), end_ms: Math.round((player.current?.currentTime || 0) * 1000) + 1000 }
        : { page_number: page, x_norm: 0.1, y_norm: 0.1, width_norm: 0.3, height_norm: 0.1 }),
    });
  }
  function saveRegion() {
    const spatial = regionEdit.x_norm != null;
    if (spatial && (!Number.isInteger(regionEdit.page_number) || regionEdit.page_number < 1 || regionEdit.page_number > 10)) { setError("Choose a PDF page from 1 to 10."); return; }
    if (spatial && (regionEdit.x_norm < 0 || regionEdit.y_norm < 0 || regionEdit.width_norm <= 0 || regionEdit.height_norm <= 0 || regionEdit.x_norm + regionEdit.width_norm > 1 || regionEdit.y_norm + regionEdit.height_norm > 1)) {
      setError("Keep the rectangle inside the page using coordinates from 0 to 1."); return;
    }
    if (!spatial && (regionEdit.start_ms < 0 || regionEdit.end_ms <= regionEdit.start_ms || regionEdit.end_ms > 120000)) { setError("Choose an increasing timestamp interval within the first two minutes."); return; }
    setRegions((old) => old.some((r) => r.region_id === regionEdit.region_id) ? old.map((r) => r.region_id === regionEdit.region_id ? regionEdit : r) : [...old, regionEdit]);
    if (current) patchStep({ evidence_ids: [...new Set([...linked, regionEdit.region_id])] });
    setDirty(true); setRegionEdit(null);
  }
  function drawPoint(event) {
    const box = event.currentTarget.getBoundingClientRect();
    return { x: Math.max(0, Math.min(1, (event.clientX - box.left) / box.width)), y: Math.max(0, Math.min(1, (event.clientY - box.top) / box.height)) };
  }
  async function action(stage) {
    await runtimeJson(`${base}/${stage}`, "POST", { expected_version: version });
    await load(submission.submission_id);
  }
  async function save() {
    if (steps.some((s) => !s.evidence_ids?.length)) throw new Error("Bind every step to original evidence before saving.");
    if (steps.some((s) => !s.plain_text?.trim() && !s.latex_text?.trim())) throw new Error("Enter text or LaTeX for every step before saving.");
    const result = await runtimeJson(`${base}/transcription`, "PUT", transcriptionPayload(version, steps, regions));
    await load(submission.submission_id);
    setNotice(`Corrections saved${result?.transcription_version ? ` · version ${result.transcription_version}` : ""}. Approve this version before analysis.`);
  }

  return <div>
    <PageHeader icon={instructor ? "clipboard-check" : "file-earmark-richtext"} title={instructor ? "Attempt media review" : "My submitted work"}
      subtitle={instructor ? "Inspect original evidence and preserve a clear review history." : "Review the transcription against your original before submitting it."}
      pills={submission && <><Pill tone={approved ? "success" : "warning"}>{approved ? "Approved attempt" : "Candidate · not submitted"}</Pill><Pill>Version {version}</Pill>{dirty && <Pill tone="warning">Unsaved edits</Pill>}</>}
      actions={submission && <IconButton icon="arrow-clockwise" label="Reload saved submission" disabled={busy || dirty} onClick={() => run(() => load(submission.submission_id))} />} />
    {error && <Callout tone="danger" role="alert" className="mb-3">{error}</Callout>}
    {notice && <Callout tone="success" role="status" className="mb-3">{notice}</Callout>}
    {(access === "signed-out" || listStatus === "signed-out") && <Callout tone="warning" role="alert" className="mb-3" title="Sign in required">
      Your submissions are private. <Link href={`/login?next=${encodeURIComponent("/learn/attempt-media")}`}>Student login</Link>
    </Callout>}
    {listError && listStatus === "error" && <Callout tone="danger" role="alert" className="mb-3">{listError}</Callout>}
    {(listStatus === "error" || access === "error") && <button className="btn btn-outline-secondary mb-3" onClick={() => { setError(""); setRetry(retry + 1); }}>Retry workspace connection</button>}
    {busy && <Callout tone="hint" role="status" className="mb-3"><span className="spinner-border spinner-border-sm me-2" aria-hidden="true" />Saving or processing your submission… Original evidence stays available.</Callout>}
    {!instructor && !submission && <form className="card card-body mb-3" onSubmit={(e) => { e.preventDefault(); void run(create); }}>
      <label className="form-label" htmlFor="attempt-problem">Problem reference</label>
      <div className="d-flex flex-wrap gap-2"><input id="attempt-problem" className="form-control flex-grow-1" value={problem} onChange={(e) => setProblem(e.target.value)} required placeholder="Problem code or ID" />
        <button className="btn btn-primary" disabled={busy || access !== "ready" || listStatus !== "ready"}>Start media submission</button></div>
    </form>}
    {!submission ? <section className="card card-body">
      <h2 className="mb-section-title mb-3">{instructor ? "Student submissions" : "Saved submissions"}</h2>
      {listStatus === "loading" ? <p role="status">Loading saved submissions…</p>
        : listStatus !== "ready" ? null : !listing.length ? <EmptyState>There are no saved submissions to review.</EmptyState> : listing.slice(0, 25).map((item) =>
        <button className="mb-attempt-list-row" key={item.submission_id} onClick={() => run(async () => { persistId(item.submission_id); await load(item.submission_id); })}>
          <span>{item.canonical_code || item.problem_code || item.problem_id || item.submission_id}</span>{instructor && <span>{item.student_id || item.owner_id}</span>}<Pill>{item.status}</Pill>
        </button>)}
      {listStatus === "ready" && <Pager offset={offset} limit={25} hasMore={hasMore} count={Math.min(listing.length, 25)} onPrev={() => setOffset(offset - 25)} onNext={() => setOffset(offset + 25)} />}
    </section> : <>
      <Callout tone="hint" className="mb-3">Transcription preserves your mathematics as written, including mistakes. Low-confidence text is uncertainty, not a mathematical error.</Callout>
      <div className="mb-evidence-workspace">
        <section className="card card-body mb-evidence-original" aria-label="Original media">
          <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
            <h2 className="mb-section-title">Original evidence</h2>
            <Pill>{submission.problem_code || submission.problem_id}</Pill>
          </div>
          <div className="d-flex gap-2 flex-wrap mb-3">
            <label className="btn btn-outline-secondary mb-0">Attach original<input className="visually-hidden" type="file" aria-label="Upload original media" accept={MEDIA_TYPES.join(",")} disabled={busy || dirty} onChange={(e) => { void upload(e.target.files?.[0]); e.target.value = ""; }} /></label>
            <button className="btn btn-primary" disabled={busy || dirty || !availableAssets.length} onClick={() => run(() => action("process"))}>Transcribe media · uses AI</button>
          </div>
          <small className="text-secondary mb-3">Private · up to 10 assets · 20 MB each · 10 PDF pages · 2 minutes of audio/video</small>
          {!!availableAssets.length && <label className="form-label">Original asset<select aria-label="Original asset" className="form-select mt-1" value={assetId(asset) || ""} onChange={(e) => { setLocalPreview(null); setActiveAsset(e.target.value); setPage(1); }}>
            {availableAssets.map((a) => <option key={assetId(a)} value={assetId(a)}>{a.filename || a.original_filename || mime(a)}</option>)}
          </select></label>}
          {originalUrl ? <>
            {sourceType === "application/pdf" && <div className="d-flex gap-2 align-items-center mb-2">
              <IconButton icon="chevron-left" label="Previous PDF page" disabled={page <= 1} onClick={() => setPage(page - 1)} />
              <label>PDF page<input className="form-control" type="number" aria-label="PDF page" min="1" max={pages} value={page} onChange={(e) => setPage(Math.max(1, Math.min(pages, Number(e.target.value))))} /></label>
              <span>of {pages}</span><IconButton icon="chevron-right" label="Next PDF page" disabled={page >= pages} onClick={() => setPage(page + 1)} />
            </div>}
            {sourceType?.startsWith("audio/") || sourceType?.startsWith("video/") ?
              <div>{sourceType.startsWith("audio/") ? <audio key={originalUrl} ref={player} controls src={originalUrl} className="w-100" onTimeUpdate={() => { if (intervalEnd.current != null && player.current.currentTime >= intervalEnd.current) { player.current.pause(); intervalEnd.current = null; } }} />
                : <video key={originalUrl} ref={player} controls src={originalUrl} className="w-100" onTimeUpdate={() => { if (intervalEnd.current != null && player.current.currentTime >= intervalEnd.current) { player.current.pause(); intervalEnd.current = null; } }} />}
                {companionEvidence.map((evidence) => {
                  const companion = availableAssets.find((a) => assetId(a) === evidence.media_asset_id);
                  if (!companion) return null;
                  const source = `${base}/assets/${assetId(companion)}/${mime(companion) === "application/pdf" ? `pages/${evidence.page_number || 1}` : "content"}`;
                  return <div key={`${evidence.media_asset_id}:${evidence.page_number}`} className="mt-3">
                    <Pill className="mb-2">{companion.timestamp_ms != null ? `Video keyframe · ${intervalLabel({ start_ms: companion.timestamp_ms, end_ms: companion.timestamp_ms }).split("–")[0]}` : `Accompanying original · page ${evidence.page_number || 1}`}</Pill>
                    <div className="mb-evidence-canvas">
                      <img src={source} className="mb-source-image" alt="Accompanying original evidence" />
                      {regions.filter((r) => r.media_asset_id === evidence.media_asset_id && (r.page_number || 1) === (evidence.page_number || 1) && r.x_norm != null).map((r) =>
                        <button key={r.region_id} className={`mb-evidence-rectangle${highlighted.includes(r.region_id) ? " selected" : ""}`} aria-label={`Select accompanying evidence region ${r.reading_order || r.region_id}`} title={r.region_type} disabled={busy} onClick={() => selectRegion(r)}
                          style={{ left: `${r.x_norm * 100}%`, top: `${r.y_norm * 100}%`, width: `${r.width_norm * 100}%`, height: `${r.height_norm * 100}%` }} />)}
                    </div>
                  </div>;
                })}
              </div>
              : <><label className="form-label">Zoom<input className="form-range" type="range" aria-label="Original zoom" min="1" max="3" step=".25" value={zoom} onChange={(e) => setZoom(Number(e.target.value))} /></label>
                <div className="mb-evidence-scroll"><div className={`mb-evidence-canvas${drawing ? " is-drawing" : ""}`} style={{ width: `${zoom * 100}%` }}
                  onPointerDown={(e) => { if (!drawing || busy) return; e.preventDefault(); drawStart.current = drawPoint(e); e.currentTarget.setPointerCapture(e.pointerId); }}
                  onPointerUp={(e) => {
                    if (!drawing || !drawStart.current || !asset) return;
                    const end = drawPoint(e), start = drawStart.current; drawStart.current = null; setDrawing(false);
                    if (Math.abs(end.x - start.x) < .01 || Math.abs(end.y - start.y) < .01) return;
                    setRegionEdit({ region_id: crypto.randomUUID(), media_asset_id: assetId(asset), page_number: page,
                      x_norm: Math.min(start.x, end.x), y_norm: Math.min(start.y, end.y), width_norm: Math.abs(end.x - start.x), height_norm: Math.abs(end.y - start.y),
                      region_type: "MATH_LINE", reading_order: regions.length + 1, confidence: 1 });
                  }}>
                  {sourceType === "application/pdf" ? (asset ?
                    <img className="mb-source-image" src={`${base}/assets/${assetId(asset)}/pages/${page}`} alt={`Original PDF page ${page}`} onError={() => setError("This PDF page is unavailable. Open the original or select another page.")} />
                    : <object className="mb-pdf-pending" data={originalUrl} type="application/pdf" aria-label="Original PDF upload preview" />)
                    : <img className="mb-source-image" src={originalUrl} alt="Original submitted work" />}
                  {regions.filter((r) => r.media_asset_id === assetId(asset) && (r.page_number || 1) === page && r.x_norm != null).map((r) =>
                    <button key={r.region_id} className={`mb-evidence-rectangle${highlighted.includes(r.region_id) ? " selected" : ""}`} aria-label={`Select evidence region ${r.reading_order || r.region_id}`} title={`${r.region_type} · ${r.confidence == null ? "Confidence unknown" : `${Math.round(r.confidence * 100)}% confidence`}`}
                      disabled={busy} onClick={() => { if (!drawing) selectRegion(r); }} style={{ left: `${r.x_norm * 100}%`, top: `${r.y_norm * 100}%`, width: `${r.width_norm * 100}%`, height: `${r.height_norm * 100}%` }} />)}
                </div></div></>}
            <div className="d-flex gap-2 flex-wrap mt-3">
              <button className="btn btn-ghost" disabled={!asset || busy} onClick={newRegion}>Add evidence region</button>
              {!sourceType?.startsWith("audio/") && !sourceType?.startsWith("video/") && <button className="btn btn-ghost" disabled={!asset || busy} aria-pressed={drawing} onClick={() => setDrawing(!drawing)}>{drawing ? "Cancel drawing" : "Draw evidence rectangle"}</button>}
              <a className="btn btn-ghost" href={originalUrl} target="_blank" rel="noreferrer">Open original</a>
              {asset && <button className="btn btn-ghost text-danger" disabled={busy || dirty} onClick={() => {
                if (window.confirm("Purge this original media? Approved structured work is retained.")) void run(async () => { await runtimeJson(`${base}/assets/${assetId(asset)}`, "DELETE"); await load(submission.submission_id); });
              }}>Purge original media</button>}
            </div>
          </> : <EmptyState icon="file-earmark-image">Attach an original, or enter a faithful transcription manually.</EmptyState>}
          {drawing && <Callout tone="hint" className="mt-2">Drag over the original to draw a region, or use Add evidence region for keyboard coordinate entry.</Callout>}
          {regionEdit && <fieldset disabled={busy} className="card card-body mt-3"><legend className="mb-section-title">Evidence coordinates</legend>
            <small className="text-secondary mb-2">Spatial coordinates are fractions of the original page; temporal coordinates are exact milliseconds.</small>
            {(regionEdit.x_norm != null ? ["page_number", "x_norm", "y_norm", "width_norm", "height_norm"] : ["start_ms", "end_ms"]).map((field) =>
              <label key={field} className="form-label">{field.replace(/_/g, " ")}<input type="number" className="form-control" step={field.endsWith("_norm") ? ".01" : "1"} value={regionEdit[field] ?? ""} onChange={(e) => setRegionEdit({ ...regionEdit, [field]: Number(e.target.value) })} /></label>)}
            <div className="d-flex gap-2"><button className="btn btn-outline-primary" onClick={saveRegion}>Apply and bind evidence</button><button className="btn btn-ghost" onClick={() => setRegionEdit(null)}>Cancel</button></div>
          </fieldset>}
        </section>
        <section className="card card-body" aria-label="Editable transcription">
          <div className="d-flex justify-content-between align-items-center mb-3"><h2 className="mb-section-title">{approved ? "Approved transcription" : "Candidate transcription"}</h2>
            <IconButton icon="plus-lg" label="Add missing step" disabled={busy} onClick={() => { changeSteps([...steps, emptyStep()]); setSelected(steps.length); }} /></div>
          {!steps.length && <EmptyState icon="pencil">Transcribe the original, or add a missing step.</EmptyState>}
          <div className="mb-attempt-step-list">
            {steps.map((s, index) => {
              const evidence = regions.filter((r) => s.evidence_ids?.includes(r.region_id));
              const result = currentAssessment(submission, s.step_id, dirty);
              return <button key={s.step_id || `new-${index}`} className={`mb-attempt-list-row${selected === index ? " selected" : ""}`} aria-label={`Select step ${index + 1}`} aria-pressed={selected === index} onClick={() => selectStep(index)}>
                <span>Step {index + 1}<span className="d-flex flex-wrap gap-1 mt-1"><Pill>{s.step_type}</Pill>
                  {s.confidence != null && <Pill title="Transcription confidence, not a correctness score">{Math.round(s.confidence * 100)}% transcription</Pill>}
                  {s.confidence == null || s.confidence < .8 ? <Pill tone="warning">Check transcription</Pill> : null}
                  {evidence.map((r) => <Pill key={r.region_id}>{r.start_ms != null ? intervalLabel(r) : `Page ${r.page_number || 1} · region ${r.reading_order || ""}`}</Pill>)}
                  {result && <Pill tone={result.correctness === "CORRECT" ? "success" : result.correctness === "UNCERTAIN" ? "warning" : "danger"}>{result.correctness.replace(/_/g, " ")}</Pill>}</span>
                  <span className="d-block mt-2">{s.plain_text || s.latex_text || "Empty step"}</span></span>
              </button>;
            })}
          </div>
          {current && <fieldset disabled={busy} className="mt-3">
            <h3 className="mb-section-title mb-2">Edit step {selected + 1}</h3>
            {(current.confidence == null || current.confidence < .8) && <Callout tone="warning" className="mb-3">Check the original. Uncertain recognition does not mean your reasoning is wrong.</Callout>}
            {current.source_plain_text && <details className="mb-2"><summary>Machine candidate (unchanged)</summary><p>{current.source_plain_text}</p><pre>{current.source_latex_text}</pre></details>}
            <label className="form-label w-100">Step text<textarea aria-label="Step text" className="form-control" value={current.plain_text || ""} onChange={(e) => patchStep({ plain_text: e.target.value })} /></label>
            <label className="form-label w-100">LaTeX transcription<textarea aria-label="LaTeX transcription" className="form-control" value={current.latex_text || ""} onChange={(e) => patchStep({ latex_text: e.target.value })} /></label>
            {current.latex_text && <div className="mb-3"><MathText>{`$$${current.latex_text}$$`}</MathText></div>}
            <label className="form-label w-100">Step type<select aria-label="Step type" className="form-select" value={current.step_type || "OBSERVATION"} onChange={(e) => patchStep({ step_type: e.target.value })}>
              {STEP_TYPES.map((type) => <option key={type} value={type}>{type.replace(/_/g, " ")}</option>)}</select></label>
            <fieldset className="mb-3"><legend className="mb-section-title mb-2">Bind original evidence</legend>
              {regions.map((r) => <label key={r.region_id} className="d-block"><input type="checkbox" className="form-check-input me-2" checked={linked.includes(r.region_id)}
                onChange={(e) => patchStep({ evidence_ids: e.target.checked ? [...linked, r.region_id] : linked.filter((id) => id !== r.region_id) })} />
                {r.start_ms != null ? intervalLabel(r) : `Page ${r.page_number || 1} · region ${r.reading_order}`}<button className="btn btn-ghost btn-sm" type="button" aria-label={`Edit evidence ${r.reading_order || r.region_id}`} onClick={() => setRegionEdit({ ...r })}>Edit</button></label>)}
            </fieldset>
            <div className="d-flex flex-wrap gap-1 mb-3">
              <IconButton icon="arrow-up" label="Move step up" disabled={selected === 0} onClick={() => move(-1)} />
              <IconButton icon="arrow-down" label="Move step down" disabled={selected === steps.length - 1} onClick={() => move(1)} />
              <button className="btn btn-ghost" disabled={selected === steps.length - 1} onClick={merge}>Merge with next</button>
              <button className="btn btn-ghost" onClick={split} title="Split at the first newline; review the new row and its evidence">Split step</button>
              <button className="btn btn-ghost" onClick={() => patchStep({ step_type: "QUESTION_OR_UNCERTAINTY", confidence: 0, plain_text: current.plain_text || "[unreadable]" })}>Mark unreadable</button>
              <IconButton icon="trash" label="Delete step" onClick={() => { changeSteps(steps.filter((_, i) => i !== selected)); setSelected(Math.max(0, selected - 1)); }} />
            </div>
            {assessment && <Callout tone={assessment.correctness === "CORRECT" ? "success" : "hint"} title={assessment.correctness.replace(/_/g, " ")}>
              <p>{assessment.why}</p><p className="mb-0">{assessment.next_action}</p>
              <div className="d-flex flex-wrap gap-1 mt-2">{regions.filter((r) => assessment.evidence_ids?.includes(r.region_id)).map((r) =>
                <button key={r.region_id} className="btn btn-ghost btn-sm" onClick={() => {
                  setEvidenceFocus(assessment.evidence_ids); setActiveAsset(r.media_asset_id); setPage(r.page_number || 1);
                  if (r.start_ms != null) setTimeout(() => {
                    if (player.current) { intervalEnd.current = r.end_ms / 1000; player.current.currentTime = r.start_ms / 1000; player.current.play().catch(() => {}); }
                  }, 0);
                }}>Show cited evidence · {r.start_ms != null ? intervalLabel(r) : `page ${r.page_number || 1}, region ${r.reading_order}`}</button>)}</div>
              {assessment.alignment_type && <Pill className="mt-2">{assessment.alignment_type.replace(/_/g, " ")}</Pill>}
              {assessment.confidence != null && assessment.confidence < .8 && <Pill tone="warning" className="mt-2">Assessment uncertain</Pill>}
            </Callout>}
          </fieldset>}
          {dirty && <Callout tone="warning" className="mb-3">Edits hide the previous assessment. Save, approve the new version, then request fresh analysis.</Callout>}
          <div className="d-flex flex-wrap gap-2 mt-3">
            {dirty ? <><button className="btn btn-primary" disabled={busy} onClick={() => run(save)}>Save transcription edits</button>
              <button className="btn btn-ghost" disabled={busy} onClick={() => { if (window.confirm("Discard unsaved corrections?")) void run(() => load(submission.submission_id)); }}>Discard unsaved edits</button></>
              : !approved ? (instructor ? <Pill tone="warning">Awaiting student approval</Pill> : <button className="btn btn-primary" disabled={busy || !steps.length || steps.some((s) => !s.evidence_ids?.length)} onClick={() => run(() => action("approve"))}>Approve transcription as my submitted attempt</button>)
                : <button className="btn btn-primary" disabled={busy} onClick={() => run(() => action("analyse"))}>Analyse approved attempt · uses AI</button>}
          </div>
          {!!steps.length && steps.some((s) => !s.evidence_ids?.length) && <small className="text-secondary mt-2">Bind every step to original evidence before approving.</small>}
          {instructor && current?.step_id && approved && <form className="card card-body mt-3" onSubmit={(e) => { e.preventDefault(); void run(async () => {
            await runtimeJson(`${base}/override`, "POST", { expected_version: version, step_id: current.step_id, ...override }); await load(submission.submission_id); setNotice("Instructor decision added to review history.");
          }); }}>
            <h3 className="mb-section-title mb-3">Instructor override</h3>
            <label className="form-label">Correctness<select aria-label="Correctness" className="form-select" value={override.correctness} onChange={(e) => setOverride({ ...override, correctness: e.target.value })}>
              {["CORRECT", "PARTIALLY_CORRECT", "INCORRECT", "UNJUSTIFIED", "UNCERTAIN"].map((v) => <option key={v}>{v}</option>)}</select></label>
            <label className="form-label">Alignment<select aria-label="Alignment" className="form-select" value={override.alignment_type} onChange={(e) => setOverride({ ...override, alignment_type: e.target.value })}>
              {["VALID_ALTERNATE_STEP", "MATCHES_SOLUTION_STEP", "PARTIAL_STEP", "PREREQUISITE_STEP", "IRRELEVANT_STEP", "UNSUPPORTED_LEAP", "UNMATCHED_BUT_PLAUSIBLE"].map((v) => <option key={v}>{v}</option>)}</select></label>
            <label className="form-label">Why<textarea aria-label="Why" className="form-control" required value={override.why} onChange={(e) => setOverride({ ...override, why: e.target.value })} /></label>
            <label className="form-label">Next useful action<textarea aria-label="Next useful action" className="form-control" required value={override.next_action} onChange={(e) => setOverride({ ...override, next_action: e.target.value })} /></label>
            <button className="btn btn-outline-primary" disabled={busy}>Record audited override</button>
          </form>}
        </section>
      </div>
      <details className="card card-body mt-3"><summary>Approval and review history</summary>
        {(submission.approvals || []).map((a, i) => <div key={i} className="mt-2"><Pill tone="success">Approved version {a.approved_version ?? a.transcription_version}</Pill></div>)}
        {(submission.assessment_history || submission.assessments || []).map((a, i) => <div key={i} className="mt-2"><Pill>{a.source || "Assessment"}</Pill><Pill>{a.correctness}</Pill> {a.why} {a.next_action}</div>)}
        {(submission.events || []).map((e, i) => <div key={e.sequence || i} className="mt-2"><Pill>{e.event_type || e.type}</Pill> <span className="mb-num">#{e.sequence}</span></div>)}
      </details>
    </>}
  </div>;
}
