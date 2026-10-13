import { clearStudentSession } from "../../../../lib/session.js";

export async function POST() {
  await clearStudentSession();
  return Response.json({ ok: true });
}
