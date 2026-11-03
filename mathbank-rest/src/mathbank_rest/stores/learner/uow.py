"""LearnerUnitOfWork: one atomic ``TransactWriteItems`` for a learner operation (requirement 70 C1 section 4).

    uow = LearnerUnitOfWork(student_id)
    uow.put_new(OUTCOME_item)                              # append-only items: attribute_not_exists(PK)
    uow.update(LearnerSolve, pk, sk, {"current_mode": "RECOVERY"}, expected={"state_version": 2}, bump="state_version")
    uow.add(ddb.Check(...))                                # any toolkit op
    uow.commit()                                           # <= 100 items, conflicts mapped to domain errors

or, for mutations that accept ``Idempotency-Key`` (the receipt is written in the SAME transaction as the effect):

    response, replayed = run_idempotent(student_id, key=key, operation="submit_step_response", body=body,
                                        build=lambda uow: (uow.put_new(...), response_dict)[1])

Rules enforced here so no store re-implements them:

* **Ownership.** Items in a ``STUDENT#<sid>`` partition must be the operation's own student; a foreign id cannot be written.
  Global partitions (``UNIQUE#...`` sentinels, ``<KIND>#<id>`` owner pointers) are allowed, since they carry the owner inside.
* **Append-only types** (OUTCOME, MEVID, EVENT, MCEVENT, IXEVENT, MISCEVID, DIAG) can only be created: ``update``/``delete`` on them
  raises. Creating one always carries ``attribute_not_exists(PK)``.
* **Typed writes.** Items are models (``stores.typed.prepare``: strict, offloaded, re-validated); updates validate each changed
  attribute against its model field before the conditional write.
* **Versions.** ``update`` always does ``SET <bump> = <bump> + 1, updated_at = :now`` and is conditional on the expected
  version / state counters you pass.
* **Size.** ``commit`` refuses more than 100 items; ``remaining()`` tells a builder how much budget is left so optional parts
  (auto-diagnosis, tag evidence) can be skipped or deferred exactly as the design says.
"""
from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

from mathbank_rest.models.base import DdbItem
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.errors import ConditionFailed, StoreError, ValidationFailed

CTX = "learner"
MAX_ITEMS = 100
APPEND_ONLY = frozenset({"OUTCOME", "MEVID", "EVENT", "MCEVENT", "IXEVENT", "MISCEVID", "DIAG"})
T = TypeVar("T")


class LearnerUnitOfWork:
    """Atomic transaction builder over one DynamoDB table; ``CTX`` and ``APPEND_ONLY`` are class attributes so another context
    (``stores/exam/uow.py``) reuses every rule with its own table and append-only types."""

    CTX = CTX
    APPEND_ONLY = APPEND_ONLY

    def __init__(self, student_id: Any) -> None:
        self.student_id = str(student_id)
        self.pk = ddb.student_pk(student_id)
        self._ops: list[ddb.TxOp] = []

    # ------------------------------------------------------------------ introspection

    def __len__(self) -> int:
        return len(self._ops)

    def remaining(self) -> int:
        """Items still available in this transaction (the idempotency receipt takes one more when used)."""
        return MAX_ITEMS - len(self._ops) - 1

    def fits(self, n: int) -> bool:
        return n <= self.remaining()

    # ------------------------------------------------------------------ ownership

    def _own(self, pk: str, what: str) -> None:
        if pk.startswith("STUDENT#") and pk != self.pk:
            raise ValidationFailed(f"{what}: item belongs to another student", pk=pk)

    # ------------------------------------------------------------------ writes

    def put_new(self, item: DdbItem, *, conflict: StoreError | None = None, label: str = "") -> LearnerUnitOfWork:
        """Create-only (``attribute_not_exists(PK)``): the only way to write append-only types."""
        self._own(item.PK, f"put {item.type}")
        self._ops.append(typed.tx_put(item, ddb.NOT_EXISTS, conflict or ConditionFailed(f"{item.type} already exists", op=item.type),
                                      label or item.type))
        return self

    def put(self, item: DdbItem, *, cond: ddb.Cond | None = None, conflict: StoreError | None = None, label: str = "") -> LearnerUnitOfWork:
        """Create or replace an item of a mutable type, optionally conditional (e.g. ``version = :v``)."""
        if item.type in self.APPEND_ONLY:
            raise ValidationFailed(f"{item.type} is append-only: use put_new", type=item.type)
        self._own(item.PK, f"put {item.type}")
        self._ops.append(typed.tx_put(item, cond, conflict, label or item.type))
        return self

    def update(self, model: type[DdbItem], pk: str, sk: str, changes: dict[str, Any], *, expected: dict[str, Any] | None = None,
               bump: str = "version", increment: dict[str, int] | None = None, remove: tuple[str, ...] = (),
               cond: ddb.Cond | None = None, conflict: StoreError | None = None, label: str = "") -> LearnerUnitOfWork:
        """``SET <changes>, <bump> = <bump> + 1, updated_at = :now`` guarded by ``expected`` attribute equalities (optimistic
        concurrency: pass ``{"version": 3}`` or ``{"state_version": 5}``), the item existing, and an extra ``cond``.
        ``increment`` adds to numeric counters (``{"attempt_count": 1}``); ``remove`` drops attributes."""
        if model.TYPE in self.APPEND_ONLY:
            raise ValidationFailed(f"{model.TYPE} is append-only: it cannot be updated", type=model.TYPE)
        self._own(pk, f"update {model.TYPE}")
        sets: list[str] = []
        names: dict[str, str] = {"#upd": "updated_at", "#bump": bump}
        values: dict[str, Any] = {":now": ddb.now_iso(), ":one": 1, ":zero": 0}
        for i, (attr, val) in enumerate(typed.validate_changes(model, changes).items()):
            if attr in ("PK", "SK", bump, "updated_at"):
                raise ValidationFailed(f"cannot set {attr} directly")
            names[f"#c{i}"], values[f":c{i}"] = attr, val
            sets.append(f"#c{i} = :c{i}")
        for i, (attr, by) in enumerate((increment or {}).items()):
            names[f"#i{i}"], values[f":i{i}"] = attr, int(by)
            sets.append(f"#i{i} = if_not_exists(#i{i}, :zero) + :i{i}")
        sets += ["#bump = if_not_exists(#bump, :zero) + :one", "#upd = :now"]
        expr = "SET " + ", ".join(sets)
        if remove:
            for i, attr in enumerate(remove):
                names[f"#r{i}"] = attr
            expr += " REMOVE " + ", ".join(f"#r{i}" for i in range(len(remove)))
        guards = ["attribute_exists(PK)"]
        for i, (attr, val) in enumerate((expected or {}).items()):
            names[f"#e{i}"], values[f":e{i}"] = attr, val
            guards.append(f"#e{i} = :e{i}")
        if cond:
            guards.append(f"({cond.expr})")
            names.update(cond.names)
            values.update(cond.values)
        self._ops.append(ddb.Update(self.CTX, pk, sk, expr, names=names, values=values, cond=ddb.Cond(" AND ".join(guards)),
                                    conflict=conflict, label=label or f"{model.TYPE}:{sk}"))
        return self

    def delete(self, model: type[DdbItem], pk: str, sk: str, *, cond: ddb.Cond | None = None, conflict: StoreError | None = None) -> LearnerUnitOfWork:
        if model.TYPE in self.APPEND_ONLY:
            raise ValidationFailed(f"{model.TYPE} is append-only: it cannot be deleted", type=model.TYPE)
        self._own(pk, f"delete {model.TYPE}")
        self._ops.append(ddb.Delete(self.CTX, pk, sk, cond, conflict, label=model.TYPE))
        return self

    def sentinel(self, field: str, value: Any, owner: dict | None = None, *, ttl: int | None = None) -> LearnerUnitOfWork:
        """Uniqueness sentinel (a PostgreSQL UNIQUE): the transaction fails with ``UniqueViolation(field)`` when taken."""
        self._ops.append(ddb.sentinel_put(self.CTX, field, value, owner, ttl=ttl))
        return self

    def add(self, op: ddb.TxOp) -> LearnerUnitOfWork:
        """Any toolkit op (Check, Put, Update ...) for the rare case the helpers above do not fit."""
        self._ops.append(op)
        return self

    # ------------------------------------------------------------------ commit

    def ops(self) -> list[ddb.TxOp]:
        return list(self._ops)

    def commit(self, *, token: str | None = None) -> None:
        if len(self._ops) > MAX_ITEMS:
            raise StoreError(f"learner transaction has {len(self._ops)} items; the limit is {MAX_ITEMS}", ops=len(self._ops))
        ddb.transact(self._ops, token=token)
        self._ops = []


# ---------------------------------------------------------------------------------------------- helpers

def run_idempotent(student_id: Any, *, key: str | None, operation: str, body: Any,
                   build: Callable[[LearnerUnitOfWork], T], uow_class: type[LearnerUnitOfWork] = LearnerUnitOfWork) -> tuple[T, bool]:
    """Run ``build(uow)`` and commit its ops atomically. With an ``Idempotency-Key`` the receipt is part of the same transaction:
    a repeat of the same request replays the stored response (``replayed=True``); the same key with a different request is 422.
    ``build`` runs at most once per key and returns the response document stored in the receipt. Without a key it just commits."""
    uow = uow_class(student_id)
    if not key:
        response = build(uow)
        uow.commit()
        return response, False

    def stage() -> tuple[list[ddb.TxOp], Any]:
        response = build(uow)
        if len(uow) > MAX_ITEMS - 1:
            raise StoreError(f"learner transaction has {len(uow)} items; with the receipt the limit is {MAX_ITEMS}")
        return uow.ops(), response

    return ddb.run_idempotent(uow.CTX, owner_pk=uow.pk, key=key, req_hash=ddb.request_hash({"operation": operation, "body": body}),
                              build=stage)


def with_retries(fn: Callable[[], T], *, attempts: int = 3, on: tuple[type[Exception], ...] = (ConditionFailed,)) -> T:
    """Retry an operation (reload state, rebuild the transaction, commit) when a SERVER-derived condition failed because a
    concurrent writer got there first. Never use it for the client's own version check: that must surface as 409."""
    for attempt in range(attempts):
        try:
            return fn()
        except on:
            if attempt == attempts - 1:
                raise
            time.sleep(min(0.03 * 2 ** attempt, 0.4) * (0.5 + random.random()))
    raise AssertionError("unreachable")
