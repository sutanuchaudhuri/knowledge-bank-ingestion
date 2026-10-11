// Cached node/link sample for one relationship view (see lib/graphConfig.js),
// shaped for react-force-graph-2d: { nodes: [{id,label,name}], links: [{source,target}] }.
import { withCache } from "../../../../../lib/cache.js";
import { runQuery, neo4j } from "../../../../../lib/neo4jClient.js";
import { RELATIONSHIPS, labelOf, GRAPH_DEFAULT_LIMIT, GRAPH_MAX_LIMIT } from "../../../../../lib/graphConfig.js";
import { nodeMetadata, edgeMetadata } from "../../../../../lib/graphMetadata.mjs";

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
  const rawReviewed = new URL(request.url).searchParams.get("reviewed");
  if (rawReviewed !== null && !["true", "false"].includes(rawReviewed)) {
    return Response.json({ error: "reviewed must be true or false" }, { status: 400 });
  }
  const reviewedOnly = config.pedagogical && rawReviewed !== "false";
  const where = reviewedOnly ? "WHERE r.review_status = 'REVIEWED' AND (NOT a:Skill OR a.review_status = 'REVIEWED') AND (NOT b:Skill OR b.review_status = 'REVIEWED')" : "";

  try {
    // v3: bumped cache key so stale non-randomized v2 samples (requirements/50 BUG-1) expire
    // immediately instead of being served for up to TTL_MS after this fix deploys.
    const data = await withCache(`graph:rel:v3:${rel}:${limit}:${Boolean(reviewedOnly)}`, TTL_MS, async () => {
      // BUG-1 fix (requirements/50): a plain `LIMIT` with no ORDER BY returns whatever
      // arbitrary order Neo4j's scan happens to produce, which in practice is far from a
      // representative sample (confirmed live: a `TESTS` sample of 1000 edges showed only
      // 1 of 619 real distinct concepts). Ordering by a per-row random value before LIMIT
      // gives an unbiased sample across the whole match set at the cost of visiting every
      // matching row once — the same cost the paired `count(*)` query already pays, so this
      // is not a new full-scan, just an additional cheap computation on an existing one.
      const [records, countRows] = await Promise.all([
        runQuery(
          `MATCH (a:${config.from})-[r:${config.type}]->(b:${config.to}) ${where} ` +
            `WITH a, b, r, rand() AS _sample_order ORDER BY _sample_order LIMIT $limit RETURN a, b, r`,
          { limit: neo4j.int(limit) }
        ),
        runQuery(`MATCH (a:${config.from})-[r:${config.type}]->(b:${config.to}) ${where} RETURN count(*) AS total`),
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
          nodesById.set(aId, { id: aId, label: config.from, name: labelOf(config.from, a.properties), properties: nodeMetadata(a.properties) });
        }
        if (!nodesById.has(bId)) {
          nodesById.set(bId, { id: bId, label: config.to, name: labelOf(config.to, b.properties), properties: nodeMetadata(b.properties) });
        }
        links.push({ source: aId, target: bId, type: config.type, properties: edgeMetadata(record.get("r").properties) });
      }

      return { nodes: [...nodesById.values()], links, limit, reviewedOnly: Boolean(reviewedOnly), totalRelationships, truncated: totalRelationships > records.length };
    });
    return Response.json(data);
  } catch (err) {
    return Response.json({ error: err.message }, { status: 502 });
  }
}
