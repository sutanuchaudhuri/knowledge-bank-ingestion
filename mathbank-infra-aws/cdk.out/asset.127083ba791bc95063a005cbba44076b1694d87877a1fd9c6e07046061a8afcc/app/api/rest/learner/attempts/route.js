import { restAuthGet } from "../../../../../lib/restClient.js";
import { getStudentToken } from "../../../../../lib/session.js";

export async function GET(request) {
  const token = await getStudentToken();
  if (!token) return Response.json({ error: "not logged in" }, { status: 401 });
  const { searchParams } = new URL(request.url);
  try {
    const result = await restAuthGet("/v1/learner/attempts", token, {
      limit: searchParams.get("limit") || 50,
      offset: searchParams.get("offset") || 0,
    });
    return Response.json(result);
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
