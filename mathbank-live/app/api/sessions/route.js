// Instructor-only: list and create live sessions (REST /v1/live/sessions, admin key server-side).
import { authHeaders } from "../../../lib/gateway.mjs";
import { errorJson, json, rest } from "../../../lib/server.js";
import { currentActor } from "../../../lib/session.js";

export const dynamic = "force-dynamic";

async function instructor() {
  const actor = await currentActor();
  return actor?.role === "INSTRUCTOR" ? actor : null;
}

export async function GET() {
  const actor = await instructor();
  if (!actor) return json({ error: "instructor login required" }, 401);
  try {
    return json(await rest({ path: "/v1/live/sessions?limit=20", headers: authHeaders(actor) }));
  } catch (err) {
    return errorJson(err);
  }
}

export async function POST(request) {
  const actor = await instructor();
  if (!actor) return json({ error: "instructor login required" }, 401);
  const body = await request.json().catch(() => ({}));
  const minutes = Math.min(Math.max(Number(body.minutes) || 30, 5), 240);
  const topics = (Array.isArray(body.topics) ? body.topics : [])
    .map((t) => String(t || "").trim()).filter(Boolean).slice(0, 12)
    .map((title, i, all) => ({ ordinal: i, title: title.slice(0, 120), planned_seconds: Math.round((minutes * 60) / all.length) }));
  try {
    const created = await rest({ method: "POST", path: "/v1/live/sessions", headers: authHeaders(actor), body: {
      title: String(body.title || "Live geometry session").slice(0, 200),
      ...(body.plan_id ? { plan_id: body.plan_id } : { topics, course_limit_seconds: minutes * 60 }),
    } });
    return json(created, 201);
  } catch (err) {
    return errorJson(err);
  }
}
