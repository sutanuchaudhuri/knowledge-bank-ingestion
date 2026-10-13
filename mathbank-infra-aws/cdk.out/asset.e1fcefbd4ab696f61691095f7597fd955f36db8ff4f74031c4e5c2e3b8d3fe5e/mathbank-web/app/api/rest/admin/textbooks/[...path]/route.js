// Admin textbook corpus browser (read-only) — see lib/adminTextbooksProxy.mjs for the allowlist.
import { restAdminGet, restAdminRaw } from "../../../../../../lib/restClient.js";
import { hasValidAdminSession } from "../../../../../../lib/session.js";
import { createTextbookHandlers } from "../../../../../../lib/adminTextbooksProxy.mjs";

const handlers = createTextbookHandlers({ hasSession: hasValidAdminSession, get: restAdminGet, raw: restAdminRaw });

export async function GET(request, context) {
  const { path } = await context.params;
  return handlers.GET(request, path);
}
