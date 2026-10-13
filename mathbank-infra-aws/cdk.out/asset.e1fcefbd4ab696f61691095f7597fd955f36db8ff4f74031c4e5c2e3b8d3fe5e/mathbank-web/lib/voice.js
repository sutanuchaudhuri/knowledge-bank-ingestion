// Server-only: ElevenLabs voice + math-format proxies (requirements 29). Shared logic lives in
// mathbank-widgets/server so mathbank-web and mathbank-live behave identically.
import { createFormatHandler, createVoiceHandlers } from "mathbank-widgets/server";
import { deterministicFormat } from "mathbank-widgets/format";
import { restAuthPost } from "./restClient.js";
import { getStudentToken } from "./session.js";

export const voice = createVoiceHandlers();
export const formatMath = createFormatHandler({ getToken: getStudentToken, post: restAuthPost, fallback: deterministicFormat });
