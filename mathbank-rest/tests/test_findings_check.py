"""Findings ledger rules (requirement 71 §4)."""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("findings_check", Path(__file__).resolve().parents[1] / "scripts" / "findings_check.py")
fc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fc)

HEADER = ["id", "schema_doc", "kind", "priority", "design_owner", "primary_wp", "secondary_wps", "rest_impact",
          "item_abridged", "status", "pr", "tests", "routing_note"]


def row(i="LRN-F01", wp="WP5", status="PLANNED", pr="", tests="", note=""):
    return dict(zip(HEADER, [i, "learner", "F", "P1", "C1", wp, "", "Y", "x", status, pr, tests, note]))


def write(tmp_path, rows):
    p = tmp_path / "ledger.csv"
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, HEADER)
        w.writeheader()
        w.writerows(rows)
    return p


def test_real_ledger_is_complete_and_valid():
    rows = fc.load()
    assert len(rows) == 760 and len({r["id"] for r in rows}) == 760
    assert fc.validate(rows) == []
    assert {r["kind"] for r in rows} == {"F", "S", "E"}


@pytest.mark.parametrize("bad,why", [
    (row(status="DONE"), "DONE needs both"),
    (row(status="DONE", pr="abc123"), "DONE needs both"),
    (row(status="DONE", tests="tests/x.py"), "DONE needs both"),
    (row(status="DECLINED"), "DECLINED needs a reason"),
    (row(status="MAYBE"), "not in"),
    (row(wp="C7"), "not a work package")])
def test_invalid_rows_are_reported(bad, why):
    assert any(why in p for p in fc.validate([bad]))


def test_valid_closed_rows_pass():
    assert fc.validate([row(status="DONE", pr="abc123", tests="tests/x.py::t"),
                        row("LRN-F02", status="DECLINED", note="replaced by LRN-F03"), row("LRN-F03")]) == []


def test_duplicate_ids_are_reported():
    assert any("duplicate" in p for p in fc.validate([row(), row()]))


def test_exit_codes(tmp_path, capsys):
    done = row("A-F01", "WP1", "DONE", "abc", "t")
    ledger = write(tmp_path, [done, row("B-F01", "WP2")])
    assert fc.main(["--ledger", str(ledger)]) == 0                    # report only
    assert fc.main(["--ledger", str(ledger), "--wp", "WP1"]) == 0     # WP1 is closed
    assert fc.main(["--ledger", str(ledger), "--wp", "WP2"]) == 2     # WP2 still open
    assert fc.main(["--ledger", str(ledger), "--strict"]) == 2        # merge gate: something is open
    assert fc.main(["--ledger", str(write(tmp_path, [row(status="DONE")])), "--wp", "WP5"]) == 1  # invalid row
    err = capsys.readouterr().err
    assert "NOT COMPLETE" in err and "invalid row" in err


def test_strict_gate_passes_only_when_everything_is_closed(tmp_path):
    ledger = write(tmp_path, [row("A-F01", "WP1", "DONE", "abc", "t"), row("B-F01", "WP2", "DECLINED", note="why")])
    assert fc.main(["--ledger", str(ledger), "--strict"]) == 0


def test_real_ledger_fails_the_merge_gate_today():
    assert fc.main(["--strict"]) == 2
