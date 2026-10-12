"use client";

import { useState } from "react";
import Link from "next/link";
import { EmptyState, Icon, Pager, Pill, StatCard } from "../_components/ui.jsx";

const PAGE = 12;

export default function PracticeThemes({ items }) {
  const [kind, setKind] = useState("concept");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [offset, setOffset] = useState(0);
  const themes = items.filter((item) => item.kind === kind);
  const rows = themes.filter((item) => item.name.toLowerCase().includes(query.toLowerCase())
    && (status === "all" || (status === "new" ? item.available > 0 && item.attempted === 0
      : status === "remaining" ? item.remaining > 0 : item.available > 0 && item.remaining === 0)));
  const visible = rows.slice(offset, offset + PAGE);
  function update(setter, value) { setter(value); setOffset(0); }

  return <section aria-label="Practice by theme">
    <div className="nav nav-pills gap-2 mb-3" role="tablist" aria-label="Practice theme type">
      {[["concept", "Skills", "bullseye"], ["technique", "Techniques", "tools"]].map(([value, label, icon]) =>
        <button key={value} id={`themes-${value}`} role="tab" aria-selected={kind === value}
          aria-controls="practice-themes" className={`nav-link${kind === value ? " active" : ""}`}
          onClick={() => update(setKind, value)}><Icon name={icon} />{label}
          <span className="ms-2 mb-num">{items.filter((item) => item.kind === value && item.available > 0).length}</span>
        </button>)}
    </div>
    <div id="practice-themes" role="tabpanel" aria-labelledby={`themes-${kind}`}>
      <div className="row g-3 mb-3">
        <div className="col-4"><StatCard icon="collection" label="Themes with practice" value={themes.filter((item) => item.available > 0).length} /></div>
        <div className="col-4"><StatCard icon="circle" label="Not attempted" value={themes.filter((item) => item.available > 0 && item.attempted === 0).length} tone="info" /></div>
        <div className="col-4"><StatCard icon="signpost-split" label="With problems left" value={themes.filter((item) => item.remaining > 0).length} tone="warning" /></div>
      </div>
      <div className="d-flex flex-wrap gap-2 mb-3">
        <input className="form-control flex-grow-1 w-auto" aria-label="Search practice themes"
          placeholder="Find a theme…" value={query} onChange={(event) => update(setQuery, event.target.value)} />
        <select className="form-select w-auto" aria-label="Practice coverage" value={status}
          onChange={(event) => update(setStatus, event.target.value)}>
          <option value="all">All themes</option><option value="new">Not attempted</option>
          <option value="remaining">Problems left</option><option value="covered">All attempted</option>
        </select>
      </div>
      <p className="small text-secondary">Distinct recorded problems, not repeat attempts. “Left” means not attempted—not unsolved. A problem can belong to several themes.</p>
      {visible.length ? <div className="row g-3">
        {visible.map((item) => <div key={`${item.kind}-${item.slug}`} className="col-12 col-lg-6 col-xxl-4">
          <article className="card p-3 h-100" aria-label={item.name}>
            <div className="d-flex justify-content-between align-items-start gap-2 mb-3">
              <h3 className="h6 mb-0"><Icon name={kind === "concept" ? "bullseye" : "tools"} />{item.name}</h3>
              <Pill tone={item.available === 0 ? "neutral" : item.remaining === 0 ? "success" : item.attempted ? "warning" : "info"}>
                {item.available === 0 ? "No practice yet" : item.remaining === 0 ? "All attempted" : item.attempted ? "In progress" : "Not started"}
              </Pill>
            </div>
            <dl className="row text-center mb-2">
              {[["Available", item.available], ["Attempted", item.attempted], ["Left", item.remaining]].map(([label, count]) =>
                <div className="col-4" key={label}><dt className="small text-secondary fw-normal">{label}</dt><dd className="fw-semibold mb-num mb-0">{count}</dd></div>)}
            </dl>
            <div className="mb-bar-track mb-2" role="progressbar" aria-label={`${item.name} practice coverage`}
              aria-valuemin={0} aria-valuemax={item.available || 1} aria-valuenow={item.attempted}
              aria-valuetext={`${item.attempted} of ${item.available} problems attempted`}>
              <div className="mb-bar-fill" style={{ width: `${item.available ? item.attempted / item.available * 100 : 0}%` }} />
            </div>
            {item.available > 0 && <Link className="btn btn-outline-primary btn-sm mt-auto align-self-start"
              href={`/db/problems?${kind}=${encodeURIComponent(item.slug)}`}
              aria-label={`Jump to practice ${item.name}`}><Icon name="signpost-split" />Jump to practice</Link>}
          </article>
        </div>)}
      </div> : <EmptyState icon="search">No themes match this filter.</EmptyState>}
      {rows.length > PAGE && <Pager offset={offset} limit={PAGE} count={visible.length} hasMore={offset + PAGE < rows.length}
        onPrev={() => setOffset(Math.max(0, offset - PAGE))} onNext={() => setOffset(offset + PAGE)} />}
    </div>
  </section>;
}
