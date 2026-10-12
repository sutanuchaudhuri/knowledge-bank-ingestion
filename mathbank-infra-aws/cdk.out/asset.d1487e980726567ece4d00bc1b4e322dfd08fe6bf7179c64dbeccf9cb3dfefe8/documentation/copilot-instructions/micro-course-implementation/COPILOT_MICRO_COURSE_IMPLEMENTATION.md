# Copilot Implementation Instructions — Deterministic Admin-Authored Micro-Courses

## 0. Mission

Extend the existing MathBank architecture with **admin/teacher-authored deterministic micro-courses**
attached to the **existing canonical mathematics graph**.

A micro-course is prepared in advance for a Concept / Technique ("strategy") / Skill.

The admin/teacher must be able to use both **Web UI** and **CLI** to:

- create courses and versioned releases;
- map them to EXISTING canonical `knowledge.concept`, `knowledge.technique`, and `knowledge.skill`;
- arrange modules and states;
- attach approved theory/slides/text/images/diagrams;
- paste and approve YouTube videos;
- import or create transcripts during authoring;
- edit timestamped transcript segments;
- annotate segments to existing canonical nodes and misconceptions;
- attach fixed quizzes/checkpoints;
- attach deterministic misconception diagnostics;
- create fixed intervention scripts;
- define all allowed state transitions;
- validate and publish an immutable release;
- project the course into Neo4j;
- rebuild the Neo4j micro-course projection entirely from PostgreSQL;
- verify/diff PostgreSQL versus Neo4j.

At learner runtime, **no new curriculum content is generated**.

The runtime agent may:
- navigate only approved/published states;
- answer within the current approved state/context;
- rephrase approved content;
- classify a learner question/answer to a known misconception;
- choose only among authored branches/interventions;
- administer only pre-authored quizzes/activities;
- resume at the exact prior state/video timestamp.

The runtime agent may NOT:
- search YouTube;
- choose a new video;
- recommend a new URL;
- generate a new quiz;
- generate a new slide;
- generate a new image/diagram;
- invent a new course branch;
- invent a new intervention;
- create a new canonical Concept/Technique/Skill;
- write to Neo4j directly;
- mutate a published course release.

---

# 1. Existing architecture: preserve and reuse

Do not create parallel replacements for existing subsystems.

## Existing canonical knowledge nodes

Reuse:
- `knowledge.concept`
- `knowledge.technique`
- `knowledge.skill`

### IMPORTANT
User-facing **strategy** maps to:

```text
strategy -> knowledge.technique
```

Do NOT introduce a second `Strategy` canonical type.

Use `pedagogy.taxonomy_node` only where the existing textbook-local bridge is needed.
Do not create canonical nodes automatically from free text.

## Existing quiz/problem infrastructure

Reuse:
- `pedagogy.learning_item`

Do not create another learning-item/question bank.

## Existing interactive activity infrastructure

Reuse:
- `activity.definition`
- `activity.instance`
- `activity.response`

Published micro-course activities must be:
- precompiled or instructor-created;
- `persistence_mode='STATIC'`;
- never `LIVE_AGENT_CREATED`.

## Existing visual/media infrastructure

Reuse:
- `visual.widget_spec`
- `visual.asset`

`visual.asset` currently exists but has no application write path.
Implement that write path rather than inventing another generic binary asset table.

## Existing projection infrastructure

Reuse:
- `pipeline.outbox_event`
- `pipeline.outbox_consumption`
- `pipeline.projection_request`
- `pipeline.graph_projection`

Graph projection remains asynchronous and independently verifiable.

## Existing authoring lifecycle

Use the same **immutability/versioning semantics** already proven by `authoring.presentation_plan`,
but do not overload presentation plans as the micro-course canonical store.

Required lifecycle:

```text
DRAFT -> REVIEWED -> APPROVED -> PUBLISHED -> SUPERSEDED / RETIRED
```

Published content is immutable.
Editing a published release means creating a new release version.

---

# 2. Architectural boundary

```text
                EXISTING CANONICAL KNOWLEDGE
           Concept / Technique / Skill / Problem
                          |
                          v
                    MicroCourse
                          |
                          v
                MicroCourseRelease
                    (immutable)
                          |
              +-----------+-----------+
              |                       |
            Modules                State Graph
              |                       |
              +-----------------> CourseState
                                      |
                 +--------------------+-------------------+
                 |                    |                   |
              Assets               Quiz/Check        Intervention
                 |                                        |
        Slide/Image/Video                       fixed authored flow
                 |
          VideoTranscript
                 |
        Timestamped Segments
                 |
    Canonical semantic annotations
```

PostgreSQL is canonical.
Neo4j is derived.
Search/vector indexes are derived.

---

# 3. Migration

Before coding, inspect the migration directory.

Current reviewed architecture includes migration 026 for geometry.
Use the **next available** migration number. Do not assume 027 is still free.

Suggested name if available:

```text
027_deterministic_micro_courses.sql
```

Never modify old migrations.

---

# 4. New PostgreSQL tables

## 4.1 `knowledge.misconception`

Canonical reusable misconception library.

```sql
CREATE TABLE knowledge.misconception (
    misconception_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_code text NOT NULL UNIQUE,
    name text NOT NULL,
    description text NOT NULL,
    symptom text,
    why_wrong text,
    correct_model text,
    recognition_pattern jsonb NOT NULL DEFAULT '{}'::jsonb,
    severity smallint CHECK (severity IS NULL OR severity BETWEEN 1 AND 5),
    level smallint CHECK (level IS NULL OR level BETWEEN 1 AND 10),
    source text NOT NULL DEFAULT 'HUMAN',
    review_status text NOT NULL DEFAULT 'PENDING_REVIEW'
      CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED')),
    approval_method text
      CHECK (approval_method IS NULL OR approval_method IN ('automatic','human')),
    approved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
```

This is canonical knowledge.
Learner-specific hypotheses remain in the existing gap/diagnosis system.

---

## 4.2 `pedagogy.micro_course`

```sql
CREATE TABLE pedagogy.micro_course (
    micro_course_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_code text NOT NULL UNIQUE,
    title text NOT NULL,
    description text,
    estimated_minutes integer CHECK (estimated_minutes IS NULL OR estimated_minutes > 0),
    difficulty_level smallint CHECK (difficulty_level IS NULL OR difficulty_level BETWEEN 1 AND 10),
    created_by text NOT NULL DEFAULT 'admin',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
```

---

## 4.3 `pedagogy.micro_course_target`

Every course must map to existing canonical nodes.

Use real FKs instead of a polymorphic free-text reference.

```sql
CREATE TABLE pedagogy.micro_course_target (
    micro_course_id uuid NOT NULL
      REFERENCES pedagogy.micro_course ON DELETE CASCADE,

    target_type text NOT NULL
      CHECK (target_type IN ('CONCEPT','TECHNIQUE','SKILL')),

    concept_id uuid REFERENCES knowledge.concept,
    technique_id uuid REFERENCES knowledge.technique,
    skill_id uuid REFERENCES knowledge.skill,

    role text NOT NULL DEFAULT 'PRIMARY'
      CHECK (role IN ('PRIMARY','SECONDARY','PREREQUISITE')),

    ordinal integer NOT NULL DEFAULT 0 CHECK (ordinal >= 0),

    PRIMARY KEY (micro_course_id, target_type, role, ordinal),

    CHECK (
       (target_type='CONCEPT'
         AND concept_id IS NOT NULL
         AND technique_id IS NULL
         AND skill_id IS NULL)
    OR (target_type='TECHNIQUE'
         AND concept_id IS NULL
         AND technique_id IS NOT NULL
         AND skill_id IS NULL)
    OR (target_type='SKILL'
         AND concept_id IS NULL
         AND technique_id IS NULL
         AND skill_id IS NOT NULL)
    )
);
```

Publication requires at least one PRIMARY target.

---

## 4.4 `pedagogy.micro_course_release`

```sql
CREATE TABLE pedagogy.micro_course_release (
    release_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    micro_course_id uuid NOT NULL
      REFERENCES pedagogy.micro_course ON DELETE CASCADE,

    version integer NOT NULL CHECK (version >= 1),

    parent_release_id uuid
      REFERENCES pedagogy.micro_course_release ON DELETE SET NULL,

    status text NOT NULL DEFAULT 'DRAFT'
      CHECK (status IN (
        'DRAFT','REVIEWED','APPROVED',
        'PUBLISHED','SUPERSEDED','RETIRED'
      )),

    learning_objectives jsonb NOT NULL DEFAULT '[]'::jsonb,
    prerequisite_summary jsonb NOT NULL DEFAULT '[]'::jsonb,

    agent_policy jsonb NOT NULL DEFAULT '{}'::jsonb,

    content_hash text,

    created_by text NOT NULL,
    reviewed_by text,
    approved_by text,

    created_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz,
    approved_at timestamptz,
    published_at timestamptz,

    UNIQUE (micro_course_id, version)
);
```

```sql
CREATE UNIQUE INDEX micro_course_one_published
ON pedagogy.micro_course_release(micro_course_id)
WHERE status='PUBLISHED';
```

Implement an immutability trigger analogous to the current published presentation-plan guard.

When parent release is PUBLISHED/SUPERSEDED/RETIRED:
- no child INSERT;
- no child UPDATE;
- no child DELETE.

Only lifecycle transition PUBLISHED -> SUPERSEDED/RETIRED is allowed.

---

## 4.5 Modules

```sql
CREATE TABLE pedagogy.micro_course_module (
    module_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    release_id uuid NOT NULL
      REFERENCES pedagogy.micro_course_release ON DELETE CASCADE,
    module_key text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    title text NOT NULL,
    objective text,
    estimated_seconds integer CHECK (estimated_seconds IS NULL OR estimated_seconds > 0),
    required boolean NOT NULL DEFAULT true,
    UNIQUE(release_id, module_key),
    UNIQUE(release_id, ordinal)
);
```

---

## 4.6 Course states

Think in **instructional states**, not just pages.

```sql
CREATE TABLE pedagogy.micro_course_state (
    state_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    release_id uuid NOT NULL
      REFERENCES pedagogy.micro_course_release ON DELETE CASCADE,

    module_id uuid
      REFERENCES pedagogy.micro_course_module ON DELETE CASCADE,

    state_key text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal >= 0),

    state_type text NOT NULL CHECK (state_type IN (
      'ORIENTATION',
      'EXPLANATION',
      'SLIDE',
      'VIDEO',
      'READING',
      'VISUAL',
      'EXAMPLE',
      'CHECKPOINT',
      'QUIZ',
      'DIAGNOSTIC',
      'REMEDIATION',
      'PRACTICE',
      'SUMMARY',
      'TRANSFER'
    )),

    title text NOT NULL,
    objective text,
    student_instruction text,

    estimated_seconds integer CHECK (
      estimated_seconds IS NULL OR estimated_seconds > 0
    ),

    required boolean NOT NULL DEFAULT true,
    skippable boolean NOT NULL DEFAULT false,

    agent_policy jsonb NOT NULL DEFAULT '{}'::jsonb,

    created_at timestamptz NOT NULL DEFAULT now(),

    UNIQUE(release_id, state_key),
    UNIQUE(release_id, ordinal)
);
```

---

# 5. Strong semantic bindings to EXISTING graph nodes

Do not store free-text authoritative concept names.

Create separate FK-backed tables.

## State -> Concept

```sql
pedagogy.micro_course_state_concept
(
  state_id FK,
  concept_id FK knowledge.concept,
  role TEACHES|REQUIRES|REVIEWS|MENTIONS,
  importance,
  PRIMARY KEY(state_id, concept_id, role)
)
```

## State -> Technique

```sql
pedagogy.micro_course_state_technique
(
  state_id FK,
  technique_id FK knowledge.technique,
  role TEACHES|REQUIRES|RECOGNIZES|APPLIES|REVIEWS,
  importance,
  PRIMARY KEY(state_id, technique_id, role)
)
```

## State -> Skill

```sql
pedagogy.micro_course_state_skill
(
  state_id FK,
  skill_id FK knowledge.skill,
  role TEACHES|REQUIRES|ASSESSES|REVIEWS,
  required_level,
  PRIMARY KEY(state_id, skill_id, role)
)
```

## State -> Misconception

```sql
pedagogy.micro_course_state_misconception
(
  state_id FK,
  misconception_id FK knowledge.misconception,
  role WATCH_FOR|ADDRESSES|DIAGNOSES,
  PRIMARY KEY(state_id, misconception_id, role)
)
```

---

# 6. Reuse `visual.asset`

Do not create a duplicate generic asset table.

The existing `visual.asset` is currently not written by application code.
Implement a service/writer.

If needed, add backward-compatible metadata columns:

```sql
ALTER TABLE visual.asset
  ADD COLUMN IF NOT EXISTS asset_kind text,
  ADD COLUMN IF NOT EXISTS title text,
  ADD COLUMN IF NOT EXISTS source_url text,
  ADD COLUMN IF NOT EXISTS rights_note text,
  ADD COLUMN IF NOT EXISTS reviewed_by text,
  ADD COLUMN IF NOT EXISTS reviewed_at timestamptz;
```

Use:

```text
persistence_mode = STATIC
validation_status = VALID
```

for published reusable course assets.

Binary bytes remain in the existing object-storage pattern.

---

# 7. State assets

```sql
CREATE TABLE pedagogy.micro_course_state_asset (
    state_id uuid NOT NULL
      REFERENCES pedagogy.micro_course_state ON DELETE CASCADE,

    asset_id uuid NOT NULL
      REFERENCES visual.asset ON DELETE RESTRICT,

    ordinal integer NOT NULL CHECK (ordinal >= 0),

    presentation_role text NOT NULL CHECK (
      presentation_role IN (
        'PRIMARY','SUPPORT','EXAMPLE','REFERENCE','OPTIONAL'
      )
    ),

    PRIMARY KEY(state_id, asset_id),
    UNIQUE(state_id, ordinal)
);
```

---

# 8. YouTube/video model

The runtime tutor must NEVER search YouTube.

Admin explicitly supplies a URL.

## 8.1 `pedagogy.video_asset`

```sql
CREATE TABLE pedagogy.video_asset (
    video_asset_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    visual_asset_id uuid NOT NULL UNIQUE
      REFERENCES visual.asset ON DELETE RESTRICT,

    provider text NOT NULL
      CHECK (provider IN ('YOUTUBE','VIMEO','INTERNAL')),

    external_video_id text NOT NULL,
    canonical_url text NOT NULL,

    title text NOT NULL,
    creator_name text,
    channel_name text,

    duration_ms bigint CHECK (
      duration_ms IS NULL OR duration_ms > 0
    ),

    retrieved_at timestamptz,
    metadata_hash text,

    transcript_status text NOT NULL DEFAULT 'MISSING'
      CHECK (transcript_status IN (
        'MISSING','IMPORTED','TRANSCRIBED',
        'REVIEWED','APPROVED','STALE'
      )),

    review_status text NOT NULL DEFAULT 'PENDING_REVIEW'
      CHECK (review_status IN (
        'PENDING_REVIEW','APPROVED','REJECTED','STALE'
      )),

    approved_by text,
    approved_at timestamptz,

    UNIQUE(provider, external_video_id)
);
```

---

# 9. Versioned transcript

```sql
CREATE TABLE pedagogy.video_transcript (
    transcript_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    video_asset_id uuid NOT NULL
      REFERENCES pedagogy.video_asset ON DELETE CASCADE,

    version integer NOT NULL CHECK (version >= 1),

    language_code text NOT NULL,

    source_type text NOT NULL CHECK (source_type IN (
      'PROVIDER_CAPTIONS',
      'HUMAN',
      'MODEL_TRANSCRIPTION',
      'IMPORTED_FILE'
    )),

    raw_text text,
    content_hash text NOT NULL,

    status text NOT NULL DEFAULT 'DRAFT'
      CHECK (status IN (
        'DRAFT','REVIEWED','APPROVED','SUPERSEDED'
      )),

    created_by text NOT NULL,
    reviewed_by text,

    created_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz,

    UNIQUE(video_asset_id, version)
);
```

A model may transcribe during AUTHORING if explicitly invoked,
but this is only a DRAFT proposal until reviewed.

---

# 10. Timestamped transcript segments

```sql
CREATE TABLE pedagogy.video_transcript_segment (
    segment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    transcript_id uuid NOT NULL
      REFERENCES pedagogy.video_transcript ON DELETE CASCADE,

    segment_index integer NOT NULL CHECK (segment_index >= 0),

    start_ms bigint NOT NULL CHECK (start_ms >= 0),
    end_ms bigint NOT NULL CHECK (end_ms > start_ms),

    transcript_text text NOT NULL
      CHECK (length(trim(transcript_text)) > 0),

    speaker text,
    segment_hash text NOT NULL,

    review_status text NOT NULL DEFAULT 'PENDING_REVIEW'
      CHECK (review_status IN (
        'PENDING_REVIEW','APPROVED','REJECTED'
      )),

    UNIQUE(transcript_id, segment_index)
);
```

```sql
CREATE INDEX video_segment_time_idx
ON pedagogy.video_transcript_segment(
  transcript_id,
  start_ms,
  end_ms
);
```

---

# 11. Transcript segment annotations

Use FK-backed mapping tables:

```text
pedagogy.video_segment_concept
pedagogy.video_segment_technique
pedagogy.video_segment_skill
pedagogy.video_segment_misconception
```

Each contains:
- `segment_id`;
- canonical target FK;
- `role`;
- `importance` / `confidence`;
- `review_status`;
- `source_type`.

Example Technique roles:

```text
EXPLAINS
USES
REQUIRES
RECOGNITION_CUE
EXAMPLE_OF
```

Example Misconception roles:

```text
MISCONCEPTION_TRIGGER
ADDRESSES
REMEDIATES
```

The transcript annotator UI must select from existing canonical nodes.

---

# 12. Video timeline markers

Add:

```sql
pedagogy.video_timeline_marker
(
  marker_id uuid PK,
  state_id uuid FK,
  video_asset_id uuid FK,
  timestamp_ms bigint NOT NULL,
  marker_type text,
  learning_item_id text NULL FK,
  activity_id uuid NULL FK,
  intervention_id uuid NULL FK,
  note text,
  review_status text
)
```

Recommended marker types:

```text
SEGMENT_START
REQUIRED_PAUSE
OPTIONAL_PAUSE
QUIZ
DIAGNOSTIC
INTERVENTION
RESUME_POINT
```

---

# 13. Approved Q&A context

The learner may ask questions, but the agent must answer from approved bounded context.

```sql
CREATE TABLE pedagogy.state_qa_context (
    qa_context_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    state_id uuid NOT NULL
      REFERENCES pedagogy.micro_course_state ON DELETE CASCADE,

    context_type text NOT NULL CHECK (
      context_type IN (
        'EXPLANATION',
        'DEFINITION',
        'FAQ',
        'DERIVATION',
        'EXAMPLE',
        'COUNTEREXAMPLE',
        'NOTATION',
        'MISCONCEPTION_RESPONSE'
      )
    ),

    question_pattern text,
    approved_content text NOT NULL,

    concept_id uuid REFERENCES knowledge.concept,
    technique_id uuid REFERENCES knowledge.technique,
    skill_id uuid REFERENCES knowledge.skill,
    misconception_id uuid REFERENCES knowledge.misconception,

    priority integer NOT NULL DEFAULT 0,

    review_status text NOT NULL DEFAULT 'PENDING_REVIEW'
      CHECK (review_status IN (
        'PENDING_REVIEW','APPROVED','REJECTED'
      )),

    created_by text NOT NULL,
    approved_by text,

    created_at timestamptz NOT NULL DEFAULT now(),
    approved_at timestamptz
);
```

The model may rephrase `approved_content`.
It may not create new canonical curriculum facts.

---

# 14. Reuse existing `pedagogy.learning_item`

Do not duplicate quiz storage.

```sql
CREATE TABLE pedagogy.micro_course_state_learning_item (
    state_id uuid NOT NULL
      REFERENCES pedagogy.micro_course_state ON DELETE CASCADE,

    learning_item_id text NOT NULL
      REFERENCES pedagogy.learning_item ON DELETE RESTRICT,

    ordinal integer NOT NULL CHECK (ordinal >= 0),

    purpose text NOT NULL CHECK (
      purpose IN (
        'ENTRY_CHECK',
        'COMPREHENSION',
        'RECOGNITION',
        'MISCONCEPTION_DIAGNOSTIC',
        'EXECUTION',
        'EXIT_CHECK',
        'TRANSFER'
      )
    ),

    required boolean NOT NULL DEFAULT true,

    PRIMARY KEY(state_id, learning_item_id),
    UNIQUE(state_id, ordinal)
);
```

---

# 15. Reuse `activity.definition`

For micro-course-only interactions that are not corpus learning items:

```sql
CREATE TABLE pedagogy.micro_course_state_activity (
    state_id uuid NOT NULL
      REFERENCES pedagogy.micro_course_state ON DELETE CASCADE,

    activity_id uuid NOT NULL
      REFERENCES activity.definition ON DELETE RESTRICT,

    ordinal integer NOT NULL CHECK (ordinal >= 0),

    purpose text NOT NULL,
    required boolean NOT NULL DEFAULT true,

    PRIMARY KEY(state_id, activity_id),
    UNIQUE(state_id, ordinal)
);
```

When authored for a course:

```text
source_type = INSTRUCTOR_CREATED or PRECOMPILED
persistence_mode = STATIC
```

Never `LIVE_AGENT_CREATED`.

---

# 16. Deterministic transitions

```sql
CREATE TABLE pedagogy.micro_course_transition (
    transition_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    release_id uuid NOT NULL
      REFERENCES pedagogy.micro_course_release ON DELETE CASCADE,

    from_state_id uuid NOT NULL
      REFERENCES pedagogy.micro_course_state ON DELETE CASCADE,

    to_state_id uuid NOT NULL
      REFERENCES pedagogy.micro_course_state ON DELETE CASCADE,

    transition_type text NOT NULL CHECK (
      transition_type IN (
        'NEXT',
        'CORRECT',
        'INCORRECT',
        'RETRY',
        'MISCONCEPTION',
        'PREREQUISITE_GAP',
        'USER_CONTINUE',
        'USER_BACK',
        'USER_QUESTION_RESOLVED',
        'INTERVENTION_COMPLETE'
      )
    ),

    condition_type text NOT NULL DEFAULT 'ALWAYS'
      CHECK (
        condition_type IN (
          'ALWAYS',
          'LEARNING_ITEM_RESULT',
          'ACTIVITY_RESULT',
          'MISCONCEPTION_CODE',
          'SKILL_STATUS',
          'INTERVENTION_RESULT'
        )
      ),

    condition_payload jsonb NOT NULL DEFAULT '{}'::jsonb,

    priority integer NOT NULL DEFAULT 0,

    review_status text NOT NULL DEFAULT 'PENDING_REVIEW'
      CHECK (
        review_status IN (
          'PENDING_REVIEW','APPROVED','REJECTED'
        )
      ),

    CHECK (
      from_state_id <> to_state_id
      OR transition_type='RETRY'
    )
);
```

Validator must reject:
- required unreachable states;
- invalid cross-release edges;
- uncontrolled cycles;
- missing required exit/fallback.

---

# 17. Static interventions

## `pedagogy.intervention_script`

```sql
CREATE TABLE pedagogy.intervention_script (
    intervention_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    release_id uuid NOT NULL
      REFERENCES pedagogy.micro_course_release ON DELETE CASCADE,

    canonical_code text NOT NULL,
    name text NOT NULL,

    target_misconception_id uuid
      REFERENCES knowledge.misconception,

    target_skill_id uuid
      REFERENCES knowledge.skill,

    target_technique_id uuid
      REFERENCES knowledge.technique,

    entry_state_id uuid
      REFERENCES pedagogy.micro_course_state,

    review_status text NOT NULL DEFAULT 'PENDING_REVIEW',

    UNIQUE(release_id, canonical_code)
);
```

## `pedagogy.intervention_step`

```sql
CREATE TABLE pedagogy.intervention_step (
    intervention_step_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    intervention_id uuid NOT NULL
      REFERENCES pedagogy.intervention_script ON DELETE CASCADE,

    ordinal integer NOT NULL CHECK (ordinal >= 0),

    step_type text NOT NULL CHECK (
      step_type IN (
        'ASK',
        'EXPLAIN',
        'SHOW_ASSET',
        'LEARNING_ITEM',
        'ACTIVITY',
        'WAIT_FOR_RESPONSE',
        'RETURN'
      )
    ),

    prompt_text text,

    asset_id uuid REFERENCES visual.asset,
    learning_item_id text REFERENCES pedagogy.learning_item,
    activity_id uuid REFERENCES activity.definition,

    expected_response_type text,

    UNIQUE(intervention_id, ordinal)
);
```

Example:

```text
M-POWER-001 intervention

1 ASK:
  "Which two points on this secant lie on the circle?"

2 ASK:
  "Which length represents the entire secant from P?"

3 EXPLAIN:
  approved explanation

4 LEARNING_ITEM:
  fixed diagnostic quiz

5 RETURN:
  resume VIDEO state at stored timestamp
```

The runtime agent cannot create step 6.

---

# 18. Course review

Add append-only review history:

```sql
CREATE TABLE pedagogy.micro_course_review (
    review_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    release_id uuid NOT NULL
      REFERENCES pedagogy.micro_course_release ON DELETE CASCADE,

    status text NOT NULL
      CHECK (status IN (
        'APPROVED','NEEDS_REVISION','REJECTED'
      )),

    note text,
    reviewed_by text NOT NULL,

    reviewed_at timestamptz NOT NULL DEFAULT now()
);
```

Do not overwrite history.

---

# 19. Learner course runtime

Do not overload the current step-solving `tutor.runtime_state`.

## Enrollment

```sql
CREATE TABLE learner.micro_course_enrollment (
    enrollment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    student_id uuid NOT NULL
      REFERENCES learner.student_profile ON DELETE CASCADE,

    micro_course_id uuid NOT NULL
      REFERENCES pedagogy.micro_course,

    release_id uuid NOT NULL
      REFERENCES pedagogy.micro_course_release,

    status text NOT NULL DEFAULT 'IN_PROGRESS'
      CHECK (
        status IN (
          'IN_PROGRESS','COMPLETED','ABANDONED'
        )
      ),

    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);
```

## Append-only events

```sql
CREATE TABLE learner.micro_course_state_event (
    event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    enrollment_id uuid NOT NULL
      REFERENCES learner.micro_course_enrollment ON DELETE CASCADE,

    state_id uuid
      REFERENCES pedagogy.micro_course_state,

    event_type text NOT NULL,

    payload jsonb NOT NULL DEFAULT '{}'::jsonb,

    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
```

Add append-only protection.

## Runtime pointer

```sql
CREATE TABLE tutor.micro_course_runtime (
    enrollment_id uuid PRIMARY KEY
      REFERENCES learner.micro_course_enrollment ON DELETE CASCADE,

    current_state_id uuid NOT NULL
      REFERENCES pedagogy.micro_course_state,

    current_video_asset_id uuid
      REFERENCES pedagogy.video_asset,

    current_video_time_ms bigint,

    active_intervention_id uuid
      REFERENCES pedagogy.intervention_script,

    state_version bigint NOT NULL DEFAULT 1,

    updated_at timestamptz NOT NULL DEFAULT now()
);
```

Enrollment is pinned to exact `release_id`.

---

# 20. Admin REST API

Prefix:

```text
/v1/admin/micro-courses
```

All mutation routes use current admin security.

## Courses

```text
GET    /v1/admin/micro-courses
POST   /v1/admin/micro-courses
GET    /v1/admin/micro-courses/{course_id}
PATCH  /v1/admin/micro-courses/{course_id}
```

## Existing taxonomy search

```text
GET /v1/admin/micro-courses/taxonomy/search
    ?q=power
    &type=CONCEPT|TECHNIQUE|SKILL
```

Return canonical IDs.

No implicit node creation.

## Releases

```text
POST /{course_id}/releases
GET  /{course_id}/releases
GET  /releases/{release_id}

POST /releases/{release_id}/validate
POST /releases/{release_id}/review
POST /releases/{release_id}/approve
POST /releases/{release_id}/publish
POST /releases/{release_id}/new-version
```

Mutation of published content => 409.

## Modules/states

```text
POST   /releases/{release_id}/modules
PUT    /releases/{release_id}/modules/reorder

POST   /releases/{release_id}/states
PATCH  /states/{state_id}
DELETE /states/{state_id}

PUT    /states/{state_id}/semantic-bindings
```

## Assets

```text
POST   /states/{state_id}/assets
GET    /states/{state_id}/assets
DELETE /states/{state_id}/assets/{asset_id}
```

## Videos

```text
POST  /releases/{release_id}/videos
GET   /videos/{video_asset_id}
PATCH /videos/{video_asset_id}

POST /videos/{video_asset_id}/refresh-metadata
POST /videos/{video_asset_id}/transcripts/import
GET  /videos/{video_asset_id}/transcripts
```

## Transcript editor

```text
GET /transcripts/{transcript_id}/segments
PUT /transcripts/{transcript_id}/segments

POST   /segments/{segment_id}/annotations
DELETE /segments/{segment_id}/annotations/{annotation_id}

POST /transcripts/{transcript_id}/review
POST /transcripts/{transcript_id}/approve
```

## Quiz/activity linking

```text
POST /states/{state_id}/learning-items
POST /states/{state_id}/activities
```

## Q&A

```text
GET    /states/{state_id}/qa-context
POST   /states/{state_id}/qa-context
PATCH  /qa-context/{id}
DELETE /qa-context/{id}
```

## Transitions

```text
GET    /releases/{release_id}/transitions
POST   /releases/{release_id}/transitions
PATCH  /transitions/{id}
DELETE /transitions/{id}
```

## Interventions

```text
POST /releases/{release_id}/interventions
GET  /releases/{release_id}/interventions
GET  /interventions/{id}
PUT  /interventions/{id}/steps
POST /interventions/{id}/review
```

## Graph

```text
POST /releases/{release_id}/projection-request
GET  /releases/{release_id}/projection-status
GET  /releases/{release_id}/graph-preview
GET  /releases/{release_id}/graph-diff
```

---

# 21. Admin UI

Create:

```text
/admin/micro-courses
```

Use existing protected admin session/proxy conventions.

## Course inventory

Show:
- canonical code;
- title;
- primary target;
- target type;
- latest release;
- publication status;
- validation;
- state count;
- video count;
- transcript approval count;
- unresolved mapping count;
- graph projection status.

Actions:
- open;
- new version;
- validate;
- review;
- publish;
- request graph projection;
- graph rebuild;
- graph diff;
- retire.

## Three-pane editor

```text
+----------------+-------------------------------+----------------------+
| Outline        | Current state                 | Semantic inspector   |
|                |                               |                      |
| Modules        | Slide/Video/Quiz/etc.         | Concepts             |
| States         |                               | Techniques           |
| Branches       |                               | Skills               |
|                |                               | Misconceptions       |
|                |                               | Q&A / Assets         |
+----------------+-------------------------------+----------------------+
```

### Left
- module/state tree;
- drag/reorder in DRAFT only;
- branch markers;
- validation badges.

### Center
State-specific editor.

### Right
Canonical binding search + selected nodes.

Every binding must show:
- canonical ID;
- name;
- role;
- graph presence;
- review state.

---

# 22. YouTube UI

Button:

```text
+ Add YouTube video
```

Admin pastes URL.

Server:
1. normalize provider + video ID;
2. fetch metadata using configured integration;
3. register `visual.asset`;
4. register `pedagogy.video_asset`;
5. do NOT publish;
6. show transcript import options.

No learner route can discover/search videos.

## Transcript Annotator screen

Required UI:

```text
---------------------------------------------------------
| Embedded video                                       |
---------------------------------------------------------
| Timeline with quiz/intervention/annotation markers   |
---------------------------------------------------------
| Timestamped transcript                               |
| 00:00-00:28 ...                                      |
| 00:28-01:03 ...                                      |
---------------------------------------------------------
| Selected segment                                     |
| start / end / text                                   |
---------------------------------------------------------
| Bind: Concept / Technique / Skill / Misconception    |
---------------------------------------------------------
```

Actions:
- seek;
- select active segment;
- split;
- merge;
- edit timestamp;
- edit transcript text;
- annotate;
- approve/reject;
- attach quiz marker;
- attach intervention marker.

Clicking transcript seeks video.
Pausing video selects active segment.

---

# 23. CLI

Add to the existing CLI convention.

Suggested command group:

```bash
micro-courses
```

## Inventory

```bash
micro-courses list
micro-courses show MC-GEO-POWER-POINT
micro-courses releases MC-GEO-POWER-POINT
```

## Create

```bash
micro-courses create \
  --code MC-GEO-POWER-POINT \
  --title "Power of a Point" \
  --technique <existing-technique-uuid>
```

Unknown canonical IDs fail.

## Release/state

```bash
micro-courses release create MC-GEO-POWER-POINT

micro-courses state add <release-id> \
  --key S010 \
  --type ORIENTATION \
  --title "Recognize the configuration"

micro-courses state bind-technique S010 <technique-uuid> \
  --role TEACHES

micro-courses state bind-concept S010 <concept-uuid> \
  --role REQUIRES
```

## Video

```bash
micro-courses video add <release-id> \
  --url "https://www.youtube.com/watch?v=..." \
  --state S030

micro-courses video metadata <video-id>

micro-courses video transcript-import <video-id> --captions

micro-courses video transcript-import <video-id> \
  --file transcript.vtt
```

## Segment annotation

```bash
micro-courses segment list <transcript-id>

micro-courses segment split <segment-id> --at-ms 78000

micro-courses segment merge <segment-a> <segment-b>

micro-courses segment bind-technique \
  <segment-id> <technique-uuid> \
  --role EXPLAINS

micro-courses segment bind-concept \
  <segment-id> <concept-uuid> \
  --role EXPLAINS

micro-courses segment bind-misconception \
  <segment-id> <misconception-uuid> \
  --role MISCONCEPTION_TRIGGER
```

## Attach quiz

```bash
micro-courses state attach-learning-item \
  S040 <learning-item-id> \
  --purpose RECOGNITION
```

## Validate / publish

```bash
micro-courses validate <release-id>

micro-courses review <release-id> \
  --status APPROVED \
  --note "Reviewed by ..."

micro-courses publish <release-id>
```

## Graph

```bash
micro-courses graph request <release-id>
micro-courses graph status <release-id>
micro-courses graph project <release-id>
micro-courses graph verify <release-id>
micro-courses graph diff <release-id>
micro-courses graph rebuild --all-published
```

UI and CLI must use the same service layer.

---

# 24. Neo4j projection

PostgreSQL stays authoritative.

## New labels

```text
MicroCourse
MicroCourseRelease
CourseModule
CourseState
TeachingAsset
VideoAsset
VideoSegment
Misconception
Intervention
```

Do NOT project:
- full transcript text;
- Q&A body;
- correct quiz answers;
- learner responses;
- learner mastery;
- private storage object keys.

## Canonical identity

```text
MicroCourse.canonical_id        = micro_course_id::text
MicroCourseRelease.canonical_id = release_id::text
CourseModule.canonical_id       = module_id::text
CourseState.canonical_id        = state_id::text
TeachingAsset.canonical_id      = visual.asset.asset_id::text
VideoAsset.canonical_id         = video_asset_id::text
VideoSegment.canonical_id       = segment_id::text
Misconception.canonical_id      = misconception_id::text
Intervention.canonical_id       = intervention_id::text
```

Common:

```text
projection_kind = "micro_course"
projection_version = "v1"
```

## Edges

```text
MicroCourse -[:TARGETS]-> Concept
MicroCourse -[:TARGETS]-> Technique
MicroCourse -[:TARGETS]-> Skill

MicroCourse -[:HAS_RELEASE]-> MicroCourseRelease

MicroCourseRelease -[:HAS_MODULE]-> CourseModule
MicroCourseRelease -[:HAS_STATE]-> CourseState

CourseModule -[:HAS_STATE]-> CourseState

CourseState -[:NEXT]-> CourseState
CourseState -[:BRANCHES_TO]-> CourseState

CourseState -[:TEACHES]-> Concept
CourseState -[:REQUIRES]-> Concept

CourseState -[:TEACHES]-> Technique
CourseState -[:REQUIRES]-> Technique

CourseState -[:REQUIRES]-> Skill
CourseState -[:ASSESSES]-> Skill

CourseState -[:ADDRESSES]-> Misconception
CourseState -[:WATCHES_FOR]-> Misconception

CourseState -[:USES_ASSET]-> TeachingAsset

TeachingAsset -[:VIDEO_METADATA]-> VideoAsset
VideoAsset -[:HAS_SEGMENT]-> VideoSegment

VideoSegment -[:EXPLAINS]-> Concept
VideoSegment -[:EXPLAINS]-> Technique
VideoSegment -[:REQUIRES]-> Skill
VideoSegment -[:MENTIONS_MISCONCEPTION]-> Misconception

CourseState -[:USES_LEARNING_ITEM]-> LearningItem

Intervention -[:REMEDIATES]-> Misconception
CourseState -[:CAN_TRIGGER]-> Intervention
```

## Filter

Project only:
- `release.status='PUBLISHED'`;
- approved video;
- approved transcript;
- approved transcript segments;
- approved misconception;
- approved semantic bindings.

DRAFT content stays out of learner graph.

---

# 25. Graph projector

Create:

```text
mathbank-graph/etl/project_micro_courses.py
```

Reuse current connection/config patterns.

Projector ownership:

```text
projection_kind='micro_course'
```

Never delete unrelated graph content.

Never run:

```cypher
MATCH (n) DETACH DELETE n
```

on the shared DB.

## Rebuild algorithm

```text
1 query all PUBLISHED releases
2 create pipeline.graph_projection row
3 MERGE micro-course nodes
4 MERGE edges to existing Concept/Technique/Skill by canonical_id
5 fail on required missing canonical node
6 prune stale projector-owned micro_course nodes/edges
7 complete pipeline.graph_projection
8 run parity verification
```

---

# 26. Extend projection request vocabulary

Current `pipeline.projection_request` supports textbook steps/embeddings/learning items.

Add target:

```text
GRAPH_MICRO_COURSES
```

Add scopes:

```text
MICRO_COURSE
COURSE_RELEASE
VIDEO_ASSET
```

Publishing inserts an outbox event.

Example:

```json
{
  "event_type": "MICRO_COURSE_PUBLISHED",
  "aggregate_type": "MICRO_COURSE_RELEASE",
  "aggregate_id": "<release-id>",
  "payload": {
    "micro_course_id": "...",
    "version": 3
  }
}
```

Outbox consumer creates projection request.

Do NOT write Neo4j inside the PostgreSQL publication transaction.

---

# 27. Graph verify/diff

Admin UI + CLI must compare PostgreSQL expected structure to Neo4j actual structure.

Verify:
- state counts;
- transition counts;
- target edges;
- semantic bindings;
- asset links;
- video/segment counts;
- misconception edges;
- intervention edges.

Fail if:
- DRAFT release appears;
- rejected/stale video appears;
- missing canonical Concept/Technique/Skill target;
- duplicate canonical ID;
- unexpected cross-release edge;
- stale micro-course node remains.

---

# 28. Course validator

Publication must fail if:

- no PRIMARY canonical target;
- unresolved required canonical mapping;
- no states;
- duplicate ordinals;
- no entry state;
- required state unreachable;
- no terminal path;
- unbounded required cycle;
- invalid cross-release edge;
- required video not approved;
- required transcript not approved;
- required used segment not approved;
- required `visual.asset` not VALID;
- required quiz/activity invalid;
- intervention lacks RETURN/resume path;
- misconception branch references unapproved misconception;
- agent policy allows forbidden dynamic generation.

Warnings:
- optional state untagged;
- optional Q&A missing;
- old/stale external metadata;
- missing estimated time.

---

# 29. Publication transaction

Within one PostgreSQL transaction:

```text
lock release
-> validate
-> require APPROVED review
-> supersede old published release
-> mark this release PUBLISHED
-> set published_at
-> insert pipeline.outbox_event
-> commit
```

Graph publication occurs later.

---

# 30. Learner runtime REST

Suggested:

```text
POST /v1/micro-courses/{course_code}/enroll

GET /v1/micro-course-enrollments/{enrollment_id}

POST /v1/micro-course-enrollments/{enrollment_id}/continue

POST /v1/micro-course-enrollments/{enrollment_id}/responses

POST /v1/micro-course-enrollments/{enrollment_id}/video-position

POST /v1/micro-course-enrollments/{enrollment_id}/ask
```

Enrollment pins exact published release.

---

# 31. Paused-video learner question

When learner pauses at `time_ms`:

```text
video_asset_id
+ current_time_ms
+ current state
        |
        v
resolve APPROVED transcript segment
        |
        v
load segment annotations
        |
        v
load approved Q&A context
        |
        v
load allowed misconception/intervention IDs
        |
        v
bounded agent answer
```

SQL pattern:

```sql
SELECT ...
FROM pedagogy.video_transcript_segment s
JOIN pedagogy.video_transcript t USING (transcript_id)
WHERE t.video_asset_id = :video_asset_id
  AND t.status='APPROVED'
  AND s.review_status='APPROVED'
  AND s.start_ms <= :time_ms
  AND s.end_ms > :time_ms
ORDER BY s.start_ms DESC
LIMIT 1;
```

---

# 32. Runtime agent envelope

The model receives only an approved envelope.

Example:

```json
{
  "course": {
    "release_id": "...",
    "title": "Power of a Point"
  },
  "state": {
    "state_id": "...",
    "type": "VIDEO",
    "objective": "Recognize the secant case"
  },
  "video": {
    "time_ms": 137000,
    "active_segment": {
      "start_ms": 118000,
      "end_ms": 164000,
      "text": "approved transcript text"
    }
  },
  "approved_qa": [],
  "concept_ids": [],
  "technique_ids": [],
  "skill_ids": [],
  "misconception_ids": [],
  "allowed_intervention_ids": [],
  "policy": {
    "may_rephrase": true,
    "may_explain_current_content": true,
    "may_create_quiz": false,
    "may_search_web": false,
    "may_recommend_media": false,
    "may_generate_diagram": false,
    "may_add_course_state": false
  }
}
```

---

# 33. Typed agent output

Require:

```json
{
  "answer": "...",
  "grounding_ids": [
    "qa_context:...",
    "video_segment:..."
  ],
  "suspected_misconception_id": null,
  "requested_action": "NONE",
  "intervention_id": null,
  "confidence": 0.87
}
```

Allowed actions only:

```text
NONE
START_INTERVENTION
REPEAT_SEGMENT
SEEK_TO_MARKER
RETURN_TO_STATE
ESCALATE_UNSUPPORTED
```

The model cannot return an arbitrary next state.

Server validates every ID before acting.

---

# 34. Out-of-scope learner question

Learners may ask anything.

If approved state/course material does not support the answer:

```text
status = OUT_OF_APPROVED_SCOPE
```

Do not silently invent curriculum.

UI may offer:
- continue;
- go back to an authored prerequisite state;
- submit/flag question for teacher workflow.

---

# 35. Static intervention resume

If an intervention starts during video:

Persist:
- originating `state_id`;
- `video_asset_id`;
- exact `video_time_ms`.

Run authored intervention.

On RETURN:
- restore exact state;
- restore exact timestamp;
- do not auto-advance.

---

# 36. Admin graph preview

UI needs:

```text
Postgres authoring graph
Neo4j projected graph
Diff
```

Show:
- node counts;
- edge counts;
- missing graph nodes;
- stale graph nodes;
- unresolved canonical targets;
- projection run ID/watermark.

Graph sync success is not equivalent to course content approval.

---

# 37. Admin audit

Every authoring mutation must be traceable.

Reuse/extend current audit patterns.

Audit should contain:
- actor;
- operation;
- target;
- release;
- before;
- after;
- note;
- timestamp.

Published review history must remain append-only.

---

# 38. Test fixture

Create a deterministic fixture:

```text
MC-GEO-POWER-POINT
```

Must contain:
- 1 existing Technique target;
- 1 existing Concept target;
- prerequisite Skills;
- 1 approved Misconception;
- 1 fake/mocked YouTube video asset;
- 4 approved transcript segments;
- semantic annotations;
- at least 5 states;
- recognition quiz;
- misconception diagnostic;
- fixed two-question intervention;
- summary state;
- deterministic transitions.

No live YouTube/provider call in CI.

---

# 39. Unit/integration tests

## DB

Test:
- target exact-one-FK CHECK;
- one published release;
- immutability guard;
- timestamps valid;
- intervention ordering;
- append-only event behavior.

## Services

Test:
- create course with existing Technique;
- reject unknown Technique;
- edit DRAFT;
- reject edit PUBLISHED;
- new version copy;
- validation;
- approval;
- publish;
- outbox event.

## YouTube

Mock provider.

Test:
- URL normalization;
- duplicate provider/video ID;
- metadata hash;
- caption import;
- VTT/SRT import;
- bad timestamps;
- split/merge;
- semantic mapping validation.

## Runtime

Test:
- enrollment pins release;
- later release does not change active enrollment;
- deterministic NEXT;
- quiz CORRECT/INCORRECT branches;
- paused-video segment lookup;
- intervention;
- exact resume timestamp;
- unsupported question;
- invalid model-selected intervention rejected;
- model cannot add new URL/quiz/state.

## Graph

Test:
- only PUBLISHED projected;
- DRAFT absent;
- canonical target edges resolve;
- transcript text absent;
- quiz answer absent;
- prune only `projection_kind='micro_course'`;
- rebuild idempotent;
- graph diff catches missing edge.

## End-to-end

```text
create
-> map existing canonical technique/concept
-> add states
-> add mock YouTube
-> import transcript
-> annotate segments
-> attach quiz
-> create intervention
-> validate
-> approve
-> publish
-> projection request
-> Neo4j project
-> verify graph
-> enroll learner
-> play/pause video
-> ask question
-> fixed intervention
-> resume exact video time
-> complete course
```

---

# 40. Required documentation updates

Update:
- PostgreSQL schema docs;
- DML docs;
- migration order;
- REST API/OpenAPI;
- graph schema docs;
- graph projector ownership docs;
- admin UI docs;
- CLI docs;
- micro-course architecture docs.

Do not claim graph parity until verification has actually run.

---

# 41. Copilot implementation sequence

Copilot must follow this sequence:

1. inspect current source tree and migration maximum;
2. read current schema/DML/graph/API docs;
3. add migration;
4. add DB models/query/service layer;
5. add taxonomy resolver;
6. add asset writer using `visual.asset`;
7. add micro-course CRUD service;
8. add YouTube metadata service;
9. add transcript adapters and editor service;
10. add semantic binding service;
11. add validator;
12. add review/publish service;
13. add admin REST;
14. add CLI;
15. add admin UI;
16. add graph projector;
17. add projection request/outbox integration;
18. add graph verifier/diff;
19. add learner course runtime;
20. add bounded agent tool;
21. add tests;
22. refresh docs/OpenAPI.

Do not begin learner-time generative behavior before the deterministic authoring/publish model is complete.

---

# 42. Hard "do not do" list

Do not:
- replace `authoring.presentation_plan`;
- create a second Concept taxonomy;
- create a second Technique/Strategy taxonomy;
- create a second Skill taxonomy;
- create a second quiz bank;
- create duplicate generic binary storage;
- put transcript bodies in Neo4j;
- put correct answers in Neo4j;
- put learner mastery in shared Neo4j;
- synchronize Neo4j inside PostgreSQL transaction;
- auto-publish AI-authored content;
- allow runtime YouTube search;
- allow runtime arbitrary web resource selection;
- allow runtime quiz generation;
- allow runtime slide/image/diagram generation;
- create canonical nodes from arbitrary strings;
- edit old migration files;
- mutate PUBLISHED release content;
- wipe the shared Neo4j graph during rebuild.

---

# 43. Definition of done

This feature is not complete until:

- Admin Web UI can create full course;
- CLI can perform equivalent core authoring workflow;
- course maps to existing canonical nodes;
- explicit YouTube URL can be added;
- transcript can be imported and edited;
- transcript can be timestamp annotated;
- video segments can be mapped to existing Concept/Technique/Skill;
- approved misconceptions can be attached;
- quizzes are deterministic and pre-authored;
- interventions are deterministic and pre-authored;
- course DAG/state graph is visible before publish;
- validator blocks unresolved required mappings;
- published release is immutable;
- graph projection is asynchronous;
- graph can be rebuilt from PostgreSQL;
- graph diff can prove parity for the micro-course projection;
- learner enrollment pins an immutable release;
- paused-video questions use approved transcript timestamp context;
- agent cannot dynamically create course content;
- intervention resumes exact prior state/time;
- all tests pass;
- existing step-runtime, corpus, graph and authoring tests do not regress.
