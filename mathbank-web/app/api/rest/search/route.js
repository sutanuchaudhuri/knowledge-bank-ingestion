// "Find similar questions" — hybrid semantic+lexical vector search, proxies POST /v1/search/problems.
// Semantic ranking is a paid embedding call, so it is only requested with the student's own token;
// an anonymous visitor (or an expired token) gets the lexical/graph results.
import { restAuthPost, restPost } from "../../../../lib/restClient.js";
import { studentTokenFromRequest } from "../../../../lib/studentCookie.mjs";

export async function POST(request) {
  const body = await request.json();
  try {
    const token = studentTokenFromRequest(request);
    let data;
    if (token) {
      try {
        data = await restAuthPost("/v1/search/problems", token, body);
      } catch (err) {
        if (err.status !== 401) throw err;
      }
    }
    data ??= await restPost("/v1/search/problems", body);
    return Response.json(data);
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
