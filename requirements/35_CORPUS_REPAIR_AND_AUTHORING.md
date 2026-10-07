# 35 - Corpus repair, original practice authoring and developer queries

## Delivered workflow

`/admin/corpus` uses the protected admin shell, Bootstrap theme, responsive
master-detail layout and three pill tabs: Repair questions, New practice and
Review drafts. No model call occurs on page load or ordinary corpus browsing.

| ID | Requirement | Implementation |
|---|---|---|
| CRA-1 | Find competition questions by competition, year, paper, problem number or canonical-code fragment. | Paginated admin inventory, 20 rows in the UI; collapsed canonical question/figure previews. |
| CRA-2 | Distinguish a likely missing required diagram from a question that legitimately has none. | Explicit statement-reference heuristic and student-safe image counts. References to diagram/figure/shown above/below/pictured with no safe figure are flagged. No reference and no figure means requirement unknown, not an established defect. |
| CRA-3 | Correct canonical question text without publishing immediately. | Markdown preview, source note, immutable original text in the draft and source-hash concurrency checks at save and approval. Text repairs retain the same mathematical problem; substantial changes should be authored as new practice. |
| CRA-4 | Upload permitted original-source images, keeping solutions separate. | Explicit rights confirmation, PNG/JPEG only, 5 MB input / 16-megapixel limit, header/signature/decode validation, native-resolution normalized PNG in the existing private object store. Source hash is checked at upload and approval. Problem/solution classification is reviewed before publication. |
| CRA-5 | Explicit human approval/rejection and retained provenance. | Durable migration-025 drafts; mandatory review note, row locks and expected content revision; repeated identical decisions are idempotent. Reviewed records cannot be changed/deleted. Shared admin-key auth is not individual reviewer identity. |
| CRA-6 | Author new practice manually or use explicit paid AI generation. | Separate original-practice form; AI checkbox authorizes a single bounded configured-provider call. AI drafts can be edited, retaining immutable AI origin and initial generation provenance. Nothing is automatically approved. |
| CRA-7 | Never represent synthetic work as an official competition question. | Approved drafts receive a fresh `GENERATED_<draft UUID>_Q01` identity in `MATHBANK_GENERATED`, on a dedicated nonofficial paper. Solutions remain `UNVERIFIED`; approval does not certify mathematics or non-paraphrase. |
| CRA-8 | Preserve student spoiler boundaries. | Draft image bytes require admin authorization. Approved source figures use the normal question-image route; `ADMIN_SOLUTION_DIAGRAM` is excluded from student figure queries and serving. Solution-image publication does not automatically add it to solution Markdown. |
| CRA-9 | Make stale projections and import protection explicit. | Reviewed text clears stale `statement_latex`, marks statement search representations STALE, updates hashes/timestamps and protects reviewed text against ingestion overwrite. Source image upserts do not overwrite admin images. Graph/vector publication is not run automatically. |
| CRA-10 | Hundreds of explained developer SQL queries with an index. | [210 read-only templates](../mathbank_data_ingestion/queries/README.md), grouped by corpus, diagrams, solutions, taxonomy, pedagogy, imports, pipeline, vectors, storage and privacy-conscious learner aggregates. |

## Persistence and activation

[Migration 025](../mathbank-db/sql/025_corpus_authoring.sql) owns
`ingest.corpus_draft` and canonical-text protection. Private image objects are
immutable and are never exposed by storage key. An image approval inserts only
metadata into `core.problem_image`; the public UUID route reads its object
through the existing private store.

`make -C mathbank-rest migrate-corpus-authoring` explicitly applies **only 025**
transactionally to REST's configured database. It is not a general migration
runner and never starts services, ingests sources or invokes models.

Separate implementation verification on 2026-10-07 UTC: the user selected
REST's configured database, migration 025 was applied, and the exact REST
process was gracefully reloaded. Swagger returned 200; anonymous corpus
reads returned 401; authenticated inventory, canonical detail/hash and draft
listing returned 200. No drafts or corpus edits were published during these
activation checks.

## Verification and remaining boundaries

- 41 focused REST tests covering corpus review, native-resolution uploads, image visibility and source
  provenance passed; targeted authoring lint passed.
- Three desktop/mobile browser tests cover filtering, text repair,
  solution-image classification, paid consent, review gating and editable AI
  drafts. These use fixtures: they do not call paid models or publish data.
- Production web build and three proxy authorization/allowlist unit tests passed.
- Query-library tests verify all 210 distinct templates; PostgreSQL
  PREPARE/DEALLOCATE validated parsing/binding without executing diagnostics.
  This is not evidence of result semantics, runtime cost or universal privileges.
- This workflow does not recover blocked AoPS pages, certify generated
  mathematical correctness, perform non-paraphrase validation, regenerate
  embeddings, publish Neo4j, or migrate temporary student-workspace progress.
- Question-image classification remains a manual responsibility. The heuristic
  cannot detect every missing visual or verify a source image's mathematical
  alignment. Storage is outside the SQL transaction: failed SQL can leave an
  unreferenced immutable object, never a student-visible draft.

See the [DDL](reference/POSTGRES_SCHEMA.md#corpus-authoring-migration-025),
[DML](reference/POSTGRES_DML.md#reviewed-corpus-authoring),
[HTTP contracts](reference/REST_API.md#admin-corpus-authoring) and
[graph boundary](reference/GRAPH_SCHEMA.md#corpus-authoring-boundary).
