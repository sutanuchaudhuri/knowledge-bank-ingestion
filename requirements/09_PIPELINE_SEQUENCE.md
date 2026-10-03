# MathBank — Pipeline Sequence Diagrams

Five phases: Extract → Build → Crawl → Classify → (Migrate / API)

---

## Phase 0 — Extract CSVs from Master Excel

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant Script as extract_corpus_csvs.py
    participant XLSX as Excel Corpus<br/>(Master Question Corpus.xlsx)
    participant FS as Local Filesystem<br/>(data/maths_corpus/)

    Dev->>Script: python scripts/extract_corpus_csvs.py
    Script->>XLSX: openpyxl.load_workbook(read_only=True)
    XLSX-->>Script: 52 sheet names + headers

    loop For each non-empty sheet
        Script->>XLSX: iter_rows(values_only=True)
        XLSX-->>Script: raw row data
        Script->>Script: trim trailing blank rows/cols<br/>normalise cell values
        Script->>FS: write <sheet_slug>.csv
    end

    Script->>FS: write _manifest.csv (inventory)
    Script-->>Dev: 42 CSVs exported, 9 empty skipped
```

---

## Phase 1 — Build Local SQLite Database

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant Script as build_sqlite.py
    participant Mig as db/migrations.py
    participant Schema as db/schema.py
    participant Loader as db/loader.py
    participant CSV as CSV Files<br/>(data/maths_corpus/)
    participant DB as SQLite<br/>(data/mathbank.db)

    Dev->>Script: python scripts/build_sqlite.py --fresh
    Script->>DB: PRAGMA journal_mode=WAL
    Script->>Mig: apply_all(conn) — idempotent ALTER TABLE
    Mig->>DB: ADD COLUMN problem_text_latex, solution_text_latex,<br/>image_paths, classified_at, classifier_model …
    Script->>Schema: load TABLES, INDEXES, VIEWS definitions
    Script->>DB: CREATE TABLE IF NOT EXISTS (22 tables)
    Script->>DB: CREATE INDEX IF NOT EXISTS (25 indexes)
    Script->>DB: CREATE VIEW (6 analytics views)

    Script->>Loader: load_all(conn, TABLES)

    loop For each CSV → table mapping (21 tables)
        Loader->>CSV: open <file>.csv, read DictReader
        Loader->>Loader: slug headers, coerce INTEGER/REAL columns
        Loader->>DB: INSERT OR REPLACE batch (500 rows/commit)
    end

    Note over Loader,DB: Domain union: combinatorics + geometry +<br/>number_theory + complex_numbers → domain_indexed_questions

    Script-->>Dev: 35,514 rows loaded across 22 tables<br/>6 views ready for query
```

---

## Phase 2 — Crawl Unmapped Questions from AoPS

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant Script as crawl_unmapped.py
    participant DB as SQLite<br/>(mathbank.db)
    participant DL as crawl/downloader.py
    participant AoPS as AoPS Wiki<br/>(artofproblemsolving.com)
    participant Parser as crawl/aops_parser.py
    participant FS as Local Filesystem<br/>(data/crawl/)

    Dev->>Script: python scripts/crawl_unmapped.py --limit 100 --delay 2.0
    Script->>DB: SELECT question_id, exam_level, problem_url<br/>FROM unmapped_questions<br/>WHERE mapping_status IN ('UNMAPPED','PENDING')<br/>LIMIT 100
    DB-->>Script: queue of (question_id, level, aops_url)

    loop For each question
        Script->>Script: check data/crawl/<level>/<question_id>/parsed.json exists?

        alt Already downloaded (resume)
            Script->>DB: UPDATE mapping_status = 'CRAWLED' (skip fetch)
        else Not yet downloaded
            Script->>DL: fetch_html(session, url, delay=2.0s)
            DL->>DL: throttle() — enforce min gap between requests
            DL->>AoPS: GET /wiki/index.php/<year>_<exam>_Problems/Problem_N
            AoPS-->>DL: HTML page (200) or HTTP error
            DL->>DL: retry up to 4× with exponential backoff
            DL-->>Script: html string

            Script->>FS: save problem.html

            Script->>Parser: parse_aops_page(html, question_id, url)
            Parser->>Parser: BeautifulSoup parse mw-parser-output
            Parser->>Parser: extract Problem section (h2 headline match)
            Parser->>Parser: extract Solution sections (all variants)

            Note over Parser: img[src*=latex] → alt attribute<br/>contains raw LaTeX: "$x^2$"<br/>(older AoPS pages use PNG for math)

            Parser->>Parser: extract answer_choices (MCQ A–E pattern)
            Parser->>Parser: extract \boxed{} answer value
            Parser->>Parser: collect image_urls
            Parser-->>Script: ParsedQuestion(problem_text, solution_texts,<br/>answer_choices, answer_value, image_urls)

            Script->>FS: write problem_text.md (Problem + Solutions in Markdown)
            Script->>FS: write parsed.json (structured JSON artifact)
            Script->>DB: UPDATE unmapped_questions<br/>SET mapping_status = 'CRAWLED'
        end
    end

    Script-->>Dev: ok=N  failed=M  skipped=K<br/>Artifacts in data/crawl/
```

### Reparse variant (no network)

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant Script as crawl_unmapped.py --reparse
    participant FS as data/crawl/ (existing HTML)
    participant Parser as crawl/aops_parser.py
    participant DB as SQLite

    Dev->>Script: python scripts/crawl_unmapped.py --reparse

    Script->>FS: rglob("problem.html") — scan filesystem
    FS-->>Script: list of html paths

    loop For each problem.html
        Script->>FS: read HTML (no network call)
        Script->>Parser: parse_aops_page(html, ...)
        Parser-->>Script: ParsedQuestion with fixed LaTeX
        Script->>FS: overwrite problem_text.md and parsed.json
        Script->>DB: UPDATE mapping_status = 'CRAWLED'
    end

    Script-->>Dev: Reparse done — ok=N  failed=M
```

---

## Phase 3 — OpenAI Concept Classification

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant Script as classify_crawled.py
    participant Mig as db/migrations.py
    participant DB as SQLite<br/>(mathbank.db)
    participant Clf as classify/concept_classifier.py
    participant OAI as OpenAI API<br/>(gpt-4o-mini / gpt-4o)
    participant FS as data/crawl/<level>/<qid>/parsed.json

    Dev->>Script: python scripts/classify_crawled.py --limit 100
    Script->>Mig: apply_all(conn) — ensure new columns exist
    Script->>DB: SELECT question_id, exam_level, problem_url<br/>FROM unmapped_questions<br/>WHERE mapping_status = 'CRAWLED'<br/>LIMIT 100
    DB-->>Script: queue

    Script->>Clf: load_taxonomy_prompt_block(conn)
    Clf->>DB: SELECT canonical_topic_id, canonical_path, node_type, definition<br/>FROM concepts WHERE canonical_path != ''
    DB-->>Clf: ~280 concept rows
    Clf-->>Script: compact taxonomy string (ID | path | type | definition)

    loop For each question
        Script->>FS: load parsed.json
        FS-->>Script: problem_text, solution_texts, image_urls, answer_value

        Script->>DB: UPDATE questions SET<br/>problem_text_latex, problem_text_raw,<br/>solution_text_latex, all_solutions_json,<br/>image_paths, answer_value, crawled_at
        Note over DB: Text stored BEFORE API call<br/>(safe even if API fails)

        Script->>Clf: classify_question(conn, question_id, exam_level,<br/>problem_text, solution_texts, image_paths, ...)

        Clf->>Clf: _model_for_level(exam_level)<br/>AMC → gpt-4o-mini<br/>AIME/HMMT/SMT → gpt-4o

        Clf->>Clf: build system prompt<br/>(role + taxonomy block + JSON schema)
        Clf->>Clf: build user prompt<br/>(question_id, exam_level, problem,<br/>solutions ×3, image refs, answer)

        Clf->>OAI: chat.completions.create(<br/>  model=gpt-4o-mini|gpt-4o,<br/>  response_format=json_object,<br/>  temperature=0.1<br/>)
        OAI-->>Clf: JSON: primary_mapping, additional_mappings[],<br/>suggested_difficulty, suggested_primary_topic,<br/>classifier_notes

        Clf->>Clf: parse response → ClassificationResult<br/>(ConceptMapping per concept)
        Clf-->>Script: ClassificationResult

        loop For each ConceptMapping in result
            alt Existing concept (is_new=False)
                Script->>DB: INSERT OR REPLACE INTO question_taxonomy_maps<br/>(mapping_id, question_id, concept_id,<br/>association_type, confidence, evidence)
            else New concept proposed (is_new=True)
                Script->>DB: INSERT OR IGNORE INTO concepts<br/>(canonical_topic_id, domain, topic, subtopic,<br/>concept_or_technique, node_type,<br/>canonical_path, definition)
                Script->>DB: INSERT OR REPLACE INTO question_taxonomy_maps
                Note over DB: New concept available immediately<br/>for subsequent classifications
            end
        end

        Script->>DB: UPDATE questions SET<br/>classification_status = 'SOLUTION_REVIEWED',<br/>taxonomy_evidence_status = 'AGENT_INFERRED',<br/>taxonomy_mapping_count, difficulty_band,<br/>primary_topic, classified_at, classifier_model

        Script->>DB: UPDATE unmapped_questions<br/>SET mapping_status = 'CLASSIFIED'
    end

    Script-->>Dev: classified=N  failed=M  new_concepts_created=K
```

---

## Phase 4 — Firestore Migration (planned)

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant Script as setup_firestore.py
    participant DB as SQLite<br/>(mathbank.db)
    participant FS_SDK as google-cloud-firestore
    participant Firestore as Google Firestore<br/>(mathbank-prod)

    Dev->>Script: python scripts/setup_firestore.py --project mathbank-prod
    Script->>Firestore: write _schema sentinel per collection
    Script->>Firestore: write __config__/corpus (schema_version)

    Note over Dev,Firestore: Then migrate data from SQLite

    Script->>DB: SELECT * FROM competitions
    Script->>Firestore: batch write → /competitions/{competition_id}

    Script->>DB: SELECT * FROM concepts
    Script->>Firestore: batch write → /concepts/{canonical_topic_id}

    Script->>DB: SELECT * FROM papers
    Script->>Firestore: batch write → /papers/{paper_id}

    Script->>DB: SELECT * FROM questions<br/>WHERE classification_status = 'SOLUTION_REVIEWED'
    Script->>Firestore: batch write → /questions/{question_id}

    Script->>DB: SELECT * FROM question_taxonomy_maps
    Script->>Firestore: batch write → /question_taxonomy_maps/{mapping_id}

    Dev->>Dev: firebase deploy --only firestore:indexes<br/>(deploys composite indexes from firestore.indexes.json)

    Script-->>Dev: Migration complete
```

---

## Phase 5 — API & RAG (planned)

```mermaid
sequenceDiagram
    autonumber
    actor Agent as Agentic Caller<br/>(future learning assistant)
    participant API as mathbank-api<br/>(Cloud Run / FastAPI)
    participant Firestore as Firestore
    participant VectorDB as Vertex AI<br/>Vector Search
    participant OAI as OpenAI<br/>(embedding)

    Note over Agent,OAI: Read-only query path

    Agent->>API: GET /v1/questions?topic=Probability&difficulty=medium
    API->>Firestore: query questions<br/>WHERE course_id=X AND primary_topic=Probability<br/>AND difficulty_band=medium
    Firestore-->>API: question list
    API-->>Agent: JSON question array

    Agent->>API: POST /v1/search {"q":"logarithm change of base", "filters":{...}}
    API->>OAI: embed query → vector (text-embedding-004)
    OAI-->>API: query vector
    API->>VectorDB: ANN search with metadata pre-filter<br/>(course_id, competition_id, primary_topic)
    VectorDB-->>API: top-K chunk IDs + scores
    API->>Firestore: fetch chunk metadata
    Firestore-->>API: chunk records
    API-->>Agent: ranked results with scores

    Agent->>API: GET /v1/categories
    API->>Firestore: SELECT canonical_topic_id, question_count<br/>FROM categories
    Firestore-->>API: category tree
    API-->>Agent: topic hierarchy with counts
```

---

## End-to-End Data Flow Summary

```mermaid
flowchart TD
    XLSX["📊 Master Excel Corpus\n(52 sheets)"]
    CSV["📁 42 CSV Files\ndata/maths_corpus/"]
    SQLite["🗄️ SQLite DB\ndata/mathbank.db\n22 tables · 25 indexes · 6 views"]
    HTML["🌐 AoPS Wiki Pages\ndata/crawl/<level>/<qid>/problem.html"]
    Parsed["📄 Parsed Artifacts\nproblem_text.md · parsed.json"]
    OAI["🤖 OpenAI GPT-4o\nConcept classification"]
    Maps["🔗 question_taxonomy_maps\n+ updated concepts table"]
    Firestore["☁️ Firestore\n(planned migration)"]
    API["🚀 mathbank-api\n(planned Cloud Run)"]

    XLSX -->|extract_corpus_csvs.py| CSV
    CSV -->|build_sqlite.py| SQLite
    SQLite -->|unmapped_questions queue| HTML
    HTML -->|crawl_unmapped.py + aops_parser| Parsed
    Parsed -->|classify_crawled.py| OAI
    OAI -->|concept mappings| Maps
    Maps -->|stored in| SQLite
    SQLite -->|setup_firestore.py| Firestore
    Firestore --> API
```
