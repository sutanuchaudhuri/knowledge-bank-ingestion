"""Optional pre-write validation of migrated items against the REST pydantic models (requirement 71 §2.10).

    MB_VALIDATE_MODELS=1     abort the run on the first item that violates its model
    MB_VALIDATE_MODELS=warn  log and count violations, keep copying

Needs the mathbank-rest dependencies (pydantic, pydantic-settings, fastapi): run the migration with
`mathbank-rest/.venv/bin/python` and `PYTHONPATH=<repo>/mathbank-db`. Item types without a model (new contexts)
are skipped, so adding a spec never blocks a copy before its model exists. The post-copy check of everything in the
table is `make -C mathbank-rest ddb-models-validate`.
"""
from __future__ import annotations

import collections
import os
import sys
from pathlib import Path
from typing import Callable

MODE = os.environ.get("MB_VALIDATE_MODELS", "").lower()


def make_gate() -> Callable[[str, dict], None] | None:
    if MODE not in ("1", "true", "warn"):
        return None
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "mathbank-rest" / "src"))
    from mathbank_rest.models import base                      # noqa: PLC0415 - optional heavy import
    from mathbank_rest.stores.errors import ItemSchemaError    # noqa: PLC0415

    base._load_models()
    counts: collections.Counter = collections.Counter()

    def gate(table: str, item: dict) -> None:
        model = base.model_for(table.replace("-", "_"), item["type"])
        if model is None:
            counts["no_model"] += 1
            return
        try:
            model.from_item(item).to_item()
            counts["ok"] += 1
        except ItemSchemaError as exc:
            counts["violations"] += 1
            if MODE != "warn":
                raise
            print(f"model violation {table}/{item['type']} {item['PK']} {item['SK']}: {exc.detail.get('errors') or exc.message}", file=sys.stderr)

    gate.counts = counts  # type: ignore[attr-defined]
    return gate
