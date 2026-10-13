import { restAdminGet, restAdminPost } from "../../../../../../lib/restClient.js";
import { hasValidAdminSession } from "../../../../../../lib/session.js";
import { createAdminManimStudioHandlers } from "../../../../../../lib/adminManimStudioProxy.mjs";

const handlers = createAdminManimStudioHandlers({
  hasSession: hasValidAdminSession, get: restAdminGet, post: restAdminPost,
});

export const GET = () => handlers.getScenes();
