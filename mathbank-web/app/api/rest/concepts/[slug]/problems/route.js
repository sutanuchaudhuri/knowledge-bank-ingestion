// Problems tagged with a concept (TESTS relation), proxies GET /v1/concepts/{slug}/problems.
import { restGetPage } from "../../../../../../lib/restClient.js";

export async function GET(request, context) {
  const { slug } = await context.params;
  const { searchParams } = new URL(request.url);
  const limit = Math.min(Number(searchParams.get("limit")) || 20, 100);
  const offset = Math.max(Number(searchParams.get("offset")) || 0, 0);
  try {
    const page = await restGetPage(`/v1/concepts/${encodeURIComponent(slug)}/problems`, {}, limit, offset);
    return Response.json(page);
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
