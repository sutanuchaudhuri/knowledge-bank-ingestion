// Server-only cookie helpers. Cookie names and the admin HMAC marker match mathbank-web, so on one host
// (cookies are not port-scoped) a learner/admin signed in to mathbank-web is also signed in here.
import { cookies } from "next/headers";
import { ADMIN_COOKIE, STUDENT_COOKIE, resolveActor, signAdminMarker } from "./gateway.mjs";

const opts = (maxAge) => ({ httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge });

export async function currentActor() {
  const store = await cookies();
  const header = store.getAll().map((c) => `${c.name}=${encodeURIComponent(c.value)}`).join("; ");
  return resolveActor(header);
}

export async function setStudentToken(token) {
  (await cookies()).set(STUDENT_COOKIE, token, opts(60 * 60 * 24 * 7));
}

export async function setAdmin(username) {
  (await cookies()).set(ADMIN_COOKIE, signAdminMarker(username, process.env.ADMIN_SESSION_SECRET), opts(60 * 60 * 8));
}

export async function clearAll() {
  const store = await cookies();
  store.delete(STUDENT_COOKIE);
  store.delete(ADMIN_COOKIE);
}

export async function studentToken() {
  return (await cookies()).get(STUDENT_COOKIE)?.value || null;
}
