# Pipeline job console and graph/vector retrieval

## Scope

Extends requirements 03, 05, 11, 12, 14 and 15. A paper batch ending at
`graph_verified` is not an end-to-end success: embeddings and generated
pedagogy have separate workers and independent completion conditions.

## Job console acceptance

- JOB-01: Admin-only, paginated inventory joins registered sources and canonical
  papers, including competitions with HTML/AoPS sources, not only PDF batches.
  Filter by competition and paper; expose total inventory and competition counts.
- JOB-02: Separate download, parse, ingest, classify, vectors, corpus graph,
  pedagogy generation and pedagogy graph publication. Display PENDING, PARTIAL,
  IN_PROGRESS, FAILED, STALLED, COMPLETED, UNKNOWN or NOT_TRACKED as evidence
  warrants. Never infer vectors/pedagogy completion from a paper batch status.
- JOB-03: Show recorded source timestamps, latest job start/end/heartbeat,
  attempt count, errors, stage log references and response observation time.
  Missing historical timestamps remain unknown; observation time is not a
  fabricated completion timestamp. Old heartbeats flag stalled work.
  A verified classifier may finish before its batch imports tag assertions;
  expose both classifier completion and imported classification counts.
- JOB-04: Count canonical problems, solutions, images, classified problems,
  concept/technique links, reviewed skill mappings, pedagogy coverage,
  active representations/chunks and active embeddings. Count solutions as
  separate vector entities. Require all active chunks on every expected entity,
  for the active embedding model; a single vector is not complete coverage.
- JOB-05: Read live Neo4j nodes and classification/pedagogical assertion evidence
  for the displayed page. Verify identity/provenance, not only edge counts.
  Graph outages are explicit UNKNOWN plus a warning, never zero/success.
  Shared taxonomy relationship counts are not additive per-paper totals.
- JOB-06: Overall COMPLETED requires all required layers to be complete.
  Untracked source history prevents a certified end-to-end claim. Human
  rejection is preserved and reported, not overwritten to satisfy coverage.
- JOB-07: Bootstrap full-width admin table, metrics details and eight independent
  stage badges plus separate taxonomy relationship publication; refresh every
  15 seconds without overlapping polls. Preserve
  registration/retry and existing run/projection metrics. Errors remain visible.

## Tutor retrieval acceptance

- RAG-019: Tutor topic/similarity search explicitly requests graph + semantic
  vectors + lexical retrieval. Semantic similarity uses pgvector; graph
  candidates use reviewed concept/technique/skill connections, with bounded
  expansion from semantic seeds. Return per-source ranks and graph evidence.
- RAG-020: Fuse distinct problems using reciprocal rank fusion. Exact competition
  and year eligibility applies before graph ranking, as for vector retrieval.
  Deduplicate multiple chunks from the same problem; hydrate only canonical
  statements/metadata. Never include official answers or solution bodies.
- RAG-021: Graph disconnection produces explicit degraded-retrieval warnings;
  it must not be described as a successful graph search. Empty graph evidence
  is distinct from a graph outage. Vector/model errors remain explicit errors.
- RAG-022: Preserve lexical/semantic opt-outs and recent-first sorting. Validate
  nonempty query, bounded result limits, valid order and at least one source.
  Agent explains source gaps and uses learning-context tools for coaching.

## Gotchas

- Pipeline source inventories and one historical batch snapshot have different
  denominators. Always label scope; pending papers may have no work item yet.
- A full projection republishes existing pedagogy; it does not generate missing
  skill/difficulty metadata. Published job markers alone do not certify current
  graph assertions.
- Status values are evidence summaries, not process-liveness probes.
- Model revision/status and active representation matter for vector coverage.
- No schema migration or destructive graph rebuild is needed for the console.
- Existing runtime workers retain loaded code until their next safe restart;
  historical stage timestamps cannot be reconstructed retroactively.

## Verified implementation

- Authenticated `/v1/admin/pipeline/jobs` and browser proxy respond with all nine
  independently observed layers. The live joined inventory contained 1,566
  papers at validation time (registered sources plus canonical papers).
- A live HMMT paper correctly reported classifier completion while its vectors
  and generated pedagogy remained pending; graph presence alone stayed PARTIAL.
- Filtered live search returned both graph-ranked and vector-ranked AIME results
  with per-source ranks, without answer or solution-body retrieval.
- Focused backend/tool tests, web tests, lint/type checks and production build
  passed. Retrieval quality thresholds require the separate golden evaluation;
  this validation does not claim measured Precision@10.
