import { json } from "../../../lib/server.js";
import { currentActor } from "../../../lib/session.js";

export const dynamic = "force-dynamic";
export async function GET() {
  const actor = await currentActor();
  return json({ role: actor?.role || null, name: actor?.role === "INSTRUCTOR" ? actor.name : null });
}
