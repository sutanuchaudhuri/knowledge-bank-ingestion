"""File-only credentials shared by classifiers and reviewers."""
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]


def configure_openai() -> str:
    sys.path.insert(0, str(SERVICE_ROOT.parent / "scripts"))
    from project_env import load_project_openai

    return load_project_openai(SERVICE_ROOT / ".env")
