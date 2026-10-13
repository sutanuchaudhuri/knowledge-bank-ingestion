import { redirect } from "next/navigation";
import { getStudentToken } from "../../../../lib/session.js";
import SolveWorkspace from "./SolveWorkspace.jsx";

export default async function SolvePage({ params }) {
  const { code } = await params;
  if (!(await getStudentToken())) redirect(`/login?next=${encodeURIComponent(`/learn/solve/${code}`)}`);
  return <SolveWorkspace code={decodeURIComponent(code)} />;
}
