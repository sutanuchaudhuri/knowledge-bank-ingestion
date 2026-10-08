# Live Neo4j metadata appendix

Observed **2026-10-08T01:57:56.201870+00:00**, user-selected **REST-configured Neo4j**, source `2bb4c2f682bf205556b8d6e895c868b10cdcc7a7`.
Read-only schema procedures, SHOW metadata and DISTINCT endpoint-label sets. No node/relationship property values were returned.
Types and mandatory flags are empirical property observations, **not property-type/existence constraints**.
A missing observed property or endpoint is not proof that the checked-in projector does not support it.
Neo4j warned that the `propertyTypes` output format will change in its next major version; types below retain the observed format.

[Source projection contract](GRAPH_SCHEMA.md) | [PostgreSQL catalog](postgres/README.md) | [Step lifecycle](../36_STEP_GENERATOR_AND_AUTHORING.md)

## Observed constraints

| Name | Type | Entity | Labels/types | Properties |
|---|---|---|---|---|
| `competition_id` | UNIQUENESS | NODE | Competition | canonical_id |
| `concept_id` | UNIQUENESS | NODE | Concept | canonical_id |
| `learning_item_id` | UNIQUENESS | NODE | LearningItem | canonical_id |
| `paper_id` | UNIQUENESS | NODE | Paper | canonical_id |
| `problem_id` | UNIQUENESS | NODE | Problem | canonical_id |
| `skill_id` | UNIQUENESS | NODE | Skill | canonical_id |
| `solution_id` | UNIQUENESS | NODE | Solution | canonical_id |
| `solution_part_id` | UNIQUENESS | NODE | SolutionPart | canonical_id |
| `solution_step_id` | UNIQUENESS | NODE | SolutionStep | canonical_id |
| `technique_id` | UNIQUENESS | NODE | Technique | canonical_id |

## Observed indexes

| Name | Type | Entity | Labels/types | Properties | State |
|---|---|---|---|---|---|
| `competition_id` | RANGE | NODE | Competition | canonical_id | ONLINE |
| `concept_id` | RANGE | NODE | Concept | canonical_id | ONLINE |
| `index_1b9dcc97` | LOOKUP | RELATIONSHIP |  |  | ONLINE |
| `index_460996c0` | LOOKUP | NODE |  |  | ONLINE |
| `learning_item_id` | RANGE | NODE | LearningItem | canonical_id | ONLINE |
| `paper_id` | RANGE | NODE | Paper | canonical_id | ONLINE |
| `problem_id` | RANGE | NODE | Problem | canonical_id | ONLINE |
| `skill_id` | RANGE | NODE | Skill | canonical_id | ONLINE |
| `solution_id` | RANGE | NODE | Solution | canonical_id | ONLINE |
| `solution_part_id` | RANGE | NODE | SolutionPart | canonical_id | ONLINE |
| `solution_step_id` | RANGE | NODE | SolutionStep | canonical_id | ONLINE |
| `technique_id` | RANGE | NODE | Technique | canonical_id | ONLINE |

## Every observed node label-set/property/type

| Labels | Property | Observed types | Mandatory in observed label-set |
|---|---|---|---|
| Competition | `canonical_id` | String | True |
| Competition | `external_code` | String | True |
| Competition | `level` | String | True |
| Competition | `name` | String | True |
| Concept | `canonical_id` | String | True |
| Concept | `level` | Long | False |
| Concept | `name` | String | True |
| Concept | `slug` | String | True |
| Concept + Subconcept | `canonical_id` | String | True |
| Concept + Subconcept | `level` | Long | True |
| Concept + Subconcept | `name` | String | True |
| Concept + Subconcept | `slug` | String | True |
| LearningItem | `book_code` | String | True |
| LearningItem | `canonical_id` | String | True |
| LearningItem | `content_version` | String | True |
| LearningItem | `difficulty_direction` | String | True |
| LearningItem | `external_id` | String | True |
| LearningItem | `postgres_id` | String | True |
| LearningItem | `projection_kind` | String | True |
| LearningItem | `projection_version` | String | True |
| LearningItem | `publication_status` | String | True |
| LearningItem | `source_package_id` | String | True |
| LearningItem | `transformation_type` | String | True |
| LearningItem | `transformed_form` | String | True |
| Paper | `canonical_id` | String | True |
| Paper | `external_code` | String | True |
| Paper | `paper_code` | String | True |
| Paper | `question_count` | Long | False |
| Paper | `year` | Long | False |
| Problem | `algebraic_load` | Long | False |
| Problem | `canonical_code` | String | True |
| Problem | `canonical_id` | String | True |
| Problem | `classification_status` | String | False |
| Problem | `conceptual_depth` | Long | False |
| Problem | `difficulty_band` | String | False |
| Problem | `estimated_contest_level` | String | False |
| Problem | `insight_required` | Long | False |
| Problem | `number_of_steps` | Long | False |
| Problem | `official_answer` | String | False |
| Problem | `pedagogy_approval_method` | String | False |
| Problem | `pedagogy_confidence` | Double | False |
| Problem | `pedagogy_review_status` | String | False |
| Problem | `pedagogy_source` | String | False |
| Problem | `prerequisite_depth` | Long | False |
| Problem | `problem_number` | Long | True |
| Problem | `problem_page_images` | Long | True |
| Problem | `solution_page_images` | Long | True |
| Problem | `source_url` | String | False |
| Problem | `technical_load` | Long | False |
| Skill | `approval_method` | String | True |
| Skill | `canonical_id` | String | True |
| Skill | `confidence` | Double | True |
| Skill | `level` | Long | False |
| Skill | `name` | String | True |
| Skill | `objective` | String | True |
| Skill | `projection_kind` | String | True |
| Skill | `review_status` | String | True |
| Skill | `slug` | String | True |
| Skill | `source` | String | True |
| SolutionPart | `book_code` | String | True |
| SolutionPart | `canonical_id` | String | True |
| SolutionPart | `content_version` | String | True |
| SolutionPart | `external_id` | String | True |
| SolutionPart | `occurrence` | Long | True |
| SolutionPart | `part_label` | String | True |
| SolutionPart | `part_ordinal` | Long | True |
| SolutionPart | `postgres_id` | String | True |
| SolutionPart | `problem_canonical_code` | String | True |
| SolutionPart | `projection_kind` | String | True |
| SolutionPart | `projection_version` | String | True |
| SolutionPart | `publication_status` | String | True |
| SolutionPart | `source_package_id` | String | True |
| SolutionPart | `source_page` | Long | False |
| SolutionPart | `step_count` | Long | True |
| SolutionStep | `book_code` | String | True |
| SolutionStep | `canonical_id` | String | True |
| SolutionStep | `content_version` | String | True |
| SolutionStep | `external_id` | String | True |
| SolutionStep | `global_step_index` | Long | True |
| SolutionStep | `hint_level` | Long | True |
| SolutionStep | `is_checkpoint` | Boolean | True |
| SolutionStep | `occurrence` | Long | True |
| SolutionStep | `postgres_id` | String | True |
| SolutionStep | `problem_canonical_code` | String | True |
| SolutionStep | `projection_kind` | String | True |
| SolutionStep | `projection_version` | String | True |
| SolutionStep | `publication_status` | String | True |
| SolutionStep | `skill_name` | String | True |
| SolutionStep | `source_package_id` | String | True |
| SolutionStep | `source_page` | Long | False |
| SolutionStep | `step_index_in_part` | Long | True |
| SolutionStep | `step_type` | String | True |
| SolutionStep | `tutor_role` | String | True |
| Solution | `canonical_id` | String | True |
| Solution | `revision` | Long | True |
| Solution | `solution_kind` | String | True |
| Solution | `verification_status` | String | True |
| Technique | `canonical_id` | String | True |
| Technique | `name` | String | True |
| Technique | `slug` | String | True |

## Every observed relationship property/type

| Relationship type | Property | Observed types | Mandatory in observed type |
|---|---|---|---|
| :`ANCHORED_AT` | `ordinal` | Long | True |
| :`ANCHORED_AT` | `projection_key` | String | True |
| :`ANCHORED_AT` | `projection_kind` | String | True |
| :`ASSESSES` | `projection_key` | String | True |
| :`ASSESSES` | `projection_kind` | String | True |
| :`BUILDS_ON` | `approval_method` | String | True |
| :`BUILDS_ON` | `confidence` | Double | True |
| :`BUILDS_ON` | `projection_kind` | String | True |
| :`BUILDS_ON` | `review_status` | String | True |
| :`BUILDS_ON` | `source` | String | True |
| :`CONCEPT_RELATION` | `approval_method` | String | True |
| :`CONCEPT_RELATION` | `confidence` | Double | True |
| :`CONCEPT_RELATION` | `relation_type` | String | True |
| :`CONCEPT_RELATION` | `review_status` | String | True |
| :`CONCEPT_RELATION` | `source` | String | True |
| :`CONCEPT_RELATION` | `strength` | Double | True |
| :`DEPENDS_ON` | `approval_method` | String | True |
| :`DEPENDS_ON` | `confidence` | Double | True |
| :`DEPENDS_ON` | `logical_dependency` | String | True |
| :`DEPENDS_ON` | `projection_key` | String | True |
| :`DEPENDS_ON` | `projection_kind` | String | True |
| :`DEPENDS_ON` | `review_status` | String | True |
| :`DEPENDS_ON` | `source_type` | String | True |
| :`DERIVED_FROM` | `projection_key` | String | True |
| :`DERIVED_FROM` | `projection_kind` | String | True |
| :`HAS_PAPER` | `None` |  | False |
| :`HAS_PART` | `part_ordinal` | Long | True |
| :`HAS_PART` | `projection_key` | String | True |
| :`HAS_PART` | `projection_kind` | String | True |
| :`HAS_PROBLEM` | `None` |  | False |
| :`HAS_SOLUTION` | `None` |  | False |
| :`HAS_STEP` | `projection_key` | String | True |
| :`HAS_STEP` | `projection_kind` | String | True |
| :`HAS_STEP` | `step_index_in_part` | Long | True |
| :`NEXT` | `approval_method` | String | True |
| :`NEXT` | `confidence` | Double | True |
| :`NEXT` | `logical_dependency` | String | True |
| :`NEXT` | `projection_key` | String | True |
| :`NEXT` | `projection_kind` | String | True |
| :`NEXT` | `review_status` | String | True |
| :`NEXT` | `source_type` | String | True |
| :`PART_OF` | `approval_method` | String | True |
| :`PART_OF` | `confidence` | Double | True |
| :`PART_OF` | `projection_kind` | String | True |
| :`PART_OF` | `review_status` | String | True |
| :`PART_OF` | `source` | String | True |
| :`PRACTICES` | `approval_method` | String | True |
| :`PRACTICES` | `confidence` | Double | True |
| :`PRACTICES` | `importance` | Double | True |
| :`PRACTICES` | `projection_kind` | String | True |
| :`PRACTICES` | `required_level` | Long | True |
| :`PRACTICES` | `review_status` | String | True |
| :`PRACTICES` | `role` | String | True |
| :`PRACTICES` | `source` | String | True |
| :`PREREQUISITE_OF` | `approval_method` | String | True |
| :`PREREQUISITE_OF` | `confidence` | Double | True |
| :`PREREQUISITE_OF` | `projection_kind` | String | True |
| :`PREREQUISITE_OF` | `review_status` | String | True |
| :`PREREQUISITE_OF` | `source` | String | True |
| :`REQUIRES` | `approval_method` | String | True |
| :`REQUIRES` | `confidence` | Double | True |
| :`REQUIRES` | `importance` | Double | True |
| :`REQUIRES` | `projection_kind` | String | True |
| :`REQUIRES` | `required_level` | Long | False |
| :`REQUIRES` | `review_status` | String | True |
| :`REQUIRES` | `role` | String | True |
| :`REQUIRES` | `source` | String | True |
| :`TARGETS_CONCEPT` | `projection_key` | String | True |
| :`TARGETS_CONCEPT` | `projection_kind` | String | True |
| :`TARGETS_SUBCONCEPT` | `projection_key` | String | True |
| :`TARGETS_SUBCONCEPT` | `projection_kind` | String | True |
| :`TESTS` | `approval_method` | String | True |
| :`TESTS` | `confidence` | Double | True |
| :`TESTS` | `importance` | Double | False |
| :`TESTS` | `projection_kind` | String | False |
| :`TESTS` | `required_level` | Long | False |
| :`TESTS` | `review_status` | String | True |
| :`TESTS` | `role` | String | True |
| :`TESTS` | `source` | String | True |
| :`USES_CONCEPT` | `projection_key` | String | True |
| :`USES_CONCEPT` | `projection_kind` | String | True |
| :`USES_SKILL` | `projection_key` | String | True |
| :`USES_SKILL` | `projection_kind` | String | True |
| :`USES_SUBCONCEPT` | `projection_key` | String | True |
| :`USES_SUBCONCEPT` | `projection_kind` | String | True |
| :`USES_TECHNIQUE` | `approval_method` | String | True |
| :`USES_TECHNIQUE` | `confidence` | Double | True |
| :`USES_TECHNIQUE` | `derivation_version` | String | False |
| :`USES_TECHNIQUE` | `projection_key` | String | False |
| :`USES_TECHNIQUE` | `projection_kind` | String | False |
| :`USES_TECHNIQUE` | `review_status` | String | True |
| :`USES_TECHNIQUE` | `role` | String | False |
| :`USES_TECHNIQUE` | `source` | String | False |
| :`USES_TECHNIQUE` | `source_type` | String | False |

## Every observed directed endpoint label-set

| Source labels | Relationship | Target labels |
|---|---|---|
| LearningItem | `ANCHORED_AT` | SolutionStep |
| LearningItem | `ASSESSES` | Skill |
| Skill | `BUILDS_ON` | Skill |
| Concept | `CONCEPT_RELATION` | Concept |
| Concept | `CONCEPT_RELATION` | Concept + Subconcept |
| Concept + Subconcept | `CONCEPT_RELATION` | Concept |
| SolutionStep | `DEPENDS_ON` | SolutionStep |
| LearningItem | `DERIVED_FROM` | Problem |
| Competition | `HAS_PAPER` | Paper |
| Solution | `HAS_PART` | SolutionPart |
| Paper | `HAS_PROBLEM` | Problem |
| Problem | `HAS_SOLUTION` | Solution |
| SolutionPart | `HAS_STEP` | SolutionStep |
| SolutionStep | `NEXT` | SolutionStep |
| Concept | `PART_OF` | Concept |
| Concept + Subconcept | `PART_OF` | Concept |
| Skill | `PART_OF` | Concept |
| Skill | `PART_OF` | Concept + Subconcept |
| Skill | `PART_OF` | Skill |
| Problem | `PRACTICES` | Skill |
| Concept | `PREREQUISITE_OF` | Concept |
| Concept | `PREREQUISITE_OF` | Concept + Subconcept |
| Concept + Subconcept | `PREREQUISITE_OF` | Concept |
| Concept + Subconcept | `PREREQUISITE_OF` | Concept + Subconcept |
| Skill | `PREREQUISITE_OF` | Skill |
| Problem | `REQUIRES` | Skill |
| LearningItem | `TARGETS_CONCEPT` | Concept |
| LearningItem | `TARGETS_SUBCONCEPT` | Concept + Subconcept |
| Problem | `TESTS` | Concept |
| Problem | `TESTS` | Concept + Subconcept |
| Problem | `TESTS` | Skill |
| SolutionStep | `USES_CONCEPT` | Concept |
| SolutionStep | `USES_SKILL` | Skill |
| SolutionStep | `USES_SUBCONCEPT` | Concept + Subconcept |
| Problem | `USES_TECHNIQUE` | Technique |
| SolutionStep | `USES_TECHNIQUE` | Technique |

## Observed vocabulary

**Labels:** `Competition`, `Concept`, `LearningItem`, `Paper`, `Problem`, `Skill`, `Solution`, `SolutionPart`, `SolutionStep`, `Subconcept`, `Technique`.

**Relationship types:** `ANCHORED_AT`, `ASSESSES`, `BUILDS_ON`, `CONCEPT_RELATION`, `DEPENDS_ON`, `DERIVED_FROM`, `HAS_PAPER`, `HAS_PART`, `HAS_PROBLEM`, `HAS_SOLUTION`, `HAS_STEP`, `NEXT`, `PART_OF`, `PRACTICES`, `PREREQUISITE_OF`, `REQUIRES`, `TARGETS_CONCEPT`, `TARGETS_SUBCONCEPT`, `TESTS`, `USES_CONCEPT`, `USES_SKILL`, `USES_SUBCONCEPT`, `USES_TECHNIQUE`.

Access/use cases and projection ownership are documented in the source contract, not inferred from graph presence.
No learner mastery projection or automatic step/widget attachment can be inferred from this observed graph.
