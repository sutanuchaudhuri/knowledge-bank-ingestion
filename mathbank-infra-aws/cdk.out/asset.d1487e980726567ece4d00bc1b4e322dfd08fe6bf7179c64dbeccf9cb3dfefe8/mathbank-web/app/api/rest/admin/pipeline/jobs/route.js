import { restAdminGet } from "../../../../../../lib/restClient.js";
import { hasValidAdminSession } from "../../../../../../lib/session.js";

export async function GET(request) {
  if (!await hasValidAdminSession()) return Response.json({ error: "Admin login required" }, { status: 401 });
  try {
    const params = Object.fromEntries(new URL(request.url).searchParams.entries());
    return Response.json(await restAdminGet("/v1/admin/pipeline/jobs", params));
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
