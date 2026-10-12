import { json } from "../../../../lib/server.js";
import { clearAll } from "../../../../lib/session.js";

export const dynamic = "force-dynamic";
export async function POST() {
  await clearAll();
  return json({ ok: true });
}
