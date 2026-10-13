import { CognitoAuthError, forgotPassword } from "../../../../lib/cognito.js";

export async function POST(request) {
  const body = await request.json().catch(() => ({}));
  const { username } = body;
  if (typeof username !== "string" || !username) {
    return Response.json({ error: "username is required" }, { status: 422 });
  }
  try {
    const result = await forgotPassword({ username });
    return Response.json(result, { status: 200 });
  } catch (err) {
    if (err instanceof CognitoAuthError) {
      return Response.json({ error: err.message }, { status: 422 });
    }
    return Response.json({ error: "could not start password reset" }, { status: 502 });
  }
}
