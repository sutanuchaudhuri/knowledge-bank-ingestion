# Markdown Catalog Requirements

## Purpose

Every entity in the corpus is stored in a canonical markdown form. Markdown is the durable, LLM-readable artifact. It is the source for vector embedding and the format exposed by the API for document retrieval.

## Markdown Artifact Types

| Artifact | Granularity | File Pattern |
|---|---|---|
| Paper Whole Document | Full paper | `paper.md` |
| Question Whole Document | Single question with metadata | `question.md` |
| Statement Chunk | Question statement only | `statement_chunk.md` |
| Solution Chunk | Solution text only | `solution_chunk.md` |
| Context Chunk | Related prior knowledge | `context_chunk.md` |

## Paper Markdown Format (MDR-001)

```markdown
---
doc_type: paper
paper_id: PAPER_AMC10A_2023
test_id: AMC10A_2023
competition: AMC10
year: 2023
form: A
session: November
expected_questions: 30
problem_url: https://...
solution_url: https://...
generated_at: 2026-08-24T00:00:00Z
---

# AMC10A 2023

## Metadata
- **Competition:** AMC 10A
- **Year:** 2023
- **Session:** November
- **Questions:** 30

## Questions

### Question 1
...

### Question 2
...
```

## Question Markdown Format (MDR-002)

```markdown
---
doc_type: question
question_id: AMC10A_2023_Q05
paper_id: PAPER_AMC10A_2023
test_id: AMC10A_2023
q_number: 5
primary_topic: Probability
subtopic: Conditional Probability
concept_ids: [PROB_COND, PROB_BASIC]
technique_ids: [TECH_CASEWORK]
difficulty_band: medium
correct_answer: C
visual_role: none
generated_at: 2026-08-24T00:00:00Z
---

# AMC10A 2023 — Question 5

## Statement

<question text here>

## Answer Choices
- (A) ...
- (B) ...
- (C) ...
- (D) ...
- (E) ...

## Correct Answer
C

## Solution

<solution text here>

## Classification
- **Primary Topic:** Probability
- **Subtopic:** Conditional Probability
- **Difficulty:** Medium
- **Concepts:** PROB_COND, PROB_BASIC
- **Techniques:** TECH_CASEWORK
```

## Formatting Rules

- MDR-003: All LaTeX math expressions are enclosed in `$...$` (inline) or `$$...$$` (block).
- MDR-004: Section headers use `##` for major sections, `###` for sub-sections.
- MDR-005: Answer choices are rendered as unordered lists with `(A)`, `(B)` labels preserved.
- MDR-006: YAML front-matter is required on every artifact; all IDs must be populated.
- MDR-007: Visual descriptions are inserted as a `## Visual Context` section when `visual_role` is not `none`.
- MDR-008: Missing text fields are replaced with `[not available]`; do not emit blank fields.

## Chunk Formatting Rules

- MDR-009: Each chunk's markdown begins with a `<!-- chunk_type: <type> -->` HTML comment for machine identification.
- MDR-010: Chunks include a condensed header: `question_id`, `primary_topic`, `difficulty_band`.
- MDR-011: Maximum chunk size is 512 tokens. Overlap of 64 tokens is applied at boundaries.
- MDR-012: Statement chunks never include solution text.
- MDR-013: Solution chunks include a back-reference to the statement chunk_id.

## Category Index Files

In addition to per-entity markdown, the pipeline generates category-level index files.

### MDR-014: Topic Index

Path: `gs://mathbank-corpus-docs/index/topics/<topic_slug>.md`

Lists all questions tagged to a topic with links to question documents.

```markdown
---
index_type: topic
topic: Probability
total_questions: 142
competitions: [AMC10, AMC12, AIME]
---

# Probability — Question Index

| Question ID | Competition | Year | Subtopic | Difficulty |
|---|---|---|---|---|
| AMC10A_2023_Q05 | AMC10 | 2023 | Conditional | Medium |
...
```

### MDR-015: Competition Index

Path: `gs://mathbank-corpus-docs/index/competitions/<competition_id>.md`

Lists all papers and question counts for a competition.

### MDR-016: Difficulty Index

Path: `gs://mathbank-corpus-docs/index/difficulty/<band>.md`

Lists all questions at a given difficulty band.

### MDR-017: Master Category Index

Path: `gs://mathbank-corpus-docs/index/categories.md`

Single file listing every topic, subtopic, and question count.

```markdown
---
index_type: category_master
generated_at: 2026-08-24T00:00:00Z
---

# MathBank Corpus — Category Index

## Algebra (312 questions)
- Polynomials (48)
- Systems of Equations (35)
...

## Probability (142 questions)
- Conditional Probability (29)
...
```

## Generation Tooling

- MDR-018: Markdown generation is deterministic given identical source fields. Running twice produces identical output.
- MDR-019: Generation writes to local `data/<scope>/<competition>/<year>/<test_id>/markdown/` first, then uploads to Drive and GCS.
- MDR-020: A `generate_indexes` command rebuilds all index files from scratch using current Sheets data.
