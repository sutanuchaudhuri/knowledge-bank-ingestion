# Ingestion Pipeline Requirements

## Overview

The ingestion pipeline reads structured data from the master spreadsheet, normalises it to canonical entities, produces markdown artifacts, and writes back to the Google Cloud storage and Sheets layers.

## Source Spreadsheet

Path: `/Volumes/External/Developer/knowledge-bank-ingestion/Tika Competition Math Prep - AMC10 AMC12 AIME MathPrize HMMT SMT PUMaC CMM CHMMC/Tika Competition Math Master Question Corpus.xlsx`

- Multiple tabs, each representing a competition or supporting reference table.
- The existing archived pipeline already has a Sheets API sync layer and a batch queue pattern.
- This ingestion layer targets the **local Excel file** as the bootstrapping source, then syncs state back to Google Sheets.

## Tab Inventory And Roles

| Tab Pattern | Role | Ingest Priority |
|---|---|---|
| AMC10_*, AMC12_*, AIME_* | Paper and question rows | P0 |
| HMMT_*, SMT_*, PUMaC_* | Paper and question rows | P0 |
| MathPrize_*, CMM_*, CHMMC_* | Paper and question rows | P0 |
| Canonical_Taxonomy | Taxonomy node definitions | P0 (pre-load before questions) |
| Technique_Catalog | Technique definitions | P0 (pre-load before questions) |
| Paper_Registry | Paper-level metadata | P1 |
| Parsing_Batch_Queue | Pipeline batch control | P1 |
| Question_Index | Master question rows | P0 (ingest target) |
| Question_Taxonomy_Map | Concept assignments | P1 |
| Question_Technique_Map | Technique assignments | P1 |
| Question_Visual_Evidence | Visual asset links | P1 |
| Config | Schema version, IDs | P0 (read-only at start) |

## Pipeline Stages

### Stage 0 — Config and Taxonomy Pre-Load (IGR-001)
- Read Config tab to determine spreadsheet_id, Drive root folder IDs, and schema version.
- Load Canonical_Taxonomy and Technique_Catalog into in-memory caches.
- Validate: all IDs unique, required fields non-empty, hierarchy acyclic.
- Fail fast if taxonomy is invalid.

### Stage 1 — Excel Tab Discovery and Row Extraction (IGR-002)
- Use `openpyxl` to open the local `.xlsx` file.
- Discover all tabs. Match each tab to entity type using name-pattern rules.
- For each question tab: read header row, map columns by name, extract all non-empty rows.
- Assign `source_tab` and `source_row` provenance fields.
- Write extracted rows to `data/import/<tab_name>_raw.jsonl`.

### Stage 2 — Validation and Normalisation (IGR-003)
- For each row:
  - Validate required fields: competition_id, year, q_number, primary_topic.
  - Normalise text: strip whitespace, unify quote styles, lowercase category IDs.
  - Resolve concept IDs against taxonomy cache.
  - Flag unresolvable IDs in a validation error report.
- Write `data/import/<tab_name>_validated.jsonl`.
- Write `data/import/<tab_name>_errors.jsonl` for all row-level failures.
- Pipeline continues for valid rows; skips errored rows after logging.

### Stage 3 — Entity Construction (IGR-004)
- Construct Competition, Event (Paper), Question, and Concept-Map entities.
- Assign deterministic IDs where not present, following existing ID conventions.
- Detect duplicates: if a question_id already exists in the target, compare content hash.
  - If content is identical: skip (idempotent).
  - If content differs: flag for review (do not auto-overwrite).

### Stage 4 — Markdown Generation (IGR-005)
- See [04_MARKDOWN_CATALOG_REQUIREMENTS.md](04_MARKDOWN_CATALOG_REQUIREMENTS.md) for format spec.
- For each paper: generate `paper.md` (whole document).
- For each question: generate `question.md` (whole question + solution if available).
- For each question: generate question-level chunks (statement, solution, context).

### Stage 5 — Drive Upload (IGR-006)
- Mirror markdown artifacts to Drive at canonical paths.
- Upload only if content has changed (compare SHA256 before upload).
- Record `drive_file_id` and `drive_url` in local receipt files.

### Stage 6 — Google Sheets Sync (IGR-007)
- Upsert normalised entity rows into target Sheets tabs via existing `SheetsStore.upsert_by_key`.
- Respect the existing column write-list configuration.
- Never overwrite `SKIP_COMPLETE` rows unless `--force-overwrite` flag is set.
- Write `sheets.sync.json` receipt per paper on completion.

### Stage 7 — Chunk and Embed (IGR-008)
- For each markdown document, split into chunks using fixed token window with overlap.
  - Default: 512 tokens, 64-token overlap.
  - Question-boundary-aware splitting: never split across question boundary.
- Generate embedding vector per chunk using configured embedding model.
- Upsert chunk + vector into vector database.
- Record embedding model version and timestamp per chunk.

### Stage 8 — Status Reporting (IGR-009)
- Emit per-batch completion summary: counts of papers, questions, chunks, errors.
- Emit validation error report as `reports/<batch_id>_validation_errors.tsv`.
- Write batch status to Parsing_Batch_Queue tab.

## Batch Execution Model

- IGR-010: All stages run within a named batch (`batch_id`).
- IGR-011: Each stage is independently restartable; completed stages are skipped on rerun.
- IGR-012: Stage receipts stored in `batches/<batch_id>/stage_<N>.json`.
- IGR-013: A `--resume` flag picks up from last completed stage.

## Excel Ingestion Script

Location: `mathbank/scripts/ingest_excel.py`

```
python scripts/ingest_excel.py \
  --xlsx "/path/to/Competition Math Master Question Corpus.xlsx" \
  --batch EXCEL_IMPORT_001 \
  --stage all
```

Optional flags:
- `--stage {discover,validate,build,markdown,upload,sync,embed}` — run a single stage.
- `--tab <tab_name>` — process a single tab.
- `--force-overwrite` — allow rewriting existing synced rows.
- `--dry-run` — validate and build only; no writes to Drive or Sheets.

## Dependencies To Add

- `openpyxl>=3.1` — Excel file reading.
- `tiktoken>=0.7` — token counting for chunking.
- `vertexai>=1.49` or `openai>=1.30` — embedding generation.
- `google-cloud-firestore>=2.16` — if Firestore is chosen for structured query.
