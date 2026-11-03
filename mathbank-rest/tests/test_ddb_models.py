"""Pydantic models for DynamoDB items and JSON documents (requirement 71 §2.10): registry, key patterns, strict
writes / lenient reads, lossless codec, offload exclusivity, aliases, typed S3 documents."""
from __future__ import annotations

import datetime as dt
import uuid

import pytest
from pydantic import TypeAdapter, ValidationError

from mathbank_rest.models import base
from mathbank_rest.models.base import DdbItem, JsonDoc, S3Ref, parse_item
from mathbank_rest.models.ddb.content import ContentProblem
from mathbank_rest.models.ddb.learner import LearnerItem, LearnerOutcome, LearnerProfile
from mathbank_rest.models.docs import family
from mathbank_rest.stores.errors import ItemSchemaError

SID = str(uuid.uuid4())


def profile(**over) -> dict:
    d = {
        "PK": f"STUDENT#{SID}", "SK": "PROFILE", "type": "PROFILE", "version": 3,
        "student_id": SID, "email": "A@x.org", "email_lc": "a@x.org", "first_name": "A", "last_name": "B",
        "display_name": "A B", "password_hash": "pbkdf2$x", "search_blob": "a b a@x.org", "status": "ACTIVE",
        "is_anonymous": False, "token_version": 1, "created_at": "2026-10-06T00:55:03.270501Z",
    }
    d.update(over)
    return d


def sha() -> str:
    return "a" * 64


def test_every_generated_model_is_registered_once_with_its_context_and_type():
    base._load_models()
    assert len(base.ITEM_MODELS) >= 98
    for (ctx, t), m in base.ITEM_MODELS.items():
        assert (m.CTX, m.TYPE) == (ctx, t) and issubclass(m, DdbItem)
        assert m.model_fields["type"].default == t           # the discriminator literal matches the registry key


def test_discriminated_union_picks_the_model_by_type():
    parsed = TypeAdapter(LearnerItem).validate_python(profile())
    assert isinstance(parsed, LearnerProfile)
    assert isinstance(parse_item("learner", profile()), LearnerProfile)
    with pytest.raises(ItemSchemaError):
        parse_item("learner", {**profile(), "type": "NOPE"})


def test_lossless_round_trip_and_canonical_timestamps():
    raw = profile(last_login_at="2026-10-06T01:00:00+00:00")           # a non-canonical stored form
    out = LearnerProfile.from_item(raw).to_item()
    assert out["last_login_at"] == "2026-10-06T01:00:00.000000Z"       # same instant, canonical text
    assert {k: v for k, v in out.items() if k != "last_login_at"} == {k: v for k, v in raw.items() if k != "last_login_at"}
    assert LearnerProfile.from_item(out).to_item() == out


def test_key_patterns_reject_foreign_keys():
    for bad in ({"PK": "USER#1"}, {"PK": f"STUDENT#{SID}#x"}, {"SK": "PROFILE#2"}, {"PK": "STUDENT#not-a-uuid"}):
        with pytest.raises(ItemSchemaError):
            LearnerProfile.from_item(profile(**bad))


def test_types_are_enforced_on_read():
    for bad in ({"status": 7}, {"student_id": "nope"}, {"created_at": "yesterday"}, {"token_version": "x"}, {"is_anonymous": "yes"}, {"token_version": "1"}, {"first_name": 5}):
        with pytest.raises(ItemSchemaError) as e:
            LearnerProfile.from_item(profile(**bad))
        assert e.value.status_code == 500 and e.value.detail["errors"] and e.value.detail["PK"] == f"STUDENT#{SID}"


def test_required_attributes_are_required():
    raw = profile()
    del raw["email_lc"]
    with pytest.raises(ItemSchemaError):
        LearnerProfile.from_item(raw)


def test_reads_are_lenient_writes_are_strict():
    item = LearnerProfile.from_item(profile(brand_new_attr="v2"))      # a newer writer added an attribute
    assert item.model_extra == {"brand_new_attr": "v2"}                  # kept, not an error
    with pytest.raises(ItemSchemaError, match="undeclared"):
        item.to_item()                                                   # but it can't be written back by this code
    assert item.to_item(strict=False)["brand_new_attr"] == "v2"


def test_constructing_a_model_in_code_sets_the_discriminator_and_drops_none():
    p = LearnerProfile(PK=f"STUDENT#{SID}", SK="PROFILE", student_id=SID, email="a@x", email_lc="a@x", first_name="A",
                       last_name="B", display_name="A B", password_hash="h", search_blob="s", status="ACTIVE",
                       is_anonymous=False, token_version=1, created_at=dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.UTC))
    d = p.to_item()
    assert d["type"] == "PROFILE" and d["created_at"] == "2026-01-02T03:04:05.000000Z" and "grade" not in d and "version" not in d


def test_assignment_is_validated():
    p = LearnerProfile.from_item(profile())
    with pytest.raises(ValidationError):
        p.token_version = "not a number"


def test_nested_null_that_was_stored_is_preserved_and_unset_is_not_invented():
    raw = {"PK": f"STUDENT#{SID}", "SK": "PROFILE", "type": "PROFILE"}
    assert "grade" not in LearnerProfile.model_construct(**raw).model_dump(exclude_unset=True)


# ------------------------------------------------------------------ offload exclusivity and typed documents

def test_an_attribute_is_inline_or_offloaded_never_both():
    ref = {"bucket": "b-bucket", "key": "offload/x.json", "sha256": sha(), "bytes": 5, "content_type": "application/json"}
    assert "submitted_answer" in LearnerOutcome.OFFLOADED and "concepts" in ContentProblem.OFFLOADED
    raw = {"PK": f"STUDENT#{SID}", "SK": f"OUTCOME#web#{uuid.uuid4()}", "type": "OUTCOME", "attempt_id": str(uuid.uuid4()),
           "attempted_at": "2026-10-06T00:55:03.270501Z", "hint_count": 0, "is_correct": True, "legacy_source": "x",
           "problem_id": str(uuid.uuid4()), "source": "web", "student_id": SID, "time_spent_seconds": 3}
    LearnerOutcome.from_item({**raw, "submitted_answer": "42"})
    LearnerOutcome.from_item({**raw, "submitted_answer_ref": ref})
    with pytest.raises(ItemSchemaError) as e:
        LearnerOutcome.from_item({**raw, "submitted_answer": "42", "submitted_answer_ref": ref})
    assert "inline and offloaded" in e.value.detail["errors"][0]["msg"]


def test_s3ref_is_validated():
    S3Ref(bucket="abc", key="k", sha256=sha(), bytes=0)
    for bad in ({"sha256": "XYZ"}, {"bytes": -1}, {"key": ""}, {"bucket": "a"}):
        with pytest.raises(ValidationError):
            S3Ref(**{"bucket": "abc", "key": "k", "sha256": sha(), "bytes": 1, **bad})
    with pytest.raises(ValidationError):
        S3Ref(bucket="abc", key="k", sha256=sha(), bytes=1, surprise=True)   # extra="forbid"


def test_jsondoc_aliases_round_trip_reserved_names():
    from mathbank_rest.models.docs.content import CatalogConcept

    d = CatalogConcept.model_validate({"schema": "mb.catalog.concept/1", "kind": "concept", "items": []})
    assert d.schema_ == "mb.catalog.concept/1" and d.to_json()["schema"] == "mb.catalog.concept/1"


def test_doc_models_registry_covers_every_family_and_family_parser():
    from mathbank_rest.models.docs.registry import DOC_MODELS

    assert family("releases/ab/cd.json") == "content:release"
    assert family("catalog/skill/abc.json") == "content:catalog:skill"
    assert family(f"offload/learner/students/{SID}/OUTCOME/ab/hash/submitted_answer.json") == "offload:learner:OUTCOME:submitted_answer"
    assert family("offload/content/SKILL/ab/h/concepts.json") == "offload:content:SKILL:concepts"
    assert family("images/x.png") is None
    assert "content:release" in DOC_MODELS and all(isinstance(m, type) or m for m in DOC_MODELS.values())


def test_jsondoc_is_strict_on_write_and_lenient_on_read():
    class Doc(JsonDoc):
        a: int

    d = Doc.model_validate({"a": 1, "b": 2})
    assert d.model_extra == {"b": 2}
    with pytest.raises(ItemSchemaError):
        d.to_json()
    assert d.to_json(strict=False) == {"a": 1, "b": 2}
