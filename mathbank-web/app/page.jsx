import Link from "next/link";
import Chat from "./Chat.jsx";
import { PageHeader, Icon } from "./_components/ui.jsx";

export default function Page() {
  return (
    <>
      <PageHeader icon="stars" title="MathBank Tutor"
        subtitle="Ask, explore and learn competition math with a streaming AI tutor."
        actions={<Link href="/learn" className="btn btn-outline-primary btn-sm"><Icon name="signpost-split" className="me-1" />Guided practice</Link>} />
      <Chat />
    </>
  );
}
