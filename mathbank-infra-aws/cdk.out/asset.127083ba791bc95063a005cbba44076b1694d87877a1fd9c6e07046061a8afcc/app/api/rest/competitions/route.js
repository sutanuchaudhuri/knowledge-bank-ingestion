// Competitions grid, enriched with per-competition coverage counts (papers/problems)
// since there's no standalone /v1/papers endpoint yet.
import { restGet } from "../../../../lib/restClient.js";

export async function GET() {
  try {
    const [competitions, coverage] = await Promise.all([
      restGet("/v1/competitions"),
      restGet("/v1/corpus/coverage"),
    ]);
    const coverageByName = Object.fromEntries(coverage.map((c) => [c.competition, c]));
    const items = competitions.map((c) => ({ ...c, ...(coverageByName[c.name] || {}) }));
    return Response.json({ items });
  } catch (err) {
    return Response.json({ error: err.message }, { status: err.status || 502 });
  }
}
