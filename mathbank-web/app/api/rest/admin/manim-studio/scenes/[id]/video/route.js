import { restAdminImage } from "../../../../../../../../lib/restClient.js";
import { hasValidAdminSession } from "../../../../../../../../lib/session.js";
import { createAdminManimStudioHandlers } from "../../../../../../../../lib/adminManimStudioProxy.mjs";

const handlers = createAdminManimStudioHandlers({
  hasSession: hasValidAdminSession,
  // restAdminImage is a generically-named "fetch with admin headers, return raw
  // Response" helper (mathbank-web/lib/restClient.js) — reused here for video bytes.
  video: restAdminImage,
});

export async function GET(request, context) {
  const { id } = await context.params;
  return handlers.getSceneVideo(id);
}
