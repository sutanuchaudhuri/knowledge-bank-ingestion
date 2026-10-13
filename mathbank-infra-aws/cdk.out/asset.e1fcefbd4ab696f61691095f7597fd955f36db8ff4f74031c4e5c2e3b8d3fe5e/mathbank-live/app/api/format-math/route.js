import { formatMath } from "../../../lib/server.js";

export const dynamic = "force-dynamic";
export function POST(request) { return formatMath(request); }
