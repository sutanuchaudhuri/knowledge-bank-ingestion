"""Admin / authoring app (requirement 71): PostgreSQL-backed authoring, import, review and release routers.

Run locally with `uvicorn mathbank_rest.app_admin:app`. `main.py` remains the combined app that mounts everything.
"""
from __future__ import annotations

import os

os.environ.setdefault("MB_APP_PROFILE", "admin")

from mathbank_rest.profiles import create_app

app = create_app("admin")
