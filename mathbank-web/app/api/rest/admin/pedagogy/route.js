import { restAdminGet, restAdminPost } from "../../../../../lib/restClient.js";
import { hasValidAdminSession } from "../../../../../lib/session.js";
import { invalidateGraphCache } from "../../../../../lib/cache.js";
import { createAdminPedagogyHandlers } from "../../../../../lib/adminPedagogyProxy.mjs";

const handlers = createAdminPedagogyHandlers({
  hasSession: hasValidAdminSession,
  get: restAdminGet,
  post: restAdminPost,
  invalidate: invalidateGraphCache,
});

export const GET = handlers.GET;
export const POST = handlers.POST;
