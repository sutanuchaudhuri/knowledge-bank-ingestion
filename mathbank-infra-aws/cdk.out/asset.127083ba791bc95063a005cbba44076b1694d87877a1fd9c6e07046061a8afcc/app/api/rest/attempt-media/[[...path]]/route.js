import { getStudentToken, hasValidAdminSession } from "../../../../../lib/session.js";
import { createPrivateRuntimeHandler } from "../../../../../lib/privateRuntimeProxy.mjs";

const handle = createPrivateRuntimeHandler({
  domain: "attempt-media", getToken: getStudentToken, hasAdmin: hasValidAdminSession,
  adminKey: process.env.MATHBANK_ADMIN_API_KEY,
  baseUrl: process.env.MATHBANK_REST_BASE_URL || "http://127.0.0.1:8000",
});
export async function GET(request, context) { return handle(request, (await context.params).path); }
export const POST = GET;
export const PUT = GET;
export const PATCH = GET;
export const DELETE = GET;
