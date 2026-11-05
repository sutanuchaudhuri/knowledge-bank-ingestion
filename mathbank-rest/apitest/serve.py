"""python -m apitest.serve --mode dev-readonly|test-writable [--port 8000]

Run the API in the foreground against real AWS for manual exploration (Bruno, curl, the web UI).
dev-readonly: real migrated data, every AWS write is refused. test-writable: state in `test`, content/vectors read from `dev`.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from apitest.server import MODES, ROOT, server_env


def main() -> None:
    ap = argparse.ArgumentParser(prog="apitest.serve")
    ap.add_argument("--mode", choices=MODES, default="dev-readonly")
    ap.add_argument("--profile", default=os.environ.get("MB_AWS_PROFILE") or "aws-sutanu-admin")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    env = server_env(a.mode, a.profile)
    print(f"API on http://127.0.0.1:{a.port}  mode={a.mode}  aws-profile={a.profile}", flush=True)
    os.chdir(Path(ROOT))
    os.execvpe(sys.executable, [sys.executable, "-m", "uvicorn", "apitest.app:app", "--app-dir", str(ROOT), "--port", str(a.port)], env)


if __name__ == "__main__":
    main()
