// Paginated Problems grid, proxies GET /v1/problems with competition/year/concept/technique filters.
import { restGetPage } from "../../../../lib/restClient.js";

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const limit = Math.min(Number(searchParams.get("limit")) || 20, 100);
  const offset = Math.max(Number(searchParams.get("offset")) || 0, 0);
  const filters = {
    competition: searchParams.get("competition") || undefined,
    year_min: searchParams.get("year_min") || undefined,
    year_max: searchParams.get("year_max") || undefined,
    concept: searchParams.get("concept") || undefined,
    technique: searchParams.get("technique") || undefined,
  };
  try {
    const page = await restGetPage("/v1/problems", filters, limit, offset);
    return Response.json(page);
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
