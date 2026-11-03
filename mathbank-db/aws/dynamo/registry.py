"""Load spec modules and resolve tables/mappings."""
from __future__ import annotations

import importlib

from .spec import Mapping, Table
from .specs import CONTEXTS


def load(names: list[str] | None = None):
    mods = []
    for n in names or CONTEXTS:
        if n not in CONTEXTS:
            raise SystemExit(f"unknown spec {n!r}; choose from {CONTEXTS}")
        mods.append(importlib.import_module(f"aws.dynamo.specs.{n}"))
    return mods


def tables(mods) -> dict[str, Table]:
    out: dict[str, Table] = {}
    for m in mods:
        for t in getattr(m, "TABLES", []):
            if t.ctx in out and out[t.ctx] != t:
                raise SystemExit(f"table {t.ctx} defined twice with different settings")
            out[t.ctx] = t
    return out


def mappings(mods) -> list[Mapping]:
    seen, out = set(), []
    for m in mods:
        for mp in getattr(m, "MAPPINGS", []):
            if mp.name in seen:
                raise SystemExit(f"duplicate mapping name {mp.name}")
            seen.add(mp.name)
            out.append(mp)
    return out


def offload(mods) -> dict[tuple[str, str], tuple[str, ...]]:
    """Merge module-level OFFLOAD policies: {(table ctx, item type): (attr, ...)}."""
    out: dict[tuple[str, str], tuple[str, ...]] = {}
    for m in mods:
        for k, attrs in getattr(m, "OFFLOAD", {}).items():
            out[k] = tuple(dict.fromkeys(out.get(k, ()) + tuple(attrs)))
    return out
