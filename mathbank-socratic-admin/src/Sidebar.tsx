import { useMemo } from "react";
import type { Program, Strategy, WorkflowSummary } from "./contracts";
import { typeIcons } from "./narrative";
import { searchWorkspace } from "./search";
import { Icon, MathText, Pager } from "./ui";

export function Sidebar({ query, setQuery, workflows, strategies, program, activeId, loading, failed, page, hasMore, disabled,
  onPage, onRetry, onOpen, onStep, onStrategy, onNew, onExport }: {
  query: string; setQuery: (value: string) => void; workflows: WorkflowSummary[]; strategies: Strategy[];
  program: Program | null; activeId?: string; loading: boolean; failed: boolean; page: number; hasMore: boolean;
  disabled: boolean; onPage: (page: number) => void; onRetry: () => void; onOpen: (id: string) => void;
  onStep: (key: string) => void; onStrategy: (strategy: Strategy) => void; onNew: () => void; onExport: () => void;
}) {
  const results = useMemo(() => searchWorkspace(query, { workflows, strategies, program }), [query, workflows, strategies, program]);
  const searching = !!query.trim();
  return <aside className="sc-sidebar" id="studio-sidebar" aria-label="Workspace search">
    <div className="sc-sidehead">Socratic Studio</div>
    <div className="sc-search-box">
      <Icon name="search" />
      <input type="search" className="sc-search" placeholder="Search workflows, steps, strategies…" aria-label="Search workspace"
        value={query} onChange={event => setQuery(event.target.value)} />
    </div>
    {searching && <p className="sc-tiny sc-result-count" role="status">{results.total} {results.total === 1 ? "result" : "results"}</p>}
    <div className="sc-micro">Workspaces</div>
    {loading ? <p className="sc-tiny sc-pad" role="status">Loading…</p> : failed ? <button className="sc-topic" onClick={onRetry}><Icon name="arrow-clockwise" />Retry loading drafts</button> :
      !results.domains.length ? <p className="sc-tiny sc-pad">{searching ? "No matching workflows." : "No drafts yet."}</p> :
      results.domains.map(group => <div key={group.domain} role="group" aria-label={group.domain}>
        <div className="sc-domain">{group.domain}</div>
        {group.workflows.map(item => <button key={item.workflow_id} className={`sc-topic${item.workflow_id === activeId ? " sc-active" : ""}`}
          aria-current={item.workflow_id === activeId ? "true" : undefined} disabled={disabled} onClick={() => onOpen(item.workflow_id)}>
          <span className="sc-dot" aria-hidden="true" /><span className="sc-ellipsis"><MathText text={item.title} /></span><small>r{item.revision}</small>
        </button>)}
      </div>)}
    {!searching && <Pager page={page} hasMore={hasMore} onChange={onPage} disabled={disabled || loading} />}
    {searching && results.steps.length > 0 && <>
      <div className="sc-micro">Steps in this workflow</div>
      {results.steps.map(step => <button key={step.key} className="sc-topic sc-hit" onClick={() => onStep(step.key)}>
        <Icon name={typeIcons[step.type] || "circle"} /><span><span className="sc-ellipsis"><MathText text={step.label} /></span>
          <small className="sc-hit-match"><MathText text={step.match} /></small></span>
      </button>)}
    </>}
    {searching && results.strategies.length > 0 && <>
      <div className="sc-micro">Strategy templates</div>
      {results.strategies.slice(0, 8).map(item => <button key={item.code} className="sc-topic" onClick={() => onStrategy(item)}>
        <Icon name="grid" /><span className="sc-ellipsis">{item.label}</span><small>{item.domain}</small>
      </button>)}
    </>}
    <div className="sc-micro">Quick actions</div>
    <button className="sc-topic" disabled={disabled} onClick={onNew}><Icon name="plus-lg" />New workflow</button>
    <button className="sc-topic" disabled={!program} onClick={onExport}><Icon name="download" />Export draft JSON</button>
  </aside>;
}
