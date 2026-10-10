# MathBank Corpus Requirements Index

This folder defines the implementation plan and requirements for building the MathBank competition math corpus pipeline from the master spreadsheet into a Google Cloud-backed corpus with RAG and APIs.

## Document Map

1. [01_PRODUCT_REQUIREMENTS.md](01_PRODUCT_REQUIREMENTS.md)
2. [02_DATA_MODEL_AND_STORAGE.md](02_DATA_MODEL_AND_STORAGE.md)
3. [03_INGESTION_PIPELINE_REQUIREMENTS.md](03_INGESTION_PIPELINE_REQUIREMENTS.md)
4. [04_MARKDOWN_CATALOG_REQUIREMENTS.md](04_MARKDOWN_CATALOG_REQUIREMENTS.md)
5. [05_RAG_AND_INDEXING_REQUIREMENTS.md](05_RAG_AND_INDEXING_REQUIREMENTS.md)
6. [06_API_REQUIREMENTS.md](06_API_REQUIREMENTS.md)
7. [07_GCP_INFRA_AND_SECURITY_REQUIREMENTS.md](07_GCP_INFRA_AND_SECURITY_REQUIREMENTS.md)
8. [08_ROADMAP_AND_ACCEPTANCE.md](08_ROADMAP_AND_ACCEPTANCE.md)
9. [09_PIPELINE_SEQUENCE.md](09_PIPELINE_SEQUENCE.md)
10. [10_AGENTIC_TUTOR_AND_STUDENT_MASTERY_REQUIREMENTS.md](10_AGENTIC_TUTOR_AND_STUDENT_MASTERY_REQUIREMENTS.md) — ADK/OpenAI agent architecture, scaling requirements for more papers/graph nodes/REST endpoints, and the student mastery extraction design (new `learner.*` schema, new graph attributes).
11. [11_SYSTEM_DIAGRAMS_TESTING_AND_METRICS.md](11_SYSTEM_DIAGRAMS_TESTING_AND_METRICS.md) — entity-relationship diagram, sequence diagrams for every end-to-end flow (ingestion, student login, attempts/mastery, agent query), how to test each flow independently, how to inject future question papers, the test framework, the precision/recall metrics framework with trend tracking, and the agentic-layer/ingestion-layer evals + feedback/analytics endpoints.
12. [12_STUDENT_PROFILE_AND_ADMIN_LOGIN_UI_REQUIREMENTS.md](12_STUDENT_PROFILE_AND_ADMIN_LOGIN_UI_REQUIREMENTS.md) — student login/register/profile dashboard UI (past attempts, strength/weakness by concept, improvement plan) and a predefined-credential admin login gating `/admin`, both an explicit bridge until real OAuth; entity-relationship diagram for the extended `learner.*` schema (`first_name`/`last_name`).
13. [13_PEDAGOGICAL_GRAPH_AND_TUTOR_REQUIREMENTS.md](13_PEDAGOGICAL_GRAPH_AND_TUTOR_REQUIREMENTS.md) — P0 measurable skills, reviewed prerequisites/hierarchy, rich graph metadata, and anonymous diagnostic/progressive-hint UI; P1 solution steps, misconceptions, versioned courses and P2 learner evidence roadmap.
14. [14_AUTOMATIC_ENRICHMENT_RECOVERY.md](14_AUTOMATIC_ENRICHMENT_RECOVERY.md) — automatic metadata recovery and publication retries.
15. [15_RELATIONSHIP_ENRICHMENT.md](15_RELATIONSHIP_ENRICHMENT.md) — semantic taxonomy relationship generation and graph publication.
16. [16_PIPELINE_JOB_CONSOLE_AND_HYBRID_RAG.md](16_PIPELINE_JOB_CONSOLE_AND_HYBRID_RAG.md) — per-paper/competition completion evidence, timestamps and live metrics across all layers; graph + vector + lexical tutor retrieval.
17. [17_DOMAIN_AND_TECHNICAL_GLOSSARY.md](17_DOMAIN_AND_TECHNICAL_GLOSSARY.md) — domain/technical vocabulary, actual database and graph representations, exact strength/weakness scoring, operational states and implemented-vs-planned distinctions.
18. [18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md](18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md) — verifiable progress tracker for the v2 pack (phases 0–13): Prasolov package import, reconciliation, step-graph projection, safety SQL and commands.
19. [19_GOTCHAS_AND_OPERATIONAL_PITFALLS.md](19_GOTCHAS_AND_OPERATIONAL_PITFALLS.md) — every known pitfall (source data, PostgreSQL/locking, graph, pipeline runners, credentials/tools, UI/REST, tests), each with its symptom, cause, fix or rule, and where it is enforced.
20. [20_NOT_YET_IMPLEMENTED.md](20_NOT_YET_IMPLEMENTED.md) — register of what is not built yet: open v2 phases 6–13, gaps inside delivered phases, and the verified operational backlog (failed papers, failed enrichment jobs, stale runs).
21. [21_V2_PACK_IMPLEMENTATION_AUDIT.md](21_V2_PACK_IMPLEMENTATION_AUDIT.md) — file-by-file audit of how much of the v2 pack (incl. `runtime_extension/`) is implemented (~79 % after doc 26), acceptance/golden-flow and what-not-to-do compliance; open gaps merged into 20.
22. [22_AGENT_SESSION_TRANSCRIPTS.md](22_AGENT_SESSION_TRANSCRIPTS.md) — student_id ↔ agent session link (migration 016) and rebuilding full conversations for the student or an admin.
23. [23_E2E_REGRESSION_SUITE.md](23_E2E_REGRESSION_SUITE.md) — Playwright browser regression suite: how to run, coverage, paid `@llm` opt-in, baseline.
24. [24_ADMIN_TEXTBOOK_CORPUS_DASHBOARD.md](24_ADMIN_TEXTBOOK_CORPUS_DASHBOARD.md) — admin Prasolov corpus dashboard (problems, solutions/steps, transformations, taxonomy, diagrams) and the measured source → Postgres → pgvector → Neo4j coverage matrix.
25. [25_LEARNING_ITEM_CONCEPT_EDGES.md](25_LEARNING_ITEM_CONCEPT_EDGES.md) — `LearningItem -[:TARGETS_CONCEPT|TARGETS_SUBCONCEPT]->` graph edges (NYI-ATB-7): contract, implementation, run results, queries, acceptance.
26. [26_GEOMETRY_RUNTIME_COMPLETION_PLAN.md](26_GEOMETRY_RUNTIME_COMPLETION_PLAN.md) — Prasolov-only completion of the runtime extension: step→technique tags (WP1), agent step-runtime tools (WP2), admin import/reconciliation/DAG review UI (WP3), outbox consumers and event lifecycle (WP4), remaining WPs, and the NULL policy + runtime population plan for non-Prasolov corpora.
27. [27_FLUID_WIDGET_LAYER.md](27_FLUID_WIDGET_LAYER.md) — fluid experience & widget orchestration (`math_tutor_fluid_widget_selected_docs`): admin chat → proposed patch → apply, versioned presentation plans, course time orchestrator, activities/polls, WidgetSpec DSL + validation, static/dynamic widgets; per-file pack map.
28. [28_DISTRIBUTED_LIVE_PLATFORM.md](28_DISTRIBUTED_LIVE_PLATFORM.md) — the separate socket deployable `mathbank-live` (:5174): Socket.IO gateway, event contract, rooms/replay, instructor console and takeover; per-file map of `math_tutor_distributed_platform_copilot_handoff`.
29. [29_STUDENT_INPUT_ADDONS.md](29_STUDENT_INPUT_ADDONS.md) — slim student add-ons: LaTeX MathComposer, ElevenLabs voice (TTS/STT) and agentic/deterministic math formatting, delegated through Next.js server routes.
30. [30_MODERN_UI_DESIGN_SYSTEM.md](30_MODERN_UI_DESIGN_SYSTEM.md) — modern UI design system and navigation revamp: tokens, Inter font, icons and pills, sidebar, breadcrumbs, avatars, analytics dashboards, pagination, master-detail, a composer with the mic inside the field, and page coverage; contract in `.github/skills/modern-ui-design`.
31. [31_QUESTION_SPECIFIC_DIAGRAMS.md](31_QUESTION_SPECIFIC_DIAGRAMS.md) — question-specific PDF figure extraction, safe student visibility, tutor rendering, corrective backfill and regression coverage; no full-page fallback.
32. [32_MULTIMODAL_ATTEMPTS_AND_ARTIFACTS.md](32_MULTIMODAL_ATTEMPTS_AND_ARTIFACTS.md) — private multimodal student attempts with versioned evidence, explicit approval and step assessment, plus deterministic declarative artifact generation, validation, publication, private storage and explicit indexing.
33. [33_TOPIC_FIRST_TUTOR_AND_PRACTICE.md](33_TOPIC_FIRST_TUTOR_AND_PRACTICE.md) — durable expanded requirements for intent routing, persisted interactive lesson progress, evidence-gated/versioned practice selection, structural audits, reviewed negatives, source provenance and context-bound printed-work review.
34. [34_GUIDED_PROBLEM_WORKSPACE.md](34_GUIDED_PROBLEM_WORKSPACE.md) — Tutor + My work, authored orientation checks, progressive Q31 construction, step-bound provisional coaching, private upload/paste and explicit learning-data recovery; delivered/partial/planned mapping of the student workspace brief.
35. [35_CORPUS_REPAIR_AND_AUTHORING.md](35_CORPUS_REPAIR_AND_AUTHORING.md) — admin missing-figure triage, reviewed question/image repairs, manual and explicit paid AI original practice drafts, nonofficial publication, and the indexed 210-query developer library.
36. [36_STEP_GENERATOR_AND_AUTHORING.md](36_STEP_GENERATOR_AND_AUTHORING.md) — complete implemented step import/runtime/admin/visual lifecycle with diagrams and REST examples; persistence/cache/reveal boundaries; explicitly proposed universal atomic generator, versioned text/split/merge editor and source/widget/artifact/video attachments.
37. [37_GEOMETRY_SCENE_ENGINE.md](37_GEOMETRY_SCENE_ENGINE.md) — independent deterministic geometry core plus required model-backed reasoning/presentation roles: semi-deterministic planning, bounded validation/revision/acceptance loop, ten offline image-producing fixtures, paid semantic interpretation tests, REST/tutor/UI/storage integration and honest progress tracking.
38. [38_NEURAL_GEOMETRY_ENGINE.md](38_NEURAL_GEOMETRY_ENGINE.md) — independent Neural-Symbolic Geometry Compiler: executable cumulative construction-program foundation reusing geometry tools, layout/fact separation, provisional-curve to trusted-circle transitions, independent image tests, and phased planner/critic/training/Manim/integration roadmap.
39. [39_PRECOMPILED_TUTORING_ROUTES.md](39_PRECOMPILED_TUTORING_ROUTES.md) — offline source-grounded solution compilation, immutable reviewed route snapshots, precomputed H1-H5, owned release-pinned checkpoints, graph metadata and the bounded 20-solution DRAFT pilot; full proposal inventory and remaining acceptance gates.
40. [40_MICRO_COURSE_PLATFORM.md](40_MICRO_COURSE_PLATFORM.md) — deterministic admin/teacher-authored micro-courses bound to existing Concept/Technique/Skill, immutable versioned releases, curated+transcript-approved YouTube ingestion, bounded runtime Q&A and fixed misconception interventions, and an additive `projection_kind='micro_course'` Neo4j projection. Schema and initial authoring/admin/student web slices are present; see the implementation status for verified gaps.
41. [41_INTERACTION_TEMPLATE_LIBRARY.md](41_INTERACTION_TEMPLATE_LIBRARY.md) — reusable interaction/animation/feedback template platform (refactoring the Inequalities/Polynomials/Markov prototypes), deterministic evaluation, misconception evidence accumulation with fixed diagnostics/remediation, Web/Manim SceneSpec parity, and an additive `projection_kind='interaction_template'` Neo4j projection; depends on doc 40's `CourseState` schema. Not yet implemented.
42. [42_MICRO_COURSE_STUDENT_NAVIGATION.md](42_MICRO_COURSE_STUDENT_NAVIGATION.md) — JSON-contract specification (content-agnostic) for the student stepper/enrollment-runtime experience: published-course and enrollment-runtime response shapes, the one-step-at-a-time stepper state machine (done/current/locked, review vs. live-edge), responsive vertical/horizontal layout rules, and real persisted enrollment/quiz-attempt recording. Implemented for the three seeded reference courses.
43. [43_ADMIN_MICRO_COURSE_AUTHORING_UI.md](43_ADMIN_MICRO_COURSE_AUTHORING_UI.md) — implemented design plan for a compact, tabbed admin micro-course workspace: catalog/workspace separation, JSON view, deactivate/reactivate, new-draft-version workflow with diff, activity/analytics tab, interaction-template library browser, and student-preview parity (AMC-1–8, 13, 14) are shipped and tested; YouTube+AI-assisted transcription, AI-partnered content drafting, and the graph/mastery/misconception/wiki insights rail (AMC-9–12) remain deferred and are flagged "coming soon" in the UI. See doc §0/§6 for the per-requirement status table.
44. [44_MICRO_COURSE_MOBILE_AI_ANALYTICS_PLATFORM.md](44_MICRO_COURSE_MOBILE_AI_ANALYTICS_PLATFORM.md) — design plan (backend foundation slice implemented — see §0) for a tablet-tier responsive layout, a React Native mobile app sharing doc 42's JSON contract, silent-interaction-telemetry capture feeding the existing transactional outbox and Neo4j projections, a correlated audit/traceability log, rollup-then-purge data retention, a consolidated new-endpoint inventory, export/auto-generated-cheat-sheet features, a scoped/cited in-course AI tutor, a feedback-reporting loop, per-student AI token/cost usage logging, and non-manipulative completion nudges — every capability mapped against existing Postgres/Neo4j/pgvector/REST surface versus explicitly new additions. Shipped: the audit log and the interaction-event write+outbox-enqueue path (not yet the Neo4j-projecting consumer). Deferred in full: the mobile app, notifications, gamification, AI token metering, export/cheat sheets, and purge automation.
45. [45_REST_API_DOCUMENTATION_AND_ADMIN_CRUD_GAPS.md](45_REST_API_DOCUMENTATION_AND_ADMIN_CRUD_GAPS.md) — planning-only gap analysis (APID-1–11), grounded in the live 268-operation OpenAPI schema: thin/missing Swagger documentation (76% of operations undocumented, 15 untagged, inconsistent tag naming, the admin API key not registered as a real OpenAPI security scheme and misreported as optional), free-text "enum" fields that should be `Literal`s or point at a lookup endpoint, and the taxonomy admin CRUD gap — concept/technique ("strategy")/skill/misconception have no update-description, alias, or activate/deactivate endpoints, and skill/misconception have no listing endpoint at all. Proposes generalizing this session's micro-course audit-log/deactivate/canonical-target-lookup patterns rather than inventing new ones. Not yet implemented.
46. [46_MICRO_COURSE_QUIZ_AUTHORING_API_GAPS.md](46_MICRO_COURSE_QUIZ_AUTHORING_API_GAPS.md) — planning-only gap analysis (QZA-1–8): the `attach_activity`/`attach_learning_item` service functions already exist, fully validated, with zero REST endpoint; there is no endpoint to create/update/deactivate a quiz question (`activity.definition`) at all, and "map to skill"/"map to source" are ambiguous today because three different skill representations and an unstructured `source_lineage` jsonb exist. Proposes a Tier-A activity/quiz bank CRUD surface plus Tier-B state-binding endpoints wiring the already-built service functions. Not yet implemented.
47. [47_MICRO_COURSE_STUDENT_NAVIGATION_V2_AND_AI_ASSIST.md](47_MICRO_COURSE_STUDENT_NAVIGATION_V2_AND_AI_ASSIST.md) — planning-only refinement (MCN2-1–8) of doc 42's implemented state-level stepper: decomposes a single state's multiple videos/interactions/quizzes into a per-item sub-rail with only one item active at a time, fixes the discovered gap that `learning_item` quizzes render as inert non-interactive text today, and specifies a "Help me?"/"Give up" micro-chat scoped to the current item only (reusing, not replacing, doc 42/44's existing AI-grounding design), plus bounded non-manipulative engagement nudges. Not yet implemented.
48. [48_SITE_WIDE_UX_VISUAL_AUDIT.md](48_SITE_WIDE_UX_VISUAL_AUDIT.md) — planning-only, page-by-page re-sweep (UXS-1–8) of all 33 `mathbank-web` routes against the `modern-ui-design` skill's checklist: inconsistent loading/empty-state treatment is the single most common gap, the `db/*` and `graph/*` routes predate the design-token system and show hard-coded colors/missing `PageHeader` throughout, several admin authoring screens have dense multi-action regions with no primary/secondary hierarchy, and five pages format dates/numbers with locale-dependent calls during render (a hydration-risk pattern). Maps findings back to doc 30's existing `UI-2`/`UI-6`/`UI-14`/`UI-15` ✅ rows to flag now-known exceptions. Not yet implemented.
49. [49_FASTMCP_INTELLITUTOR_MCP_APPS_INTEGRATION.md](49_FASTMCP_INTELLITUTOR_MCP_APPS_INTEGRATION.md) — planning-only (FMI-1–8) registration and cross-document impact map for the [../FASTMCP_INTELLITUTOR_COPILOT/](../FASTMCP_INTELLITUTOR_COPILOT) implementation pack (FastMCP Apps/Prefab/Generative UI/Custom HTML exposing MathBank as an MCP server). Identifies the single highest-priority open question — the pack never reconciles with the existing, evaluated `mathbank-agent` Google ADK tutor, which already implements closely overlapping hint-ladder/route/geometry/widget-proposal tools under a different framework — plus concrete impacts on docs 10, 13, 27, 30, 39, 40–48, requiring an explicit replace/coexist/converge decision before implementation. Not yet implemented.

## Scope Summary

- Source data: multi-tab spreadsheet corpus and related PDF/HTML artifacts.
- Output artifacts: canonical markdown per paper and per question-part chunks.
- Storage model: store each document as whole object and chunked objects.
- Indexing model: category + concept + competition + year + difficulty indexes.
- Retrieval model: hybrid reviewed graph evidence, vector similarity and lexical RAG for curriculum and question search.
- Integration model: APIs for future agentic workflows.
- Current implementation reference: [reference/](reference/) contains the canonical source-derived PostgreSQL schema through migration 024, DML, Neo4j projection schema, REST/OpenAPI snapshot and web/agent HTTP notes. It distinguishes checked-in source from migration deployment and live acceptance evidence.

## Naming And Versioning

- Requirement IDs use prefixes:
  - PRD-* for product requirements
  - DMR-* for data model requirements
  - IGR-* for ingestion requirements
  - MDR-* for markdown requirements
  - RAG-* for retrieval requirements
  - API-* for service requirements
  - GCP-* for infrastructure and security requirements
  - AGT-* for agentic tutor / agent-layer requirements
  - MST-* for student mastery extraction requirements
  - SPL-* for student profile / login UI requirements (and the admin login bridge)
  - PED-* for pedagogical graph and anonymous tutoring requirements
  - GOT-* for gotchas / operational pitfalls (doc 19)
  - FW-* for fluid widget / presentation-plan requirements (doc 27)
  - LIVE-* for the distributed live platform and socket gateway (doc 28)
  - UXA-* for student input add-ons: composer, voice, formatting (doc 29)
  - GSE-* for the deterministic geometry core and semi-deterministic agentic scene system (doc 37)
  - NGE-* for the independent neural-symbolic geometry compiler and training roadmap (doc 38)
  - PCR-* for precompiled instructional routes and reasoning graph (doc 39)
  - MCR-* for the deterministic micro-course platform (doc 40)
  - ITL-* for the interaction/animation/feedback/evidence template library (doc 41)
  - MCN-* for the micro-course student navigation JSON contract and stepper state machine (doc 42)
  - AMC-* for the admin micro-course authoring/publish UI design plan (doc 43, not yet implemented)
  - MCX-* for the micro-course mobile/AI/analytics/data-lifecycle platform design plan (doc 44, not yet implemented)
- Version baseline: v1.0 for spreadsheet migration and first production RAG.
