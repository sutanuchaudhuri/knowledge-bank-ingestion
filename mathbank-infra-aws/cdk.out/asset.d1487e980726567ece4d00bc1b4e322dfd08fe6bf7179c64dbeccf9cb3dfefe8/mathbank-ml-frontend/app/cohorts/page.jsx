"use client";

import { useEffect, useState } from "react";
import { PageHeader, StatusBadge, TodoPanel } from "../_components/ui.jsx";
import { fetchMl } from "../../lib/mlClient.mjs";

export default function CohortsPage() {
  const [result, setResult] = useState(null);

  useEffect(() => {
    fetchMl("cohorts/clusters").then(setResult);
  }, []);

  return (
    <>
      <PageHeader title="Cohorts" subtitle='Validated student cluster assignments (requirements/58 §2, requirements/56 §2 GET /v1/admin/ml/cohorts/clusters).' />
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
        // TODO: once implemented, render: cluster_id, membership counts, top interpretable feature differences per cluster (requirements/08 §5's example profiles)
        <pre>{JSON.stringify(result.body, null, 2)}</pre>
      )}
    </>
  );
}
