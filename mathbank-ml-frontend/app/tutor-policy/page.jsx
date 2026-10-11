"use client";

import { useEffect, useState } from "react";
import { PageHeader, StatusBadge, TodoPanel } from "../_components/ui.jsx";
import { fetchMl } from "../../lib/mlClient.mjs";

export default function TutorPolicyPage() {
  const [result, setResult] = useState(null);

  useEffect(() => {
    fetchMl("tutor-policy").then(setResult);
  }, []);

  return (
    <>
      <PageHeader title="Tutor policy" subtitle='Current policy version/stage and offline evaluation summary (requirements/11, requirements/56 §2 GET /v1/admin/ml/tutor-policy).' />
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
        // TODO: once implemented, render: policy_version, stage (0-5, requirements/11 §1), action_vocabulary_version, offline_eval_summary
        <pre>{JSON.stringify(result.body, null, 2)}</pre>
      )}
    </>
  );
}
