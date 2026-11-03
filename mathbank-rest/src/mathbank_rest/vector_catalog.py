"""S3 Vectors index catalogue for the REST service (requirement 71 §2.5, requirement 70 §13 C6 §8b).

One entry per vector family. Index names and metadata keys mirror ``mathbank-db/aws/s3/vector_indexes.py`` (the
catalogue the copy used); ``tests/test_vector_catalog.py`` fails if the two drift. Every index is float32 / 1536 /
cosine. A family's *metadata model* is the pydantic contract of what is stored next to each vector: filterable keys
(usable in a query filter) and non-filterable keys (returned, never filtered; S3 Vectors rejects a filter on them).

``Family.<X>`` is the argument of every ``VectorStore`` call, so callers never spell an index name.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, StrictBool, StrictFloat, StrictInt, StrictStr

MODEL_TAG = "te3small-1536-v1"
EMBEDDING_MODEL = "text-embedding-3-small"
DIMENSIONS = 1536


class Family(StrEnum):
    MISCONCEPTION = "misconception"
    TAXONOMY_NODE = "taxonomy-node"
    TAXONOMY_SEARCH = "taxonomy-search"
    PROBLEM = "problem"
    SOLUTION = "solution"
    STEP = "step"
    LEARNING_ITEM = "learning-item"
    SEARCH_ARCHIVE = "search-archive"
    THEOREM = "theorem"
    ARTIFACT_PUBLIC = "artifact-public"
    ARTIFACT_PRIVATE = "artifact-private"
    QUIZ_QUESTION = "quiz-question"

    @property
    def index_name(self) -> str:
        return f"{self.value}-{MODEL_TAG}"


class VectorMetadata(BaseModel):
    """Base of the per-family metadata models. Values are S3 Vectors metadata types only: string, number, boolean,
    list of strings. ``None`` means "key absent" (S3 Vectors has no null, and rejects empty lists)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    NON_FILTERABLE: ClassVar[frozenset[str]] = frozenset()

    def to_metadata(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump(mode="json").items() if v not in (None, [])}

    @classmethod
    def filterable(cls) -> frozenset[str]:
        return frozenset(cls.model_fields) - cls.NON_FILTERABLE


class MisconceptionMeta(VectorMetadata):
    NON_FILTERABLE = frozenset({"source_sha256", "generated_at"})
    lifecycle: StrictStr
    taxonomy_node_ids: list[StrictStr] | None = None
    source_sha256: StrictStr | None = None
    generated_at: StrictStr | None = None


class TaxonomyNodeMeta(VectorMetadata):
    NON_FILTERABLE = frozenset({"source_sha256", "generated_at"})
    node_type: StrictStr | None = None
    lifecycle: StrictStr
    book_code: StrictStr | None = None
    chapter_number: StrictInt | StrictFloat | None = None
    source_sha256: StrictStr | None = None
    generated_at: StrictStr | None = None


class TaxonomySearchMeta(VectorMetadata):
    NON_FILTERABLE = frozenset({"content_sha256", "representation_id"})
    node_type: StrictStr | None = None
    chapter_number: StrictInt | StrictFloat | None = None
    taxonomy_node_id: StrictStr | None = None
    content_sha256: StrictStr
    representation_id: StrictStr


class ProblemMeta(VectorMetadata):
    NON_FILTERABLE = frozenset({"canonical_code", "content_sha256", "chunk_ordinal", "representation_id"})
    competition: StrictStr | None = None
    year: StrictInt | None = None
    problem_id: StrictStr
    chunk_kind: StrictStr
    canonical_code: StrictStr
    content_sha256: StrictStr
    chunk_ordinal: StrictInt
    representation_id: StrictStr


class SolutionMeta(VectorMetadata):
    NON_FILTERABLE = frozenset({"solution_id", "content_sha256", "chunk_ordinal"})
    problem_id: StrictStr
    solution_kind: StrictStr | None = None
    verification_status: StrictStr | None = None
    competition: StrictStr | None = None
    year: StrictInt | None = None
    solution_id: StrictStr
    content_sha256: StrictStr
    chunk_ordinal: StrictInt


class StepMeta(VectorMetadata):
    NON_FILTERABLE = frozenset({"solution_step_id", "content_sha256", "problem_code"})
    skill_node_id: StrictStr | None = None
    subconcept_node_id: StrictStr | None = None
    concept_node_id: StrictStr | None = None
    step_type: StrictStr | None = None
    tutor_role: StrictStr | None = None
    is_checkpoint: StrictBool | None = None
    hint_level: StrictInt | None = None
    problem_id: StrictStr
    technique_node_ids: list[StrictStr] | None = None
    book_code: StrictStr | None = None
    solution_step_id: StrictStr
    content_sha256: StrictStr
    problem_code: StrictStr | None = None


class LearningItemMeta(VectorMetadata):
    NON_FILTERABLE = frozenset({"learning_item_id", "content_sha256"})
    kind: StrictStr
    target_skill_node_id: StrictStr | None = None
    target_subconcept_node_id: StrictStr | None = None
    transformed_form: StrictStr | None = None
    transformation_type: StrictStr | None = None
    difficulty_direction: StrictStr | None = None
    source_problem_id: StrictStr | None = None
    anchor_step_ids: list[StrictStr] | None = None
    learning_item_id: StrictStr
    content_sha256: StrictStr


class SearchArchiveMeta(VectorMetadata):
    NON_FILTERABLE = frozenset({"representation_id"})
    kind: StrictStr | None = None
    status: StrictStr | None = None
    representation_id: StrictStr | None = None


class TheoremMeta(VectorMetadata):
    NON_FILTERABLE = frozenset({"slug", "source_sha256"})
    review_status: StrictStr
    taxonomy_node_ids: list[StrictStr] | None = None
    technique_ids: list[StrictStr] | None = None
    slug: StrictStr | None = None
    source_sha256: StrictStr | None = None


class ArtifactPublicMeta(VectorMetadata):
    NON_FILTERABLE = frozenset({"search_text_sha256"})
    subject: StrictStr | None = None
    status: StrictStr
    concept_tags: list[StrictStr] | None = None
    skill_tags: list[StrictStr] | None = None
    theorem_tags: list[StrictStr] | None = None
    search_text_sha256: StrictStr | None = None


class ArtifactPrivateMeta(VectorMetadata):
    NON_FILTERABLE = frozenset({"search_text_sha256"})
    owner_student_id: StrictStr
    subject: StrictStr | None = None
    status: StrictStr
    search_text_sha256: StrictStr | None = None


class QuizQuestionMeta(VectorMetadata):
    NON_FILTERABLE = frozenset({"topic_key_sha256"})
    style: StrictStr | None = None
    question_type: StrictStr | None = None
    difficulty_band: StrictStr | None = None
    concept_slugs: list[StrictStr] | None = None
    topic_key_sha256: StrictStr | None = None


META_MODELS: dict[Family, type[VectorMetadata]] = {
    Family.MISCONCEPTION: MisconceptionMeta,
    Family.TAXONOMY_NODE: TaxonomyNodeMeta,
    Family.TAXONOMY_SEARCH: TaxonomySearchMeta,
    Family.PROBLEM: ProblemMeta,
    Family.SOLUTION: SolutionMeta,
    Family.STEP: StepMeta,
    Family.LEARNING_ITEM: LearningItemMeta,
    Family.SEARCH_ARCHIVE: SearchArchiveMeta,
    Family.THEOREM: TheoremMeta,
    Family.ARTIFACT_PUBLIC: ArtifactPublicMeta,
    Family.ARTIFACT_PRIVATE: ArtifactPrivateMeta,
    Family.QUIZ_QUESTION: QuizQuestionMeta,
}
assert set(META_MODELS) == set(Family)


def meta_model(family: Family) -> type[VectorMetadata]:
    return META_MODELS[family]
