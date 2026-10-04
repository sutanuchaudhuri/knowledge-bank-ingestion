"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { table, th, td, rowStyle, masterDetail, panel } from "../dbStyles.js";
import Pager from "../Pager.jsx";

const LIMIT = 25;

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
    <div>
      {error && <p style={{ color: "#b91c1c" }}>Could not load techniques: {error}</p>}

      <div className={masterDetail}>
        <div className={panel}>
          {!page ? (
            <p>Loading…</p>
          ) : (
            <>
              <div className="table-responsive"><table className={table}>
                <thead>
                  <tr>
                    <th style={th}>Slug</th>
                    <th style={th}>Name</th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((t) => (
                    <tr key={t.slug} style={rowStyle(selected?.slug === t.slug)} onClick={() => setSelected(t)}>
                      <td style={td}>{t.slug}</td>
                      <td style={td}>{t.name}</td>
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
            <p style={{ color: "#666" }}>Select a technique to see problems that use it.</p>
          ) : !problems ? (
            <p>Loading…</p>
          ) : (
            <>
              <h3 style={{ marginTop: 0, fontSize: 15 }}>{selected.name}</h3>
              {selected.description && <p style={{ fontSize: 13, color: "#444" }}>{selected.description}</p>}
              <p style={{ fontSize: 13 }}>
                <strong>Problems (USES_TECHNIQUE):</strong> {problems.length}
                {problems.length > 0 && (
                  <>
                    {" · "}
                    <Link href={`/db/problems?technique=${encodeURIComponent(selected.slug)}`} style={{ color: "#2563eb" }}>
                      view all →
                    </Link>
                  </>
                )}
              </p>
              <ul style={{ fontSize: 13 }}>
                {problems.slice(0, 8).map((p) => (
                  <li key={p.canonical_code}>
                    {p.canonical_code} ({p.competition} {p.year})
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
