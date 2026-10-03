# Graph 07 — Versioning, Reconciliation, and Operations

## Versioning

Every projection run has a version and PostgreSQL watermark. Nodes/edges carry `projection_version` or updated timestamp where operationally useful.

## Reconciliation

After projection compare:

- PostgreSQL accepted concepts vs graph concepts
- accepted problem-concept assertions vs `TESTS` edges
- accepted prerequisites vs graph prerequisite edges
- expected active problems vs graph problem nodes

Store count mismatches and sampled missing IDs.

## Drift detection

Nightly or weekly drift jobs should detect graph-local nodes/edges with no PostgreSQL source identity. Such items are either deleted or converted into PostgreSQL candidate assertions.

## Backup

Because the graph is rebuildable, PostgreSQL backups remain primary. Graph-native backups are still useful for recovery time but not the only recovery mechanism.

## Performance

Bound variable-length traversals. Add graph indexes/constraints on canonical IDs and frequently filtered slugs/status. Precompute named projections for expensive graph algorithms rather than running unconstrained whole-graph algorithms during user requests.
