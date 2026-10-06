import { voice } from "../../../../lib/server.js";

export const dynamic = "force-dynamic";
export function GET(request) { return voice.health(request); }
