import Chat from "./Chat.jsx";
import Link from "next/link";

export default function Page() {
  return (
    <div>
      <header className="mb-4">
        <span className="badge text-bg-primary mb-2">Competition math, connected</span>
        <h1 className="h2 fw-bold">MathBank Tutor</h1>
        <p className="text-secondary mb-0">Explore ideas, retrieve problems, and learn with a streaming AI tutor. This is an anonymous session.</p>
        <Link href="/learn" className="btn btn-outline-primary mt-3">Stuck on a problem? Start guided practice</Link>
      </header>
      <Chat />
    </div>
  );
}
