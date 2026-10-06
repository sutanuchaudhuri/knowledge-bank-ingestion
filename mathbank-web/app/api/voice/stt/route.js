// POST multipart {file} -> {text} via ElevenLabs speech-to-text (scribe_v1).
import { voice } from "../../../../lib/voice.js";

export const dynamic = "force-dynamic";
export function POST(request) { return voice.stt(request); }
