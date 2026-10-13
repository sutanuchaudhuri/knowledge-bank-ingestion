# Graph node enrichment migration — agent runbook

> Companion reference for [requirements/51 ENR-7](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/requirements/51_POSTGRES_METADATA_ENRICHMENT_FOR_GRAPH_CLUSTERING.md). This is the exact, step-by-step technical guide for whichever agent implements rich node properties — not a repeat of the research, just the precise before/after schema and file targets.

## What is broken today (confirmed live)

```cypher
MATCH (n:TheoryItem) RETURN properties(n) LIMIT 1
// -> {projection_kind, route_release_id, purpose, canonical_id, asset_key: "THEORY_STEP_1", review_status}
// NO title, NO description — labelOf() has nothing better to show than "THEORY_STEP_1".
```

Same for `Misconception` (`asset_key: "MIS_STEP_4"`) and `Claim` (`asset_key: "CLAIM_STEP_1"`).

## Exact root cause

1. [mathbank-rest/src/mathbank_rest/route_projection.py](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-rest/src/mathbank_rest/route_projection.py), function `metadata()`, inside the per-release loop (`for asset in assets.values(): nodes.append(...)`):
   ```python
   nodes.append({
       "id": aid,
       "label": LABELS[asset["kind"]],
       "properties": {
           "canonical_id": aid,
           "route_release_id": rid,
           "asset_key": asset["key"],
           "purpose": asset["purpose"],
           "review_status": "REVIEWED",
       },
   })
   ```
   `asset` at this point **is already** the full `pedagogy.route_asset.content` JSONB (see `assets = {row["content"]["key"]: row["content"] for row in asset_rows}` a few lines above) — `asset["title"]`, `asset["description"]` and, for `MISCONCEPTION` specifically, `asset["symptom"]`/`asset["why_wrong"]`/`asset["correct_model"]` are all present in memory and simply never copied into `properties`.
2. `_project()` (same file) writes exactly that `properties` dict onto the Neo4j node via `SET n += row.properties` — nothing is lost after `metadata()` returns; the entire gap is at the one call site above.
3. [mathbank-web/lib/graphConfig.js](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-web/lib/graphConfig.js), function `labelOf()`:
   ```js
   case "Claim":
   case "Misconception":
   case "TheoryItem":
   case "LearningItem":
     return props.asset_key || props.external_id || label;
   ```
   Even after step 1 is fixed, this must change too, or the new `title` property is silently ignored in the UI.

## Target property schema (per node label)

| Label | New properties to add | Source field on `asset` (= `route_asset.content`) |
|---|---|---|
| `TheoryItem` | `title`, `description` | `asset["title"]`, `asset["description"]` |
| `Misconception` | `title`, `description`, `symptom`, `why_wrong`, `correct_model` | same-named keys on `asset` (see `route_enrichment.py`'s `MISCONCEPTION` content dict) |
| `Claim` | `title`, `description`, `canonical_expression` | same-named keys on `asset` |
| `LearningItem` (diagnostic kind only — not the textbook-import `LearningItem`, which already has `question_text` via a different path) | `title`, `question`, `expected_answer` | same-named keys on `asset`. **Do not** use `asset["description"]` for this one — it is a hardcoded literal (`"Check the current step's misconception."`), confirmed live, not real content. |

All four kinds already have these fields in Postgres today (`route_asset.content`) — this is a **pure property-projection fix**, not a new authoring/generation requirement. No backfill script is needed for the *property* half; the next `route_projection.project()` run naturally picks it up because it does a full delete-and-recreate of the `projection_kind='tutoring_routes'` layer.

## Migration steps

1. Edit `route_projection.py`'s `metadata()`: extend the `properties` dict in the node-building loop per the table above, branching on `asset["kind"]` the same way the existing `LABELS[asset["kind"]]` lookup already does.
2. Edit `graphConfig.js`'s `labelOf()`: prefer `props.title` over `props.asset_key` for these four cases (keep `asset_key`/`external_id`/`label` as the fallback chain for nodes that genuinely have no title).
3. Re-run the projection: `POST` to whatever endpoint/CLI calls `route_projection.project()` (check `routers/` for the mount point, or call it directly via the same pattern used in this session's other one-off scripts — a `.venv/bin/python -c "from mathbank_rest.route_projection import project; print(project())"` against the live DB is sufficient and matches this repo's existing idempotent, delete-then-recreate design — safe to re-run).
4. Validate:
   ```cypher
   MATCH (n:Misconception) WHERE n.title IS NOT NULL RETURN count(n)
   // expect close to the full Misconception count, not zero
   ```
5. Spot-check the UI: open `/graph/theory-techniques` (or any of the misconception-* tabs) and confirm the node tooltip/detail panel shows real text instead of `THEORY_STEP_N`/`MIS_STEP_N`.
6. Update [requirements/50](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/requirements/50_NEO4J_KNOWLEDGE_GRAPH_QUALITY_BUGS.md) and [requirements/51](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/requirements/51_POSTGRES_METADATA_ENRICHMENT_FOR_GRAPH_CLUSTERING.md) with before/after screenshots, following the established pattern in those two documents' own `assets/` folders.

## Generation-time note (do not implement until ENR-2's embeddings exist)

Once `knowledge.misconception_embedding` (ENR-2) exists, `route_enrichment.py`'s `enrich()` should retrieve the nearest existing canonical misconceptions (by embedding similarity) and include them in the prompt sent to the model, instructing it to reuse an existing one when it genuinely fits rather than always minting a new one. This is a generation-time deduplication habit, not a property-projection fix — do not conflate the two; the property fix above is safe to ship independently and immediately.
