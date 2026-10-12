import { restAdminGet, restAdminPost } from "../../../../../lib/restClient.js";

export async function GET(request) {
  try {
    const { searchParams } = new URL(request.url);
    const params = Object.fromEntries(searchParams.entries());
    const items = await restAdminGet("/v1/admin/papers", params);
    return Response.json({ items });
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}

export async function POST(request) {
  try {
    const body = await request.json();
    const path = Array.isArray(body.papers) ? "/v1/admin/papers/batch" : "/v1/admin/papers";
    const result = await restAdminPost(path, body);
    return Response.json(result, { status: 201 });
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
