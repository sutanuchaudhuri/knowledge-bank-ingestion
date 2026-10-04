"""Agent-level eval — tool-selection accuracy + basic safety checks, per
mathematics_tutor_db_plan/agent/16_observability_and_evaluation.md section 2
("tool-selection accuracy") and section 3 ("golden evaluation set").

Runs each golden case (scripts/golden_agent_cases.py) through the REAL ADK
agent + OpenAI, using the same Runner/InMemorySessionService pattern as
scripts/smoke_test.py, and inspects which tools were actually invoked during
the turn. This is a black-box eval of the live agentic layer — not a mock.

Needs mathbank-rest already running (MATHBANK_REST_BASE_URL) and
OPENAI_API_KEY set. Costs OpenAI credits (one real agent turn per case) — not
meant to run on every commit, same caveat as mathbank-rest's eval-retrieval.

Usage:
    cd mathbank-agent
    .venv/bin/python scripts/evaluate_agent.py
    .venv/bin/python scripts/evaluate_agent.py --case scaffold-decompose
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import datetime as dt
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from golden_agent_cases import GOLDEN_AGENT_CASES, GoldenAgentCase
from mathbank_tutor.agent import root_agent

EVAL_HISTORY_PATH = ROOT / "eval_history.csv"
_CSV_FIELDS = ["run_at", "git_sha", "case", "query", "expected_tools", "tools_called", "passed", "notes"]


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


async def _run_case(case: GoldenAgentCase, session_id: str) -> tuple[list[str], str]:
    """Returns (tool_names_called, final_text)."""
    session_service = InMemorySessionService()
    await session_service.create_session(app_name="mathbank_tutor_eval", user_id="eval", session_id=session_id)
    runner = Runner(agent=root_agent, app_name="mathbank_tutor_eval", session_service=session_service)

    message = types.Content(role="user", parts=[types.Part(text=case.query)])
    tools_called: list[str] = []
    final_text = ""
    async for event in runner.run_async(user_id="eval", session_id=session_id, new_message=message):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call:
                    tools_called.append(part.function_call.name)
                if part.text:
                    final_text = part.text
    return tools_called, final_text


def _judge(case: GoldenAgentCase, tools_called: list[str]) -> tuple[bool, str]:
    forbidden_hit = [t for t in case.forbidden_tools if t in tools_called]
    if forbidden_hit:
        return False, f"forbidden tool(s) called: {forbidden_hit}"
    if not case.expected_tools:
        return True, "no specific tool required; no forbidden tool called"
    expected_hit = [t for t in case.expected_tools if t in tools_called]
    if expected_hit:
        return True, f"expected tool(s) called: {expected_hit}"
    return False, f"none of expected {case.expected_tools} were called"


async def _run_all(cases: list[GoldenAgentCase]) -> list[dict]:
    rows: list[dict] = []
    for i, case in enumerate(cases):
        print(f"\n=== {case.name} ===\n  query: {case.query!r}")
        tools_called, final_text = await _run_case(case, session_id=f"eval-{i}")
        passed, reason = _judge(case, tools_called)
        print(f"  tools called: {tools_called}")
        print(f"  {'PASS' if passed else 'FAIL'} — {reason}")
        if final_text:
            print(f"  final text (truncated): {final_text[:160]!r}")
        rows.append({
            "run_at": _now(), "git_sha": _git_sha(), "case": case.name, "query": case.query,
            "expected_tools": ",".join(case.expected_tools), "tools_called": ",".join(tools_called),
            "passed": passed, "notes": reason,
        })
    return rows


def _append_history(log_file: Path | None, rows: list[dict]) -> None:
    if log_file is None:
        return
    is_new = not log_file.exists()
    with open(log_file, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        if is_new:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", default=None, help="Run only the named case (default: all)")
    parser.add_argument("--log-file", default=str(EVAL_HISTORY_PATH), help="CSV to append to ('' disables)")
    args = parser.parse_args()

    cases = GOLDEN_AGENT_CASES
    if args.case:
        cases = [c for c in cases if c.name == args.case]
        if not cases:
            print(f"No golden case named {args.case!r}. Available: {[c.name for c in GOLDEN_AGENT_CASES]}")
            sys.exit(1)

    rows = asyncio.run(_run_all(cases))
    log_file = Path(args.log_file) if args.log_file else None
    _append_history(log_file, rows)

    n_passed = sum(1 for r in rows if r["passed"])
    print(f"\n{n_passed}/{len(rows)} passed.")
    if log_file:
        print(f"Appended results to {log_file}")
    sys.exit(0 if n_passed == len(rows) else 1)


if __name__ == "__main__":
    main()
