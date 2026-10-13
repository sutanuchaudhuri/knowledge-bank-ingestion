// Server-side proxy to mathbank-agent /run and /run_sse — see lib/agentRunProxy.mjs.
// The ADK user id is derived server-side (student_id or "anonymous"); a client userId is ignored.
import { restAuthGet } from "../../../../lib/restClient.js";
import { getStudentToken } from "../../../../lib/session.js";
import { createAgentIdentity } from "../../../../lib/agentIdentity.mjs";
import { createAgentRunHandler } from "../../../../lib/agentRunProxy.mjs";

const identity = createAgentIdentity({ getToken: getStudentToken, get: restAuthGet });

export const POST = createAgentRunHandler({ resolveUser: identity.resolve });
