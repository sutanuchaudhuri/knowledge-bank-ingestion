"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import MathText from "../../../_components/MathText.jsx";
import { ProblemPreviewCard } from "../../../_components/ProblemPreview.jsx";
import { Callout, EmptyState, Icon, PageHeader, Pager, Pill } from "../../../_components/ui.jsx";

const API = "/api/rest/admin/corpus";
const blank = { statement: "", solution: "", answer: "", diagram_required: false, note: "" };
async function request(path, body, method = "POST", signal) {
  const response = await fetch(API + path, {
    method: body ? method : "GET", signal, cache: "no-store",
    ...(body ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {}),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || result.detail || `Request failed (${response.status})`);
  return result;
}

function TextField({ label, value, onChange, rows = 5, required = true }) {
  return <label className="d-block mb-3"><span className="form-label">{label}</span>
    <textarea className="form-control" aria-label={label} rows={rows} required={required} value={value} onChange={(e) => onChange(e.target.value)} />
  </label>;
}

export default function CorpusAuthoring() {
  const [tab, setTab] = useState("repair");
  const [filters, setFilters] = useState({ competition: "", year: "", paper: "", number: "", q: "", missing_only: true });
  const [applied, setApplied] = useState(filters);
  const [offset, setOffset] = useState(0);
  const [result, setResult] = useState(null);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState(blank);
  const [file, setFile] = useState(null);
  const [side, setSide] = useState("problem");
  const [rights, setRights] = useState(false);
  const [drafts, setDrafts] = useState(null);
  const [draftState, setDraftState] = useState("DRAFT");
  const [draftOffset, setDraftOffset] = useState(0);
  const [editing, setEditing] = useState(null);
  const [reviewNotes, setReviewNotes] = useState({});
  const [theme, setTheme] = useState("");
  const [paid, setPaid] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setResult(null);
    const query = new URLSearchParams({ limit: "20", offset: String(offset), missing_only: String(applied.missing_only) });
    Object.entries(applied).forEach(([key, value]) => { if (key !== "missing_only" && value) query.set(key, value); });
    request(`/problems?${query}`, null, "GET", controller.signal).then(setResult)
      .catch((err) => { if (err.name !== "AbortError") setError(err.message); });
    return () => controller.abort();
  }, [applied, offset, refresh]);
  useEffect(() => {
    const controller = new AbortController();
    setDrafts(null);
    request(`/drafts?state=${draftState}&limit=20&offset=${draftOffset}`, null, "GET", controller.signal).then(setDrafts)
      .catch((err) => { if (err.name !== "AbortError") setError(err.message); });
    return () => controller.abort();
  }, [draftState, draftOffset, refresh]);

  async function action(fn, success) {
    setBusy(true); setError(""); setNotice("");
    try {
      const data = await fn();
      setNotice(typeof success === "function" ? success(data) : success);
      setRefresh((n) => n + 1);
      return data;
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  async function choose(item) {
    await action(async () => {
      const problem = await request(`/problems/${encodeURIComponent(item.canonical_code)}`);
      setSelected(problem); setForm({ ...blank, statement: problem.statement_text });
      setFile(null); setRights(false); setEditing(null);
      return problem;
    }, "Canonical question loaded; changes require review.");
  }
  async function saveText(event) {
    event.preventDefault();
    await action(() => request("/drafts", { ...form, kind: "TEXT_EDIT",
      problem_code: selected.canonical_code, expected_hash: selected.expected_hash }), "Text draft saved for review.");
  }
  async function upload(event) {
    event.preventDefault();
    await action(async () => {
      if (!file || file.size > 5 * 1024 * 1024) throw new Error("Choose a PNG or JPEG up to 5 MB.");
      const encoded = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(",")[1]);
        reader.onerror = () => reject(new Error("Image could not be read."));
        reader.readAsDataURL(file);
      });
      return request("/images", { problem_code: selected.canonical_code, side,
        mime_type: file.type, data_base64: encoded, note: form.note, rights_confirmed: rights,
        expected_hash: selected.expected_hash });
    }, "Image is private until approved. Review its problem/solution classification.");
  }
  async function saveNew(event) {
    event.preventDefault();
    const result = await action(() => editing ? request(`/drafts/${editing.id}`, { ...form, expected_revision: editing.revision }, "PUT")
      : request("/drafts", { ...form, kind: "NEW_PROBLEM" }), "Original practice draft saved; nothing published yet.");
    if (editing && result) setEditing({ ...editing, revision: result.revision });
  }
  async function review(draft, decision) {
    await action(() => request(`/drafts/${draft.draft_id}/review`,
      { decision, note: reviewNotes[draft.draft_id] || "", expected_revision: draft.revision }), (data) => data.state === "APPROVED" && data.canonical_code
      ? `Approved: ${data.canonical_code}. Search embeddings and graph publication were not run.`
      : "Draft rejected. The review record is retained.");
  }

  return <div>
    <PageHeader icon="database" title="Corpus repair & authoring" subtitle="Restore source figures, review question edits, or publish clearly labelled original practice." />
    <div className="d-flex flex-wrap gap-2 mb-4" role="tablist" aria-label="Corpus tools">
      {[["repair", "image", "Repair questions"], ["new", "stars", "New practice"], ["review", "clipboard-check", "Review drafts"]].map(([id, icon, label]) =>
        <button key={id} role="tab" aria-selected={tab === id} className={`btn rounded-pill ${tab === id ? "btn-primary" : "btn-outline-secondary"}`}
          onClick={() => { setTab(id); setError(""); if (id === "new") { setForm(blank); setEditing(null); } }}><Icon name={icon} />{label}</button>)}
    </div>
    {error && <Callout tone="danger" role="alert">{error}<button className="btn btn-sm btn-outline-secondary ms-2" onClick={() => { setError(""); setRefresh((n) => n + 1); }}>Retry</button></Callout>}
    {notice && <Callout tone="success" role="status">{notice}</Callout>}
    {tab === "repair" && <div className="row g-4">
      <section className="col-12 col-xl-6">
        <form className="card card-body mb-3" onSubmit={(event) => { event.preventDefault(); setApplied({ ...filters }); setOffset(0); setError(""); }}>
          <div className="row g-2">
            {[["competition", "Competition code", "AMC10"], ["year", "Year", "2011"], ["paper", "Paper", "A"], ["number", "Problem number", "1"], ["q", "Canonical code", "AIME_1985_Q04"]].map(([key, label, hint]) =>
              <label className="col-6" key={key}><span className="form-label">{label}</span>
                <input className="form-control" value={filters[key]} placeholder={hint} type={["year", "number"].includes(key) ? "number" : "text"}
                  onChange={(e) => setFilters({ ...filters, [key]: e.target.value })} /></label>)}
          </div>
          <label className="form-check my-3"><input className="form-check-input" type="checkbox" checked={filters.missing_only}
            onChange={(e) => setFilters({ ...filters, missing_only: e.target.checked })} />
            <span className="form-check-label">Likely missing required diagrams only</span></label>
          <button className="btn btn-primary" disabled={busy}><Icon name="search" />Find questions</button>
        </form>
        <Callout tone="warning">Detection uses references to figures in the question. No figure does not automatically mean a defect.</Callout>
        {!result ? <p role="status">Loading corpus…</p> : !result.items.length ? <EmptyState icon="image" title="No matching questions" /> :
          result.items.map((item) => <div key={item.canonical_code} className={`card card-body my-3 ${selected?.canonical_code === item.canonical_code ? "border-primary" : ""}`}>
            <div className="d-flex flex-wrap gap-2 mb-2">
              <Pill tone={item.diagram_missing ? "danger" : "info"} icon="image">{item.diagram_missing ? "Likely missing" : `${item.diagram_count} source figures`}</Pill>
              {!item.diagram_required && !item.diagram_count && <Pill>Requirement unknown</Pill>}
            </div>
            <ProblemPreviewCard item={item} revealSolutions={false} />
            <button className="btn btn-outline-primary btn-sm mt-3" disabled={busy} onClick={() => choose(item)}>Edit or upload source</button>
          </div>)}
        <Pager offset={offset} limit={20} count={result?.items.length || 0} hasMore={result?.hasMore}
          loading={busy || !result} onPrev={() => setOffset(offset - 20)} onNext={() => setOffset(offset + 20)} />
      </section>
      <section className="col-12 col-xl-6">
        {!selected ? <EmptyState icon="file-earmark-text" title="Choose a question to repair" /> : <div className="card card-body">
          <h2 className="h5 text-break">{selected.canonical_code}</h2>
          <form onSubmit={saveText}>
            <TextField label="Question Markdown" value={form.statement} onChange={(statement) => setForm({ ...form, statement })} rows={10} />
            <TextField label="Source / repair note" value={form.note} onChange={(note) => setForm({ ...form, note })} rows={2} />
            <button className="btn btn-primary" disabled={busy}>Save text draft</button>
          </form>
          <details className="border rounded-3 p-3 my-3"><summary>Formatted question preview</summary><MathText>{form.statement}</MathText></details>
          <form onSubmit={upload} className="border-top pt-3">
            <h3 className="h6">Upload a source figure</h3>
            <label className="d-block form-label">Figure belongs to
              <select className="form-select mt-1" value={side} onChange={(e) => setSide(e.target.value)}>
                <option value="problem">Question · visible to students after approval</option>
                <option value="solution">Solution · never shown as a question figure</option>
              </select></label>
            <label className="d-block form-label">PNG or JPEG · maximum 5 MB
              <input className="form-control mt-1" type="file" accept="image/png,image/jpeg" required onChange={(e) => setFile(e.target.files?.[0] || null)} /></label>
            <label className="form-check my-3"><input type="checkbox" className="form-check-input" required checked={rights} onChange={(e) => setRights(e.target.checked)} />
              <span className="form-check-label">I have permission to use this source image.</span></label>
            <button className="btn btn-outline-primary" disabled={busy || !rights || !form.note.trim()}>Upload private image draft</button>
          </form>
        </div>}
      </section>
    </div>}
    {tab === "new" && <div className="row g-4">
      <section className="col-12 col-lg-7"><form className="card card-body" onSubmit={saveNew}>
        <h2 className="h5">{editing ? "Edit pending practice draft" : "Author original practice"}</h2>
        <Pill tone="warning" icon="patch-exclamation">Synthetic / nonofficial · solution unverified</Pill>
        <div className="mt-3"><TextField label="New question Markdown" value={form.statement} onChange={(statement) => setForm({ ...form, statement })} rows={8} /></div>
        <TextField label="Worked solution (staff review)" value={form.solution} onChange={(solution) => setForm({ ...form, solution })} rows={8} />
        <label className="d-block mb-3"><span className="form-label">Answer</span><input className="form-control" value={form.answer} onChange={(e) => setForm({ ...form, answer: e.target.value })} /></label>
        <TextField label="Author / provenance note" value={form.note} onChange={(note) => setForm({ ...form, note })} rows={2} />
        <Callout tone="warning">Use a self-contained question. Approval cannot publish a draft requiring an absent diagram.</Callout>
        <button className="btn btn-primary" disabled={busy}>Save practice draft</button>
      </form></section>
      <section className="col-12 col-lg-5"><form className="card card-body" onSubmit={(e) => {
        e.preventDefault(); action(() => request("/generate", { theme, confirm_paid: paid }), "AI draft saved privately. Open Review drafts to inspect, edit and approve.");
      }}>
        <h2 className="h5"><Icon name="stars" />Optional AI draft</h2>
        <TextField label="Theme and constraints" value={theme} onChange={setTheme} />
        <Callout tone="warning">This explicitly calls the configured paid model. No original contest problem is replaced, and no generated draft is published automatically.</Callout>
        <label className="form-check my-3"><input className="form-check-input" type="checkbox" required checked={paid} onChange={(e) => setPaid(e.target.checked)} />
          <span className="form-check-label">I authorize this paid generation request.</span></label>
        <button className="btn btn-outline-primary" disabled={busy || !paid}>{busy ? "Working…" : "Generate private draft"}</button>
      </form><details className="card card-body mt-3"><summary>Formatted question preview</summary><MathText>{form.statement}</MathText></details></section>
    </div>}
    {tab === "review" && <section>
      <div className="d-flex flex-wrap gap-2 mb-3">
        {["DRAFT", "APPROVED", "REJECTED"].map((state) => <button key={state} className={`btn btn-sm ${draftState === state ? "btn-primary" : "btn-outline-secondary"}`}
          onClick={() => { setDraftState(state); setDraftOffset(0); }}>{state === "DRAFT" ? "Pending" : state === "APPROVED" ? "Approved" : "Rejected"}</button>)}
      </div>
      {!drafts ? <p role="status">Loading drafts…</p> : !drafts.items.length ? <EmptyState icon="clipboard-check" title="No drafts in this view" /> :
        drafts.items.map((draft) => <details key={draft.draft_id} className="card card-body mb-3">
          <summary className="d-flex flex-wrap gap-2 align-items-center"><Pill icon={draft.kind === "IMAGE" ? "image" : "file-earmark-text"}>{draft.kind.replaceAll("_", " ")}</Pill>
            <span className="text-break">{draft.canonical_code || "New nonofficial practice"}</span><Pill tone={draft.origin === "AI" ? "warning" : "info"}>{draft.origin}</Pill></summary>
          <div className="mt-3">
            <p>{draft.note}</p>
            {draft.payload.before_statement && <details className="border rounded p-3 mb-3"><summary>Original question</summary><MathText>{draft.payload.before_statement}</MathText></details>}
            {draft.payload.statement && <div className="mb-tutor-problem"><MathText>{draft.payload.statement}</MathText></div>}
            {draft.kind === "IMAGE" && <><Pill tone={draft.payload.side === "solution" ? "warning" : "info"}>{draft.payload.side} figure</Pill>
              <img src={`${API}/drafts/${draft.draft_id}/image`} className="img-fluid d-block my-3" alt="Uploaded figure awaiting staff classification and review" /></>}
            {draft.payload.solution && <details className="border rounded p-3 my-3"><summary>Unverified solution and answer</summary>
              <MathText>{draft.payload.solution}</MathText><MathText>{draft.payload.answer || ""}</MathText></details>}
            {draft.state === "DRAFT" ? <>
              {draft.kind === "NEW_PROBLEM" && <button className="btn btn-outline-secondary mb-3" disabled={busy} onClick={() => {
                setForm({ ...blank, ...draft.payload, note: draft.note }); setEditing({ id: draft.draft_id, revision: draft.revision }); setTab("new");
              }}>Edit this draft</button>}
              <TextField label={`Review note ${draft.draft_id}`} value={reviewNotes[draft.draft_id] || ""} rows={2}
                onChange={(note) => setReviewNotes({ ...reviewNotes, [draft.draft_id]: note })} />
              <div className="d-flex gap-2"><button className="btn btn-primary" disabled={busy || (reviewNotes[draft.draft_id] || "").trim().length < 3} onClick={() => review(draft, "APPROVED")}>Approve & publish</button>
                <button className="btn btn-outline-danger" disabled={busy || (reviewNotes[draft.draft_id] || "").trim().length < 3} onClick={() => review(draft, "REJECTED")}>Reject</button></div>
            </> : <><p className="mt-3">Review: {draft.review_note}</p>
              {draft.canonical_code && <Link href={`/learn?problem=${encodeURIComponent(draft.canonical_code)}`} className="btn btn-outline-secondary">Open practice</Link>}</>}
          </div>
        </details>)}
      <Pager offset={draftOffset} limit={20} count={drafts?.items.length || 0} hasMore={drafts?.hasMore}
        loading={busy || !drafts} onPrev={() => setDraftOffset(draftOffset - 20)} onNext={() => setDraftOffset(draftOffset + 20)} />
    </section>}
  </div>;
}
