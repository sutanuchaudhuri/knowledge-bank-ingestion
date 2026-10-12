import { getStudentToken } from "../../../../lib/session.js";
import { restAuthGet } from "../../../../lib/restClient.js";
import { renderAsymptote } from "../../../../lib/asymptoteRenderer.mjs";
import { createAsymptoteHandler } from "../../../../lib/asymptoteProxy.mjs";

export const runtime = "nodejs";

export const POST = createAsymptoteHandler({
  authenticate: async () => {
    const token = await getStudentToken();
    if (!token) return false;
    await restAuthGet("/v1/learner/me", token);
    return true;
  },
  render: renderAsymptote,
});
