import { restPost } from "../../../../lib/restClient.js";
import { setStudentSession } from "../../../../lib/session.js";

export async function POST(request) {
  try {
    const body = await request.json();
    const result = await restPost("/v1/learner/login", body);
    await setStudentSession(result.access_token);
    const { access_token, ...profile } = result;
    return Response.json(profile, { status: 200 });
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
