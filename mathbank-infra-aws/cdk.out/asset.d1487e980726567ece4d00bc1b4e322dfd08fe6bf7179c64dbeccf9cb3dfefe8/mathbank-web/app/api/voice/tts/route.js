// POST {text} -> audio/mpeg via ElevenLabs (key attached server-side; length-capped, rate-limited).
import { voice } from "../../../../lib/voice.js";

export const dynamic = "force-dynamic";
export function POST(request) { return voice.tts(request); }
