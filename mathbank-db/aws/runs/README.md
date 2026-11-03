# Executed migration runs (env `dev`, account 848941468793, us-east-2)

The manifests and verification reports below contain only counts, item types, mapping names and
SHA-256 hashes. They hold no row data. Source: Neon `neondb`, opened read-only. Run logs stay in the
git-ignored `logs/aws/`.

| Run | What | Result |
|---|---|---|
| [20261103T035331Z](20261103T035331Z/dynamo-manifest.json) | Full DynamoDB + S3 migration, all 192 mappings | 394,747 items written, 37,616 S3 objects (811 MB), 57 attributes offloaded. 0 key collisions; all 172 row-count-checked mappings matched. |
| [20261103T043925Z](20261103T043925Z/dynamo-manifest.json) | Re-run of `learner exam live media staff` after adding the "skip already-expired TTL items" rule | 3,029 items rewritten; 173 expired `learner/IDEM` idempotency records skipped and deleted |
| [20261103T043925Z verify](20261103T043925Z/dynamo-verify.json) | Full consistent scan of all 12 tables against both manifests (newest manifest per table) | **PASSED**: count and SHA-256 equal for every (table, item type); 57/57 offloaded S3 objects present with matching size and SHA-256 |
| [20261103T052858Z](20261103T052858Z/vectors-manifest.json) | S3 Vectors copy of 11 indexes + Parquet archives | 59,511 vectors; each index count equals its source |
| 20261103T042926Z (log only) | S3 Vectors copy of `misconception-te3small-1536-v1` + Parquet archive (`vectors-archive/20261103T042926Z/…`, 209.8 MB) | 70,018 vectors written. The run's manifest was not written because Neon dropped the long-held source connection afterwards; fixed by opening one connection per index. |
| [20261103T064509Z](20261103T064509Z/vectors-verify.json) | Vector verification of all 12 indexes against their Parquet archives (each row's SHA-256 recomputed) plus a live Neon `count(*)` | **PASSED**: 129,529 vectors; S3 Vectors = archive = live source per index; 300-vector samples bit-exact with equal metadata; tie-aware recall@8 0.967–0.9996 (gate 0.95): misconception 0.9929, taxonomy-node 0.9671 (within `node_type`), taxonomy-search 0.9996, problem 0.9879, solution 0.9879, step 0.9738, learning-item 0.9796. The 5 empty families are empty on both sides. |

**Notes**
- The first verification of run 035331Z failed on exactly one type: the 173 `IDEM` idempotency records had
  `ttl` = created + 7 days, already in the past, and DynamoDB TTL deleted them minutes after the write.
  Expired idempotency records are absent by design. The engine now skips (and deletes) items whose
  `ttl` has passed, and run 043925Z re-ran the affected contexts.
- Item totals per table (after run 043925Z): content 391,545 · exam 1,055 · learner 1,079 · agent-sessions 445 ·
  live 344 · socratic 93 · geometry 9 · audit 4. media, artifacts, jobs and notify are empty: their source tables
  hold no rows (or only expired Studio jobs), and `notification.event` was never created in Neon.
- Recall is tie-aware: a returned neighbour counts when it is at least as similar as the exact 8th neighbour.
  30% of learning-item vectors are exact duplicates (variants sharing text), so plain key-set recall (0.90) counted
  equally good neighbours as misses.
- Content bucket: 37,190 release snapshots, 6 catalogue snapshots and 359 images. 363 image uploads became 359
  keys because images are content-addressed and 4 are byte-identical.
