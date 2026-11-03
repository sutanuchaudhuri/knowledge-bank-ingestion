"""Request paths must never scan DynamoDB (requirement 70 §5, requirement 71 §2.3)."""
from __future__ import annotations

import ast
from pathlib import Path

STORES = Path(__file__).resolve().parents[2] / "src" / "mathbank_rest" / "stores"
FORBIDDEN = {"scan", "batch_write_item"}  # runtime IAM denies both as well; bulk work belongs to workers/


def _calls(path: Path):
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if name in FORBIDDEN:
                yield node.lineno, name


def test_stores_contain_no_scan_or_batch_write():
    offenders = [f"{p.relative_to(STORES)}:{line} {name}" for p in STORES.rglob("*.py") for line, name in _calls(p)]
    assert offenders == [], "scan/batch_write_item are forbidden in stores/**: " + ", ".join(offenders)


def test_lint_detects_a_scan_call(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text("def x(c):\n    return c.scan(TableName='t')\n")
    assert list(_calls(f)) == [(2, "scan")]
