import { restAuthGet } from "../../../../../lib/restClient.js";
import { getStudentToken } from "../../../../../lib/session.js";

export async function GET() {
  const token = await getStudentToken();
  if (!token) return Response.json({ error: "not logged in" }, { status: 401 });
  try {
    return Response.json(await restAuthGet("/v1/learner/practice-progress", token));
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
