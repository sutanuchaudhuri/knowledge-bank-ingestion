// requirements/53: student-authenticated proxy for /v1/quiz/* (generate/fetch/respond/review).
import { restAuthGet, restAuthPost } from "../../../../../lib/restClient.js";
import { getStudentToken } from "../../../../../lib/session.js";

function unauthorized() {
  return Response.json({ error: "SIGN_IN_REQUIRED", message: "Sign in to use quizzes." }, { status: 401 });
}

function errorResponse(err) {
  const status = err.status || 502;
  let detail = err.message;
  try {
    detail = JSON.parse(err.message);
  } catch {
    // plain string message is fine
  }
  return Response.json({ error: detail }, { status });
}

export async function GET(request, context) {
  const token = await getStudentToken();
  if (!token) return unauthorized();
  const { path } = await context.params;
  try {
    const body = await restAuthGet(`/v1/quiz/${(path || []).join("/")}`, token);
    return Response.json(body);
  } catch (err) {
    return errorResponse(err);
  }
}

export async function POST(request, context) {
  const token = await getStudentToken();
  if (!token) return unauthorized();
  const { path } = await context.params;
  const payload = await request.json().catch(() => ({}));
  try {
    const body = await restAuthPost(`/v1/quiz/${(path || []).join("/")}`, token, payload);
    return Response.json(body);
  } catch (err) {
    return errorResponse(err);
  }
}
