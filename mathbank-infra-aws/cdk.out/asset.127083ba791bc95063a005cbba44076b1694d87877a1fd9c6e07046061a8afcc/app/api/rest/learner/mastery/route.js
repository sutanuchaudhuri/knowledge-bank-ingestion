import { restAuthGet } from "../../../../../lib/restClient.js";
import { getStudentToken } from "../../../../../lib/session.js";

export async function GET() {
  const token = await getStudentToken();
  if (!token) return Response.json({ error: "not logged in" }, { status: 401 });
  try {
    const result = await restAuthGet("/v1/learner/mastery", token);
    return Response.json(result);
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
