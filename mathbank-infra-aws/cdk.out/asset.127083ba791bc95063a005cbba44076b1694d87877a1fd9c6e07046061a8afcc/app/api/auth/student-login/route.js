// Student login, now backed by Cognito (requirements/64 §6a) instead of
// mathbank-rest's own password check. Cognito replaces the credential check and the
// login screen only — the ongoing API session is still a plain mathbank-rest JWT
// (lib/cognitoBridge.js mints one from the already-authenticated Cognito identity),
// so every existing /v1/learner/*|/v1/quiz/* caller elsewhere in this app is unaffected.
import { CognitoAuthError, login } from "../../../../lib/cognito.js";
import { resolveStudentSession } from "../../../../lib/cognitoBridge.js";
import { setStudentSession } from "../../../../lib/session.js";

export async function POST(request) {
  const body = await request.json().catch(() => ({}));
  const { email, password } = body;
  if (typeof email !== "string" || typeof password !== "string") {
    return Response.json({ error: "invalid email or password" }, { status: 401 });
  }
  try {
    const { claims } = await login({ username: email, password });
    const result = await resolveStudentSession({
      cognitoSub: claims.sub,
      firstName: claims.given_name || "Student",
      lastName: claims.family_name || "",
      email: claims.email || email,
    });
    await setStudentSession(result.access_token);
    const { access_token, ...profile } = result;
    return Response.json(profile, { status: 200 });
  } catch (err) {
    if (err instanceof CognitoAuthError) {
      return Response.json({ error: err.message }, { status: 401 });
    }
    return Response.json({ error: err.message || "login failed" }, { status: err.status || 502 });
  }
}
