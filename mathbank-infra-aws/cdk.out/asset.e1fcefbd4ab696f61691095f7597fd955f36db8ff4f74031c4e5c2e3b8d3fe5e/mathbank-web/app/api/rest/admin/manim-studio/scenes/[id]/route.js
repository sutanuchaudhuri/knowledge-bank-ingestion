import { restAdminGet, restAdminPost } from "../../../../../../../lib/restClient.js";
import { hasValidAdminSession } from "../../../../../../../lib/session.js";
import { createAdminManimStudioHandlers } from "../../../../../../../lib/adminManimStudioProxy.mjs";

const handlers = createAdminManimStudioHandlers({
  hasSession: hasValidAdminSession, get: restAdminGet, post: restAdminPost,
});

export async function GET(request, context) {
  const { id } = await context.params;
  return handlers.getScene(id);
}
