import { Suspense } from "react";
import LearningWorkspace from "./LearningWorkspace.jsx";

export default function LearningPage() {
  return (
    <Suspense fallback={<p role="status">Loading learning workspace...</p>}>
      <LearningWorkspace />
    </Suspense>
  );
}
