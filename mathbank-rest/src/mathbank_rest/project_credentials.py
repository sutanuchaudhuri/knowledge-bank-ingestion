"""Use the shared repository credential loader for REST and teaching workers."""
import os
import re
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]

# Matches load_project_openai's own placeholder/invalid-literal checks (project_env.py),
# so a deployed environment's real key is validated the same way the local .env flow is.
_INVALID_KEY = re.compile(r"""[\s"'`\\#$]""")
_PLACEHOLDER_KEY = re.compile(r"^(change-me|your[-_]|<)", re.I)


def configure_openai() -> str:
    """Resolve the OpenAI API key for this process.

    Deployed environments (Lambda, containers, anywhere outside this repo's own
    monorepo checkout) set `OPENAI_API_KEY` as a real process environment variable —
    honor that directly, with no monorepo-relative filesystem assumption. Only when it
    is absent does this fall back to the repo's own file-only, sibling-`mathbank-scripts`
    loader (`project_env.load_project_openai`), which is what every local dev/test run
    already exercises, since a bare `OPENAI_API_KEY` env var is not normally set outside
    a deployed environment — this preserves that behavior unchanged.
    """
    env_key = os.environ.get("OPENAI_API_KEY", "")
    if env_key and not _INVALID_KEY.search(env_key) and not _PLACEHOLDER_KEY.match(env_key):
        return env_key

    sys.path.insert(0, str(SERVICE_ROOT.parent / "mathbank-scripts"))
    from project_env import load_project_openai

    return load_project_openai(SERVICE_ROOT / ".env")
