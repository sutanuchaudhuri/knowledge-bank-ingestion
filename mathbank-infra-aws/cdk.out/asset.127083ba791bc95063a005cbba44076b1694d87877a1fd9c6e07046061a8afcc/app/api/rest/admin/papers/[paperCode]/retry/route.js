import { restAdminPost } from "../../../../../../../lib/restClient.js";

export async function POST(_request, { params }) {
  try {
    const { paperCode } = await params;
    const result = await restAdminPost(`/v1/admin/papers/${encodeURIComponent(paperCode)}/retry`, {});
    return Response.json(result);
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
