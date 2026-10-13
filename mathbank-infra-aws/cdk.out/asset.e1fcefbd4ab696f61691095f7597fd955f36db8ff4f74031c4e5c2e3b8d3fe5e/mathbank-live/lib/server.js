// Shared server-side singletons for route handlers.
import { createFormatHandler, createVoiceHandlers } from "mathbank-widgets/server";
import { deterministicFormat } from "mathbank-widgets/format";
import { authHeaders } from "./gateway.mjs";
import { createRest } from "./rest.mjs";
import { studentToken } from "./session.js";

export const rest = createRest();
export const voice = createVoiceHandlers();
export const formatMath = createFormatHandler({
  getToken: studentToken,
  post: (path, token, body) => rest({ method: "POST", path, body, headers: authHeaders({ role: "STUDENT", token }) }),
  fallback: deterministicFormat,
});

export const json = (body, status = 200) => Response.json(body, { status });
export const errorJson = (err) => json({ error: err.message, code: err.code || null }, err.status && err.status < 600 ? err.status : 502);
