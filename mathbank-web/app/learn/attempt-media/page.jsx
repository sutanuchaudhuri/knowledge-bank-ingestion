import { redirect } from "next/navigation";
import { getStudentToken } from "../../../lib/session.js";
import AttemptMediaWorkspace from "../../_components/AttemptMediaWorkspace.jsx";

export default async function AttemptMediaPage({ searchParams }) {
  if (!(await getStudentToken())) {
    const params = await searchParams;
    const query = new URLSearchParams(Object.entries(params || {}).filter(([key]) => ["submission_id", "problem_ref"].includes(key))).toString();
    redirect(`/login?next=${encodeURIComponent(`/learn/attempt-media${query ? `?${query}` : ""}`)}`);
  }
  return <AttemptMediaWorkspace />;
}
