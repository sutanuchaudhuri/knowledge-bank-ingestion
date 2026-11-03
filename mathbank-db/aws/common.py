"""Shared configuration and helpers for the AWS migration scripts.

Source credentials come from the environment (NEON_PG_HOST/PORT/DATABASE/USER/PASSWORD), normally
loaded from the git-ignored mathbank-graph/remote.env by the Makefile targets. Nothing here writes to
PostgreSQL: every source session is forced read-only before the first query.
"""
from __future__ import annotations

import base64
import dataclasses
import datetime as dt
import decimal
import hashlib
import json
import logging
import os
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

LOG = logging.getLogger("mbaws")

REGION = os.environ.get("AWS_REGION", "us-east-2")
PROFILE = os.environ.get("AWS_PROFILE", "aws-sutanu-admin")
HERE = os.path.dirname(os.path.abspath(__file__))
RUN_DIR = os.path.join(os.path.dirname(HERE), "logs", "aws")


@dataclasses.dataclass(frozen=True)
class Env:
    name: str  # dev | prod

    def table(self, ctx: str) -> str:
        return f"mb-{ctx}-{self.name}"

    def bucket(self, kind: str) -> str:
        """kind: data | content. Account id keeps global bucket names unique."""
        return f"mathbank-{kind}-{self.name}-{account_id()}"

    @property
    def vector_bucket(self) -> str:
        return f"mathbank-vectors-{self.name}"


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


_SESSION = None


def session():
    global _SESSION
    if _SESSION is None:
        import boto3
        _SESSION = boto3.session.Session(profile_name=PROFILE or None, region_name=REGION)
    return _SESSION


def client(name: str):
    from botocore.config import Config
    return session().client(name, config=Config(retries={"max_attempts": 10, "mode": "adaptive"},
                                                 max_pool_connections=64))


_ACCOUNT = None


def account_id() -> str:
    global _ACCOUNT
    if _ACCOUNT is None:
        _ACCOUNT = client("sts").get_caller_identity()["Account"]
    return _ACCOUNT


# ---------------------------------------------------------------- source (read-only)

def source_dsn() -> str:
    missing = [k for k in ("NEON_PG_HOST", "NEON_PG_DATABASE", "NEON_PG_USER", "NEON_PG_PASSWORD") if not os.environ.get(k)]
    if missing:
        raise SystemExit(f"missing {missing}: source mathbank-graph/remote.env (see aws/README.md)")
    return (f"host={os.environ['NEON_PG_HOST']} port={os.environ.get('NEON_PG_PORT', '5432')} "
            f"dbname={os.environ['NEON_PG_DATABASE']} user={os.environ['NEON_PG_USER']} "
            f"password={os.environ['NEON_PG_PASSWORD']} sslmode={os.environ.get('NEON_PG_SSLMODE', 'require')} "
            f"application_name=mathbank-aws-migration")


@contextmanager
def source() -> Iterator[Any]:
    """Read-only psycopg connection. The pooled Neon endpoint rejects startup options, so the
    read-only flag is set with SET and verified before returning."""
    import psycopg
    from psycopg.rows import dict_row
    conn = psycopg.connect(source_dsn(), row_factory=dict_row, autocommit=True)
    try:
        conn.execute("SET default_transaction_read_only = on")
        conn.execute("SET statement_timeout = '15min'")
        assert conn.execute("SHOW default_transaction_read_only").fetchone()["default_transaction_read_only"] == "on"
        yield conn
    finally:
        conn.close()


def stream(conn, sql: str, params: dict | None = None, itersize: int = 2000) -> Iterator[dict]:
    """Server-side cursor inside one read-only transaction."""
    with conn.transaction():
        with conn.cursor(name=f"mb_{uuid.uuid4().hex[:12]}") as cur:
            cur.itersize = itersize
            cur.execute(sql, params or {})
            yield from cur


# ---------------------------------------------------------------- conversion and hashing

def to_ddb(v: Any) -> Any:
    """Python/psycopg value → DynamoDB-safe value (no floats, no None at top level handled by caller)."""
    if v is None or isinstance(v, (str, bool)):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        if v != v or v in (float("inf"), float("-inf")):
            return str(v)
        return decimal.Decimal(repr(v))
    if isinstance(v, decimal.Decimal):
        return v if v.is_finite() else str(v)
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, dt.datetime):
        if v.tzinfo is not None:
            v = v.astimezone(dt.timezone.utc).replace(tzinfo=None)
        return v.isoformat(timespec="microseconds") + "Z"
    if isinstance(v, (dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, dt.timedelta):
        return decimal.Decimal(str(v.total_seconds()))
    if isinstance(v, (bytes, bytearray, memoryview)):
        return bytes(v)
    if isinstance(v, dict):
        return {str(k): to_ddb(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [to_ddb(x) for x in v]
    if isinstance(v, (set, frozenset)):
        return [to_ddb(x) for x in sorted(v, key=str)]
    return str(v)


def clean_item(item: dict) -> dict:
    """Drop top-level None/empty-set attributes and convert values."""
    return {k: to_ddb(v) for k, v in item.items() if v is not None}


def _canon(v: Any) -> Any:
    if isinstance(v, decimal.Decimal):
        n = v.normalize()
        return {"N": format(n, "f") if n == n.to_integral_value() or abs(n.adjusted()) < 30 else str(n)}
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return _canon(decimal.Decimal(v))
    if isinstance(v, (bytes, bytearray)):
        return {"B": base64.b64encode(bytes(v)).decode()}
    if hasattr(v, "value") and type(v).__name__ == "Binary":
        return {"B": base64.b64encode(bytes(v.value)).decode()}
    if isinstance(v, dict):
        return {k: _canon(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_canon(x) for x in v]
    if isinstance(v, (set, frozenset)):
        return sorted((_canon(x) for x in v), key=lambda x: json.dumps(x, sort_keys=True))
    return v


def item_hash(item: dict) -> str:
    """Stable sha256 of an item as written to / read back from DynamoDB."""
    return hashlib.sha256(json.dumps(_canon(item), sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def json_bytes(obj: Any) -> bytes:
    def default(o):
        if isinstance(o, decimal.Decimal):
            return int(o) if o == o.to_integral_value() else float(o)
        if isinstance(o, (bytes, bytearray)):
            return base64.b64encode(bytes(o)).decode()
        return str(o)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=default).encode()


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def run_id() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(json_bytes(obj))
