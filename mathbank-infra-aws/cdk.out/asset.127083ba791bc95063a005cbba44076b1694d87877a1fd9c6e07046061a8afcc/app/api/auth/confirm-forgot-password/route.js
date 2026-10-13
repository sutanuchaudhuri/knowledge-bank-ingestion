import { CognitoAuthError, confirmForgotPassword } from "../../../../lib/cognito.js";

export async function POST(request) {
  const body = await request.json().catch(() => ({}));
  const { username, confirmation_code: confirmationCode, new_password: newPassword } = body;
  if (typeof username !== "string" || typeof confirmationCode !== "string" || typeof newPassword !== "string") {
    return Response.json({ error: "username, confirmation_code, new_password are required" }, { status: 422 });
  }
  try {
    await confirmForgotPassword({ username, confirmationCode, newPassword });
    return Response.json({ ok: true }, { status: 200 });
  } catch (err) {
    if (err instanceof CognitoAuthError) {
      return Response.json({ error: err.message }, { status: 422 });
    }
    return Response.json({ error: "could not reset password" }, { status: 502 });
  }
}
