// Paginated Concepts grid, proxies GET /v1/concepts with an optional name-substring filter.
import { restGetPage } from "../../../../lib/restClient.js";

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const limit = Math.min(Number(searchParams.get("limit")) || 25, 100);
  const offset = Math.max(Number(searchParams.get("offset")) || 0, 0);
  const domain = searchParams.get("domain") || undefined;
  try {
    const page = await restGetPage("/v1/concepts", { domain }, limit, offset);
    return Response.json(page);
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
