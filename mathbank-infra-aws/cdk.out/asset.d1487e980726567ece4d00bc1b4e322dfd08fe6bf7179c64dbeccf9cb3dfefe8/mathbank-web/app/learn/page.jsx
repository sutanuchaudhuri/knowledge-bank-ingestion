import { Suspense } from "react";
import LearningWorkspace from "./LearningWorkspace.jsx";

export default function LearningPage() {
  return (
    <Suspense fallback={<p role="status" className="text-secondary"><span className="spinner-border spinner-border-sm me-2" aria-hidden="true" />Loading learning workspace…</p>}>
      <LearningWorkspace />
    </Suspense>
  );
}
