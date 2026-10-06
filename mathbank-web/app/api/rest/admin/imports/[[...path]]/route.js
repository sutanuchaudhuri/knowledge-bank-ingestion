// Admin import / reconciliation / DAG review — see lib/adminImportsProxy.mjs for the allowlist.
import { restAdminGet, restAdminSend } from "../../../../../../lib/restClient.js";
import { hasValidAdminSession } from "../../../../../../lib/session.js";
import { createImportHandlers } from "../../../../../../lib/adminImportsProxy.mjs";

const handlers = createImportHandlers({ hasSession: hasValidAdminSession, get: restAdminGet, send: restAdminSend });

export async function GET(request, context) {
  const { path } = await context.params;
  return handlers.GET(request, path);
}

export async function POST(request) {
  return handlers.POST(request);
}
