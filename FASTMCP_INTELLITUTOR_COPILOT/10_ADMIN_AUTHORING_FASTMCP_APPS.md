# 10 — Admin Authoring with FastMCP Apps

## 1. Admin use cases

Build one protected `FastMCPApp("intellitutor-admin")` for:
- course catalog;
- draft course editing;
- state ordering/transitions;
- canonical graph binding;
- video/transcript annotation;
- quiz authoring;
- interaction instance authoring;
- tutoring route attachment;
- validation;
- review/approval/publish;
- graph/search status.

## 2. Model-visible entry points

Keep admin model surface narrow:

```text
open_course_authoring(course_id)
open_release_review(release_id)
open_content_health_dashboard()
```

Backend CRUD stays app-only.

## 3. Catalog Prefab

Use `DataTable`:
- title;
- canonical code;
- target;
- latest version;
- status;
- validation;
- graph status;
- search status.

Client-side search/sort can stay local if data already loaded.

Server-side filters should use `CallTool`.

## 4. Course editor

Prefab can handle:
- text fields/forms;
- lists/cards;
- status badges;
- module/state tables;
- canonical selector results;
- validation reports.

Use Custom HTML or specialized fixed app for:
- flow graph editor;
- transcript timeline if precision requires it;
- SceneSpec visual editor.

## 5. Quiz authoring

A quiz is canonical content.

Admin form:
- prompt;
- answer options;
- correct answer;
- explanation;
- purpose;
- canonical targets;
- misconception diagnostic mapping;
- review state.

Learner API will later hide the correct answer.

## 6. AI-assisted draft creation

AI may propose:
- a quiz;
- state explanation;
- FAQ;
- transcript semantic annotation;
- interaction configuration;
- remediation text.

Every proposal stores:
- provider/model;
- request ID;
- source IDs;
- prompt/version metadata;
- draft status.

Admin must explicitly accept/edit/reject.

## 7. Generative UI in authoring

Use only to prototype:
- dashboard layouts;
- alternative content arrangements;
- graph summaries.

Do not make the generated UI itself the canonical release artifact.

## 8. Publication review Prefab

Wireframe:

```text
Release v4

Identity                 PASS
Canonical mappings       PASS
State machine            PASS
Video transcripts        PASS
Quizzes                   PASS
Interactions              PASS
Tutoring routes           PASS
Accessibility             PASS
Student payload security  PASS

Graph readiness           READY
Search readiness          READY

[Review details] [Approve] [Publish]
```

After publish:
- publication transaction commits;
- graph/search jobs become pending;
- UI must not claim success until each derived job reports completion.

## 9. FastMCP authorization

Admin backend tools must perform explicit role checks even though they are app-only.

Visibility is not a security boundary.

## 10. Composition safety

Use `CallTool(function_reference)` for admin backend calls wherever possible.

This lets the server/app be mounted under namespaces without brittle hardcoded tool names.
