import { restAdminPost } from "../../../../../lib/restClient.js";

export async function POST(request) {
  try {
    const body = await request.json();
    const result = await restAdminPost("/v1/admin/competitions", body);
    return Response.json(result, { status: 201 });
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
