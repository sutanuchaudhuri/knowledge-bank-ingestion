// Admin agent conversations (read-only) — see lib/conversationsProxy.mjs.
import { restAdminGet } from "../../../../../lib/restClient.js";
import { hasValidAdminSession } from "../../../../../lib/session.js";
import { createAdminConversationHandlers } from "../../../../../lib/conversationsProxy.mjs";

const handlers = createAdminConversationHandlers({ hasSession: hasValidAdminSession, get: restAdminGet });

export const GET = handlers.GET;
