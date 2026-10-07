"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { input, button } from "../dbStyles.js";
import Pager from "../Pager.jsx";
import { ProblemPreviewCard } from "../../_components/ProblemPreview.jsx";
import { Callout, EmptyState, Pill } from "../../_components/ui.jsx";

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
  const [competitionError, setCompetitionError] = useState("");

  useEffect(() => {
    fetch("/api/rest/competitions")
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`Could not load competition filters (${res.status}).`))))
      .then((data) => setCompetitions(data.items))
      .catch((err) => setCompetitionError(err.message));
  }, []);

  useEffect(() => {
    setPage(null);
    setError(null);
    const controller = new AbortController();
    const params = new URLSearchParams({ ...filters, limit: String(LIMIT), offset: String(offset) });
    fetch(`/api/rest/problems?${params}`, { signal: controller.signal })
      .then((res) =>
        res.ok ? res.json() : res.json().then((body) => Promise.reject(new Error(body.error || `status ${res.status}`)))
      )
      .then((data) => { if (!controller.signal.aborted) setPage(data); })
      .catch((err) => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [filters, offset]);

  function updateFilter(key, value) {
    setOffset(0);
    setFilters((f) => ({ ...f, [key]: value }));
  }

  function clearFilters() {
    setOffset(0);
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

      {competitionError && <Callout tone="warning" role="alert">{competitionError}</Callout>}
      {error && <Callout tone="danger" role="alert">Could not load problems: {error}</Callout>}

      <div className="card p-3">
          {filters.competition && <div className="mb-3"><Pill tone="primary" icon="trophy">{filters.competition}</Pill></div>}
          {!page && !error ? (
            <p role="status">Loading…</p>
          ) : page ? (
            <>
              {page.items.length ? <div className="d-grid gap-3">
                {page.items.map((problem) => <ProblemPreviewCard key={problem.canonical_code} item={problem} related />)}
              </div> : <EmptyState icon="search">No problems match these filters.</EmptyState>}
              <Pager
                offset={offset}
                limit={LIMIT}
                hasMore={page.hasMore}
                count={page.items.length}
                onPrev={() => setOffset((o) => Math.max(o - LIMIT, 0))}
                onNext={() => setOffset((o) => o + LIMIT)}
              />
            </>
          ) : (
            null
          )}
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
