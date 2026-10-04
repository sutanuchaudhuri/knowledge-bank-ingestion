// Paginated Techniques grid, proxies GET /v1/techniques.
import { restGetPage } from "../../../../lib/restClient.js";

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const limit = Math.min(Number(searchParams.get("limit")) || 25, 100);
  const offset = Math.max(Number(searchParams.get("offset")) || 0, 0);
  try {
    const page = await restGetPage("/v1/techniques", {}, limit, offset);
    return Response.json(page);
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
