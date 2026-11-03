"""Pydantic foundation for DynamoDB items and their JSON content (requirement 71 §2.10).

Every DynamoDB item and every S3 JSON document the service reads or writes has a pydantic model:

* ``DdbItem`` - one subclass per ``(table context, item type)``, registered by ``__pydantic_init_subclass__``.
  The generated subclasses live in ``models/ddb/<ctx>.py``; hand-written refinements go in ``models/overrides.py``.
* ``S3Ref`` - the ``<attr>_ref`` pointer written by the offload rule, validated (64-hex SHA-256, non-negative size).
* ``JsonDoc`` - base of the models for S3 JSON documents (release snapshots, catalogue snapshots, offloaded
  attributes) in ``models/docs/``.

Rules (all enforced by tests and by ``python -m mathbank_rest.models.validate``):
  1. Writes are strict: ``to_item()`` rejects attributes the model does not declare, so schema drift cannot be written.
  2. Reads are lenient: unknown attributes are kept in ``model_extra`` so a newer writer never breaks an older reader.
  3. ``to_item()`` is lossless: ``Model.from_item(raw).to_item() == raw`` for every migrated item.
  4. An attribute is either inline or offloaded (``<attr>_ref``), never both; ``resolve()`` returns it typed.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from typing import Annotated, Any, ClassVar, Self, TypeVar

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    TypeAdapter,
    ValidationError,
    model_validator,
)
from pydantic_core import PydanticUndefined

from mathbank_rest.stores.errors import ItemSchemaError

T = TypeVar("T")

REF_SUFFIX = "_ref"
SHA256_RE = r"^[0-9a-f]{64}$"
KEY_ATTRS = frozenset({"PK", "SK", "type", "version", "ttl"})
_GSI_ATTR = re.compile(r"^GSI\d+(PK|SK)$")


# ------------------------------------------------------------------ scalar types

def _parse_ts(v: Any) -> Any:
    if isinstance(v, dt.datetime):
        return v if v.tzinfo else v.replace(tzinfo=dt.UTC)
    if isinstance(v, str):
        parsed = dt.datetime.fromisoformat(v)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.UTC)
    return v


def _fmt_ts(v: dt.datetime) -> str:
    """The migration's canonical form: UTC, microseconds, trailing Z (``spec.iso``)."""
    return v.astimezone(dt.UTC).replace(tzinfo=None).isoformat(timespec="microseconds") + "Z"


UtcDateTime = Annotated[dt.datetime, BeforeValidator(_parse_ts), PlainSerializer(_fmt_ts, return_type=str)]
"""ISO-8601 string in DynamoDB/JSON, timezone-aware ``datetime`` in Python."""

Sha256 = Annotated[str, Field(pattern=SHA256_RE)]


class S3Ref(BaseModel):
    """Pointer to an offloaded object: ``{bucket, key, sha256, bytes, content_type}`` (stores/ddb.offload_attr)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bucket: str = Field(min_length=3)
    key: str = Field(min_length=1)
    sha256: Sha256
    bytes: int = Field(ge=0)
    content_type: str = "application/json"


# ------------------------------------------------------------------ items

ITEM_MODELS: dict[tuple[str, str], type[DdbItem]] = {}


class DdbItem(BaseModel):
    """Common shape of every item: ``PK``/``SK``, the ``type`` discriminator, optional ``version`` (CAS), ``ttl``
    and the GSI key attributes. Subclasses declare ``ctx`` and ``item_type`` as class keywords::

        class LearnerProfile(DdbItem, ctx="learner", item_type="PROFILE"): ...
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True, validate_assignment=True, protected_namespaces=())

    CTX: ClassVar[str] = ""
    TYPE: ClassVar[str] = ""
    OFFLOADED: ClassVar[frozenset[str]] = frozenset()       # attributes that may live in S3 as <attr>_ref
    OFFLOAD_DOCS: ClassVar[dict[str, type[BaseModel] | Any]] = {}   # attr -> pydantic type of the offloaded JSON

    PK: str = Field(min_length=1, max_length=2048)
    SK: str = Field(min_length=1, max_length=1024)
    type: str
    version: int | None = Field(default=None, ge=0)
    ttl: int | None = Field(default=None, ge=0)
    updated_at: UtcDateTime | None = None          # written by ddb.cas_update on every mutation
    GSI1PK: str | None = None
    GSI1SK: str | None = None
    GSI2PK: str | None = None
    GSI2SK: str | None = None
    GSI3PK: str | None = None
    GSI3SK: str | None = None

    def __init_subclass__(cls, *, ctx: str | None = None, item_type: str | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if ctx and item_type:
            cls.CTX, cls.TYPE = ctx, item_type
            ITEM_MODELS[(ctx, item_type)] = cls       # a later (hand-written) subclass replaces the generated one

    @model_validator(mode="after")
    def _inline_xor_offloaded(self) -> DdbItem:
        extra = self.model_extra or {}
        for attr in self.OFFLOADED:
            has_ref = getattr(self, attr + REF_SUFFIX, None) is not None or (attr + REF_SUFFIX) in extra
            has_val = getattr(self, attr, None) is not None or attr in extra
            if has_ref and has_val:
                raise ValueError(f"{attr} is both inline and offloaded ({attr}{REF_SUFFIX})")
        return self

    # -------------------------------------------------------------- codec

    @classmethod
    def from_item(cls, raw: dict) -> Self:
        """Validate a decoded DynamoDB item. Unknown attributes are kept (rule 2)."""
        try:
            return cls.model_validate(raw)
        except ValidationError as exc:
            raise _schema_error(cls.__name__, raw, exc) from None

    def model_post_init(self, _context: Any, /) -> None:
        # defaults that are not None (``type``, hand-written refinements) are part of the item even when not passed
        for name, f in type(self).model_fields.items():
            if f.default is not PydanticUndefined and f.default is not None:
                self.model_fields_set.add(name)

    def to_item(self, *, strict: bool = True) -> dict:
        """DynamoDB-ready dict: JSON-mode dump of what was set (a nested ``null`` that was stored stays, one that was
        never set is not invented), top-level ``None`` dropped, and (strict) no undeclared attributes (rule 1)."""
        if strict and self.model_extra:
            raise ItemSchemaError(f"{type(self).__name__} has undeclared attributes {sorted(self.model_extra)}",
                                  model=type(self).__name__, extra=sorted(self.model_extra))
        d = self.model_dump(mode="json", by_alias=True, exclude_unset=True)
        return {k: v for k, v in d.items() if v is not None}

    # -------------------------------------------------------------- offloaded JSON

    def ref(self, attr: str) -> S3Ref | None:
        v = getattr(self, attr + REF_SUFFIX, None)
        if v is None and self.model_extra:
            v = self.model_extra.get(attr + REF_SUFFIX)
        return None if v is None else v if isinstance(v, S3Ref) else S3Ref.model_validate(v)

    def resolve(self, attr: str, model: Any = None) -> Any:
        """The attribute's value, typed: the inline value or the S3 object (size and SHA-256 verified). ``model`` is
        a pydantic model / type; default is the generated document model for this attribute, else plain JSON."""
        model = model or self.OFFLOAD_DOCS.get(attr)
        inline = getattr(self, attr, None)
        if inline is None and self.model_extra:
            inline = self.model_extra.get(attr)
        if inline is not None:
            return _typed(model, inline, f"{type(self).__name__}.{attr}")
        ref = self.ref(attr)
        if ref is None:
            return None
        from mathbank_rest.stores import ddb  # local: ddb imports nothing from models

        raw = json.loads(ddb.resolve_ref(ref.model_dump()))
        return _typed(model, raw, f"{type(self).__name__}.{attr}")


def _typed(model: Any, raw: Any, what: str) -> Any:
    if model is None:
        return raw
    try:
        return TypeAdapter(model).validate_python(raw)
    except ValidationError as exc:
        raise _schema_error(what, raw, exc) from None


def _schema_error(what: str, raw: Any, exc: ValidationError) -> ItemSchemaError:
    errs = [{"loc": ".".join(str(p) for p in e["loc"]), "type": e["type"], "msg": e["msg"]} for e in exc.errors()[:5]]
    ident = {k: raw.get(k) for k in ("PK", "SK") if isinstance(raw, dict) and k in raw}
    return ItemSchemaError(f"{what} failed validation ({exc.error_count()} errors)", model=what, errors=errs, **ident)


# ------------------------------------------------------------------ JSON documents

class JsonDoc(BaseModel):
    """Base of the models for S3 JSON documents and nested JSON records. Lenient on read like ``DdbItem``."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, protected_namespaces=())

    def to_json(self, *, strict: bool = True) -> dict:
        if strict and self.model_extra:
            raise ItemSchemaError(f"{type(self).__name__} has undeclared attributes {sorted(self.model_extra)}",
                                  model=type(self).__name__, extra=sorted(self.model_extra))
        return self.model_dump(mode="json", by_alias=True, exclude_unset=True)


# ------------------------------------------------------------------ registry access

def model_for(ctx: str, item_type: str) -> type[DdbItem] | None:
    _load_models()
    return ITEM_MODELS.get((ctx, item_type))


def parse_item(ctx: str, raw: dict) -> DdbItem:
    """Validate a decoded item with the model registered for ``(ctx, raw["type"])``."""
    m = model_for(ctx, raw.get("type", ""))
    if m is None:
        raise ItemSchemaError(f"no model for {ctx}/{raw.get('type')!r}", ctx=ctx, item_type=raw.get("type"))
    return m.from_item(raw)


def is_key_attr(name: str) -> bool:
    return name in KEY_ATTRS or bool(_GSI_ATTR.match(name))


_loaded = False


def _load_models() -> None:
    """Import the generated modules and the overrides exactly once (they register themselves); ``models/manual`` holds the hand-written ones."""
    global _loaded
    if _loaded:
        return
    import importlib
    import pkgutil

    import mathbank_rest.models.ddb as gen
    from mathbank_rest.models import manual

    for pkg in (gen, manual):
        for mod in pkgutil.iter_modules(pkg.__path__):
            importlib.import_module(f"{pkg.__name__}.{mod.name}")
    importlib.import_module("mathbank_rest.models.overrides")
    _loaded = True
