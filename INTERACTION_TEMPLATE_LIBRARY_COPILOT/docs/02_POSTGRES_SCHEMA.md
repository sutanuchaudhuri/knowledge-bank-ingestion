# 02 — PostgreSQL Additions

Use the next available migration after inspecting the repository.
Never edit previous migrations.

## `visual.interaction_template`

```sql
CREATE TABLE visual.interaction_template (
    interaction_template_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    template_key text NOT NULL UNIQUE,
    name text NOT NULL,
    interaction_family text NOT NULL,
    description text,
    status text NOT NULL DEFAULT 'ACTIVE',
    created_at timestamptz NOT NULL DEFAULT now()
);
```

## `visual.interaction_template_version`

```sql
CREATE TABLE visual.interaction_template_version (
    interaction_template_version_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_template_id uuid NOT NULL REFERENCES visual.interaction_template,
    version integer NOT NULL,
    input_schema jsonb NOT NULL,
    state_schema jsonb NOT NULL,
    event_schema jsonb NOT NULL,
    output_schema jsonb NOT NULL,
    default_layout jsonb NOT NULL DEFAULT '{}'::jsonb,
    allowed_controls jsonb NOT NULL DEFAULT '[]'::jsonb,
    allowed_icons jsonb NOT NULL DEFAULT '[]'::jsonb,
    diagnostic_capabilities jsonb NOT NULL DEFAULT '[]'::jsonb,
    animation_slots jsonb NOT NULL DEFAULT '[]'::jsonb,
    accessibility_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
    content_hash text NOT NULL,
    status text NOT NULL DEFAULT 'DRAFT',
    created_by text NOT NULL,
    reviewed_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz,
    published_at timestamptz,
    UNIQUE(interaction_template_id, version)
);
```

Published versions are immutable.

## `visual.control_template`

```sql
CREATE TABLE visual.control_template (
    control_template_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    control_key text NOT NULL UNIQUE,
    control_type text NOT NULL,
    config_schema jsonb NOT NULL,
    accessibility_schema jsonb NOT NULL,
    status text NOT NULL DEFAULT 'ACTIVE'
);
```

Initial `control_type` vocabulary:

```text
BUTTON
SLIDER
STEPPER
TOGGLE
RADIO
CHECKBOX
DROPDOWN
NUMBER_INPUT
TEXT_INPUT
DRAG_HANDLE
TIMELINE
PLAYBACK
MATRIX_CELL
VECTOR_HANDLE
GRAPH_POINT
```

## `visual.icon_token`

```sql
CREATE TABLE visual.icon_token (
    icon_token_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    token_key text NOT NULL UNIQUE,
    icon_class text NOT NULL CHECK (
      icon_class IN ('SEMANTIC','CONTEXTUAL','DECORATIVE')
    ),
    semantic_role text,
    asset_id uuid REFERENCES visual.asset,
    accessible_label text NOT NULL,
    allowed_contexts jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL DEFAULT 'ACTIVE'
);
```

## `visual.interaction_instance`

```sql
CREATE TABLE visual.interaction_instance (
    interaction_instance_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_template_version_id uuid NOT NULL
      REFERENCES visual.interaction_template_version,
    canonical_code text NOT NULL UNIQUE,
    title text NOT NULL,
    instance_config jsonb NOT NULL,
    initial_state jsonb NOT NULL DEFAULT '{}'::jsonb,
    learning_objective text NOT NULL,
    success_criteria jsonb NOT NULL,
    feedback_policy_id uuid,
    scene_spec_id uuid,
    content_hash text NOT NULL,
    review_status text NOT NULL DEFAULT 'PENDING_REVIEW',
    created_by text NOT NULL,
    approved_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    approved_at timestamptz
);
```

## Semantic bindings

Add FK-backed tables:

```text
visual.interaction_instance_concept
visual.interaction_instance_technique
visual.interaction_instance_skill
visual.interaction_instance_misconception
```

Roles:

```text
TEACHES
REQUIRES
PRACTICES
ASSESSES
CAN_REVEAL
REMEDIATES
```

## `visual.animation_template`

```sql
CREATE TABLE visual.animation_template (
    animation_template_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    animation_key text NOT NULL UNIQUE,
    name text NOT NULL,
    input_schema jsonb NOT NULL,
    semantic_output_events jsonb NOT NULL DEFAULT '[]'::jsonb,
    reduced_motion_behavior jsonb NOT NULL,
    status text NOT NULL DEFAULT 'ACTIVE'
);
```

## `visual.scene_spec`

```sql
CREATE TABLE visual.scene_spec (
    scene_spec_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_code text NOT NULL,
    version integer NOT NULL,
    scene_schema_version text NOT NULL,
    scene_json jsonb NOT NULL,
    content_hash text NOT NULL,
    status text NOT NULL DEFAULT 'DRAFT',
    created_by text NOT NULL,
    approved_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    approved_at timestamptz,
    UNIQUE(canonical_code, version)
);
```

## `pedagogy.feedback_template`

```sql
CREATE TABLE pedagogy.feedback_template (
    feedback_template_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    feedback_key text NOT NULL,
    version integer NOT NULL,
    feedback_type text NOT NULL,
    approved_content text NOT NULL,
    icon_token_id uuid REFERENCES visual.icon_token,
    animation_template_id uuid REFERENCES visual.animation_template,
    allowed_agent_rephrase boolean NOT NULL DEFAULT false,
    review_status text NOT NULL DEFAULT 'PENDING_REVIEW',
    UNIQUE(feedback_key, version)
);
```

Feedback types:

```text
CORRECT
PARTIAL
TRY_AGAIN
PROCEDURAL_ERROR
CONCEPTUAL_ERROR
MISCONCEPTION_PROBE
MISCONCEPTION_CONFIRMED
PREREQUISITE_GAP
TRANSFER_SUCCESS
OUT_OF_SCOPE
```

## `pedagogy.feedback_policy`

```sql
CREATE TABLE pedagogy.feedback_policy (
    feedback_policy_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_key text NOT NULL,
    version integer NOT NULL,
    policy_json jsonb NOT NULL,
    review_status text NOT NULL DEFAULT 'PENDING_REVIEW',
    UNIQUE(policy_key, version)
);
```

## `pedagogy.misconception_evidence_rule`

```sql
CREATE TABLE pedagogy.misconception_evidence_rule (
    evidence_rule_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    misconception_id uuid NOT NULL REFERENCES knowledge.misconception,
    interaction_template_version_id uuid REFERENCES visual.interaction_template_version,
    semantic_action text NOT NULL,
    error_signature text NOT NULL,
    predicate_json jsonb NOT NULL,
    evidence_weight numeric(5,4) NOT NULL CHECK (evidence_weight BETWEEN -1 AND 1),
    severity smallint,
    requires_probe boolean NOT NULL DEFAULT false,
    diagnostic_learning_item_id text REFERENCES pedagogy.learning_item,
    feedback_template_id uuid REFERENCES pedagogy.feedback_template,
    intervention_id uuid REFERENCES pedagogy.intervention_script,
    review_status text NOT NULL DEFAULT 'PENDING_REVIEW'
);
```

## `learner.interaction_event`

Append-only.

```sql
CREATE TABLE learner.interaction_event (
    interaction_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id uuid NOT NULL REFERENCES learner.student_profile,
    enrollment_id uuid,
    course_state_id uuid,
    interaction_instance_id uuid NOT NULL REFERENCES visual.interaction_instance,
    event_type text NOT NULL,
    semantic_action text NOT NULL,
    control_key text,
    object_id text,
    before_state jsonb,
    action_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    after_state jsonb,
    evaluation_outcome text,
    error_signature text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
```

## `learner.misconception_evidence`

```sql
CREATE TABLE learner.misconception_evidence (
    evidence_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id uuid NOT NULL REFERENCES learner.student_profile,
    interaction_event_id uuid REFERENCES learner.interaction_event,
    misconception_id uuid NOT NULL REFERENCES knowledge.misconception,
    evidence_type text NOT NULL,
    evidence_weight numeric(5,4) NOT NULL,
    confidence_before numeric(5,4),
    confidence_after numeric(5,4),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
```

Do not project learner evidence to shared Neo4j.

## Immutability

Published:
- template versions
- scene specs
- feedback policy versions
- course-bound approved interaction instances

must not be edited in place.
