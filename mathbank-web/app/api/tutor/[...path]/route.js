import { restGet, restPost } from "../../../../lib/restClient.js";
import { prepareProblemPresentation } from "../../../../lib/problemPresentation.mjs";

const READ_PATHS = new Set(["workspace", "learning-context", "prerequisites", "practice"]);

export async function GET(request, context) {
  const { path } = await context.params;
  if (path.length !== 2 || !READ_PATHS.has(path[0])) {
    return Response.json({ error: "Unknown tutor endpoint" }, { status: 404 });
  }
  const params = new URL(request.url).searchParams;
  const query = path[0] === "prerequisites" ? { max_depth: params.get("max_depth") } :
    path[0] === "practice" ? { limit: params.get("limit") } : {};
  try {
    const result = await restGet(`/v1/tutor/${path[0]}/${encodeURIComponent(path[1])}`, query, {
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(20000)]),
    });
    if (result.problem) {
      const presentation = prepareProblemPresentation(result.problem.statement_text, result.problem.canonical_code);
      result.problem = { ...result.problem, display_statement: presentation.markdown };
      result.format_warnings = presentation.warnings;
    }
    return Response.json(result);
  } catch (err) {
    if (err.name === "TimeoutError") return Response.json({ error: "Teaching data timed out. You can keep writing and retry." }, { status: 504 });
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}

export async function POST(request, context) {
  const { path } = await context.params;
  if (path.length !== 1 || !["coach", "micro-check"].includes(path[0])) {
    return Response.json({ error: "Unknown tutor endpoint" }, { status: 404 });
  }
  let body;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Request body must be valid JSON" }, { status: 400 });
  }
  try {
    return Response.json(await restPost(`/v1/tutor/${path[0]}`, body));
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
