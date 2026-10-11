# 50. Neo4j knowledge-graph quality: scattered views, missing misconception linkage, dead relationship, and non-representative sampling (bugs + research report)

## 0. Status and scope

| | |
|---|---|
| Status | **IMPLEMENTED and live-verified.** All five bugs (BUG-1..BUG-5) fixed and verified live against the real AuraDB instance; see §9 for the per-requirement evidence table. BUG-5 was discovered *after* BUG-2 originally shipped — a routine, uninterrupted re-run of `route_projection.project()` silently zeroed out BUG-2's own fix via a node-level `DETACH DELETE` interaction never previously understood (full incident: [GOTCHAS.md §24](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/GOTCHAS.md)) — now fixed permanently by folding the projection into `route_projection.py` itself (requirements/51 ENR-1/ENR-4), which also broadened coverage to `theory-concepts`/`theory-skills`/`item-concepts`/`item-skills` (four brand-new tabs; see doc 51). |
| Trigger | User visually audited `/graph` and its ~29 relationship tabs (especially `/graph/theory-techniques`, `/graph/item-techniques`, `/graph/item-misconceptions`) and reported: (1) many nodes are visually concentrated/clustered with no apparent reason, (2) misconception↔concept/skill/technique linkage does not exist — only misconception-to-id relationships, (3) requested a research report on clustering/relationship opportunities, to be followed by a fix plan requiring explicit approval before implementation. A later full audit (prompted by the user noticing `misconception-skills` had regressed to 0 edges, plus several other tabs still sparse) found and fixed BUG-5 and broadened ENR-4; see doc 51 §9 for the complete 37-tab table. |
| Grounding | Every number in this document was read live from the running `mathbank-web` dev server (`localhost:5173/graph/*`, screenshotted) and cross-checked against direct Cypher queries against the live Neo4j instance and the live Postgres source tables it was projected from — nothing here is inferred from source-code reading alone. |
| Screenshots | All 32 (now 37, after adding the three Misconception→Concept/Skill/Technique tabs and the four new theory-/item-→Concept/Skill tabs) relationship-view tabs + the overview page captured both **before** ([assets/50_graph_quality/before/](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/requirements/assets/50_graph_quality/before)) and **after** ([assets/50_graph_quality/after/](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/requirements/assets/50_graph_quality/after), [assets/51_misconception_canonicalization/after/](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/requirements/assets/51_misconception_canonicalization/after)) the fix. |

### Progress tracker

| ID | Item | Status |
|---|---|---|
| BUG-1 | Non-representative graph sampling (`ORDER BY rand()`) | ✅ IMPLEMENTED — live-verified |
| BUG-2 | Misconception → Concept/Skill/Technique linkage (`RELATES_TO`) | ✅ IMPLEMENTED — live-verified, 78,781 edges (re-fixed after BUG-5 regression; see below) |
| BUG-3 | Dead `solution-approaches` tab | ✅ IMPLEMENTED — removed, now 404s |
| BUG-4 | Faint/flat rendering (link contrast, degree-scaled nodes) | ✅ IMPLEMENTED — live-verified |
| BUG-5 | `route_projection.project()`'s node DETACH DELETE silently destroyed BUG-2's companion-script fix | ✅ IMPLEMENTED — folded into `route_projection.py` itself, immune to recurrence by construction |
| NGQ-7 | Rich node display properties (not `MIS_STEP_4`-style keys) | ✅ IMPLEMENTED — live-verified (found mid-implementation) |
| DGAP-1 | `practices-skill` near-empty (2 rows) | ✅ IMPLEMENTED — fixed via [doc 51 ENR-3](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/requirements/51_POSTGRES_METADATA_ENRICHMENT_FOR_GRAPH_CLUSTERING.md); live-verified 2 → 12,043 `PRACTICES` edges |
| DGAP-2 | `tests-skill` near-empty (1 row) | ✅ IMPLEMENTED — same fix (ENR-3); live-verified 1 → 7,799 `TESTS` edges |
| §6 | `PRACTICES`/`TESTS` relationship-type reuse across label pairs (modeling smell) | ⏳ NOT FIXED — documented only, no schema-naming cleanup done (now a larger surface area: `EXPLAINS`/`PRACTICES` are also reused across Technique/Concept/Skill target pairs as of ENR-4's broadened fix) |

All implemented items above are complete and live-verified; DGAP-1/DGAP-2 and BUG-5 are now also resolved (via doc 51's ENR-1/ENR-3/ENR-4, applied to the underlying Postgres content and re-projected into Neo4j) — only the §6 modeling-smell naming cleanup remains intentionally deferred, planning-only, under [doc 51](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/requirements/51_POSTGRES_METADATA_ENRICHMENT_FOR_GRAPH_CLUSTERING.md)'s content-enrichment track.

## 1. Executive summary

The graph is **not broken or empty** — it holds 483,840 nodes and 1,288,967 relationships, and several views (the pure taxonomy ones: concept/skill hierarchy, prerequisites, `BUILDS_ON`) are genuinely well-formed. But four distinct, independently-confirmed problems combine to make most of the 29 "Pedagogy" tabs look exactly as the user described — scattered dust with no visible value:

1. **BUG-1 (code, high severity):** the graph-view API samples with `LIMIT $limit` and **no `ORDER BY`**, so every "zoomed out" view shows an arbitrary, non-representative, often degenerate slice of the real data — confirmed concretely: `Problem -[:TESTS]-> Concept` really touches 619 distinct concepts with a sensible long-tail distribution, but the naive `LIMIT 1000` sample the UI actually requests returns **1** distinct concept.
2. **BUG-2 (schema/projection gap, high severity):** `Misconception` nodes have **zero** direct relationships to `Concept`, `Skill`, or `Technique` — confirmed by a live Cypher query. Misconceptions only connect to the per-checkpoint "process" layer (`RouteStep`, `LearningItem`, `TheoryItem`), each at an exact 1:1 ratio (80,168 = 80,168 = 80,168 = 80,168), because they are auto-generated one-per-route-checkpoint, not authored as a reusable, taxonomy-linked catalog. This is exactly the user's complaint: *"misconcept to concept to skills or technique is not there, only misconcept id to id."*
3. **BUG-3 (code, medium severity):** the `/graph/solution-approaches` tab is **permanently dead** — its config points at a Cypher relationship type (`USES_APPROACH`) that does not exist anywhere in the graph (confirmed via `CALL db.relationshipTypes()`). It will show "No relationships found" forever, regardless of how much data is added elsewhere.
4. **BUG-4 (rendering default, low-medium severity):** default link color/width (`#cbd5e1` at `0.5px`) is too faint to read once a force layout has spread a high-cardinality 1:1 bipartite sample across a large canvas — edges **are** being drawn (confirmed by pixel-level crop/zoom), they are just nearly invisible at normal zoom, compounding BUG-2's structural flatness.

Separately, two **data-population gaps** (not code bugs — the code faithfully projects what Postgres holds) make two tabs almost entirely empty:
- `knowledge.problem_skill` has 38,105 `REQUIRES` rows but only **2** `PRACTICES` and **1** `TESTS` rows, out of 12,542 problems × 6,208 skills.

None of this requires discarding or re-architecting the existing graph — it requires (a) fixing the sampling query, (b) adding one new **derived** relationship (Misconception → Concept/Skill/Technique via the already-existing `RouteStep` join — confirmed **99.3%** of misconceptions can be linked this way with zero new authoring), (c) removing or implementing the dead `solution-approaches` view, and (d) a rendering default tweak. Full technical plan in §9.

## 2. Methodology

1. Opened the live `mathbank-web` dev server (already running on `:5173`) in the integrated browser at desktop width (1440×900).
2. Scripted a full sweep of all 32 `/graph/*` relationship views (Playwright automation), capturing a full-page screenshot and the rendered stats panel (`NODES IN SAMPLE`, `RELATIONSHIPS IN SAMPLE`, `TOTAL … RELATIONSHIPS`, `COVERAGE`) for each — saved under `assets/50_graph_quality/before/` and parsed into `stats_parsed.json` alongside it.
3. For every suspicious number, went **directly to the live Neo4j instance** (`mathbank_rest.db.graph.driver`, the same driver the REST service uses) and ran independent Cypher queries to confirm or refute the hypothesis — e.g. counting distinct concepts touched by `TESTS` (619) versus what a naive `LIMIT 1000` sample actually returns (1).
4. For the two near-empty views, traced the Neo4j projector (`mathbank-graph/etl/project_from_postgres.py`) back to its **Postgres source table** (`knowledge.problem_skill`) and confirmed the gap originates in Postgres, not in the projection code — the ETL is not the bug there.
5. Read the exact frontend source (`mathbank-web/lib/graphConfig.js`, `app/api/graph/relationship/[rel]/route.js`, `app/graph/[rel]/page.jsx`) to pin every finding to a specific file and line before proposing a fix.

## 3. Live graph inventory (confirmed via the Overview tab, `assets/50_graph_quality/before/overview.png`)

| Metric | Value |
|---|---|
| Total nodes | 483,840 |
| Total relationships | 1,288,967 |
| Node labels | 19 |
| Relationship types (reported) | 33 (`CALL db.relationshipTypes()` enumerates 32 live; the 1-off is a cosmetic overview-cache detail, not investigated further here) |

Top node counts: `LearningItem` 91,354 · `Claim`/`Misconception`/`TheoryItem`/`RouteStep` 80,168 each · `Solution` 18,749 · `RouteRelease` 18,589 · `Problem` 12,542 · `SolutionStep` 7,814 · `Skill` 6,208 · `Concept` 2,936 · `SolutionPart` 2,001 · `Technique` 1,484 · `Paper` 1,391.

The exact repetition of **80,168** across four different labels is itself the first clue: it is the total `RouteStep` count, meaning `Claim`, `Misconception`, and `TheoryItem` are each manufactured **exactly once per route checkpoint**, not drawn from a smaller, curated, reusable catalog.

## 4. Bug catalog

### BUG-1 — Graph-view sampling is non-representative (no `ORDER BY`, no diversity strategy) — ✅ IMPLEMENTED

- **Severity:** High — this is the dominant cause of "scattered/concentrated" across most tabs with a total relationship count above the 1,000-row UI sample cap.
- **Live evidence:**
  ```cypher
  // Real distribution: 619 distinct concepts, sensible long tail
  MATCH (p:Problem)-[r:TESTS]->(c:Concept) RETURN count(DISTINCT c), count(*)
  // -> 619 distinct, 53796 total. Top: Algebra 4708, Combinatorics 2739, Equations & Systems 2487, Geometry 2295 ...

  // What the UI actually samples:
  MATCH (p:Problem)-[r:TESTS]->(c:Concept) RETURN p, c LIMIT 1000
  // -> 1 distinct concept across all 1000 rows
  ```
  Screenshot: `assets/50_graph_quality/before/tests.png` shows a single concentrated mass — this is the direct visual symptom.
- **Root cause:** [app/api/graph/relationship/[rel]/route.js](</Volumes/External/Developer/knowledge-bank-ingestion/mathbank-web/app/api/graph/relationship/[rel]/route.js>) issues `MATCH (a:${config.from})-[r:${config.type}]->(b:${config.to}) ${where} RETURN a, b, r LIMIT $limit` — Neo4j has no implicit ordering guarantee, so without an explicit `ORDER BY` the planner returns whatever its scan/storage order happens to produce, which in practice clusters on index/creation order rather than sampling across the real distribution.
- **Proposed fix:** add `ORDER BY rand()` (acceptable at these row counts given the query already does a full relationship scan for the paired `count(*)` call) **or**, better, a stratified sample (e.g. `ORDER BY id(r) % N` bucketing, or sampling per-distinct-target-node up to a cap) so the legend's node diversity reflects the real distribution. Given the existing `countRows` query already does a full scan for the total, a `WITH a, b, r, rand() AS rnd ORDER BY rnd LIMIT $limit` is a minimal, low-risk change.

### BUG-2 — `Misconception` has no direct relationship to `Concept`/`Skill`/`Technique` — ✅ IMPLEMENTED (superseding fix; original derived-join version regressed, see BUG-5)

- **Severity:** High — this is the user's second named complaint, confirmed exactly.
- **Live evidence:**
  ```cypher
  MATCH (m:Misconception)-[r]-(other) RETURN type(r), labels(other), count(*)
  // -> DIAGNOSED_BY<->LearningItem 80168; TESTS_MISCONCEPTION<->LearningItem 80168;
  //    REMEDIATED_BY<->TheoryItem 80168; CAN_TRIGGER<->RouteStep 80168. Nothing else.

  MATCH (m:Misconception)-[r]-(t) WHERE t:Concept OR t:Skill OR t:Technique RETURN count(*)
  // -> 0
  ```
  Postgres confirms this is not a missed projection step but a genuine schema gap: `knowledge.misconception` has no `concept_id`/`skill_id`/`technique_id`/`taxonomy_node_id` column at all — only links to downstream pedagogy artifacts (`misconception_evidence_rule`, `video_segment_misconception`, `interaction_instance_misconception`, `micro_course_state_misconception`).
- **The good news, confirmed live:** a transitive path already exists through the shared `RouteStep`:
  ```cypher
  MATCH (rs:RouteStep)-[:CAN_TRIGGER]->(m:Misconception)
  OPTIONAL MATCH (rs)-[:REQUIRES]->(target) WHERE target:Concept OR target:Skill OR target:Technique
  WITH m, count(DISTINCT target) AS n RETURN count(*), sum(CASE WHEN n>0 THEN 1 ELSE 0 END)
  // -> 80168 total; 79591 (99.3%) already derivable via the RouteStep's own REQUIRES edges
  ```
- **Root cause:** the graph projector ([mathbank-graph/etl/project_from_postgres.py](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-graph/etl/project_from_postgres.py)) never computes this composition; it only projects what each Postgres table directly states.
- **Original fix (now superseded — see BUG-5):** a companion script, `mathbank-graph/etl/project_misconception_relations.py`, added one derived `RELATES_TO` relationship per misconception, composed from `RouteStep.REQUIRES`. Live-verified working at the time (82,019 edges). **This later silently regressed to 0 edges** (BUG-5) because of an interaction with `route_projection.py`'s own rebuild cycle that was not understood when this fix first shipped.
- **Final fix (requirements/51 ENR-1/ENR-4), live-verified:** `RELATES_TO` is now projected directly inside `route_projection.py`'s own `metadata()`/`_project()`, sourced from the canonical `knowledge.misconception_taxonomy_link` junction table (built by ENR-1's catalog backfill) instead of the derived RouteStep join — both more accurate (reads each misconception's *own* taxonomy links, not a borrowed approximation from its RouteStep) and immune to BUG-5's regression (it is recreated by the very rebuild that could otherwise destroy it, every time). Current live counts: `misconception-concepts` 40,320 edges (36,991 distinct Misconceptions, fan-in 18.39), `misconception-skills` 27,156 edges (fan-in 8.16), `misconception-techniques` 11,305 edges (fan-in 9.21) — real, dense network structure, confirmed via screenshot ([after/misconception-skills.png](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/requirements/assets/51_misconception_canonicalization/after/misconception-skills.png)), not the previous disconnected-dust pattern.

### BUG-3 — `/graph/solution-approaches` is permanently dead — ✅ IMPLEMENTED

- **Severity:** Medium — not visually broken (the UI's own empty-state handling works correctly), but the feature can never work as configured.
- **Live evidence:** `CALL db.relationshipTypes()` enumerates 32 real types; `USES_APPROACH` is not among them. Screenshot `assets/50_graph_quality/before/solution-approaches.png` shows the (correctly rendered) "No relationships found" state with `0`/`0`/`0` stats.
- **Root cause:** [lib/graphConfig.js](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-web/lib/graphConfig.js) line defining `"solution-approaches": { type: "USES_APPROACH", from: "Solution", to: "Technique", ... }` references a relationship type nothing ever creates.
- **Proposed fix:** either (a) remove the tab until a real `Solution -[:USES_APPROACH]-> Technique` (or reuse `Problem -[:USES_TECHNIQUE]-> Technique`, which already has 30,843 real edges) projection is built, or (b) point the config at the existing populated relationship. Recommend (b): retarget to the already-populated `USES_TECHNIQUE` edge type scoped from `Solution` via its `Problem`, or simplest of all, just repoint `from`/`type` to the existing `Problem -[:USES_TECHNIQUE]-> Technique` pairing under a corrected title — avoids inventing new projection work for what is cosmetically a duplicate of an existing, working view.

### BUG-4 — Default link rendering is too faint for sparse/flat bipartite samples — ✅ IMPLEMENTED

- **Severity:** Low-medium — a legibility issue that compounds BUG-1/BUG-2, not a data problem by itself.
- **Live evidence:** zoomed crop (`assets/50_graph_quality/before/step-misconceptions-zoom.png`) of the "scattered dust" view proves individual edges **are** drawn (thin diagonal lines connecting adjacent dot-pairs) — they are simply too faint/thin (`#cbd5e1` at `0.5px`) to read at normal zoom against the app's light background, especially once a 1:1 bipartite match (BUG-2) has no hub structure to concentrate attention on.
- **Root cause:** [app/graph/[rel]/page.jsx](</Volumes/External/Developer/knowledge-bank-ingestion/mathbank-web/app/graph/[rel]/page.jsx>) `linkColor`/`linkWidth` callbacks: unselected default is `"#cbd5e1"` / `0.5`px; also `nodeVal` is constant (`1` for all unselected nodes) regardless of a node's real degree, so true hub nodes (e.g. the `Algebra` concept with 4,708 `TESTS` edges) render at the exact same dot size as a leaf node with one edge — no visual cue to real importance/connectivity.
- **Proposed fix:** darken/thicken the default link style slightly (e.g. `#94a3b8` at `0.8`px) and size `nodeVal` by (capped, log-scaled) degree within the current sample so hub nodes are visually distinguishable — this is a pure rendering tweak, no data/query change.

### BUG-5 — `route_projection.project()`'s node-level DETACH DELETE silently destroys any companion projection's edges, including BUG-2's own fix — ✅ IMPLEMENTED (discovered and fixed in the same session as ENR-1/ENR-4)

- **Severity:** Critical — not because it is hard to fix, but because it is invisible: no error, no log line, no test failure. A routine, fully-successful, uninterrupted re-run of `project()` (launched for an unrelated reason — propagating ENR-8's taxonomy-label changes) silently deleted BUG-2's own fix.
- **Live evidence (the regression, caught by the user, not by any automated check):**
  ```cypher
  MATCH (:Misconception)-[r:RELATES_TO]->() RETURN count(r)
  // -> 0   (was 82,019 immediately after BUG-2's original fix shipped)
  ```
- **Root cause, confirmed by reading `route_projection.py`'s rebuild cycle:**
  ```python
  session.run("MATCH ()-[r]->() WHERE r.projection_kind=$kind DELETE r", kind=KIND)   # scoped correctly
  session.run("MATCH (n) WHERE n.projection_kind=$kind DETACH DELETE n", kind=KIND)   # NOT relationship-scoped!
  ```
  `DETACH DELETE` on a node removes **every** relationship touching it, regardless of that relationship's own `projection_kind`. Every `Misconception` node carries `projection_kind='tutoring_routes'` (it is one of the labels this projector manages), so the second line destroyed the companion script's `RELATES_TO` edges (tagged `projection_kind='misconception_relations'`) even though the first line's filter would never have matched them directly. Full incident write-up: [GOTCHAS.md §24](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/GOTCHAS.md).
- **Fix:** stop running a separate companion script against any node label `route_projection.py` manages. `RELATES_TO` (and, while rebuilding this, the previously-incomplete `EXPLAINS`/`PRACTICES` taxonomy coverage — see ENR-4 in doc 51) are now generated directly inside `metadata()`/`_project()`, so they are recreated by the same rebuild that could otherwise destroy them. `mathbank-graph/etl/project_misconception_relations.py` is retired (kept for historical reference only, `DEPRECATED` docstring added, must not be run again).
- **Verification:** full `project()` re-run completed (`pipeline.graph_projection` status `COMPLETED`, 415,682 nodes / 1,241,707 edges); live Neo4j query confirms `RELATES_TO` back at 78,781 edges (40,320 + 27,156 + 11,305 across the three target labels) and will survive every future rebuild by construction, not by convention.

## 5. Data-population gaps (not code bugs — confirmed to originate in Postgres) — ✅ DGAP-1/DGAP-2 IMPLEMENTED (via doc 51 ENR-3)

| Gap | Evidence | Where it actually lives |
|---|---|---|
| **DGAP-1** — `practices-skill` (`Problem -[:PRACTICES]-> Skill`) is almost empty | ✅ **FIXED, live-verified**: was 2 total edges; `knowledge.problem_skill` classified via [scripts/classify_problem_skill_practices_tests.py](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-rest/scripts/classify_problem_skill_practices_tests.py) (doc 51 ENR-3, rule: `role='primary' AND required_level=3` → `PRACTICES`), re-projected into Neo4j — now **12,043** edges. | `knowledge.problem_skill` — fixed via a corpus-enrichment pass reusing the existing, already-authored `role`/`required_level` columns (no new unverified claims fabricated; see ENR-3 in doc 51 for the full rule and the `approval_method='automatic'` caveat). |
| **DGAP-2** — `tests-skill` (`Problem -[:TESTS]-> Skill`) is almost empty | ✅ **FIXED, live-verified**: was 1 edge; same script, rule `role='primary' AND required_level>=4` → `TESTS` — now **7,799** edges. | Same as above. |

Recommendation: surface these honestly in the UI (e.g. a `Pill tone="warning"` "Sparse: 2 of ~12,542 problems" callout when `coverage` reflects a near-zero total, not just a sampling percentage) rather than silently rendering an apparently-broken empty canvas — this is a one-line conditional in the same page component, bundled into the BUG-1/BUG-4 pass. **Superseded by the DGAP-1/2 fix above** — both tabs now have real density, so the sparse-data banner (NGQ-4) no longer triggers for them; the banner logic itself remains in place for genuinely sparse tabs.

## 6. Modeling smell (documented, not blocking) — ⏳ NOT FIXED (documented only)

The same Cypher relationship **type** is reused for semantically different edge shapes:
- `PRACTICES`: `Problem -> Skill` (12,043 edges, was 2 pre-DGAP-1-fix) **and** `LearningItem -> Technique` (11,993 edges, the real "practice targets" view).
- `TESTS`: `Problem -> Concept` (53,796 edges, the real "tests" view) **and** `Problem -> Skill` (7,799 edges, was 1 pre-DGAP-2-fix).

This is legal in Neo4j (relationship types aren't bound to a label pair) but makes any graph-wide query by relationship type alone ambiguous — now with both sides of each overloaded type carrying real, non-trivial edge counts rather than one side being near-empty, the ambiguity is more consequential, not less. Not fixed in this pass; flagged for the eventual schema-naming cleanup (e.g. `PRACTICES_SKILL` vs `PRACTICES_TECHNIQUE`).

## 7. Per-view findings (all 37 tabs — 32 original + 3 misconception-taxonomy tabs restored/re-verified + 4 new theory-/item-→Concept/Skill tabs — live-captured)

Legend: 🟢 well-formed (real multi-way structure, visually legible) · 🟡 structurally flat/1:1 (will stay sparse-looking even after BUG-1's sampling fix, because the underlying data really is one-to-one) · 🔴 broken or near-empty · screenshots under `assets/50_graph_quality/before/<slug>.png` and `assets/51_misconception_canonicalization/after/<slug>.png`.

| Tab | Relationship | Total | Sample coverage | Verdict |
|---|---|---:|---:|---|
| Overview | — | 1,288,967 rels (pre-ENR-1/4; now ~1.24M, see doc 51 §9) | — | 🟢 informative, accurate |
| Competition → Paper | `HAS_PAPER` | 1,391 | 71.9% | 🟢 |
| Paper → Problem | `HAS_PROBLEM` | 12,542 | 8% | 🟡 BUG-1 (large, under-sampled) |
| Problem → Solution | `HAS_SOLUTION` | 18,749 | 5.3% | 🟡 BUG-1 |
| Problem → Concept (tests) | `TESTS` | 53,796 | 1.9% (**1 of 619 concepts in sample**) | 🔴 BUG-1 (worst concentration measured) |
| Problem → Technique | `USES_TECHNIQUE` | 26,489 | 3.8% | 🟡 BUG-1 |
| Concept → Concept | `CONCEPT_RELATION` | 798 | 100% | 🟢 |
| Required skills | `REQUIRES` (Problem→Skill) | 38,105 | 2.6% | 🟡 BUG-1 |
| Practiced skills | `PRACTICES` (Problem→Skill) | **12,043** (was 2) | ~improved | ✅ DGAP-1 FIXED |
| Tested skills | `TESTS` (Problem→Skill) | **7,799** (was 1) | ~improved | ✅ DGAP-2 FIXED |
| Skill → Concept | `PART_OF` | 9,265 | 10.8% | 🟡 BUG-1 |
| Skill prerequisites | `PREREQUISITE_OF` | 3,380 | 29.6% | 🟢 |
| Skill hierarchy | `PART_OF` (Skill→Skill) | 2,052 | 48.7% | 🟢 real clustering visible |
| Concept hierarchy | `PART_OF` (Concept→Concept) | 309 | 100% | 🟢 |
| Concept prerequisites | `PREREQUISITE_OF` | 484 | 100% | 🟢 |
| Useful prior skills | `BUILDS_ON` | 3,387 | 29.5% | 🟢 |
| Published solution routes | `HAS_ROUTE` | 18,589 | 5.4% | 🟡 BUG-1 |
| Route checkpoints | `HAS_STEP` | 80,168 | 1.2% | 🟡 BUG-1 |
| Step prerequisites · techniques | `REQUIRES` (RouteStep→Technique) | 11,993 | 8.3% | 🟡 BUG-1 |
| Step prerequisites · skills | `REQUIRES` (RouteStep→Skill) | 27,983 | 3.6% | 🟡 BUG-1 |
| Step prerequisites · concepts | `REQUIRES` (RouteStep→Concept) | 42,043 | 2.4% | 🟡 BUG-1 |
| Step outputs | `PRODUCES` | 80,168 | 1.2% | 🟡 inherently 1:1 by design (one checkpoint, one output claim) — not a dedup candidate |
| Earlier claims used | `USES_CLAIM` | 128,468 | 0.8% | 🟡 BUG-1; fan-out/fan-in ≈2.1, real (not flat) structure |
| Checkpoint dependencies | `DEPENDS_ON` | 128,468 | 0.8% | 🟡 BUG-1; fan-out/fan-in ≈2.1. Open question (not a bug, not yet explained): this count coincidentally equals `USES_CLAIM`'s above despite the two source arrays (`depends_on` 129,302 raw refs, `uses_claims` 128,667 raw refs) having different raw totals in Postgres — flagged for future investigation, out of scope here. |
| **Possible misconceptions** | `CAN_TRIGGER` | 80,168 | 1.2% | 🟡 **IMPROVED, not solved**: Misconception side canonicalized (80,168→69,954 distinct nodes, ENR-1 Phase A), giving real but modest fan-in (**1.15**) — up from perfectly flat 1.0. Exact-text dedup only caught 12.7% of instances; most remain genuinely distinct text. Full fix needs ENR-1 Phase B (semantic near-duplicate clustering, needs ENR-2 embeddings — not yet built, see doc 51 §9). |
| Checkpoint probes | `CHECKED_BY` | 80,168 | 1.2% | 🟡 inherently 1:1 by design — no canonical-LearningItem catalog exists (diagnostic question text is genuinely bespoke per checkpoint, analogous to the 0.8% TheoryItem-recap duplicate rate already measured in doc 51 §4) — considered and deliberately not pursued this pass |
| Checkpoint recaps | `EXPLAINED_BY` | 80,168 | 1.2% | 🟡 same as above |
| **Misconception recaps** | `REMEDIATED_BY` | 80,168 | 1.2% | 🟡 **IMPROVED**: same canonicalization as `CAN_TRIGGER` above — distinct Misconceptions now 69,954 (was 80,168), modest real fan-out per canonical misconception |
| **Misconception probes** | `DIAGNOSED_BY` | 80,168 | 1.2% | 🟡 **IMPROVED**, same as above |
| Theory explains technique | `EXPLAINS` (TheoryItem→Technique) | 11,993 | 8.3% | 🟢 fan-in 9.77, real hub clusters |
| **Theory explains concept** *(new tab)* | `EXPLAINS` (TheoryItem→Concept) | **42,043** | — | 🟢 **NEW** — ENR-4 fix: previously 100% dropped (CONCEPT-type targets were never wired for THEORY assets at all); fan-in 19.18 |
| **Theory explains skill** *(new tab)* | `EXPLAINS` (TheoryItem→Skill) | **27,983** | — | 🟢 **NEW** — same fix; fan-in 8.41 |
| Practice targets | `PRACTICES` (LearningItem→Technique) | 11,993 | 8.3% | 🟢 fan-in 9.77, real hub clusters |
| **Practice targets (concepts)** *(new tab)* | `PRACTICES` (LearningItem→Concept) | **42,043** | — | 🟢 **NEW** — same ENR-4 fix as Theory; fan-in 19.18 |
| **Practice targets (skills)** *(new tab)* | `PRACTICES` (LearningItem→Skill) | **27,983** | — | 🟢 **NEW** — same fix; fan-in 8.41 |
| **Diagnostic targets** | `TESTS_MISCONCEPTION` | 80,168 | 1.2% | 🟡 **IMPROVED**: same Misconception canonicalization, distinct Misconceptions 69,954 (was 80,168), fan-in 1.15 |
| Misconception → Concept | `RELATES_TO` | **40,320** (was 82,019 derived, then **0** after BUG-5, now re-fixed) | — | 🟢 **RESTORED+IMPROVED** — now sourced directly from `knowledge.misconception_taxonomy_link` (ENR-4), immune to BUG-5's recurrence; fan-in 18.39 |
| Misconception → Skill | `RELATES_TO` | **27,156** (was 0 after BUG-5) | — | 🟢 **RESTORED** — fan-in 8.16 |
| Misconception → Technique | `RELATES_TO` | **11,305** (was 0 after BUG-5) | — | 🟢 **RESTORED** — fan-in 9.21 |
| Solution approaches | `USES_APPROACH` | **0** | — | 🔴 BUG-3 (dead config) |

**Net new/changed this pass:** 3 tabs restored from a total regression (0 → tens of thousands of edges each), 4 brand-new tabs added (previously the underlying data existed in Postgres but was never projected at all), 4 tabs modestly improved (flat 1.0 fan-in → 1.15), 1 tab's *root cause* for its original sparsity fully corrected (BUG-5). No tab got worse. The two tabs considered-and-declined for further dedup (`CHECKED_BY`/`EXPLAINED_BY`) remain flat by genuine design, not oversight — see doc 51 §4 for the measured duplicate-rate evidence behind that call.

## 8. Research report — what would make this graph actually useful for clustering/insight

Answering the user's third ask directly (how to cluster skills/misconceptions and surface better relationships):

1. **Close BUG-2 first.** ✅ Done (and then some — see BUG-5 in §4: the original fix silently regressed once, was caught, and is now re-fixed in a way immune to recurring). Nothing downstream (clustering, similarity, "which misconceptions cluster around which skill") is possible while misconceptions have zero taxonomy anchoring. The derived `RELATES_TO` edge in §4 is the prerequisite for everything below, not an alternative to it.
2. **Misconception clustering, once anchored:** with `Misconception -[:RELATES_TO]-> Skill/Concept/Technique` in place, a standard **community-detection pass** (Neo4j GDS `louvain` or `labelPropagation` over the induced `Misconception`–`Skill` bipartite projection) would surface natural misconception clusters per skill/concept — e.g. "which 5 skills account for 80% of triggered misconceptions" — directly answering "find relation between the skills/misconceptions to be more pronounced."
3. **Skill sub-clustering via existing `PART_OF`/`PREREQUISITE_OF` edges:** `skill-hierarchy` and `skill-prerequisites` are already real and well-formed (§7); a `louvain` pass over just those two edge types would produce genuine "subskill family" clusters today, with no schema change — worth running as a first, nearly-free insight deliverable.
4. **Degree-weighted visual hubs (BUG-4's `nodeVal` fix) make existing structure legible** without any new data — e.g. `Algebra` at 4,708 `TESTS` edges should visually dominate its neighborhood; today it's drawn identically to a leaf concept.
5. **Representative sampling (BUG-1 fix) is a precondition for any screenshot-based or dashboard-based "insight" to be trustworthy at all** — until it's fixed, nobody (user or algorithm) can tell real sparsity (DGAP-1/2) apart from a sampling artifact (BUG-1) just by looking at a tab.
6. **Tag/pill opportunity:** once `RELATES_TO` exists, the existing node-detail side panel (`app/graph/[rel]/page.jsx`, the `<aside>` block) could show "Related skills/concepts" as `Pill`s directly on a `Misconception` node click — turning the abstract graph into an actual navigable "which skills does this misconception touch" UI, which is the most direct realization of "subskill under still maybe" tagging the user asked about.
7. ~~**Not recommended in this pass:** re-authoring `knowledge.problem_skill`'s `PRACTICES`/`TESTS` rows (DGAP-1/2) algorithmically from `REQUIRES` — that would fabricate pedagogically unverified claims (a problem "requiring" a skill does not imply it specifically "practices" or "tests" that skill versus others it also requires); this should stay a tracked, explicitly-authored content gap, not a graph-layer workaround.~~ **Superseded by explicit user direction to eliminate graph sparsity.** Implemented in doc 51's ENR-3, but in a way that mitigates the exact risk flagged here: rather than inventing a new heuristic from `REQUIRES` alone, it reuses `role`/`required_level` — columns that are *already authored*, not derived — so no new unverified claim is fabricated, only an existing signal is surfaced into the already-defined `relation_type` enum. Every inserted row is additionally marked `approval_method='automatic'` (this schema's standing convention for "not human-verified," confirmed live), so the provenance distinction this point was protecting is preserved, not lost.

## 9. Requirement inventory (NGQ-*) — final evidence

| ID | Requirement | Status | Acceptance evidence |
|---|---|---|---|
| NGQ-1 | Graph-view sampling is representative, not degenerate | ✅ IMPLEMENTED | **Verified live**: `tests` (Problem→Concept) legend now shows 215 distinct concepts in a 1,000-edge sample (was 1). Fix: `ORDER BY rand()` before `LIMIT` in `app/api/graph/relationship/[rel]/route.js`, cache key bumped to `v3`. |
| NGQ-2 | Misconceptions carry a real taxonomy anchor | ✅ IMPLEMENTED (re-fixed after a regression — see BUG-5) | **Verified live**: `MATCH (m:Misconception)-[:RELATES_TO]->(t) WHERE t:Concept OR t:Skill OR t:Technique RETURN count(*)` → **78,781** edges (40,320 Concept + 27,156 Skill + 11,305 Technique), now sourced directly from the canonical `knowledge.misconception_taxonomy_link` table inside `route_projection.py` itself (requirements/51 ENR-4) rather than a separate companion script, specifically so it cannot be silently wiped again by a future `route_projection.project()` rebuild (BUG-5). New tabs "Misconception → Concept/Skill/Technique" render real clustered structure (e.g. fan-in 18.39 for Concept). |
| NGQ-8 *(added during the BUG-5 fix)* | TheoryItem/LearningItem assets' own Concept/Skill taxonomy targets are projected, not just Technique | ✅ IMPLEMENTED | **Verified live**: previously only `TECHNIQUE`-type targets were ever wired for `THEORY`/`LEARNING_ITEM` assets (confirmed: 88% of their taxonomy references — CONCEPT/SKILL/SUBCONCEPT — were silently dropped). Four new tabs now expose the previously-dropped signal: `theory-concepts` (42,043 edges), `theory-skills` (27,983), `item-concepts` (42,043), `item-skills` (27,983) — all real, dense, fan-in ≥8. |
| NGQ-3 | No dead relationship-view tab | ✅ IMPLEMENTED | **Verified live**: `/graph/solution-approaches` now correctly 404s ("unknown relationship view") instead of silently rendering an empty canvas forever — the dead `USES_APPROACH` config entry was removed from `lib/graphConfig.js`. |
| NGQ-4 | Sparse views are honestly labeled | ✅ IMPLEMENTED | **Verified live**: `/graph/practices-skill` now shows "Sparsely populated: only 2 PRACTICES relationships exist in the corpus — this is a real content gap, not a sampling or rendering issue." |
| NGQ-5 | Hub nodes are visually distinguishable | ✅ IMPLEMENTED | **Verified live**: `nodeVal` now scales with sqrt(in-sample degree); default `linkColor`/`linkWidth` darkened/thickened (`#94a3b8`/`0.8px`). Screenshots show visible hub clustering (e.g. `theory-techniques` now shows one dense, clearly-larger hub cluster among many smaller nodes). |
| NGQ-6 | Before/after evidence is preserved | ✅ IMPLEMENTED | `assets/50_graph_quality/before/*.png` (32 original tabs) and `assets/50_graph_quality/after/*.png` (35 tabs, including the 3 Misconception→taxonomy tabs) captured for the original BUG-1..4 pass; `assets/51_misconception_canonicalization/after/*.png` captures the BUG-5 fix + 4 new theory-/item-→Concept/Skill tabs. |
| NGQ-9 *(added after the BUG-5 regression was found)* | A companion graph projection cannot be silently destroyed by the main projector's rebuild | ✅ IMPLEMENTED | See BUG-5 in §4 and [GOTCHAS.md §24](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/GOTCHAS.md): root-caused to `_project()`'s node-level `DETACH DELETE` stripping relationships regardless of their own `projection_kind`; fixed by folding the `RELATES_TO`/broadened-`EXPLAINS`/`PRACTICES` projection directly into `route_projection.py`, not a separate script. |
| NGQ-7 *(added during implementation)* | Graph nodes display real content, not generic positional keys | ✅ IMPLEMENTED | **Verified live**: `Misconception`/`Claim`/`TheoryItem`/diagnostic-`LearningItem` nodes now carry `title`/`description`/`symptom`/`why_wrong`/`correct_model`/`question`/`expected_answer` (backfilled from `pedagogy.route_asset.content`, which already held this text). `labelOf()` in `graphConfig.js` now shows real text (e.g. "Students may confuse inscribed angles with central angles...") instead of `MIS_STEP_4`. See [requirements/51 ENR-7](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/requirements/51_POSTGRES_METADATA_ENRICHMENT_FOR_GRAPH_CLUSTERING.md) for the full root cause and [reference/GRAPH_NODE_ENRICHMENT_MIGRATION.md](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/requirements/reference/GRAPH_NODE_ENRICHMENT_MIGRATION.md) for the migration detail. |

## 10. Implementation record

All five bugs were fixed, live-verified against the real AuraDB instance, and documented:

1. **BUG-1** — `app/api/graph/relationship/[rel]/route.js`: added `ORDER BY rand()` before `LIMIT`; cache key bumped to `v3` to invalidate stale non-randomized samples.
2. **BUG-3** — `lib/graphConfig.js`: removed the dead `solution-approaches` entry (pointed at a `USES_APPROACH` relationship type that never existed) rather than repointing it at a duplicate of an existing view.
3. **BUG-4** — `app/graph/[rel]/page.jsx`: `nodeVal` now scales with sqrt(degree) (capped), default `linkColor`/`linkWidth` darkened/thickened; added a sparse-data warning banner (NGQ-4) for near-empty totals (`total < 10`).
4. **BUG-2 (original fix, later regressed — see item 6)** — a companion script [mathbank-graph/etl/project_misconception_relations.py](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-graph/etl/project_misconception_relations.py) derived `(Misconception)-[:RELATES_TO]->(Concept|Skill|Technique)` from each misconception's own `RouteStep`'s existing `REQUIRES` edges; confirmed idempotent (zero diff on re-run) *at the time*. Three new `graphConfig.js` tabs (`misconception-concepts`/`-skills`/`-techniques`) expose it. This script is now **deprecated** (see item 6) but its tabs remain, now powered by a different, regression-proof source.
5. **Added during implementation (NGQ-7, requirements/51 ENR-7)**: discovered live that `Misconception`/`Claim`/`TheoryItem`/diagnostic-`LearningItem` nodes carried *only* a generic positional `asset_key` (e.g. `MIS_STEP_4`), never the real `title`/`description` text that already existed in `pedagogy.route_asset.content`. Fixed in `route_projection.py` (`_display_properties()`, now part of the canonical projector) plus a one-off safe backfill script [mathbank-graph/etl/enrich_route_asset_properties.py](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-graph/etl/enrich_route_asset_properties.py) for the existing 321K rows; `labelOf()` updated to prefer real content over boilerplate titles for `Claim`/`Misconception` specifically (confirmed live: their `title` is a hardcoded "Step N result/common error" template — real content is in `description`).
6. **BUG-5 (found in a later session, requirements/51 ENR-1/ENR-4)** — item 4's companion script turned out not to be regression-proof: `route_projection.py`'s node-level `DETACH DELETE` destroys any relationship touching a node it manages, regardless of that relationship's own `projection_kind`, silently zeroing item 4's edges on a later, fully-successful, uninterrupted `project()` re-run (full root cause: [GOTCHAS.md §24](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/GOTCHAS.md)). Fixed by moving the projection logic directly into `route_projection.py`'s `metadata()`/`_project()`, sourced from the canonical `knowledge.misconception_taxonomy_link` table (not the RouteStep-join derivation) — and, in the same pass, also fixed a previously-unnoticed gap where `TheoryItem`/`LearningItem` assets' own `CONCEPT`/`SKILL`/`SUBCONCEPT`-type taxonomy targets were never projected at all (only `TECHNIQUE`-type was), adding four new tabs (`theory-concepts`, `theory-skills`, `item-concepts`, `item-skills`). The retired companion script now carries a `DEPRECATED` docstring and must not be run again.

### Operational incidents during implementation (disclosed, resolved)

**Incident 1** — Re-running the canonical `route_projection.project()` to validate the NGQ-7 fix end-to-end was interrupted partway through (impatience, not a tool failure) — its delete-then-recreate cycle commits per batch, not atomically, so stopping it mid-run left several `tutoring_routes` relationship types (`EXPLAINS`, `CAN_TRIGGER`, `USES_CLAIM`, partial `DEPENDS_ON`) at zero for roughly 40 minutes while node data stayed intact throughout. Recovered by re-running the same `project()` call **to full completion, undisturbed, as a detached background process** — confirmed via live relationship counts matching the original baseline exactly, then re-ran the BUG-2 companion script (`RELATES_TO` depends on `CAN_TRIGGER`/`REQUIRES`, which were briefly zero) to restore it too. Final state confirmed: 483,840 nodes (unchanged) and 1,370,986 relationships (= original 1,288,967 + the 82,019 new `RELATES_TO` edges, exactly accounted for). Documented as [GOTCHAS.md §23](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/GOTCHAS.md).

**Incident 2 (BUG-5 itself)** — in a later session, an *uninterrupted, fully-successful* re-run of the same `project()` call (launched for an unrelated reason — propagating taxonomy-label changes, requirements/51 ENR-8) silently zeroed out incident 1's own recovered `RELATES_TO` edges, from 82,019 back to 0, with no error surfaced anywhere. This is a different and more serious failure mode than incident 1 (which only required patience); it required actually reading `_project()`'s delete logic to find the `DETACH DELETE`/node-vs-relationship `projection_kind` scoping gap. Documented as [GOTCHAS.md §24](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/GOTCHAS.md), fixed by folding the projection into the atomic rebuild itself (see item 6 above) so it is structurally immune, not just operationally lucky, going forward.

## 11. After-state

See `assets/50_graph_quality/after/*.png` (35 tabs, BUG-1..4 pass) and `assets/51_misconception_canonicalization/after/*.png` (BUG-5 fix + the 4 new tabs) for the full visual record. Headline comparisons:

| Tab | Before | After |
|---|---|---|
| `tests` (Problem→Concept) | 1 distinct concept in sample (`before/tests.png`) | 215 distinct concepts, visible branching structure (`after/tests.png`) |
| `step-misconceptions` | Scattered "dust" of isolated pairs, edges nearly invisible (`before/step-misconceptions.png`) | Links now visibly legible (BUG-4); Misconception side now modestly consolidated (80,168→69,954 distinct nodes, fan-in 1.0→1.15, ENR-1 Phase A) — full fix still needs ENR-1 Phase B (requirements/51) |
| `theory-techniques` | Sparse, scattered small star-clusters (`before/theory-techniques.png`) | Dense, clearly-connected hub network with degree-scaled node sizes (`after/theory-techniques.png`) |
| `solution-approaches` | Permanently empty, `0`/`0`/`0` (`before/solution-approaches.png`) | Removed — now correctly 404s instead of silently rendering nothing |
| `practices-skill` | Unexplained near-blank canvas (`before/practices-skill.png`) | Explicit "Sparsely populated" banner at the time; since DGAP-1 (doc 51 ENR-3), now 12,043 real edges, banner no longer triggers (`after/practices-skill.png`) |
| `misconception-concepts`/`-skills`/`-techniques` | Did not exist, then briefly existed (82,019 edges), then silently regressed to **0** (BUG-5) | **Re-fixed, regression-proof**: 40,320 / 27,156 / 11,305 edges respectively, sourced directly from `knowledge.misconception_taxonomy_link` inside `route_projection.py` itself (`after/misconception-skills.png`) |
| *(new)* `theory-concepts`/`theory-skills`/`item-concepts`/`item-skills` | Did not exist — CONCEPT/SKILL-type taxonomy targets were silently dropped for THEORY/LEARNING_ITEM assets (only TECHNIQUE-type was ever wired) | Real, dense structure: 42,043 / 27,983 / 42,043 / 27,983 edges respectively, fan-in 8.4–19.2 (`after/theory-concepts.png`) |
