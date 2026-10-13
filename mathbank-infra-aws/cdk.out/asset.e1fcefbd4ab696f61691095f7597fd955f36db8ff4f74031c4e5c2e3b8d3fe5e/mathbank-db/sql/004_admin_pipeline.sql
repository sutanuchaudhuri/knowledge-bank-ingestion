-- Additive: distinguish PDF-parsed (Docling) vs HTML-parsed (generic fetch)
-- papers in the existing pipeline.pdf_source tracker, so the same table/stage
-- model (PENDING -> DOWNLOADED -> PARSED -> INGESTED) works for competitions
-- that publish problems as PDFs (CHMMC/CMM/SMT/PUMaC/MPG_OLY, via Docling in
-- mathbank_data_ingestion/scripts/crawl_pdf_papers.py) as well as ones that
-- publish a single HTML page per paper (generic fetch in etl/pdf_pipeline.py's
-- cmd_fetch_html — no Docling/PDF-specific dependency needed for those).
--
-- Not a CHECK constraint (ADD CONSTRAINT IF NOT EXISTS isn't idempotent in
-- Postgres) — validated at the application layer (admin REST endpoint) instead.
ALTER TABLE pipeline.pdf_source ADD COLUMN IF NOT EXISTS source_kind text NOT NULL DEFAULT 'PDF';

CREATE INDEX IF NOT EXISTS idx_pdf_source_kind ON pipeline.pdf_source(source_kind, download_status);
