// Admin login, now backed by a real Cognito identity instead of a single predefined
// env-configured credential (requirements/64 §6a's shared User Pool). The only change
// to session issuance itself is WHAT is checked before calling setAdminSession — the
// marker format and verifyAdminMarker()/hasValidAdminSession() are completely
// unchanged, so existing e2e cookie mocking (e2e/mock-auth.mjs) keeps working as-is.
// The actual /v1/admin/* mathbank-rest calls still use the static admin API key
// (restClient.js), unaffected — that is a service credential, not a human admin's.
import { CognitoAuthError, isAdminClaims, login } from "../../../../lib/cognito.js";
import { setAdminSession } from "../../../../lib/session.js";

export async function POST(request) {
  const body = await request.json().catch(() => ({}));
  const { username, password } = body;
  if (typeof username !== "string" || typeof password !== "string") {
    return Response.json({ error: "invalid username or password" }, { status: 401 });
  }
  try {
    const { claims } = await login({ username, password });
    if (!isAdminClaims(claims)) {
      return Response.json({ error: "this account is not an admin" }, { status: 403 });
    }
    await setAdminSession(username);
    return Response.json({ ok: true, username });
  } catch (err) {
    if (err instanceof CognitoAuthError) {
      return Response.json({ error: err.message }, { status: 401 });
    }
    return Response.json({ error: "login failed" }, { status: 502 });
  }
}
