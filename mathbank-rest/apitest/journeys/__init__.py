"""Write journeys: end-to-end flows that create data. They run only in `test-writable` mode (writes go to `-test` resources).

A journey is `def my_journey(ctx: Ctx) -> None` registered with `@journey("name")`; it records every step through
`ctx.api.expect(...)` and must never raise for an HTTP failure (a failed step is a recorded failure, later steps are skipped
with `return`). Journeys must create their own data (register a fresh learner, etc.), read published content only through the API,
and never depend on another journey having run.
"""
from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable

from apitest.context import Ctx

JOURNEYS: dict[str, Callable[[Ctx], None]] = {}


def journey(name: str):
    def deco(fn: Callable[[Ctx], None]):
        assert name not in JOURNEYS, f"duplicate journey {name}"
        JOURNEYS[name] = fn
        fn.journey_name = name
        return fn
    return deco


def load_all() -> dict[str, Callable[[Ctx], None]]:
    for m in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{__name__}.{m.name}")
    return JOURNEYS
