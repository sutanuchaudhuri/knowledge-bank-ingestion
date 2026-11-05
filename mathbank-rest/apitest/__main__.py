"""python -m apitest --mode dev-readonly|test-writable [--suite sweep|journeys|all] [--only name ...] [--base-url URL]

Starts a real local uvicorn process (unless --base-url is given), runs the suites over HTTP against real AWS and writes
apitest/reports/<timestamp>/report.{md,json}. Exit code 1 when any check fails.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

from apitest.server import MODES, server_env

PROFILE_DEFAULT = "aws-sutanu-admin"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="apitest")
    ap.add_argument("--mode", choices=MODES, required=True)
    ap.add_argument("--suite", choices=("sweep", "journeys", "all"), default="all")
    ap.add_argument("--only", nargs="*", default=[], help="journey names (or sweep case names) to run")
    ap.add_argument("--profile", default=os.environ.get("MB_AWS_PROFILE") or PROFILE_DEFAULT)
    ap.add_argument("--base-url", help="use an already running API (it must have been started in the same mode)")
    ap.add_argument("--port", type=int)
    args = ap.parse_args(argv)

    # The harness process itself reads AWS for fixture discovery, so it gets the same guarded configuration as the server.
    os.environ.update(server_env(args.mode, args.profile))

    from apitest import report
    from apitest.client import Api, Recorder
    from apitest.context import Ctx
    from apitest.server import running

    out_dir = report.REPORTS
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / f"server-{args.mode}.log"
    rec = Recorder()

    def run(base: str) -> None:
        from mathbank_rest.config import settings

        api = Api(base, rec, admin_key=settings.admin_api_key.get_secret_value() if hasattr(settings.admin_api_key, "get_secret_value")
                  else str(settings.admin_api_key or ""))
        ctx = Ctx(api=api, rec=rec, mode=args.mode)
        if args.suite in ("sweep", "all"):
            from apitest import sweep

            sweep.run(ctx, only=args.only)
        if args.suite in ("journeys", "all"):
            if not ctx.writable:
                print("journeys skipped: they write data and only run with --mode test-writable")
            else:
                from apitest.journeys import load_all

                for name, fn in load_all().items():
                    if args.only and name not in args.only:
                        continue
                    rec.suite = f"journey:{name}"
                    try:
                        fn(ctx)
                    except Exception as exc:  # noqa: BLE001 -- a crashing journey is a recorded failure, not an abort
                        rec.add(case="journey crashed", method="-", path="-", status=None, ms=0, ok=False,
                                note=f"{type(exc).__name__}: {exc}")

    if args.base_url:
        run(args.base_url)
        findings_log = None
    else:
        with running(args.mode, args.profile, log_path, port=args.port) as base:
            run(base)
        findings_log = log_path
    meta = {"mode": args.mode, "when": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "profile": args.profile}
    out = report.write(rec, meta, findings_log)
    total, bad = len(rec.exchanges), len(rec.failures)
    print(f"{total} checks, {bad} failed -> {out}/report.md")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
