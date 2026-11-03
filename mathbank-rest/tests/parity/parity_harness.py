"""Dual-backend contract parity (requirement 71 §5).

A work package that moves a context to DynamoDB writes ParityCase objects for its routes and runs them against
two TestClients built from the same app, one with the context on `postgres` and one on `dynamodb`. The
responses must match structurally. Differences that the design allows are listed explicitly (`allowed`), so an
unexplained difference fails the test rather than being normalised away.

    clients = {"postgres": TestClient(app_pg), "dynamodb": TestClient(app_ddb)}
    assert_parity(clients, ParityCase("start attempt", "POST", "/v1/attempts", json={...}),
                  allowed=["$.version"])          # design: DynamoDB reports item version, SQL did not
"""
from __future__ import annotations

import dataclasses
import re
from collections.abc import Iterable
from typing import Any

BACKENDS = ("postgres", "dynamodb")
# Generated per request or per backend; never part of the contract.
VOLATILE_KEYS = frozenset({"request_id", "next_token", "created_at", "updated_at", "ttl", "served_at", "elapsed_ms"})


@dataclasses.dataclass
class ParityCase:
    name: str
    method: str
    path: str
    json: Any = None
    params: dict | None = None
    headers: dict | None = None
    expect_status: int | None = None        # when set, both backends must return exactly this status
    unordered: tuple[str, ...] = ()         # JSON paths (e.g. "$.items") whose lists compare as sets of items


def _walk(a: Any, b: Any, path: str, ignore: frozenset, unordered: tuple[str, ...], out: list[str]) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k in ignore:
                continue
            p = f"{path}.{k}"
            if k not in a:
                out.append(f"{p}: only in dynamodb → {b[k]!r}"[:200])
            elif k not in b:
                out.append(f"{p}: only in postgres → {a[k]!r}"[:200])
            else:
                _walk(a[k], b[k], p, ignore, unordered, out)
    elif isinstance(a, list) and isinstance(b, list):
        if path in unordered:
            key = lambda x: repr(_strip(x, ignore))
            a, b = sorted(a, key=key), sorted(b, key=key)
        if len(a) != len(b):
            out.append(f"{path}: length {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            _walk(x, y, f"{path}[{i}]", ignore, unordered, out)
    elif a != b:
        out.append(f"{path}: {a!r} vs {b!r}"[:200])


def _strip(x: Any, ignore: frozenset) -> Any:
    if isinstance(x, dict):
        return {k: _strip(v, ignore) for k, v in x.items() if k not in ignore}
    if isinstance(x, list):
        return [_strip(v, ignore) for v in x]
    return x


def _pattern(pat: str) -> re.Pattern[str]:
    """JSON-path pattern -> regex where only `*` is a wildcard (so `[*]` means any list index)."""
    return re.compile(re.escape(pat).replace(r"\*", ".*"))


def diff(a: Any, b: Any, *, ignore: Iterable[str] = VOLATILE_KEYS, allowed: Iterable[str] = (),
         unordered: Iterable[str] = ()) -> list[str]:
    """Structural differences between two JSON values, minus volatile keys and `allowed` path patterns
    (`*` is a wildcard, e.g. "$.items[*].rank"). Each entry starts with its path."""
    out: list[str] = []
    _walk(a, b, "$", frozenset(ignore), tuple(unordered), out)
    pats = [_pattern(p) for p in allowed]
    return [d for d in out if not any(p.fullmatch(d.split(":", 1)[0]) for p in pats)]


def run_case(clients: dict, case: ParityCase) -> dict[str, tuple[int, Any]]:
    res = {}
    for backend, client in clients.items():
        r = client.request(case.method, case.path, json=case.json, params=case.params, headers=case.headers)
        try:
            body = r.json()
        except ValueError:
            body = r.text
        res[backend] = (r.status_code, body)
    return res


def assert_parity(clients: dict, case: ParityCase, *, allowed: Iterable[str] = ()) -> dict:
    """Run `case` on every backend; fail with a readable report if status or body differ unexpectedly."""
    res = run_case(clients, case)
    (b0, (s0, j0)), (b1, (s1, j1)) = list(res.items())[:2]
    problems: list[str] = []
    if s0 != s1:
        problems.append(f"status: {b0}={s0} {b1}={s1}")
    if case.expect_status is not None and (s0, s1) != (case.expect_status, case.expect_status):
        problems.append(f"expected status {case.expect_status}, got {s0}/{s1}")
    problems += diff(j0, j1, allowed=allowed, unordered=case.unordered)
    assert not problems, f"parity failed for {case.name!r} ({case.method} {case.path}):\n  " + "\n  ".join(problems)
    return res
