# 54. IntelliTutor ML/RL platform: project architecture and scaffolding plan

> **Status: scaffolded, not implemented, not tested.** This document and its siblings
> (55–59) turn the existing, mature design pack in
> [documentation/copilot-instructions/intellitutor-ml-rl/](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/copilot-instructions/intellitutor-ml-rl)
> (16 files, read in full before writing this doc) into concrete repository structure,
> naming, and a phased build plan. Three new independent top-level projects
> (`mathbank-ml-training`, `mathbank-ml-inference`, `mathbank-ml-frontend`) and one new
> module inside the existing `mathbank-rest` (notifications, doc 59) have been
> **scaffolded** in this pass — folder structure, `pyproject.toml`/`package.json`,
> pydantic/zod data contracts, and heavily-commented function/endpoint stubs with
> `# TODO:` / `// TODO:` markers at every point real logic is still needed. **No business
> logic, no model training, no deployed inference, and no automated tests were written in
> this pass** — see §6 for the explicit completed/partial/not-started breakdown and §7 for
> gotchas already discovered while scaffolding.

## 0. Why this exists (verbatim framing from the request)

This is **the heart of the application** — the reason so much learner/content/interaction
data is collected in the first place. Everything built in this session and prior sessions
(micro-courses, tutoring routes, quiz generation, attempt/interaction events, exam
sessions) exists to feed two outcomes:

1. **A customized recognition/mastery path for each student** — what they're weak at,
   what's improving, what's "scratchy" vs genuinely weak, what to practice next, how to
   prepare for a specific competition.
2. **A recalibration/publishing loop for admins** — which courses/routes are working,
   which cohorts need a different intervention, which content needs an admin-reviewed
   metadata fix before it can support a reliable recommendation, and when to publish a
   new or revised course based on aggregated student feedback/outcomes.

## 1. Three independent projects, one new module

| Project | Role | Where it runs | New? |
|---|---|---|---|
| `mathbank-ml-training` | Offline feature/label/dataset building and model training — the part the request says happens in "an ML environment, SageMaker/Jupyter." Produces model artifacts + a `ml.training_run`/`ml.model_registry` row. | Local dev now; SageMaker (notebook instances or Processing/Training jobs) later — see §4. | ✅ new, scaffolded |
| `mathbank-ml-inference` | The one place "online" predictions/recommendations/tutor-policy scoring happen. A FastAPI service, deliberately separate from `mathbank-rest` (doc 13's own suggested name, §5). Reads feature snapshots + approved content, never raw mutable OLTP joins (doc 01 §4). | Own process/port, called by `mathbank-rest` (server-to-server) and, read-only, by `mathbank-ml-frontend`. | ✅ new, scaffolded |
| `mathbank-ml-frontend` | The **separate** frontend the request asked for — the ML-ops/admin-analyst-facing surface (model registry, training runs, cohort clusters, data-readiness backlog, tutor-policy dashboard: doc 14 §3/§5/§6). A distinct audience from `mathbank-web`'s students/course-admins. | Own Next.js app, own port. | ✅ new, scaffolded |
| `mathbank-rest` notifications module | Student/admin notifications (doc 59) — **not** an ML concern, kept out of the `mathbank-ml-*` family on purpose (see §2). | Inside the existing `mathbank-rest` service. | ✅ new module, scaffolded |

**What does *not* get a new project**: the **student-facing** ML surfaces from doc 14 §2/§4
(learning profile, recommendations, exam strategy, misconception trend, data-readiness)
render **inside the existing `mathbank-web`** app, not inside `mathbank-ml-frontend`. This
is the answer to "plan this out with a plan how to integrate in student dashboard or admin
the inference": `mathbank-web` gains new pages under `/learn/intelligence` (student) and a
new admin tab under `/admin` (course-admin-facing, same audience as the rest of
`mathbank-web`'s admin area) that call `mathbank-ml-inference`'s REST API through the same
same-origin-proxy pattern every other `mathbank-web` REST call already uses (`app/api/rest/*`
route handlers) — see §5. `mathbank-ml-frontend` is for the *different*, ML-engineering
audience (doc 14 §5/§6's wireframes plus the registry/training-run/tutor-policy views doc
14 §3 lists) who are not students or course content admins.

## 2. Naming rationale (resolving the request's "all ML projects must be `mathbank-ml-*`")

- `mathbank-ml-training`, `mathbank-ml-inference`, `mathbank-ml-frontend` — all three are
  genuinely ML-specific (training pipeline, inference service, ML-ops dashboard), so all
  three get the `mathbank-ml-*` prefix, matching the request exactly.
- Notifications (doc 59) is **explicitly scoped by the request as "different from ML
  requirements"** — it has nothing to do with models, features, or training; it is "tell a
  student their submission was graded" infrastructure. It is scaffolded as a module inside
  `mathbank-rest` (new `notification` schema + service + router), not a fourth
  `mathbank-ml-*` project, because it needs to sit next to the existing attempt/response/
  grading code paths it reacts to (quiz grading in `quiz_runtime.py`, micro-course activity
  responses in `micro_course_service.py`, attempt grading elsewhere) rather than duplicate a
  whole new service boundary for what is fundamentally an event-driven side effect of
  `mathbank-rest`'s own write paths.

## 3. Repository layout (scaffolded this pass)

```text
mathbank-ml-training/
  pyproject.toml
  README.md
  notebooks/
    00_data_readiness_report.ipynb
    01_feature_label_pipeline.ipynb
    02_mastery_baseline_bkt_ewma.ipynb
    03_success_time_baselines.ipynb
    04_recommendation_ranker.ipynb
    05_exam_pacing_and_dynamic_assembly.ipynb
    06_cohort_clustering.ipynb
    07_tutor_policy_supervised_then_bandit.ipynb
  src/mathbank_ml_training/
    __init__.py
    config.py
    contracts.py            # pydantic entities shared across notebooks/pipelines
    extract/
      __init__.py
      postgres_extract.py
      neo4j_extract.py
    features/
      __init__.py
      mastery_features.py
      content_features.py
      exam_features.py
    labels/
      __init__.py
      success_labels.py
      transfer_labels.py
      reward_labels.py
    datasets/
      __init__.py
      manifest.py
      builder.py
    models/
      __init__.py
      mastery_bkt.py
      success_gbm.py
      time_regression.py
      recommendation_ranker.py
      exam_pacing.py
      cohort_clustering.py
      tutor_policy.py
    evaluation/
      __init__.py
      offline_policy_eval.py
      calibration.py
      leakage_checks.py
    registry/
      __init__.py
      model_registry_client.py
    sagemaker/
      __init__.py
      processing_job.py
      training_job.py
      pipeline.py
  tests/                    # placeholders only, see §6
    test_contracts.py

mathbank-ml-inference/
  pyproject.toml
  Makefile
  README.md
  src/mathbank_ml_inference/
    __init__.py
    main.py                 # FastAPI app
    config.py
    contracts.py            # pydantic request/response models (doc 56)
    db.py                   # Postgres/Neo4j read-only connections
    cache.py
    feature_store.py
    routers/
      __init__.py
      student.py            # GET /v1/ml/me/*
      admin.py               # GET /v1/admin/ml/*
      tutor_policy.py
    services/
      __init__.py
      student_state.py
      recommendation.py
      exam_strategy.py
      tutor_action.py
      data_readiness.py
    registry/
      __init__.py
      model_loader.py
  tests/
    test_contracts.py

mathbank-ml-frontend/
  package.json
  README.md
  app/
    layout.jsx
    page.jsx                 # ML-ops landing: links to the views below
    model-registry/page.jsx
    training-runs/page.jsx
    cohorts/page.jsx
    tutor-policy/page.jsx
    data-readiness/page.jsx
    _components/ui.jsx        # intentionally tiny subset, not a copy of mathbank-web's kit
    api/
      ml/[...path]/route.js   # same-origin proxy to mathbank-ml-inference, same pattern
                               # mathbank-web already uses for mathbank-rest
  lib/
    mlClient.mjs

mathbank-rest/ (existing project, new module only)
  src/mathbank_rest/
    notifications.py          # service functions (doc 59)
    routers/notifications.py  # REST router (doc 59)
  sql/043_notifications.sql   # new migration (doc 59)
```

## 4. SageMaker / Jupyter plan (slow, incremental — per the request)

**Phase 0 (this pass)**: notebooks run **locally** against the dev Postgres/Neo4j, reading
through `mathbank_ml_training.extract.*` — no AWS dependency yet. This lets the pipeline
logic be developed and sanity-checked before any cloud spend.

**Phase 1 (next)**: `sagemaker/processing_job.py` wraps the *same* feature/label code as a
SageMaker Processing job (container = this package installed via `pip install -e .`),
reading from a Postgres snapshot exported to S3/Parquet (doc 13 §4) rather than hitting the
live OLTP database from inside AWS.

**Phase 2**: `sagemaker/training_job.py` wraps `models/*` as SageMaker Training jobs;
artifacts land in S3, a row is written to `ml.training_run`/`ml.model_registry` (doc 55 §4).

**Phase 3**: `sagemaker/pipeline.py` chains extract → feature → label → train → evaluate →
register as a SageMaker Pipeline, matching the `EXTRACT → ... → DEPLOY → MONITOR` stage list
in doc 13 §1 one-for-one.

Every notebook in `notebooks/` is deliberately a thin orchestration layer over
`src/mathbank_ml_training/*` functions, not a place where real logic lives — so the same
logic runs unchanged whether invoked from a notebook, a local script, or a SageMaker job.

## 5. Integration plan — student/admin dashboards (`mathbank-web`)

Not built in this pass (tracked as a follow-on in doc 56 §6), but planned now so the
inference service's contract is designed for it from day one:

```text
mathbank-web (existing)
  app/learn/intelligence/page.jsx        — student learning profile (doc 14 §4)
  app/learn/intelligence/exam-strategy/page.jsx
  app/admin/(protected)/ml-intelligence/[studentId]/page.jsx   — admin student intelligence (doc 14 §5)
  app/api/rest/ml/[[...path]]/route.js   — same-origin proxy to mathbank-ml-inference,
                                            mirroring app/api/rest/quiz/[[...path]]/route.js
```

`mathbank-rest` gains no new ML logic of its own — it is a thin pass-through (or
`mathbank-web`'s proxy calls `mathbank-ml-inference` directly if network topology allows;
either way `mathbank-ml-inference` is the single source of truth for predictions). This
keeps the invariant from doc 16: "PostgreSQL remains canonical ... ML is a service behind
existing experiences" (doc 14 §1).

## 6. Status — what is done, partial, and not started

| Area | Status | Evidence |
|---|---|---|
| Design grounding | ✅ Done | All 16 files in `intellitutor-ml-rl/` read before writing this doc and 55–59 |
| Project scaffolding (folders, `pyproject.toml`/`package.json`, lint/format config) | ✅ Done | §3 tree exists on disk for all 3 new projects + the `mathbank-rest` notifications module |
| Pydantic/zod data contracts | ✅ Done (shapes only) | `contracts.py` in training/inference, matches doc 02's schemas field-for-field; **no validators beyond type/required are implemented** — see `# TODO` markers |
| Postgres/Neo4j extraction functions | 🟡 Partial — function signatures + docstrings + `# TODO` only | `extract/postgres_extract.py`, `extract/neo4j_extract.py` — no actual SQL/Cypher written yet |
| Feature/label pipelines | 🟡 Partial — signatures only | `features/*.py`, `labels/*.py` |
| Model training code | ⬜ Not started (stub only) | `models/*.py` — every function raises `NotImplementedError` with a `# TODO` pointing at the relevant design doc section |
| SageMaker wiring | ⬜ Not started (stub only) | `sagemaker/*.py` |
| Inference endpoints | 🟡 Partial — FastAPI routes exist, return `501 Not Implemented` with a structured `# TODO` body | `routers/*.py`, `services/*.py` |
| `mathbank-ml-frontend` pages | 🟡 Partial — page shells + fetch wiring to the proxy exist, render `// TODO` placeholder content | `app/*/page.jsx` |
| Notifications migration | ✅ Done (schema only) | `043_notifications.sql` — not applied to any live database in this pass |
| Notifications service/router | 🟡 Partial — function signatures + `# TODO` | `notifications.py`, `routers/notifications.py` |
| `mathbank-web` integration pages (§5) | ⬜ Not started | Deliberately deferred — tracked in doc 56 §6, not part of this pass's scope |
| Automated tests | ⬜ Not started (placeholder files only) | Per the explicit instruction: scaffold, do not test yet |
| Any migration applied to a live database | ⬜ Not done | All SQL is new-file-only; nothing has been run against dev Postgres |

## 7. Gotchas discovered while scaffolding (see also GOTCHAS.md)

- `mathbank-rest`'s existing migrations stop at `042_quiz_generation.sql` — the new
  notifications migration is `043_notifications.sql`; **do not reuse 043 for anything else**
  without checking `mathbank-db/sql/` again, since this repo's convention (confirmed by
  reading `mathbank-rest/scripts/migrate_*.py`) is one script per migration file, applied
  explicitly, never auto-run.
- The existing `ml` schema name is free (grep confirmed: no table named `ml.*` exists
  anywhere in `mathbank-db/sql/` today) — doc 02's `ml.*` table names can be used verbatim
  without a collision.
- `mathbank-ml-inference` and `mathbank-ml-frontend` both need their own `.env.example`
  pointing at `mathbank-ml-inference`'s port — follow the exact `.env`/`.env.example`
  convention already used by `mathbank-rest`/`mathbank-agent` (confirmed by inspecting both).

## 8. Requirement inventory (MLARCH-*)

| ID | Requirement | Acceptance evidence | Status |
|---|---|---|---|
| MLARCH-1 | Three independent `mathbank-ml-*` projects exist with the §3 layout | `ls` shows all three directories with `pyproject.toml`/`package.json` present | ✅ |
| MLARCH-2 | Notifications is scaffolded as a `mathbank-rest` module, not a 4th `mathbank-ml-*` project | `mathbank-rest/src/mathbank_rest/notifications.py` exists; no `mathbank-ml-notifications` project was created | ✅ |
| MLARCH-3 | Every stubbed function has a `# TODO`/`// TODO` citing the design-doc section it implements | Spot-checked across all new files | ✅ |
| MLARCH-4 | A SageMaker phase-in plan exists without requiring AWS access today | §4 | ✅ (plan only — no AWS resources created) |
| MLARCH-5 | An explicit, non-duplicative integration plan for `mathbank-web` exists | §5 | ✅ (plan only — `mathbank-web` itself not yet touched) |

## Cross-document relationship

- Source design pack: [documentation/copilot-instructions/intellitutor-ml-rl/](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/copilot-instructions/intellitutor-ml-rl) (16 files, unmodified).
- Companions: [55](55_ML_TRAINING_PIPELINE_REQUIREMENTS.md) (training), [56](56_ML_INFERENCE_SERVICE_REQUIREMENTS.md) (inference), [57](57_ML_NIGHTLY_REINDEXING_REQUIREMENTS.md) (reindexing), [58](58_ML_ANALYTICS_AND_COHORT_DASHBOARDS_REQUIREMENTS.md) (analytics), [59](59_STUDENT_ADMIN_NOTIFICATIONS_PLATFORM.md) (notifications, non-ML).
- Independent of docs 45–53 (this session's other work) — no ordering dependency.
