import "server-only";
import OpenAI from "openai";

export function createNeonAIClient() {
  const { NEON_AI_GATEWAY_BASE_URL: base, NEON_AI_GATEWAY_TOKEN: apiKey } = process.env;
  if (!base || !apiKey) throw new Error("Neon AI Gateway settings are missing. Run make sync-neon-env.");
  const url = new URL(base);
  if (url.protocol !== "https:" || url.username || url.password) throw new Error("Neon AI Gateway must use credential-free HTTPS.");
  return new OpenAI({ baseURL: `${base.replace(/\/+$/, "")}/v1`, apiKey, maxRetries: 0 });
}
