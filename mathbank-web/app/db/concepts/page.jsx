"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { table, th, td, rowStyle, masterDetail, panel, input } from "../dbStyles.js";
import Pager from "../Pager.jsx";

const LIMIT = 25;

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
    <div>
      <div style={{ marginBottom: 12 }}>
        <input
          style={{ ...input, width: 220 }}
          placeholder="Search concept name…"
          value={domain}
          onChange={(e) => {
            setOffset(0);
            setSelected(null);
            setDomain(e.target.value);
          }}
        />
      </div>

      {error && <p style={{ color: "#b91c1c" }}>Could not load concepts: {error}</p>}

      <div style={masterDetail}>
        <div>
          {!page ? (
            <p>Loading…</p>
          ) : (
            <>
              <table style={table}>
                <thead>
                  <tr>
                    <th style={th}>Slug</th>
                    <th style={th}>Name</th>
                    <th style={{ ...th, textAlign: "right" }}>Level</th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((c) => (
                    <tr key={c.slug} style={rowStyle(selected?.slug === c.slug)} onClick={() => setSelected(c)}>
                      <td style={td}>{c.slug}</td>
                      <td style={td}>{c.name}</td>
                      <td style={{ ...td, textAlign: "right" }}>{c.level ?? "–"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
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

        <div style={panel}>
          {!selected ? (
            <p style={{ color: "#666" }}>Select a concept to see its problems and related concepts.</p>
          ) : !detail ? (
            <p>Loading…</p>
          ) : (
            <>
              <h3 style={{ marginTop: 0, fontSize: 15 }}>{selected.name}</h3>
              {selected.description && <p style={{ fontSize: 13, color: "#444" }}>{selected.description}</p>}

              <p style={{ fontSize: 13 }}>
                <strong>Problems (TESTS):</strong> {detail.problems.length}
                {detail.problems.length > 0 && (
                  <>
                    {" · "}
                    <Link href={`/db/problems?concept=${encodeURIComponent(selected.slug)}`} style={{ color: "#2563eb" }}>
                      view all →
                    </Link>
                  </>
                )}
              </p>
              <ul style={{ fontSize: 13 }}>
                {detail.problems.slice(0, 8).map((p) => (
                  <li key={p.canonical_code}>
                    {p.canonical_code} ({p.competition} {p.year})
                  </li>
                ))}
              </ul>

              {detail.neighbors.length > 0 && (
                <>
                  <p style={{ fontSize: 13 }}>
                    <strong>Related concepts (CONCEPT_RELATION):</strong>
                  </p>
                  <ul style={{ fontSize: 13 }}>
                    {detail.neighbors.map((n, i) => (
                      <li key={i}>
                        {n.direction === "outgoing" ? "→" : "←"} {n.name} ({n.relation_type})
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
