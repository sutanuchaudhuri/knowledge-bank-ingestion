"""Runtime app (requirement 71): learner/agent/live traffic with no PostgreSQL access.

Sets MB_APP_PROFILE=runtime *before* configuration is imported, so `db/postgres.py` hands out a guard instead
of a database engine. Run locally with `uvicorn mathbank_rest.app_runtime:app`.
"""
from __future__ import annotations

import os

os.environ.setdefault("MB_APP_PROFILE", "runtime")

from mathbank_rest.profiles import create_app

app = create_app("runtime")
