"use client";

import { useState } from "react";
import { table, masterDetail, panel, input, primaryButton } from "../dbStyles.js";
import ProblemDetail from "../ProblemDetail.jsx";
import { Callout, EmptyState } from "../../_components/ui.jsx";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [competition, setCompetition] = useState("");
  const [yearMin, setYearMin] = useState("");
  const [yearMax, setYearMax] = useState("");
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedCode, setSelectedCode] = useState(null);

  async function runSearch(e) {
    e?.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setSelectedCode(null);
    try {
      const res = await fetch("/api/rest/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          filters: {
            competition: competition || undefined,
            year_min: yearMin ? Number(yearMin) : undefined,
            year_max: yearMax ? Number(yearMax) : undefined,
          },
          limit: 25,
        }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || `status ${res.status}`);
      setResults(body.results);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="d-grid gap-3">
      <form onSubmit={runSearch} className="app-filters card p-3 flex-row">
        <input
          className={`${input} app-search-query`} aria-label="Find similar questions"
          placeholder='Find similar questions, e.g. "cyclic quadrilateral with equal diagonals"'
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <input className={input} aria-label="Competition" placeholder="Competition" value={competition} onChange={(e) => setCompetition(e.target.value)} />
        <input className={input} aria-label="Minimum year" type="number" placeholder="Year ≥" value={yearMin} onChange={(e) => setYearMin(e.target.value)} />
        <input className={input} aria-label="Maximum year" type="number" placeholder="Year ≤" value={yearMax} onChange={(e) => setYearMax(e.target.value)} />
        <button type="submit" className={primaryButton} disabled={loading}>
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      {error && <Callout tone="danger" role="alert">Search failed: {error}</Callout>}

      <div className={masterDetail}>
        <div className={panel}>
          {!results ? (
            <Callout tone="insight" title="Hybrid ranking">
              Search over problem statements with semantic and lexical signals combined into one ranked list.
            </Callout>
          ) : results.length === 0 ? (
            <EmptyState icon="search">No matching problems.</EmptyState>
          ) : (
            <div className="table-responsive"><table className={table}>
              <thead>
                <tr>
                  <th className="fw-semibold">Code</th>
                  <th className="fw-semibold">Competition</th>
                  <th className="fw-semibold">Year</th>
                  <th className="fw-semibold text-end">Score</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.canonical_code} className={selectedCode === r.canonical_code ? "table-active" : ""} onClick={() => setSelectedCode(r.canonical_code)}>
                    <td>{r.canonical_code}</td>
                    <td>{r.competition}</td>
                    <td>{r.year}</td>
                    <td className="text-end mb-num">{Number(r.rrf_score).toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
        </div>

        {selectedCode ? <ProblemDetail code={selectedCode} /> : <div className={panel}><EmptyState icon="file-earmark-text">Select a result to see the full problem.</EmptyState></div>}
      </div>
    </div>
  );
}
