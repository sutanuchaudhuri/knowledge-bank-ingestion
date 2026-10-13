import { CognitoAuthError, login } from "../../../../lib/cognito.js";
import { resolveStudentSession } from "../../../../lib/cognitoBridge.js";
import { errorJson, json } from "../../../../lib/server.js";
import { setStudentToken } from "../../../../lib/session.js";

export const dynamic = "force-dynamic";

export async function POST(request) {
  const { email, password } = await request.json().catch(() => ({}));
  if (typeof email !== "string" || typeof password !== "string") {
    return json({ error: "invalid credentials" }, 401);
  }
  try {
    const { claims } = await login({ username: email, password });
    const result = await resolveStudentSession({
      cognitoSub: claims.sub, firstName: claims.given_name || "Student",
      lastName: claims.family_name || "", email: claims.email || email,
    });
    await setStudentToken(result.access_token);
    return json({ ok: true, role: "STUDENT", display_name: result.display_name || result.first_name || null });
  } catch (err) {
    if (err instanceof CognitoAuthError) return json({ error: err.message }, 401);
    return errorJson(err);
  }
}
