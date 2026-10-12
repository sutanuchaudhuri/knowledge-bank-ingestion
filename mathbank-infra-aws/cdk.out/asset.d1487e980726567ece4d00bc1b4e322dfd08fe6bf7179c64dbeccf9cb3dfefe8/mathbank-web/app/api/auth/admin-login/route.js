// Predefined single admin account (env-configured) — a bridge until real
// OAuth login lands (see requirements/12_STUDENT_PROFILE_AND_ADMIN_LOGIN_UI_REQUIREMENTS.md).
// This only gates the /admin UI in this app; it is intentionally independent
// of mathbank-rest's own ADMIN_API_KEY (restClient.js still attaches that
// server-side for the actual /v1/admin/* calls, unchanged).
import crypto from "node:crypto";
import { setAdminSession } from "../../../../lib/session.js";

function safeEqual(a, b) {
  const bufA = Buffer.from(a);
  const bufB = Buffer.from(b);
  if (bufA.length !== bufB.length) return false;
  return crypto.timingSafeEqual(bufA, bufB);
}

export async function POST(request) {
  const body = await request.json().catch(() => ({}));
  const { username, password } = body;
  const expectedUsername = process.env.ADMIN_LOGIN_USERNAME || "admin";
  const expectedPassword = process.env.ADMIN_LOGIN_PASSWORD || "";
  if (
    typeof username !== "string" ||
    typeof password !== "string" ||
    !safeEqual(username, expectedUsername) ||
    !expectedPassword ||
    !safeEqual(password, expectedPassword)
  ) {
    return Response.json({ error: "invalid username or password" }, { status: 401 });
  }
  await setAdminSession(username);
  return Response.json({ ok: true, username });
}
