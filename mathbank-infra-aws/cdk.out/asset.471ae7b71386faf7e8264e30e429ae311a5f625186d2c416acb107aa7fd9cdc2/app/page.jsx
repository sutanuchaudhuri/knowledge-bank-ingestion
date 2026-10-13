import { currentActor } from "../lib/session.js";
import Home from "./_components/Home.jsx";

export const dynamic = "force-dynamic";

export default async function Page() {
  const actor = await currentActor();
  return <Home role={actor?.role || null} name={actor?.role === "INSTRUCTOR" ? actor.name : null} />;
}
