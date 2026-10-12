// "Find similar questions" — hybrid semantic+lexical vector search, proxies POST /v1/search/problems.
import { restPost } from "../../../../lib/restClient.js";

export async function POST(request) {
  const body = await request.json();
  try {
    const data = await restPost("/v1/search/problems", body);
    return Response.json(data);
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
