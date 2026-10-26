import { useEffect, useState } from "react";
import { api } from "./api";
import type { Program, Resource, Source, Strategy } from "./contracts";
import { typeIcons, typeNames } from "./narrative";
import { Empty, Hero, Icon, MathText, Pager, Pill, Segmented } from "./ui";

type Tab = "strategies" | "sources" | "steps";

export function Library({ strategies, program, domain, disabled, onError, onUseStrategy, onStartFrom, onAttach, onPreview }: {
  strategies: Strategy[]; program: Program | null; domain: string; disabled: boolean; onError: (error: unknown) => void;
  onUseStrategy: (strategy: Strategy) => void; onStartFrom: (strategy: Strategy) => void;
  onAttach: (source: Source) => void; onPreview: (key: string) => void;
}) {
  const [tab, setTab] = useState<Tab>(() => window.location.hash === "#library-sources" ? "sources" : "strategies");
  return <div className="sc-canvas-inner">
    <Hero kicker="Library" title="Templates & sources" description="Start from a teaching strategy, link a canonical source, or preview a step." />
    <Segmented label="Library section" value={tab} onChange={setTab} options={[
      { value: "strategies", label: "Strategies", icon: "grid" },
      { value: "sources", label: "Sources", icon: "database" },
      { value: "steps", label: "Steps", icon: "list-check" },
    ]} />
    {tab === "strategies" && <Strategies strategies={strategies} domain={domain} canUse={!!program} disabled={disabled} onUse={onUseStrategy} onStart={onStartFrom} />}
    {tab === "sources" && <Sources canAttach={!!program} disabled={disabled} onError={onError} onAttach={onAttach} />}
    {tab === "steps" && <Steps program={program} disabled={disabled} onPreview={onPreview} />}
  </div>;
}

function Strategies({ strategies, domain, canUse, disabled, onUse, onStart }: {
  strategies: Strategy[]; domain: string; canUse: boolean; disabled: boolean; onUse: (s: Strategy) => void; onStart: (s: Strategy) => void;
}) {
  const [filter, setFilter] = useState(domain);
  const [page, setPage] = useState(0);
  const shown = strategies.filter(item => !filter || item.domain === filter);
  return <>
    <div className="sc-chips" role="group" aria-label="Strategy domain">
      {["", ...new Set(strategies.map(item => item.domain))].map(value => <button type="button" key={value || "all"} aria-pressed={filter === value}
        className={`sc-chip${filter === value ? " sc-active" : ""}`} onClick={() => { setFilter(value); setPage(0); }}>{value || "All domains"}</button>)}
    </div>
    {!shown.length ? <Empty icon="grid">No strategies in this domain.</Empty> : <div className="sc-cards">
      {shown.slice(page * 24, (page + 1) * 24).map(item => <article key={item.code} className="sc-card">
        <div className="sc-row sc-space"><strong>{item.label}</strong><Pill>{item.status}</Pill></div>
        <span className="sc-sub">{item.domain} · <code>{item.code}</code></span>
        <div className="sc-chips sc-chips-quiet">{item.phases.map(phase => <span key={phase} className="sc-chip-static">{phase}</span>)}</div>
        <div className="sc-row">
          {canUse && item.domain === domain && <button type="button" className="sc-light" disabled={disabled} onClick={() => onUse(item)}>Use in this workflow</button>}
          <button type="button" className="sc-light" disabled={disabled} onClick={() => onStart(item)}>Start new workflow</button>
        </div>
      </article>)}
    </div>}
    <Pager page={page} hasMore={(page + 1) * 24 < shown.length} onChange={setPage} />
  </>;
}

function Sources({ canAttach, disabled, onError, onAttach }: {
  canAttach: boolean; disabled: boolean; onError: (error: unknown) => void; onAttach: (source: Source) => void;
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
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setFailed(false); setSelected(null);
    api.request<{ resources: Resource[]; has_more: boolean }>(
      `/resources?q=${encodeURIComponent(search)}&limit=25&offset=${page * 25}`, { signal: controller.signal },
    ).then(data => { setResources(data.resources.slice(0, 25)); setHasMore(data.has_more); })
      .catch(error => { if (!controller.signal.aborted) { setFailed(true); onError(error); } })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [search, page, retry, onError]);
  return <>
    <form className="sc-search-box sc-search-wide" role="search" onSubmit={event => { event.preventDefault(); setPage(0); setSearch(query.trim()); setRetry(value => value + 1); }}>
      <Icon name="search" /><input className="sc-search" aria-label="Find a source problem" placeholder="Problem code or statement…" value={query} onChange={event => setQuery(event.target.value)} />
    </form>
    {selected ? <div className="sc-student-box sc-form" aria-label="Source reference selection">
      <div className="sc-row sc-space"><strong>{selected.canonical_code}</strong>
        <button type="button" className="sc-light" onClick={() => setSelected(null)}><Icon name="arrow-left" />Back to results</button></div>
      <div className="sc-reading"><MathText text={selected.statement_text} /></div>
      <label>Reference solution revision<select value={solution} disabled={disabled} onChange={event => { setSolution(event.target.value); setRoute(""); }}>
        <option value="">Choose explicitly…</option>
        {selected.solutions.map(item => <option key={item.solution_id} value={item.solution_id}>Revision {item.revision} · {item.verification_status}</option>)}
      </select></label>
      <label>Released route (optional)<select value={route} disabled={disabled || !solution} onChange={event => setRoute(event.target.value)}>
        <option value="">No released route</option>
        {selected.routes.filter(item => !item.solution_id || item.solution_id === solution).map(item =>
          <option key={item.route_release_id} value={item.route_release_id} disabled={item.status !== "PUBLISHED"}>{item.approach_name} · {item.status}</option>)}
      </select></label>
      <p className="sc-tiny">Linking a source is not pedagogical approval; the server checks compatibility when you save.</p>
      <button type="button" className="sc-primary" disabled={disabled || !canAttach || !solution} onClick={() => onAttach({
        problem_code: selected.canonical_code, solution_id: solution,
        solution_revision: selected.solutions.find(item => item.solution_id === solution)!.revision, route_release_id: route || null,
      })}>Use in current draft</button>
      {!canAttach && <p className="sc-tiny">Open a workflow first.</p>}
    </div> : <section aria-label="Source problems" aria-busy={loading}>
      {loading ? <p className="sc-tiny" role="status">Loading source problems…</p>
        : failed ? <button type="button" className="sc-light" onClick={() => setRetry(value => value + 1)}>Retry</button>
        : !resources.length ? <Empty icon="database">No matching source problems.</Empty>
        : resources.map(resource => <button type="button" key={resource.problem_id} className="sc-list-row" aria-label={`Select source ${resource.canonical_code}`}
          onClick={() => { setSelected(resource); setSolution(""); setRoute(""); }}>
          <span><strong>{resource.canonical_code}</strong><span className="sc-sub sc-clamp"><MathText text={resource.statement_text} /></span></span>
          <span className="sc-tiny">{resource.solutions.length} solutions · {resource.routes.length} routes</span>
        </button>)}
      <Pager page={page} hasMore={hasMore && !failed} onChange={setPage} disabled={loading || disabled} />
    </section>}
  </>;
}

function Steps({ program, disabled, onPreview }: { program: Program | null; disabled: boolean; onPreview: (key: string) => void }) {
  const [page, setPage] = useState(0);
  if (!program) return <Empty icon="list-check">Open a workflow to preview its steps.</Empty>;
  return <>
    {program.nodes.slice(page * 25, (page + 1) * 25).map(node => <div key={node.key} className="sc-list-row sc-static">
      <span className="sc-row"><span className="sc-glyph"><Icon name={typeIcons[node.type] || "circle"} /></span>
        <span><strong><MathText text={node.label} /></strong><span className="sc-sub">{typeNames[node.type]}{node.topic ? ` · ${node.topic}` : ""}</span></span></span>
      <button type="button" className="sc-light" disabled={disabled} onClick={() => onPreview(node.key)} aria-label={`View in simulator · ${node.label}`}>
        <Icon name="person-video3" />Preview</button>
    </div>)}
    <Pager page={page} hasMore={(page + 1) * 25 < program.nodes.length} onChange={setPage} />
  </>;
}
