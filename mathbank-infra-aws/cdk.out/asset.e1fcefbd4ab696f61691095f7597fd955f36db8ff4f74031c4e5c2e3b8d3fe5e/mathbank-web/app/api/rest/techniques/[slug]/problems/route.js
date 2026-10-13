// Problems using a technique (USES_TECHNIQUE relation), proxies GET /v1/techniques/{slug}/problems.
import { restGetPage } from "../../../../../../lib/restClient.js";

export async function GET(request, context) {
  const { slug } = await context.params;
  const { searchParams } = new URL(request.url);
  const limit = Math.min(Number(searchParams.get("limit")) || 20, 100);
  const offset = Math.max(Number(searchParams.get("offset")) || 0, 0);
  try {
    const page = await restGetPage(`/v1/techniques/${encodeURIComponent(slug)}/problems`, {}, limit, offset);
    return Response.json(page);
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
