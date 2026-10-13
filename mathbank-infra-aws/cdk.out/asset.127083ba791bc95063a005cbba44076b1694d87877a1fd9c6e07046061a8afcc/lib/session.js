// Cookie-based session helpers — server-side only (Route Handlers and Server
// Components). Students carry the real mathbank-rest JWT as their cookie
// value (that JWT IS their REST credential, same token /v1/learner/* already
// expects). Admin carries a locally HMAC-signed marker that only gates the
// /admin UI — the actual /v1/admin/* REST calls still go through the
// existing static MATHBANK_ADMIN_API_KEY in restClient.js, unchanged. Both
// are a deliberate bridge until real OAuth login lands (see
// requirements/12_STUDENT_PROFILE_AND_ADMIN_LOGIN_UI_REQUIREMENTS.md).
import { cookies } from "next/headers";
import crypto from "node:crypto";

const STUDENT_COOKIE = "mb_student_token";
const ADMIN_COOKIE = "mb_admin_session";
const ADMIN_SESSION_SECRET = process.env.ADMIN_SESSION_SECRET || "dev-only-insecure-admin-session-secret-change-me";
const SEVEN_DAYS = 60 * 60 * 24 * 7;
const EIGHT_HOURS = 60 * 60 * 8;

function cookieOptions(maxAge) {
  return { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge };
}

export async function setStudentSession(token) {
  const store = await cookies();
  store.set(STUDENT_COOKIE, token, cookieOptions(SEVEN_DAYS));
}

export async function getStudentToken() {
  const store = await cookies();
  return store.get(STUDENT_COOKIE)?.value || null;
}

export async function clearStudentSession() {
  const store = await cookies();
  store.delete(STUDENT_COOKIE);
}

function signAdminMarker(username) {
  const payload = `admin:${username}`;
  const sig = crypto.createHmac("sha256", ADMIN_SESSION_SECRET).update(payload).digest("hex");
  return `${payload}:${sig}`;
}

function verifyAdminMarker(value) {
  if (!value) return false;
  const parts = value.split(":");
  if (parts.length !== 3) return false;
  const [prefix, username, sig] = parts;
  const expected = crypto.createHmac("sha256", ADMIN_SESSION_SECRET).update(`${prefix}:${username}`).digest("hex");
  const a = Buffer.from(sig);
  const b = Buffer.from(expected);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

export async function setAdminSession(username) {
  const store = await cookies();
  store.set(ADMIN_COOKIE, signAdminMarker(username), cookieOptions(EIGHT_HOURS));
}

export async function hasValidAdminSession() {
  const store = await cookies();
  return verifyAdminMarker(store.get(ADMIN_COOKIE)?.value);
}

export async function clearAdminSession() {
  const store = await cookies();
  store.delete(ADMIN_COOKIE);
}
