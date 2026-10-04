# Vector 03 — Mathematics-Aware Chunking and Semantic Representations

## 1. Generic token chunking is not enough

Ordinary RAG pipelines often split text every fixed number of tokens. That is a poor default for mathematics because a split can separate:

- theorem statement from conditions;
- equation from symbol definitions;
- geometry description from the diagram relation it defines;
- proof step from the claim it establishes;
- substitution from the expression it transforms;
- hint from the referenced problem.

Use **semantic mathematical boundaries first and token size second**.

## 2. Problem representations

A typical competition problem should create multiple searchable surfaces rather than arbitrary fragments.

### `PROBLEM_STATEMENT`

Original/canonical statement with preserved mathematics.

### `STRUCTURAL_NORMALIZED`

A generated representation that optionally normalizes local variables and formula form to improve structural matching.

Example:

```text
a^2 + b^2 = c^2
```

may additionally produce:

```text
v1^2 + v2^2 = v3^2
```

The original must always remain available.

### `PROBLEM_WITH_TAXONOMY`

A retrieval-only enrichment containing reviewed concept/technique context.

The generated enrichment must be marked as derived data so it is never mistaken for source text.

## 3. Solution representations

For each solution create:

- one `SOLUTION_FULL` representation;
- one or more `SOLUTION_STEP` chunks;
- optionally a `SOLUTION_TECHNIQUE_SIGNATURE`.

This supports both whole-approach similarity and local reasoning retrieval.

## 4. Concept representations

A concept may have several surfaces:

```text
CONCEPT_DEFINITION
CONCEPT_INTUITION
CONCEPT_PROPERTIES
CONCEPT_APPLICATIONS
CONCEPT_MISCONCEPTIONS
```

Do not embed one giant concept document if the tutor will need these for different pedagogical purposes.

## 5. Technique representations

Techniques such as telescoping, Vieta jumping, power of a point, invariants, AM-GM, Cauchy-Schwarz, LTE, or angle chasing should have compact `TECHNIQUE_SIGNATURE` representations in addition to long teaching notes.

A signature can include:

```text
name
problem cues
canonical transformations
preconditions
common goals
related concepts
anti-patterns
```

## 6. Preserve notation

Do not turn rich mathematics into vague English summaries.

For example, retain:

```text
Given \(x + \frac1x = 3\), find \(x^2 + \frac1{x^2}\).
```

A generated semantic representation may append context:

```text
Entity: competition problem
Domain: algebra
Objects: reciprocal expressions
Likely transformation: square an identity
```

but should preserve the formula itself.

## 7. Formula normalization

Keep two layers:

### Canonical/display form

Original or carefully normalized LaTeX.

### Search-normalized form

Possible operations:

- Unicode normalization;
- whitespace normalization;
- canonical LaTeX command spelling;
- optional local-variable normalization;
- structural annotations;
- extraction of operator/function signatures.

Do not replace all mathematical symbols with English text.

## 8. Geometry representations

Geometry needs special treatment because text may omit diagram structure.

Future representations can include:

- `GEOMETRY_TEXT`
- `GEOMETRY_RELATION_SIGNATURE`
- `DIAGRAM_CAPTION`

Example relation signature:

```text
triangle ABC
D lies on BC
AD perpendicular BC
AB = AC
goal: ...
```

Vector similarity may propose related geometry problems but must not be treated as proof of geometric equivalence.

## 9. Solution-step windows

A step alone can be too context-poor. For step `i`, optionally embed a window containing:

```text
problem summary
previous step
current step
next step
```

Store the center-step identity explicitly so citations point to the correct reasoning unit.

## 10. Chunk hierarchy

Allow parent-child chunks.

```text
Solution full
├── setup
├── transformation
├── key lemma
├── computation
└── conclusion
```

A precise step can be retrieved first and then expanded to its parent solution when the tutor needs more context.

## 11. Initial size guidance

Use these only as soft limits:

- competition problem: entire problem whenever practical;
- solution step/window: ~100–600 tokens;
- concept explanation: ~200–800 tokens;
- book/handout section: ~400–1000 tokens;
- full solution: can be longer, but step chunks should still exist.

Never split merely because a token counter reached N if the split breaks a formula or proof unit.

## 12. Duplicate handling

Compute deterministic content hashes before embedding.

Exact duplicates should avoid duplicate embedding calls while preserving separate provenance links when the same content appears in several sources.

Near duplicates should remain separate canonical entities unless provenance rules say otherwise; vector similarity can flag them for review.

## 13. Representation matrix

| Entity | Representation | Main use |
|---|---|---|
| Problem | `PROBLEM_STATEMENT` | similar-problem retrieval |
| Problem | `STRUCTURAL_NORMALIZED` | variable-insensitive similarity |
| Problem | `PROBLEM_WITH_TAXONOMY` | tutor retrieval with concepts |
| Solution | `SOLUTION_FULL` | approach similarity |
| Solution step | `SOLUTION_STEP` | local reasoning retrieval |
| Concept | `CONCEPT_DEFINITION` | concept lookup |
| Concept | `CONCEPT_INTUITION` | teaching |
| Technique | `TECHNIQUE_SIGNATURE` | technique retrieval |
| Misconception | `MISCONCEPTION` | diagnostic tutoring |
| Hint | `HINT` | graduated assistance |
