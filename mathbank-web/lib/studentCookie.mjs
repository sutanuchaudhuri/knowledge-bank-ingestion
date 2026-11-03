// Dependency-free reader for the student's REST token cookie, usable where next/headers is not (plain Requests).
export const STUDENT_COOKIE = "mb_student_token";

export function studentTokenFromRequest(request) {
  for (const part of (request.headers.get("cookie") || "").split(";")) {
    const [name, ...value] = part.trim().split("=");
    if (name === STUDENT_COOKIE) return decodeURIComponent(value.join("=")) || null;
  }
  return null;
}
