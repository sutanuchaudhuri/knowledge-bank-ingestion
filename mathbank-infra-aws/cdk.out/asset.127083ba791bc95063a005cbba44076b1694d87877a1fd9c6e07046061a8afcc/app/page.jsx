import Link from "next/link";
import Chat from "./Chat.jsx";
import { PageHeader, Icon } from "./_components/ui.jsx";

export default async function Page({ searchParams }) {
  const params = await searchParams;
  const problem = typeof params?.problem === "string" ? params.problem : "";
  const validProblem = /^[A-Z][A-Z0-9_]{2,119}$/.test(problem) ? problem : "";
  return (
    <>
      <PageHeader icon="stars" title="MathBank Tutor"
        subtitle="Ask, explore and learn competition math with a streaming AI tutor."
        actions={<Link href="/learn" className="btn btn-outline-primary btn-sm"><Icon name="signpost-split" className="me-1" />Guided practice</Link>} />
      <Chat key={validProblem} initialProblemCode={validProblem} invalidProblem={Boolean(problem && !validProblem)} />
    </>
  );
}
