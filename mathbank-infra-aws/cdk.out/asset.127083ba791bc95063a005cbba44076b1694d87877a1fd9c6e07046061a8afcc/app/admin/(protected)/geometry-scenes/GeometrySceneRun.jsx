"use client";

import { useEffect, useState } from "react";
import { RUN_ID, DEBUG_OWNER } from "../../../../lib/geometryScenes.mjs";
import { Callout, EmptyState } from "../../../_components/ui.jsx";

export default function GeometrySceneRun({ run, owner }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    setResult(null);
    setError(null);
    setLoading(true);
    if (!run) { setLoading(false); return; }
    if (typeof run !== "string" || !RUN_ID.test(run)) { setError("Invalid run identifier."); setLoading(false); return; }
    if (typeof owner !== "string" || !DEBUG_OWNER.test(owner)) { setError("A valid diagnostics owner is required."); setLoading(false); return; }
    const controller = new AbortController();
    fetch(`/api/rest/geometry-scenes/debug/runs/${run}?owner=${encodeURIComponent(owner)}`, { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok || response.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") throw new Error("The run diagnostics are unavailable.");
        const body = await response.json();
        if (!controller.signal.aborted) setResult(body);
      }).catch((err) => { if (!controller.signal.aborted) setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [run, owner]);
  if (loading) return <div role="status">Loading run diagnostics…</div>;
  if (error) return <Callout tone="danger" role="alert">{error}</Callout>;
  if (!result) return <EmptyState icon="activity">Open a run diagnostics link to inspect its outcome.</EmptyState>;
  return <details className="mb-corpus-preview" open>
    <summary>Staff run diagnostics</summary>
    <pre className="text-break text-wrap mt-3" data-testid="geometry-run-diagnostics">{JSON.stringify(result, null, 2)}</pre>
  </details>;
}
