# Data Model And Storage Requirements

## Core Entities

### Course
A study track that groups competitions for a student (e.g. "AMC10 Prep", "AIME Intensive").

| Field | Type | Description |
|---|---|---|
| course_id | string (PK) | e.g. COURSE_AMC10_PREP |
| display_name | string | Human-readable name |
| description | string | Optional short description |
| level | enum | middle, high_school, open |
| competition_ids | string[] | Competitions included in this course |
| created_at | datetime | |

### Competition
Represents a named math competition series (AMC10, AMC12, AIME, HMMT, SMT, PUMaC, MathPrize, CMM, CHMMC).

| Field | Type | Description |
|---|---|---|
| competition_id | string (PK) | e.g. AMC10, AIME, HMMT |
| course_ids | string[] | Courses this competition belongs to |
| display_name | string | Human-readable name |
| organizer | string | Sponsoring body |
| competition_type | enum | individual, team, relay |
| level | enum | middle, high_school, open |

### Event (Paper)
One sitting of a competition in a given year and form/round.

| Field | Type | Description |
|---|---|---|
| paper_id | string (PK) | e.g. PAPER_AMC10A_2023 |
| course_id | string (FK) | Primary course this paper is filed under |
| test_id | string (unique) | e.g. AMC10A_2023 |
| competition_id | string (FK) | |
| year | int | |
| form_or_round | string | A, B, I, II, Fall, Spring |
| session | string | Annual, February, November |
| expected_questions | int | Total question count |
| problem_url | string | Canonical source URL |
| solution_url | string | Canonical solution URL |
| problem_sha256 | string | Hash of source artifact |
| solution_sha256 | string | Hash of solution artifact |
| status | enum | raw, extracted, classified, synced |
| source_tab | string | Source spreadsheet tab name |
| source_row | int | Row index within tab |

### Question
One question from one paper.

| Field | Type | Description |
|---|---|---|
| question_id | string (PK) | e.g. AMC10A_2023_Q05 |
| course_id | string (FK) | Inherited from parent paper |
| paper_id | string (FK) | |
| q_number | int | Position within paper |
| primary_topic | string | Top-level math domain |
| subtopic | string | Narrower classification |
| primary_concept_id | string (FK) | Canonical taxonomy ID |
| concept_ids | string[] | All assigned taxonomy IDs |
| technique_ids | string[] | Technique catalog IDs |
| difficulty_band | enum | easy, medium, hard, very_hard |
| correct_answer | string | Official answer |
| confidence | enum | high, medium, low |
| evidence_locator | string | Page/figure reference |
| notes | string | Classifier notes |
| visual_role | string | none, geometry_diagram, graph, table, etc. |
| visual_asset_ids | string[] | Linked image asset IDs |

### Concept (Canonical Taxonomy Node)
Pre-existing taxonomy from the spreadsheet. New categories can be added as rows.

| Field | Type | Description |
|---|---|---|
| canonical_topic_id | string (PK) | e.g. PROB_COND |
| course_ids | string[] | Courses that reference this concept (derived at index time) |
| domain | string | e.g. Probability |
| topic | string | e.g. Conditional Probability |
| subtopic | string | Optional further split |
| node_type | enum | Domain, Topic, Concept, Subtopic, Technique |
| canonical_path | string | Slash-delimited hierarchy |

### Technique
Fine-grained solution technique cross-referenced to concepts.

| Field | Type | Description |
|---|---|---|
| technique_id | string (PK) | |
| course_ids | string[] | Courses that reference this technique (derived at index time) |
| technique_name | string | |
| parent_concept_id | string (FK) | |

### Document (Markdown Artifact)
Stores canonical markdown for each granularity level.

| Field | Type | Description |
|---|---|---|
| doc_id | string (PK) | |
| course_id | string (FK) | Inherited from parent entity |
| entity_type | enum | paper, question, chunk |
| entity_id | string (FK) | paper_id or question_id |
| chunk_index | int | 0 = whole document |
| content_md | text | Markdown content |
| char_count | int | |
| created_at | datetime | |
| content_hash | string | SHA256 of content_md |

### Chunk (Retrieval Unit)
A segment of a document suitable for vector embedding.

| Field | Type | Description |
|---|---|---|
| chunk_id | string (PK) | |
| course_id | string (FK) | Inherited from parent document |
| doc_id | string (FK) | Parent document |
| question_id | string (FK, nullable) | Question chunk belongs to |
| chunk_type | enum | header, statement, solution, context |
| content | text | |
| token_count | int | |
| embedding_model | string | |
| embedding_vector | vector(768) | Stored in vector DB |

## Storage Layers

### DMR-001: Google Sheets (Source of Truth for Corpus Metadata)
- All competition, event, question, taxonomy, and technique rows live in named Sheets tabs.
- Ingestion reads from and writes back to these tabs via Sheets API.
- Schema version is tracked in a dedicated Config tab.

### DMR-002: Google Drive (Artifact Store)
- Raw PDFs stored under `01_source/`.
- Extracted text and page renders under `02_extracted/`.
- Canonical feature markdown under `03_corpus_features/<scope>/<competition>/<year>/<test_id>/features.md`.
- Visual assets under `03_corpus_features/.../<test_id>/visuals/`.

### DMR-003: Firestore / Postgres (Structured Query Layer)
- Question and concept entities indexed for keyword and faceted search.
- Category and difficulty facets indexed for filter-first retrieval.
- `course_id` is a top-level filter on all collections; every composite index includes it as the leading field.

### DMR-004: Vector Database (Semantic Retrieval Layer)
- Each chunk embedded at ingest time.
- Metadata fields: question_id, paper_id, competition_id, year, primary_topic, subtopic, difficulty_band, chunk_type.
- Filter on metadata before ANN search.

### DMR-005: Cloud Storage Bucket (Bulk File Store)
- Markdown artifacts exported as `.md` files under `gs://mathbank-corpus-docs/<entity_type>/<entity_id>.md`.
- Source PDFs archived alongside for reprocessing.

## Category Extensibility

- DMR-006: Taxonomy categories are rows in the Canonical Taxonomy Sheets tab. Adding a new category requires only a new row with a unique ID; no schema migration is required in downstream systems.
- DMR-007: Category hierarchy depth is unlimited via the canonical_path field.
- DMR-008: Concept-to-question mappings are stored in a separate join table, so retroactive category tagging does not require updating question rows.
