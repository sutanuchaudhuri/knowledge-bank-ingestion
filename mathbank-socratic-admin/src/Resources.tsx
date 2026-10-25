import { useEffect, useState } from "react";
import { api } from "./api";
import type { Program, Resource, Source } from "./contracts";
import { MathText, Pager, Pill } from "./ui";

export function Resources({ disabled, canAttach, onAttach, onError, program, onPreview }: {
  disabled: boolean; canAttach: boolean; onAttach: (source: Source) => void; onError: (error: unknown) => void;
  program: Program | null; onPreview: (key: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [resources, setResources] = useState<Resource[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  const [selected, setSelected] = useState<Resource | null>(null);
  const [solution, setSolution] = useState("");
  const [route, setRoute] = useState("");
  const [activityPage, setActivityPage] = useState(0);
  const [kind, setKind] = useState("");
  const [topic, setTopic] = useState("");
  const activities = program?.nodes.filter(node => (!kind || node.type === kind) && (!topic || node.topic === topic)) || [];
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setFailed(false); setSelected(null);
    api.request<{ resources: Resource[]; has_more: boolean }>(
      `/resources?q=${encodeURIComponent(search)}&limit=25&offset=${page * 25}`, { signal: controller.signal },
    ).then(data => {
      setResources(data.resources.slice(0, 25)); setHasMore(data.has_more);
    }).catch(error => {
      if (!controller.signal.aborted) { setFailed(true); onError(error); }
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [search, page, retry, onError]);
  return <section className="sc-stack">
    <section className="sc-card sc-stack" aria-label="Workflow resource library">
      <div className="sc-toolbar sc-between"><h2>Quizzes, lessons & topics</h2><Pill>Current draft resources</Pill></div>
      <p className="sc-muted">Inspect the activities available to this journey. Starting from a resource creates a new synthetic preview; REST verifies the requested start and prerequisites.</p>
      <div className="sc-config">
        <label>Resource type<select value={kind} onChange={event => { setKind(event.target.value); setActivityPage(0); }}>
          <option value="">All types</option>{[...new Set(program?.nodes.map(node => node.type))].map(value => <option key={value}>{value}</option>)}
        </select></label>
        <label>Resource topic<select value={topic} onChange={event => { setTopic(event.target.value); setActivityPage(0); }}>
          <option value="">All topics</option>{[...new Set(program?.nodes.map(node => node.topic).filter((value): value is string => !!value))].map(value => <option key={value}>{value}</option>)}
        </select></label>
      </div>
      {!activities.length ? <p>No activities in this selection. Open a workflow or change the filters.</p> :
        <div className="sc-strategy-grid">{activities.slice(activityPage * 25, (activityPage + 1) * 25).map(node => <article className="sc-rule sc-stack" key={node.key}>
          <div className="sc-toolbar"><Pill>{node.type}</Pill>{node.topic && <Pill>{node.topic}</Pill>}</div>
          <h3><MathText text={node.label} /></h3><div className="sc-reading"><MathText text={node.prompt} /></div>
          <button disabled={disabled} onClick={() => onPreview(node.key)}>View in simulator · {node.label}</button>
        </article>)}</div>}
      {activities.length > 25 && <Pager page={activityPage} hasMore={(activityPage + 1) * 25 < activities.length} onChange={setActivityPage} />}
    </section>
    <h2>Canonical source library</h2>
    <form className="sc-toolbar" onSubmit={event => { event.preventDefault(); setPage(0); setSearch(query.trim()); setRetry(value => value + 1); }}>
      <label className="sc-grow">Find a source problem<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Problem code or statement" /></label>
      <button className="sc-primary" disabled={loading}>Search</button>
    </form>
    <p className="sc-callout">One source workflow: choose a problem, its explicit reference solution revision and an optional released route. This links existing step-authoring sources; it does not generate, verify or publish atomic steps.</p>
    <div className="sc-master-detail">
      <section className="sc-card" aria-label="Source problems" aria-busy={loading}>
        {loading ? <p role="status">Loading source problems…</p> : failed ? <button onClick={() => setRetry(value => value + 1)}>Retry resource search</button> : resources.length === 0 ? <p>No matching source problems.</p> :
          <div className="sc-stack">{resources.map(resource => <button className="sc-resource" key={resource.problem_id}
            aria-label={`Select source ${resource.canonical_code}`}
            aria-pressed={selected?.problem_id === resource.problem_id}
            onClick={() => { setSelected(resource); setSolution(""); setRoute(""); }}>
            <strong>{resource.canonical_code}</strong>
            <span className="sc-resource-preview"><MathText text={resource.statement_text} /></span>
            <span className="sc-muted">{resource.solutions.length} reference solutions · {resource.routes.length} routes</span>
          </button>)}</div>}
        <Pager page={page} hasMore={hasMore && !failed} onChange={setPage} disabled={loading || disabled} />
      </section>
      <section className="sc-card sc-stack" aria-label="Source reference selection">
        <h2>Source & step-authoring references</h2>
        {!selected ? <p>Select a problem to inspect available source references.</p> : <>
          <Pill>{selected.canonical_code}</Pill><div className="sc-reading"><MathText text={selected.statement_text} /></div>
          <label>Reference solution revision<select value={solution} onChange={event => { setSolution(event.target.value); setRoute(""); }} disabled={disabled}>
            <option value="">Select explicitly…</option>
            {selected.solutions.map(item => <option key={item.solution_id} value={item.solution_id}>Revision {item.revision} · {item.verification_status} · {item.solution_id}</option>)}
          </select></label>
          <label>Released route reference (optional)<select value={route} onChange={event => setRoute(event.target.value)} disabled={disabled}>
            <option value="">No released route reference</option>
            {selected.routes.filter(item => !item.solution_id || item.solution_id === solution).map(item => <option key={item.route_release_id} value={item.route_release_id} disabled={item.status !== "PUBLISHED"}>
              {item.approach_name} · {item.status} · {item.route_release_id}
            </option>)}
          </select></label>
          <p className="sc-muted">Source verification is not pedagogical approval. Route/solution compatibility must be validated by REST; this catalog does not prove compatibility.</p>
          <button className="sc-primary" disabled={disabled || !canAttach || !solution} onClick={() => onAttach({
            problem_code: selected.canonical_code, solution_id: solution,
            solution_revision: selected.solutions.find(item => item.solution_id === solution)!.revision,
            route_release_id: route || null,
          })}>Use references in current draft</button>
          {!canAttach && <p>Open or create a workflow in Designer before attaching references.</p>}
        </>}
      </section>
    </div>
  </section>;
}
