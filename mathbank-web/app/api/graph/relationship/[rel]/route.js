// Cached node/link sample for one relationship view (see lib/graphConfig.js),
// shaped for react-force-graph-2d: { nodes: [{id,label,name}], links: [{source,target}] }.
import { withCache } from "../../../../../lib/cache.js";
import { runQuery, neo4j } from "../../../../../lib/neo4jClient.js";
import { RELATIONSHIPS, labelOf } from "../../../../../lib/graphConfig.js";

const TTL_MS = 5 * 60 * 1000; // 5 min — matches all /api/graph/* cache TTLs
const SAMPLE_LIMIT = 150; // caps canvas rendering cost for the force-directed layout

export async function GET(_request, context) {
  const { rel } = await context.params;
  const config = RELATIONSHIPS[rel];
  if (!config) {
    return Response.json({ error: `unknown relationship view: ${rel}` }, { status: 404 });
  }

  try {
    const data = await withCache(`graph:rel:${rel}`, TTL_MS, async () => {
      const records = await runQuery(
        `MATCH (a:${config.from})-[r:${config.type}]->(b:${config.to}) RETURN a, b LIMIT $limit`,
        { limit: neo4j.int(SAMPLE_LIMIT) }
      );

      const nodesById = new Map();
      const links = [];
      for (const record of records) {
        const a = record.get("a");
        const b = record.get("b");
        const aId = a.properties.canonical_id;
        const bId = b.properties.canonical_id;
        if (!nodesById.has(aId)) {
          nodesById.set(aId, { id: aId, label: config.from, name: labelOf(config.from, a.properties) });
        }
        if (!nodesById.has(bId)) {
          nodesById.set(bId, { id: bId, label: config.to, name: labelOf(config.to, b.properties) });
        }
        links.push({ source: aId, target: bId });
      }

      return { nodes: [...nodesById.values()], links, truncated: records.length >= SAMPLE_LIMIT };
    });
    return Response.json(data);
  } catch (err) {
    return Response.json({ error: err.message }, { status: 502 });
  }
}
