// Full problem detail (statement, concepts, techniques, solutions), proxies
// GET /v1/problems/by-code/{code}.
import { restGet } from "../../../../../lib/restClient.js";

export async function GET(_request, context) {
  const { code } = await context.params;
  try {
    const problem = await restGet(`/v1/problems/by-code/${encodeURIComponent(code)}`);
    return Response.json(problem);
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
