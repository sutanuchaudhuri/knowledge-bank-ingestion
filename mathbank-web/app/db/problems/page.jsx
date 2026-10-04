"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { table, th, td, rowStyle, masterDetail, panel, input, button } from "../dbStyles.js";
import Pager from "../Pager.jsx";
import ProblemDetail from "../ProblemDetail.jsx";

const LIMIT = 20;

function ProblemsPageInner() {
  const searchParams = useSearchParams();
  const [competitions, setCompetitions] = useState([]);
  const [filters, setFilters] = useState({
    competition: searchParams.get("competition") || "",
    year_min: searchParams.get("year_min") || "",
    year_max: searchParams.get("year_max") || "",
    concept: searchParams.get("concept") || "",
    technique: searchParams.get("technique") || "",
  });
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState(null);
  const [error, setError] = useState(null);
  const [selectedCode, setSelectedCode] = useState(null);

  useEffect(() => {
    fetch("/api/rest/competitions")
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => setCompetitions(data.items))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setPage(null);
    setError(null);
    const params = new URLSearchParams({ ...filters, limit: String(LIMIT), offset: String(offset) });
    fetch(`/api/rest/problems?${params}`)
      .then((res) =>
        res.ok ? res.json() : res.json().then((body) => Promise.reject(new Error(body.error || `status ${res.status}`)))
      )
      .then(setPage)
      .catch((err) => setError(err.message));
  }, [filters, offset]);

  function updateFilter(key, value) {
    setOffset(0);
    setSelectedCode(null);
    setFilters((f) => ({ ...f, [key]: value }));
  }

  function clearFilters() {
    setOffset(0);
    setSelectedCode(null);
    setFilters({ competition: "", year_min: "", year_max: "", concept: "", technique: "" });
  }

  return (
    <div>
      <div className="app-filters card p-3 flex-row">
        <select className="form-select" aria-label="Competition" value={filters.competition} onChange={(e) => updateFilter("competition", e.target.value)}>
          <option value="">All competitions</option>
          {competitions.map((c) => (
            <option key={c.external_code} value={c.external_code}>{c.name}</option>
          ))}
        </select>
        <input
          className={input} aria-label="Minimum year"
          type="number"
          placeholder="Year ≥"
          value={filters.year_min}
          onChange={(e) => updateFilter("year_min", e.target.value)}
        />
        <input
          className={input} aria-label="Maximum year"
          type="number"
          placeholder="Year ≤"
          value={filters.year_max}
          onChange={(e) => updateFilter("year_max", e.target.value)}
        />
        <input
          className={input} aria-label="Concept slug"
          placeholder="Concept slug"
          value={filters.concept}
          onChange={(e) => updateFilter("concept", e.target.value)}
        />
        <input
          className={input} aria-label="Technique slug"
          placeholder="Technique slug"
          value={filters.technique}
          onChange={(e) => updateFilter("technique", e.target.value)}
        />
        <button
          type="button"
          className={button}
          onClick={clearFilters}
        >
          Clear
        </button>
      </div>

      {error && <p style={{ color: "#b91c1c" }}>Could not load problems: {error}</p>}

      <div className={masterDetail}>
        <div className={panel}>
          {!page ? (
            <p>Loading…</p>
          ) : (
            <>
              <div className="table-responsive"><table className={table}>
                <thead>
                  <tr>
                    <th style={th}>Code</th>
                    <th style={th}>Competition</th>
                    <th style={th}>Year</th>
                    <th style={th}>Paper</th>
                    <th style={{ ...th, textAlign: "right" }}>#</th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((p) => (
                    <tr key={p.canonical_code} style={rowStyle(selectedCode === p.canonical_code)} onClick={() => setSelectedCode(p.canonical_code)}>
                      <td style={td}>{p.canonical_code}</td>
                      <td style={td}>{p.competition}</td>
                      <td style={td}>{p.year}</td>
                      <td style={td}>{p.paper_code}</td>
                      <td style={{ ...td, textAlign: "right" }}>{p.problem_number}</td>
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

        {selectedCode ? <ProblemDetail code={selectedCode} /> : <div className={panel}><p className="text-secondary mb-0">Select a row to see details.</p></div>}
      </div>
    </div>
  );
}

export default function ProblemsPage() {
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <ProblemsPageInner />
    </Suspense>
  );
}
