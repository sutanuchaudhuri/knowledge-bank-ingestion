# Cross-cutting 01 — Identifier and Version Contract

## Canonical IDs

Every durable entity has a canonical UUID. External/native identifiers are stored separately and may be unique within a source namespace.

## Canonical human codes

Human-friendly codes should be deterministic where possible:

`{competition}-{year}-{paper}-{question}`

Example: `AMC10-2025-A-Q17`.

These codes are alternate keys, not foreign-key substitutes.

## Version dimensions

Keep separate versions for:

- schema migration
- corpus record revision
- taxonomy version
- parser/extractor version
- prompt/schema version
- embedding model/version
- graph projection version
- API version

Do not overload one "version" field to mean all of these.

## Content hashes

Hash normalized content used by derivations. A changed problem statement should invalidate or mark stale any dependent embeddings/classifications whose `input_hash` no longer matches.
