"""Typed access to DynamoDB: the toolkit's operations, but taking and returning pydantic models.

Reads validate every item into its model (``ItemSchemaError`` = 500 if stored data drifted); writes are strict
(undeclared attributes rejected), offload the model's ``OFFLOADED`` attributes through the one S3 offload rule, and
re-validate the final item so what reaches DynamoDB always satisfies the model. Updates validate each changed
attribute against the model's field type before the conditional write.

    from mathbank_rest.models.ddb.learner import LearnerProfile
    p = typed.require(LearnerProfile, student_pk(sid), "PROFILE")
    typed.update(LearnerProfile, p.PK, p.SK, p.version, {"status": "DISABLED"})
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError

from mathbank_rest.models import base
from mathbank_rest.models.base import DdbItem
from mathbank_rest.stores import ddb
from mathbank_rest.stores.errors import ConditionFailed, ItemSchemaError, NotFound, StoreError

M = TypeVar("M", bound=DdbItem)


class Page(BaseModel, Generic[M]):
    """One page of a key-condition query; ``next_token`` is the toolkit's signed, bound token."""

    items: list[M]
    next_token: str | None = None


# ------------------------------------------------------------------ reads

def get(model: type[M], pk: str, sk: str, *, consistent: bool = True) -> M | None:
    raw = ddb.get_item(model.CTX, pk, sk, consistent=consistent)
    return None if raw is None else model.from_item(raw)


def require(model: type[M], pk: str, sk: str, *, consistent: bool = True) -> M:
    found = get(model, pk, sk, consistent=consistent)
    if found is None:
        raise NotFound(f"{model.CTX}: {pk} {sk}")
    return found


def batch_get(model: type[M], keys: Iterable[tuple[str, str]], *, consistent: bool = True) -> list[M]:
    return [model.from_item(r) for r in ddb.batch_get(model.CTX, keys, consistent=consistent)]


def query(ctx: str | type[M], pk: str, *, models: Iterable[type[DdbItem]] | None = None, **kwargs: Any) -> Page[Any]:
    """Query one partition. With a model class the items are all that type; with a context name each item is parsed by
    its ``type`` attribute (optionally restricted to ``models``; any other type in the partition raises)."""
    if isinstance(ctx, type):
        page = ddb.query_page(ctx.CTX, pk, **kwargs)
        return Page(items=[ctx.from_item(r) for r in page["items"]], next_token=page["next_token"])
    allowed = {m.TYPE: m for m in models} if models else None
    page = ddb.query_page(ctx, pk, **kwargs)
    out: list[DdbItem] = []
    for raw in page["items"]:
        m = allowed.get(raw.get("type")) if allowed else base.model_for(ctx, raw.get("type", ""))
        if m is None:
            raise ItemSchemaError(f"unexpected item type {raw.get('type')!r} in {ctx} partition", ctx=ctx, item_type=raw.get("type"),
                                  PK=raw.get("PK"), SK=raw.get("SK"))
        out.append(m.from_item(raw))
    return Page(items=out, next_token=page["next_token"])


# ------------------------------------------------------------------ writes

def prepare(item: DdbItem) -> dict:
    """Strict dump → offload the model's large attributes → re-validate. The dict is ready for ``ddb.put_item``."""
    d = item.to_item()
    d = ddb.offload(item.CTX, d, item.OFFLOADED)
    type(item).from_item(d)                      # the offloaded shape (… _ref instead of the value) must still be valid
    return d


def put(item: DdbItem, *, cond: ddb.Cond | None = None, conflict: StoreError | None = None) -> None:
    ddb.put_item(item.CTX, prepare(item), cond, conflict)


def put_new(item: DdbItem, *, conflict: StoreError | None = None) -> None:
    """Create only: fails with ``conflict`` (default ``ConditionFailed``) when the key already exists."""
    put(item, cond=ddb.NOT_EXISTS, conflict=conflict or ConditionFailed(f"{item.CTX}: {item.PK} {item.SK} already exists"))


def tx_put(item: DdbItem, cond: ddb.Cond | None = None, conflict: StoreError | None = None, label: str = "") -> ddb.TxOp:
    """A transactional Put built from a model, for ``ddb.transact([...])``."""
    return ddb.Put(item.CTX, prepare(item), cond, conflict, label)


def _field_adapters(model: type[DdbItem]) -> dict[str, TypeAdapter]:
    cache = model.__dict__.get("_adapters")
    if cache is None:
        cache = {}
        for name, f in model.model_fields.items():
            tp = Annotated[(f.annotation, *f.metadata)] if f.metadata else f.annotation
            cache[f.alias or name] = TypeAdapter(tp)
            cache[name] = cache[f.alias or name]
        type.__setattr__(model, "_adapters", cache)
    return cache


def validate_changes(model: type[DdbItem], changes: dict[str, Any]) -> dict[str, Any]:
    """Validate each changed attribute against the model's field type; returns JSON-mode values ready for DynamoDB."""
    adapters, out = _field_adapters(model), {}
    for attr, value in changes.items():
        ad = adapters.get(attr)
        if ad is None:
            raise ItemSchemaError(f"{model.__name__} has no attribute {attr!r}", model=model.__name__, attr=attr)
        try:
            out[attr] = ad.dump_python(ad.validate_python(value), mode="json")
        except ValidationError as exc:
            raise ItemSchemaError(f"{model.__name__}.{attr} invalid", model=model.__name__, attr=attr,
                                  errors=[{"type": e["type"], "msg": e["msg"]} for e in exc.errors()[:3]]) from None
    return out


def update(model: type[M], pk: str, sk: str, expected_version: int, changes: dict[str, Any], *,
           remove: Iterable[str] = (), cond: ddb.Cond | None = None) -> M:
    """Optimistic-concurrency update of validated attributes; returns the new, re-validated item."""
    new = ddb.cas_update(model.CTX, pk, sk, expected_version, validate_changes(model, changes), remove=remove, cond=cond)
    return model.from_item(new)
