import { CognitoAuthError, isAdminClaims, login } from "../../../../lib/cognito.js";
import { errorJson, json } from "../../../../lib/server.js";
import { setAdmin } from "../../../../lib/session.js";

export const dynamic = "force-dynamic";

export async function POST(request) {
  const { username, password } = await request.json().catch(() => ({}));
  if (typeof username !== "string" || typeof password !== "string") {
    return json({ error: "invalid credentials" }, 401);
  }
  try {
    const { claims } = await login({ username, password });
    if (!isAdminClaims(claims)) {
      return json({ error: "this account is not an admin" }, 403);
    }
    await setAdmin(username);
    return json({ ok: true, role: "INSTRUCTOR" });
  } catch (err) {
    if (err instanceof CognitoAuthError) return json({ error: err.message }, 401);
    return errorJson(err);
  }
}
