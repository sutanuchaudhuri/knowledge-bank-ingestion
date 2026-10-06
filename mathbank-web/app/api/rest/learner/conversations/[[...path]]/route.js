// Student's own agent conversations (read-only) — see lib/conversationsProxy.mjs.
import { restAuthGet } from "../../../../../../lib/restClient.js";
import { getStudentToken } from "../../../../../../lib/session.js";
import { createLearnerConversationHandlers } from "../../../../../../lib/conversationsProxy.mjs";

const handlers = createLearnerConversationHandlers({ getToken: getStudentToken, get: restAuthGet });

export async function GET(request, context) {
  const { path } = await context.params;
  return handlers.GET(request, path || []);
}
