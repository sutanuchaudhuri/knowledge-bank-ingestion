"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { table, masterDetail, panel } from "../dbStyles.js";
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

export default function TechniquesPage() {
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [problems, setProblems] = useState(null);

  useEffect(() => {
    setPage(null);
    setError(null);
    const params = new URLSearchParams({ limit: String(LIMIT), offset: String(offset) });
    fetch(`/api/rest/techniques?${params}`)
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`status ${res.status}`))))
      .then(setPage)
      .catch((err) => setError(err.message));
  }, [offset]);

  useEffect(() => {
    if (!selected) return;
    setProblems(null);
    fetch(`/api/rest/techniques/${encodeURIComponent(selected.slug)}/problems`)
      .then((r) => r.json())
      .then((data) => setProblems(data.items));
  }, [selected]);

  return (
    <div className="d-grid gap-3">
      {error && <Callout tone="danger" role="alert">Could not load techniques: {error}</Callout>}

      <div className={masterDetail}>
        <div className={panel}>
          {!page ? (
            error ? <EmptyState icon="tools">Techniques are unavailable right now.</EmptyState> : <LoadingState>Loading techniques…</LoadingState>
          ) : !page.items.length ? (
            <EmptyState icon="tools">No techniques are available yet.</EmptyState>
          ) : (
            <>
              <div className="table-responsive"><table className={table}>
                <thead>
                  <tr>
                    <th className="fw-semibold">Slug</th>
                    <th className="fw-semibold">Name</th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((t) => (
                    <tr key={t.slug} className={selected?.slug === t.slug ? "table-active" : ""} onClick={() => setSelected(t)}>
                      <td>{t.slug}</td>
                      <td>{t.name}</td>
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
            <EmptyState icon="tools">Select a technique to see the problems that use it.</EmptyState>
          ) : !problems ? (
            <LoadingState>Loading linked problems…</LoadingState>
          ) : (
            <div className="d-grid gap-3">
              <div>
                <h2 className="h5 fw-bold mb-1">{selected.name}</h2>
                <div className="d-flex flex-wrap gap-2">
                  <Pill tone="primary" icon="tools">{selected.slug}</Pill>
                </div>
                {selected.description && <p className="small text-body-secondary mt-3 mb-0">{selected.description}</p>}
              </div>
              <section className="d-grid gap-2">
                <div className="d-flex flex-wrap align-items-center gap-2">
                  <h3 className="h6 fw-bold mb-0">Linked problems</h3>
                  <Pill tone="neutral" icon="file-earmark-text">{problems.length}</Pill>
                  {problems.length > 0 && (
                    <Link href={`/db/problems?technique=${encodeURIComponent(selected.slug)}`} className="btn btn-outline-primary btn-sm ms-sm-auto">
                      view all →
                    </Link>
                  )}
                </div>
                {problems.length ? (
                  <ul className="small mb-0 ps-3">
                    {problems.slice(0, 8).map((p) => (
                      <li key={p.canonical_code}>
                        {p.canonical_code} ({p.competition} {p.year})
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState icon="file-earmark-text">No linked problems are available for this technique yet.</EmptyState>
                )}
              </section>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
