// Student self-service signup, now via Cognito (requirements/64 §6a) instead of
// mathbank-rest's own /v1/learner/register password-hash path. Collects the same
// profile fields mathbank-exam-agent's signup already does (first/last name, optional
// grade/email/phone) for platform-wide profile consistency (shared User Pool).
import { CognitoAuthError, signUp } from "../../../../lib/cognito.js";
import { resolveStudentSession } from "../../../../lib/cognitoBridge.js";
import { setStudentSession } from "../../../../lib/session.js";

export async function POST(request) {
  const body = await request.json().catch(() => ({}));
  const { email, password, first_name: firstName, last_name: lastName, grade, phone } = body;
  if (
    typeof email !== "string" || typeof password !== "string" ||
    typeof firstName !== "string" || typeof lastName !== "string"
  ) {
    return Response.json({ error: "email, password, first_name, last_name are required" }, { status: 422 });
  }
  try {
    const signedUp = await signUp({ password, firstName, lastName, grade, email });
    const result = await resolveStudentSession({
      cognitoSub: signedUp.cognitoSub, firstName, lastName, grade, email,
    });
    await setStudentSession(result.access_token);
    const { access_token, ...profile } = result;
    return Response.json(profile, { status: 201 });
  } catch (err) {
    if (err instanceof CognitoAuthError && err.code === "USERNAME_EXISTS") {
      return Response.json({ error: err.message }, { status: 409 });
    }
    if (err instanceof CognitoAuthError) {
      return Response.json({ error: err.message }, { status: 422 });
    }
    return Response.json({ error: err.message || "signup failed" }, { status: err.status || 502 });
  }
}
