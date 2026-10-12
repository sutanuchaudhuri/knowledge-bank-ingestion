"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Callout, EmptyState, Icon, Pill, StatCard } from "../_components/ui.jsx";
import { CompetitionProblemPreviews } from "../_components/ProblemPreview.jsx";

function LoadingState({ children }) {
  return (
    <div className="d-flex align-items-center gap-2 text-body-secondary" role="status">
      <span className="spinner-border spinner-border-sm" aria-hidden="true" />
      <span>{children}</span>
    </div>
  );
}

export default function CompetitionsPage() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    fetch("/api/rest/competitions")
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`status ${res.status}`))))
      .then((data) => setItems(data.items))
      .catch((err) => setError(err.message));
  }, []);

  return (
    <div className="d-grid gap-3">
      {error && <Callout tone="danger" role="alert">Could not load competitions: {error}</Callout>}
      {!items ? (
        <div className="card shadow-sm p-3 p-lg-4">
          {error ? <EmptyState icon="database">Competitions are unavailable right now.</EmptyState> : <LoadingState>Loading corpus competitions…</LoadingState>}
        </div>
      ) : (
        <div className="app-master-detail">
          <div className="card shadow-sm p-3 p-lg-4">
            {!items.length ? (
              <EmptyState icon="database">No competitions are available in the corpus yet.</EmptyState>
            ) : (
              <div className="table-responsive">
                <table className="table table-hover align-middle mb-0">
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>Name</th>
                      <th>Level</th>
                      <th className="text-end">Papers</th>
                      <th className="text-end">Problems</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((c) => (
                      <tr key={c.competition_id} className={selected?.competition_id === c.competition_id ? "table-active" : ""} onClick={() => setSelected(c)}>
                        <td><Pill tone="primary" icon="trophy">{c.external_code}</Pill></td>
                        <td><button className="btn btn-ghost btn-sm text-start" aria-pressed={selected?.competition_id === c.competition_id} onClick={() => setSelected(c)}>{c.name}</button></td>
                        <td className="small text-body-secondary">{c.level}</td>
                        <td className="text-end mb-num">{c.papers ?? "–"}</td>
                        <td className="text-end mb-num">{c.problems ?? "–"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="card shadow-sm p-3 p-lg-4">
            {!selected ? (
              <EmptyState icon="trophy">Select a competition to explore its questions.</EmptyState>
            ) : (
              <>
                <h2 className="h5 fw-bold mb-1">{selected.name} ({selected.external_code})</h2>
                <div className="d-flex flex-wrap gap-2 mb-3">
                  <Pill tone="primary" icon="trophy">{selected.external_code}</Pill>
                  {selected.level && <Pill icon="layers">{selected.level}</Pill>}
                </div>
                <div className="row g-2 mb-3">
                  {[
                    ["Papers", selected.papers, "journal"],
                    ["Problems", selected.problems, "file-earmark-text"],
                    ["Concept-tagged", selected.problems_with_concept, "diagram-3"],
                    ["Technique-tagged", selected.problems_with_technique, "tools"],
                  ].map(([label, value, icon]) => <div className="col-6" key={label}><StatCard label={label} value={value} icon={icon} /></div>)}
                </div>
                <p className="mb-3">
                  <Link href={`/db/problems?competition=${encodeURIComponent(selected.external_code)}`} className="btn btn-outline-primary btn-sm">
                    <Icon name="collection" />
                    View all {selected.name} problems →
                  </Link>
                </p>
                <CompetitionProblemPreviews key={selected.external_code} competition={selected.external_code} />
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
