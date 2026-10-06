"use client";

import { use, useEffect, useState } from "react";
import { IconButton, PageHeader, TabBar } from "../../../../../_components/ui.jsx";
import Link from "next/link";
import MathText from "../../../../../_components/MathText.jsx";
import { DagReview, ItemReview } from "../../../imports/importsClient.jsx";

const API = "/api/rest/admin/textbooks";
const human = (s) => (s ? String(s).replaceAll("_", " ").toLowerCase() : "—");
const Yes = ({ ok, yes = "yes", no = "no" }) => (
  <span className={`badge text-bg-${ok ? "success" : "danger"}`}>{ok ? yes : no}</span>
);

function Field({ label, children }) {
  if (children === null || children === undefined || children === "") return null;
  return (<><dt className="col-sm-4 text-secondary fw-normal">{label}</dt><dd className="col-sm-8">{children}</dd></>);
}

function NodeChip({ id, names }) {
  if (!id) return null;
  const n = names?.[id];
  return (
    <Link href={`/admin/textbooks?tab=problems&node=${encodeURIComponent(id)}`} className="badge text-bg-light border text-decoration-none me-1 mb-1"
      title={id}>{n?.name || id}</Link>
  );
}

function ProblemTab({ d }) {
  const e = d.enrichment;
  return (
    <div className="row g-4">
      <div className="col-xl-8">
        <div className="card shadow-sm border-0 mb-4">
          <div className="card-header bg-white fw-semibold">Statement</div>
          <div className="card-body" data-testid="problem-statement"><MathText>{d.statement_text}</MathText></div>
        </div>
        {e && (
          <div className="card shadow-sm border-0">
            <div className="card-header bg-white fw-semibold">Concepts &amp; taxonomy</div>
            <div className="card-body">
              <dl className="row small mb-0">
                <Field label="Concept"><NodeChip id={e.concept_node_id} names={{ [e.concept_node_id]: { name: e.concept_name } }} /></Field>
                <Field label="Subconcept"><NodeChip id={e.subconcept_node_id} names={{ [e.subconcept_node_id]: { name: e.subconcept_name } }} /></Field>
                <Field label="Primary skill"><NodeChip id={e.primary_skill_node_id} names={{ [e.primary_skill_node_id]: { name: e.primary_skill_name } }} /></Field>
                <Field label="Step skills">{(e.solution_step_skill_ids || []).map((id) => <NodeChip key={id} id={id} names={d.taxonomy_names} />)}</Field>
                <Field label="Techniques">{(e.technique_ids || []).length
                  ? e.technique_ids.map((id) => <NodeChip key={id} id={id} names={d.taxonomy_names} />)
                  : <span className="text-secondary">none in source</span>}</Field>
                <Field label="Form">{human(e.problem_form)}</Field>
                <Field label="Mapping basis">{e.taxonomy_mapping_basis}{e.taxonomy_confidence != null && ` · confidence ${Number(e.taxonomy_confidence).toFixed(2)}`}</Field>
              </dl>
            </div>
          </div>
        )}
      </div>
      <div className="col-xl-4">
        <div className="card shadow-sm border-0">
          <div className="card-header bg-white fw-semibold">Source</div>
          <div className="card-body">
            <dl className="row small mb-0">
              <Field label="Book">{d.book_code}</Field>
              <Field label="Package">{d.package_name}</Field>
              <Field label="Chapter">{d.chapter_number} — {d.chapter_title}</Field>
              <Field label="Section">{d.section_number} — {d.section_title}</Field>
              <Field label="Problem">{d.source_problem_id}{d.source_printed_problem_id && d.source_printed_problem_id !== d.source_problem_id && ` (printed ${d.source_printed_problem_id})`}</Field>
              <Field label="Editorial">{d.source_editorial_marker}</Field>
              <Field label="Numbering">{d.source_numbering_note}</Field>
              <Field label="Pages">{d.source_page_start}{d.source_page_end && d.source_page_end !== d.source_page_start && `–${d.source_page_end}`}</Field>
              <Field label="Difficulty">{d.difficulty_band}{d.difficulty_rank_in_section && ` · rank ${d.difficulty_rank_in_section}/${d.section_problem_count}`}</Field>
              <Field label="Needs diagram">{d.problem_requires_diagram ? "problem" : ""}{d.solution_requires_diagram ? " solution" : ""}</Field>
              <Field label="Answer">{d.official_answer}</Field>
              <Field label="Canonical"><code className="small">{d.canonical_code}</code></Field>
            </dl>
          </div>
        </div>
      </div>
    </div>
  );
}

function StepRow({ s, deps }) {
  const incoming = deps.filter((x) => x.to_step_id === s.solution_step_id && x.relationship_type !== "NEXT");
  return (
    <li className="list-group-item">
      <div className="d-flex gap-2 align-items-start">
        <span className="badge text-bg-primary">{s.global_step_index}</span>
        <div className="flex-grow-1">
          <MathText>{s.step_text}</MathText>
          <div className="small text-secondary mt-1 d-flex flex-wrap gap-1 align-items-center">
            <span className="badge text-bg-light border">{human(s.step_type)}</span>
            {s.tutor_role && <span className="badge text-bg-light border">{human(s.tutor_role)}</span>}
            {s.skill_name && <span className="badge text-bg-info-subtle border" title={s.skill_node_id}>{s.skill_name}</span>}
            {s.is_checkpoint && <span className="badge text-bg-warning">checkpoint</span>}
            {s.hint_level != null && <span>hint L{s.hint_level}</span>}
            <span>· vector <Yes ok={s.embedded} /></span>
            {incoming.length > 0 && <span>· depends on {incoming.map((x) => x.from_step_id.split(".").pop()).join(", ")}</span>}
            <code className="ms-auto small">{s.solution_step_id}</code>
          </div>
        </div>
      </div>
    </li>
  );
}

function SolutionTab({ d }) {
  if (!d.solutions.length) return <div className="alert alert-warning">This problem has no solution in the source package.</div>;
  const rel = d.dependencies.reduce((acc, x) => ({ ...acc, [x.relationship_type]: (acc[x.relationship_type] || 0) + 1 }), {});
  return (
    <div className="row g-4">
      <div className="col-xl-6">
        {d.solutions.map((s) => (
          <div className="card shadow-sm border-0 mb-4" key={s.solution_id}>
            <div className="card-header bg-white d-flex gap-2 align-items-center">
              <span className="fw-semibold">Solution {s.source_solution_id || ""}</span>
              <span className="badge text-bg-light border">{human(s.solution_kind)}</span>
              <span className="ms-auto small">vector <Yes ok={s.embedded} /></span>
            </div>
            <div className="card-body" data-testid="solution-body"><MathText>{s.body_markdown}</MathText></div>
          </div>
        ))}
      </div>
      <div className="col-xl-6">
        <div className="small text-secondary mb-2">
          {d.parts.length} part(s) · {d.vector.steps} steps · dependencies {Object.entries(rel).map(([k, v]) => `${k} ${v}`).join(", ") || "none"}
        </div>
        {d.parts.map((p) => (
          <div className="card shadow-sm border-0 mb-3" key={p.solution_part_id} data-testid="solution-part">
            <div className="card-header bg-white">
              <span className="fw-semibold">Part {p.part_label || p.part_ordinal}</span>
              <span className="small text-secondary ms-2">{p.steps.length} steps{p.source_step_count != null && p.source_step_count !== p.steps.length && ` (source said ${p.source_step_count})`}</span>
            </div>
            <ul className="list-group list-group-flush small">
              {p.steps.map((s) => <StepRow key={s.solution_step_id} s={s} deps={d.dependencies} />)}
            </ul>
          </div>
        ))}
        {d.unassigned_steps.length > 0 && (
          <div className="card border-warning mb-3">
            <div className="card-header">Steps without a part</div>
            <ul className="list-group list-group-flush small">
              {d.unassigned_steps.map((s) => <StepRow key={s.solution_step_id} s={s} deps={d.dependencies} />)}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function ItemsTab({ d }) {
  const [type, setType] = useState("");
  const types = [...new Set(d.learning_items.map((i) => i.transformation_type))];
  const items = d.learning_items.filter((i) => !type || i.transformation_type === type);
  if (!d.learning_items.length) return <div className="alert alert-secondary">No transformations were generated for this problem.</div>;
  return (
    <>
      <div className="btn-group btn-group-sm mb-3 flex-wrap" role="group" aria-label="Transformation type">
        <button type="button" className={`btn ${type === "" ? "btn-primary" : "btn-outline-primary"}`} onClick={() => setType("")}>All {d.learning_items.length}</button>
        {types.map((t) => (
          <button type="button" key={t} className={`btn ${type === t ? "btn-primary" : "btn-outline-primary"}`} onClick={() => setType(t)}>
            {human(t)} {d.learning_items.filter((i) => i.transformation_type === t).length}
          </button>
        ))}
      </div>
      <div className="row g-3" data-testid="item-cards">
        {items.map((i) => (
          <div className="col-xl-6" key={i.learning_item_id}>
            <div className="card shadow-sm border-0 h-100">
              <div className="card-header bg-white d-flex flex-wrap gap-1 align-items-center small">
                <span className="fw-semibold">{human(i.transformation_type)}</span>
                <span className="badge text-bg-light border">{human(i.transformed_form)}</span>
                <span className="badge text-bg-light border">{human(i.difficulty_direction)}</span>
                <ItemReview item={i} />
                <span className="ms-auto">vector <Yes ok={i.embedded} /></span>
              </div>
              <div className="card-body small">
                <MathText>{i.question_text}</MathText>
                {Array.isArray(i.choices) && i.choices.length > 0 && (
                  <ol type="A" className="mt-2">
                    {i.choices.map((c, n) => {
                      const text = typeof c === "string" ? c : c?.text ?? JSON.stringify(c);
                      return <li key={n} className={String(i.correct_answer || "").trim() === text.trim() ? "fw-semibold text-success" : ""}><MathText>{text}</MathText></li>;
                    })}
                  </ol>
                )}
                {i.correct_answer && <div className="mt-2"><span className="text-secondary">Answer:</span> <MathText>{String(i.correct_answer)}</MathText></div>}
                {i.answer_or_solution_seed && (
                  <details className="mt-2"><summary className="text-secondary">Solution seed</summary><MathText>{i.answer_or_solution_seed}</MathText></details>
                )}
                <div className="text-secondary mt-2">
                  {i.target_skill_name && <>skill {i.target_skill_name} · </>}
                  {i.solution_part_label && <>part {i.solution_part_label} · </>}
                  {i.anchor_step_ids?.length > 0 && <>anchored at {i.anchor_step_ids.map((a) => a.split(".").pop()).join(", ")} · </>}
                  {human(i.generation_mode)} · <code>{i.learning_item_id}</code>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

function DiagramsTab({ d }) {
  if (!d.diagrams.length) return <div className="alert alert-secondary">No diagrams for this problem.</div>;
  return (
    <div className="row g-3">
      {d.diagrams.map((g) => (
        <div className="col-md-6 col-xl-4" key={g.diagram_id}>
          <div className="card shadow-sm border-0 h-100">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`${API}/diagrams/${encodeURIComponent(g.source_diagram_id)}/image`} alt={g.source_caption || g.source_diagram_id}
              className="card-img-top p-2 bg-white" style={{ objectFit: "contain", maxHeight: 360 }} data-testid="diagram-image" />
            <div className="card-body small">
              <span className={`badge text-bg-${g.visibility === "STUDENT_PROBLEM" ? "primary" : "secondary"} me-1`}>{human(g.visibility)}</span>
              <span className="badge text-bg-light border me-1">{human(g.usage)}</span>
              <div className="text-secondary mt-1">{g.source_diagram_id}{g.source_pdf_page && ` · page ${g.source_pdf_page}`}{g.source_caption && ` · ${g.source_caption}`}</div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function StoresTab({ d }) {
  const v = d.vector;
  const g = d.graph;
  return (
    <div className="row g-4" data-testid="store-status">
      <div className="col-md-6">
        <div className="card shadow-sm border-0">
          <div className="card-header bg-white fw-semibold">pgvector</div>
          <table className="table table-sm mb-0 small">
            <tbody>
              <tr><td>Problem statement</td><td><Yes ok={v.problem} /></td></tr>
              <tr><td>Solutions embedded</td><td>{v.solutions_embedded} / {d.solutions.length}</td></tr>
              <tr><td>Steps embedded</td><td className={v.steps_embedded < v.steps ? "text-danger" : ""}>{v.steps_embedded} / {v.steps}</td></tr>
              <tr><td>Transformations embedded</td><td className={v.items_embedded < v.items ? "text-danger" : ""}>{v.items_embedded} / {v.items}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
      <div className="col-md-6">
        <div className="card shadow-sm border-0">
          <div className="card-header bg-white fw-semibold">Neo4j</div>
          {!g.ok ? <div className="card-body small text-warning">Graph not observed ({g.error}).</div> : (
            <table className="table table-sm mb-0 small">
              <tbody>
                <tr><td>Problem node</td><td><Yes ok={g.present} /></td></tr>
                <tr><td>Steps reachable via HAS_SOLUTION→HAS_PART→HAS_STEP</td><td className={g.steps < v.steps ? "text-danger" : ""}>{g.steps} / {v.steps}</td></tr>
                {g.edges.map((e) => (
                  <tr key={`${e.type}-${e.label}-${e.direction}`}><td>{e.direction === "out" ? "→" : "←"} {e.type} {e.label}</td><td>{e.count}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

const TABS = [["problem", "Problem"], ["solution", "Solution & steps"], ["items", "Transformations"], ["diagrams", "Diagrams"], ["stores", "Store status"], ["dag", "DAG review"]];

export default function TextbookProblemPage({ params }) {
  const { code } = use(params);
  const [state, setState] = useState({ data: null, error: null });
  const [tab, setTab] = useState("problem");
  useEffect(() => {
    if (window.location.hash === "#items") setTab("items");
    const ctl = new AbortController();
    fetch(`${API}/problems/${encodeURIComponent(code)}`, { signal: ctl.signal, cache: "no-store" })
      .then(async (r) => {
        const body = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(body.error || body.detail || `Request failed (${r.status})`);
        setState({ data: body, error: null });
      })
      .catch((e) => e.name !== "AbortError" && setState({ data: null, error: e.message }));
    return () => ctl.abort();
  }, [code]);
  const d = state.data;
  const counts = d && { solution: d.vector.steps, items: d.learning_items.length, diagrams: d.diagrams.length };
  return (
    <div>
      {state.error && <div className="alert alert-danger">{state.error}</div>}
      {!d && !state.error && <div className="spinner-border spinner-border-sm text-primary" role="status" aria-label="Loading" />}
      {d && (
        <>
          <PageHeader icon="triangle" tone="info" title={`Problem ${d.source_problem_id}`}
            subtitle={`Chapter ${d.chapter_number} · ${d.chapter_title} · §${d.section_number} ${d.section_title}`}
            actions={<IconButton icon="list-ul" label="All textbook problems" variant="outline-secondary" href="/admin/textbooks?tab=problems" />} />
          <TabBar tabs={TABS} value={tab} onChange={setTab} counts={counts} label="Problem sections" />
          {tab === "problem" && <ProblemTab d={d} />}
          {tab === "solution" && <SolutionTab d={d} />}
          {tab === "items" && <div id="items"><ItemsTab d={d} /></div>}
          {tab === "diagrams" && <DiagramsTab d={d} />}
          {tab === "stores" && <StoresTab d={d} />}
          {tab === "dag" && <DagReview code={d.canonical_code} />}
        </>
      )}
    </div>
  );
}
