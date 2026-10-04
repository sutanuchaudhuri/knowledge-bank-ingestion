// Cached node/link sample for one relationship view (see lib/graphConfig.js),
// shaped for react-force-graph-2d: { nodes: [{id,label,name}], links: [{source,target}] }.
import { withCache } from "../../../../../lib/cache.js";
import { runQuery, neo4j } from "../../../../../lib/neo4jClient.js";
import { RELATIONSHIPS, labelOf, GRAPH_DEFAULT_LIMIT, GRAPH_MAX_LIMIT } from "../../../../../lib/graphConfig.js";

const TTL_MS = 5 * 60 * 1000; // 5 min — matches all /api/graph/* cache TTLs
export async function GET(request, context) {
  const { rel } = await context.params;
  const config = Object.hasOwn(RELATIONSHIPS, rel) ? RELATIONSHIPS[rel] : null;
  if (!config) {
    return Response.json({ error: `unknown relationship view: ${rel}` }, { status: 404 });
  }

  const rawLimit = new URL(request.url).searchParams.get("limit");
  const limit = rawLimit === null ? GRAPH_DEFAULT_LIMIT : Number(rawLimit);
  if (!Number.isInteger(limit) || limit < 1 || limit > GRAPH_MAX_LIMIT) {
    return Response.json({ error: `limit must be an integer between 1 and ${GRAPH_MAX_LIMIT}` }, { status: 400 });
  }

  try {
    const data = await withCache(`graph:rel:${rel}:${limit}`, TTL_MS, async () => {
      const [records, countRows] = await Promise.all([
        runQuery(
          `MATCH (a:${config.from})-[r:${config.type}]->(b:${config.to}) RETURN a, b LIMIT $limit`,
          { limit: neo4j.int(limit) }
        ),
        runQuery(`MATCH (:${config.from})-[:${config.type}]->(:${config.to}) RETURN count(*) AS total`),
      ]);
      const totalRelationships = countRows[0].get("total").toNumber();

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

      return { nodes: [...nodesById.values()], links, limit, totalRelationships, truncated: totalRelationships > records.length };
    });
    return Response.json(data);
  } catch (err) {
    return Response.json({ error: err.message }, { status: 502 });
  }
}
