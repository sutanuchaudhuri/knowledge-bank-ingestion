import { restGet, restPost } from "../../../../lib/restClient.js";

const READ_PATHS = new Set(["learning-context", "prerequisites", "practice"]);

export async function GET(request, context) {
  const { path } = await context.params;
  if (path.length !== 2 || !READ_PATHS.has(path[0])) {
    return Response.json({ error: "Unknown tutor endpoint" }, { status: 404 });
  }
  const params = new URL(request.url).searchParams;
  const query = path[0] === "prerequisites" ? { max_depth: params.get("max_depth") } :
    path[0] === "practice" ? { limit: params.get("limit") } : {};
  try {
    return Response.json(await restGet(`/v1/tutor/${path[0]}/${encodeURIComponent(path[1])}`, query));
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}

export async function POST(request, context) {
  const { path } = await context.params;
  if (path.length !== 1 || path[0] !== "coach") {
    return Response.json({ error: "Unknown tutor endpoint" }, { status: 404 });
  }
  let body;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Request body must be valid JSON" }, { status: 400 });
  }
  try {
    return Response.json(await restPost("/v1/tutor/coach", body));
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
