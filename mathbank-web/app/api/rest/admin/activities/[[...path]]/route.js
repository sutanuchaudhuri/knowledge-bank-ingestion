import { restAdminGet, restAdminSend } from "../../../../../../lib/restClient.js";
import { hasValidAdminSession } from "../../../../../../lib/session.js";

function errorResponse(error) {
  return Response.json(
    { error: error.message || "Activity request failed." },
    { status: error.status || 502 },
  );
}

async function upstreamPath(context) {
  const { path = [] } = await context.params;
  const suffix = path.map(segment => encodeURIComponent(segment)).join("/");
  return `/v1/admin/activities${suffix ? `/${suffix}` : ""}`;
}

export async function GET(request, context) {
  if (!(await hasValidAdminSession())) {
    return Response.json({ error: "not authorized" }, { status: 401 });
  }
  try {
    const query = Object.fromEntries(new URL(request.url).searchParams);
    return Response.json(await restAdminGet(await upstreamPath(context), query));
  } catch (error) {
    return errorResponse(error);
  }
}

export async function POST(request, context) {
  if (!(await hasValidAdminSession())) {
    return Response.json({ error: "not authorized" }, { status: 401 });
  }
  try {
    const body = await request.json();
    return Response.json(await restAdminSend("POST", await upstreamPath(context), body), { status: 201 });
  } catch (error) {
    return errorResponse(error);
  }
}

export async function PATCH(request, context) {
  if (!(await hasValidAdminSession())) {
    return Response.json({ error: "not authorized" }, { status: 401 });
  }
  try {
    const body = await request.json();
    return Response.json(await restAdminSend("PATCH", await upstreamPath(context), body));
  } catch (error) {
    return errorResponse(error);
  }
}
