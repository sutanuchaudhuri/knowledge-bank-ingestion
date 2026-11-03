"""Context stores must use the typed layer, not raw dict helpers (requirement 71 §2.10).

Any `stores/<context>/dynamodb*.py` talks to DynamoDB through `stores.typed` (models in, models out), so every read
is validated into its pydantic model and every write is strict. Raw `ddb.get_item/put_item/query_page/batch_get/
cas_update` are reserved for `stores/ddb.py` and `stores/typed.py` themselves.
"""
from __future__ import annotations

import ast
from pathlib import Path

STORES = Path(__file__).resolve().parents[2] / "src" / "mathbank_rest" / "stores"
RAW = {"get_item", "put_item", "query_page", "batch_get", "cas_update", "encode_item"}


def _raw_calls(path: Path):
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in RAW:
            owner = node.func.value
            if getattr(owner, "id", "") in ("ddb", "toolkit"):
                yield node.lineno, node.func.attr


def test_context_stores_do_not_use_raw_item_helpers():
    offenders = [f"{p.relative_to(STORES)}:{line} ddb.{name}" for p in STORES.glob("*/dynamodb*.py") for line, name in _raw_calls(p)]
    assert offenders == [], "use stores.typed (models in/out) instead of raw dicts: " + ", ".join(offenders)


def test_lint_detects_a_raw_call(tmp_path):
    f = tmp_path / "dynamodb.py"
    f.write_text("from mathbank_rest.stores import ddb\n\ndef x():\n    return ddb.get_item('learner', 'a', 'b')\n")
    assert list(_raw_calls(f)) == [(4, "get_item")]
