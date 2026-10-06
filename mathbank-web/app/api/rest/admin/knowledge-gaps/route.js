// Admin knowledge gaps & recovery plans (read-only) — see lib/adminGapsProxy.mjs for the allowlist.
import { restAdminGet } from "../../../../../lib/restClient.js";
import { hasValidAdminSession } from "../../../../../lib/session.js";
import { createAdminGapHandlers } from "../../../../../lib/adminGapsProxy.mjs";

const handlers = createAdminGapHandlers({ hasSession: hasValidAdminSession, get: restAdminGet });

export const GET = handlers.GET;
