// Student step runtime proxy (Phase 7) — see lib/solveProxy.mjs for the allowlist.
import { restAuthGet, restAuthPost, restGet, restRaw } from "../../../../../lib/restClient.js";
import { getStudentToken } from "../../../../../lib/session.js";
import { createSolveHandlers } from "../../../../../lib/solveProxy.mjs";

const handlers = createSolveHandlers({
  getToken: getStudentToken,
  get: (path, token, query) => (token ? restAuthGet(path, token, query) : restGet(path, query)),
  post: restAuthPost,
  raw: restRaw,
});

export async function GET(request, context) {
  const { path } = await context.params;
  return handlers.GET(request, path);
}

export async function POST(request, context) {
  const { path } = await context.params;
  return handlers.POST(request, path);
}
