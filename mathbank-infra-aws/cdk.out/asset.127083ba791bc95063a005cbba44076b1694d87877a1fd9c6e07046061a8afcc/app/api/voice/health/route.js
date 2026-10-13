// GET -> {configured, reachable} using the free /v1/models endpoint (no characters billed).
import { voice } from "../../../../lib/voice.js";

export const dynamic = "force-dynamic";
export function GET() { return voice.health(); }
