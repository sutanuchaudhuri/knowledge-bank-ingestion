// POST {text, mode} -> mathbank-rest /v1/tutor/format-math with the student's token; offline fallback.
import { formatMath } from "../../../lib/voice.js";

export const dynamic = "force-dynamic";
export function POST(request) { return formatMath(request); }
