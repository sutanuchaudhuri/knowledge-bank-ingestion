"""The app under API test: the runtime profile (no PostgreSQL) plus every router already moved onto a store.

`uvicorn apitest.app:app` — the harness starts it; see apitest/server.py.
"""
from __future__ import annotations

import os

os.environ.setdefault("MB_APP_PROFILE", "runtime")

from mathbank_rest.profiles import create_app  # noqa: E402

# WP6 routers are store-backed but stay in RUNTIME_PENDING until the zero-Postgres gate passes.
app = create_app("runtime", extra=("quiz_runtime", "exam_integration"))
