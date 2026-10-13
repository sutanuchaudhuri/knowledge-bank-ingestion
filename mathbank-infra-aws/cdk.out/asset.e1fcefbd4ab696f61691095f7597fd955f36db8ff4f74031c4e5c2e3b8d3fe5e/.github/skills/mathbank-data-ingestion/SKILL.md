---
name: mathbank-data-ingestion
description: 'Working in mathbank-data-ingestion: the crawl/classify/export corpus pipeline. Use when editing a script under src/mathbank/crawl, classify, or firestore, or asked about the ingestion pipeline stages.'
argument-hint: 'Optional: pipeline stage (crawl, classify, export, review) to focus on'
---

# mathbank-data-ingestion conventions

Full detail: [mathbank-data-ingestion/README.md](../../../mathbank-data-ingestion/README.md).

## Non-negotiables

- This project never writes to Postgres/Neo4j — it writes local files (`data/`, `logs/`) that
  `mathbank-db`'s ETL scripts read via hardcoded path strings. If you rename this folder again,
  grep `mathbank-db/etl/*.py` and `mathbank-db/tests/*.py` for the literal old name first.
- Prefer the `*-dry` variant of any crawl/classify target (`crawl-dry`, `classify-dry`,
  `export-classifications` has no network/paid-model side effects) before a real run — these
  pipelines are explicitly bounded/non-AI by design where documented.
- `src/mathbank/db/tracking.py` owns crawl/classify/export progress semantics — read it before
  changing what counts as "complete" for any stage; `make progress` surfaces its output.

## Before changing anything

1. `make test` (5 test files), `make lint`, `make typecheck` — `make audit` runs the combined
   check.
2. `make test-cov`'s `--cov=tika_corpus` flag is a known, pre-existing stale reference (doesn't
   match this project's actual package name, `mathbank`) — don't trust its coverage numbers, and
   don't "fix" it as an unrelated drive-by change unless that's the actual task.
3. Check [documentation/requirements/03_INGESTION_PIPELINE_REQUIREMENTS.md](../../../documentation/requirements/03_INGESTION_PIPELINE_REQUIREMENTS.md)
   and [18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md](../../../documentation/requirements/18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md)
   for current pipeline-stage status before assuming a gap is new.
