"use client";

import { useEffect, useState } from "react";
import { PageHeader, StatusBadge, TodoPanel } from "../_components/ui.jsx";
import { fetchMl } from "../../lib/mlClient.mjs";

export default function DataReadinessPage() {
  const [result, setResult] = useState(null);

  useEffect(() => {
    fetchMl("data-readiness?use_case=GLOBAL").then(setResult);
  }, []);

  return (
    <>
      <PageHeader title="Data readiness" subtitle='Ranked "what data should improve?" admin report (requirements/09 §8, requirements/58 §3, requirements/56 §2 GET /v1/admin/ml/data-readiness).' />
      {!result ? (
        <p>Loading…</p>
      ) : result.body.status === "NOT_IMPLEMENTED" ? (
        <>
          <StatusBadge status={result.body.status} />
          <div style={{ marginTop: "1rem" }}>
            <TodoPanel todoRef={result.body.todo_ref} designDocRef={result.body.design_doc_ref} />
          </div>
        </>
      ) : (
        // TODO: once implemented, render: ranked list of missing-metadata items by expected downstream model-quality impact (requirements/09 §8's worked example)
        <pre>{JSON.stringify(result.body, null, 2)}</pre>
      )}
    </>
  );
}
