"""File-only OpenAI credentials for this repository; never read shell profiles."""
from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import dotenv_values

PROVIDER_KEYS = (
    "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE",
    "OPENAI_ORGANIZATION", "OPENAI_ORG_ID", "OPENAI_PROJECT",
)


def load_project_openai(service_env: Path) -> str:
    service_env = service_env.resolve()
    root_env = service_env.parent.parent / ".env"
    source = root_env if root_env.is_file() else service_env
    root_values = dotenv_values(source, interpolate=False)
    service_values = dotenv_values(service_env, interpolate=False)
    key = root_values.get("OPENAI_API_KEY") or ""
    invalid = re.search(r"""[\s"'`\\#$]""", key) or re.match(
        r"^(change-me|your[-_]|<)", key, re.I
    )
    if not key or invalid:
        raise RuntimeError(
            f"Set a literal OPENAI_API_KEY in {source}; shell credentials are ignored. "
            "Run make sync-openai-key after updating the root .env."
        )
    for name in PROVIDER_KEYS:
        value = root_values.get(name) or service_values.get(name)
        if name == "OPENAI_API_KEY":
            value = key
        if value:
            os.environ[name] = value
        else:
            os.environ.pop(name, None)
    return key
