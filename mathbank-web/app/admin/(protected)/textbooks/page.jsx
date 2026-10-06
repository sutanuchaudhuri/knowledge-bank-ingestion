"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API = "/api/rest/admin/textbooks";
const NODE_TYPES = ["CONCEPT", "SUBCONCEPT", "SKILL", "TECHNIQUE", "DOMAIN"];
const STATUS_TONE = { OK: "success", GAP: "danger", UNKNOWN: "warning", PROVENANCE: "secondary" };
const human = (s) => (s ? String(s).replaceAll("_", " ").toLowerCase() : "—");
const num = (n) => (n === null || n === undefined ? "—" : Number(n).toLocaleString());

async function load(path, params = {}, signal) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v !== undefined && v !== null));
  const response = await fetch(`${API}/${path}${qs.size ? `?${qs}` : ""}`, { signal, cache: "no-store" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}

function useLoad(path, params) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const key = JSON.stringify([path, params]);
  useEffect(() => {
    const ctl = new AbortController();
    setState((s) => ({ ...s, loading: true, error: null }));
    load(path, params, ctl.signal)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((e) => e.name !== "AbortError" && setState({ data: null, error: e.message, loading: false }));
    return () => ctl.abort();
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return state;
}

function Pager({ total, limit, offset, onChange }) {
  if (!total) return null;
  return (
    <div className="d-flex align-items-center gap-2 small">
      <span className="text-secondary">{num(offset + 1)}–{num(Math.min(offset + limit, total))} of {num(total)}</span>
      <button type="button" className="btn btn-sm btn-outline-secondary" disabled={offset === 0}
        onClick={() => onChange(Math.max(0, offset - limit))}>‹ Prev</button>
      <button type="button" className="btn btn-sm btn-outline-secondary" disabled={offset + limit >= total}
        onClick={() => onChange(offset + limit)}>Next ›</button>
    </div>
  );
}

function Status({ loading, error }) {
  if (error) return <div className="alert alert-danger">{error}</div>;
  if (loading) return <div className="spinner-border spinner-border-sm text-primary" role="status" aria-label="Loading" />;
  return null;
}

function Coverage() {
  const { data, error, loading } = useLoad("coverage", {});
  if (!data) return <Status loading={loading} error={error} />;
  const m = Object.fromEntries(data.matrix.map((r) => [r.entity, r]));
  const cards = [
    ["Problems", m.problem], ["Solutions", m.solution], ["Solution steps", m.solution_step],
    ["Transformations", m.learning_item], ["Taxonomy nodes", m.taxonomy_node], ["Diagrams", m.diagram],
  ];
  const gaps = data.matrix.filter((r) => r.status === "GAP" || r.status === "UNKNOWN");
  return (
    <>
      <div className="row g-3 mb-4" data-testid="coverage-cards">
        {cards.map(([label, r]) => (
          <div className="col-6 col-md-4 col-xl-2" key={label}>
            <div className="card shadow-sm border-0 h-100">
              <div className="card-body">
                <div className="small text-secondary">{label}</div>
                <div className="fs-4 fw-semibold">{num(r?.postgres)}</div>
                <div className="small text-secondary">source {num(r?.source_rows)}</div>
                <span className={`badge text-bg-${STATUS_TONE[r?.status] || "secondary"}`}>{r?.status}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
      {gaps.length > 0 && (
        <div className="alert alert-warning small" data-testid="coverage-gaps">
          <strong>Coverage gaps:</strong>{" "}
          {gaps.map((g) => `${human(g.entity)} (${g.gaps.join(", ")})`).join(" · ")}
          {!data.graph_ok && <> · Neo4j not observed ({data.graph_error})</>}
        </div>
      )}
      <div className="card shadow-sm border-0 mb-4">
        <div className="card-header bg-white fw-semibold">Coverage matrix — source CSV vs Postgres vs pgvector vs Neo4j</div>
        <div className="table-responsive">
          <table className="table table-sm align-middle mb-0 small" data-testid="coverage-matrix">
            <thead><tr><th>Entity</th><th className="text-end">Source rows</th><th className="text-end">Postgres</th>
              <th className="text-end">Vectors</th><th className="text-end">Graph</th><th>Expected in</th><th>Status</th><th>Note</th></tr></thead>
            <tbody>
              {data.matrix.map((r) => (
                <tr key={r.entity}>
                  <td className="fw-semibold">{human(r.entity)}</td>
                  <td className="text-end">{num(r.source_rows)}</td>
                  <td className="text-end">{num(r.postgres)}</td>
                  <td className={`text-end ${r.gaps.includes("vector") ? "text-danger fw-semibold" : ""}`}>{num(r.vector)}</td>
                  <td className={`text-end ${r.gaps.includes("graph") ? "text-danger fw-semibold" : ""}`}>{num(r.graph)}</td>
                  <td>{r.expected.join(" · ") || "—"}</td>
                  <td><span className={`badge text-bg-${STATUS_TONE[r.status]}`}>{r.status}</span></td>
                  <td className="text-secondary">{r.note || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card-footer bg-white small text-secondary">
          Source rows are summed across both packages before de-duplication; see requirements/24 for why Postgres can be
          lower (duplicate ids, repeated chapter/section rows, ambiguous step dependencies).
        </div>
      </div>
      <div className="row g-4">
        <div className="col-xl-8">
          <div className="card shadow-sm border-0">
            <div className="card-header bg-white fw-semibold">Per chapter</div>
            <div className="table-responsive">
              <table className="table table-sm table-hover align-middle mb-0 small" data-testid="chapter-table">
                <thead><tr><th>Ch</th><th>Title</th><th className="text-end">Sections</th><th className="text-end">Problems</th>
                  <th className="text-end">Solutions</th><th className="text-end">Steps</th><th className="text-end">Items</th>
                  <th className="text-end">Diagrams</th><th className="text-end">Embedded</th></tr></thead>
                <tbody>
                  {data.chapters.map((c) => (
                    <tr key={c.chapter_number}>
                      <td>{c.chapter_number}</td><td>{c.chapter_title}</td><td className="text-end">{c.sections}</td>
                      <td className="text-end">{num(c.problems)}</td><td className="text-end">{num(c.solutions)}</td>
                      <td className="text-end">{num(c.steps)}</td><td className="text-end">{num(c.learning_items)}</td>
                      <td className="text-end">{num(c.diagrams)}</td>
                      <td className={`text-end ${c.problems_embedded < c.problems ? "text-danger" : ""}`}>{num(c.problems_embedded)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <div className="col-xl-4">
          <div className="card shadow-sm border-0 mb-4">
            <div className="card-header bg-white fw-semibold">Packages</div>
            <ul className="list-group list-group-flush small">
              {data.packages.map((p) => (
                <li className="list-group-item" key={p.content_package_id}>
                  <div className="fw-semibold">{p.package_name}</div>
                  <span className="badge text-bg-light border me-1">{p.status}</span>
                  <span className="text-secondary">v{p.package_version} · {p.conflicts} conflicts · imported {p.imported_at ? new Date(p.imported_at).toLocaleString() : "—"}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="card shadow-sm border-0">
            <div className="card-header bg-white fw-semibold">Import conflicts</div>
            <table className="table table-sm mb-0 small">
              <tbody>
                {data.conflicts.map((c) => (
                  <tr key={`${c.entity_type}-${c.conflict_type}`}><td>{human(c.entity_type)}</td><td>{human(c.conflict_type)}</td>
                    <td><span className={`badge text-bg-${c.severity === "WARNING" ? "warning" : "light border"}`}>{c.severity}</span></td>
                    <td className="text-end">{c.count}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}

function Problems({ initialNode }) {
  const [filters, setFilters] = useState({ q: "", chapter: "", node: initialNode || "", has_diagram: "", has_solution: "" });
  const [draft, setDraft] = useState(filters);
  const [offset, setOffset] = useState(0);
  useEffect(() => {
    if (initialNode) { setFilters((f) => ({ ...f, node: initialNode })); setDraft((f) => ({ ...f, node: initialNode })); setOffset(0); }
  }, [initialNode]);
  const limit = 50;
  const { data, error, loading } = useLoad("problems", { ...filters, limit, offset });
  const submit = (e) => { e.preventDefault(); setFilters(draft); setOffset(0); };
  return (
    <>
      <form className="row g-2 align-items-end mb-3" onSubmit={submit} data-testid="problem-filters">
        <div className="col-md-3"><label className="form-label small mb-0" htmlFor="pf-q">Search</label>
          <input id="pf-q" className="form-control form-control-sm" placeholder="text, code or 6.76" value={draft.q} onChange={(e) => setDraft({ ...draft, q: e.target.value })} /></div>
        <div className="col-md-1"><label className="form-label small mb-0" htmlFor="pf-ch">Chapter</label>
          <input id="pf-ch" className="form-control form-control-sm" type="number" min="1" max="99" value={draft.chapter} onChange={(e) => setDraft({ ...draft, chapter: e.target.value })} /></div>
        <div className="col-md-3"><label className="form-label small mb-0" htmlFor="pf-node">Taxonomy node</label>
          <input id="pf-node" className="form-control form-control-sm" placeholder="SUBCONCEPT.GEO…" value={draft.node} onChange={(e) => setDraft({ ...draft, node: e.target.value })} /></div>
        <div className="col-md-2"><label className="form-label small mb-0" htmlFor="pf-d">Diagram</label>
          <select id="pf-d" className="form-select form-select-sm" value={draft.has_diagram} onChange={(e) => setDraft({ ...draft, has_diagram: e.target.value })}>
            <option value="">any</option><option value="true">has diagram</option><option value="false">no diagram</option></select></div>
        <div className="col-md-2"><label className="form-label small mb-0" htmlFor="pf-s">Solution</label>
          <select id="pf-s" className="form-select form-select-sm" value={draft.has_solution} onChange={(e) => setDraft({ ...draft, has_solution: e.target.value })}>
            <option value="">any</option><option value="true">has solution</option><option value="false">no solution</option></select></div>
        <div className="col-md-1"><button className="btn btn-sm btn-primary w-100" type="submit">Filter</button></div>
      </form>
      <Status loading={loading && !data} error={error} />
      {data && (
        <div className="card shadow-sm border-0">
          <div className="card-header bg-white d-flex align-items-center">
            <span className="fw-semibold">Problems</span>
            <span className="ms-auto"><Pager total={data.total} limit={limit} offset={offset} onChange={setOffset} /></span>
          </div>
          <div className="table-responsive">
            <table className="table table-sm table-hover align-middle mb-0 small" data-testid="problem-table">
              <thead><tr><th>Source</th><th>Ch.§</th><th>Statement</th><th>Concept / subconcept</th>
                <th className="text-end">Sol</th><th className="text-end">Steps</th><th className="text-end">Items</th>
                <th className="text-end">Diag</th><th>Vec</th></tr></thead>
              <tbody>
                {data.items.map((p) => (
                  <tr key={p.canonical_code}>
                    <td className="text-nowrap"><Link href={`/admin/textbooks/problems/${p.canonical_code}`}>{p.source_problem_id}</Link></td>
                    <td className="text-nowrap">{p.chapter_number}.{p.section_number}</td>
                    <td style={{ maxWidth: 480 }}>{p.statement_preview}</td>
                    <td><div>{p.concept_name}</div><div className="text-secondary">{p.subconcept_name}</div></td>
                    <td className={`text-end ${p.solutions ? "" : "text-danger"}`}>{p.solutions}</td>
                    <td className="text-end">{p.steps}</td><td className="text-end">{p.learning_items}</td>
                    <td className="text-end">{p.diagrams || ""}</td>
                    <td>{p.embedded ? <span className="badge text-bg-success">yes</span> : <span className="badge text-bg-danger">no</span>}</td>
                  </tr>
                ))}
                {data.items.length === 0 && <tr><td colSpan={9} className="text-secondary">No problems match.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}

function LearningItems() {
  const [filters, setFilters] = useState({ transformation_type: "", chapter: "", q: "" });
  const [draft, setDraft] = useState(filters);
  const [offset, setOffset] = useState(0);
  const limit = 50;
  const { data, error, loading } = useLoad("learning-items", { ...filters, limit, offset });
  return (
    <>
      <form className="row g-2 align-items-end mb-3" onSubmit={(e) => { e.preventDefault(); setFilters(draft); setOffset(0); }}>
        <div className="col-md-4"><label className="form-label small mb-0" htmlFor="lf-t">Transformation type</label>
          <select id="lf-t" className="form-select form-select-sm" value={draft.transformation_type} onChange={(e) => setDraft({ ...draft, transformation_type: e.target.value })}>
            <option value="">all types</option>
            {(data?.types || []).map((t) => <option key={t.transformation_type} value={t.transformation_type}>{human(t.transformation_type)} ({num(t.count)})</option>)}
          </select></div>
        <div className="col-md-1"><label className="form-label small mb-0" htmlFor="lf-ch">Chapter</label>
          <input id="lf-ch" className="form-control form-control-sm" type="number" min="1" max="99" value={draft.chapter} onChange={(e) => setDraft({ ...draft, chapter: e.target.value })} /></div>
        <div className="col-md-4"><label className="form-label small mb-0" htmlFor="lf-q">Search</label>
          <input id="lf-q" className="form-control form-control-sm" value={draft.q} onChange={(e) => setDraft({ ...draft, q: e.target.value })} /></div>
        <div className="col-md-1"><button className="btn btn-sm btn-primary w-100" type="submit">Filter</button></div>
      </form>
      <Status loading={loading && !data} error={error} />
      {data && (
        <div className="card shadow-sm border-0">
          <div className="card-header bg-white d-flex align-items-center">
            <span className="fw-semibold">Transformations (learning items)</span>
            <span className="ms-auto"><Pager total={data.total} limit={limit} offset={offset} onChange={setOffset} /></span>
          </div>
          <div className="table-responsive">
            <table className="table table-sm table-hover align-middle mb-0 small" data-testid="item-table">
              <thead><tr><th>Problem</th><th>Type</th><th>Form</th><th>Direction</th><th>Question</th><th>Status</th></tr></thead>
              <tbody>
                {data.items.map((i) => (
                  <tr key={i.learning_item_id}>
                    <td className="text-nowrap"><Link href={`/admin/textbooks/problems/${i.canonical_code}#items`}>{i.source_problem_id}</Link></td>
                    <td>{human(i.transformation_type)}</td><td>{human(i.transformed_form)}</td><td>{human(i.difficulty_direction)}</td>
                    <td style={{ maxWidth: 520 }}>{i.question_preview}</td>
                    <td><span className="badge text-bg-success">{i.review_status}</span>{i.student_visible ? "" : <span className="badge text-bg-secondary ms-1">hidden</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}

function TaxonomyNode({ id, onClose, onProblems }) {
  const { data, error, loading } = useLoad(`taxonomy/${encodeURIComponent(id)}`, {});
  return (
    <div className="card shadow-sm border-0 mb-3" data-testid="taxonomy-detail">
      <div className="card-header bg-white d-flex align-items-center gap-2">
        <span className="fw-semibold">{data?.name || id}</span>
        {data && <span className="badge text-bg-light border">{data.node_type}</span>}
        <button type="button" className="btn-close ms-auto" aria-label="Close" onClick={onClose} />
      </div>
      <div className="card-body small">
        <Status loading={loading} error={error} />
        {data && (
          <>
            <div className="text-secondary mb-2"><code>{data.taxonomy_node_id}</code>{data.parent_name && <> · parent {data.parent_name}</>}
              {data.chapter_number && <> · ch {data.chapter_number}.{data.section_number}</>} · {data.source_basis}</div>
            {data.description && <p>{data.description}</p>}
            {data.children.length > 0 && <p><strong>Children:</strong> {data.children.map((c) => c.name).join(", ")}</p>}
            <h6 className="mt-3">Edges ({data.edges.length})</h6>
            <ul className="list-unstyled mb-3">
              {data.edges.slice(0, 40).map((e, n) => (
                <li key={n}>{e.direction === "out" ? "→" : "←"} <span className="badge text-bg-light border">{human(e.relationship_type)}</span>{" "}
                  {e.direction === "out" ? e.to_name || e.to_node_id : e.from_name || e.from_node_id}
                  {e.confidence !== null && <span className="text-secondary"> · {Number(e.confidence).toFixed(2)}</span>}</li>
              ))}
            </ul>
            <h6>Problems ({data.problems.length}{data.problems.length === 50 ? "+" : ""})</h6>
            <ul className="list-unstyled mb-2">
              {data.problems.slice(0, 15).map((p) => (
                <li key={p.canonical_code}><Link href={`/admin/textbooks/problems/${p.canonical_code}`}>{p.source_problem_id}</Link> <span className="text-secondary">{p.statement_preview}</span></li>
              ))}
            </ul>
            <button type="button" className="btn btn-sm btn-outline-primary" onClick={() => onProblems(data.taxonomy_node_id)}>All problems with this node</button>
          </>
        )}
      </div>
    </div>
  );
}

function Taxonomy({ onProblems }) {
  const [nodeType, setNodeType] = useState("");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState(null);
  const limit = 100;
  const { data, error, loading } = useLoad("taxonomy", { node_type: nodeType, q: query, limit, offset });
  return (
    <div className="row g-4">
      <div className={selected ? "col-xl-7" : "col-12"}>
        <div className="d-flex flex-wrap gap-2 mb-3 align-items-center">
          <div className="btn-group btn-group-sm" role="group" aria-label="Node type">
            <button type="button" className={`btn ${nodeType === "" ? "btn-primary" : "btn-outline-primary"}`} onClick={() => { setNodeType(""); setOffset(0); }}>All</button>
            {NODE_TYPES.map((t) => (
              <button type="button" key={t} className={`btn ${nodeType === t ? "btn-primary" : "btn-outline-primary"}`} onClick={() => { setNodeType(t); setOffset(0); }}>
                {human(t)} {data?.types?.find((x) => x.node_type === t)?.count ?? ""}
              </button>
            ))}
          </div>
          <form className="d-flex gap-2" onSubmit={(e) => { e.preventDefault(); setQuery(q); setOffset(0); }}>
            <input className="form-control form-control-sm" placeholder="name or id" aria-label="Search taxonomy" value={q} onChange={(e) => setQ(e.target.value)} />
            <button className="btn btn-sm btn-primary" type="submit">Search</button>
          </form>
          {data && <span className="ms-auto"><Pager total={data.total} limit={limit} offset={offset} onChange={setOffset} /></span>}
        </div>
        <Status loading={loading && !data} error={error} />
        {data && (
          <div className="card shadow-sm border-0">
            <div className="table-responsive">
              <table className="table table-sm table-hover align-middle mb-0 small" data-testid="taxonomy-table">
                <thead><tr><th>Type</th><th>Name</th><th>Id</th><th className="text-end">Problems</th><th className="text-end">Steps</th><th className="text-end">Edges</th></tr></thead>
                <tbody>
                  {data.items.map((n) => (
                    <tr key={n.taxonomy_node_id} role="button" className={selected === n.taxonomy_node_id ? "table-active" : ""} onClick={() => setSelected(n.taxonomy_node_id)}>
                      <td><span className="badge text-bg-light border">{n.node_type}</span></td>
                      <td>{n.name}</td><td><code className="small">{n.taxonomy_node_id}</code></td>
                      <td className="text-end">{n.problems}</td><td className="text-end">{n.steps}</td><td className="text-end">{n.edges}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
      {selected && <div className="col-xl-5"><TaxonomyNode id={selected} onClose={() => setSelected(null)} onProblems={onProblems} /></div>}
    </div>
  );
}

const TABS = [["coverage", "Coverage"], ["problems", "Problems"], ["items", "Transformations"], ["taxonomy", "Taxonomy"]];

export default function TextbookDashboard() {
  const [tab, setTab] = useState("coverage");
  const [node, setNode] = useState("");
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    if (TABS.some(([k]) => k === p.get("tab"))) setTab(p.get("tab"));
    if (p.get("node")) setNode(p.get("node"));
  }, []);
  const choose = (k) => { setTab(k); window.history.replaceState(null, "", `?tab=${k}`); };
  return (
    <div className="container-fluid py-4 px-lg-5">
      <p className="small mb-2"><Link href="/admin">← Admin</Link></p>
      <h1 className="h3 mb-0">Textbook corpus</h1>
      <div className="text-secondary small mb-3">Prasolov, Problems in Plane Geometry — chapters 1–30 (two packages). Read-only admin view including answers and solution-only diagrams.</div>
      <ul className="nav nav-tabs mb-4" role="tablist">
        {TABS.map(([k, label]) => (
          <li className="nav-item" key={k} role="presentation">
            <button type="button" role="tab" aria-selected={tab === k} className={`nav-link ${tab === k ? "active" : ""}`} onClick={() => choose(k)}>{label}</button>
          </li>
        ))}
      </ul>
      {tab === "coverage" && <Coverage />}
      {tab === "problems" && <Problems initialNode={node} />}
      {tab === "items" && <LearningItems />}
      {tab === "taxonomy" && <Taxonomy onProblems={(id) => { setNode(id); choose("problems"); }} />}
    </div>
  );
}
