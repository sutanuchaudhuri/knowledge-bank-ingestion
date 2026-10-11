import { restAdminGet } from "../../../../../../lib/restClient.js";
import { hasValidAdminSession } from "../../../../../../lib/session.js";
import { createAdminManimStudioHandlers } from "../../../../../../lib/adminManimStudioProxy.mjs";

const handlers = createAdminManimStudioHandlers({ hasSession: hasValidAdminSession, get: restAdminGet });

export const GET = () => handlers.getCandidates();
