"""Shared DynamoDB / S3 toolkit for the store layer (requirement 71 §2.3).

Everything a ``stores/<context>/dynamodb.py`` needs so that no store re-implements concurrency, uniqueness,
pagination, idempotency or S3 offload. Rules enforced here (requirement 70 §5):

* every mutable item carries ``version``; updates are conditional on it (``cas_update``)
* UNIQUE constraints are sentinel items written in the same transaction (``sentinel_put``)
* multi-item effects use one ``TransactWriteItems`` with cancellation reasons mapped to domain errors
* ``Idempotency-Key`` handling writes the receipt **in the same transaction** as the effect
* list endpoints return an HMAC-signed opaque ``next_token`` — never a raw ``LastEvaluatedKey``
* large attributes live in S3 as ``<attr>_ref = {bucket,key,sha256,bytes,content_type}`` with the same key
  layout as the migration (student-owned objects under ``offload/<table>/students/<sid>/…``)
* there is deliberately **no scan helper**: request paths must not scan (a lint test enforces it)
"""
from __future__ import annotations

import base64
import dataclasses
import datetime as dt
import decimal
import hashlib
import hmac
import json
import logging
import math
import os
import random
import threading
import time
import uuid
from collections.abc import Callable, Iterable
from typing import Any

from boto3.dynamodb.types import Binary, TypeDeserializer, TypeSerializer
from botocore.config import Config
from botocore.exceptions import ClientError

from mathbank_rest.config import settings
from mathbank_rest.stores.errors import (
    ConditionFailed,
    IdempotencyKeyReused,
    InvalidToken,
    NotFound,
    RevisionConflict,
    StoreError,
    StoreUnavailable,
    UniqueViolation,
)

LOG = logging.getLogger("mathbank_rest.stores.ddb")

OFFLOAD_THRESHOLD = 16 * 1024
REF_SUFFIX = "_ref"
MAX_ITEM_BYTES = 350_000
_SER, _DES = TypeSerializer(), TypeDeserializer()

# ------------------------------------------------------------------ clients and names

_clients: dict[tuple, Any] = {}
_lock = threading.Lock()
_account: str | None = None


def _cfg(service: str = "dynamodb") -> Config:
    kw: dict[str, Any] = {"retries": {"max_attempts": 10, "mode": "adaptive"}, "max_pool_connections": 32}
    if service == "s3":
        # SigV4 + virtual-hosted addressing: presigned URLs use the regional host
        # (bucket.s3.<region>.amazonaws.com). botocore's default would presign against the global
        # bucket.s3.amazonaws.com, which answers 307 for buckets outside us-east-1.
        kw["signature_version"] = "s3v4"
        kw["s3"] = {"addressing_style": "virtual"}
    return Config(**kw)


def _make(service: str):
    import boto3

    kw: dict[str, Any] = {"region_name": settings.ddb_region, "config": _cfg(service)}
    if settings.ddb_endpoint_url and service in ("dynamodb",):
        kw["endpoint_url"] = settings.ddb_endpoint_url
    return boto3.client(service, **kw)


def client(service: str = "dynamodb"):
    key = (service, settings.ddb_region, settings.ddb_endpoint_url if service == "dynamodb" else "")
    with _lock:
        if key not in _clients:
            _clients[key] = _make(service)
        return _clients[key]


def reset_clients() -> None:
    """Tests: drop cached clients (e.g. after switching a moto mock on/off)."""
    global _account
    with _lock:
        _clients.clear()
        _account = None


def table_name(ctx: str) -> str:
    return f"mb-{ctx.replace('_', '-')}-{settings.ddb_env}"


def account_id() -> str:
    global _account
    if _account is None:
        _account = client("sts").get_caller_identity()["Account"]
    return _account


def data_bucket() -> str:
    return settings.data_bucket or f"mathbank-data-{settings.ddb_env}-{account_id()}"


def content_bucket() -> str:
    return settings.content_bucket or f"mathbank-content-{settings.ddb_env}-{account_id()}"


# ------------------------------------------------------------------ keys, time, ids

def student_pk(student_id: Any) -> str:
    return f"STUDENT#{student_id}"


def unique_key(field: str, value: Any) -> tuple[str, str]:
    return f"UNIQUE#{field}#{value}", "UNIQUE"


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None).isoformat(timespec="microseconds") + "Z"


def epoch_after(days: float) -> int:
    return int(time.time() + days * 86400)


def uuid7() -> str:
    """Time-ordered UUID (RFC 9562 v7): lexicographic order == creation order, good sort keys."""
    ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand = int.from_bytes(os.urandom(10), "big") & ((1 << 74) - 1)   # 12 bits rand_a + 62 bits rand_b
    v = (ms << 80) | (0x7 << 76) | ((rand >> 62) << 64) | (0b10 << 62) | (rand & ((1 << 62) - 1))
    return str(uuid.UUID(int=v))


# ------------------------------------------------------------------ value conversion

def encode(v: Any) -> Any:
    """Python value → DynamoDB-safe Python value (no float, UUID→str, datetime→ISO-8601 'Z', sets→sorted lists)."""
    if v is None or isinstance(v, (str, bool, int, decimal.Decimal, bytes, bytearray)):
        return bytes(v) if isinstance(v, bytearray) else v
    if isinstance(v, float):
        return str(v) if math.isnan(v) or math.isinf(v) else decimal.Decimal(repr(v))
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, dt.datetime):
        if v.tzinfo is not None:
            v = v.astimezone(dt.UTC).replace(tzinfo=None)
        return v.isoformat(timespec="microseconds") + "Z"
    if isinstance(v, (dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, dict):
        return {str(k): encode(x) for k, x in v.items() if x is not None}
    if isinstance(v, (list, tuple)):
        return [encode(x) for x in v]
    if isinstance(v, (set, frozenset)):
        return [encode(x) for x in sorted(v, key=str)]
    return str(v)


def encode_item(item: dict) -> dict:
    return {k: encode(v) for k, v in item.items() if v is not None}


def decode(v: Any) -> Any:
    if isinstance(v, decimal.Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, Binary):
        return bytes(v.value)
    if isinstance(v, dict):
        return {k: decode(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [decode(x) for x in v]
    if isinstance(v, (set, frozenset)):
        return [decode(x) for x in v]
    return v


def _ser_map(d: dict) -> dict:
    return {k: _SER.serialize(encode(v)) for k, v in d.items()}


def _des_item(raw: dict) -> dict:
    return decode({k: _DES.deserialize(v) for k, v in raw.items()})


# ------------------------------------------------------------------ conditions and operations

@dataclasses.dataclass(frozen=True)
class Cond:
    """A condition expression with its placeholders, e.g. Cond("#v = :v", {"#v": "version"}, {":v": 3})."""

    expr: str
    names: dict[str, str] = dataclasses.field(default_factory=dict)
    values: dict[str, Any] = dataclasses.field(default_factory=dict)


NOT_EXISTS = Cond("attribute_not_exists(PK)")
EXISTS = Cond("attribute_exists(PK)")


def version_is(expected: int) -> Cond:
    return Cond("#ver = :ev", {"#ver": "version"}, {":ev": expected})


@dataclasses.dataclass
class TxOp:
    """One element of a TransactWriteItems. `conflict` is raised when THIS op's condition fails."""

    kind: str                                   # put | update | delete | check
    ctx: str
    item: dict | None = None                    # put
    pk: str | None = None
    sk: str | None = None
    update: str | None = None                   # update expression
    cond: Cond | None = None
    names: dict[str, str] = dataclasses.field(default_factory=dict)
    values: dict[str, Any] = dataclasses.field(default_factory=dict)
    conflict: StoreError | None = None
    label: str = ""


def Put(ctx: str, item: dict, cond: Cond | None = None, conflict: StoreError | None = None, label: str = "") -> TxOp:
    return TxOp("put", ctx, item=item, cond=cond, conflict=conflict, label=label)


def Update(ctx: str, pk: str, sk: str, update: str, *, names=None, values=None, cond: Cond | None = None,
           conflict: StoreError | None = None, label: str = "") -> TxOp:
    return TxOp("update", ctx, pk=pk, sk=sk, update=update, names=names or {}, values=values or {}, cond=cond,
                conflict=conflict, label=label)


def Delete(ctx: str, pk: str, sk: str, cond: Cond | None = None, conflict: StoreError | None = None, label: str = "") -> TxOp:
    return TxOp("delete", ctx, pk=pk, sk=sk, cond=cond, conflict=conflict, label=label)


def Check(ctx: str, pk: str, sk: str, cond: Cond, conflict: StoreError | None = None, label: str = "") -> TxOp:
    return TxOp("check", ctx, pk=pk, sk=sk, cond=cond, conflict=conflict, label=label)


def sentinel_put(ctx: str, field: str, value: Any, owner: dict | None = None, *, ttl: int | None = None) -> TxOp:
    """Uniqueness sentinel (replaces a PostgreSQL UNIQUE): fails with UniqueViolation(field) when taken."""
    pk, sk = unique_key(field, value)
    item = {"PK": pk, "SK": sk, "type": f"UNIQUE_{field.upper()}", "version": 1, **(owner or {})}
    if ttl:
        item["ttl"] = ttl
    return Put(ctx, item, NOT_EXISTS, UniqueViolation(field, str(value)), label=f"unique:{field}")


def _cond_kwargs(cond: Cond | None, names: dict, values: dict) -> dict:
    out: dict[str, Any] = {}
    n, v = dict(names), dict(values)
    if cond is not None:
        out["ConditionExpression"] = cond.expr
        n.update(cond.names)
        v.update(cond.values)
    if n:
        out["ExpressionAttributeNames"] = n
    if v:
        out["ExpressionAttributeValues"] = _ser_map(v)
    return out


def _tx_item(op: TxOp) -> dict:
    t = table_name(op.ctx)
    key = lambda: {"PK": {"S": op.pk}, "SK": {"S": op.sk}}
    if op.kind == "put":
        d = {"TableName": t, "Item": _ser_map(op.item), **_cond_kwargs(op.cond, {}, {})}
        return {"Put": d}
    if op.kind == "update":
        return {"Update": {"TableName": t, "Key": key(), "UpdateExpression": op.update,
                           **_cond_kwargs(op.cond, op.names, op.values)}}
    if op.kind == "delete":
        return {"Delete": {"TableName": t, "Key": key(), **_cond_kwargs(op.cond, {}, {})}}
    return {"ConditionCheck": {"TableName": t, "Key": key(), **_cond_kwargs(op.cond, {}, {})}}


_RETRYABLE_TX = {"TransactionConflict", "ThrottlingError", "ProvisionedThroughputExceeded"}


def transact(ops: list[TxOp], *, token: str | None = None, attempts: int = 5) -> None:
    """One TransactWriteItems (≤100 items). Maps cancellation reasons to the failing op's `conflict`
    (default ConditionFailed). Retries transaction conflicts with jitter."""
    if not ops:
        return
    if len(ops) > 100:
        raise StoreError(f"transaction has {len(ops)} items; DynamoDB allows 100", ops=len(ops))
    items = [_tx_item(o) for o in ops]
    ddb = client()
    for attempt in range(attempts):
        try:
            kw = {"TransactItems": items}
            if token:
                kw["ClientRequestToken"] = token[:36]
            ddb.transact_write_items(**kw)
            return
        except ClientError as exc:
            err = exc.response.get("Error", {})
            if err.get("Code") != "TransactionCanceledException":
                raise
            reasons = exc.response.get("CancellationReasons") or []
            codes = {r.get("Code") for r in reasons}
            for i, r in enumerate(reasons):
                if r.get("Code") == "ConditionalCheckFailed":
                    raise (ops[i].conflict or ConditionFailed(ops[i].label or "transaction condition failed",
                                                              op=ops[i].label)) from None
            if codes & _RETRYABLE_TX and attempt < attempts - 1:
                time.sleep(min(0.05 * 2 ** attempt, 1.0) * (0.5 + random.random()))
                continue
            if codes & _RETRYABLE_TX:
                raise StoreUnavailable("transaction conflict; retry") from None
            raise StoreError(f"transaction cancelled: {sorted(c for c in codes if c)}") from None


# ------------------------------------------------------------------ single-item operations

def get_item(ctx: str, pk: str, sk: str, *, consistent: bool = True) -> dict | None:
    r = client().get_item(TableName=table_name(ctx), Key={"PK": {"S": pk}, "SK": {"S": sk}}, ConsistentRead=consistent)
    return _des_item(r["Item"]) if "Item" in r else None


def batch_get(ctx: str, keys: Iterable[tuple[str, str]], *, consistent: bool = True) -> list[dict]:
    """BatchGetItem in chunks of 100 with unprocessed-key retry; missing items are simply absent."""
    keys = list(dict.fromkeys(keys))
    out, name, ddb = [], table_name(ctx), client()
    for i in range(0, len(keys), 100):
        req = {name: {"Keys": [{"PK": {"S": p}, "SK": {"S": s}} for p, s in keys[i:i + 100]], "ConsistentRead": consistent}}
        delay = 0.05
        while req:
            r = ddb.batch_get_item(RequestItems=req)
            out += [_des_item(x) for x in r.get("Responses", {}).get(name, [])]
            req = r.get("UnprocessedKeys") or {}
            if req:
                time.sleep(delay)
                delay = min(delay * 2, 2)
    return out


def put_item(ctx: str, item: dict, cond: Cond | None = None, conflict: StoreError | None = None) -> None:
    try:
        client().put_item(TableName=table_name(ctx), Item=_ser_map(item), **_cond_kwargs(cond, {}, {}))
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise (conflict or ConditionFailed("put condition failed")) from None
        raise


def cas_update(ctx: str, pk: str, sk: str, expected_version: int, set_values: dict | None = None, *,
               remove: Iterable[str] = (), cond: Cond | None = None, now: str | None = None) -> dict:
    """UPDATE ... SET <values>, version = version + 1, updated_at = :now WHERE version = :expected.
    Raises NotFound if the item is absent, RevisionConflict(current_revision) if the version moved,
    ConditionFailed if the extra `cond` fails. Returns the new item."""
    names, values, sets = {"#ver": "version", "#upd": "updated_at"}, {":ev": expected_version, ":one": 1, ":now": now or now_iso()}, []
    for i, (k, v) in enumerate((set_values or {}).items()):
        if k in ("PK", "SK", "version", "updated_at"):
            raise ValueError(f"cas_update cannot set {k}")
        names[f"#a{i}"], values[f":a{i}"] = k, v
        sets.append(f"#a{i} = :a{i}")
    sets += ["#ver = #ver + :one", "#upd = :now"]
    expr = "SET " + ", ".join(sets)
    rm = [f"#r{i}" for i, _ in enumerate(remove)]
    for i, k in enumerate(remove):
        names[f"#r{i}"] = k
    if rm:
        expr += " REMOVE " + ", ".join(rm)
    guard = Cond("attribute_exists(PK) AND #ver = :ev" + (f" AND ({cond.expr})" if cond else ""),
                 cond.names if cond else {}, cond.values if cond else {})
    kw = _cond_kwargs(guard, names, values)
    try:
        r = client().update_item(TableName=table_name(ctx), Key={"PK": {"S": pk}, "SK": {"S": sk}}, UpdateExpression=expr,
                                 ReturnValues="ALL_NEW", ReturnValuesOnConditionCheckFailure="ALL_OLD", **kw)
        return _des_item(r["Attributes"])
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        old = exc.response.get("Item")
        if not old:
            raise NotFound(f"{ctx}: {pk} {sk}") from None
        cur = _des_item(old)
        if int(cur.get("version", 0)) != expected_version:
            raise RevisionConflict(int(cur.get("version", 0))) from None
        raise ConditionFailed("update condition failed") from None


# ------------------------------------------------------------------ pagination

def _token_key() -> bytes:
    secret = settings.next_token_secret.get_secret_value() or hmac.new(
        settings.jwt_secret.encode(), b"mathbank-next-token", hashlib.sha256).hexdigest()
    return secret.encode()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign_token(payload: dict, ttl_seconds: int = 3600) -> str:
    body = _b64(json.dumps({**payload, "exp": int(time.time()) + ttl_seconds}, sort_keys=True, separators=(",", ":")).encode())
    return f"{body}.{_b64(hmac.new(_token_key(), body.encode(), hashlib.sha256).digest())}"


def verify_token(token: str, **bound: Any) -> dict:
    """Validate signature and expiry and that every `bound` field equals the token's (table/index/partition)."""
    try:
        body, sig = token.split(".", 1)
        if not hmac.compare_digest(_unb64(sig), hmac.new(_token_key(), body.encode(), hashlib.sha256).digest()):
            raise ValueError("signature")
        payload = json.loads(_unb64(body))
        if payload["exp"] < time.time():
            raise ValueError("expired")
        for k, v in bound.items():
            if payload.get(k) != v:
                raise ValueError(f"bound:{k}")
        return payload
    except (ValueError, KeyError, json.JSONDecodeError):
        raise InvalidToken("invalid or expired next_token") from None


def query_page(ctx: str, pk: str, *, index: str | None = None, sk_begins: str | None = None,
               sk_between: tuple[str, str] | None = None, forward: bool = True, limit: int = 50,
               next_token: str | None = None, consistent: bool | None = None) -> dict:
    """Key-condition query of one partition (or one GSI partition). Returns {"items": [...], "next_token": str|None}.
    `limit` is capped at 200 (guide §5). The token is bound to table, index and partition."""
    limit = max(1, min(int(limit), 200))
    pk_attr, sk_attr = (f"{index}PK", f"{index}SK") if index else ("PK", "SK")
    names, values, cond = {"#pk": pk_attr}, {":pk": pk}, "#pk = :pk"
    if sk_begins is not None:
        names["#sk"], values[":sb"], cond = sk_attr, sk_begins, cond + " AND begins_with(#sk, :sb)"
    elif sk_between is not None:
        names["#sk"], values[":lo"], values[":hi"] = sk_attr, sk_between[0], sk_between[1]
        cond += " AND #sk BETWEEN :lo AND :hi"
    kw: dict[str, Any] = {"TableName": table_name(ctx), "KeyConditionExpression": cond, "ExpressionAttributeNames": names,
                          "ExpressionAttributeValues": _ser_map(values), "Limit": limit, "ScanIndexForward": forward}
    if index:
        kw["IndexName"] = index
    elif consistent is not False:
        kw["ConsistentRead"] = True
    if next_token:
        p = verify_token(next_token, t=table_name(ctx), i=index or "", p=pk, f=forward)
        kw["ExclusiveStartKey"] = {k: {"S": v} for k, v in p["k"].items()}
    r = client().query(**kw)
    nxt = None
    if r.get("LastEvaluatedKey"):
        lek = {k: v["S"] for k, v in r["LastEvaluatedKey"].items()}
        nxt = sign_token({"t": table_name(ctx), "i": index or "", "p": pk, "f": forward, "k": lek})
    return {"items": [_des_item(x) for x in r.get("Items", [])], "next_token": nxt}


# ------------------------------------------------------------------ S3 offload / references

def offload_key(table_ctx: str, item: dict, attr: str) -> str:
    """Same layout as mathbank-db/aws/dynamo/migrate.py so migrated and new objects share prefixes."""
    h = hashlib.sha256((item["PK"] + "|" + item["SK"]).encode()).hexdigest()
    sid = None
    if item["PK"].startswith("STUDENT#"):
        sid = item["PK"].split("#", 1)[1].split("#", 1)[0]
    else:
        sid = next((str(item[a]) for a in ("student_id", "linked_student_id", "owner_student_id")
                    if isinstance(item.get(a), str) and item[a]), None)
    table = table_ctx.replace("_", "-")
    if sid:
        return f"offload/{table}/students/{sid}/{item['type']}/{h}/{attr}.json"
    return f"offload/{table}/{item['type']}/{h[:2]}/{h}/{attr}.json"


def _json_bytes(obj: Any) -> bytes:
    def default(o):
        if isinstance(o, decimal.Decimal):
            return int(o) if o == o.to_integral_value() else float(o)
        if isinstance(o, (bytes, bytearray)):
            return base64.b64encode(bytes(o)).decode()
        return str(o)

    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=default).encode()


def offload_attr(ctx: str, item: dict, attr: str) -> dict:
    """Move one attribute to S3, replacing it with `<attr>_ref`. Returns the (mutated) item."""
    body = _json_bytes(item.pop(attr))
    digest = hashlib.sha256(body).hexdigest()
    key = offload_key(ctx, item, attr)
    bucket = data_bucket()
    client("s3").put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json", ChecksumAlgorithm="SHA256",
                            Metadata={"sha256": digest})
    item[f"{attr}{REF_SUFFIX}"] = {"bucket": bucket, "key": key, "sha256": digest, "bytes": len(body),
                                   "content_type": "application/json"}
    return item


def offload(ctx: str, item: dict, attrs: Iterable[str] = (), *, threshold: int = OFFLOAD_THRESHOLD) -> dict:
    """Policy: each listed attribute larger than `threshold` bytes → S3; then a 350 KB safety net."""
    for a in attrs:
        if a in item and len(_json_bytes(item[a])) > threshold:
            offload_attr(ctx, item, a)
    while len(_json_bytes(item)) > MAX_ITEM_BYTES:
        a = max((k for k in item if k not in ("PK", "SK", "type", "version") and not k.endswith(("PK", "SK", REF_SUFFIX))),
                key=lambda k: len(_json_bytes(item[k])))
        offload_attr(ctx, item, a)
    return item


def resolve_ref(ref: dict, *, verify: bool = True) -> bytes:
    """Fetch an offloaded object; verifies size and SHA-256 unless verify=False."""
    body = client("s3").get_object(Bucket=ref["bucket"], Key=ref["key"])["Body"].read()
    if verify:
        if "bytes" in ref and len(body) != int(ref["bytes"]):
            raise StoreError("offloaded object size mismatch", key=ref["key"])
        if hashlib.sha256(body).hexdigest() != ref["sha256"]:
            raise StoreError("offloaded object checksum mismatch", key=ref["key"])
    return body


def load_attr(item: dict, attr: str) -> Any:
    """The attribute's value whether inline or offloaded (JSON-decoded)."""
    if attr in item:
        return item[attr]
    ref = item.get(f"{attr}{REF_SUFFIX}")
    return json.loads(resolve_ref(ref)) if ref else None


def presign(ref: dict, expires: int = 300) -> str:
    """Short-lived download URL for learners (never expose raw bucket keys)."""
    return client("s3").generate_presigned_url("get_object", Params={"Bucket": ref["bucket"], "Key": ref["key"]},
                                               ExpiresIn=min(int(expires), 900))


# ------------------------------------------------------------------ idempotency

def request_hash(body: Any) -> str:
    return hashlib.sha256(_json_bytes(body)).hexdigest()


def run_idempotent(ctx: str, *, owner_pk: str, key: str, req_hash: str,
                   build: Callable[[], tuple[list[TxOp], Any]], ttl_days: float | None = None) -> tuple[Any, bool]:
    """Standard Idempotency-Key handling. `build()` returns (ops, response) and is called at most once per
    key. The receipt `IDEM#<key>` under `owner_pk` is written in the same transaction as the ops, so a
    crash can never leave an effect without its receipt (or vice versa). Returns (response, replayed).
    A different request body under the same key raises IdempotencyKeyReused (422)."""
    sk = f"IDEM#{key}"

    def replay(item: dict):
        if item.get("request_hash") != req_hash:
            raise IdempotencyKeyReused("Idempotency-Key was used with a different request")
        return load_attr(item, "response"), True

    existing = get_item(ctx, owner_pk, sk)
    if existing and existing.get("ttl", 1 << 62) > time.time():
        return replay(existing)
    ops, response = build()
    receipt = {"PK": owner_pk, "SK": sk, "type": "IDEM", "request_hash": req_hash, "response": response, "version": 1,
               "created_at": now_iso(), "ttl": epoch_after(ttl_days if ttl_days is not None else settings.idempotency_ttl_days)}
    offload(ctx, receipt, ("response",))
    race = ConditionFailed("idempotency receipt exists", op="idempotency")
    free = Cond("attribute_not_exists(PK) OR #t <= :now", {"#t": "ttl"}, {":now": int(time.time())})
    try:
        transact([*ops, Put(ctx, receipt, free, race, label="idempotency")])
    except ConditionFailed as exc:
        if exc is not race:
            raise
        winner = get_item(ctx, owner_pk, sk)
        if winner is None:
            raise
        return replay(winner)
    return response, False
