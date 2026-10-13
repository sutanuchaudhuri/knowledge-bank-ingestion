import { restAdminGet } from "../../../../../../lib/restClient.js";

export async function GET() {
  try {
    const data = await restAdminGet("/v1/admin/pipeline/runs");
    return Response.json(data);
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
