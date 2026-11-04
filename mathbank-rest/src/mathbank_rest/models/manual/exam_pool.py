"""Item models of the question pool in ``mb-exam`` (requirement 71 WP6, design C2 sections 3 and 4).

``quiz.question_pool`` had no live rows when the generated models were built, so these are written from the migration transform
(``mathbank-db/aws/dynamo/specs/exam.py``: ``pool``, ``pool_served``) and the design:

======================  ===========================  =======================================================  ==========================
item type               PK / SK                      GSI1 / GSI2                                              notes
======================  ===========================  =======================================================  ==========================
POOL_QUESTION           ``POOL#<id>`` / ``POOL``      ``POOLKEY#<style>#<qtype>#<band|NONE>`` /                ``question`` inline, or
                                                     ``<status>#<times_served:08d>#<id>``;                    ``question_ref`` over 100 KB
                                                     ``POOL_STATUS#<status>`` / ``<created_at>#<id>``
UNIQUE_CONTENT_HASH     ``UNIQUE#content_hash#<sha>``  -                                                      ``pool_question_id``
POOL_CONCEPT            ``POOLCONCEPT#<slug>`` /      -                                                       ``status`` mirrors the pool item
                        ``<style>#<qtype>#<band>#<id>``
POOL_SERVED             ``STUDENT#<sid>`` /           -                                                       the learner's history
                        ``POOLSERVED#<id>``
======================  ===========================  =======================================================  ==========================

Enums are ``Literal`` types validated before every write (the pool style CHECK of QUZ-S05 lives here). The GSI keys are derived from
the attributes and the model refuses an item whose keys disagree with them, so a status change that forgets a key cannot be written.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, ClassVar, Literal, Self
from uuid import UUID

from pydantic import Field, StrictInt, StrictStr, model_validator

from mathbank_rest.models.base import SHA256_RE, DdbItem, S3Ref, UtcDateTime

_UUID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

PoolStyle = Literal["AIME", "HMMT", "PROOF_BASED", "TOPIC_BASED", "SKILL_BASED", "MIXED"]
PoolQuestionType = Literal["MCQ", "FREE_TEXT", "PROOF"]
PoolBand = Literal["easy", "medium", "hard", "very_hard"]
PoolStatus = Literal["ACTIVE", "RETIRED"]
VectorState = Literal["PENDING", "INDEXED"]
ServedOrigin = Literal["SERVED", "WRITE_BACK"]

STYLES: tuple[str, ...] = PoolStyle.__args__          # type: ignore[attr-defined]
QUESTION_TYPES: tuple[str, ...] = PoolQuestionType.__args__   # type: ignore[attr-defined]
BANDS: tuple[str, ...] = PoolBand.__args__            # type: ignore[attr-defined]
STATUSES: tuple[str, ...] = PoolStatus.__args__       # type: ignore[attr-defined]
NO_BAND = "NONE"
CONTENT_HASH_FIELD = "content_hash"
INLINE_QUESTION_MAX_BYTES = 100 * 1024                # larger payloads go to S3 ``exam/pool/<pool_id>.json``


# ------------------------------------------------------------------------------------------------ key builders

def pool_pk(pool_id: Any) -> str:
    return f"POOL#{pool_id}"


def poolkey(style: str, question_type: str, band: str | None) -> str:
    """GSI1PK of a pool item: the lookup by style, type and band (``NONE`` for a null band)."""
    return f"POOLKEY#{style}#{question_type}#{band or NO_BAND}"


def pool_gsi1sk(status: str, times_served: int, pool_id: Any) -> str:
    return f"{status}#{int(times_served):08d}#{pool_id}"


def pool_status_pk(status: str) -> str:
    return f"POOL_STATUS#{status}"


def concept_pk(slug: str) -> str:
    return f"POOLCONCEPT#{slug}"


def concept_prefix(style: str, question_type: str, band: str | None) -> str:
    return f"{style}#{question_type}#{band or NO_BAND}#"


def concept_sk(style: str, question_type: str, band: str | None, pool_id: Any) -> str:
    return f"{concept_prefix(style, question_type, band)}{pool_id}"


def served_sk(pool_id: Any) -> str:
    return f"POOLSERVED#{pool_id}"


def normalize_band(value: Any) -> str | None:
    """Bands are stored lower-case (design section 7 pre-check); an empty value is no band."""
    if value is None:
        return None
    band = str(value).strip().lower()
    return band or None


# ------------------------------------------------------------------------------------------------ POOL_QUESTION

class PoolQuestion(DdbItem, ctx="exam", item_type="POOL_QUESTION"):
    """``quiz.question_pool``. ``question`` is the finalize payload (answer key included: it is only ever returned to the agent and to
    staff). ``question_ref`` replaces it when it exceeds ``INLINE_QUESTION_MAX_BYTES``."""

    type: Literal["POOL_QUESTION"] = "POOL_QUESTION"
    PK: str = Field(pattern=f"^POOL#{_UUID}$")
    SK: str = Field(pattern="^POOL$")
    pool_question_id: UUID
    content_hash: str = Field(pattern=SHA256_RE)
    style: PoolStyle
    question_type: PoolQuestionType
    difficulty_band: PoolBand | None = None
    topic_key: StrictStr = Field(default="", max_length=200)
    concept_slugs: list[StrictStr] | None = None
    technique_slugs: list[StrictStr] | None = None
    question: dict[str, Any] | None = None
    question_ref: S3Ref | None = None
    source_quiz_id: UUID | None = None
    generated_by: StrictStr | None = None
    times_served: StrictInt = Field(default=0, ge=0)
    last_served_at: UtcDateTime | None = None
    created_at: UtcDateTime
    status: PoolStatus = "ACTIVE"
    retired_at: UtcDateTime | None = None
    retired_reason: StrictStr | None = Field(default=None, max_length=500)
    near_duplicate_of: UUID | None = None
    vector_state: VectorState = "PENDING"
    version: StrictInt = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.PK != pool_pk(self.pool_question_id):
            raise ValueError("PK does not match pool_question_id")
        if (self.question is None) == (self.question_ref is None):
            raise ValueError("exactly one of question and question_ref is required")
        if (self.status == "RETIRED") != (self.retired_at is not None):
            raise ValueError("retired_at is set exactly when status is RETIRED")
        if self.GSI1PK is not None and self.GSI1PK != poolkey(self.style, self.question_type, self.difficulty_band):
            raise ValueError("GSI1PK does not match style, question_type and difficulty_band")
        if self.GSI1SK is not None and not self.GSI1SK.startswith(f"{self.status}#"):
            raise ValueError("GSI1SK does not start with the status")
        if self.GSI2PK is not None and self.GSI2PK != pool_status_pk(self.status):
            raise ValueError("GSI2PK does not match status")
        return self

    @classmethod
    def build(cls, *, pool_id: Any, created_at: str, **attrs: Any) -> Self:
        """A new item with its primary key and both GSI key pairs derived from the attributes."""
        style, qtype, band = attrs["style"], attrs["question_type"], attrs.get("difficulty_band")
        status, served = attrs.get("status", "ACTIVE"), attrs.get("times_served", 0)
        return cls(PK=pool_pk(pool_id), SK="POOL", pool_question_id=pool_id, created_at=created_at,
                   GSI1PK=poolkey(style, qtype, band), GSI1SK=pool_gsi1sk(status, served, pool_id),
                   GSI2PK=pool_status_pk(status), GSI2SK=f"{created_at}#{pool_id}", **attrs)


class PoolQuestionRow(DdbItem):
    """A POOL_QUESTION as a GSI returns it (INCLUDE projection: no ``question``, ``content_hash`` or ``version``). Unregistered: it only
    exists so a typed query through GSI1/GSI2 does not fail validation; full items are read with ``PoolQuestion``."""

    CTX: ClassVar[str] = "exam"
    TYPE: ClassVar[str] = "POOL_QUESTION"
    type: Literal["POOL_QUESTION"] = "POOL_QUESTION"
    PK: str = Field(pattern=f"^POOL#{_UUID}$")
    SK: str = Field(pattern="^POOL$")
    style: StrictStr
    question_type: StrictStr
    difficulty_band: StrictStr | None = None
    topic_key: StrictStr = ""
    concept_slugs: list[StrictStr] | None = None
    times_served: StrictInt = 0
    created_at: UtcDateTime
    status: PoolStatus

    @property
    def pool_id(self) -> str:
        return self.PK.split("#", 1)[1]


# ------------------------------------------------------------------------------------------------ sentinel, concept index, history

class PoolUniqueHash(DdbItem, ctx="exam", item_type="UNIQUE_CONTENT_HASH"):
    """``UNIQUE#content_hash#<sha256>``: the pool's UNIQUE (content_hash). Written by ``ddb.sentinel_put``; the migration wrote the
    same item with type ``UNIQUE`` (see ``PoolUniqueHashMigrated``), so both read through this model."""

    type: Literal["UNIQUE_CONTENT_HASH", "UNIQUE"] = "UNIQUE_CONTENT_HASH"
    PK: str = Field(pattern="^UNIQUE#content_hash#[0-9a-f]{64}$")
    SK: str = Field(pattern="^UNIQUE$")
    pool_question_id: UUID


class PoolUniqueHashMigrated(PoolUniqueHash, ctx="exam", item_type="UNIQUE"):
    type: Literal["UNIQUE"] = "UNIQUE"


class PoolConcept(DdbItem, ctx="exam", item_type="POOL_CONCEPT"):
    """One index item per (concept slug, pool question): ``Query PK=POOLCONCEPT#<slug>, SK begins_with '<style>#<qtype>#<band>#'``.
    ``status`` is kept in sync with the pool item by ``set_pool_status``."""

    type: Literal["POOL_CONCEPT"] = "POOL_CONCEPT"
    PK: str = Field(pattern="^POOLCONCEPT#.+$")
    SK: str = Field(pattern=f"^[A-Z_]+#(MCQ|FREE_TEXT|PROOF)#(easy|medium|hard|very_hard|NONE)#{_UUID}$")
    pool_question_id: UUID
    concept_slug: StrictStr = Field(min_length=1, max_length=200)
    status: PoolStatus

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.PK != concept_pk(self.concept_slug):
            raise ValueError("PK does not match concept_slug")
        if not self.SK.endswith(f"#{self.pool_question_id}"):
            raise ValueError("SK does not end with pool_question_id")
        return self


class PoolServed(DdbItem, ctx="exam", item_type="POOL_SERVED"):
    """``STUDENT#<sid>`` / ``POOLSERVED#<pool_id>``: the pool question reached this learner (served from the pool, or written back
    from this learner's paper). Its existence is the exclusion rule of the match; the ``first_*`` attributes never change."""

    type: Literal["POOL_SERVED"] = "POOL_SERVED"
    PK: str = Field(pattern=f"^STUDENT#{_UUID}$")
    SK: str = Field(pattern=f"^POOLSERVED#{_UUID}$")
    student_id: UUID
    pool_question_id: UUID
    first_quiz_id: UUID | None = None
    first_served_at: UtcDateTime
    origin: ServedOrigin

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.SK != served_sk(self.pool_question_id):
            raise ValueError("SK does not match pool_question_id")
        return self


def content_hash_of(prompt_text: str) -> str:
    """sha256 of the whitespace/case-normalised prompt: the same value as ``quiz_runtime._pool_content_hash``."""
    return hashlib.sha256(normalize_prompt(prompt_text).encode("utf-8")).hexdigest()


def normalize_prompt(prompt_text: str) -> str:
    return " ".join(prompt_text.lower().split())


_UUID_RE = re.compile(f"^{_UUID}$")


def is_uuid(value: Any) -> bool:
    return isinstance(value, str) and bool(_UUID_RE.match(value))
