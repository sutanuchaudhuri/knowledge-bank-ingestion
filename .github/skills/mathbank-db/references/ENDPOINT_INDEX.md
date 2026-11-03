# Endpoint index — every REST route → tables it touches

One row per `mathbank-rest` route (from the static route table `generated/endpoints.json`) plus any documented `/v1/` route served elsewhere (⚠). **Verified** tables come from the hand-checked "REST operations today" sections of [documentation/database/schemas/](../../../../documentation/database/schemas/) (reverse of [TABLE_INDEX.md](TABLE_INDEX.md)). **Static trace only** lists tables the call-graph trace found that no doc attributes to the route — usually transitive reads, occasionally dynamic SQL or a doc gap; confirm in code before relying on it. Ops: C=insert R=select U=update/upsert D=delete. Auth = FastAPI dependency found by the trace (`anonymous*` = none found at route level; check router-level dependencies).

## `activities`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `POST /v1/activities/definitions` | staff_actor | `activity.definition` C | — | `routers.live.activity_definition` |

## `admin/activities`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/admin/activities` | Admin key | `activity.definition` R | `core.problem` R, `knowledge.skill` R | `routers.admin_activities.list_activities` |
| `POST /v1/admin/activities` | Admin key | `activity.definition` C, `audit.action_log` C | `core.problem` R, `knowledge.skill` R | `routers.admin_activities.create_activity` |
| `GET /v1/admin/activities/{activity_id}` | Admin key | `activity.definition` R | `core.problem` R, `knowledge.skill` R | `routers.admin_activities.get_activity` |
| `PATCH /v1/admin/activities/{activity_id}` | Admin key | `activity.definition` U, `audit.action_log` C | `core.problem` R, `knowledge.skill` R | `routers.admin_activities.update_activity` |
| `POST /v1/admin/activities/{activity_id}/deactivate` | Admin key | `activity.definition` U, `audit.action_log` C, `pedagogy.micro_course` R, `pedagogy.micro_course_release` R, `pedagogy.micro_course_state` R, `pedagogy.micro_course_state_activity` R | — | `routers.admin_activities.deactivate_activity` |
| `POST /v1/admin/activities/{activity_id}/reactivate` | Admin key | `activity.definition` U, `audit.action_log` C | — | `routers.admin_activities.reactivate_activity` |
| `PATCH /v1/admin/activities/{activity_id}/skill-mapping` | Admin key | `activity.definition` U, `audit.action_log` C | `core.problem` R, `knowledge.skill` R | `routers.admin_activities.set_skill_mapping` |
| `PATCH /v1/admin/activities/{activity_id}/source-mapping` | Admin key | `activity.definition` U, `audit.action_log` C | `core.problem` R, `knowledge.skill` R | `routers.admin_activities.set_source_mapping` |

## `admin/agent-sessions`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/admin/agent-sessions` | Admin key | `learner.agent_session_link` R, `learner.student_profile` R | — | `routers.agent_sessions.admin_agent_sessions` |
| `GET /v1/admin/agent-sessions/{agent_session_id}/transcript` | Admin key | `learner.agent_session_link` R | `learner.student_profile` R | `routers.agent_sessions.admin_agent_transcript` |

## `admin/attempts`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/admin/attempts/{attempt_id}/diagnoses` | Admin key | `learner.solve_attempt` R, `pedagogy.gap_diagnosis` R, `pedagogy.knowledge_gap` R | — | `routers.step_runtime.admin_list_diagnoses` |

## `admin/competitions`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `POST /v1/admin/competitions` | Admin key | `core.competition` CU | — | `routers.admin.create_competition` |

## `admin/corpus`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/admin/corpus/drafts` | Admin key | `core.problem` R, `ingest.corpus_draft` R | — | `routers.admin_corpus.drafts` |
| `POST /v1/admin/corpus/drafts` | Admin key | `core.problem` R, `ingest.corpus_draft` C | — | `routers.admin_corpus.create_draft` |
| `PUT /v1/admin/corpus/drafts/{draft_id}` | Admin key | `ingest.corpus_draft` U | — | `routers.admin_corpus.update_draft` |
| `GET /v1/admin/corpus/drafts/{draft_id}/image` | Admin key | `ingest.corpus_draft` R | — | `routers.admin_corpus.draft_image` |
| `POST /v1/admin/corpus/drafts/{draft_id}/review` | Admin key | `core.competition` C, `core.competition_edition` CU, `core.paper` C, `core.problem` CU, `core.problem_image` C, `core.solution` CR, `ingest.corpus_draft` U, `search.chunk` R, `search.representation` U | — | `routers.admin_corpus.review` |
| `POST /v1/admin/corpus/generate` | Admin key | `core.problem` R, `ingest.corpus_draft` C | — | `routers.admin_corpus.generate` |
| `POST /v1/admin/corpus/images` | Admin key | `core.problem` R, `ingest.corpus_draft` C | — | `routers.admin_corpus.upload` |
| `GET /v1/admin/corpus/problems` | Admin key | `core.competition` R, `core.problem` R, `core.problem_image` R | `core.competition_edition` R, `core.paper` R | `routers.admin_corpus.problems` |
| `GET /v1/admin/corpus/problems/{code}` | Admin key | `core.problem` R | — | `routers.admin_corpus.detail` |

## `admin/imports`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/admin/imports/actions` | Admin key | `ingest.admin_review_action` R | — | `routers.admin_imports.actions` |
| `POST /v1/admin/imports/conflicts/{conflict_id}/decision` | Admin key | `ingest.admin_review_action` C, `ingest.import_conflict` U | — | `routers.admin_imports.decide_conflict` |
| `PUT /v1/admin/imports/dependencies` | Admin key | `ingest.admin_review_action` C, `pedagogy.solution_step_dependency` CDU, `pipeline.outbox_event` C | `core.problem` R, `pedagogy.solution_step` R | `routers.admin_imports.upsert_dependency` |
| `POST /v1/admin/imports/dependencies/reject` | Admin key | `ingest.admin_review_action` C, `pedagogy.solution_step_dependency` U, `pipeline.outbox_event` C | `core.problem` R, `pedagogy.solution_step` R | `routers.admin_imports.reject_dependency` |
| `POST /v1/admin/imports/learning-items/{learning_item_id}/review` | Admin key | `ingest.admin_review_action` C, `pedagogy.learning_item` U, `pipeline.outbox_event` C | — | `routers.admin_imports.review_learning_item` |
| `GET /v1/admin/imports/packages` | Admin key | `ingest.content_package` R, `ingest.import_conflict` R, `ingest.package_file` R, `ingest.reconciliation` R, `ingest.staging_row` R, `pipeline.projection_request` R | — | `routers.admin_imports.packages` |
| `GET /v1/admin/imports/packages/{package_id}` | Admin key | `ingest.content_package` R, `ingest.import_conflict` R, `ingest.package_file` R, `ingest.package_status_event` R, `ingest.reconciliation` R, `ingest.staging_row` R | — | `routers.admin_imports.package_detail` |
| `GET /v1/admin/imports/packages/{package_id}/conflicts` | Admin key | `ingest.import_conflict` R | — | `routers.admin_imports.conflicts` |
| `GET /v1/admin/imports/packages/{package_id}/issues` | Admin key | `ingest.staging_row` R | — | `routers.admin_imports.issues` |
| `GET /v1/admin/imports/problems/{code}/dag` | Admin key | `ingest.admin_review_action` R, `pedagogy.solution_dag_review` R, `pedagogy.solution_step` R, `pedagogy.solution_step_dependency` R | `core.problem` R | `routers.admin_imports.problem_dag` |
| `POST /v1/admin/imports/problems/{code}/dag/review` | Admin key | `ingest.admin_review_action` C, `pedagogy.solution_dag_review` CU | `core.problem` R, `pedagogy.solution_step` R | `routers.admin_imports.review_dag` |
| `GET /v1/admin/imports/projection-requests` | Admin key | `pipeline.projection_request` R | — | `routers.admin_imports.projection_requests` |
| `POST /v1/admin/imports/projection-requests` | Admin key | `ingest.admin_review_action` C, `pipeline.projection_request` CR | — | `routers.admin_imports.request_projection` |
| `GET /v1/admin/imports/reconciliation` | Admin key | `ingest.content_package` R, `ingest.import_conflict` R, `ingest.package_file` R, `pedagogy.chapter_section` R, `pedagogy.diagram` R, `pedagogy.learning_item` R, `pedagogy.learning_item_step_anchor` R, `pedagogy.problem_enrichment` R, `pedagogy.problem_source_ref` R, `pedagogy.solution_part` R, `pedagogy.solution_source_ref` R, `pedagogy.solution_step` R, `pedagogy.solution_step_dependency` R, `pedagogy.solution_step_technique` R, `pedagogy.taxonomy_edge` R, `pedagogy.taxonomy_node` R, `pipeline.projection_request` R, `search.embedding_job` R, `search.embedding_model` R, `search.preprocessing_profile` R, `search.representation` R | `search.chunk` R, `search.embedding` R | `routers.admin_imports.reconciliation` |
| `PATCH /v1/admin/imports/steps/{step_id:path}` | Admin key | `ingest.admin_review_action` C, `pedagogy.solution_step` RU, `pedagogy.taxonomy_node` R, `pipeline.outbox_event` C | `core.problem` R | `routers.admin_imports.edit_step` |

## `admin/interaction-templates`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/admin/interaction-templates` | Admin key | `visual.interaction_template` R, `visual.interaction_template_version` R | — | `routers.interaction_templates.list_templates` |
| `POST /v1/admin/interaction-templates/graph/rebuild` | Admin key | `pedagogy.feedback_policy` R, `pedagogy.feedback_template` R, `pedagogy.misconception_evidence_rule` R, `pipeline.graph_projection` CU, `visual.animation_template` R, `visual.control_template` R, `visual.icon_token` R, `visual.interaction_instance` R, `visual.interaction_instance_concept` R, `visual.interaction_instance_misconception` R, `visual.interaction_instance_skill` R, `visual.interaction_instance_technique` R, `visual.interaction_template` R, `visual.interaction_template_version` R, `visual.scene_spec` R | — | `routers.interaction_templates.rebuild_graph` |
| `GET /v1/admin/interaction-templates/graph/verify` | Admin key | `pedagogy.feedback_policy` R, `pedagogy.feedback_template` R, `pedagogy.misconception_evidence_rule` R | `visual.animation_template` R, `visual.control_template` R, `visual.icon_token` R, `visual.interaction_instance` R, `visual.interaction_template` R, `visual.interaction_template_version` R, `visual.scene_spec` R | `routers.interaction_templates.verify_graph` |
| `POST /v1/admin/interaction-templates/instances/{instance_id}/approve` | Admin key | `pedagogy.feedback_policy` R, `pedagogy.misconception_evidence_rule` R, `visual.interaction_instance` RU, `visual.interaction_instance_misconception` R, `visual.interaction_template_version` R, `visual.scene_spec` R | — | `routers.interaction_templates.approve_instance` |
| `POST /v1/admin/interaction-templates/instances/{instance_id}/validate` | Admin key | `pedagogy.feedback_policy` R, `pedagogy.misconception_evidence_rule` R, `visual.interaction_instance` R, `visual.interaction_instance_misconception` R, `visual.interaction_template_version` R, `visual.scene_spec` R | — | `routers.interaction_templates.validate_instance` |
| `POST /v1/admin/interaction-templates/load-seed-catalog` | Admin key | `visual.animation_template` CU, `visual.control_template` CU, `visual.icon_token` CU, `visual.interaction_template` CU, `visual.interaction_template_version` C | — | `routers.interaction_templates.load_seed_catalog` |
| `GET /v1/admin/interaction-templates/scenes` | Admin key | `visual.scene_spec` R | — | `routers.interaction_templates.list_scenes` |
| `GET /v1/admin/interaction-templates/scenes/promotable-candidates` | Admin key | `visual.scene_spec` R | — | `routers.interaction_templates.list_promotable_candidates_endpoint` |
| `POST /v1/admin/interaction-templates/scenes/promote` | Admin key | `visual.asset` C, `visual.scene_spec` CR | — | `routers.interaction_templates.promote_scene` |
| `GET /v1/admin/interaction-templates/scenes/{scene_spec_id}` | Admin key | `visual.asset` R, `visual.scene_spec` R | — | `routers.interaction_templates.get_scene` |
| `POST /v1/admin/interaction-templates/scenes/{scene_spec_id}/approve` | Admin key | `visual.asset` U, `visual.scene_spec` RU | — | `routers.interaction_templates.approve_scene` |
| `POST /v1/admin/interaction-templates/scenes/{scene_spec_id}/create-instance` | Admin key | `visual.interaction_instance` C, `visual.interaction_instance_concept` C, `visual.interaction_instance_technique` C, `visual.interaction_template` CR, `visual.interaction_template_version` CR, `visual.scene_spec` R | `knowledge.concept` R, `knowledge.technique` R | `routers.interaction_templates.create_instance_from_scene` |
| `POST /v1/admin/interaction-templates/scenes/{scene_spec_id}/validate` | Admin key | `visual.scene_spec` R | — | `routers.interaction_templates.validate_scene` |
| `GET /v1/admin/interaction-templates/scenes/{scene_spec_id}/video` | Admin key | `visual.scene_spec` R | `visual.asset` R | `routers.interaction_templates.get_scene_video` |
| `POST /v1/admin/interaction-templates/versions/{version_id}/publish` | Admin key | `visual.control_template` R, `visual.interaction_template_version` RU | `visual.icon_token` R | `routers.interaction_templates.publish_template_version` |
| `POST /v1/admin/interaction-templates/versions/{version_id}/validate` | Admin key | `visual.control_template` R, `visual.interaction_template_version` R | `visual.icon_token` R | `routers.interaction_templates.validate_template_version` |

## `admin/knowledge-gaps`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/admin/knowledge-gaps` | Admin key | `learner.solve_attempt` R, `learner.student_profile` R, `pedagogy.gap_diagnosis` R, `pedagogy.knowledge_gap` R, `pedagogy.recovery_plan` R | `core.problem` R | `routers.step_runtime.admin_gap_overview` |

## `admin/micro-courses`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/admin/micro-courses` | Admin key | `knowledge.theorem` R, `pedagogy.micro_course` R, `pedagogy.micro_course_release` R, `pedagogy.micro_course_target` R | `knowledge.concept` R, `knowledge.skill` R, `knowledge.technique` R, `pedagogy.micro_course_state` R | `routers.micro_courses.list_admin_courses` |
| `POST /v1/admin/micro-courses` | Admin key | `audit.action_log` C, `pedagogy.micro_course` C, `pedagogy.micro_course_target` C | — | `routers.micro_courses.create_admin_course` |
| `GET /v1/admin/micro-courses/interactions` | Admin key | `visual.interaction_instance` R, `visual.interaction_template` R, `visual.interaction_template_version` R | — | `routers.micro_courses.get_approved_interactions` |
| `GET /v1/admin/micro-courses/releases/{release_id}` | Admin key | `activity.definition` R, `pedagogy.micro_course` R, `pedagogy.micro_course_module` R, `pedagogy.micro_course_release` R, `pedagogy.micro_course_state` R, `pedagogy.micro_course_state_activity` R, `pedagogy.micro_course_state_asset` R, `pedagogy.micro_course_state_concept` R, `pedagogy.micro_course_state_interaction` R, `pedagogy.micro_course_state_misconception` R, `pedagogy.micro_course_state_skill` R, `pedagogy.micro_course_state_technique` R, `pedagogy.micro_course_transition` R, `visual.asset` R | `visual.interaction_instance` R, `visual.interaction_template` R, `visual.interaction_template_version` R | `routers.micro_courses.get_admin_release` |
| `GET /v1/admin/micro-courses/releases/{release_id}/diff/{other_release_id}` | Admin key | `pedagogy.micro_course` R, `pedagogy.micro_course_release` R, `pedagogy.micro_course_state` R, `pedagogy.micro_course_state_interaction` R | `visual.interaction_instance` R | `routers.micro_courses.diff_admin_releases` |
| `POST /v1/admin/micro-courses/releases/{release_id}/modules` | Admin key | `pedagogy.micro_course_module` C | `pedagogy.micro_course_release` R | `routers.micro_courses.create_module` |
| `POST /v1/admin/micro-courses/releases/{release_id}/publish` | Admin key | `audit.action_log` C, `knowledge.misconception` R, `pedagogy.intervention_script` R, `pedagogy.intervention_step` R, `pedagogy.micro_course_release` U, `pedagogy.micro_course_review` R, `pedagogy.state_qa_context` R, `pedagogy.video_asset` R, `pedagogy.video_timeline_marker` R, `pedagogy.video_transcript` R, `pedagogy.video_transcript_segment` R, `pipeline.outbox_event` C | `activity.definition` R, `pedagogy.learning_item` R, `pedagogy.micro_course` R, `pedagogy.micro_course_module` R, `pedagogy.micro_course_state` R, `pedagogy.micro_course_state_activity` R, `pedagogy.micro_course_state_asset` R, `pedagogy.micro_course_state_concept` R, `pedagogy.micro_course_state_interaction` R, `pedagogy.micro_course_state_learning_item` R, `pedagogy.micro_course_state_misconception` R, `pedagogy.micro_course_state_skill` R, `pedagogy.micro_course_state_technique` R, `pedagogy.micro_course_target` R, `pedagogy.micro_course_transition` R, `visual.asset` R, `visual.interaction_instance` R, `visual.interaction_template_version` R | `routers.micro_courses.publish_admin_release` |
| `POST /v1/admin/micro-courses/releases/{release_id}/review` | Admin key | `audit.action_log` C, `knowledge.misconception` R, `pedagogy.intervention_script` RU, `pedagogy.intervention_step` R, `pedagogy.micro_course_release` U, `pedagogy.micro_course_review` C, `pedagogy.micro_course_transition` U, `pedagogy.state_qa_context` U, `pedagogy.video_asset` R, `pedagogy.video_timeline_marker` U, `pedagogy.video_transcript` R, `pedagogy.video_transcript_segment` R | `activity.definition` R, `pedagogy.learning_item` R, `pedagogy.micro_course` R, `pedagogy.micro_course_module` R, `pedagogy.micro_course_state` R, `pedagogy.micro_course_state_activity` R, `pedagogy.micro_course_state_asset` R, `pedagogy.micro_course_state_interaction` R, `pedagogy.micro_course_state_learning_item` R, `pedagogy.micro_course_state_misconception` R, `pedagogy.micro_course_target` R, `visual.asset` R, `visual.interaction_instance` R, `visual.interaction_template_version` R | `routers.micro_courses.review_admin_release` |
| `POST /v1/admin/micro-courses/releases/{release_id}/states` | Admin key | `pedagogy.micro_course_module` R, `pedagogy.micro_course_state` C | `pedagogy.micro_course_release` R | `routers.micro_courses.create_state` |
| `POST /v1/admin/micro-courses/releases/{release_id}/transitions` | Admin key | `pedagogy.micro_course_transition` C | `pedagogy.micro_course_release` R, `pedagogy.micro_course_state` R | `routers.micro_courses.create_transition` |
| `POST /v1/admin/micro-courses/releases/{release_id}/validate` | Admin key | `knowledge.misconception` R, `pedagogy.intervention_script` R, `pedagogy.intervention_step` R, `pedagogy.state_qa_context` R, `pedagogy.video_asset` R, `pedagogy.video_timeline_marker` R, `pedagogy.video_transcript` R, `pedagogy.video_transcript_segment` R | `activity.definition` R, `pedagogy.learning_item` R, `pedagogy.micro_course` R, `pedagogy.micro_course_module` R, `pedagogy.micro_course_release` R, `pedagogy.micro_course_state` R, `pedagogy.micro_course_state_activity` R, `pedagogy.micro_course_state_asset` R, `pedagogy.micro_course_state_interaction` R, `pedagogy.micro_course_state_learning_item` R, `pedagogy.micro_course_state_misconception` R, `pedagogy.micro_course_target` R, `pedagogy.micro_course_transition` R, `visual.asset` R, `visual.interaction_instance` R, `visual.interaction_template_version` R | `routers.micro_courses.validate_admin_release` |
| `POST /v1/admin/micro-courses/states/{state_id}/activities` | Admin key | `activity.definition` R, `pedagogy.micro_course_state_activity` C | `pedagogy.micro_course_release` R, `pedagogy.micro_course_state` R | `routers.admin_activities.attach_activity` |
| `PATCH /v1/admin/micro-courses/states/{state_id}/activities/{activity_id}` | Admin key | `pedagogy.micro_course_state_activity` U | `pedagogy.micro_course_release` R, `pedagogy.micro_course_state` R | `routers.admin_activities.update_activity_binding` |
| `DELETE /v1/admin/micro-courses/states/{state_id}/activities/{activity_id}` | Admin key | `pedagogy.micro_course_state_activity` D | `pedagogy.micro_course_release` R, `pedagogy.micro_course_state` R | `routers.admin_activities.detach_activity` |
| `POST /v1/admin/micro-courses/states/{state_id}/assets` | Admin key | `pedagogy.micro_course_release` R, `pedagogy.micro_course_state_asset` C, `visual.asset` C | `pedagogy.micro_course_state` R | `routers.micro_courses.upload_state_asset` |
| `POST /v1/admin/micro-courses/states/{state_id}/bindings` | Admin key | `pedagogy.micro_course_release` R, `pedagogy.micro_course_state_concept` C, `pedagogy.micro_course_state_misconception` C, `pedagogy.micro_course_state_skill` C, `pedagogy.micro_course_state_technique` C | `pedagogy.micro_course_state` R | `routers.micro_courses.bind_state` |
| `POST /v1/admin/micro-courses/states/{state_id}/interactions` | Admin key | `pedagogy.micro_course_release` R, `pedagogy.micro_course_state_interaction` C, `visual.interaction_instance` R, `visual.interaction_template_version` R | `pedagogy.micro_course_state` R | `routers.micro_courses.bind_interaction` |
| `PATCH /v1/admin/micro-courses/states/{state_id}/items/{item_kind}/{item_id}/sequence` | Admin key | `pedagogy.micro_course_release` R, `pedagogy.micro_course_state_activity` U, `pedagogy.micro_course_state_asset` U, `pedagogy.micro_course_state_interaction` U, `pedagogy.micro_course_state_learning_item` U | `pedagogy.micro_course_state` R | `routers.admin_activities.set_item_sequence_position` |
| `GET /v1/admin/micro-courses/targets` | Admin key | `knowledge.concept` R, `knowledge.misconception` R | — | `routers.micro_courses.search_targets` |
| `GET /v1/admin/micro-courses/templates` | Admin key | `visual.animation_template` R, `visual.control_template` R, `visual.icon_token` R, `visual.interaction_template` R, `visual.interaction_template_version` R | — | `routers.micro_courses.get_widget_library` |
| `GET /v1/admin/micro-courses/{canonical_code}` | Admin key | `pedagogy.micro_course` R, `pedagogy.micro_course_release` R, `pedagogy.micro_course_target` R | — | `routers.micro_courses.get_admin_course` |
| `GET /v1/admin/micro-courses/{canonical_code}/activity` | Admin key | `activity.definition` R, `learner.micro_course_enrollment` R, `learner.micro_course_state_event` R, `learner.student_profile` R, `pedagogy.micro_course` R, `pedagogy.micro_course_state` R, `pedagogy.micro_course_state_activity` R | `pedagogy.micro_course_release` R | `routers.micro_courses.get_admin_course_activity` |
| `POST /v1/admin/micro-courses/{canonical_code}/deactivate` | Admin key | `audit.action_log` C, `pedagogy.micro_course` U | — | `routers.micro_courses.deactivate_admin_course` |
| `GET /v1/admin/micro-courses/{canonical_code}/preview` | Admin key | `activity.definition` R, `pedagogy.state_qa_context` R, `pedagogy.video_asset` R, `pedagogy.video_transcript` R, `pedagogy.video_transcript_segment` R, `visual.asset` R | `knowledge.concept` R, `knowledge.skill` R, `knowledge.technique` R, `knowledge.theorem` R, `pedagogy.learning_item` R, `pedagogy.micro_course` R, `pedagogy.micro_course_module` R, `pedagogy.micro_course_release` R, `pedagogy.micro_course_state` R, `pedagogy.micro_course_state_activity` R, `pedagogy.micro_course_state_asset` R, `pedagogy.micro_course_state_interaction` R, `pedagogy.micro_course_state_learning_item` R, `pedagogy.micro_course_target` R, `pedagogy.micro_course_transition` R, `visual.interaction_instance` R, `visual.interaction_template` R, `visual.interaction_template_version` R, `visual.scene_spec` R | `routers.micro_courses.get_admin_course_preview` |
| `POST /v1/admin/micro-courses/{canonical_code}/reactivate` | Admin key | `audit.action_log` C, `pedagogy.micro_course` U | — | `routers.micro_courses.reactivate_admin_course` |
| `POST /v1/admin/micro-courses/{canonical_code}/releases` | Admin key | `pedagogy.micro_course` R, `pedagogy.micro_course_release` C | — | `routers.micro_courses.create_admin_release` |

## `admin/papers`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/admin/papers` | Admin key | `pipeline.pdf_source` R, `pipeline.work_item` R | — | `routers.admin.list_papers` |
| `POST /v1/admin/papers` | Admin key | `pipeline.pdf_source` CU | — | `routers.admin.register_paper` |
| `POST /v1/admin/papers/batch` | Admin key | `pipeline.pdf_source` CU | — | `routers.admin.register_papers_batch` |
| `POST /v1/admin/papers/{paper_external_code}/retry` | Admin key | `pipeline.pdf_source` U | — | `routers.admin.retry_paper` |

## `admin/pedagogy`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `POST /v1/admin/pedagogy/approve-starter` | Admin key | `knowledge.pedagogy_review_event` C, `knowledge.problem_pedagogy` RU, `knowledge.problem_skill` RU, `knowledge.skill` U, `knowledge.skill_relation` RU | `core.problem` R, `knowledge.concept` R | `routers.pedagogy_admin.approve_starter` |
| `POST /v1/admin/pedagogy/bulk-review` | Admin key | `knowledge.concept_relation` U, `knowledge.pedagogy_review_event` C, `knowledge.problem_concept` RU, `knowledge.problem_pedagogy` RU, `knowledge.problem_skill` RU, `knowledge.problem_technique` RU, `knowledge.skill` U, `knowledge.skill_relation` RU | — | `routers.pedagogy_admin.bulk_review` |
| `POST /v1/admin/pedagogy/edit` | Admin key | `knowledge.concept_relation` U, `knowledge.pedagogy_review_event` C, `knowledge.problem_concept` RU, `knowledge.problem_pedagogy` RU, `knowledge.problem_skill` RU, `knowledge.problem_technique` RU, `knowledge.skill` U, `knowledge.skill_relation` RU | — | `routers.pedagogy_admin.edit` |
| `GET /v1/admin/pedagogy/feedback` | Admin key | `learner.pedagogy_feedback` R | `core.problem` R | `routers.pedagogy_admin.feedback_queue` |
| `POST /v1/admin/pedagogy/feedback-review` | Admin key | `learner.pedagogy_feedback` U | — | `routers.pedagogy_admin.feedback_review` |
| `POST /v1/admin/pedagogy/history` | Admin key | `knowledge.pedagogy_review_event` R, `knowledge.problem_concept` RU, `knowledge.problem_pedagogy` RU, `knowledge.problem_skill` RU, `knowledge.problem_technique` RU, `knowledge.skill` R, `knowledge.skill_relation` RU | — | `routers.pedagogy_admin.history` |
| `POST /v1/admin/pedagogy/publish` | Admin key | `knowledge.enrichment_job` U, `knowledge.pedagogy_publication` C, `knowledge.problem_pedagogy` R, `knowledge.problem_skill` R, `knowledge.relationship_enrichment_job` U, `knowledge.skill_relation` R | `core.problem` R, `knowledge.skill` R | `routers.pedagogy_admin.publish` |
| `GET /v1/admin/pedagogy/queue` | Admin key | `knowledge.concept_relation` R, `knowledge.enrichment_job` R, `knowledge.pedagogy_publication` R, `knowledge.problem_concept` RU, `knowledge.problem_pedagogy` RU, `knowledge.problem_skill` RU, `knowledge.problem_technique` RU, `knowledge.relationship_enrichment_job` R, `knowledge.skill` R, `knowledge.skill_relation` RU | `core.problem` R, `knowledge.concept` R, `knowledge.technique` R | `routers.pedagogy_admin.queue` |
| `POST /v1/admin/pedagogy/reclassify` | Admin key | `core.solution` R, `knowledge.enrichment_job` CU, `knowledge.problem_concept` CD, `knowledge.problem_pedagogy` CU, `knowledge.problem_skill` CDU, `knowledge.problem_technique` CD, `knowledge.skill` CU, `knowledge.skill_relation` CU, `pedagogy.problem_source_ref` R | `core.problem` R, `pedagogy.taxonomy_node` R | `routers.pedagogy_admin.reclassify` |
| `GET /v1/admin/pedagogy/retrieval-examples` | Admin key | `learner.pedagogy_feedback` R | `core.problem` R | `routers.pedagogy_admin.retrieval_examples` |
| `POST /v1/admin/pedagogy/review` | Admin key | `knowledge.concept_relation` U, `knowledge.pedagogy_review_event` C, `knowledge.problem_concept` RU, `knowledge.problem_pedagogy` RU, `knowledge.problem_skill` RU, `knowledge.problem_technique` RU, `knowledge.skill` U, `knowledge.skill_relation` RU | — | `routers.pedagogy_admin.review` |

## `admin/pipeline`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/admin/pipeline/jobs` | Admin key | `core.competition` R, `core.paper` R, `core.problem_image` R, `core.solution` R, `knowledge.enrichment_job` R, `knowledge.problem_concept` R, `knowledge.problem_pedagogy` R, `knowledge.problem_skill` R, `knowledge.relationship_enrichment_job` R, `pipeline.pdf_source` R, `pipeline.run` R, `pipeline.work_item` R, `search.embedding_job` R, `search.embedding_model` R, `search.representation` R | `core.competition_edition` R, `core.problem` R, `knowledge.concept` R, `knowledge.concept_relation` R, `knowledge.problem_technique` R, `knowledge.skill` R, `knowledge.skill_relation` R, `search.chunk` R, `search.embedding` R | `routers.admin.pipeline_jobs_status` |
| `GET /v1/admin/pipeline/runs` | Admin key | `pipeline.graph_projection` R, `pipeline.run` R | — | `routers.admin.pipeline_runs` |

## `admin/recovery-plans`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/admin/recovery-plans` | Admin key | `learner.student_profile` R, `pedagogy.recovery_plan` R, `pedagogy.recovery_plan_item` R | `core.problem` R | `routers.step_runtime.admin_recovery_plans` |
| `GET /v1/admin/recovery-plans/{plan_id}` | Admin key | `pedagogy.learning_item` R, `pedagogy.recovery_plan` R, `pedagogy.recovery_plan_item` R, `pedagogy.solution_part` R | `core.problem` R, `pedagogy.solution_step` R, `pedagogy.taxonomy_node` R | `routers.step_runtime.admin_recovery_plan` |

## `admin/socratic`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/admin/socratic/previews/{preview_id}` | Staff cookie | `orchestration.socratic_preview` R, `orchestration.socratic_preview_event` R, `orchestration.socratic_revision` R, `orchestration.socratic_workflow` R | — | `routers.socratic.get_preview` |
| `POST /v1/admin/socratic/previews/{preview_id}/assist` | Staff cookie | `orchestration.socratic_preview` RU, `orchestration.socratic_preview_event` CR, `orchestration.socratic_revision` R, `orchestration.socratic_workflow` R | — | `routers.socratic.assist_preview` |
| `POST /v1/admin/socratic/previews/{preview_id}/respond` | Staff cookie | `orchestration.socratic_preview` RU, `orchestration.socratic_preview_event` CR, `orchestration.socratic_revision` R, `orchestration.socratic_workflow` R | — | `routers.socratic.respond_preview` |
| `POST /v1/admin/socratic/previews/{preview_id}/reveal` | Staff cookie | `orchestration.socratic_preview` RU, `orchestration.socratic_preview_event` CR, `orchestration.socratic_revision` R, `orchestration.socratic_workflow` R | — | `routers.socratic.reveal_preview` |
| `POST /v1/admin/socratic/previews/{preview_id}/transition` | Staff cookie | `orchestration.socratic_preview` RU, `orchestration.socratic_preview_event` CR, `orchestration.socratic_revision` R, `orchestration.socratic_workflow` R | — | `routers.socratic.transition_preview` |
| `GET /v1/admin/socratic/resources` | Staff cookie | `core.solution` R, `pedagogy.solution_route_release` R | `core.problem` R | `routers.socratic.resources` |
| `GET /v1/admin/socratic/session` | Staff cookie | — | — | `routers.socratic.session` |
| `POST /v1/admin/socratic/session` | anonymous* | `audit.action_log` C | — | `routers.socratic.login` |
| `DELETE /v1/admin/socratic/session` | <fastapi.security.api_key.APIKeyCookie object at 0x11bbbe150>, <fastapi.security.api_key.APIKeyCookie object at 0x1158d3c90> | `audit.action_log` C | — | `routers.socratic.logout` |
| `POST /v1/admin/socratic/session/password` | <fastapi.security.api_key.APIKeyCookie object at 0x11bbbe150> | `audit.action_log` C | — | `routers.socratic.change_password` |
| `PUT /v1/admin/socratic/session/role` | <fastapi.security.api_key.APIKeyCookie object at 0x11bbbe150> | `audit.action_log` C | — | `routers.socratic.switch_role` |
| `GET /v1/admin/socratic/strategies` | Staff cookie | `orchestration.socratic_strategy` R | — | `routers.socratic.strategies` |
| `GET /v1/admin/socratic/users` | Staff cookie | — | — | `routers.socratic.list_users` |
| `GET /v1/admin/socratic/users/{username}` | Staff cookie | `audit.action_log` R | — | `routers.socratic.get_user` |
| `PUT /v1/admin/socratic/users/{username}/enabled` | Staff cookie | `audit.action_log` C | — | `routers.socratic.set_enabled` |
| `PUT /v1/admin/socratic/users/{username}/groups/{group}` | Staff cookie | — | `audit.action_log` CR | `routers.socratic.add_group` |
| `DELETE /v1/admin/socratic/users/{username}/groups/{group}` | Staff cookie | `audit.action_log` C | — | `routers.socratic.remove_group` |
| `POST /v1/admin/socratic/users/{username}/password-reset` | Staff cookie | `audit.action_log` C | — | `routers.socratic.reset_password` |
| `POST /v1/admin/socratic/users/{username}/sign-out` | Staff cookie | `audit.action_log` C | — | `routers.socratic.sign_out_everywhere` |
| `GET /v1/admin/socratic/workflows` | Staff cookie | `orchestration.socratic_workflow` R | — | `routers.socratic.workflows` |
| `POST /v1/admin/socratic/workflows` | Staff cookie | `audit.action_log` C, `orchestration.socratic_command` CR, `orchestration.socratic_revision` CR, `orchestration.socratic_strategy` R, `orchestration.socratic_workflow` CR, `pedagogy.solution_route_release` R, `pipeline.outbox_event` C | `core.problem` R, `core.solution` R | `routers.socratic.create_workflow` |
| `GET /v1/admin/socratic/workflows/{workflow_id}` | Staff cookie | `orchestration.socratic_revision` R, `orchestration.socratic_workflow` R | — | `routers.socratic.workflow` |
| `PUT /v1/admin/socratic/workflows/{workflow_id}` | Staff cookie | `audit.action_log` C, `orchestration.socratic_command` CR, `orchestration.socratic_revision` CR, `orchestration.socratic_strategy` R, `orchestration.socratic_workflow` RU, `pedagogy.solution_route_release` R, `pipeline.outbox_event` C | `core.problem` R, `core.solution` R | `routers.socratic.update_workflow` |
| `GET /v1/admin/socratic/workflows/{workflow_id}/revisions/{revision}` | Staff cookie | `orchestration.socratic_revision` R, `orchestration.socratic_workflow` R | — | `routers.socratic.workflow_revision` |
| `POST /v1/admin/socratic/workflows/{workflow_id}/simulate` | Staff cookie | `activity.definition` R, `orchestration.socratic_preview` C, `orchestration.socratic_preview_event` C, `orchestration.socratic_revision` R, `orchestration.socratic_strategy` R, `orchestration.socratic_workflow` R, `pedagogy.solution_route_release` R | `core.problem` R, `core.solution` R | `routers.socratic.simulate` |
| `POST /v1/admin/socratic/workflows/{workflow_id}/validate` | Staff cookie | `activity.definition` R, `orchestration.socratic_revision` R, `orchestration.socratic_strategy` R, `orchestration.socratic_workflow` R, `pedagogy.solution_route_release` R | `core.problem` R, `core.solution` R | `routers.socratic.validate_workflow` |

## `admin/students`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/admin/students/{student_id}/knowledge-gaps` | Admin key | `pedagogy.knowledge_gap` R | — | `routers.step_runtime.admin_student_gaps` |

## `admin/taxonomy`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/admin/taxonomy/{kind}` | Admin key | `knowledge.concept` R, `knowledge.entity_alias` R, `knowledge.misconception` R, `knowledge.skill` RU, `knowledge.technique` R | — | `routers.admin_taxonomy.list_entities` |
| `GET /v1/admin/taxonomy/{kind}/{code}` | Admin key | `knowledge.concept` R, `knowledge.misconception` R, `knowledge.problem_concept` R, `knowledge.technique` R, `studio.video_render_job` R, `visual.animation_template` R, `visual.control_template` R, `visual.icon_token` R, `visual.interaction_instance` R, `visual.interaction_instance_concept` R, `visual.interaction_instance_misconception` R, `visual.interaction_instance_skill` R, `visual.interaction_instance_technique` R, `visual.interaction_template` R, `visual.interaction_template_version` R, `visual.scene_spec` R | `knowledge.entity_alias` R | `routers.admin_taxonomy.get_entity` |
| `PATCH /v1/admin/taxonomy/{kind}/{code}` | Admin key | `audit.action_log` C, `knowledge.concept` U, `knowledge.misconception` U, `knowledge.technique` U | `knowledge.entity_alias` R | `routers.admin_taxonomy.update_entity` |
| `GET /v1/admin/taxonomy/{kind}/{code}/aliases` | Admin key | `knowledge.entity_alias` R, `knowledge.theorem` R, `studio.scene_research_job` R, `studio.video_render_job` R | — | `routers.admin_taxonomy.list_aliases` |
| `POST /v1/admin/taxonomy/{kind}/{code}/aliases` | Admin key | `audit.action_log` C, `knowledge.entity_alias` C | — | `routers.admin_taxonomy.add_alias` |
| `DELETE /v1/admin/taxonomy/{kind}/{code}/aliases/{alias_id}` | Admin key | `audit.action_log` C, `knowledge.entity_alias` D | — | `routers.admin_taxonomy.remove_alias` |
| `POST /v1/admin/taxonomy/{kind}/{code}/deactivate` | Admin key | `audit.action_log` C, `knowledge.concept` U, `knowledge.misconception` U, `knowledge.technique` U, `pedagogy.micro_course` R, `pedagogy.micro_course_release` R, `pedagogy.micro_course_target` R | — | `routers.admin_taxonomy.deactivate_entity` |
| `POST /v1/admin/taxonomy/{kind}/{code}/reactivate` | Admin key | `audit.action_log` C, `knowledge.concept` U, `knowledge.misconception` U, `knowledge.technique` U | — | `routers.admin_taxonomy.reactivate_entity` |

## `admin/textbooks`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/admin/textbooks/coverage` | Admin key | `ingest.content_package` R, `ingest.import_conflict` R, `ingest.package_file` R, `pedagogy.chapter_section` R, `pedagogy.problem_enrichment` R, `pedagogy.problem_source_ref` R, `pedagogy.solution_part` R, `pedagogy.solution_source_ref` R, `pedagogy.solution_step_dependency` R, `pedagogy.solution_step_technique` R, `pedagogy.taxonomy_edge` R, `pedagogy.taxonomy_node` R, `search.representation` R | `pedagogy.diagram` R, `pedagogy.learning_item` R, `pedagogy.learning_item_step_anchor` R, `pedagogy.solution_step` R, `search.chunk` R, `search.embedding` R | `routers.admin_textbooks.coverage` |
| `GET /v1/admin/textbooks/diagrams/{source_diagram_id}/image` | Admin key | `pedagogy.diagram` R, `pedagogy.problem_enrichment` R, `pedagogy.problem_source_ref` R | — | `routers.admin_textbooks.diagram_image` |
| `GET /v1/admin/textbooks/learning-items` | Admin key | `pedagogy.learning_item` R | `core.problem` R, `pedagogy.problem_source_ref` R | `routers.admin_textbooks.learning_items` |
| `GET /v1/admin/textbooks/problems` | Admin key | `pedagogy.learning_item` R, `pedagogy.problem_enrichment` R, `pedagogy.problem_source_ref` R, `pedagogy.solution_source_ref` R, `pedagogy.solution_step` R, `pedagogy.taxonomy_node` R, `search.representation` R | `core.problem` R, `pedagogy.diagram` R, `search.chunk` R, `search.embedding` R | `routers.admin_textbooks.problems` |
| `GET /v1/admin/textbooks/problems/{code}` | Admin key | `core.solution` R, `ingest.content_package` R, `pedagogy.chapter_section` R, `pedagogy.diagram` R, `pedagogy.learning_item` R, `pedagogy.learning_item_step_anchor` R, `pedagogy.problem_enrichment` R, `pedagogy.problem_source_ref` R, `pedagogy.solution_part` R, `pedagogy.solution_source_ref` R, `pedagogy.solution_step` R, `pedagogy.solution_step_dependency` R, `pedagogy.taxonomy_node` R, `search.representation` R | `core.problem` R, `search.chunk` R, `search.embedding` R | `routers.admin_textbooks.problem` |
| `GET /v1/admin/textbooks/taxonomy` | Admin key | `pedagogy.taxonomy_edge` R, `pedagogy.taxonomy_node` R | `ingest.content_package` R, `pedagogy.problem_enrichment` R, `pedagogy.solution_step` R | `routers.admin_textbooks.taxonomy` |
| `GET /v1/admin/textbooks/taxonomy/{node_id}` | Admin key | `pedagogy.taxonomy_edge` R, `pedagogy.taxonomy_node` R | `core.problem` R, `pedagogy.problem_enrichment` R, `pedagogy.problem_source_ref` R | `routers.admin_textbooks.taxonomy_node` |

## `admin/theorems`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/admin/theorems` | Admin key | `knowledge.theorem` R | — | `routers.theorems.list_admin_theorems` |
| `POST /v1/admin/theorems` | Admin key | `audit.action_log` C, `knowledge.theorem` C | — | `routers.theorems.create_admin_theorem` |
| `GET /v1/admin/theorems/search` | Admin key | `knowledge.theorem` R | — | `routers.theorems.search_admin_theorems` |
| `POST /v1/admin/theorems/sources/{theorem_source_id}/approve` | Admin key | `audit.action_log` C, `knowledge.theorem_source` U | — | `routers.theorems.approve_theorem_source` |
| `GET /v1/admin/theorems/{slug}` | Admin key | `knowledge.theorem` R, `knowledge.theorem_asset` R, `knowledge.theorem_source` R, `knowledge.theorem_taxonomy_link` R | `pedagogy.taxonomy_node` R, `visual.asset` R | `routers.theorems.get_admin_theorem` |
| `PATCH /v1/admin/theorems/{slug}` | Admin key | `audit.action_log` C, `knowledge.theorem` U | `knowledge.theorem_asset` R, `knowledge.theorem_source` R, `knowledge.theorem_taxonomy_link` R, `pedagogy.taxonomy_node` R, `visual.asset` R | `routers.theorems.update_admin_theorem` |
| `POST /v1/admin/theorems/{slug}/approve` | Admin key | `audit.action_log` C, `knowledge.theorem` U | — | `routers.theorems.approve_admin_theorem` |
| `POST /v1/admin/theorems/{slug}/assets` | Admin key | `knowledge.theorem_asset` CU, `visual.asset` R | `knowledge.theorem` R, `knowledge.theorem_source` R, `knowledge.theorem_taxonomy_link` R, `pedagogy.taxonomy_node` R | `routers.theorems.create_theorem_asset` |
| `GET /v1/admin/theorems/{slug}/prerequisites` | Admin key | `knowledge.theorem` R, `knowledge.theorem_relation` R | `knowledge.theorem_asset` R, `knowledge.theorem_source` R, `knowledge.theorem_taxonomy_link` R, `pedagogy.taxonomy_node` R, `visual.asset` R | `routers.theorems.get_theorem_prerequisites_admin` |
| `POST /v1/admin/theorems/{slug}/reject` | Admin key | `audit.action_log` C, `knowledge.theorem` U | — | `routers.theorems.reject_admin_theorem` |
| `GET /v1/admin/theorems/{slug}/relations` | Admin key | `knowledge.theorem` R, `knowledge.theorem_relation` R | `knowledge.theorem_asset` R, `knowledge.theorem_source` R, `knowledge.theorem_taxonomy_link` R, `pedagogy.taxonomy_node` R, `visual.asset` R | `routers.theorems.get_theorem_relations` |
| `POST /v1/admin/theorems/{slug}/relations` | Admin key | `audit.action_log` C, `knowledge.theorem_relation` C | `knowledge.theorem` R, `knowledge.theorem_asset` R, `knowledge.theorem_source` R, `knowledge.theorem_taxonomy_link` R, `pedagogy.taxonomy_node` R, `visual.asset` R | `routers.theorems.create_theorem_relation` |
| `POST /v1/admin/theorems/{slug}/sources` | Admin key | `knowledge.theorem_source` C | `knowledge.theorem` R, `knowledge.theorem_asset` R, `knowledge.theorem_taxonomy_link` R, `pedagogy.taxonomy_node` R, `visual.asset` R | `routers.theorems.create_theorem_source` |
| `POST /v1/admin/theorems/{slug}/taxonomy-links` | Admin key | `audit.action_log` C, `knowledge.theorem_taxonomy_link` CU | `knowledge.theorem` R, `knowledge.theorem_asset` R, `knowledge.theorem_source` R, `pedagogy.taxonomy_node` R, `visual.asset` R | `routers.theorems.link_theorem_taxonomy` |
| `POST /v1/admin/theorems/{slug}/techniques` | Admin key | `audit.action_log` C, `knowledge.technique` R, `knowledge.technique_theorem` C | `knowledge.theorem` R, `knowledge.theorem_asset` R, `knowledge.theorem_source` R, `knowledge.theorem_taxonomy_link` R, `pedagogy.taxonomy_node` R, `visual.asset` R | `routers.theorems.link_theorem_technique` |

## `admin/tutoring-routes`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/admin/tutoring-routes` | Admin key | `pedagogy.route_step` R, `pedagogy.solution_route_release` R | `core.problem` R | `routers.tutoring_routes.drafts` |
| `POST /v1/admin/tutoring-routes/refresh-graph` | Admin key | `knowledge.misconception` R, `knowledge.misconception_similarity` R, `knowledge.misconception_taxonomy_link` R, `pedagogy.route_asset` R, `pedagogy.route_step` R, `pedagogy.solution_route_release` R, `pedagogy.solution_step_requirement` R, `pedagogy.taxonomy_node` R, `pedagogy.taxonomy_node_similarity` R, `pipeline.graph_projection` CU | `core.problem` R, `knowledge.route_asset_misconception_link` R, `pedagogy.route_asset_link` R | `routers.tutoring_routes.refresh_graph` |
| `GET /v1/admin/tutoring-routes/{release_id}` | Admin key | `core.solution` R, `pedagogy.route_asset` R, `pedagogy.route_step` R, `pedagogy.route_step_hint` R, `pedagogy.solution_route_release` R, `pedagogy.solution_step_instruction` R, `pedagogy.solution_step_requirement` R | `core.problem` R, `pedagogy.route_asset_link` R | `routers.tutoring_routes.preview` |
| `POST /v1/admin/tutoring-routes/{release_id}/edit` | Admin key | `core.solution` R, `ingest.content_package` R, `pedagogy.route_asset` CD, `pedagogy.route_step` CDRU, `pedagogy.route_step_hint` CD, `pedagogy.solution_route_release` RU, `pedagogy.solution_step_instruction` CD, `pedagogy.solution_step_requirement` CD, `pedagogy.taxonomy_node` C | `pedagogy.route_asset_link` C | `routers.tutoring_routes.edit` |
| `POST /v1/admin/tutoring-routes/{release_id}/publish` | Admin key | `pedagogy.route_asset` R, `pedagogy.route_step` R, `pedagogy.route_step_hint` R, `pedagogy.solution_route_release` RU, `pedagogy.solution_step_instruction` R, `pedagogy.solution_step_requirement` R | `pedagogy.route_asset_link` R | `routers.tutoring_routes.publish` |
| `POST /v1/admin/tutoring-routes/{release_id}/review` | Admin key | `pedagogy.route_asset` R, `pedagogy.route_step` R, `pedagogy.route_step_hint` R, `pedagogy.solution_route_release` RU, `pedagogy.solution_step_instruction` R, `pedagogy.solution_step_requirement` R, `pedagogy.taxonomy_node` R | `core.problem` R, `core.solution` R, `pedagogy.route_asset_link` R | `routers.tutoring_routes.review` |

## `analytics`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/analytics/weak-concepts` | anonymous* | `learner.concept_mastery` R | `knowledge.concept` R | `routers.v1.get_weak_concepts` |

## `artifacts`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/artifacts/bundles/{bundle_id}` | staff_or_student | `artifact_runtime.artifact_bundle` R | — | `routers.artifacts.get_bundle` |
| `GET /v1/artifacts/bundles/{bundle_id}/assets` | staff_or_student | `artifact_runtime.artifact_asset` R, `artifact_runtime.artifact_bundle` R | — | `routers.artifacts.assets` |
| `GET /v1/artifacts/bundles/{bundle_id}/assets/{asset_id}/content` | staff_or_student | `artifact_runtime.artifact_asset` R, `artifact_runtime.artifact_bundle` R | — | `routers.artifacts.asset_content` |
| `GET /v1/artifacts/bundles/{bundle_id}/frames` | staff_or_student | `artifact_runtime.artifact_asset` R, `artifact_runtime.artifact_bundle` R, `artifact_runtime.frame_sequence` R | — | `routers.artifacts.frames` |
| `GET /v1/artifacts/bundles/{bundle_id}/frames/{ordinal}/content` | staff_or_student | `artifact_runtime.artifact_asset` R, `artifact_runtime.artifact_bundle` R, `artifact_runtime.artifact_request` R, `artifact_runtime.frame_sequence` R | — | `routers.artifacts.frame_content` |
| `POST /v1/artifacts/bundles/{bundle_id}/index` | Admin key | `artifact_runtime.artifact_bundle` R, `artifact_runtime.artifact_embedding` CU | — | `routers.artifacts.index` |
| `POST /v1/artifacts/bundles/{bundle_id}/publish` | Admin key | `artifact_runtime.artifact_asset` R, `artifact_runtime.artifact_bundle` RU, `artifact_runtime.artifact_request` R, `artifact_runtime.validation_result` C | — | `routers.artifacts.publish` |
| `POST /v1/artifacts/bundles/{bundle_id}/similar` | staff_or_student | `artifact_runtime.artifact_bundle` R, `artifact_runtime.artifact_embedding` R, `artifact_runtime.artifact_search_tag` R | `artifact_runtime.artifact_asset` R | `routers.artifacts.similar` |
| `POST /v1/artifacts/bundles/{bundle_id}/validate` | staff_or_student | `artifact_runtime.artifact_asset` R, `artifact_runtime.artifact_bundle` R, `artifact_runtime.artifact_request` R, `artifact_runtime.validation_result` C | — | `routers.artifacts.validate_bundle` |
| `GET /v1/artifacts/embedding-profile` | staff_or_student | — | — | `routers.artifacts.embedding_profile` |
| `POST /v1/artifacts/geometry-preview` | staff_or_student | — | `artifact_runtime.artifact_bundle` R, `artifact_runtime.artifact_embedding` CU | `routers.artifacts.geometry_preview` |
| `POST /v1/artifacts/geometry-preview/content` | staff_or_student | — | `artifact_runtime.artifact_bundle` R, `artifact_runtime.artifact_embedding` CU | `routers.artifacts.geometry_preview_content` |
| `POST /v1/artifacts/preview` | staff_or_student | — | — | `routers.artifacts.preview` |
| `POST /v1/artifacts/preview/content` | staff_or_student | — | — | `routers.artifacts.preview_content` |
| `POST /v1/artifacts/requests` | staff_or_student | `artifact_runtime.artifact_request` C | `core.problem` R | `routers.artifacts.request_artifact` |
| `GET /v1/artifacts/requests/{request_id}` | staff_or_student | `artifact_runtime.artifact_request` R | — | `routers.artifacts.get_request` |
| `POST /v1/artifacts/requests/{request_id}/generate` | Admin key | `artifact_runtime.artifact_annotation` C, `artifact_runtime.artifact_asset` C, `artifact_runtime.artifact_bundle` C, `artifact_runtime.artifact_lineage` C, `artifact_runtime.artifact_metadata` C, `artifact_runtime.artifact_request` RU, `artifact_runtime.artifact_search_tag` C, `artifact_runtime.frame_sequence` C, `artifact_runtime.overlay_state` C, `artifact_runtime.validation_result` C | — | `routers.artifacts.generate` |
| `POST /v1/artifacts/search` | staff_or_student | `artifact_runtime.artifact_asset` R, `artifact_runtime.artifact_bundle` R, `artifact_runtime.artifact_search_tag` R | `artifact_runtime.artifact_embedding` R | `routers.artifacts.search` |
| `POST /v1/artifacts/search/semantic` | staff_or_student | `artifact_runtime.artifact_bundle` R, `artifact_runtime.artifact_embedding` R, `artifact_runtime.artifact_search_tag` R | `artifact_runtime.artifact_asset` R | `routers.artifacts.semantic_search` |
| `POST /v1/artifacts/validate` | staff_or_student | — | — | `routers.artifacts.validate` |

## `attempt-media`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/attempt-media/attempts/{aid}/steps` | staff_or_student | `attempt_media.approval` R, `attempt_media.step_candidate` R, `attempt_media.submission` R | `attempt_media.approved_step` R | `routers.attempt_media.approved_steps` |
| `GET /v1/attempt-media/attempts/{aid}/steps/{step_id}/assessment` | staff_or_student | `attempt_media.approval` R, `attempt_media.media_asset` R, `attempt_media.step_assessment` R, `attempt_media.submission` R | — | `routers.attempt_media.approved_assessment` |
| `GET /v1/attempt-media/attempts/{aid}/steps/{step_id}/visual` | staff_or_student | — | `attempt_media.approval` R, `attempt_media.step_assessment` R, `attempt_media.submission` R | `routers.attempt_media.approved_assessment` |
| `GET /v1/attempt-media/submissions` | staff_or_student | `attempt_media.submission` R | `core.problem` R | `routers.attempt_media.listing` |
| `POST /v1/attempt-media/submissions` | staff_or_student | `attempt_media.submission` C | `attempt_media.approval` R, `attempt_media.event` R, `attempt_media.evidence_region` R, `attempt_media.media_asset` R, `attempt_media.step_assessment` R, `attempt_media.step_candidate` R, `attempt_media.step_candidate_evidence` R, `core.problem` R | `routers.attempt_media.create` |
| `GET /v1/attempt-media/submissions/{sid}` | staff_or_student | `attempt_media.submission` R | `attempt_media.approval` R, `attempt_media.event` R, `attempt_media.evidence_region` R, `attempt_media.media_asset` R, `attempt_media.step_assessment` R, `attempt_media.step_candidate` R, `attempt_media.step_candidate_evidence` R | `routers.attempt_media.get` |
| `POST /v1/attempt-media/submissions/{sid}/analyse` | staff_or_student | `attempt_media.approval` R, `attempt_media.event` C, `attempt_media.step_assessment` C, `attempt_media.submission` U, `pedagogy.solution_step` R, `pedagogy.solution_step_dependency` R | `attempt_media.evidence_region` R, `attempt_media.media_asset` R, `attempt_media.step_candidate` R, `attempt_media.step_candidate_evidence` R, `core.problem` R, `pipeline.outbox_event` C | `routers.attempt_media.analyse` |
| `POST /v1/attempt-media/submissions/{sid}/approve` | staff_or_student | `attempt_media.approval` C, `attempt_media.event` C, `attempt_media.submission` U, `learner.attempt` C | `attempt_media.evidence_region` R, `attempt_media.media_asset` R, `attempt_media.step_assessment` R, `attempt_media.step_candidate` R, `attempt_media.step_candidate_evidence` R, `pipeline.outbox_event` C | `routers.attempt_media.approve` |
| `POST /v1/attempt-media/submissions/{sid}/assets` | staff_or_student | `attempt_media.event` C, `attempt_media.media_asset` C, `attempt_media.submission` U | `attempt_media.approval` R, `attempt_media.evidence_region` R, `attempt_media.step_assessment` R, `attempt_media.step_candidate` R, `attempt_media.step_candidate_evidence` R, `pipeline.outbox_event` C | `routers.attempt_media.upload` |
| `DELETE /v1/attempt-media/submissions/{sid}/assets/{aid}` | staff_or_student | `attempt_media.event` C, `attempt_media.media_asset` U, `attempt_media.submission` U | `pipeline.outbox_event` C | `routers.attempt_media.purge` |
| `GET /v1/attempt-media/submissions/{sid}/assets/{aid}/content` | staff_or_student | — | `attempt_media.media_asset` R, `attempt_media.submission` R | `routers.attempt_media.content` |
| `GET /v1/attempt-media/submissions/{sid}/assets/{aid}/pages/{page}` | staff_or_student | — | `attempt_media.media_asset` R, `attempt_media.submission` R | `routers.attempt_media.pdf_page` |
| `GET /v1/attempt-media/submissions/{sid}/events` | staff_or_student | `attempt_media.event` R | `attempt_media.submission` R | `routers.attempt_media.events` |
| `POST /v1/attempt-media/submissions/{sid}/override` | staff_or_student | `attempt_media.approval` R, `attempt_media.event` C, `attempt_media.step_assessment` C, `attempt_media.submission` U, `pedagogy.solution_step` R | `attempt_media.evidence_region` R, `attempt_media.media_asset` R, `attempt_media.step_candidate` R, `attempt_media.step_candidate_evidence` R, `pipeline.outbox_event` C | `routers.attempt_media.override` |
| `POST /v1/attempt-media/submissions/{sid}/process` | staff_or_student | `attempt_media.event` C, `attempt_media.evidence_region` C, `attempt_media.media_asset` C, `attempt_media.step_candidate` C, `attempt_media.step_candidate_evidence` C, `attempt_media.submission` U, `attempt_media.transcription_candidate` C | `attempt_media.approval` R, `attempt_media.step_assessment` R, `pipeline.outbox_event` C | `routers.attempt_media.process` |
| `GET /v1/attempt-media/submissions/{sid}/transcription` | staff_or_student | — | `attempt_media.approval` R, `attempt_media.event` R, `attempt_media.evidence_region` R, `attempt_media.media_asset` R, `attempt_media.step_assessment` R, `attempt_media.step_candidate` R, `attempt_media.step_candidate_evidence` R, `attempt_media.submission` R | `routers.attempt_media.transcription` |
| `PUT /v1/attempt-media/submissions/{sid}/transcription` | staff_or_student | `attempt_media.evidence_region` C, `attempt_media.step_candidate` C, `attempt_media.step_candidate_evidence` C, `attempt_media.submission` U, `attempt_media.transcription_candidate` C | `attempt_media.approval` R, `attempt_media.event` CR, `attempt_media.media_asset` R, `attempt_media.step_assessment` R, `pipeline.outbox_event` C | `routers.attempt_media.replace` |
| `POST /v1/attempt-media/submissions/{sid}/transcription/merge` | staff_or_student | `attempt_media.event` C, `attempt_media.evidence_region` C, `attempt_media.step_candidate` C, `attempt_media.step_candidate_evidence` C, `attempt_media.submission` U, `attempt_media.transcription_candidate` C | `attempt_media.approval` R, `attempt_media.media_asset` R, `attempt_media.step_assessment` R, `pipeline.outbox_event` C | `routers.attempt_media.merge` |
| `POST /v1/attempt-media/submissions/{sid}/transcription/split` | staff_or_student | `attempt_media.event` C, `attempt_media.evidence_region` C, `attempt_media.step_candidate` C, `attempt_media.step_candidate_evidence` C, `attempt_media.submission` U, `attempt_media.transcription_candidate` C | `attempt_media.approval` R, `attempt_media.media_asset` R, `attempt_media.step_assessment` R, `pipeline.outbox_event` C | `routers.attempt_media.split` |
| `PATCH /v1/attempt-media/submissions/{sid}/transcription/steps/{step_id}` | staff_or_student | `attempt_media.evidence_region` C, `attempt_media.step_candidate` C, `attempt_media.step_candidate_evidence` C, `attempt_media.submission` U, `attempt_media.transcription_candidate` C | `attempt_media.approval` R, `attempt_media.event` CR, `attempt_media.media_asset` R, `attempt_media.step_assessment` R, `pipeline.outbox_event` C | `routers.attempt_media.patch` |

## `attempts`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/attempts/{attempt_id}` | Learner JWT | `learner.attempt_step_state` R, `learner.solve_attempt` R, `pedagogy.gap_diagnosis` R, `pedagogy.knowledge_gap` R, `pedagogy.recovery_plan` R, `pedagogy.solution_part` R, `pedagogy.solution_step` R, `tutor.runtime_state` R | `core.problem` R, `pedagogy.solution_step_dependency` R | `routers.step_runtime.get_runtime` |
| `GET /v1/attempts/{attempt_id}/diagnoses` | Learner JWT | `pedagogy.gap_diagnosis` R, `pedagogy.knowledge_gap` R | `learner.solve_attempt` R | `routers.step_runtime.list_diagnoses` |
| `GET /v1/attempts/{attempt_id}/recovery-plans` | Learner JWT | `pedagogy.recovery_plan` R, `pedagogy.recovery_plan_item` R | `core.problem` R, `learner.solve_attempt` R, `pedagogy.learning_item` R, `pedagogy.solution_part` R, `pedagogy.solution_step` R, `pedagogy.taxonomy_node` R | `routers.step_runtime.list_recovery_plans` |
| `POST /v1/attempts/{attempt_id}/recovery-plans` | Learner JWT | `learner.attempt_step_state` U, `learner.event` C, `learner.idempotency_record` CR, `learner.solve_attempt` U, `pedagogy.gap_diagnosis` R, `pedagogy.knowledge_gap` R, `pedagogy.learning_item` R, `pedagogy.problem_enrichment` R, `pedagogy.recovery_plan` CRU, `pedagogy.recovery_plan_item` CRU, `pipeline.outbox_event` C, `tutor.runtime_state` RU | `core.problem` R, `pedagogy.solution_part` R, `pedagogy.solution_step` R, `pedagogy.taxonomy_node` R | `routers.step_runtime.create_recovery_plan` |
| `GET /v1/attempts/{attempt_id}/runtime` | Learner JWT | `learner.attempt_step_state` R, `learner.solve_attempt` R, `pedagogy.gap_diagnosis` R, `pedagogy.knowledge_gap` R, `pedagogy.recovery_plan` R, `pedagogy.solution_part` R, `pedagogy.solution_step` R, `tutor.runtime_state` R | `core.problem` R, `pedagogy.solution_step_dependency` R | `routers.step_runtime.get_runtime` |
| `POST /v1/attempts/{attempt_id}/steps/{step_id:path}/diagnose` | Learner JWT | `learner.attempt_step_state` R, `learner.event` C, `learner.solve_attempt` R, `pedagogy.gap_diagnosis` CRU, `pedagogy.knowledge_gap` CR, `pedagogy.learning_item` R, `pedagogy.solution_step` R, `pedagogy.solution_step_technique` R, `pedagogy.taxonomy_node` R, `pipeline.outbox_event` C, `tutor.runtime_state` R | `core.problem` R, `knowledge.concept` R, `knowledge.concept_relation` R, `pedagogy.solution_step_dependency` R | `routers.step_runtime.diagnose_step` |
| `POST /v1/attempts/{attempt_id}/steps/{step_id:path}/hint` | Learner JWT | `learner.attempt_step_state` U, `learner.event` C, `learner.idempotency_record` CR, `learner.solve_attempt` R, `pedagogy.solution_part` R, `pedagogy.solution_step` R, `pedagogy.step_hint` CR, `tutor.runtime_state` RU | `core.problem` R | `routers.step_runtime.request_hint` |
| `GET /v1/attempts/{attempt_id}/steps/{step_id:path}/hints` | Learner JWT | `learner.attempt_step_state` R, `learner.solve_attempt` R, `pedagogy.gap_diagnosis` R, `pedagogy.knowledge_gap` R, `pedagogy.recovery_plan` R, `pedagogy.solution_part` R, `pedagogy.solution_step` R, `pedagogy.step_hint` CR, `tutor.runtime_state` R | `core.problem` R, `pedagogy.solution_step_dependency` R | `routers.step_runtime.list_hints` |
| `POST /v1/attempts/{attempt_id}/steps/{step_id:path}/outcome` | Admin key | `learner.attempt` C, `learner.attempt_step_state` U, `learner.concept_mastery` CU, `learner.event` CR, `learner.idempotency_record` CR, `learner.solve_attempt` U, `pedagogy.gap_diagnosis` CR, `pedagogy.knowledge_gap` CRU, `pedagogy.solution_step` R, `pedagogy.solution_step_technique` R, `pedagogy.taxonomy_node` R, `pipeline.outbox_event` C, `quiz.paper` R, `quiz.question_concept` R, `quiz.question_technique` R, `quiz.response` R, `tutor.runtime_state` RU | `core.problem` R, `knowledge.concept` R, `knowledge.concept_relation` R, `knowledge.problem_concept` R, `knowledge.problem_technique` R, `learner.technique_mastery` CU, `pedagogy.learning_item` R, `pedagogy.solution_step_dependency` R | `routers.step_runtime.record_step_outcome` |
| `POST /v1/attempts/{attempt_id}/steps/{step_id:path}/responses` | Learner JWT | `learner.attempt` C, `learner.attempt_step_state` U, `learner.concept_mastery` CU, `learner.event` C, `learner.idempotency_record` CR, `learner.solve_attempt` U, `pedagogy.gap_diagnosis` CRU, `pedagogy.knowledge_gap` CRU, `pedagogy.solution_part` R, `pedagogy.solution_step` R, `pedagogy.solution_step_technique` R, `pedagogy.taxonomy_node` R, `pipeline.outbox_event` C, `quiz.paper` R, `quiz.question_concept` R, `quiz.question_technique` R, `quiz.response` R, `tutor.runtime_state` RU | `core.problem` R, `knowledge.concept` R, `knowledge.concept_relation` R, `knowledge.problem_concept` R, `knowledge.problem_technique` R, `learner.technique_mastery` CU, `pedagogy.learning_item` R, `pedagogy.solution_step_dependency` R | `routers.step_runtime.submit_step_response` |
| `POST /v1/attempts/{attempt_id}/submit` | Learner JWT | `learner.event` C, `learner.idempotency_record` CR, `learner.solve_attempt` U, `tutor.runtime_state` RU | — | `routers.step_runtime.submit_attempt` |

## `authoring`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `POST /v1/authoring/chat/sessions` | Admin key | `authoring.chat_message` R, `authoring.chat_session` CR, `authoring.plan_topic` R, `authoring.presentation_plan` R, `authoring.proposed_patch` R | — | `routers.fluid.chat_create` |
| `GET /v1/authoring/chat/sessions/{chat_id}` | Admin key | `authoring.chat_message` R, `authoring.chat_session` R, `authoring.proposed_patch` R | — | `routers.fluid.chat_get` |
| `POST /v1/authoring/chat/sessions/{chat_id}/messages` | Admin key | `authoring.chat_message` C, `authoring.chat_session` R, `authoring.plan_topic` R, `authoring.presentation_plan` R, `authoring.proposed_patch` C | — | `routers.fluid.chat_message` |
| `GET /v1/authoring/chat/sessions/{chat_id}/proposed-patches` | Admin key | `authoring.proposed_patch` R | — | `routers.fluid.chat_patches` |
| `POST /v1/authoring/chat/sessions/{chat_id}/proposed-patches/{patch_id}/apply` | Admin key | `authoring.chat_message` C, `authoring.chat_session` R, `authoring.plan_topic` CD, `authoring.presentation_plan` CU, `authoring.proposed_patch` CU | — | `routers.fluid.chat_patch_decide` |
| `GET /v1/authoring/presentation-plans` | Admin key | `authoring.plan_topic` R, `authoring.presentation_plan` R | — | `routers.fluid.plans` |
| `POST /v1/authoring/presentation-plans` | Admin key | `authoring.plan_topic` C, `authoring.presentation_plan` C | — | `routers.fluid.create_plan` |
| `GET /v1/authoring/presentation-plans/{plan_id}` | Admin key | `authoring.plan_topic` R, `authoring.presentation_plan` R | — | `routers.fluid.plan` |
| `POST /v1/authoring/presentation-plans/{plan_id}/approve` | Admin key | `authoring.plan_topic` R, `authoring.presentation_plan` U | — | `routers.fluid.plan_approve` |
| `POST /v1/authoring/presentation-plans/{plan_id}/new-version` | Admin key | `authoring.plan_topic` C, `authoring.presentation_plan` C | — | `routers.fluid.plan_new_version` |
| `POST /v1/authoring/presentation-plans/{plan_id}/publish` | Admin key | `authoring.plan_topic` R, `authoring.presentation_plan` U | — | `routers.fluid.plan_publish` |
| `PATCH /v1/authoring/presentation-plans/{plan_id}/timing` | Admin key | `authoring.plan_topic` CD, `authoring.presentation_plan` U | — | `routers.fluid.plan_timing` |
| `PUT /v1/authoring/presentation-plans/{plan_id}/topics` | Admin key | `authoring.plan_topic` CD, `authoring.presentation_plan` U | — | `routers.fluid.plan_topics` |
| `POST /v1/authoring/presentation-plans/{plan_id}/validate` | Admin key | `authoring.plan_topic` R, `authoring.presentation_plan` R | — | `routers.fluid.plan_validate` |

## `competitions`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/competitions` | anonymous* | `core.competition` R | — | `routers.v1.get_competitions` |

## `concepts`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/concepts` | anonymous* | `knowledge.concept` R, `knowledge.entity_alias` R | — | `routers.v1.get_concepts` |
| `GET /v1/concepts/{slug}/neighbors` | anonymous* | `knowledge.concept` R, `knowledge.concept_relation` R | — | `routers.v1.get_concept_neighbors` |
| `GET /v1/concepts/{slug}/problems` | anonymous* | `core.problem` R, `knowledge.concept` R, `knowledge.concept_relation` R, `knowledge.problem_concept` R | `core.competition` R, `core.competition_edition` R, `core.paper` R | `routers.v1.get_concept_problems` |

## `corpus`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/corpus/coverage` | anonymous* | `core.competition` R, `core.problem` R, `knowledge.problem_concept` R, `knowledge.problem_technique` R | `core.competition_edition` R, `core.paper` R | `routers.v1.get_corpus_coverage` |

## `geometry-scenes`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `POST /v1/geometry-scenes` | authorize_math_status, geometry_owner, get_geometry_repository | `geometry_scene.receipts` CR, `geometry_scene.runs` C, `geometry_scene.scenes` C, `geometry_scene.versions` C | — | `geometry_scene.api.create` |
| `GET /v1/geometry-scenes/debug/runs` | authorize_math_status, staff, get_geometry_repository | `geometry_scene.runs` R | — | `routers.geometry_scenes.list_runs` |
| `GET /v1/geometry-scenes/debug/runs/{run_id}` | authorize_math_status, staff, get_geometry_repository | `geometry_scene.runs` R | — | `routers.geometry_scenes.read_run` |
| `POST /v1/geometry-scenes/debug/runs/{run_id}/review` | authorize_math_status, staff, get_geometry_repository | `geometry_scene.runs` U | — | `routers.geometry_scenes.review_run` |
| `POST /v1/geometry-scenes/interpret` | geometry_owner, get_geometry_repository, staff_or_student | `geometry_scene.receipts` CR, `geometry_scene.runs` C, `geometry_scene.scenes` CRU, `geometry_scene.versions` C, `learner.attempt_step_state` R, `learner.solve_attempt` R, `pedagogy.gap_diagnosis` R, `pedagogy.knowledge_gap` R, `pedagogy.recovery_plan` R, `pedagogy.solution_part` R, `pedagogy.solution_step` R, `pedagogy.solution_step_dependency` R, `tutor.runtime_state` R | `core.problem` R | `routers.geometry_interpretation.interpret_scene` |
| `GET /v1/geometry-scenes/{scene_id}` | authorize_math_status, geometry_owner, get_geometry_repository | `geometry_scene.scenes` R, `geometry_scene.versions` R | — | `geometry_scene.api.current` |
| `POST /v1/geometry-scenes/{scene_id}/deltas` | authorize_math_status, geometry_owner, get_geometry_repository | `geometry_scene.receipts` CR, `geometry_scene.scenes` RU, `geometry_scene.versions` C | — | `geometry_scene.api.delta` |
| `GET /v1/geometry-scenes/{scene_id}/frames` | authorize_math_status, geometry_owner, get_geometry_repository | `geometry_scene.scenes` R, `geometry_scene.versions` R | — | `geometry_scene.api.frames` |
| `GET /v1/geometry-scenes/{scene_id}/versions/{version}` | authorize_math_status, geometry_owner, get_geometry_repository | `geometry_scene.scenes` R, `geometry_scene.versions` R | — | `geometry_scene.api.read` |
| `GET /v1/geometry-scenes/{scene_id}/versions/{version}/render` | authorize_math_status, geometry_owner, get_geometry_repository | `geometry_scene.scenes` R, `geometry_scene.versions` R | — | `geometry_scene.api.render_version` |
| `POST /v1/geometry-scenes/{scene_id}/versions/{version}/validate` | authorize_math_status, geometry_owner, get_geometry_repository | `geometry_scene.versions` R | — | `geometry_scene.api.validate` |

## `health`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /health` | anonymous* | — | — | `socratic_app.health` |
| `GET /health/neo4j` | anonymous* | — | — | `main.health_neo4j` |
| `GET /health/postgres` | anonymous* | — | — | `main.health_postgres` |

## `instructor`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `POST /v1/instructor/live/{sid}/commands` | staff_actor | `activity.definition` CR, `activity.instance` CU, `live.command_receipt` CR, `live.recommendation` CU, `visual.widget_spec` CRU | `activity.response` CRU, `core.problem` R, `core.problem_image` R, `live.participant` RU, `live.session` RU, `live.session_event` CR, `live.takeover` CRU, `live.topic_run` U, `pipeline.outbox_event` C, `visual.widget_state` CU | `routers.live.instructor_nl` |
| `GET /v1/instructor/live/{sid}/handoff` | staff_actor | `activity.definition` R, `activity.instance` R, `activity.response` R, `live.session_event` R, `live.takeover` R | `live.session` R | `routers.live.handoff` |
| `POST /v1/instructor/live/{sid}/overrides` | staff_actor | `live.participant` U, `live.recommendation` U, `live.session` U, `live.takeover` CU | `activity.definition` CR, `activity.instance` CRU, `activity.response` CRU, `core.problem` R, `core.problem_image` R, `live.command_receipt` CR, `live.session_event` CR, `live.topic_run` U, `pipeline.outbox_event` C, `visual.widget_spec` CRU, `visual.widget_state` CU | `routers.live.override` |
| `GET /v1/instructor/live/{sid}/recommendations` | staff_actor | `live.recommendation` R | — | `routers.live.recommendations` |
| `POST /v1/instructor/live/{sid}/recommendations/{rid}` | staff_actor | `activity.definition` CR, `activity.instance` CU, `live.command_receipt` CR, `live.recommendation` U, `live.session` U, `visual.asset` R, `visual.widget_spec` CRU | `activity.response` CRU, `core.problem` R, `core.problem_image` R, `live.participant` RU, `live.session_event` CR, `live.takeover` CRU, `live.topic_run` U, `pipeline.outbox_event` C, `visual.widget_state` CU | `routers.live.decide` |

## `learner`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/learner/agent-sessions` | Learner JWT | `learner.agent_session_link` R | `learner.student_profile` R | `routers.agent_sessions.my_agent_sessions` |
| `POST /v1/learner/agent-sessions` | Learner JWT | `learner.agent_session_link` CU | — | `routers.agent_sessions.link_agent_session` |
| `GET /v1/learner/agent-sessions/{agent_session_id}/transcript` | Learner JWT | `learner.agent_session_link` R | `learner.student_profile` R | `routers.agent_sessions.my_agent_transcript` |
| `GET /v1/learner/attempts` | Learner JWT | `learner.attempt` R | `core.competition` R, `core.competition_edition` R, `core.paper` R, `core.problem` R | `routers.learner.get_attempts` |
| `POST /v1/learner/attempts` | Learner JWT | `knowledge.problem_concept` R, `knowledge.problem_technique` R, `learner.attempt` C, `learner.concept_mastery` CU, `quiz.paper` R, `quiz.question_concept` R, `quiz.question_technique` R, `quiz.response` R | `core.problem` R, `learner.technique_mastery` CU | `routers.learner.submit_attempt` |
| `POST /v1/learner/login` | anonymous* | `learner.student_profile` RU | — | `routers.learner.login` |
| `GET /v1/learner/mastery` | Learner JWT | `learner.concept_mastery` R | `knowledge.concept` R, `knowledge.technique` R, `learner.technique_mastery` R | `routers.learner.get_mastery_summary` |
| `GET /v1/learner/mastery/improvement-plan` | Learner JWT | `knowledge.concept_relation` R, `knowledge.problem_concept` R, `learner.concept_mastery` R | `core.competition` R, `core.competition_edition` R, `core.paper` R, `core.problem` R, `knowledge.concept` R, `knowledge.technique` R, `learner.technique_mastery` R | `routers.learner.get_improvement_plan` |
| `GET /v1/learner/me` | Learner JWT | `learner.student_profile` R | — | `routers.learner.get_me` |
| `GET /v1/learner/practice-progress` | Learner JWT | `knowledge.problem_technique` R, `learner.attempt` R, `pedagogy.solution_step` R, `pedagogy.solution_step_technique` R, `pedagogy.taxonomy_node` R | `core.competition` R, `core.competition_edition` R, `core.paper` R, `core.problem` R, `knowledge.concept` R, `knowledge.problem_concept` R, `knowledge.technique` R | `routers.learner.get_practice_progress` |
| `POST /v1/learner/register` | anonymous* | `learner.student_profile` C | — | `routers.learner.register` |

## `live`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/live/sessions` | staff_actor | `live.session` R | — | `routers.live.list_sessions` |
| `POST /v1/live/sessions` | staff_actor | `authoring.plan_topic` R, `authoring.presentation_plan` R, `live.participant` C, `live.session` C, `live.session_event` C, `live.topic_run` C | `pipeline.outbox_event` C | `routers.live.create_session` |
| `POST /v1/live/sessions/join` | live_actor | `learner.student_profile` R, `live.participant` CU, `live.session` U, `live.session_event` C | `pipeline.outbox_event` C | `routers.live.join` |
| `POST /v1/live/sessions/{sid}/activities` | staff_actor | `activity.definition` CR, `activity.instance` CU, `live.session` U | `activity.response` CRU, `core.problem` R, `core.problem_image` R, `live.command_receipt` CR, `live.participant` RU, `live.recommendation` CU, `live.session_event` CR, `live.takeover` CRU, `live.topic_run` U, `pipeline.outbox_event` C, `visual.widget_spec` CRU, `visual.widget_state` CU | `routers.live.open_activity` |
| `GET /v1/live/sessions/{sid}/activities/{aid}/aggregate` | live_actor | `activity.definition` R, `activity.instance` R, `activity.response` R | — | `routers.live.activity_aggregate` |
| `POST /v1/live/sessions/{sid}/activities/{aid}/close` | staff_actor | `activity.definition` R, `activity.instance` U, `activity.response` R, `live.recommendation` C, `live.session` U | `core.problem` R, `core.problem_image` R, `live.command_receipt` CR, `live.participant` RU, `live.session_event` CR, `live.takeover` CRU, `live.topic_run` U, `pipeline.outbox_event` C, `visual.widget_spec` CRU, `visual.widget_state` CU | `routers.live.close_activity` |
| `POST /v1/live/sessions/{sid}/activities/{aid}/responses` | live_actor | `activity.definition` R, `activity.response` CU | `activity.instance` CRU, `core.problem` R, `core.problem_image` R, `live.command_receipt` CR, `live.participant` RU, `live.recommendation` CU, `live.session` RU, `live.session_event` CR, `live.takeover` CRU, `live.topic_run` U, `pipeline.outbox_event` C, `visual.widget_spec` CRU, `visual.widget_state` CU | `routers.live.respond` |
| `POST /v1/live/sessions/{sid}/activities/{aid}/reveal` | staff_actor | `activity.definition` R, `activity.instance` U, `activity.response` R, `live.session` U, `visual.widget_spec` C, `visual.widget_state` CU | `core.problem` R, `core.problem_image` R, `live.command_receipt` CR, `live.participant` RU, `live.recommendation` CU, `live.session_event` CR, `live.takeover` CRU, `live.topic_run` U, `pipeline.outbox_event` C | `routers.live.reveal_activity` |
| `POST /v1/live/sessions/{sid}/commands` | live_actor | `activity.definition` CR, `activity.instance` CU, `activity.response` CU, `live.participant` U, `live.session` U, `visual.widget_spec` CRU | `core.problem` R, `core.problem_image` R, `live.command_receipt` CR, `live.recommendation` CU, `live.session_event` CR, `live.takeover` CRU, `live.topic_run` U, `pipeline.outbox_event` C, `visual.widget_state` CU | `routers.live.command` |
| `GET /v1/live/sessions/{sid}/events` | live_actor | `live.participant` R, `live.session_event` R | `live.session` R | `routers.live.events` |
| `POST /v1/live/sessions/{sid}/pause` | staff_actor | `live.session` U | `activity.definition` CR, `activity.instance` CRU, `activity.response` CRU, `core.problem` R, `core.problem_image` R, `live.command_receipt` CR, `live.participant` RU, `live.recommendation` CU, `live.session_event` CR, `live.takeover` CRU, `live.topic_run` U, `pipeline.outbox_event` C, `visual.widget_spec` CRU, `visual.widget_state` CU | `routers.live.pause` |
| `POST /v1/live/sessions/{sid}/resume` | staff_actor | `live.session` U | `activity.definition` CR, `activity.instance` CRU, `activity.response` CRU, `core.problem` R, `core.problem_image` R, `live.command_receipt` CR, `live.participant` RU, `live.recommendation` CU, `live.session_event` CR, `live.takeover` CRU, `live.topic_run` U, `pipeline.outbox_event` C, `visual.widget_spec` CRU, `visual.widget_state` CU | `routers.live.resume` |
| `GET /v1/live/sessions/{sid}/state` | live_actor | `activity.definition` R, `activity.instance` R, `activity.response` R, `live.participant` R, `live.session` R, `live.takeover` R, `live.topic_run` R | `live.recommendation` R | `routers.live.state` |
| `GET /v1/live/sessions/{sid}/time` | staff_actor | `live.session` R | — | `routers.live.time_state` |
| `POST /v1/live/sessions/{sid}/transition` | staff_actor | `live.session` U | `activity.definition` CR, `activity.instance` CRU, `activity.response` CRU, `core.problem` R, `core.problem_image` R, `live.command_receipt` CR, `live.participant` RU, `live.recommendation` CU, `live.session_event` CR, `live.takeover` CRU, `live.topic_run` U, `pipeline.outbox_event` C, `visual.widget_spec` CRU, `visual.widget_state` CU | `routers.live.transition` |
| `POST /v1/live/sessions/{sid}/widgets` | staff_actor | `visual.widget_spec` CRU, `visual.widget_state` CU | `activity.definition` CR, `activity.instance` CRU, `activity.response` CRU, `core.problem` R, `core.problem_image` R, `live.command_receipt` CR, `live.participant` RU, `live.recommendation` CU, `live.session` RU, `live.session_event` CR, `live.takeover` CRU, `live.topic_run` U, `pipeline.outbox_event` C | `routers.live.show_widget` |
| `DELETE /v1/live/sessions/{sid}/widgets/{wid}` | staff_actor | `live.session` U, `visual.widget_state` U | `activity.definition` CR, `activity.instance` CRU, `activity.response` CRU, `core.problem` R, `core.problem_image` R, `live.command_receipt` CR, `live.participant` RU, `live.recommendation` CU, `live.session_event` CR, `live.takeover` CRU, `live.topic_run` U, `pipeline.outbox_event` C, `visual.widget_spec` CRU | `routers.live.hide_widget` |
| `PATCH /v1/live/sessions/{sid}/widgets/{wid}/state` | staff_actor | `live.session` U, `visual.widget_state` U | `activity.definition` CR, `activity.instance` CRU, `activity.response` CRU, `core.problem` R, `core.problem_image` R, `live.command_receipt` CR, `live.participant` RU, `live.recommendation` CU, `live.session_event` CR, `live.takeover` CRU, `live.topic_run` U, `pipeline.outbox_event` C, `visual.widget_spec` CRU | `routers.live.widget_state` |

## `micro-courses`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/micro-courses` | anonymous* | `knowledge.concept` R, `knowledge.theorem` R, `pedagogy.micro_course` R, `pedagogy.micro_course_release` R, `pedagogy.micro_course_target` R | `knowledge.skill` R, `knowledge.technique` R, `pedagogy.micro_course_state` R | `routers.micro_courses.list_student_courses` |
| `GET /v1/micro-courses/enrollments/{enrollment_id}` | Learner JWT | `activity.definition` R, `learner.micro_course_enrollment` R, `learner.micro_course_state_event` R, `pedagogy.state_qa_context` R, `pedagogy.video_asset` R, `tutor.micro_course_runtime` R | `pedagogy.learning_item` R, `pedagogy.micro_course` R, `pedagogy.micro_course_module` R, `pedagogy.micro_course_release` R, `pedagogy.micro_course_state` R, `pedagogy.micro_course_state_activity` R, `pedagogy.micro_course_state_asset` R, `pedagogy.micro_course_state_interaction` R, `pedagogy.micro_course_state_learning_item` R, `pedagogy.micro_course_transition` R, `pedagogy.video_transcript` R, `pedagogy.video_transcript_segment` R, `visual.asset` R, `visual.interaction_instance` R, `visual.interaction_template` R, `visual.interaction_template_version` R, `visual.scene_spec` R | `routers.micro_courses.get_enrollment` |
| `POST /v1/micro-courses/enrollments/{enrollment_id}/activity-responses` | Learner JWT | `learner.micro_course_enrollment` R, `learner.micro_course_state_event` C, `pedagogy.micro_course_state` R, `pedagogy.micro_course_state_activity` R | `activity.definition` R | `routers.micro_courses.submit_activity_response_endpoint` |
| `POST /v1/micro-courses/enrollments/{enrollment_id}/advance` | Learner JWT | `learner.micro_course_enrollment` RU, `learner.micro_course_state_event` C, `pedagogy.state_qa_context` R, `pedagogy.video_asset` R, `pedagogy.video_transcript` R, `pedagogy.video_transcript_segment` R, `tutor.micro_course_runtime` RU | `activity.definition` R, `pedagogy.learning_item` R, `pedagogy.micro_course` R, `pedagogy.micro_course_module` R, `pedagogy.micro_course_release` R, `pedagogy.micro_course_state` R, `pedagogy.micro_course_state_activity` R, `pedagogy.micro_course_state_asset` R, `pedagogy.micro_course_state_interaction` R, `pedagogy.micro_course_state_learning_item` R, `pedagogy.micro_course_transition` R, `visual.asset` R, `visual.interaction_instance` R, `visual.interaction_template` R, `visual.interaction_template_version` R, `visual.scene_spec` R | `routers.micro_courses.advance_enrollment` |
| `POST /v1/micro-courses/enrollments/{enrollment_id}/interaction-events` | Learner JWT | `learner.interaction_event` C, `learner.micro_course_enrollment` R, `pedagogy.micro_course_state` R, `pipeline.outbox_event` C, `tutor.micro_course_runtime` R, `visual.interaction_instance` R | — | `routers.micro_courses.record_interaction_event_endpoint` |
| `POST /v1/micro-courses/enrollments/{enrollment_id}/item-help` | Learner JWT | `audit.action_log` C, `learner.interaction_event` R, `learner.micro_course_enrollment` R, `learner.micro_course_state_event` C, `pedagogy.learning_item` R, `pedagogy.micro_course_release` R, `pedagogy.micro_course_state` R, `pedagogy.micro_course_state_activity` R, `pedagogy.micro_course_state_asset` R, `pedagogy.micro_course_state_interaction` R, `pedagogy.micro_course_state_learning_item` R, `pedagogy.micro_course_target` R, `pedagogy.state_qa_context` R, `pedagogy.video_asset` R, `pedagogy.video_transcript` R, `pedagogy.video_transcript_segment` R, `tutor.micro_course_runtime` R | `activity.definition` R, `knowledge.concept` R, `knowledge.skill` R, `knowledge.technique` R, `visual.asset` R, `visual.interaction_instance` R | `routers.micro_courses.get_item_help` |
| `POST /v1/micro-courses/enrollments/{enrollment_id}/responses` | Learner JWT | `pedagogy.learning_item` R, `pedagogy.micro_course_state` R, `pedagogy.micro_course_state_learning_item` R, `tutor.micro_course_runtime` R | `learner.micro_course_enrollment` R, `learner.micro_course_state_event` C | `routers.micro_courses.submit_response` |
| `GET /v1/micro-courses/{canonical_code}` | anonymous* | `activity.definition` R, `pedagogy.state_qa_context` R, `pedagogy.video_asset` R, `pedagogy.video_transcript` R, `pedagogy.video_transcript_segment` R, `visual.asset` R | `knowledge.concept` R, `knowledge.skill` R, `knowledge.technique` R, `knowledge.theorem` R, `pedagogy.learning_item` R, `pedagogy.micro_course` R, `pedagogy.micro_course_module` R, `pedagogy.micro_course_release` R, `pedagogy.micro_course_state` R, `pedagogy.micro_course_state_activity` R, `pedagogy.micro_course_state_asset` R, `pedagogy.micro_course_state_interaction` R, `pedagogy.micro_course_state_learning_item` R, `pedagogy.micro_course_target` R, `pedagogy.micro_course_transition` R, `visual.interaction_instance` R, `visual.interaction_template` R, `visual.interaction_template_version` R, `visual.scene_spec` R | `routers.micro_courses.get_student_course` |
| `GET /v1/micro-courses/{canonical_code}/assets/{asset_id}/content` | anonymous* | `pedagogy.micro_course` R, `pedagogy.micro_course_release` R, `pedagogy.micro_course_state_asset` R, `visual.asset` R | `pedagogy.micro_course_state` R, `pedagogy.micro_course_state_interaction` R, `visual.interaction_instance` R, `visual.scene_spec` R | `routers.micro_courses.get_student_asset` |
| `POST /v1/micro-courses/{canonical_code}/enroll` | Learner JWT | `activity.definition` R, `learner.micro_course_enrollment` CR, `learner.micro_course_state_event` C, `learner.student_profile` R, `pedagogy.state_qa_context` R, `pedagogy.video_asset` R, `pedagogy.video_transcript` R, `pedagogy.video_transcript_segment` R, `tutor.micro_course_runtime` CR | `pedagogy.learning_item` R, `pedagogy.micro_course` R, `pedagogy.micro_course_module` R, `pedagogy.micro_course_release` R, `pedagogy.micro_course_state` R, `pedagogy.micro_course_state_activity` R, `pedagogy.micro_course_state_asset` R, `pedagogy.micro_course_state_interaction` R, `pedagogy.micro_course_state_learning_item` R, `pedagogy.micro_course_transition` R, `visual.asset` R, `visual.interaction_instance` R, `visual.interaction_template` R, `visual.interaction_template_version` R, `visual.scene_spec` R | `routers.micro_courses.enroll_in_course` |

## `notifications`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/notifications/me` | Learner JWT | `notification.event` R | — | `routers.notifications.list_my_notifications` |
| `POST /v1/notifications/{notification_id}/read` | Learner JWT | `notification.event` U | — | `routers.notifications.mark_notification_read` |

## `problem-images`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/problem-images/{image_id}` | anonymous* | `core.problem_image` R, `pedagogy.diagram` R | — | `routers.step_runtime.get_problem_image` |

## `problems`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/problems` | anonymous* | `core.competition` R, `core.problem` R, `knowledge.problem_concept` R | `core.competition_edition` R, `core.paper` R, `knowledge.concept` R | `routers.v1.get_problems` |
| `GET /v1/problems/by-code/{canonical_code}` | anonymous* | `core.competition` R, `core.problem` R, `core.problem_image` R, `core.solution` R, `knowledge.problem_concept` R, `knowledge.problem_technique` R, `pedagogy.diagram` R | `core.competition_edition` R, `core.paper` R, `knowledge.concept` R, `knowledge.technique` R | `routers.v1.get_problem` |
| `GET /v1/problems/by-code/{code}/diagrams` | anonymous* | `core.problem_image` R, `pedagogy.diagram` R | `core.problem` R | `routers.step_runtime.list_problem_diagrams` |
| `GET /v1/problems/by-code/{code}/source` | anonymous* | `pedagogy.problem_source_ref` R, `pedagogy.source_book` R, `pipeline.pdf_source` R | `core.problem` R | `routers.step_runtime.get_problem_source` |
| `GET /v1/problems/by-code/{code}/source-highlight` | anonymous* | `pedagogy.problem_source_ref` R, `pedagogy.source_book` R, `pipeline.pdf_source` R | `core.problem` R | `routers.step_runtime.get_problem_source_highlight` |
| `GET /v1/problems/by-code/{code}/source-marked-pdf` | anonymous* | `pedagogy.problem_source_ref` R, `pedagogy.source_book` R, `pipeline.pdf_source` R | `core.problem` R | `routers.step_runtime.get_problem_source_marked_pdf` |
| `GET /v1/problems/by-code/{code}/source-pdf` | anonymous* | `pedagogy.problem_source_ref` R, `pedagogy.source_book` R, `pipeline.pdf_source` R | `core.problem` R | `routers.step_runtime.get_problem_source_pdf` |

## `quiz`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `POST /v1/quiz/generate` | Learner JWT | `knowledge.concept` R, `knowledge.concept_relation` R, `knowledge.problem_concept` R, `learner.concept_mastery` R, `quiz.paper` CU, `quiz.question` CR, `quiz.question_concept` C, `quiz.question_skill` C, `quiz.response` R, `quiz.response_draft` R, `quiz.solution` C, `search.chunk` R, `search.embedding` R, `search.embedding_model` R, `search.representation` R | `core.competition` R, `core.competition_edition` R, `core.paper` R, `core.problem` R, `knowledge.technique` R, `learner.technique_mastery` R | `routers.quiz_runtime.generate` |
| `GET /v1/quiz/mine` | Learner JWT | `quiz.paper` R, `quiz.question` R, `quiz.response` R | — | `routers.quiz_runtime.mine` |
| `GET /v1/quiz/{quiz_id}` | Learner JWT | `quiz.paper` R, `quiz.question` R, `quiz.response` R, `quiz.response_draft` R | — | `routers.quiz_runtime.get_quiz` |
| `POST /v1/quiz/{quiz_id}/questions/{question_id}/respond` | Learner JWT | `knowledge.problem_concept` R, `learner.attempt` R, `learner.concept_mastery` CU, `quiz.paper` RU, `quiz.question` R, `quiz.question_concept` R, `quiz.question_technique` R, `quiz.response` CR, `quiz.response_draft` D, `quiz.solution` R | `core.problem` R, `knowledge.problem_technique` R, `learner.technique_mastery` CU | `routers.quiz_runtime.respond` |
| `GET /v1/quiz/{quiz_id}/review` | Learner JWT | `quiz.paper` RU, `quiz.question` R, `quiz.question_source` R, `quiz.response` R, `quiz.solution` R | `core.competition` R, `core.competition_edition` R, `core.paper` R, `core.problem` R | `routers.quiz_runtime.review` |

## `quiz-integration`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/quiz-integration/difficulty-distribution` | Admin key | `knowledge.problem_concept` R | `core.problem` R, `knowledge.concept` R, `knowledge.problem_technique` R, `knowledge.technique` R | `routers.exam_integration.difficulty_distribution` |
| `POST /v1/quiz-integration/papers` | Admin key | `quiz.paper` CU, `quiz.question` CR, `quiz.question_concept` C, `quiz.question_pool` CU, `quiz.question_skill` C, `quiz.question_source` C, `quiz.question_technique` C, `quiz.response` R, `quiz.response_draft` R, `quiz.solution` C | `core.problem` R, `knowledge.concept` R, `knowledge.skill` R, `knowledge.technique` R | `routers.exam_integration.import_paper` |
| `GET /v1/quiz-integration/papers/mine` | Admin key | `quiz.paper` R | `quiz.question` R, `quiz.response` R | `routers.exam_integration.list_my_papers` |
| `POST /v1/quiz-integration/papers/start` | Admin key | `quiz.paper` C | — | `routers.exam_integration.start_paper` |
| `GET /v1/quiz-integration/papers/{quiz_id}` | Admin key | `quiz.paper` R, `quiz.response_draft` R | `quiz.question` R, `quiz.response` R | `routers.exam_integration.get_paper` |
| `GET /v1/quiz-integration/papers/{quiz_id}/diagnosis` | Admin key | `quiz.exam_diagnosis` R, `quiz.paper` R | — | `routers.exam_integration.get_diagnosis` |
| `POST /v1/quiz-integration/papers/{quiz_id}/diagnosis` | Admin key | `quiz.exam_diagnosis` CRU, `quiz.paper` R | — | `routers.exam_integration.write_diagnosis` |
| `GET /v1/quiz-integration/papers/{quiz_id}/diagnosis-input` | Admin key | `quiz.paper` R, `quiz.question` R, `quiz.question_concept` R, `quiz.question_technique` R, `quiz.response` R, `quiz.solution` R | `knowledge.concept` R, `knowledge.technique` R, `learner.concept_mastery` R, `learner.technique_mastery` R | `routers.exam_integration.diagnosis_input` |
| `GET /v1/quiz-integration/papers/{quiz_id}/events` | Admin key | `quiz.paper` R, `quiz.question` R, `quiz.response_event` R | — | `routers.exam_integration.get_events` |
| `POST /v1/quiz-integration/papers/{quiz_id}/fail` | Admin key | `quiz.paper` RU, `quiz.question` R, `quiz.response` R, `quiz.response_draft` R | — | `routers.exam_integration.fail_paper` |
| `POST /v1/quiz-integration/papers/{quiz_id}/finalize` | Admin key | `quiz.paper` RU, `quiz.question` CR, `quiz.question_concept` C, `quiz.question_pool` CU, `quiz.question_skill` C, `quiz.question_source` C, `quiz.question_technique` C, `quiz.response` R, `quiz.response_draft` R, `quiz.solution` C | `core.problem` R, `knowledge.concept` R, `knowledge.skill` R, `knowledge.technique` R | `routers.exam_integration.finalize_paper` |
| `GET /v1/quiz-integration/papers/{quiz_id}/generation-events` | Admin key | `quiz.generation_event` R, `quiz.paper` R | — | `routers.exam_integration.get_generation_events` |
| `POST /v1/quiz-integration/papers/{quiz_id}/generation-events` | Admin key | `quiz.generation_event` C | — | `routers.exam_integration.post_generation_event` |
| `PUT /v1/quiz-integration/papers/{quiz_id}/progress` | Admin key | `quiz.paper` RU, `quiz.question` R, `quiz.response_draft` CU | — | `routers.exam_integration.save_exam_progress` |
| `POST /v1/quiz-integration/papers/{quiz_id}/questions/{question_id}/events` | Admin key | `quiz.paper` R, `quiz.question` R, `quiz.response_draft` D, `quiz.response_event` C | — | `routers.exam_integration.log_event` |
| `POST /v1/quiz-integration/papers/{quiz_id}/questions/{question_id}/respond` | Admin key | `learner.attempt` R, `learner.concept_mastery` CU, `quiz.paper` RU, `quiz.question` R, `quiz.question_concept` R, `quiz.question_technique` R, `quiz.response` CR, `quiz.response_draft` D, `quiz.solution` R | `core.problem` R, `knowledge.problem_concept` R, `knowledge.problem_technique` R, `learner.technique_mastery` CU | `routers.exam_integration.respond` |
| `GET /v1/quiz-integration/papers/{quiz_id}/review` | Admin key | `quiz.paper` RU, `quiz.question` R, `quiz.question_source` R, `quiz.response` R, `quiz.solution` R | `core.competition` R, `core.competition_edition` R, `core.paper` R, `core.problem` R | `routers.exam_integration.review` |
| `POST /v1/quiz-integration/papers/{quiz_id}/submit` | Admin key | `quiz.paper` RU, `quiz.question` R, `quiz.question_source` R, `quiz.response` R, `quiz.response_draft` D, `quiz.solution` R | `core.competition` R, `core.competition_edition` R, `core.paper` R, `core.problem` R | `routers.exam_integration.submit_exam` |
| `POST /v1/quiz-integration/question-pool/match` | Admin key | `quiz.paper` R, `quiz.question` R, `quiz.question_pool` R | — | `routers.exam_integration.match_question_pool` |
| `GET /v1/quiz-integration/students/by-cognito-sub/{cognito_sub}` | Admin key | `learner.solve_attempt` R, `learner.student_profile` R | — | `routers.exam_integration.student_by_cognito_sub` |
| `POST /v1/quiz-integration/students/onboard` | Admin key | `learner.student_profile` CU | — | `routers.exam_integration.onboard_student` |
| `GET /v1/quiz-integration/students/{student_id}` | Admin key | `learner.student_profile` R | — | `routers.exam_integration.student_profile` |
| `GET /v1/quiz-integration/students/{student_id}/mastery-summary` | Admin key | `learner.concept_mastery` R | `knowledge.concept` R, `knowledge.technique` R, `learner.technique_mastery` R | `routers.exam_integration.mastery_summary` |
| `POST /v1/quiz-integration/students/{student_id}/mint-session-token` | Admin key | `learner.student_profile` R | — | `routers.exam_integration.mint_session_token` |

## `realtime`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/realtime/sessions/{sid}` | live_actor | `live.participant` R, `live.session` R | — | `routers.live.realtime_info` |

## `recovery-plans`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/recovery-plans/{plan_id}` | Learner JWT | `pedagogy.learning_item` R, `pedagogy.recovery_plan` R, `pedagogy.recovery_plan_item` R | `core.problem` R, `pedagogy.solution_part` R, `pedagogy.solution_step` R, `pedagogy.taxonomy_node` R | `routers.step_runtime.get_recovery_plan` |
| `POST /v1/recovery-plans/{plan_id}/abort` | Learner JWT | `learner.attempt_step_state` U, `learner.event` C, `learner.idempotency_record` CR, `learner.solve_attempt` U, `pedagogy.knowledge_gap` U, `pedagogy.recovery_plan` RU, `pedagogy.recovery_plan_item` RU, `pipeline.outbox_event` C, `tutor.runtime_state` RU | `pedagogy.learning_item` R, `pedagogy.solution_step` R | `routers.step_runtime.abort_recovery` |
| `POST /v1/recovery-plans/{plan_id}/items/{item_id}/responses` | Learner JWT | `learner.event` C, `learner.idempotency_record` CR, `learner.solve_attempt` R, `pedagogy.knowledge_gap` RU, `pedagogy.learning_item` R, `pedagogy.problem_enrichment` R, `pedagogy.recovery_plan` CRU, `pedagogy.recovery_plan_item` CRU, `pipeline.outbox_event` C, `tutor.runtime_state` RU | `core.problem` R, `pedagogy.solution_part` R, `pedagogy.solution_step` R, `pedagogy.taxonomy_node` R | `routers.step_runtime.answer_recovery_item` |
| `GET /v1/recovery-plans/{plan_id}/next` | Learner JWT | `pedagogy.recovery_plan` R, `pedagogy.recovery_plan_item` R | `core.problem` R, `pedagogy.learning_item` R, `pedagogy.solution_part` R, `pedagogy.solution_step` R, `pedagogy.taxonomy_node` R | `routers.step_runtime.next_recovery_item` |
| `POST /v1/recovery-plans/{plan_id}/resume` | Learner JWT | `learner.attempt_step_state` U, `learner.event` C, `learner.idempotency_record` CR, `learner.solve_attempt` U, `pedagogy.knowledge_gap` U, `pedagogy.recovery_plan` RU, `pedagogy.recovery_plan_item` RU, `pipeline.outbox_event` C, `tutor.runtime_state` RU | `pedagogy.learning_item` R, `pedagogy.solution_step` R | `routers.step_runtime.resume_from_recovery` |

## `render-jobs`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `POST /v1/render-jobs` | Anonymous | `studio.scene_research_job` R, `studio.video_render_job` CR | — | ⚠ not in mathbank-rest route table — `main.post_render_job` |
| `POST /v1/render-jobs/{job_id}/mark-promoted` | Admin key (X-Admin-Api-Key, the studio's own `ADMIN_API_KEY` setting) | `studio.video_render_job` U | — | ⚠ not in mathbank-rest route table — `main.mark_render_job_promoted` |
| `GET /v1/render-jobs/{job_id}/video` | Anonymous | `studio.video_render_job` R | — | ⚠ not in mathbank-rest route table — `main.get_render_job_video` |

## `research-jobs`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `POST /v1/research-jobs` | Anonymous (Function URL `auth_type=NONE`) | `studio.scene_research_job` CR | — | ⚠ not in mathbank-rest route table — `main.post_research_job` |

## `search`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `POST /v1/search/concepts` | anonymous* | `pedagogy.solution_step` R, `pedagogy.solution_step_technique` R, `pedagogy.taxonomy_node` R, `search.chunk` R, `search.embedding` R, `search.embedding_model` R, `search.preprocessing_profile` R, `search.representation` R | `pedagogy.learning_item` R, `pedagogy.learning_item_step_anchor` R | `routers.v1.search_concepts` |
| `POST /v1/search/problems` | anonymous* | `core.competition` R, `core.problem` R, `search.chunk` R, `search.embedding` R, `search.embedding_model` R, `search.representation` R | `core.competition_edition` R, `core.paper` R | `routers.v1.search_problems` |

## `solution-steps`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/solution-steps/{step_id:path}/practice` | Learner JWT | `pedagogy.solution_step` R, `pedagogy.solution_step_technique` R, `pedagogy.taxonomy_node` R, `search.chunk` R, `search.embedding` R, `search.embedding_model` R, `search.preprocessing_profile` R, `search.representation` R | `pedagogy.learning_item` R, `pedagogy.learning_item_step_anchor` R | `routers.step_runtime.practice_for_step` |

## `students`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/students/{student_id}/events` | Learner JWT | `learner.event` R | — | `routers.step_runtime.list_events` |
| `POST /v1/students/{student_id}/problems/{problem_ref}/attempts` | Learner JWT | `learner.attempt_step_state` CU, `learner.event` C, `learner.idempotency_record` CR, `learner.solve_attempt` CRU, `pedagogy.gap_diagnosis` R, `pedagogy.knowledge_gap` R, `pedagogy.recovery_plan` R, `pedagogy.solution_part` R, `pedagogy.solution_step` R, `pipeline.outbox_event` C, `tutor.runtime_state` CRU | `core.problem` R, `pedagogy.solution_step_dependency` R | `routers.step_runtime.start_attempt` |

## `techniques`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/techniques` | anonymous* | `knowledge.entity_alias` R, `knowledge.technique` R | — | `routers.v1.get_techniques` |
| `GET /v1/techniques/{slug}/problems` | anonymous* | `core.problem` R, `knowledge.problem_technique` R, `knowledge.technique` R | `core.competition` R, `core.competition_edition` R, `core.paper` R | `routers.v1.get_technique_problems` |

## `theorems`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `GET /v1/theorems/by-taxonomy/{taxonomy_node_id}` | anonymous* | `knowledge.theorem_taxonomy_link` R | `knowledge.theorem` R | `routers.theorems.list_student_theorems_for_taxonomy` |
| `GET /v1/theorems/by-technique/{technique_slug}` | anonymous* | `knowledge.technique` R, `knowledge.technique_theorem` R | `knowledge.theorem` R | `routers.theorems.list_student_theorems_for_technique` |
| `GET /v1/theorems/search` | anonymous* | `knowledge.theorem` R | — | `routers.theorems.search_student_theorems` |
| `GET /v1/theorems/{slug}` | anonymous* | `knowledge.theorem` R, `knowledge.theorem_asset` R, `knowledge.theorem_source` R, `knowledge.theorem_taxonomy_link` R, `pedagogy.taxonomy_node` R, `visual.asset` R | — | `routers.theorems.get_student_theorem` |
| `GET /v1/theorems/{slug}/prerequisites` | anonymous* | `knowledge.theorem` R, `knowledge.theorem_relation` R, `visual.asset` R | `knowledge.theorem_asset` R, `knowledge.theorem_source` R, `knowledge.theorem_taxonomy_link` R, `pedagogy.taxonomy_node` R | `routers.theorems.get_student_theorem_prerequisites` |

## `tutor`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `POST /v1/tutor/check-subproblem` | anonymous* | — | — | `routers.tutor.check_subproblem` |
| `POST /v1/tutor/coach` | anonymous* | `core.solution` R, `knowledge.enrichment_job` CU, `knowledge.pedagogy_publication` C, `knowledge.problem_concept` C, `knowledge.problem_pedagogy` CU, `knowledge.problem_skill` CU, `knowledge.problem_technique` C, `knowledge.relationship_enrichment_job` U, `knowledge.skill` CU, `knowledge.skill_relation` CU, `pedagogy.diagram` R, `pedagogy.problem_source_ref` R, `pedagogy.route_step_hint` R, `pedagogy.solution_route_release` R, `pedagogy.solution_step_instruction` R, `pedagogy.taxonomy_node` R | `core.competition` R, `core.competition_edition` R, `core.paper` R, `core.problem` R, `core.problem_image` R | `routers.pedagogy.coach` |
| `POST /v1/tutor/decompose` | anonymous* | `core.solution` R, `knowledge.problem_concept` R, `knowledge.problem_technique` R, `pedagogy.diagram` R | `core.competition` R, `core.competition_edition` R, `core.paper` R, `core.problem` R, `core.problem_image` R, `knowledge.concept` R, `knowledge.technique` R | `routers.tutor.decompose` |
| `POST /v1/tutor/feedback` | Learner JWT | `knowledge.problem_technique` R, `learner.pedagogy_feedback` C, `pedagogy.solution_step` R, `pedagogy.solution_step_technique` R, `pedagogy.taxonomy_node` R | `core.problem` R, `knowledge.technique` R | `routers.pedagogy.feedback` |
| `POST /v1/tutor/format-math` | staff_or_student | — | — | `routers.fluid.format_math` |
| `POST /v1/tutor/guidance-plan` | anonymous* | `core.solution` R, `pedagogy.solution_route_release` R, `pedagogy.solution_step_instruction` R | `core.problem` R | `routers.pedagogy.guidance_plan` |
| `GET /v1/tutor/learning-context/{problem_code}` | anonymous* | `core.solution` R, `knowledge.enrichment_job` CU, `knowledge.pedagogy_publication` C, `knowledge.problem_concept` C, `knowledge.problem_pedagogy` CU, `knowledge.problem_skill` CU, `knowledge.problem_technique` C, `knowledge.relationship_enrichment_job` U, `knowledge.skill` CU, `knowledge.skill_relation` CU, `pedagogy.diagram` R, `pedagogy.problem_source_ref` R, `pedagogy.taxonomy_node` R | `core.competition` R, `core.competition_edition` R, `core.paper` R, `core.problem` R, `core.problem_image` R | `routers.pedagogy.learning_context` |
| `POST /v1/tutor/micro-check` | anonymous* | `pedagogy.diagram` R | `core.competition` R, `core.competition_edition` R, `core.paper` R, `core.problem` R, `core.problem_image` R | `routers.pedagogy.micro_check` |
| `GET /v1/tutor/practice/{problem_code}` | anonymous* | `pedagogy.diagram` R | `core.competition` R, `core.competition_edition` R, `core.paper` R, `core.problem` R, `core.problem_image` R | `routers.pedagogy.practice` |
| `GET /v1/tutor/prerequisites/{skill_slug}` | anonymous* | — | — | `routers.pedagogy.prerequisites` |
| `POST /v1/tutor/route-attempts` | Learner JWT | `core.solution` R, `learner.route_attempt` C, `pedagogy.solution_route_release` R, `pedagogy.solution_step_instruction` R | `core.problem` R | `routers.tutoring_routes.start` |
| `GET /v1/tutor/route-attempts/{attempt_id}` | Learner JWT | `learner.route_attempt` R, `pedagogy.solution_step_instruction` R | — | `routers.tutoring_routes.current` |
| `POST /v1/tutor/route-attempts/{attempt_id}/assist` | Learner JWT | `learner.route_attempt` RU, `pedagogy.route_step_hint` R, `pedagogy.solution_step_instruction` R | — | `routers.tutoring_routes.assist` |
| `POST /v1/tutor/sessions/{sid}/actions` | Admin key | `activity.definition` CR, `activity.instance` CU, `live.command_receipt` CR, `live.recommendation` CU, `live.session` U, `live.session_event` C, `visual.widget_spec` CRU | `activity.response` CRU, `core.problem` R, `core.problem_image` R, `live.participant` RU, `live.takeover` CRU, `live.topic_run` U, `pipeline.outbox_event` C, `visual.widget_state` CU | `routers.live.tutor_action` |
| `GET /v1/tutor/sessions/{sid}/context` | Admin key | `activity.definition` R, `activity.instance` R, `activity.response` R, `live.session_event` R | `live.participant` R, `live.recommendation` R, `live.session` R, `live.takeover` R, `live.topic_run` R | `routers.live.tutor_context` |
| `POST /v1/tutor/sessions/{sid}/messages` | Admin key | `live.command_receipt` CR, `live.session` U | `activity.definition` CR, `activity.instance` CRU, `activity.response` CRU, `core.problem` R, `core.problem_image` R, `live.participant` RU, `live.recommendation` CRU, `live.session_event` CR, `live.takeover` CRU, `live.topic_run` RU, `pipeline.outbox_event` C, `visual.widget_spec` CRU, `visual.widget_state` CU | `routers.live.tutor_message` |
| `GET /v1/tutor/topic-plan` | anonymous* | `pedagogy.taxonomy_node` R | — | `routers.pedagogy.topic_plan` |
| `POST /v1/tutor/topic-practice` | get_optional_student_id | `knowledge.problem_concept` R, `knowledge.problem_technique` R, `learner.attempt` R, `learner.pedagogy_feedback` R, `learner.solve_attempt` R, `pedagogy.knowledge_gap` R, `pedagogy.problem_enrichment` R, `pedagogy.solution_step` R, `pedagogy.solution_step_technique` R, `pedagogy.taxonomy_edge` R, `pedagogy.taxonomy_node` R | `core.problem` R | `routers.pedagogy.topic_practice` |
| `GET /v1/tutor/workspace/{problem_code}` | anonymous* | `pedagogy.diagram` R | `core.competition` R, `core.competition_edition` R, `core.paper` R, `core.problem` R, `core.problem_image` R | `routers.pedagogy.workspace` |

## `widgets`

| Route | Auth | Tables — verified | Static trace only | Handler |
|---|---|---|---|---|
| `POST /v1/widgets/generate` | staff_or_student | `visual.widget_spec` C | `core.problem` R, `core.problem_image` R | `routers.fluid.widget_generate` |
| `GET /v1/widgets/registry` | anonymous* | — | — | `routers.fluid.widget_registry` |
| `GET /v1/widgets/specs` | Admin key | `visual.widget_spec` R | — | `routers.fluid.widget_specs` |
| `POST /v1/widgets/specs` | Admin key | `visual.widget_spec` C | `core.problem` R, `core.problem_image` R | `routers.fluid.widget_store` |
| `GET /v1/widgets/specs/{spec_id}` | staff_or_student | `visual.widget_spec` R | — | `routers.fluid.widget_spec` |
| `POST /v1/widgets/specs/{spec_id}/review` | Admin key | `visual.widget_spec` RU | — | `routers.fluid.widget_review` |
| `POST /v1/widgets/validate` | staff_or_student | — | `core.problem` R, `core.problem_image` R | `routers.fluid.widget_validate` |
