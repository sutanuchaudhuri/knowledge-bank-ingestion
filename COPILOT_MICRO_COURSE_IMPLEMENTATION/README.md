# Micro-Course Copilot Pack

Start with:

1. `COPILOT_MICRO_COURSE_IMPLEMENTATION.md`
2. `NEXT_MIGRATION_SKELETON.sql`

The Markdown file is the implementation contract.
The SQL file is only a checklist skeleton and must not be executed directly.

Key design:
- existing Concept / Technique / Skill IDs are authoritative;
- "strategy" means existing Technique;
- teacher/admin authors all course content before learner runtime;
- YouTube videos are explicitly curated and transcript-annotated in advance;
- Neo4j is rebuildable from Postgres;
- runtime agent can converse inside an approved state but cannot create curriculum.
