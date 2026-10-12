// Student joins with a code (REST /v1/live/sessions/join, using the learner's own token).
import { authHeaders } from "../../../lib/gateway.mjs";
import { errorJson, json, rest } from "../../../lib/server.js";
import { currentActor } from "../../../lib/session.js";

export const dynamic = "force-dynamic";

export async function POST(request) {
  const actor = await currentActor();
  if (actor?.role !== "STUDENT") return json({ error: "student login required" }, 401);
  const { join_code, display_name } = await request.json().catch(() => ({}));
  try {
    const out = await rest({ method: "POST", path: "/v1/live/sessions/join", headers: authHeaders(actor),
      body: { join_code: String(join_code || "").trim().toUpperCase(), ...(display_name ? { display_name } : {}) } });
    return json(out);
  } catch (err) {
    return errorJson(err);
  }
}
