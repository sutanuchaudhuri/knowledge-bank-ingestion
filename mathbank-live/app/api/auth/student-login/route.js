import { errorJson, json, rest } from "../../../../lib/server.js";
import { setStudentToken } from "../../../../lib/session.js";

export const dynamic = "force-dynamic";

export async function POST(request) {
  try {
    const { email, password } = await request.json();
    const out = await rest({ method: "POST", path: "/v1/learner/login", body: { email, password } });
    await setStudentToken(out.access_token);
    return json({ ok: true, role: "STUDENT", display_name: out.display_name || out.first_name || null });
  } catch (err) {
    return errorJson(err);
  }
}
