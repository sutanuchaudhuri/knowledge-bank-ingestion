"""Start/stop the local API process with a given AWS environment and wait until it is healthy."""
from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
STORES = ("content", "learner", "exam", "jobs", "notify")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


MODES = ("dev-readonly", "test-writable")


def server_env(mode: str, profile: str) -> dict[str, str]:
    """dev-readonly: real data, every AWS write refused. test-writable: runtime state in `test`, published content and
    vectors read from `dev`; writes are allowed only to `-test` resources, so dev cannot be mutated by a bug."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    e = dict(os.environ)
    e.update({"MB_AWS_PROFILE": profile, "AWS_PROFILE": profile, "VECTOR_STORE": "s3vectors", "MB_APP_PROFILE": "runtime",
              "DDB_STARTUP_CHECK": "true", "PYTHONUNBUFFERED": "1"})
    if mode == "dev-readonly":
        e.update({"DDB_ENV": "dev", "MB_AWS_READONLY": "1", "MB_AWS_WRITE_ENVS": "", "MB_DDB_ENV_OVERRIDES": ""})
    else:
        e.update({"DDB_ENV": "test", "MB_AWS_READONLY": "0", "MB_AWS_WRITE_ENVS": "test",
                  "MB_DDB_ENV_OVERRIDES": "content=dev,vectors=dev"})
    for ctx in STORES:
        e[f"{ctx.upper()}_STORE"] = "dynamodb"
    return e


@contextlib.contextmanager
def running(mode: str, profile: str, log_path: Path, port: int | None = None, timeout: float = 90.0):
    port = port or free_port()
    log = open(log_path, "w")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "apitest.app:app", "--app-dir", str(ROOT), "--port", str(port),
                             "--log-level", "info"], cwd=ROOT, env=server_env(mode, profile), stdout=log,
                            stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + timeout
        while True:
            if proc.poll() is not None:
                raise RuntimeError(f"API exited during startup (code {proc.returncode}); see {log_path}")
            try:
                if httpx.get(f"{base}/health", timeout=3).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.time() > deadline:
                raise RuntimeError(f"API not healthy after {timeout}s; see {log_path}")
            time.sleep(0.5)
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
