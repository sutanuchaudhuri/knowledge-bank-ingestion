import { redirect } from "next/navigation";
import { currentActor } from "../../../lib/session.js";
import Console from "../../_components/Console.jsx";

export const dynamic = "force-dynamic";

export default async function InstructorPage({ params }) {
  const { sid } = await params;
  const actor = await currentActor();
  if (actor?.role !== "INSTRUCTOR") redirect("/login");
  return <Console sid={sid} />;
}
