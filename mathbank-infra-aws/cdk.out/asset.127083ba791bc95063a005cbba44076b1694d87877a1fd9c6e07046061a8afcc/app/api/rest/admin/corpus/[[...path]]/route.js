import { restAdminGet, restAdminSend, restAdminImage } from "../../../../../../lib/restClient.js";
import { hasValidAdminSession } from "../../../../../../lib/session.js";
import { createCorpusHandlers } from "../../../../../../lib/adminCorpusProxy.mjs";

const handle = createCorpusHandlers({
  hasSession: hasValidAdminSession,
  get: restAdminGet,
  send: restAdminSend,
  async image(path) {
    const upstream = await restAdminImage(path);
    return new Response(upstream.body, { headers: {
      "Content-Type": "image/png", "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
    } });
  },
});

async function route(request, context) {
  const { path } = await context.params;
  return handle(request, path || []);
}

export const GET = route;
export const POST = route;
export const PUT = route;
