// CONCEPT_RELATION neighbors for a concept, proxies GET /v1/concepts/{slug}/neighbors.
import { restGet } from "../../../../../../lib/restClient.js";

export async function GET(_request, context) {
  const { slug } = await context.params;
  try {
    const neighbors = await restGet(`/v1/concepts/${encodeURIComponent(slug)}/neighbors`);
    return Response.json({ items: neighbors });
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
