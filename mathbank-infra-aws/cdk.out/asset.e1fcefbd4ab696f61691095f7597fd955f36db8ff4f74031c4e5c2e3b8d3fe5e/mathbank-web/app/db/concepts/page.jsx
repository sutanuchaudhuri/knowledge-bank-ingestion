"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { table, masterDetail, panel, input } from "../dbStyles.js";
import Pager from "../Pager.jsx";
import { Callout, EmptyState, Pill } from "../../_components/ui.jsx";

const LIMIT = 25;

function LoadingState({ children }) {
  return (
    <div className="d-flex align-items-center gap-2 text-body-secondary" role="status">
      <span className="spinner-border spinner-border-sm" aria-hidden="true" />
      <span>{children}</span>
    </div>
  );
}

export default function ConceptsPage() {
  const [domain, setDomain] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    setPage(null);
    setError(null);
    const params = new URLSearchParams({ domain, limit: String(LIMIT), offset: String(offset) });
    fetch(`/api/rest/concepts?${params}`)
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`status ${res.status}`))))
      .then(setPage)
      .catch((err) => setError(err.message));
  }, [domain, offset]);

  useEffect(() => {
    if (!selected) return;
    setDetail(null);
    Promise.all([
      fetch(`/api/rest/concepts/${encodeURIComponent(selected.slug)}/problems`).then((r) => r.json()),
      fetch(`/api/rest/concepts/${encodeURIComponent(selected.slug)}/neighbors`).then((r) => r.json()),
    ]).then(([problems, neighbors]) => setDetail({ problems: problems.items, neighbors: neighbors.items }));
  }, [selected]);

  return (
    <div className="d-grid gap-3">
      <div className="card shadow-sm p-3 p-lg-4">
        <input
          className={input} aria-label="Search concept name"
          placeholder="Search concept name…"
          value={domain}
          onChange={(e) => {
            setOffset(0);
            setSelected(null);
            setDomain(e.target.value);
          }}
        />
      </div>

      {error && <Callout tone="danger" role="alert">Could not load concepts: {error}</Callout>}

      <div className={masterDetail}>
        <div className={panel}>
          {!page ? (
            error ? <EmptyState icon="diagram-3">Concepts are unavailable right now.</EmptyState> : <LoadingState>Loading concepts…</LoadingState>
          ) : !page.items.length ? (
            <EmptyState icon="diagram-3">No concepts match this search.</EmptyState>
          ) : (
            <>
              <div className="table-responsive"><table className={table}>
                <thead>
                  <tr>
                    <th className="fw-semibold">Slug</th>
                    <th className="fw-semibold">Name</th>
                    <th className="fw-semibold text-end">Level</th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((c) => (
                    <tr key={c.slug} className={selected?.slug === c.slug ? "table-active" : ""} onClick={() => setSelected(c)}>
                      <td>{c.slug}</td>
                      <td>{c.name}</td>
                      <td className="text-end mb-num">{c.level ?? "–"}</td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
              <Pager
                offset={offset}
                limit={LIMIT}
                hasMore={page.hasMore}
                onPrev={() => setOffset((o) => Math.max(o - LIMIT, 0))}
                onNext={() => setOffset((o) => o + LIMIT)}
              />
            </>
          )}
        </div>

        <div className={panel}>
          {!selected ? (
            <EmptyState icon="diagram-3">Select a concept to see linked problems and related ideas.</EmptyState>
          ) : !detail ? (
            <LoadingState>Loading linked problems and related concepts…</LoadingState>
          ) : (
            <div className="d-grid gap-3">
              <div>
                <h2 className="h5 fw-bold mb-1">{selected.name}</h2>
                <div className="d-flex flex-wrap gap-2">
                  <Pill tone="primary" icon="diagram-3">{selected.slug}</Pill>
                  {selected.level != null && <Pill icon="layers">{selected.level}</Pill>}
                </div>
                {selected.description && <p className="small text-body-secondary mt-3 mb-0">{selected.description}</p>}
              </div>

              <section className="d-grid gap-2">
                <div className="d-flex flex-wrap align-items-center gap-2">
                  <h3 className="h6 fw-bold mb-0">Linked problems</h3>
                  <Pill tone="neutral" icon="file-earmark-text">{detail.problems.length}</Pill>
                  {detail.problems.length > 0 && (
                    <Link href={`/db/problems?concept=${encodeURIComponent(selected.slug)}`} className="btn btn-outline-primary btn-sm ms-sm-auto">
                      view all →
                    </Link>
                  )}
                </div>
                {detail.problems.length ? (
                  <ul className="small mb-0 ps-3">
                    {detail.problems.slice(0, 8).map((p) => (
                      <li key={p.canonical_code}>
                        {p.canonical_code} ({p.competition} {p.year})
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState icon="file-earmark-text">No linked problems are available for this concept yet.</EmptyState>
                )}
              </section>

              <section className="d-grid gap-2">
                <div className="d-flex flex-wrap align-items-center gap-2">
                  <h3 className="h6 fw-bold mb-0">Related concepts</h3>
                  <Pill tone="neutral" icon="bezier2">{detail.neighbors.length}</Pill>
                </div>
                {detail.neighbors.length ? (
                  <ul className="small mb-0 ps-3">
                    {detail.neighbors.map((n, i) => (
                      <li key={i}>
                        {n.direction === "outgoing" ? "→" : "←"} {n.name} ({n.relation_type})
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState icon="bezier2">No related concepts are recorded yet.</EmptyState>
                )}
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
