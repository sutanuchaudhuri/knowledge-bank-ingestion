"use client";

import { useEffect, useState } from "react";
import { PageHeader, StatusBadge, TodoPanel } from "../_components/ui.jsx";
import { fetchMl } from "../../lib/mlClient.mjs";

export default function TrainingRunsPage() {
  const [result, setResult] = useState(null);

  useEffect(() => {
    fetchMl("training-runs").then(setResult);
  }, []);

  return (
    <>
      <PageHeader title="Training runs" subtitle='Dataset manifest + metrics per training execution (requirements/56 §2 GET /v1/admin/ml/training-runs).' />
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
        // TODO: once implemented, render: model_family, model_version, feature_set_version, label_version, status, metrics_json summary
        <pre>{JSON.stringify(result.body, null, 2)}</pre>
      )}
    </>
  );
}
