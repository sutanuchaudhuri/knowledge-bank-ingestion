# PostgreSQL 02 — Canonical Domain Model

## Core corpus hierarchy

The practical hierarchy is:

`Competition -> Edition -> Paper -> Problem -> ProblemPart`

Examples:

- Competition: AMC 10, AIME, HMMT, Math Prize for Girls
- Edition: competition + year/session
- Paper: A/B, February/November, individual/team, round name
- Problem: numbered item
- ProblemPart: optional subpart such as 4a/4b

Do not encode all hierarchy into a single text identifier. Keep a stable canonical ID plus explicit dimensions.

## Primary entities

### `core.competition`

Fields: `competition_id`, `name`, `organization`, `country`, `level`, `homepage_url`, `active_from`, `active_to`.

### `core.competition_edition`

Fields: `edition_id`, `competition_id`, `year`, `season`, `edition_label`, `start_date`, `end_date`.

### `core.paper`

Fields: `paper_id`, `edition_id`, `paper_code`, `paper_type`, `duration_minutes`, `max_score`, `question_count`, `official`.

### `core.problem`

Fields include:

- `problem_id`
- `paper_id`
- `problem_number`
- `canonical_code` such as `AMC10-2025-A-Q17`
- `statement_text`
- `statement_latex`
- `answer_type`
- `official_answer`
- `difficulty_observed`
- `difficulty_curated`
- `status`

### `core.problem_part`

Supports nested or multipart questions. Store `part_label`, `ordinal`, and separate statement/answer where necessary.

### `core.solution`

A problem can have many solutions. Fields: `solution_id`, `problem_id`, `solution_kind`, `body_markdown`, `body_latex`, `author_type`, `verification_status`, `revision`.

### `core.solution_step`

A structured step sequence makes pedagogical and graph analysis possible. Store `ordinal`, `explanation`, `formula`, `step_type`, and optional references to concepts/techniques.

## Source model

### `core.source_document`

Represents a PDF, webpage, book excerpt, spreadsheet row set, user-authored file, or archive package.

Important fields:

- `source_document_id`
- `source_type`
- `title`
- `uri`
- `storage_key`
- `sha256`
- `mime_type`
- `publisher`
- `publication_date`
- `ingested_at`

### `core.source_locator`

Provides fine-grained provenance: page, bounding box, section, row, worksheet, URL fragment, or text span.

### `core.entity_source`

Generic association between a source locator and a domain entity with `evidence_role`, e.g. statement source, answer source, solution source, taxonomy evidence.

## Mathematics objects beyond problems

### `core.theorem`

Named theorem/lemma/property/identity useful to tutoring.

### `core.example`

Curated instructional examples that are not competition problems.

### `core.formula`

Canonical formula records with variables and conditions, useful for retrieval and graph projection.

## Relationship strategy

Relationships with independent meaning should be tables rather than arrays. Examples:

- problem-to-concept
- problem-to-technique
- concept prerequisites
- theorem-to-concept
- solution-step-to-technique
- problem variants

Each relation should be assertable, reviewable, sourceable, and time-versioned if needed.

## Avoid storing these as opaque JSON only

JSONB is useful for parser payloads and low-stability metadata, but do not bury query-critical attributes such as year, paper code, topic, technique, source ID, review state, or run status in JSON.
