import { restAdminGet, restAdminPost } from "../../../../../lib/restClient.js";
import { hasValidAdminSession } from "../../../../../lib/session.js";
import { invalidateGraphCache } from "../../../../../lib/cache.js";
import { createTutoringRoutesHandlers } from "../../../../../lib/tutoringRoutesProxy.mjs";

const handlers = createTutoringRoutesHandlers({
  hasSession: hasValidAdminSession, get: restAdminGet, post: restAdminPost, invalidate: invalidateGraphCache,
});
export const GET = handlers.GET;
export const POST = handlers.POST;
