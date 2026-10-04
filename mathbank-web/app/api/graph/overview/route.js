// Cached summary stats for the /graph overview page: node counts by label and
// relationship counts by type, plus the list of available relationship views.
import { withCache } from "../../../../lib/cache.js";
import { runQuery } from "../../../../lib/neo4jClient.js";
import { RELATIONSHIPS } from "../../../../lib/graphConfig.js";

const TTL_MS = 5 * 60 * 1000; // 5 min — matches all /api/graph/* cache TTLs

export async function GET() {
  try {
    const data = await withCache("graph:overview", TTL_MS, async () => {
      const [labelRows, relRows] = await Promise.all([
        runQuery("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC"),
        runQuery("MATCH ()-[r]->() RETURN type(r) AS rel, count(*) AS n ORDER BY n DESC"),
      ]);
      return {
        nodeCounts: labelRows.map((r) => ({ label: r.get("label"), count: r.get("n").toNumber() })),
        relationshipCounts: relRows.map((r) => ({ type: r.get("rel"), count: r.get("n").toNumber() })),
        views: Object.entries(RELATIONSHIPS).map(([slug, cfg]) => ({ slug, ...cfg })),
      };
    });
    return Response.json(data);
  } catch (err) {
    return Response.json({ error: err.message }, { status: 502 });
  }
}
