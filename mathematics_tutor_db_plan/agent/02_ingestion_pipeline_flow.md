# Agent 02 — Ingestion Pipeline Flow

This summarizes, as one end-to-end flow, the data pipeline already built and
run (see [`../00_implementation_progress.md`](../00_implementation_progress.md)
for full per-round detail, row counts, and gotchas — this page is the
30,000-foot view a new contributor or the agent's documentation should read
first).

## Flow diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│ SOURCES (mathbank_data_ingestion/)                                      │
│  • src/mathbank/data/maths_corpus/*.csv   — competition/paper/taxonomy   │
│    index (mirrors the master Google Sheet)                              │
│  • data/crawl/{aime,amc_10,amc_12,chmmc}/*/parsed.json — AoPS wiki text  │
│  • data/crawl_pdf/{chmmc,cmm,mpg_main,mpg_oly,pumac,smt}/PAPER_*/        │
│    problem.pdf, solution.pdf (+ questions/Qnn/ once parsed)              │
└───────────────────────────────┬──────────────────────────────────────┘
                                 │
                 ┌───────────────┴────────────────┐
                 ▼                                 ▼
   mathbank-db/etl/load_corpus.py      mathbank-db/etl/pdf_pipeline.py
   (Round 1/2: CSV + AoPS crawl)        (Round 3/4: per-link download→
                                         parse→ingest tracker, + Round 4's
                                         parse_mpg_pdfs.py for MPG specifically)
                 │                                 │
                 └───────────────┬────────────────┘
                                 ▼
                    PostgreSQL `mathbank` database
                    core.competition / competition_edition / paper
                    core.problem (statement_text, difficulty_band, ...)
                    core.solution / core.problem_image
                    knowledge.concept / technique / problem_concept / ...
                    pipeline.run / pipeline.work_item / pipeline.pdf_source
                                 │
                 ┌───────────────┴────────────────┐
                 ▼                                 ▼
   mathbank-db/etl/embed_corpus.py       mathbank-graph/etl/
   (Round 5: representations → chunks    project_from_postgres.py
    → OpenAI embeddings)                 (MERGE-projects into Neo4j)
                 │                                 │
                 ▼                                 ▼
        search.embedding (pgvector,          Neo4j corpus graph
        HNSW index, text-embedding-3-small)  (Competition/Paper/Problem/
                 │                            Concept/Technique/Solution
                 │                            nodes + edges)
                 ▼
     mathbank-rest (hybrid RRF search)  ◀── used by mathbank-agent's tools
```

## Stage summary

| Stage | Script | Round | What it does |
|---|---|---|---|
| Structural load | `mathbank-db/etl/load_corpus.py` | 1 | Competitions, papers, problems (placeholder text), concepts, techniques, taxonomy mappings from CSV |
| Real-text enrichment | `load_corpus.py::enrich_problems_from_aops_crawl` | 2 | Replaces placeholder text with real AoPS problem/solution text where crawled |
| PDF-sourced ingestion | `load_corpus.py::load_pdf_crawl_problems` | 2 | Creates *new* problems for PDF-only competitions (not yet in the CSV index) |
| PDF pipeline tracker | `mathbank-db/etl/pdf_pipeline.py` | 3 | Per-paper download/parse/ingest status in `pipeline.pdf_source`, resumable |
| MPG-specific parsing | `mathbank-db/etl/parse_mpg_pdfs.py` | 4 | Runs Docling/PyMuPDF extraction (via `mathbank_data_ingestion`'s own library) on already-downloaded MPG PDFs, including images → `core.problem_image` |
| Vector embeddings | `mathbank-db/etl/embed_corpus.py` | 5 | `core.problem`/`core.solution` → `search.representation` → `search.chunk` → `search.embedding` (OpenAI) |
| Graph projection | `mathbank-graph/etl/project_from_postgres.py` | — | Postgres → Neo4j, idempotent MERGE on canonical UUID |

## Current corpus scale (as of Round 5)

- 5,661 problems (4,424 with real statement text; the rest carry a
  placeholder + `source_url` pending a future crawl pass)
- 10,003 solutions, 137 extracted images
- 14,464 embedded chunks (`text-embedding-3-small`, 1536 dims)
- 723 PDF papers tracked end-to-end (download → parse → ingest status)

## Re-running the pipeline

Every stage is idempotent (upserts keyed on natural/content hashes — see
`00_implementation_progress.md` for the exact uniqueness keys per table).
Re-running after new source data appears (e.g. more AoPS crawling, more PDF
downloads via `make pdf-fetch`) only processes what's new/changed:

```bash
cd mathbank-db
make etl              # re-sync CSV + AoPS/PDF crawl text
make pdf-pipeline      # re-reconcile + ingest any newly-parsed PDF papers
make vector-backfill   # embed any new/changed problems or solutions
make vector-index      # no-op if the HNSW index already exists
cd ../mathbank-graph && make project   # re-project into Neo4j
```
