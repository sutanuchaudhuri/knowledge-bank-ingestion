import { voice } from "../../../../lib/server.js";

export const dynamic = "force-dynamic";
export function POST(request) { return voice.tts(request); }
