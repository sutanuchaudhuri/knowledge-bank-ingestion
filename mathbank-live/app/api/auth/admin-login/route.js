import crypto from "node:crypto";
import { json } from "../../../../lib/server.js";
import { setAdmin } from "../../../../lib/session.js";

export const dynamic = "force-dynamic";

const same = (a, b) => {
  const x = Buffer.from(String(a || ""));
  const y = Buffer.from(String(b || ""));
  return x.length === y.length && crypto.timingSafeEqual(x, y);
};

export async function POST(request) {
  const { username, password } = await request.json().catch(() => ({}));
  const u = process.env.ADMIN_LOGIN_USERNAME;
  const p = process.env.ADMIN_LOGIN_PASSWORD;
  if (!u || !p || !process.env.ADMIN_SESSION_SECRET) return json({ error: "instructor login is not configured" }, 503);
  if (!same(username, u) || !same(password, p)) return json({ error: "invalid credentials" }, 401);
  await setAdmin(username);
  return json({ ok: true, role: "INSTRUCTOR" });
}
