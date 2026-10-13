import { clearAdminSession } from "../../../../lib/session.js";

export async function POST() {
  await clearAdminSession();
  return Response.json({ ok: true });
}
