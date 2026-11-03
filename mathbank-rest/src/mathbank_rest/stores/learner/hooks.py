"""Step-outcome hook contract between the solve runtime and the diagnosis store (requirement 70 C1 T12/T13).

``record_step_outcome`` (solve area) builds ONE transaction. When a step fails it must ask the diagnosis area whether an
automatic diagnosis fires and, if so, add its items (DIAG + fingerprint sentinel + GAPs + events) to the SAME transaction, as long as
the total stays within the 100-item budget. The two areas are implemented independently, so they meet only here:

* the solve area calls ``run_auto_diagnose(uow, ctx)`` (a no-op returning ``False`` until the diagnosis area registers);
* the diagnosis area calls ``register_auto_diagnose(fn)`` at import time of ``stores/learner/diagnosis.py``.

``ctx`` is a plain dict with (at least) ``student_id``, ``attempt_id``, ``solve`` (the SOLVE item model), ``step_state`` (the
STEPSTATE item model after the outcome was applied), ``outcome`` (the step outcome string), ``budget`` (items still available,
``uow.remaining()``). The hook returns ``True`` when it added items, ``False`` when no diagnosis fired or it did not fit
(skipped exactly like the PostgreSQL savepoint failure today; the solve outcome is never lost to a diagnosis problem).
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from mathbank_rest.stores.learner.uow import LearnerUnitOfWork

LOG = logging.getLogger(__name__)
AutoDiagnose = Callable[[LearnerUnitOfWork, dict[str, Any]], bool]
_auto_diagnose: AutoDiagnose | None = None


def register_auto_diagnose(fn: AutoDiagnose | None) -> None:
    global _auto_diagnose
    _auto_diagnose = fn


def run_auto_diagnose(uow: LearnerUnitOfWork, ctx: dict[str, Any]) -> bool:
    if _auto_diagnose is None:
        return False
    try:
        return bool(_auto_diagnose(uow, {**ctx, "budget": uow.remaining()}))
    except Exception:
        LOG.exception("auto-diagnosis failed; the step outcome is committed without it")
        return False
