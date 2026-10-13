"use client";

import { useEffect, useState } from "react";
import { panel } from "./dbStyles.js";
import { ProblemPreview, ProblemSolutions, RelatedProblems } from "../_components/ProblemPreview.jsx";
import { Callout } from "../_components/ui.jsx";

/** Fetches and renders the full HAS_SOLUTION/TESTS/USES_TECHNIQUE detail for one problem. */
export default function ProblemDetail({ code }) {
  const [problem, setProblem] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!code) return;
    setProblem(null);
    setError(null);
    const controller = new AbortController();
    fetch(`/api/rest/problems/${encodeURIComponent(code)}`, { signal: controller.signal })
      .then((res) =>
        res.ok ? res.json() : res.json().then((body) => Promise.reject(new Error(body.error || `status ${res.status}`)))
      )
      .then((data) => { if (!controller.signal.aborted) setProblem(data); })
      .catch((err) => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [code]);

  if (!code) return <div className={panel}><p className="text-secondary mb-0">Select a row to see details.</p></div>;
  if (error) return <Callout tone="danger" role="alert">Could not load {code}: {error}</Callout>;
  if (!problem) return <div className={panel}><p className="mb-0" role="status">Loading…</p></div>;

  return (
    <div className={panel}>
      <h3 className="h5 fw-bold">{problem.canonical_code}</h3>
      <ProblemPreview problem={problem} />
      <RelatedProblems key={code} problem={problem} />

      <ProblemSolutions key={`solutions-${code}`} problem={problem} />
    </div>
  );
}
