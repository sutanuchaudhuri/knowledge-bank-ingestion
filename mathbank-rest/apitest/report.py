"""Write the run report: JSON (machine) and Markdown (human) under apitest/reports/<timestamp>/."""
from __future__ import annotations

import collections
import datetime as dt
import json
import re
from pathlib import Path

from apitest.client import Recorder

REPORTS = Path(__file__).resolve().parent / "reports"
TRACE = re.compile(r"Traceback \(most recent call last\)")


def log_findings(log_path: Path) -> dict:
    text = log_path.read_text(errors="replace") if log_path.exists() else ""
    return {"tracebacks": len(TRACE.findall(text)), "error_lines": sum(1 for ln in text.splitlines() if " ERROR" in ln)}


def write(rec: Recorder, meta: dict, log_path: Path | None = None) -> Path:
    out = REPORTS / dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=True)
    findings = log_findings(log_path) if log_path else {}
    by_suite: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for e in rec.exchanges:
        by_suite[e.suite]["pass" if e.ok else "fail"] += 1
    (out / "report.json").write_text(json.dumps({"meta": meta, "server_log": findings, "summary": {k: dict(v) for k, v in by_suite.items()},
                                                 "exchanges": [e.__dict__ for e in rec.exchanges]}, indent=1))
    lines = [f"# API test report — {meta.get('mode')} — {meta.get('when')}", "", f"Server log: {findings}", "",
             "| suite | pass | fail |", "|---|---|---|"]
    lines += [f"| {s} | {c['pass']} | {c['fail']} |" for s, c in sorted(by_suite.items())]
    fails = rec.failures
    lines += ["", f"## Failures ({len(fails)})", ""]
    lines += [f"- **{e.suite}/{e.case}** `{e.method} {e.path}` → {e.status} ({e.ms} ms) {e.note}\n  `{e.body[:240]!r}`" for e in fails]
    slow = sorted(rec.exchanges, key=lambda e: -e.ms)[:15]
    lines += ["", "## Slowest", ""] + [f"- {e.ms} ms `{e.method} {e.path}` ({e.suite}/{e.case})" for e in slow]
    (out / "report.md").write_text("\n".join(lines) + "\n")
    return out
