# 31 - Question-specific source diagrams

## Contract

- A student's problem figure must belong to that question. Never show a whole PDF
  page, neighbouring questions, an answer page or a solution page as its diagram.
- Preserve original source geometry and labels; do not have a model invent a
  missing diagram.
- For PDFs, determine complete consecutive question headings and their spatial
  boundaries. Extract vector/raster graphics only inside those boundaries,
  including a figure on a continuation page. Crop tightly around the graphics
  and nearby labels, not around the entire question or page.
- If headings are ambiguous, incomplete or out of spatial order, do not guess
  proportional page assignments. Repeated numbering and horizontally displaced
  headings are refused as potentially mixed-paper or multi-column layouts.
  Log the gap and leave automatic figures absent.
- Store image references and provenance in `core.problem_image`. Files remain on
  the application filesystem; PostgreSQL does not contain the image bytes.
- Student list and binary routes both enforce the same visibility filter:
  no solution/answer sources, no unknown legacy PDF/AoPS provenance,
  no historical `problem_page_*.png`, and no
  textbook `SOLUTION_HIDDEN` diagrams. Admin textbook routes remain separate.
- Render responsive figures in tutor replies, saved transcripts, corpus details
  and learning workspaces. Surface image failures instead of a broken image.
- Tutor tools retrieve existing source figures without fetching an official
  solution. The tutor must disclose a missing diagram rather than saying
  "diagram below" with no figure.
- An opt-in **Source** control above the diagram opens the original full problem
  document in a responsive iframe. It remains available when no diagram was
  safely extracted. Full source documents are explicitly labelled and may
  contain neighbouring questions or answers; they are never diagram fallbacks.
  No PDF iframe is mounted until the student clicks Source.

## Implementation

| Surface | Source |
|---|---|
| Ingestion-owned spatial cropper and receipts; DB compatibility exports | [`question_figures.py`](../mathbank_data_ingestion/src/mathbank/crawl/question_figures.py), [`DB shim`](../mathbank-db/etl/question_figures.py) |
| PDF parsing, crawling, splitting and visual-classification discovery | [`pdf_parser.py`](../mathbank_data_ingestion/src/mathbank/crawl/pdf_parser.py), [`crawl_pdf_papers.py`](../mathbank_data_ingestion/scripts/crawl_pdf_papers.py), [`split_pdf_artifacts.py`](../mathbank_data_ingestion/scripts/split_pdf_artifacts.py), [`classify_pdf_corpus.py`](../mathbank_data_ingestion/scripts/classify_pdf_corpus.py) |
| AoPS section-specific discovery, local/offline reparse and downloads | [`image_downloader.py`](../mathbank_data_ingestion/src/mathbank/crawl/image_downloader.py), [`crawl_unmapped.py`](../mathbank_data_ingestion/scripts/crawl_unmapped.py) |
| Artifact/SQLite repair, dry-run by default | [`repair_diagram_artifacts.py`](../mathbank_data_ingestion/scripts/repair_diagram_artifacts.py), [`Make targets`](../mathbank_data_ingestion/Makefile) |
| Shared PDF import integration | [`pdf_assets.py`](../mathbank-db/etl/pdf_assets.py), [`load_corpus.py`](../mathbank-db/etl/load_corpus.py), [`pdf_pipeline.py`](../mathbank-db/etl/pdf_pipeline.py) |
| Corrective backfill, dry-run by default | [`backfill_question_figures.py`](../mathbank-db/etl/backfill_question_figures.py) |
| Student visibility and metadata | [`problem_images.py`](../mathbank-rest/src/mathbank_rest/db/problem_images.py) |
| Diagram tool | [`rest_tools.py`](../mathbank-agent/agents/mathbank_tutor/tools/rest_tools.py) |
| Responsive rendering and error state | [`ProblemDiagrams.jsx`](../mathbank-web/app/_components/ProblemDiagrams.jsx), [`MathText.jsx`](../mathbank-web/app/_components/MathText.jsx) |
| Original document metadata and cached problem PDF | [`problem_sources.py`](../mathbank-rest/src/mathbank_rest/db/problem_sources.py), [`step_runtime.py`](../mathbank-rest/src/mathbank_rest/routers/step_runtime.py) |
| Opt-in full-document iframe, independent of crop availability | [`ProblemSource.jsx`](../mathbank-web/app/_components/ProblemSource.jsx), [`solveProxy.mjs`](../mathbank-web/lib/solveProxy.mjs) |

### Original-source viewer

- Reads the registered `pipeline.pdf_source.problem_url` for PDF questions,
  falling back to `core.problem.source_url`. Does not require a diagram row.
- Uses the cached original `problem.pdf` when available so publisher frame
  restrictions do not prevent viewing. No solution PDF or client-selected
  filesystem path can be requested through this route.
- Otherwise embeds a known remote PDF URL directly. Non-PDF source pages keep
  an original-page link rather than being falsely presented as a PDF.
- Always includes a new-tab fallback: browser PDF support and remote publishers'
  frame policies can prevent embedding; iframe load events cannot reliably
  detect cross-origin blocking.
- Rejects non-HTTP(S) and credential-bearing URLs. REST metadata never exposes
  local paths; cached-file resolution is restricted to the PDF corpus root.
- Available in tutor replies and saved transcripts (including replies already
  containing diagram Markdown), corpus detail, guided practice and step solving.
- API: `GET /v1/problems/by-code/{code}/source` returns metadata or `null`
  for a known question without a source; unknown questions return 404.
  `GET /v1/problems/by-code/{code}/source-pdf` serves only an existing cached
  original problem PDF inline; missing PDFs return 404.
- Does not fetch arbitrary remote URLs on the server, alter imported data,
  call a paid model, or relax student diagram/solution filters.
- Verification: 13 source/diagram REST tests, 77 web/widget unit tests and all
  39 non-paid browser tests pass. Browser tests cover the real SMT PDF bytes,
  click-to-open/close, no-diagram availability and 390px layout. Registered
  direct PDF links without a `.pdf` filename are also supported.

`PDF_QUESTION_FIGURE` and `PDF_SOLUTION_FIGURE` distinguish PDF source sides;
`AOPS_PROBLEM_DIAGRAM` and `AOPS_SOLUTION_DIAGRAM` do the same for cached AoPS
sections. Existing native question-region assets and textbook package diagrams
are preserved rather than blindly replaced. Solution image references remain private to student diagram routes.
Path-derived version identifiers and revalidation prevent stale whole-page
images being reused after a reference repair.

Manifests are authoritative, including empty inventories. Re-imports remove
stale references only within the matching source family. Source PDF/page renders
remain paper-level audit evidence on disk, never discovery fallbacks.
Mirrored `PAPER_*` records are excluded from the AoPS importer so a later corpus
load cannot relabel PDF figures or solutions as AoPS content.
Crop filenames include both the PDF fingerprint and the algorithm/page/clip/scale
fingerprint; receipts include algorithm version 2. A changed crop cannot silently
reuse old bytes or a stale browser image.

Per-question `diagram_status.json` and parsed-record `diagram_status` distinguish:

| Status | Meaning |
|---|---|
| `EXTRACTED` | Existing source-specific figures are referenced |
| `VERIFIED_NO_GRAPHICS` | PDF boundaries verified; no qualifying graphics found |
| `UNVERIFIED` | PDF exists but its boundaries/inventory cannot be safely verified |
| `SOURCE_MISSING` | Source-side PDF unavailable |
| `NO_SECTION_GRAPHICS` | No diagrams discovered in the selected cached AoPS section |
| `DOWNLOAD_MISSING` | Selected AoPS section references an image absent locally |

## Applied repair and progress

The ingestion-wide artifact/staging repair and Postgres reconciliation are
**applied**, not merely planned. The final idempotent Postgres pass found all
10,171 scoped question inventories unchanged.

| Scope | Applied result |
|---|---|
| PDF papers / question artifacts | 512 / 7,036 |
| AoPS question artifacts | 3,135 |
| Existing SQLite questions refreshed | 9,919 |
| Artifact questions missing from staging | 252; reported, not fabricated or migrated |
| PDF problem / solution figure references in Postgres | 320 / 208 |
| AoPS problem / solution diagram references in Postgres | 43 / 378 |
| Existing textbook image references | 40 preserved |
| Whole `problem_page_*.png` references in Postgres | 0 |
| Whole-page staging `diagram` entries | 0 |
| Problem PDF inventories verified / refused | 353 / 159 |
| Solution PDFs refused | 301 |
| Missing AoPS downloads | 7: one problem figure, six solution figures |

These are scoped source-side reference counts, **not** proof that every question
has a diagram or every source has been extracted. The stronger ambiguity guard
reduced the earlier provisional crop counts; those earlier counts must not be
used as completeness evidence. Text/classification/vector/graph enrichment and
the running enrichment watcher were not rerun or stopped.

Missing AoPS sources are recorded in cached HTML/status metadata:

| Question | Side | Missing source filenames |
|---|---|---|
| `AIME_1983_Q15` | Solution | `500px-Aime1983p15s2.png`, `800px-Dgram.png` |
| `AIME_1984_Q06` | Solution | `1984_AIME-6.png` |
| `AIME_1985_Q04` | Problem | `AIME_1985_Problem_4.png` |
| `AIME_1985_Q04` | Solution | `Aime.png`, `AIME_1985_Problem_4_Solution_3_Diagram.png` |
| `AIME_2012_II_Q15` | Solution | `500px-2012_AIME_II_15a.png` |

A refresh attempt encountered HTTP 403; no downloaded image was substituted.
Default repair remains local-only. `DOWNLOAD_MISSING=1` explicitly enables
source-image download attempts, never paid AI/OCR.

## Verification and limitations

The motivating example is `PAPER_SMT_2010_GEOM_Q06`: its statement ends on
PDF page 1 but the figure is on page 2. The verified crop is approximately
439 x 439 pixels and contains only the circle and labels A, B, M, O, T, D.
There are no headings, neighbouring questions or solution text.

Tests:

- [`test_question_figures.py`](../mathbank-db/tests/test_question_figures.py):
  cross-page figure, tight crop, no neighbouring text, no-graphics question,
  rejected inventory, dry-run and crop provenance, actual SMT labels.
- [`test_diagram_artifacts.py`](../mathbank_data_ingestion/tests/test_diagram_artifacts.py):
  parser/splitter integration, source-side isolation, body preservation, staging
  receipts/statuses, offline reparse and explicit download failures.
- [`test_pdf_assets.py`](../mathbank-db/tests/test_pdf_assets.py):
  manifest-driven imports, native-region preservation, direct solution cropping
  and source-scoped stale-reference removal.
- [`test_problem_images.py`](../mathbank-rest/tests/test_problem_images.py):
  student filters, filesystem-path privacy, safe path resolution.
- [`problem-diagrams.spec.mjs`](../mathbank-web/e2e/problem-diagrams.spec.mjs):
  real Postgres/proxy images in chat, image dimensions and mobile width;
  agent answer/session mocked to avoid paid model calls.

Latest focused validation: 42 ingestion/import tests, 15 REST tests
(two optional live-runtime tests skipped), four agent-tool tests, 76 web/widget
unit tests and two real-image browser tests passed. Runtime checks confirmed
both PDF and AoPS solution-image binary routes return 404; the tutor receives
one 439 x 439 source figure for SMT Q6, with no filesystem path in its metadata.

An initial whole-page backfill was incorrect and was superseded by the
question-specific backfill. Its image-reference counts are **not** evidence of
question-specific diagram coverage. Unverified PDF layouts and missing assets
remain gaps. The cropper is not OCR; image-only PDFs and complex layouts require
separate source-specific extraction or review. Remaining work is to review the
refused PDF layouts with source-specific boundary rules, supply inaccessible
AoPS assets and reconcile the 252 missing staging questions through the normal
inventory/import workflow. Do not relax safety checks or restore proportional
assignment to increase apparent coverage. AoPS section isolation is covered by
its own integration tests, not by PDF crop tests.

No paid AI/OCR calls are required by this correction. Database usage is subject
to the existing hosting plan.
