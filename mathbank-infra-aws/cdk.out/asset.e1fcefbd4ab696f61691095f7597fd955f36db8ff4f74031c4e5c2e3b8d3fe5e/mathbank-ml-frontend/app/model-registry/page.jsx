"use client";

import { useEffect, useState } from "react";
import { PageHeader, StatusBadge, TodoPanel } from "../_components/ui.jsx";
import { fetchMl } from "../../lib/mlClient.mjs";

export default function ModelRegistryPage() {
  const [result, setResult] = useState(null);

  useEffect(() => {
    fetchMl("model-registry").then(setResult);
  }, []);

  return (
    <>
      <PageHeader
        title="Model registry"
        subtitle="Approved/pending models per family (requirements/56 §2 GET /v1/admin/ml/model-registry)."
      />
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
        // TODO: once implemented, render a real table: model_key, model_version,
        // approval_status, deployment_stage, metrics_json summary — not built in this pass.
        <pre>{JSON.stringify(result.body, null, 2)}</pre>
      )}
    </>
  );
}
