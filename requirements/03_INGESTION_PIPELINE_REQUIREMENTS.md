# Ingestion Pipeline Requirements

## Overview

The ingestion pipeline reads structured data from the master spreadsheet, normalises it to canonical entities, produces markdown artifacts, and writes back to the Google Cloud storage and Sheets layers.

## Official Purple Comet archive extension

- Discover both MS and HS English contests from `https://purplecomet.org/answers`.
  Use embedded official PDF URLs and numbered official answer tables, not fixed
  historical question counts or an archive pointer masquerading as a paper.
- Preserve original PDFs, answer pages/JSON, source manifests, numbered
  statement/solution Markdown and every rendered problem/solution page.
- Assign page images by numbered PDF spans, retaining continuation/shared pages.
  Raster extraction alone cannot preserve vector diagrams. Missing required
  page images or available numbered solutions prevent successful ingestion.
- Send actual PNG page bytes to visual classification (`gpt-4.1`), with the
  named target question, extracted text and official answer. Filenames alone
  are not visual evidence.
- Store answers in `core.problem.official_answer`, explanatory solutions in
  `core.solution`, and page references in `core.problem_image`, distinguishing
  `PDF_PROBLEM_PAGE` from `PDF_SOLUTION_PAGE`. Answer keys must never become
  fabricated worked solutions.
- Classification assertions use the existing automatic-approval policy while
  human corrections and rejections remain protected. The ongoing pedagogical
  watcher subsequently enriches newly ingested questions.
- Use the existing resumable paper batches and exclusive advisory lock.
  Purple Comet queues behind the active SMT/HMMT run. Download/extraction can
  proceed independently; no separate competing graph publisher is introduced.
- Verify exact question/answer/solution/image inventory and classification
  edges between Postgres and Neo4j before marking a batch complete. Retain
  per-stage logs, failures, native-extraction warnings and publication state.
- PDF endpoints may return HTML with HTTP 200. These are
  explicit source failures, not empty successful papers. Missing worked-solution
  endpoints are reported separately; complete archive coverage is not claimed
  while such gaps remain. Preserve source copyright and provenance.
- Accept the whitespace-prefixed signatures in valid legacy PDFs and validate
  both official Purple Comet hosts. The initial twenty rejected problem PDFs
  were not proof of twenty missing documents: the signature check was too strict
  and has been corrected. Do not confuse a parser validation bug with a source gap.
- Force CPU Docling for archive workers, enable formula enrichment, and keep
  model caches and temporary files on the external drive. Markdown headings
  (`## Problem N`) must be recognized before falling back to native extraction.

### Live extraction acceptance snapshot

Both 2026 divisions have been downloaded and registered in live Postgres:
**50 numbered questions, 50 worked solutions, and 118 valid question-level
problem/solution PNG references**. Exact page spans and answers were verified.
The layout extractor was rejected and explicitly retried using native text;
original PDFs and all page images remain available for formula/diagram review.
A paid visual-classification pilot succeeded. This is extraction/classification
evidence, not completed Postgres problem ingestion or Neo4j publication; those
stages wait for the authorized existing paper lock.

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

## Durable ARML Archive Queue (October 2026)

`mathbank-db/etl/arml_queue.py --after-run <Purple PAPER_BATCH UUID>` queues the
four official ARML volumes (2015–2020, 2009–2014, 2004–2008, 1995–2003) in
`pipeline.run` / `pipeline.work_item`. Only the newest validation volume may be
present before Purple completes. No queued ARML downloads, classification, or
embedding calls start until the named Purple run is COMPLETED with zero failures,
its full registered Purple snapshot matches, every paper is classified and graph
verified, and downloaded/parsed/ingested inventories agree. Failed, incomplete,
and successful subset/pilot runs do not release the dependency. A direct database
session owns an ARML singleton advisory lock and cooperates with the existing
paper-batch lock during mutation stages.

`arml_archive.py` inventories all TOC contest families, including Local, Power,
and supplementary puzzle material. Native running headers and source question
anchors locate problem, answer, and worked-solution boundaries; native text is
retained as an auditable sidecar, never represented as successful Docling output.
Power multipart rounds and the explicitly identified puzzle hunt preserve their
shared parent context. Each question retains its original source ID, volume hash,
page ranges, and clip coordinates in `provenance.json`. Unknown layouts or
incomplete problem/solution/answer inventories fail explicitly, rather than
creating one whole-book question.

CPU Docling runs on bounded single-page inputs with formula enrichment and
picture extraction enabled. Off-question PDF text is actually redacted from
bounded inputs: visual clipping alone leaves hidden text accessible to PDF
backends. A `used_fallback=true` result, warnings, or empty/image-only textual
extraction blocks completion. Full rendered PNG pages retain vector diagrams;
precise region PNGs, all raster originals/PNG copies, and detected Docling figures
are retained too. Docling formula transcription remains imperfect; source images
and native sidecars remain available for corrections. All caches and temporary
inputs are under this external-drive project's `data/model_cache` and `logs/arml`.

Postgres import and scoped taxonomy links use migration 008 automatic-approval
triggers, which protect human corrections and rejections. Exact-paper vectors use
`embed_corpus.py backfill --paper <external code>` (repeatable); unscoped behavior
is preserved, and embedding failures now exit unsuccessfully. Completion verifies
active embeddings for every scoped problem and worked solution.

The queue does **not** start a competing teaching worker, paid relationship
generator, or graph publisher. It waits for the existing `enrich_corpus.py --watch
--workers 4 --relationships` lifecycle, requires published teaching and touched
catalog relationship jobs (zero justified edges is valid), then compares scoped
Neo4j assertions, teaching, relationships, and answer/solution/image inventory to
Postgres. The entire archive is COMPLETE only after all four volumes pass.

Activation from the repository root, with existing explicit database/graph
environment files and API configuration inherited:

```sh
mathbank-db/.venv/bin/python mathbank-db/etl/arml_queue.py --after-run <Purple-run-UUID>
```

The parent lifecycle manager may launch that foreground command detached under
the user's authorization. On interruption/failure, restart with `--resume
<ARML_QUEUE_RUN UUID>` from the printed log; completed paid stages are not repeated.
Do not substitute a small validation Purple run UUID.
